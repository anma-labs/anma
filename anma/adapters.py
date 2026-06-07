"""Language adapters — the per-language seam of the boundary engine.

The contract GRAPH is language-neutral: a module's ``name``, ``depends_on``,
``invariants`` and ``owners`` read identically in any language, and that is what
the generated guidance (CLAUDE.md) is built from. Everything that touches source
*syntax* lives behind a ``LanguageAdapter``:

* which files the language owns                      -> ``handles_file``
* how a module maps to its native import identity    -> ``import_identity``
* parsing imports / detecting disallowed cross-module deps
                                                     -> ``check`` / ``disallowed_targets``
* what engine config + CI the language generates     -> ``engine_artifacts`` / ``ci_workflow``

Python is implemented here, delegating to :mod:`anma.engine`. Go and TypeScript
adapters register into :data:`ADAPTERS` without touching the neutral layers.

See DECISIONS.md: the contract graph (name + depends_on + invariants + owners) is
language-neutral and shared; import identity and the public surface are
language-native and adapter-derived; the import->module resolver is per-language.
"""
from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
from typing import Protocol, runtime_checkable

from . import engine
from .contracts import ModuleContract, Project


@runtime_checkable
class LanguageAdapter(Protocol):
    """The contract a language plugs into. Implement this for Go/TypeScript."""

    language: str
    file_globs: tuple[str, ...]

    def handles_file(self, file: Path) -> bool: ...
    def load_metadata(self, project_root: Path) -> dict: ...
    def import_identity(self, module: ModuleContract, source_root: Path,
                        metadata: dict) -> str: ...
    def check(self, project: Project, backend: str | None = None) -> list[engine.Violation]: ...
    def disallowed_targets(self, project: Project, module: ModuleContract,
                           file: Path, source: str) -> set[str]: ...
    def engine_name(self, project: Project) -> str: ...
    def engine_artifacts(self, project: Project) -> dict[Path, str]: ...
    def ci_workflow(self, project: Project) -> str: ...


class PythonAdapter:
    """Python implementation. The full import-parsing logic lives in anma.engine
    (tach backend, with a zero-dependency ``ast`` fallback)."""

    language = "python"
    file_globs = ("*.py",)

    def handles_file(self, file: Path) -> bool:
        return any(fnmatch(file.name, g) for g in self.file_globs)

    def load_metadata(self, project_root: Path) -> dict:
        # Python needs no extra metadata; dotted derivation is pure from source_root.
        # (Go reads go.mod here; TypeScript reads tsconfig — plain file reads, no tools.)
        return {}

    def import_identity(self, module: ModuleContract, source_root: Path,
                        metadata: dict) -> str:
        # Python convention: dotted path from the source root (e.g. domains.billing).
        # Pure: no subprocess, no tool — safe to call in the per-edit hook path.
        rel = module.path.resolve().relative_to(source_root.resolve())
        return ".".join(rel.parts)

    def check(self, project: Project, backend: str | None = None) -> list[engine.Violation]:
        return engine.check(project, backend)

    def disallowed_targets(self, project: Project, module: ModuleContract,
                           file: Path, source: str) -> set[str]:
        return engine.disallowed_targets(project, module, file, source)

    def engine_name(self, project: Project) -> str:
        return engine.detect_engine()

    def engine_artifacts(self, project: Project) -> dict[Path, str]:
        # tach.toml is python/tach-specific; other languages emit their own config.
        from .compile import render_tach_toml
        return {project.root / "tach.toml": render_tach_toml(project)}

    def ci_workflow(self, project: Project) -> str:
        from .compile import render_ci
        return render_ci(project)


# Registry. Phase 1 (Go, TypeScript) registers here via ``register_adapter``.
ADAPTERS: dict[str, "LanguageAdapter"] = {
    PythonAdapter.language: PythonAdapter(),
}


def register_adapter(adapter: "LanguageAdapter") -> None:
    ADAPTERS[adapter.language] = adapter


def get_adapter(language: str) -> "LanguageAdapter":
    try:
        return ADAPTERS[language]
    except KeyError:
        supported = ", ".join(sorted(ADAPTERS))
        raise ValueError(
            f"unsupported language '{language}'. This anma build supports: "
            f"{supported}. (Go and TypeScript adapters plug in here.)"
        ) from None


def any_adapter_handles(file: Path) -> bool:
    """True if *any* registered language owns this file type (cheap hook pre-filter)."""
    return any(a.handles_file(file) for a in ADAPTERS.values())


# --------------------------------------------------------------------------- #
# Language adapters that live in their own leaf modules self-register here at    #
# import time, so a single `import anma.adapters` (done by the CLI and the hook) #
# makes them available with no extra wiring. They import only engine + contracts #
# — never this module — so there is no import cycle and the neutral layers are    #
# untouched.                                                                     #
# --------------------------------------------------------------------------- #
from .lang_go import GoAdapter  # noqa: E402

register_adapter(GoAdapter())

from .lang_ts import TsAdapter  # noqa: E402

register_adapter(TsAdapter())
