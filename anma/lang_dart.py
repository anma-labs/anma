"""Dart language adapter for the ANMA boundary engine.

Implements the :class:`anma.adapters.LanguageAdapter` protocol for Dart with ZERO
changes to the neutral layers. Like the Go and TypeScript adapters it is a leaf
module (imports only :mod:`anma.engine` + :mod:`anma.contracts`) and is registered
from :mod:`anma.adapters` at import time.

Design (mirrors the TS adapter — see DECISIONS.md):

* Import identity is the ``package:<own>/<dir-relative-to-lib>`` URI a sibling
  would write — derived purely from the cached ``pubspec.yaml`` package name. No
  tool runs at load.
* The import->module resolver uses **resolved-path equality**: a URI is resolved to
  an absolute path under ``lib/`` and matched to the owning module's directory
  (like TS, NOT Go's ``/``-prefix and NOT Python's dotted match). It lives HERE,
  never in :mod:`anma.engine`.
* Resolution (the four ways Dart differs from TS):
  1. a RELATIVE URI (``'../models/x.dart'``) resolves against the importing file's
     directory; a ``package:<own>/...`` URI maps to the SAME ``lib/`` path.
  2. both ``import`` and ``export`` are edges; ``part`` / ``part of`` are NOT.
  3. URIs are classified with the package name from ``pubspec.yaml`` — ``dart:`` SDK
     libraries and third-party ``package:`` URIs are skipped.
  4. the masker handles ``//``, ``/* */`` (nesting), ``///``, ``'...'``, ``"..."``,
     ``'''...'''``, ``\"\"\"...\"\"\"``, ``r'...'`` raw strings, and ``${...}``
     interpolation.
* ``load_metadata`` reads ``pubspec.yaml`` with a PLAIN line read (no subprocess on
  the load/hook path). There is NO external resolver in v1: the zero-dependency
  builtin masked-scanner is the only backend (``dart analyze`` is out of scope).
* Enforcement is module->module only (``public:`` interface enforcement is
  Python/tach-only).
"""
from __future__ import annotations

import re
from fnmatch import fnmatch
from pathlib import Path

from . import engine
from .contracts import ModuleContract, Project

# --------------------------------------------------------------------------- #
# Lightweight, dependency-free import detector (builtin backend + hook path).    #
# The directive regex runs over a MASKED copy of the source where comments and   #
# template/interpolation regions are blanked and the CONTENTS of every string    #
# literal are replaced by a recoverable sentinel ``\x00<idx>\x00``. So a regex    #
# can never match an `import`/`export` inside a comment or string, real URIs are  #
# still recovered, and line numbers are preserved (newlines are never removed).   #
# This feeds disallowed_targets in the edit-blocking PreToolUse hook, where a      #
# false positive would wrongly block a legitimate edit. NOT a full Dart parser     #
# (configurable-import alternatives are not followed); the hook fails OPEN.        #
# --------------------------------------------------------------------------- #

# `import`/`export` directive followed by a masked string sentinel. `part` and
# `part of` are excluded by construction (they are a different keyword).
_RE_DIRECTIVE = re.compile(r"""\b(?:import|export)\b\s*['"]\x00(\d+)\x00['"]""")


def _blank_like(span: str) -> str:
    """Same-length blanking that preserves newline positions (for line numbers)."""
    return "".join("\n" if ch == "\n" else " " for ch in span)


