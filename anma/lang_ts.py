"""TypeScript language adapter for the ANMA boundary engine.

Implements the :class:`anma.adapters.LanguageAdapter` protocol for TypeScript with
ZERO changes to the neutral layers. Like the Go adapter it is a leaf module
(imports only :mod:`anma.engine` + :mod:`anma.contracts`) and is registered from
:mod:`anma.adapters` at import time.

Design (see DECISIONS.md):

* Import identity is the **tsconfig-resolved specifier** a sibling would write —
  derived purely from the cached ``tsconfig.json`` (``baseUrl`` / ``paths``), e.g.
  ``@app/billing`` or ``domains/billing``. No tool runs at load.
* The import->module resolver uses **resolved-specifier equality** (a specifier is
  resolved to a path, then matched to the owning module's directory) — NOT dotted
  (Python) and NOT a ``/``-prefix (Go). It lives HERE, never in :mod:`anma.engine`.
* ``check()`` WRAPS ``dependency-cruiser`` for real resolution (tsconfig paths,
  barrels, ``import type``) and falls back to a zero-dependency builtin import
  detector with real line numbers when node/depcruise is absent.
* ``load_metadata`` reads ``tsconfig.json`` with a PLAIN read (relative ``extends``
  only); no subprocess on the load/hook path.
* Enforcement is module->module only. ``import type`` counts as a real edge.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from fnmatch import fnmatch
from pathlib import Path

from . import engine
from .contracts import ModuleContract, Project, iter_source_files

# --------------------------------------------------------------------------- #
# Lightweight, dependency-free import detector (builtin fallback + hook path).   #
# The proven specifier regexes run over a MASKED copy of the source where `//`   #
# and `/* */` comments and backtick template literals are blanked and the        #
# CONTENTS of '…'/"…" strings are replaced by recoverable sentinels. So a regex   #
# can never match an import inside a comment or string, real specifiers are still #
# recovered, and line numbers are preserved (newlines are never removed). This    #
# matters because this feeds disallowed_targets in the edit-blocking PreToolUse   #
# hook, where a false positive would wrongly block a legitimate edit. NOT a full  #
# TS parser (regex literals are not special-cased); the hook fails OPEN and       #
# dependency-cruiser is the hard gate.                                            #
# --------------------------------------------------------------------------- #
_RE_FROM = re.compile(r"""(?:import|export)\b[^;'"]*?\bfrom\s*['"]([^'"]+)['"]""")
_RE_SIDE_EFFECT = re.compile(r"""(?m)^\s*import\s+['"]([^'"]+)['"]""")
_RE_REQUIRE = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")
_RE_DYNAMIC = re.compile(r"""\bimport\(\s*['"]([^'"]+)['"]\s*\)""")


def _mask_noncode(source: str):
    """Return ``(masked, specs)``. ``masked`` blanks comments + template literals
    (newlines kept) and replaces each '…'/"…" string's content with a sentinel
    ``\\x00<idx>\\x00`` recorded in ``specs`` — so the regexes see real import
    specifiers but never import-looking text inside a comment/string/template."""
    out: list[str] = []
    specs: list[str] = []
    i, n = 0, len(source)
    while i < n:
        c = source[i]
        if c == "/" and i + 1 < n and source[i + 1] == "/":          # line comment
            out.append("  "); i += 2
            while i < n and source[i] != "\n":
                out.append(" "); i += 1
            continue
        if c == "/" and i + 1 < n and source[i + 1] == "*":          # block comment
            out.append("  "); i += 2
            while i + 1 < n and not (source[i] == "*" and source[i + 1] == "/"):
                out.append("\n" if source[i] == "\n" else " "); i += 1
            out.append("  "); i += 2
            continue
        if c == "`":                                                 # template literal
            out.append(" "); i += 1
            while i < n and source[i] != "`":
                if source[i] == "\\" and i + 1 < n:
                    out.append("  "); i += 2; continue
                out.append("\n" if source[i] == "\n" else " "); i += 1
            out.append(" "); i += 1
            continue
        if c == "'" or c == '"':                                     # string literal
            q, i, val = c, i + 1, []
            while i < n and source[i] != q:
                if source[i] == "\\" and i + 1 < n:
                    val.append(source[i + 1]); i += 2; continue
                if source[i] == "\n":                                # raw newline: bail out
                    break
                val.append(source[i]); i += 1
            i += 1  # closing quote
            idx = len(specs); specs.append("".join(val))
            out.append(f"{q}\x00{idx}\x00{q}")
            continue
        out.append(c); i += 1
    return "".join(out), specs


def scan_imports(source: str):
    """Yield ``(specifier, lineno)`` for real TS/JS imports in ``source``.

    Covers ``import … from``, ``import type … from``, ``export … from``, bare
    ``import '…'``, ``require('…')`` and dynamic ``import('…')`` — ignoring any
    that appear inside comments, strings, or template literals.
    """
    masked, specs = _mask_noncode(source)
    seen: set[tuple[str, int]] = set()
    for rx in (_RE_FROM, _RE_SIDE_EFFECT, _RE_REQUIRE, _RE_DYNAMIC):
        for m in rx.finditer(masked):
            token = m.group(1)
            try:
                spec = specs[int(token.strip("\x00"))]
            except (ValueError, IndexError):
                continue  # not a sentinel — defensive, shouldn't happen
            lineno = masked.count("\n", 0, m.start()) + 1
            key = (spec, lineno)
            if key not in seen:
                seen.add(key)
                yield spec, lineno


# --------------------------------------------------------------------------- #
# tsconfig.json (JSONC) reading — plain file reads only.                         #
# --------------------------------------------------------------------------- #
def _loads_jsonc(text: str) -> dict:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)   # block comments
    text = re.sub(r"//[^\n]*", "", text)                # line comments
    text = re.sub(r",(\s*[}\]])", r"\1", text)          # trailing commas
    data = json.loads(text)
    return data if isinstance(data, dict) else {}


