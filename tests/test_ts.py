"""TypeScript language-adapter tests.

These ADD coverage for the TS adapter; they do not touch the Python tests in
test_core.py. dependency-cruiser (the external backend) is not assumed installed —
every assertion exercises the zero-dependency builtin path, the guaranteed-available
fallback.
"""
from __future__ import annotations

import json as _json
import subprocess
from pathlib import Path

import pytest

from anma.adapters import LanguageAdapter, get_adapter
from anma.compile import check_drift, sync
from anma.contracts import load_project
from anma.hook import ALLOW, BLOCK, run_hook
from anma.lang_ts import scan_imports
from anma.scaffold import init_project


@pytest.fixture
def ts_project(tmp_path: Path):
    init_project(tmp_path, language="typescript")
    return load_project(tmp_path)


def _payload(tool, file, **inp):
    return _json.dumps({"tool_name": tool, "tool_input": {"file_path": str(file), **inp}})


# ---- registry / protocol --------------------------------------------------- #
def test_ts_adapter_registered_and_conforms():
    a = get_adapter("typescript")
    assert a.language == "typescript"
    assert isinstance(a, LanguageAdapter)


def test_ts_adapter_owns_only_ts():
    a = get_adapter("typescript")
    assert a.handles_file(Path("x/service.ts"))
    assert a.handles_file(Path("x/component.tsx"))
    assert not a.handles_file(Path("x/service.py"))
    assert not a.handles_file(Path("x/service.go"))


# ---- the import detector --------------------------------------------------- #
def test_scan_imports_all_forms():
    src = (
        'import { getUser } from "../accounts/service";\n'
        'import type { User } from "../accounts/types";\n'
        'export { x } from "./local";\n'
        'import "./side-effect";\n'
        'const a = require("../billing/service");\n'
        'const b = await import("@app/billing");\n'
    )
    got = dict(scan_imports(src))
    assert "../accounts/service" in got and got["../accounts/service"] == 1
    assert "../accounts/types" in got        # import type counts as an edge
    assert "./local" in got
    assert "./side-effect" in got
    assert "../billing/service" in got       # require()
    assert "@app/billing" in got             # dynamic import()


def test_scan_imports_handles_multiline():
    src = (
        "import {\n"
        "  getUser,\n"
        "  authenticate,\n"
        '} from "../accounts/service";\n'
    )
    got = dict(scan_imports(src))
    assert "../accounts/service" in got


# ---- metadata + pure import identity --------------------------------------- #
def test_load_metadata_reads_tsconfig(ts_project):
    assert ts_project.language == "typescript"
    assert ts_project.metadata["base_url"].endswith("/src")


def test_import_identity_is_baseurl_relative(ts_project):
    by = ts_project.by_name()
    assert by["accounts"].import_path == "domains/accounts"
    assert by["billing"].import_path == "domains/billing"


def test_import_identity_reverse_maps_path_alias(tmp_path):
    init_project(tmp_path, language="typescript")
    (tmp_path / "tsconfig.json").write_text(
        '{ "compilerOptions": { "baseUrl": "src", "paths": { "@app/*": ["domains/*"] } } }\n')
    proj = load_project(tmp_path)
    assert proj.by_name()["billing"].import_path == "@app/billing"