def _scan_string(source: str, i: int, specs: list, raw: bool):
    """Consume one string literal starting at the opening quote ``source[i]``.

    Returns ``(fragment, next_index)``. A single-line string with no interpolation
    becomes a recoverable sentinel ``q\\x00idx\\x00q`` (its content recorded in
    ``specs``); a multi-line or interpolated string is blanked, newlines preserved,
    so it can never be mistaken for an import but also never shifts line numbers.
    """
    n = len(source)
    q = source[i]
    triple = source[i:i + 3] == q * 3
    delim = q * 3 if triple else q
    j = i + len(delim)
    val: list[str] = []            # recovered content for the sentinel case
    blanks: list[str] = [" " * len(delim)]
    had_nl = False
    had_interp = False
    closed = False
    while j < n:
        ch = source[j]
        if triple:
            if source[j:j + 3] == delim:
                blanks.append("   "); j += 3; closed = True; break
        else:
            if ch == q:
                blanks.append(" "); j += 1; closed = True; break
            if ch == "\n":             # unterminated single-line string — bail out
                break
        if (not raw) and ch == "\\" and j + 1 < n:
            nxt = source[j + 1]
            val.append(nxt)
            blanks.append(" \n" if nxt == "\n" else "  ")
            if nxt == "\n":
                had_nl = True
            j += 2
            continue
        if (not raw) and ch == "$":
            had_interp = True
            if j + 1 < n and source[j + 1] == "{":
                blanks.append("  "); j += 2
                depth = 1
                while j < n and depth > 0:        # ${ ... } is code: skip balanced
                    cj = source[j]
                    if cj == "{":
                        depth += 1; blanks.append(" "); j += 1; continue
                    if cj == "}":
                        depth -= 1; blanks.append(" "); j += 1; continue
                    nested_raw = (cj == "r" and j + 1 < n
                                  and source[j + 1] in ("'", '"'))
                    if cj in ("'", '"') or nested_raw:
                        k = j + (1 if nested_raw else 0)
                        _, j2 = _scan_string(source, k, [], raw=nested_raw)
                        span = source[j:j2]
                        if "\n" in span:
                            had_nl = True
                        blanks.append(_blank_like(span)); j = j2; continue
                    if cj == "\n":
                        had_nl = True
                    blanks.append("\n" if cj == "\n" else " "); j += 1
                continue
            blanks.append(" "); j += 1        # simple $name interpolation
            continue
        if ch == "\n":
            had_nl = True
        val.append(ch)
        blanks.append("\n" if ch == "\n" else " ")
        j += 1
    if closed and not had_nl and not had_interp:
        idx = len(specs)
        specs.append("".join(val))
        return f"{q}\x00{idx}\x00{q}", j
    return "".join(blanks), j


def _mask_noncode(source: str):
    """Return ``(masked, specs)``. ``masked`` blanks comments and multi-line /
    interpolated strings (newlines kept) and replaces each single-line string's
    content with a recoverable sentinel recorded in ``specs`` — so the directive
    regex sees real import/export URIs but never import-looking text inside a
    comment or string."""
    out: list[str] = []
    specs: list[str] = []
    i, n = 0, len(source)
    while i < n:
        c = source[i]
        if c == "/" and i + 1 < n and source[i + 1] == "/":          # // and /// comment
            out.append("  "); i += 2
            while i < n and source[i] != "\n":
                out.append(" "); i += 1
            continue
        if c == "/" and i + 1 < n and source[i + 1] == "*":          # /* */ (nests)
            depth = 1; out.append("  "); i += 2
            while i < n and depth > 0:
                if source[i] == "/" and i + 1 < n and source[i + 1] == "*":
                    depth += 1; out.append("  "); i += 2; continue
                if source[i] == "*" and i + 1 < n and source[i + 1] == "/":
                    depth -= 1; out.append("  "); i += 2; continue
                out.append("\n" if source[i] == "\n" else " "); i += 1
            continue
        if (c == "r" and i + 1 < n and source[i + 1] in ("'", '"')
                and (i == 0 or not (source[i - 1].isalnum() or source[i - 1] == "_"))):
            out.append(" ")                                          # blank the `r` prefix
            frag, i = _scan_string(source, i + 1, specs, raw=True)
            out.append(frag); continue
        if c == "'" or c == '"':                                     # string literal
            frag, i = _scan_string(source, i, specs, raw=False)
            out.append(frag); continue
        out.append(c); i += 1
    return "".join(out), specs


def scan_imports(source: str):
    """Yield ``(uri, lineno)`` for real Dart ``import``/``export`` directives.

    ``part`` and ``part of`` are excluded; URIs inside comments, strings, raw
    strings, and ``${...}`` interpolation are never reported.
    """
    masked, specs = _mask_noncode(source)
    seen: set[tuple[str, int]] = set()
    for m in _RE_DIRECTIVE.finditer(masked):
        try:
            uri = specs[int(m.group(1))]
        except (ValueError, IndexError):
            continue  # not a sentinel — defensive, shouldn't happen
        lineno = masked.count("\n", 0, m.start()) + 1
        key = (uri, lineno)
        if key not in seen:
            seen.add(key)
            yield uri, lineno