def _read_tsconfig(path: Path, _depth: int = 0) -> dict:
    data = _loads_jsonc(path.read_text())
    ext = data.get("extends")
    # Phase 1: relative `extends` only (package-name extends is out of scope).
    if _depth < 8 and isinstance(ext, str) and (ext.startswith(".") or ext.startswith("/")):
        parent = (path.parent / ext).resolve()
        if not parent.suffix:
            parent = parent.with_suffix(".json")
        if parent.exists():
            base = _read_tsconfig(parent, _depth + 1)
            merged = {**base.get("compilerOptions", {}),
                      **data.get("compilerOptions", {})}
            data = {**base, **data, "compilerOptions": merged}
    return data


def _expand_alias(spec: str, paths: dict, base_url: Path) -> Path | None:
    for pattern, targets in (paths or {}).items():
        if not targets:
            continue
        if "*" in pattern:
            prefix = pattern.split("*", 1)[0]
            if spec.startswith(prefix):
                rest = spec[len(prefix):]
                tgt_prefix = targets[0].split("*", 1)[0]
                return (base_url / (tgt_prefix + rest)).resolve()
        elif spec == pattern:
            return (base_url / targets[0]).resolve()
    return None


def _spec_to_path(spec: str, file: Path, metadata: dict) -> Path:
    """Resolve an import specifier to an absolute path (extensionless is fine —
    module ownership is decided by directory containment)."""
    base_url = Path(metadata.get("base_url") or ".")
    if spec.startswith("."):
        return (file.parent / spec).resolve()
    aliased = _expand_alias(spec, metadata.get("paths", {}), base_url)
    if aliased is not None:
        return aliased
    return (base_url / spec).resolve()  # baseUrl-relative bare specifier


def _owner_for_path(target: Path, project: Project) -> ModuleContract | None:
    best: ModuleContract | None = None
    for m in project.modules:
        mdir = m.path.resolve()
        if target == mdir or mdir in target.parents:
            if best is None or len(str(mdir)) > len(str(best.path.resolve())):
                best = m
    return best


