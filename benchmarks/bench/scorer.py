"""Independent violation scorer.

Deliberately does NOT import `anma` — it scores against the scenario's declared
boundary graph (`boundaries.yaml`) using its OWN static analysis, so the benchmark
is not "graded by the tool being measured." This independence holds per language:
Python is scored with `ast`, Go and TypeScript with small stdlib-`re` scanners that
are SEPARATE implementations from anma's adapters. A parsing bug in anma therefore
cannot hide itself in the score.

`boundaries.yaml` gains an optional `language:` field (default `python`); Go also
declares `module_prefix:` (its go.mod module path) so import paths reduce to the
slash-style `path:` values. Absent `language:`, behavior is identical to before.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Violation:
    module: str
    file: str
    line: int
    imported: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line} [{self.module}] -> {self.imported}"


@dataclass
class BoundarySpec:
    source_root: str
    modules: dict  # name -> {"path": <native path>, "allow": [names]}
    language: str = "python"
    module_prefix: str = ""  # Go: the go.mod module path, stripped from import paths


def load_spec(path: Path) -> BoundarySpec:
    d = yaml.safe_load(path.read_text())
    return BoundarySpec(d.get("source_root", "src"), d["modules"],
                        d.get("language", "python"), d.get("module_prefix", ""))


def source_globs(language: str) -> tuple[str, ...]:
    return {
        "python": ("*.py",),
        "go": ("*.go",),
        "typescript": ("*.ts", "*.tsx"),
    }.get(language, ("*.py",))


def count_violations(repo: Path, spec: BoundarySpec) -> list[Violation]:
    src = (repo / spec.source_root).resolve()
    by_import = {m["path"]: name for name, m in spec.modules.items()}
    sep = "." if spec.language == "python" else "/"
    prefixes = sorted(by_import, key=len, reverse=True)

    def owner(path: str) -> str | None:
        for p in prefixes:
            if path == p or path.startswith(p + sep):
                return by_import[p]
        return None

    globs = source_globs(spec.language)
    extractor = _EXTRACTORS.get(spec.language, _py_imports)

    out: list[Violation] = []
    for name, m in spec.modules.items():
        allow = set(m.get("allow", [])) | {name}
        mod_dir = src.joinpath(*m["path"].split(sep))
        for f in sorted(p for g in globs for p in mod_dir.rglob(g)):
            try:
                text = f.read_text()
            except (OSError, UnicodeDecodeError):
                continue
            for imported, lineno in extractor(text, f, src, spec):
                tgt = owner(imported)
                if tgt is None or tgt == name:
                    continue
                if tgt not in allow:
                    out.append(Violation(name, str(f.relative_to(repo)), lineno, tgt))
    return out


# --------------------------------------------------------------------------- #
# Per-language import extractors. Each yields (module_path_string, lineno) in    #
# the same path-space as the boundaries.yaml `path:` values, so `owner()` is     #
# uniform. All are independent of anma.                                          #
# --------------------------------------------------------------------------- #
def _py_imports(text: str, file: Path, src: Path, spec: BoundarySpec):
    try:
        tree = ast.parse(text, filename=str(file))
    except SyntaxError:
        return
    parts = file.parent.resolve().relative_to(src).parts
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                base = list(parts[: len(parts) - (node.level - 1)])
                if node.module:
                    base += node.module.split(".")
                yield ".".join(base), node.lineno
            elif node.module:
                yield node.module, node.lineno


_GO_QUOTED = re.compile(r'"([^"]+)"')


def _go_imports(text: str, file: Path, src: Path, spec: BoundarySpec):
    """Independent Go import scanner; strips the go.mod module prefix so paths
    reduce to the slash-style `path:` values (e.g. domains/billing)."""
    prefix = spec.module_prefix.rstrip("/")
    in_block = False
    for lineno, raw in enumerate(text.splitlines(), start=1):
        s = raw.strip()
        if not in_block:
            if s.startswith("import (") or s.startswith("import("):
                in_block = True
                m = _GO_QUOTED.search(s.split("(", 1)[1])
                if m:
                    yield _go_strip(m.group(1), prefix), lineno
                continue
            if s.startswith("import ") or s.startswith("import\t"):
                m = _GO_QUOTED.search(s)
                if m:
                    yield _go_strip(m.group(1), prefix), lineno
        else:
            if s.startswith(")"):
                in_block = False
                continue
            if s.startswith("//"):
                continue
            m = _GO_QUOTED.search(s)
            if m:
                yield _go_strip(m.group(1), prefix), lineno


def _go_strip(path: str, prefix: str) -> str:
    if prefix and (path == prefix or path.startswith(prefix + "/")):
        return path[len(prefix):].lstrip("/")
    return path  # external (stdlib / third party) — won't match a module path


_TS_RES = (
    re.compile(r"""(?:import|export)\b[^;'"]*?\bfrom\s*['"]([^'"]+)['"]"""),
    re.compile(r"""(?m)^\s*import\s+['"]([^'"]+)['"]"""),
    re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)"""),
    re.compile(r"""\bimport\(\s*['"]([^'"]+)['"]\s*\)"""),
)


def _ts_imports(text: str, file: Path, src: Path, spec: BoundarySpec):
    """Independent TS import scanner. Resolves RELATIVE specifiers to a
    source-root-relative slash path (matching the `path:` values); non-relative
    specifiers are yielded as-is (bare/aliased → treated as external unless they
    happen to match a module path). Covers import / import type / export-from /
    require / dynamic import."""
    seen: set[tuple[str, int]] = set()
    for rx in _TS_RES:
        for m in rx.finditer(text):
            spec_str = m.group(1)
            lineno = text.count("\n", 0, m.start()) + 1
            if spec_str.startswith("."):
                target = (file.parent / spec_str).resolve()
                try:
                    resolved = "/".join(target.relative_to(src).parts)
                except ValueError:
                    continue  # outside the source root — external
            else:
                resolved = spec_str
            key = (resolved, lineno)
            if key not in seen:
                seen.add(key)
                yield resolved, lineno


_EXTRACTORS = {
    "python": _py_imports,
    "go": _go_imports,
    "typescript": _ts_imports,
}
