"""Core tests for ANMA: contracts, validation, compile, and the builtin engine."""
from __future__ import annotations

from pathlib import Path

import pytest

from anma.compile import sync
from anma.contracts import load_project, validate
from anma.engine import check
from anma.scaffold import init_project
from anma.templates import MAP_START


@pytest.fixture
def project(tmp_path: Path):
    init_project(tmp_path)
    return load_project(tmp_path)


def test_init_discovers_modules(project):
    names = {m.name for m in project.modules}
    assert names == {"accounts", "billing"}


def test_import_paths_resolved(project):
    billing = project.by_name()["billing"]
    assert billing.import_path == "domains.billing"


def test_valid_contracts_have_no_issues(project):
    assert validate(project) == []


def test_unknown_dependency_flagged(tmp_path: Path):
    init_project(tmp_path)
    (tmp_path / "src/domains/billing/anma.yaml").write_text(
        "name: billing\nsummary: x\ndepends_on:\n  - ghost\n"
    )
    issues = validate(load_project(tmp_path))
    assert any("unknown module 'ghost'" in i for i in issues)


def test_cycle_detected(tmp_path: Path):
    init_project(tmp_path)
    # make accounts depend on billing -> billing already depends on accounts
    (tmp_path / "src/domains/accounts/anma.yaml").write_text(
        "name: accounts\nsummary: x\ndepends_on:\n  - billing\n"
    )
    issues = validate(load_project(tmp_path))
    assert any("cycle" in i.lower() for i in issues)


def test_sync_generates_expected_artifacts(project):
    written = sync(project)
    rel = {Path(w).relative_to(project.root).as_posix() for w in written}
    assert "CLAUDE.md" in rel
    assert "tach.toml" in rel
    assert "src/domains/billing/CLAUDE.md" in rel
    assert ".claude/hooks/anma_pretooluse.py" in rel
    assert ".claude/rules/boundaries.md" in rel


def test_sync_is_idempotent_on_map(project):
    sync(project)
    first = (project.root / "CLAUDE.md").read_text()
    sync(project)
    second = (project.root / "CLAUDE.md").read_text()
    assert first == second
    assert second.count(MAP_START) == 1  # not duplicated


def test_sync_preserves_user_prose(project):
    root_claude = project.root / "CLAUDE.md"
    sync(project)
    text = "# My Project\n\nHand-written intro.\n\n" + root_claude.read_text().split("\n", 2)[2]
    root_claude.write_text(text)
    sync(project)
    assert "Hand-written intro." in root_claude.read_text()


def test_builtin_engine_passes_when_allowed(project):
    assert check(project, engine="builtin") == []


def test_builtin_engine_catches_illegal_import(project):
    svc = project.root / "src/domains/accounts/service.py"
    svc.write_text(svc.read_text() + "\nfrom domains.billing.service import create_invoice\n")
    violations = check(load_project(project.root), engine="builtin")
    assert len(violations) == 1
    assert violations[0].module == "accounts"
    assert "billing" in violations[0].message


def test_relative_imports_resolved(project):
    # billing/service.py uses an absolute import; add a relative one that is illegal
    svc = project.root / "src/domains/accounts/service.py"
    svc.write_text(svc.read_text() + "\nfrom ...domains.billing import service\n")
    violations = check(load_project(project.root), engine="builtin")
    assert any(v.module == "accounts" for v in violations)


def test_codeowners_generated_from_owners(tmp_path):
    init_project(tmp_path)
    p = tmp_path / "src/domains/billing/anma.yaml"
    p.write_text(p.read_text() + "owners:\n  - '@team-pay'\n")
    sync(load_project(tmp_path))
    co = (tmp_path / ".github/CODEOWNERS").read_text()
    assert "/src/domains/billing/ @team-pay" in co


def test_no_codeowners_without_owners(tmp_path):
    init_project(tmp_path)
    sync(load_project(tmp_path))
    assert not (tmp_path / ".github/CODEOWNERS").exists()


# ---- v0.5.0: drift detection, incremental adoption, monorepo, schema -------

def test_drift_clean_after_sync(project):
    from anma.compile import check_drift
    sync(project)
    assert check_drift(load_project(project.root)) == []


def test_drift_detects_unsynced_contract_edit(project):
    from anma.compile import check_drift
    sync(project)
    y = project.root / "src/domains/billing/anma.yaml"
    y.write_text(y.read_text().replace("Invoices and payment processing.", "Totally new summary."))
    stale = check_drift(load_project(project.root))
    assert any("CLAUDE.md" in s for s in stale)


