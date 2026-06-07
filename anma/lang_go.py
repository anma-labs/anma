"""Go language adapter for the ANMA boundary engine.

Implements the :class:`anma.adapters.LanguageAdapter` protocol for Go, with ZERO
changes to the neutral layers (contracts / engine / compile / templates). It is a
leaf module: it imports only :mod:`anma.engine` (for the shared ``Violation``
return type) and :mod:`anma.contracts`. :mod:`anma.adapters` imports the class at
the bottom of that module and registers it, so a single ``import anma.adapters``
makes Go available to the CLI and the PreToolUse hook with no extra wiring.

Design (see DECISIONS.md):

* Import identity = the ``go.mod`` module path + the package's directory relative
  to the module root, joined with ``/`` (e.g. ``github.com/acme/app/internal/billing``).
  Anchored at the ``go.mod`` directory, not ``source_root`` — that is the only
  correct anchor for Go import paths.
* The import->module resolver uses a ``/``-boundary prefix match and lives HERE,
  never in :mod:`anma.engine` (whose dotted ``.``-boundary resolver is Python-only).
* ``load_metadata`` reads ``go.mod`` with a PLAIN file read; ``import_identity`` is
  a pure derivation from that cache. No subprocess on the load path (the hook hot
  path). The external resolver (``go-arch-lint`` / ``go list``) runs ONLY in
  ``check()``.
* Enforcement is module->module only. ``public:`` drives guidance, not symbol-level
  checks (symbol-level remains Python/tach-only).
"""
from __future__ import annotations

import shutil
import subprocess
from fnmatch import fnmatch
from pathlib import Path

from . import engine
from .contracts import ModuleContract, Project