# --------------------------------------------------------------------------- #
# URI -> path resolution + module ownership.                                     #
# --------------------------------------------------------------------------- #
def _spec_to_path(spec: str, file: Path, metadata: dict) -> Path | None:
    """Resolve a Dart URI to an absolute path under ``lib/``, or ``None`` if it is
    not own-package code (``dart:`` SDK, or a third-party / malformed ``package:``)."""
    own = metadata.get("package_name") or ""
    lib_root = Path(metadata.get("lib_root") or ".")
    if spec.startswith("dart:"):
        return None                                   # SDK library — never a module
    if spec.startswith("package:"):
        pkg, _, tail = spec[len("package:"):].partition("/")
        if not own or pkg != own or not tail:
            return None                               # third-party / malformed — external
        return (lib_root / tail).resolve()            # package:<own>/a/b.dart -> lib/a/b.dart
    return (file.parent / spec).resolve()             # relative URI -> against importer's dir


def _owner_for_path(target: Path | None, project: Project) -> ModuleContract | None:
    if target is None:
        return None
    best: ModuleContract | None = None
    for m in project.modules:
        mdir = m.path.resolve()
        if target == mdir or mdir in target.parents:
            if best is None or len(str(mdir)) > len(str(best.path.resolve())):
                best = m
    return best


DART_CI = """# Generated by `anma sync`.
name: anma
on: [push, pull_request]
jobs:
  boundaries:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dart-lang/setup-dart@v1
        with: {{ sdk: "{sdk}" }}
      - uses: actions/setup-python@v5
        with: {{ python-version: "3.12" }}
      - run: pip install anma          # anma is a Python CLI, whatever the target language
      - run: anma sync --check         # fail if generated docs/config drifted from contracts
      - run: anma check                # enforce module boundaries (builtin masked import scanner)
"""


class DartAdapter:
    """Dart implementation of the LanguageAdapter protocol (builtin scanner only)."""

    language = "dart"
    file_globs = ("*.dart",)

    # -- file ownership ---------------------------------------------------- #
    def handles_file(self, file: Path) -> bool:
        return any(fnmatch(file.name, g) for g in self.file_globs)

    # -- metadata + identity (pure, no subprocess) ------------------------- #
    def load_metadata(self, project_root: Path) -> dict:
        root = project_root.resolve()
        md: dict = {"package_name": "", "lib_root": str(root / "lib"),
                    "module_root": str(root)}
        pub = root / "pubspec.yaml"
        if pub.exists():
            try:
                lines = pub.read_text().splitlines()
            except (OSError, UnicodeDecodeError):
                return md
            for line in lines:
                # top-level `name:` only (no leading indentation), plain read.
                if line[:1] in (" ", "\t") or ":" not in line:
                    continue
                key, _, value = line.partition(":")
                if key.strip() == "name":
                    md["package_name"] = value.split("#", 1)[0].strip().strip("'\"")
                    break
        return md

    def import_identity(self, module: ModuleContract, source_root: Path,
                        metadata: dict) -> str:
        own = metadata.get("package_name") or ""
        lib_root = Path(metadata.get("lib_root") or source_root).resolve()
        try:
            rel = "/".join(module.path.resolve().relative_to(lib_root).parts)
        except ValueError:
            return module.name
        if own:
            return f"package:{own}/{rel}" if rel else f"package:{own}"
        return rel or module.name

    # -- enforcement ------------------------------------------------------- #
    def engine_name(self, project: Project) -> str:
        # v1 has no external Dart resolver; the builtin masked scanner is the gate.
        return "builtin"

    def check(self, project: Project, backend: str | None = None) -> list[engine.Violation]:
        return self._check_builtin(project)

    def _check_builtin(self, project: Project) -> list[engine.Violation]:
        violations: list[engine.Violation] = []
        for m in project.modules:
            allowed = set(m.depends_on) | {m.name}
            deprecated = set(m.deprecated_deps)
            for f in sorted(p for g in self.file_globs for p in m.path.rglob(g)):
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
        allowed = set(module.depends_on) | set(module.deprecated_deps) | {module.name}
        out: set[str] = set()
        for spec, _ln in scan_imports(source):
            owner = _owner_for_path(_spec_to_path(spec, file, project.metadata), project)
            if owner is not None and owner.name != module.name and owner.name not in allowed:
                out.add(owner.name)
        return out

    # -- generated artifacts ----------------------------------------------- #
    def engine_artifacts(self, project: Project) -> dict[Path, str]:
        # No external Dart backend in v1 -> no engine config file to generate.
        # Boundaries live in the per-module CLAUDE.md + the PreToolUse hook.
        return {}

    def ci_workflow(self, project: Project) -> str:
        sdk = project.metadata.get("sdk") or "stable"
        return DART_CI.format(sdk=sdk)
