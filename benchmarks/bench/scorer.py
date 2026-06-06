"""Independent violation scorer.

Deliberately does NOT import `anma` — it scores against the scenario's declared
boundary graph (`boundaries.yaml`) using its own static `ast` analysis, so the
benchmark is not "graded by the tool being measured."
"""
from __future__ import annotations

import ast
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
    modules: dict  # name -> {"path": dotted, "allow": [names]}


def load_spec(path: Path) -> BoundarySpec:
    d = yaml.safe_load(path.read_text())
    return BoundarySpec(d.get("source_root", "src"), d["modules"])


def count_violations(repo: Path, spec: BoundarySpec) -> list[Violation]:
    src = (repo / spec.source_root).resolve()
    by_import = {m["path"]: name for name, m in spec.modules.items()}
    prefixes = sorted(by_import, key=len, reverse=True)

    def owner(dotted: str) -> str | None:
        for p in prefixes:
            if dotted == p or dotted.startswith(p + "."):
                return by_import[p]
        return None

    out: list[Violation] = []
    for name, m in spec.modules.items():
        allow = set(m.get("allow", [])) | {name}
        mod_dir = src.joinpath(*m["path"].split("."))
        for py in sorted(mod_dir.rglob("*.py")):
            try:
                tree = ast.parse(py.read_text(), filename=str(py))
            except SyntaxError:
                continue
            for imported, lineno in _imports(tree, py, src):
                tgt = owner(imported)
                if tgt is None or tgt == name:
                    continue
                if tgt not in allow:
                    out.append(Violation(name, str(py.relative_to(repo)), lineno, tgt))
    return out


def _imports(tree: ast.AST, file: Path, src: Path):
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
