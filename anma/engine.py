"""The boundary enforcement engine, behind a thin adapter.

Default backend is ``tach`` (Rust, fast, enforces interfaces too). If tach is
not installed, ANMA falls back to a small ``ast``-based dependency checker with
no external dependencies. The contracts never change; only the backend does, so
the tool survives tach's maintenance status either way.
"""
from __future__ import annotations

import ast
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .contracts import ModuleContract, Project


@dataclass
class Violation:
    module: str
    file: str
    line: int
    message: str
    deprecated: bool = False  # allowed-but-warned dependency

    def __str__(self) -> str:
        tag = " (deprecated)" if self.deprecated else ""
        return f"{self.file}:{self.line}  [{self.module}]  {self.message}{tag}"

    def as_dict(self) -> dict:
        return {"module": self.module, "file": self.file, "line": self.line,
                "message": self.message, "deprecated": self.deprecated}


def detect_engine() -> str:
    return "tach" if shutil.which("tach") else "builtin"


def check(project: Project, engine: str | None = None) -> list[Violation]:
    engine = engine or detect_engine()
    if engine == "tach":
        return _check_tach(project)
    return _check_builtin(project)


# --------------------------------------------------------------------------- #
def _check_tach(project: Project) -> list[Violation]:
    try:
        proc = subprocess.run(["tach", "check"], cwd=project.root,
                              capture_output=True, text=True, timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return _check_builtin(project)
    if proc.returncode == 0:
        return []
    violations: list[Violation] = []
    for line in (proc.stdout + "\n" + proc.stderr).splitlines():
        line = line.strip()
        if not line or "validated" in line.lower():
            continue
        violations.append(Violation("?", line, 0, line))
    if not violations:
        violations.append(Violation("?", "tach", 0, proc.stdout.strip() or proc.stderr.strip()))
    return violations


# --------------------------------------------------------------------------- #
def _check_builtin(project: Project) -> list[Violation]:
    by_import = {m.import_path: m for m in project.modules}
    prefixes = sorted(by_import, key=len, reverse=True)

    def owner(dotted: str) -> ModuleContract | None:
        for p in prefixes:
            if dotted == p or dotted.startswith(p + "."):
                return by_import[p]
        return None

    violations: list[Violation] = []
    for m in project.modules:
        allowed = set(m.depends_on) | {m.name}
        deprecated = set(m.deprecated_deps)
        for py in sorted(m.path.rglob("*.py")):
            try:
                tree = ast.parse(py.read_text(), filename=str(py))
            except SyntaxError:
                continue
            for imported, lineno in _iter_imports(tree, py, m._source_root):
                target = owner(imported)
                if target is None or target.name == m.name:
                    continue
                if target.name in deprecated:
                    rel = py.relative_to(project.root)
                    violations.append(Violation(
                        m.name, str(rel), lineno,
                        f"uses deprecated dependency '{target.name}'", deprecated=True))
                elif target.name not in allowed:
                    rel = py.relative_to(project.root)
                    violations.append(Violation(
                        m.name, str(rel), lineno,
                        f"imports '{target.name}' but it is not in depends_on "
                        f"{sorted(m.depends_on)}"))
    return violations


def _iter_imports(tree: ast.AST, file: Path, src: Path):
    pkg_parts = file.parent.resolve().relative_to(src).parts
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                base = list(pkg_parts[: len(pkg_parts) - (node.level - 1)])
                if node.module:
                    base += node.module.split(".")
                yield ".".join(base), node.lineno
            elif node.module:
                yield node.module, node.lineno