def test_load_project_never_spawns_subprocess(ts_project, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("load_project must not spawn a subprocess for TypeScript")
    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    p = load_project(ts_project.root)
    assert p.by_name()["billing"].import_path == "domains/billing"


# ---- builtin enforcement (relative-import resolution) ---------------------- #
def test_builtin_check_passes_when_allowed(ts_project):
    assert get_adapter("typescript").check(ts_project, backend="builtin") == []


def test_builtin_check_catches_illegal_import(ts_project):
    svc = ts_project.root / "src/domains/accounts/service.ts"
    svc.write_text('import { totalInvoiced } from "../billing/service";\n' + svc.read_text())
    violations = get_adapter("typescript").check(load_project(ts_project.root), backend="builtin")
    assert len(violations) == 1
    v = violations[0]
    assert v.module == "accounts"
    assert "billing" in v.message
    assert v.line == 1


def test_import_type_counts_as_edge(ts_project):
    svc = ts_project.root / "src/domains/accounts/service.ts"
    svc.write_text('import type { Invoice } from "../billing/service";\n' + svc.read_text())
    violations = get_adapter("typescript").check(load_project(ts_project.root), backend="builtin")
    assert any(v.module == "accounts" and "billing" in v.message for v in violations)


def test_builtin_check_deprecated_is_warning(ts_project):
    y = ts_project.root / "src/domains/accounts/anma.yaml"
    y.write_text(y.read_text() + "deprecated_deps:\n  - billing\n")
    svc = ts_project.root / "src/domains/accounts/service.ts"
    svc.write_text('import { totalInvoiced } from "../billing/service";\n' + svc.read_text())
    violations = get_adapter("typescript").check(load_project(ts_project.root), backend="builtin")
    assert len(violations) == 1
    assert violations[0].deprecated is True


def test_disallowed_targets_is_pure_and_correct(ts_project):
    a = get_adapter("typescript")
    accounts = ts_project.by_name()["accounts"]
    svc = ts_project.root / "src/domains/accounts/service.ts"
    clean = svc.read_text()
    bad = 'import { totalInvoiced } from "../billing/service";\n' + clean
    assert a.disallowed_targets(ts_project, accounts, svc, clean) == set()
    assert a.disallowed_targets(ts_project, accounts, svc, bad) == {"billing"}


# ---- the PreToolUse hook routes .ts edits through the TS adapter ------------ #
def test_hook_blocks_new_ts_violation(ts_project):
    acc = ts_project.root / "src/domains/accounts/service.ts"
    body = 'import { totalInvoiced } from "../billing/service";\n' + acc.read_text()
    assert run_hook(_payload("Write", acc, content=body)) == BLOCK


def test_hook_allows_allowed_direction(ts_project):
    bil = ts_project.root / "src/domains/billing/service.ts"
    body = bil.read_text() + '\nimport { authenticate } from "../accounts/service";\n'
    assert run_hook(_payload("Write", bil, content=body)) == ALLOW


def test_hook_allows_clean_edit(ts_project):
    acc = ts_project.root / "src/domains/accounts/service.ts"
    body = acc.read_text() + "\nexport function extra(): number { return 1; }\n"
    assert run_hook(_payload("Write", acc, content=body)) == ALLOW


def test_hook_no_deadlock_on_preexisting_violation(ts_project):
    acc = ts_project.root / "src/domains/accounts/service.ts"
    acc.write_text('import { totalInvoiced } from "../billing/service";\n' + acc.read_text())
    body = acc.read_text() + "\nexport function unrelated(): number { return 2; }\n"
    assert run_hook(_payload("Write", acc, content=body)) == ALLOW


# ---- generated artifacts --------------------------------------------------- #
def test_sync_generates_depcruiser_and_no_tach(ts_project):
    written = sync(ts_project)
    rel = {Path(w).relative_to(ts_project.root).as_posix() for w in written}
    assert ".dependency-cruiser.cjs" in rel
    assert "tach.toml" not in rel
    assert "src/domains/billing/CLAUDE.md" in rel
    cfg = (ts_project.root / ".dependency-cruiser.cjs").read_text()
    assert "module.exports" in cfg
    assert "accounts-no-billing" in cfg  # accounts may not depend on billing
    assert check_drift(load_project(ts_project.root)) == []


def test_ci_workflow_is_node_flavored(ts_project):
    ci = get_adapter("typescript").ci_workflow(ts_project)
    assert "setup-node" in ci
    assert "dependency-cruiser" in ci
    assert "anma check" in ci


def test_engine_name_falls_back_to_builtin_without_node(ts_project, monkeypatch):
    import anma.lang_ts as lt
    monkeypatch.setattr(lt.shutil, "which", lambda _name: None)
    assert get_adapter("typescript").engine_name(ts_project) == "builtin"