def render_dependency_cruiser(project: Project) -> str:
    """Render a ``.dependency-cruiser.cjs`` — the TS analogue of ``tach.toml``.

    Pure function of the contracts: a ``forbidden`` rule for every disallowed
    module->module edge, with ``deprecated_deps`` downgraded to ``warn``.
    """
    def dir_of(m: ModuleContract) -> str:
        return m.path.resolve().relative_to(project.root.resolve()).as_posix()

    forbidden = []
    for m in project.modules:
        allowed = set(m.depends_on)
        deprecated = set(m.deprecated_deps)
        for o in project.modules:
            if o.name == m.name or o.name in allowed:
                continue
            forbidden.append({
                "name": f"{m.name}-no-{o.name}",
                "comment": f"module '{m.name}' may not depend on '{o.name}'",
                "severity": "warn" if o.name in deprecated else "error",
                "from": {"path": f"^{dir_of(m)}/"},
                "to": {"path": f"^{dir_of(o)}/"},
            })
    config = {
        "forbidden": forbidden,
        "options": {
            "tsConfig": {"fileName": "tsconfig.json"},
            "doNotFollow": {"path": "node_modules"},
        },
    }
    body = json.dumps(config, indent=2)
    return ("/* Generated by `anma sync`. Edit the contracts, not this file. */\n"
            f"module.exports = {body};\n")


TS_CI = """# Generated by `anma sync`.
name: anma
on: [push, pull_request]
jobs:
  boundaries:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: npm ci || npm install
      - run: npm install --no-save dependency-cruiser
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install anma          # anma is a Python CLI, whatever the target language
      - run: anma sync --check         # fail if generated docs/config drifted from contracts
      - run: anma check                # enforce module boundaries (dependency-cruiser; builtin fallback)
"""


