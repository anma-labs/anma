"""Go language-adapter tests.

These ADD coverage for the Go adapter; they do not touch the Python tests in
test_core.py. The Go external backend (go-arch-lint / go list) is not assumed to
be installed — every assertion here exercises the zero-dependency builtin path,
which is the guaranteed-available fallback.
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
from anma.lang_go import scan_imports
from anma.scaffold import init_project


@pytest.fixture
def go_project(tmp_path: Path):
    init_project(tmp_path, language="go")
    return load_project(tmp_path)


def _payload(tool, file, **inp):
    return _json.dumps({"tool_name": tool, "tool_input": {"file_path": str(file), **inp}})


# ---- registry / protocol --------------------------------------------------- #
def test_go_adapter_registered_and_conforms():
    a = get_adapter("go")
    assert a.language == "go"
    assert isinstance(a, LanguageAdapter)


def test_go_adapter_owns_only_go():
    a = get_adapter("go")
    assert a.handles_file(Path("x/service.go"))
    assert not a.handles_file(Path("x/service.py"))
    assert not a.handles_file(Path("x/service.ts"))


# ---- metadata + pure import identity --------------------------------------- #
def test_load_metadata_reads_go_mod(go_project):
    assert go_project.language == "go"
    assert go_project.metadata["module_path"] == "example.com/shop"


def test_import_identity_is_module_path_plus_dir(go_project):
    by = go_project.by_name()
    assert by["accounts"].import_path == "example.com/shop/domains/accounts"
    assert by["billing"].import_path == "example.com/shop/domains/billing"


def test_load_project_never_spawns_subprocess(go_project, monkeypatch):
    """The Go load path (which runs in the per-edit hook) must be pure."""
    def boom(*a, **k):
        raise AssertionError("load_project must not spawn a subprocess for Go")
    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    p = load_project(go_project.root)
    assert p.by_name()["billing"].import_path == "example.com/shop/domains/billing"


# ---- the builtin import scanner -------------------------------------------- #
def test_scan_imports_single_and_block():
    src = (
        'package x\n'
        'import "fmt"\n'
        'import (\n'
        '    "strings"\n'
        '    alias "example.com/shop/domains/accounts"\n'
        '    _ "example.com/shop/domains/billing"\n'
        '    // a comment\n'
        ')\n'
    )
    got = list(scan_imports(src))
    paths = {p for p, _ in got}
    assert paths == {"fmt", "strings",
                     "example.com/shop/domains/accounts",
                     "example.com/shop/domains/billing"}
    by_path = dict(got)
    assert by_path["fmt"] == 2
    assert by_path["example.com/shop/domains/accounts"] == 5


# ---- builtin enforcement --------------------------------------------------- #
def test_builtin_check_passes_when_allowed(go_project):
    # billing -> accounts is allowed; the scaffold is clean.
    assert get_adapter("go").check(go_project, backend="builtin") == []


def test_builtin_check_catches_illegal_import(go_project):
    svc = go_project.root / "domains/accounts/service.go"
    svc.write_text(svc.read_text() +
                   '\nimport "example.com/shop/domains/billing"\n')
    violations = get_adapter("go").check(load_project(go_project.root), backend="builtin")
    assert len(violations) == 1
    v = violations[0]
    assert v.module == "accounts"
    assert "billing" in v.message
    assert v.line > 0  # real line number captured


def test_builtin_check_deprecated_is_warning(go_project):
    y = go_project.root / "domains/accounts/anma.yaml"
    y.write_text(y.read_text() + "deprecated_deps:\n  - billing\n")
    svc = go_project.root / "domains/accounts/service.go"
    svc.write_text(svc.read_text() +
                   '\nimport "example.com/shop/domains/billing"\n')
    violations = get_adapter("go").check(load_project(go_project.root), backend="builtin")
    assert len(violations) == 1
    assert violations[0].deprecated is True


def test_disallowed_targets_is_pure_and_correct(go_project):
    a = get_adapter("go")
    accounts = go_project.by_name()["accounts"]
    clean = go_project.root / "domains/accounts/service.go"
    bad = clean.read_text() + '\nimport "example.com/shop/domains/billing"\n'
    assert a.disallowed_targets(go_project, accounts, clean, clean.read_text()) == set()
    assert a.disallowed_targets(go_project, accounts, clean, bad) == {"billing"}


# ---- the PreToolUse hook routes .go edits through the Go adapter ------------ #
def test_hook_blocks_new_go_violation(go_project):
    acc = go_project.root / "domains/accounts/service.go"
    body = acc.read_text() + '\nimport "example.com/shop/domains/billing"\n'
    assert run_hook(_payload("Write", acc, content=body)) == BLOCK


def test_hook_allows_allowed_direction(go_project):
    bil = go_project.root / "domains/billing/service.go"
    body = bil.read_text() + '\nimport "example.com/shop/domains/accounts"\n'
    assert run_hook(_payload("Write", bil, content=body)) == ALLOW


def test_hook_allows_clean_edit(go_project):
    acc = go_project.root / "domains/accounts/service.go"
    body = acc.read_text() + "\nfunc extra() int { return 1 }\n"
    assert run_hook(_payload("Write", acc, content=body)) == ALLOW


def test_hook_no_deadlock_on_preexisting_violation(go_project):
    acc = go_project.root / "domains/accounts/service.go"
    acc.write_text(acc.read_text() + '\nimport "example.com/shop/domains/billing"\n')
    body = acc.read_text() + "\nfunc unrelated() int { return 2 }\n"  # keeps the bad import
    assert run_hook(_payload("Write", acc, content=body)) == ALLOW


# ---- generated artifacts --------------------------------------------------- #
def test_sync_generates_go_arch_lint_and_no_tach(go_project):
    written = sync(go_project)
    rel = {Path(w).relative_to(go_project.root).as_posix() for w in written}
    assert ".go-arch-lint.yml" in rel
    assert "tach.toml" not in rel  # tach is Python-only
    assert "domains/billing/CLAUDE.md" in rel
    assert ".claude/hooks/anma_pretooluse.py" in rel
    cfg = (go_project.root / ".go-arch-lint.yml").read_text()
    assert "accounts" in cfg and "billing" in cfg
    assert check_drift(load_project(go_project.root)) == []


def test_ci_workflow_is_go_flavored(go_project):
    ci = get_adapter("go").ci_workflow(go_project)
    assert "setup-go" in ci
    assert "go-arch-lint" in ci
    assert "anma check" in ci


def test_engine_name_falls_back_to_builtin_without_toolchain(go_project, monkeypatch):
    import anma.lang_go as lg
    monkeypatch.setattr(lg.shutil, "which", lambda _name: None)
    assert get_adapter("go").engine_name(go_project) == "builtin"


# ---- scanner skips comments + string/raw literals (hook false-positive guard) ---- #
_BILL = "example.com/shop/domains/billing"


def test_scan_ignores_line_comment():
    assert list(scan_imports(f'package x\n// import "{_BILL}"\n')) == []


def test_scan_ignores_block_comment():
    assert list(scan_imports(f'package x\n/*\nimport "{_BILL}"\n*/\n')) == []


def test_scan_ignores_interpreted_string():
    # a string whose contents look like an import must not be detected
    assert list(scan_imports(f'package x\nvar s = "import \\"{_BILL}\\""\n')) == []


def test_scan_ignores_raw_string_literal():
    assert list(scan_imports(f'package x\nvar s = `\nimport "{_BILL}"\n`\n')) == []


def test_scan_detects_real_single_import():
    assert list(scan_imports(f'package x\nimport "{_BILL}"\n')) == [(_BILL, 2)]


def test_scan_detects_collapsed_one_line_block():
    src = f'package x\nimport ( "fmt"; "{_BILL}" )\n'
    assert [p for p, _ in scan_imports(src)] == ["fmt", _BILL]


def test_scan_detects_trailing_comment_after_real_import():
    got = list(scan_imports(f'package x\nimport "{_BILL}" // needed\n'))
    assert got == [(_BILL, 2)]


# ---- the hook must NOT block an edit whose "import" is only in a comment/string -- #
def test_hook_allows_commented_out_violation(go_project):
    acc = go_project.root / "domains/accounts/service.go"
    body = acc.read_text() + f'\n// import "{_BILL}"\n'
    assert run_hook(_payload("Write", acc, content=body)) == ALLOW


def test_hook_allows_import_text_inside_raw_string(go_project):
    acc = go_project.root / "domains/accounts/service.go"
    body = acc.read_text() + f'\nvar doc = `import "{_BILL}"`\n'
    assert run_hook(_payload("Write", acc, content=body)) == ALLOW


def test_hook_still_blocks_real_violation_alongside_decoy(go_project):
    # a decoy in a comment must not mask a real import on another line
    acc = go_project.root / "domains/accounts/service.go"
    body = (acc.read_text()
            + f'\n// import "{_BILL}"  (decoy)\n'
            + f'\nimport "{_BILL}"\n')
    assert run_hook(_payload("Write", acc, content=body)) == BLOCK