def test_deprecated_dep_is_a_warning_not_error(project):
    y = project.root / "src/domains/accounts/anma.yaml"
    y.write_text(y.read_text() + "deprecated_deps:\n  - billing\n")
    svc = project.root / "src/domains/accounts/service.py"
    svc.write_text(svc.read_text() + "\nfrom domains.billing.service import create_invoice\n")
    violations = check(load_project(project.root), engine="builtin")
    assert len(violations) == 1
    assert violations[0].deprecated is True


def test_multi_source_root_discovery(tmp_path):
    (tmp_path / "anma.yaml").write_text("schema_version: 1\nsource_roots: [a, b]\n")
    for root, mod in (("a", "auth"), ("b", "api")):
        d = tmp_path / root / "mods" / mod
        d.mkdir(parents=True)
        (d / "anma.yaml").write_text(f"name: {mod}\nsummary: x\ndepends_on: []\n")
    project = load_project(tmp_path)
    assert {m.name for m in project.modules} == {"auth", "api"}
    assert project.source_roots == ["a", "b"]


def test_schema_version_too_new_is_rejected(tmp_path):
    init_project(tmp_path)
    (tmp_path / "anma.yaml").write_text("schema_version: 999\nsource_roots: [src]\n")
    with pytest.raises(ValueError, match="schema_version"):
        load_project(tmp_path)


def test_exclude_dir_skips_modules(tmp_path):
    init_project(tmp_path)  # creates src/domains/{accounts,billing}
    # a vendored copy with its own contract that must be ignored
    vend = tmp_path / "vendor" / "thing"
    vend.mkdir(parents=True)
    (vend / "anma.yaml").write_text("name: vendored\nsummary: x\ndepends_on: []\n")
    (tmp_path / "anma.yaml").write_text(
        "schema_version: 1\nsource_roots: [src, vendor]\nexclude: [vendor]\n")
    names = {m.name for m in load_project(tmp_path).modules}
    assert "vendored" not in names
    assert {"accounts", "billing"} <= names


def test_default_ignore_skips_node_modules(tmp_path):
    init_project(tmp_path)
    nm = tmp_path / "src" / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    (nm / "anma.yaml").write_text("name: junk\nsummary: x\ndepends_on: []\n")
    names = {m.name for m in load_project(tmp_path).modules}
    assert "junk" not in names


# ---- v0.5.1: hook judges the proposed edit; tach expose paths qualified ----
import json as _json
from anma.hook import run_hook, ALLOW, BLOCK


def _payload(tool, file, **inp):
    return _json.dumps({"tool_name": tool, "tool_input": {"file_path": str(file), **inp}})


def test_hook_blocks_new_violation(project):
    sync(project)
    acc = project.root / "src/domains/accounts/service.py"
    # accounts may not import billing
    body = acc.read_text() + "\nfrom domains.billing.service import total_invoiced\n"
    assert run_hook(_payload("Write", acc, content=body)) == BLOCK


def test_hook_allows_clean_edit(project):
    sync(project)
    acc = project.root / "src/domains/accounts/service.py"
    body = acc.read_text() + "\ndef extra():\n    return 1\n"
    assert run_hook(_payload("Write", acc, content=body)) == ALLOW


def test_hook_allows_allowed_direction(project):
    sync(project)
    bil = project.root / "src/domains/billing/service.py"
    body = bil.read_text() + "\nfrom domains.accounts.service import get_user as g\n"
    assert run_hook(_payload("Write", bil, content=body)) == ALLOW


def test_hook_no_deadlock_on_preexisting_violation(project):
    # file already violates on disk; an unrelated edit must NOT be blocked
    sync(project)
    acc = project.root / "src/domains/accounts/service.py"
    acc.write_text(acc.read_text() + "\nfrom domains.billing.service import total_invoiced\n")
    body = acc.read_text() + "\ndef unrelated():\n    return 2\n"  # keeps the bad import
    assert run_hook(_payload("Write", acc, content=body)) == ALLOW


def test_hook_allows_non_module_and_non_py(project):
    sync(project)
    assert run_hook(_payload("Write", project.root / "anma.yaml", content="x: 1")) == ALLOW
    assert run_hook(_payload("Write", project.root / "README.txt", content="hi")) == ALLOW


