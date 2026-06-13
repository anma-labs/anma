"""Contracts are the single source of truth for ANMA.

A project has one root ``anma.yaml`` and one ``anma.yaml`` per module.
Everything else (CLAUDE.md map, nested CLAUDE.md, tach config, hooks, CODEOWNERS)
is *generated* from these, so the agent-facing docs can never drift from the
enforced rules. The contract schema is versioned (``schema_version``) and follows
SemVer at the schema level — see README "Stability".
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT_CONFIG = "anma.yaml"
MODULE_CONFIG = "anma.yaml"
SUPPORTED_SCHEMA = 1  # highest contract schema_version this build understands

# Directories never scanned for module contracts (vendored / build / vcs dirs).
DEFAULT_IGNORE = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", "build", "dist",
    ".venv", "venv", ".tox", ".mypy_cache", ".pytest_cache", ".eggs",
}


@dataclass
class ModuleContract:
    name: str
    path: Path
    summary: str
    public: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    invariants: list[str] = field(default_factory=list)
    owners: list[str] = field(default_factory=list)        # -> CODEOWNERS
    deprecated_deps: list[str] = field(default_factory=list)  # allowed-but-warned (incremental adoption)
    _source_root: Path = field(default=None, repr=False)   # the root this module lives under
    _import_path: str = field(default="", repr=False)

    @property
    def import_path(self) -> str:
        return self._import_path or self.name


@dataclass
class Project:
    root: Path
    source_roots: list[str]
    python_version: str
    schema_version: int
    modules: list[ModuleContract]
    language: str = "python"
    metadata: dict = field(default_factory=dict)  # per-language cache read once at load (no subprocess)
    excludes: list[str] = field(default_factory=list)  # paths skipped by discovery AND scanning

    def by_name(self) -> dict[str, ModuleContract]:
        return {m.name: m for m in self.modules}


def _is_ignored(rel: Path, excludes: list[str]) -> bool:
    if any(part in DEFAULT_IGNORE for part in rel.parts):
        return True
    posix = rel.as_posix()
    for pat in excludes:
        pat = pat.rstrip("/")
        if posix == pat or posix.startswith(pat + "/") or fnmatch.fnmatch(posix, pat):
            return True
    return False


def is_excluded(project: "Project", file: Path) -> bool:
    """True if ``file`` (repo-relative) is filtered by DEFAULT_IGNORE or the
    project's ``exclude`` patterns. Used by both check() and the edit hook so
    the two agree on what is in scope."""
    try:
        rel = file.resolve().relative_to(project.root)
    except ValueError:
        return False
    return _is_ignored(rel, project.excludes)


def iter_source_files(project: "Project", module: "ModuleContract", globs):
    """Yield files under ``module.path`` matching ``globs``, skipping
    DEFAULT_IGNORE dirs and the project's ``exclude`` patterns. Single source of
    truth for file discovery so every adapter applies identical scope rules."""
    for f in sorted(p for g in globs for p in module.path.rglob(g)):
        if not is_excluded(project, f):
            yield f


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a YAML mapping, got {type(data).__name__}")
    return data


def load_project(root: Path) -> Project:
    root = root.resolve()
    cfg = _read_yaml(root / ROOT_CONFIG)

    schema_version = int(cfg.get("schema_version", 1))
    if schema_version > SUPPORTED_SCHEMA:
        raise ValueError(
            f"Contracts use schema_version {schema_version}, but this anma build "
            f"supports up to {SUPPORTED_SCHEMA}. Upgrade anma (`pip install -U anma`)."
        )

    # Accept either `source_roots: [..]` or legacy `source_root: "src"`.
    roots = cfg.get("source_roots") or cfg.get("source_root") or ["src"]
    if isinstance(roots, str):
        roots = [roots]
    python_version = str(cfg.get("python_version", "3.10"))
    language = str(cfg.get("language", "python"))
    excludes = list(cfg.get("exclude", []) or [])

    # Resolve the adapter once and read its (declarative, tool-free) metadata a
    # single time. INVARIANT: load_project must never spawn a subprocess — import
    # identity is a pure derivation from this cache; heavy resolution lives in check().
    from .adapters import get_adapter
    adapter = get_adapter(language)
    metadata = adapter.load_metadata(root)

    modules: list[ModuleContract] = []
    for source_root in roots:
        src = (root / source_root).resolve()
        if not src.exists():
            continue
        for module_yaml in sorted(src.rglob(MODULE_CONFIG)):
            if module_yaml.parent == root:
                continue  # the root config itself
            rel = module_yaml.relative_to(root)
            if _is_ignored(rel, excludes):
                continue
            data = _read_yaml(module_yaml)
            if "name" not in data:
                continue
            mc = ModuleContract(
                name=str(data["name"]),
                path=module_yaml.parent,
                summary=str(data.get("summary", "")).strip(),
                public=list(data.get("public", []) or []),
                depends_on=list(data.get("depends_on", []) or []),
                invariants=list(data.get("invariants", []) or []),
                owners=list(data.get("owners", []) or []),
                deprecated_deps=list(data.get("deprecated_deps", []) or []),
            )
            mc._source_root = src
            mc._import_path = adapter.import_identity(mc, src, metadata)
            modules.append(mc)

    return Project(root=root, source_roots=list(roots),
                   python_version=python_version,
                   schema_version=schema_version, modules=modules,
                   language=language, metadata=metadata, excludes=excludes)


def validate(project: Project) -> list[str]:
    issues: list[str] = []
    names = {m.name for m in project.modules}
    if not project.modules:
        issues.append("No module contracts found. Add an anma.yaml with a 'name:' to a module dir.")
    for m in project.modules:
        if not m.summary:
            issues.append(f"[{m.name}] missing 'summary' (needed for the architecture map).")
        for dep in list(m.depends_on) + list(m.deprecated_deps):
            if dep == m.name:
                issues.append(f"[{m.name}] depends on itself.")
            elif dep not in names:
                issues.append(f"[{m.name}] references unknown module '{dep}'.")
    graph = {m.name: {d for d in m.depends_on if d in names} for m in project.modules}
    issues.extend(_find_cycles(graph))
    return issues


def _find_cycles(graph: dict[str, set[str]]) -> list[str]:
    out: list[str] = []
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in graph}

    def dfs(n: str, stack: list[str]) -> None:
        color[n] = GRAY
        stack.append(n)
        for nxt in graph.get(n, ()):
            if color[nxt] == GRAY:
                i = stack.index(nxt)
                out.append("Dependency cycle: " + " -> ".join(stack[i:] + [nxt]))
            elif color[nxt] == WHITE:
                dfs(nxt, stack)
        stack.pop()
        color[n] = BLACK

    for n in graph:
        if color[n] == WHITE:
            dfs(n, [])
    return out