class TsAdapter:
    """TypeScript implementation of the LanguageAdapter protocol."""

    language = "typescript"
    file_globs = ("*.ts", "*.tsx")

    def handles_file(self, file: Path) -> bool:
        return any(fnmatch(file.name, g) for g in self.file_globs)

    def _scannable(self, file: Path) -> bool:
        return self.handles_file(file) and not file.name.endswith(".d.ts")

    # -- metadata + identity (pure, no subprocess) ------------------------- #
    def load_metadata(self, project_root: Path) -> dict:
        root = project_root.resolve()
        md: dict = {"base_url": str(root), "paths": {}, "module_root": str(root)}
        ts = root / "tsconfig.json"
        if ts.exists():
            try:
                data = _read_tsconfig(ts)
            except (ValueError, OSError):
                return md
            co = data.get("compilerOptions", {}) or {}
            md["base_url"] = str((root / co.get("baseUrl", ".")).resolve())
            md["paths"] = co.get("paths", {}) or {}
        return md

    def import_identity(self, module: ModuleContract, source_root: Path,
                        metadata: dict) -> str:
        base = Path(metadata.get("base_url") or source_root).resolve()
        try:
            base_spec = "/".join(module.path.resolve().relative_to(base).parts)
        except ValueError:
            return module.name
        best = None
        for pattern, targets in (metadata.get("paths") or {}).items():
            if "*" not in pattern or not targets:
                continue
            tgt = targets[0].split("*", 1)[0].rstrip("/")
            if base_spec == tgt or base_spec.startswith(tgt + "/"):
                remainder = base_spec[len(tgt):].lstrip("/")
                cand = pattern.split("*", 1)[0] + remainder
                if best is None or len(tgt) > best[0]:
                    best = (len(tgt), cand)
        return best[1] if best else base_spec

    # -- enforcement ------------------------------------------------------- #
    def engine_name(self, project: Project) -> str:
        if shutil.which("depcruise") or shutil.which("npx"):
            return "dependency-cruiser"
        return "builtin"

    def check(self, project: Project, backend: str | None = None) -> list[engine.Violation]:
        backend = backend or self.engine_name(project)
        if backend == "dependency-cruiser":
            try:
                return self._check_depcruise(project)
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError, ValueError):
                return self._check_builtin(project)
        return self._check_builtin(project)

    def _check_depcruise(self, project: Project) -> list[engine.Violation]:
        """Wrap dependency-cruiser (the real TS resolver). Uses the generated
        config so tsconfig paths/barrels/import-type are honored. Module-level
        violations (no per-line offset in the JSON graph); the builtin path has
        real line numbers."""
        cfg = project.root / ".dependency-cruiser.cjs"
        cmd = ["npx", "--yes", "dependency-cruiser", "--output-type", "json"]
        if cfg.exists():
            cmd += ["--config", str(cfg)]
        cmd += list(project.source_roots) or ["."]
        proc = subprocess.run(cmd, cwd=project.root, capture_output=True,
                              text=True, timeout=300)
        data = json.loads(proc.stdout)
        # Guard against a FALSE CLEAN: dependency-cruiser needs the `typescript`
        # peer to parse .ts files; without it, it scans nothing and reports zero
        # violations. Treat "scanned nothing" as a failure so check() falls back to
        # the builtin detector rather than silently passing.
        if data.get("summary", {}).get("totalCruised", 0) == 0:
            raise ValueError("dependency-cruiser scanned no modules "
                             "(is the `typescript` package installed?)")
        out: list[engine.Violation] = []
        for v in data.get("summary", {}).get("violations", []):
            frm = v.get("from", "")
            owner = _owner_for_path((project.root / frm).resolve(), project)
            module_name = owner.name if owner else "?"
            sev = (v.get("rule", {}) or {}).get("severity", "error")
            out.append(engine.Violation(
                module_name, frm, 0,
                f"imports '{v.get('to', '')}' — forbidden by contract "
                f"({(v.get('rule', {}) or {}).get('name', 'boundary')})",
                deprecated=(sev == "warn")))
        return out

    def _check_builtin(self, project: Project) -> list[engine.Violation]:
        violations: list[engine.Violation] = []
        for m in project.modules:
            allowed = set(m.depends_on) | {m.name}
            deprecated = set(m.deprecated_deps)
            for f in iter_source_files(project, m, self.file_globs):
                if f.name.endswith(".d.ts"):
                    continue
                try:
                    text = f.read_text()
                except (OSError, UnicodeDecodeError):
                    continue
                for spec, lineno in scan_imports(text):
                    owner = _owner_for_path(_spec_to_path(spec, f, project.metadata), project)
                    if owner is None or owner.name == m.name:
                        continue
                    rel = f.relative_to(project.root)
                    if owner.name in deprecated:
                        violations.append(engine.Violation(
                            m.name, str(rel), lineno,
                            f"uses deprecated dependency '{owner.name}'", deprecated=True))
                    elif owner.name not in allowed:
                        violations.append(engine.Violation(
                            m.name, str(rel), lineno,
                            f"imports '{owner.name}' but it is not in depends_on "
                            f"{sorted(m.depends_on)}"))
        return violations

    def disallowed_targets(self, project: Project, module: ModuleContract,
                           file: Path, source: str) -> set[str]:
        if file.name.endswith(".d.ts"):
            return set()
        allowed = set(module.depends_on) | set(module.deprecated_deps) | {module.name}
        out: set[str] = set()
        for spec, _ln in scan_imports(source):
            owner = _owner_for_path(_spec_to_path(spec, file, project.metadata), project)
            if owner is not None and owner.name != module.name and owner.name not in allowed:
                out.add(owner.name)
        return out

    # -- generated artifacts ----------------------------------------------- #
    def engine_artifacts(self, project: Project) -> dict[Path, str]:
        return {project.root / ".dependency-cruiser.cjs": render_dependency_cruiser(project)}

    def ci_workflow(self, project: Project) -> str:
        return TS_CI