def test_hook_edit_that_does_not_apply_is_allowed(project):
    sync(project)
    acc = project.root / "src/domains/accounts/service.py"
    assert run_hook(_payload("Edit", acc, old_string="NOT PRESENT", new_string="x")) == ALLOW


def test_tach_expose_paths_are_qualified(project):
    from anma.compile import render_tach_toml
    toml = render_tach_toml(project)
    assert "domains.accounts.service.get_user" in toml          # qualified to import path
    assert '"accounts.service.get_user"' not in toml            # not the bare logical name


def test_anma_yml_is_seed_once_not_drift_checked(project):
    from anma.compile import check_drift
    sync(project)
    ci = project.root / ".github/workflows/anma.yml"
    # user customizes the generated CI (e.g. install path) — must not be drift
    ci.write_text(ci.read_text().replace("pip install anma[tach]",
                                          "pip install -e .[tach]"))
    stale = check_drift(load_project(project.root))
    assert not any("anma.yml" in s for s in stale)


def test_sync_does_not_clobber_customized_ci(project):
    sync(project)
    ci = project.root / ".github/workflows/anma.yml"
    ci.write_text("# my custom CI\n")
    sync(load_project(project.root))
    assert ci.read_text() == "# my custom CI\n"


# ---- v0.6.0: the language-adapter seam (Go/TypeScript plug in here) ----
from anma.adapters import (LanguageAdapter, PythonAdapter, get_adapter,
                           register_adapter, any_adapter_handles, ADAPTERS)
from anma.engine import Violation


def test_default_language_is_python(project):
    assert project.language == "python"
    assert isinstance(get_adapter("python"), PythonAdapter)


def test_unknown_language_is_rejected():
    import pytest
    with pytest.raises(ValueError):
        get_adapter("cobol")


def test_python_adapter_owns_only_py():
    a = get_adapter("python")
    assert a.handles_file(Path("x/service.py"))
    assert not a.handles_file(Path("x/service.go"))
    assert not a.handles_file(Path("x/service.ts"))


def test_python_adapter_conforms_to_protocol():
    assert isinstance(get_adapter("python"), LanguageAdapter)


def test_engine_dispatch_is_extensible(project, monkeypatch):
    """A non-Python language plugs in via the registry and is reached end-to-end,
    with no change to the neutral layers — the whole point of the seam."""
    calls = {"check": 0, "dt": 0}

    class FakeAdapter:
        language = "fake"
        file_globs = ("*.fake",)
        def handles_file(self, file): return file.name.endswith(".fake")
        def load_metadata(self, project_root): return {"k": "v"}
        def import_identity(self, module, source_root, metadata): return module.name
        def check(self, project, backend=None):
            calls["check"] += 1; return [Violation("m", "f.fake", 1, "fake violation")]
        def disallowed_targets(self, project, module, file, source):
            calls["dt"] += 1; return {"billing"} if "billing" in source else set()
        def engine_name(self, project): return "fake-engine"
        def engine_artifacts(self, project): return {project.root / "fake.config": "ok"}
        def ci_workflow(self, project): return "name: fake-ci\n"

    monkeypatch.setitem(ADAPTERS, "fake", FakeAdapter())
    assert any_adapter_handles(Path("a/b.fake"))
    a = get_adapter("fake")
    assert a.engine_name(project) == "fake-engine"
    assert a.check(project) and calls["check"] == 1
    # the hook routes a fake-language edit through the fake adapter's resolver
    from anma.hook import run_hook, BLOCK
    import json as _j
    f = project.root / "src/domains/accounts/widget.fake"
    f.write_text("")
    object.__setattr__(project, "language", "fake")  # not needed; hook reloads project
    # simulate a fake project: write language into the root config so the hook picks it up
    cfg = (project.root / "anma.yaml").read_text()
    (project.root / "anma.yaml").write_text(cfg + "\nlanguage: fake\n")
    payload = _j.dumps({"tool_name": "Write",
                        "tool_input": {"file_path": str(f), "content": "import billing"}})
    assert run_hook(payload) == BLOCK and calls["dt"] >= 1


def test_load_project_never_spawns_subprocess(project, monkeypatch):
    """Invariant: load_project (which runs in the per-edit hook) must be pure —
    no shelling out. import_identity derives from cached metadata, not tools."""
    import subprocess
    def boom(*a, **k):
        raise AssertionError("load_project must not spawn a subprocess")
    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    p = load_project(project.root)            # must succeed with subprocess disabled
    assert p.by_name()["billing"].import_path == "domains.billing"
    assert isinstance(p.metadata, dict)