# --------------------------------------------------------------------------- #
# Lightweight, dependency-free import scanner (used by the builtin fallback and #
# by the per-edit hook). NOT a full Go parser, but a small char-level lexer that #
# skips `//` and `/* */` comments and string/rune/raw-string literals BEFORE     #
# detecting imports, so import-looking text inside a comment or a string is never #
# mistaken for an import. That matters because this feeds disallowed_targets in   #
# the edit-blocking PreToolUse hook, where a false positive would wrongly block a #
# legitimate edit. Handles single imports, grouped `import ( ... )` blocks        #
# (including collapsed one-line `import ( "a"; "b" )`), and alias / `_` / `.`     #
# prefixes. Remaining limit: build-constraint comments are not interpreted (the   #
# hook fails OPEN and CI is the hard gate).                                       #
# --------------------------------------------------------------------------- #
def _go_tokens(source: str):
    """Yield ``(kind, value, lineno)`` for the tokens that matter to import parsing.

    Comments and the *contents* of string/rune literals are consumed and never
    surface as code; string literals (interpreted ``"..."`` and raw `` `...` ``)
    become STRING tokens carrying their unquoted value. Kinds: IMPORT, STRING,
    LPAREN, RPAREN.
    """
    i, n, line = 0, len(source), 1
    while i < n:
        c = source[i]
        if c == "\n":
            line += 1; i += 1; continue
        if c.isspace():
            i += 1; continue
        if c == "/" and i + 1 < n and source[i + 1] == "/":          # line comment
            i += 2
            while i < n and source[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and source[i + 1] == "*":          # block comment
            i += 2
            while i + 1 < n and not (source[i] == "*" and source[i + 1] == "/"):
                if source[i] == "\n":
                    line += 1
                i += 1
            i += 2
            continue
        if c == "`":                                                 # raw string literal
            start, i, val = line, i + 1, []
            while i < n and source[i] != "`":
                if source[i] == "\n":
                    line += 1
                val.append(source[i]); i += 1
            i += 1
            yield "STRING", "".join(val), start
            continue
        if c == '"':                                                 # interpreted string
            start, i, val = line, i + 1, []
            while i < n and source[i] != '"':
                if source[i] == "\\" and i + 1 < n:
                    val.append(source[i + 1]); i += 2; continue
                if source[i] == "\n":
                    line += 1
                val.append(source[i]); i += 1
            i += 1
            yield "STRING", "".join(val), start
            continue
        if c == "'":                                                 # rune literal
            i += 1
            while i < n and source[i] != "'":
                i += 2 if (source[i] == "\\" and i + 1 < n) else 1
            i += 1
            continue
        if c == "(":
            yield "LPAREN", "(", line; i += 1; continue
        if c == ")":
            yield "RPAREN", ")", line; i += 1; continue
        if c.isalpha() or c == "_":                                  # identifier / keyword
            j = i
            while j < n and (source[j].isalnum() or source[j] == "_"):
                j += 1
            if source[i:j] == "import":
                yield "IMPORT", "import", line
            i = j
            continue
        i += 1


def scan_imports(source: str):
    """Yield ``(import_path, lineno)`` for real Go imports in ``source``."""
    toks = list(_go_tokens(source))
    k = 0
    while k < len(toks):
        if toks[k][0] != "IMPORT":
            k += 1
            continue
        k += 1
        if k < len(toks) and toks[k][0] == "LPAREN":                 # grouped block
            k += 1
            while k < len(toks) and toks[k][0] != "RPAREN":
                if toks[k][0] == "STRING":
                    yield toks[k][1], toks[k][2]
                k += 1
            k += 1  # consume RPAREN
        else:                                                        # single import
            while k < len(toks) and toks[k][0] not in ("STRING", "IMPORT"):
                k += 1
            if k < len(toks) and toks[k][0] == "STRING":
                yield toks[k][1], toks[k][2]
                k += 1


def _owner_resolver(project: Project):
    """Map a Go import path to its owning module (``/``-boundary prefix match)."""
    by_import = {m.import_path: m for m in project.modules}
    prefixes = sorted(by_import, key=len, reverse=True)

    def owner(path: str) -> ModuleContract | None:
        for p in prefixes:
            if path == p or path.startswith(p + "/"):
                return by_import[p]
        return None

    return owner


def render_go_arch_lint(project: Project) -> str:
    """Render a go-arch-lint v3 config — the Go analogue of ``tach.toml``.

    Pure function of the contracts: one component per module (``in:`` its dir) and
    a ``mayDependOn`` allow-list per module built from ``depends_on``.
    """
    lines = ["# Generated by `anma sync`. Edit the contracts, not this file.",
             "version: 3", "workdir: .", "", "components:"]
    for m in project.modules:
        rel = m.path.resolve().relative_to(project.root.resolve()).as_posix()
        lines.append(f"  {m.name}:")
        lines.append(f"    in: {rel}")
    lines.append("")
    lines.append("deps:")
    for m in project.modules:
        lines.append(f"  {m.name}:")
        if m.depends_on:
            lines.append("    mayDependOn:")
            for d in m.depends_on:
                lines.append(f"      - {d}")
        else:
            lines.append("    mayDependOn: []")
    return "\n".join(lines) + "\n"


GO_CI = """# Generated by `anma sync`.
name: anma
on: [push, pull_request]
jobs:
  boundaries:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with: {{ go-version: "{go}" }}
      - run: go install github.com/fe3dback/go-arch-lint@latest
      - uses: actions/setup-python@v5
        with: {{ python-version: "3.12" }}
      - run: pip install anma          # anma is a Python CLI, whatever the target language
      - run: anma sync --check         # fail if generated docs/config drifted from contracts
      - run: anma check                # enforce module boundaries (go-arch-lint; builtin fallback)
"""


class GoAdapter:
    """Go implementation of the LanguageAdapter protocol."""

    language = "go"
    file_globs = ("*.go",)

    # -- file ownership ---------------------------------------------------- #
    def handles_file(self, file: Path) -> bool:
        return any(fnmatch(file.name, g) for g in self.file_globs)

    # -- metadata + identity (pure, no subprocess) ------------------------- #
    def load_metadata(self, project_root: Path) -> dict:
        root = project_root.resolve()
        md: dict = {"module_path": "", "module_root": str(root)}
        gomod = root / "go.mod"
        if gomod.exists():
            for line in gomod.read_text().splitlines():
                s = line.strip()
                if s.startswith("module "):
                    md["module_path"] = s[len("module "):].strip()
                elif s.startswith("go "):
                    md["go_version"] = s[len("go "):].strip()
        return md

    def import_identity(self, module: ModuleContract, source_root: Path,
                        metadata: dict) -> str:
        module_path = metadata.get("module_path", "")
        anchor = Path(metadata.get("module_root") or source_root).resolve()
        try:
            rel = module.path.resolve().relative_to(anchor)
        except ValueError:
            rel = Path(module.name)
        parts = [module_path, *rel.parts]
        return "/".join(p for p in parts if p)

    # -- enforcement ------------------------------------------------------- #
    def engine_name(self, project: Project) -> str:
        if shutil.which("go-arch-lint"):
            return "go-arch-lint"
        if shutil.which("go"):
            return "go"
        return "builtin"

    def check(self, project: Project, backend: str | None = None) -> list[engine.Violation]:
        backend = backend or self.engine_name(project)
        if backend == "go-arch-lint":
            try:
                return self._check_external(project)
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                return self._check_builtin(project)
        return self._check_builtin(project)

    def _check_external(self, project: Project) -> list[engine.Violation]:
        """Wrap ``go-arch-lint check`` (the fast external backend). Mirrors the
        tach wrapper in :func:`anma.engine._check_tach`: returncode 0 == clean,
        otherwise surface its report lines. NOTE: not exercised where the Go
        toolchain is absent; the builtin fallback (with real line numbers) runs."""
        proc = subprocess.run(["go-arch-lint", "check"], cwd=project.root,
                              capture_output=True, text=True, timeout=120)
        if proc.returncode == 0:
            return []
        violations: list[engine.Violation] = []
        for line in (proc.stdout + "\n" + proc.stderr).splitlines():
            line = line.strip()
            if not line or "passed" in line.lower():
                continue
            violations.append(engine.Violation("?", line, 0, line))
        if not violations:
            violations.append(engine.Violation(
                "?", "go-arch-lint", 0, proc.stdout.strip() or proc.stderr.strip()))
        return violations

    def _check_builtin(self, project: Project) -> list[engine.Violation]:
        owner = _owner_resolver(project)
        violations: list[engine.Violation] = []
        for m in project.modules:
            allowed = set(m.depends_on) | {m.name}
            deprecated = set(m.deprecated_deps)
            for go in sorted(m.path.rglob("*.go")):
                if go.name.endswith("_test.go"):
                    continue
                try:
                    text = go.read_text()
                except (OSError, UnicodeDecodeError):
                    continue
                for imported, lineno in scan_imports(text):
                    target = owner(imported)
                    if target is None or target.name == m.name:
                        continue
                    rel = go.relative_to(project.root)
                    if target.name in deprecated:
                        violations.append(engine.Violation(
                            m.name, str(rel), lineno,
                            f"uses deprecated dependency '{target.name}'", deprecated=True))
                    elif target.name not in allowed:
                        violations.append(engine.Violation(
                            m.name, str(rel), lineno,
                            f"imports '{target.name}' but it is not in depends_on "
                            f"{sorted(m.depends_on)}"))
        return violations

    def disallowed_targets(self, project: Project, module: ModuleContract,
                           file: Path, source: str) -> set[str]:
        if file.name.endswith("_test.go"):
            return set()  # test files may cross boundaries
        owner = _owner_resolver(project)
        allowed = set(module.depends_on) | set(module.deprecated_deps) | {module.name}
        out: set[str] = set()
        for imported, _ln in scan_imports(source):
            tgt = owner(imported)
            if tgt is not None and tgt.name != module.name and tgt.name not in allowed:
                out.add(tgt.name)
        return out

    # -- generated artifacts ----------------------------------------------- #
    def engine_artifacts(self, project: Project) -> dict[Path, str]:
        return {project.root / ".go-arch-lint.yml": render_go_arch_lint(project)}

    def ci_workflow(self, project: Project) -> str:
        go_version = project.metadata.get("go_version") or "stable"
        return GO_CI.format(go=go_version)
