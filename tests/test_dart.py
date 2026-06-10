"""Dart language-adapter tests.

These ADD coverage for the Dart adapter; they do not touch the Python/Go/TS tests.
There is NO external Dart resolver in v1 — every assertion exercises the
zero-dependency builtin masked scanner, the guaranteed-available backend.

The 3-way-agreement tests cross-check anma's two graders (the per-edit hook path
``disallowed_targets`` and the full ``check``) against the benchmark's INDEPENDENT
scorer (``bench.scorer.count_violations``), which does NOT import anma — so a
parsing bug in the adapter cannot hide itself behind an equally-buggy oracle.
"""
from __future__ import annotations

import json as _json
import subprocess
import sys
from pathlib import Path

import pytest

from anma.adapters import LanguageAdapter, get_adapter
from anma.compile import check_drift, sync
from anma.contracts import load_project
from anma.hook import ALLOW, BLOCK, run_hook
from anma.lang_dart import scan_imports
from anma.scaffold import init_project

# The independent scorer lives in the benchmark harness (separate import space).
_BENCH = Path(__file__).resolve().parents[1] / "benchmarks"
if str(_BENCH) not in sys.path:
    sys.path.insert(0, str(_BENCH))
from bench.scorer import BoundarySpec, count_violations  # noqa: E402


@pytest.fixture
def dart_project(tmp_path: Path):
    init_project(tmp_path, language="dart")
    return load_project(tmp_path)


def _payload(tool, file, **inp):
    return _json.dumps({"tool_name": tool, "tool_input": {"file_path": str(file), **inp}})


# ---- registry / protocol --------------------------------------------------- #
def test_dart_adapter_registered_and_conforms():
    a = get_adapter("dart")
    assert a.language == "dart"
    assert isinstance(a, LanguageAdapter)


def test_dart_adapter_owns_only_dart():
    a = get_adapter("dart")
    assert a.handles_file(Path("x/service.dart"))
    assert not a.handles_file(Path("x/service.py"))
    assert not a.handles_file(Path("x/service.ts"))
    assert not a.handles_file(Path("x/service.go"))


# ---- the import detector: import + export, NOT part/part-of ---------------- #
def test_scan_detects_import_and_export():
    src = (
        "import 'package:example_shop/domains/accounts/service.dart';\n"
        "import '../accounts/types.dart' show User;\n"
        "export '../accounts/models.dart';\n"
        "import 'dart:async';\n"
        "import 'package:http/http.dart' as http;\n"
    )
    got = dict(scan_imports(src))
    assert got["package:example_shop/domains/accounts/service.dart"] == 1
    assert "../accounts/types.dart" in got        # `show` clause is fine
    assert "../accounts/models.dart" in got        # export counts as an edge
    assert "dart:async" in got                     # scanner is syntactic; classified later
    assert "package:http/http.dart" in got


def test_scan_excludes_part_directives():
    src = (
        "library shop.accounts;\n"
        "part 'service_impl.dart';\n"
        "part of 'service.dart';\n"
        "part of shop.accounts;\n"
    )
    assert list(scan_imports(src)) == []


def test_scan_detects_relative_and_package_imports():
    src = ("import '../billing/service.dart';\n"
           "import 'package:example_shop/domains/billing/service.dart';\n")
    got = dict(scan_imports(src))
    assert got["../billing/service.dart"] == 1
    assert got["package:example_shop/domains/billing/service.dart"] == 2


# ---- masker skips comments / strings (hook false-positive guard) ----------- #
_BILL = "package:example_shop/domains/billing/service.dart"


def test_scan_ignores_line_comment():
    assert list(scan_imports(f"// import '{_BILL}';\n")) == []


def test_scan_ignores_doc_comment():               # ///
    assert list(scan_imports(f"/// import '{_BILL}';\n")) == []


def test_scan_ignores_block_comment():
    assert list(scan_imports(f"/*\nimport '{_BILL}';\n*/\n")) == []


def test_scan_ignores_nested_block_comment():
    assert list(scan_imports(f"/* outer /* import '{_BILL}'; */ tail */\n")) == []


def test_scan_ignores_double_quoted_string():
    assert list(scan_imports(f"final s = \"import '{_BILL}'\";\n")) == []


def test_scan_ignores_single_quoted_string():
    assert list(scan_imports(f"final s = 'import \"{_BILL}\"';\n")) == []


def test_scan_ignores_triple_single_quoted_string():
    assert list(scan_imports(f"final s = '''\nimport '{_BILL}';\n''';\n")) == []


def test_scan_ignores_triple_double_quoted_string():
    assert list(scan_imports(f'final s = """\nimport \'{_BILL}\';\n""";\n')) == []


def test_scan_ignores_raw_string():
    assert list(scan_imports(f"final s = r\"import '{_BILL}'\";\n")) == []


def test_scan_ignores_interpolation_expression():
    # import-looking text inside ${...} (with a nested string) must not desync.
    src = f'final s = "x ${{wrap("import \'{_BILL}\';")}}";\n'
    assert list(scan_imports(src)) == []


def test_scan_detects_real_import_despite_interpolation():
    # a benign interpolated string must not hide a real import on another line.
    src = f"import '{_BILL}';\n" + 'final s = "v=${1 + 1} done";\n'
    assert list(scan_imports(src)) == [(_BILL, 1)]


# ---- metadata + pure import identity (no subprocess) ----------------------- #
def test_load_metadata_reads_pubspec(dart_project):
    assert dart_project.language == "dart"
    assert dart_project.metadata["package_name"] == "example_shop"
    assert dart_project.metadata["lib_root"].endswith("/lib")


def test_import_identity_is_package_uri(dart_project):
    by = dart_project.by_name()
    assert by["accounts"].import_path == "package:example_shop/domains/accounts"
    assert by["billing"].import_path == "package:example_shop/domains/billing"


def test_load_project_never_spawns_subprocess(dart_project, monkeypatch):
    """The Dart load path (which runs in the per-edit hook) must be pure."""
    def boom(*a, **k):
        raise AssertionError("load_project must not spawn a subprocess for Dart")
    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    p = load_project(dart_project.root)
    assert p.by_name()["billing"].import_path == "package:example_shop/domains/billing"


# ---- builtin enforcement --------------------------------------------------- #
def test_builtin_check_passes_when_allowed(dart_project):
    assert get_adapter("dart").check(dart_project, backend="builtin") == []


def test_builtin_check_catches_relative_violation(dart_project):
    svc = dart_project.root / "lib/domains/accounts/service.dart"
    svc.write_text("import '../billing/service.dart';\n" + svc.read_text())
    violations = get_adapter("dart").check(load_project(dart_project.root), backend="builtin")
    assert len(violations) == 1
    v = violations[0]
    assert v.module == "accounts" and "billing" in v.message and v.line == 1


def test_builtin_check_catches_package_violation(dart_project):
    svc = dart_project.root / "lib/domains/accounts/service.dart"
    svc.write_text(
        "import 'package:example_shop/domains/billing/service.dart';\n" + svc.read_text())
    violations = get_adapter("dart").check(load_project(dart_project.root), backend="builtin")
    assert any(v.module == "accounts" and "billing" in v.message for v in violations)


def test_builtin_check_catches_export_edge(dart_project):
    svc = dart_project.root / "lib/domains/accounts/service.dart"
    svc.write_text("export '../billing/service.dart';\n" + svc.read_text())
    violations = get_adapter("dart").check(load_project(dart_project.root), backend="builtin")
    assert any(v.module == "accounts" and "billing" in v.message for v in violations)


def test_builtin_check_ignores_sdk_thirdparty_and_parts(dart_project):
    svc = dart_project.root / "lib/domains/accounts/service.dart"
    svc.write_text(
        "import 'dart:async';\n"
        "import 'package:http/http.dart';\n"
        "part 'extra.dart';\n" + svc.read_text())
    (dart_project.root / "lib/domains/accounts/extra.dart").write_text(
        "part of 'service.dart';\n")
    assert get_adapter("dart").check(load_project(dart_project.root), backend="builtin") == []


def test_builtin_check_deprecated_is_warning(dart_project):
    y = dart_project.root / "lib/domains/accounts/anma.yaml"
    y.write_text(y.read_text() + "deprecated_deps:\n  - billing\n")
    svc = dart_project.root / "lib/domains/accounts/service.dart"
    svc.write_text("import '../billing/service.dart';\n" + svc.read_text())
    violations = get_adapter("dart").check(load_project(dart_project.root), backend="builtin")
    assert len(violations) == 1
    assert violations[0].deprecated is True


def test_disallowed_targets_is_pure_and_correct(dart_project):
    a = get_adapter("dart")
    accounts = dart_project.by_name()["accounts"]
    svc = dart_project.root / "lib/domains/accounts/service.dart"
    clean = svc.read_text()
    rel_bad = "import '../billing/service.dart';\n" + clean
    pkg_bad = "import 'package:example_shop/domains/billing/service.dart';\n" + clean
    assert a.disallowed_targets(dart_project, accounts, svc, clean) == set()
    assert a.disallowed_targets(dart_project, accounts, svc, rel_bad) == {"billing"}
    assert a.disallowed_targets(dart_project, accounts, svc, pkg_bad) == {"billing"}


# ---- the PreToolUse hook routes .dart edits through the Dart adapter -------- #
def test_hook_blocks_new_dart_violation(dart_project):
    acc = dart_project.root / "lib/domains/accounts/service.dart"
    body = "import '../billing/service.dart';\n" + acc.read_text()
    assert run_hook(_payload("Write", acc, content=body)) == BLOCK


def test_hook_allows_allowed_direction(dart_project):
    bil = dart_project.root / "lib/domains/billing/service.dart"
    body = bil.read_text() + "\nimport '../accounts/service.dart';\n"
    assert run_hook(_payload("Write", bil, content=body)) == ALLOW


def test_hook_allows_clean_edit(dart_project):
    acc = dart_project.root / "lib/domains/accounts/service.dart"
    body = acc.read_text() + "\nint extra() => 1;\n"
    assert run_hook(_payload("Write", acc, content=body)) == ALLOW


def test_hook_no_deadlock_on_preexisting_violation(dart_project):
    acc = dart_project.root / "lib/domains/accounts/service.dart"
    acc.write_text("import '../billing/service.dart';\n" + acc.read_text())
    body = acc.read_text() + "\nint unrelated() => 2;\n"   # keeps the bad import
    assert run_hook(_payload("Write", acc, content=body)) == ALLOW


def test_hook_allows_import_text_in_comment(dart_project):
    acc = dart_project.root / "lib/domains/accounts/service.dart"
    body = acc.read_text() + f"\n// import '{_BILL}';\n"
    assert run_hook(_payload("Write", acc, content=body)) == ALLOW


def test_hook_allows_import_text_in_string(dart_project):
    acc = dart_project.root / "lib/domains/accounts/service.dart"
    body = acc.read_text() + f"\nfinal doc = \"import '{_BILL}'\";\n"
    assert run_hook(_payload("Write", acc, content=body)) == ALLOW


def test_hook_still_blocks_real_violation_with_decoy(dart_project):
    acc = dart_project.root / "lib/domains/accounts/service.dart"
    body = (f"// import '{_BILL}';   (decoy)\n"
            f"import '{_BILL}';\n" + acc.read_text())
    assert run_hook(_payload("Write", acc, content=body)) == BLOCK


# ---- generated artifacts --------------------------------------------------- #
def test_sync_generates_claude_and_hook_no_tach(dart_project):
    written = sync(dart_project)
    rel = {Path(w).relative_to(dart_project.root).as_posix() for w in written}
    assert "tach.toml" not in rel                    # tach is Python-only
    assert "lib/domains/billing/CLAUDE.md" in rel
    assert ".claude/hooks/anma_pretooluse.py" in rel
    assert check_drift(load_project(dart_project.root)) == []


def test_ci_workflow_is_dart_flavored(dart_project):
    ci = get_adapter("dart").ci_workflow(dart_project)
    assert "setup-dart" in ci
    assert "anma check" in ci


def test_engine_name_is_builtin(dart_project):
    assert get_adapter("dart").engine_name(dart_project) == "builtin"


# ---- 3-way agreement: disallowed_targets == check == independent scorer ----- #
def _dart_spec() -> BoundarySpec:
    return BoundarySpec(
        source_root="lib",
        modules={
            "accounts": {"path": "domains/accounts", "allow": []},
            "billing": {"path": "domains/billing", "allow": ["accounts"]},
        },
        language="dart",
        package_name="example_shop",
    )


def _build_violating_fixture(root: Path) -> None:
    init_project(root, language="dart")          # clean accounts/billing scaffold
    acc = root / "lib/domains/accounts/service.dart"
    acc.write_text(
        "import 'dart:async';\n"                                          # SDK — ignored
        "import 'package:http/http.dart';\n"                             # third-party — ignored
        "import '../billing/service.dart';\n"                            # RELATIVE cross-boundary
        "import 'package:example_shop/domains/billing/service.dart';\n"  # package:<own> cross-boundary
        "export '../billing/models.dart';\n"                             # export edge cross-boundary
        "part 'helpers.dart';\n"                                         # part — NOT an edge
        "\nclass Account {}\n"
    )
    (root / "lib/domains/accounts/helpers.dart").write_text("part of 'service.dart';\n")
    (root / "lib/domains/billing/models.dart").write_text("class Invoice {}\n")


def test_three_way_agreement_on_violations(tmp_path):
    """All three graders see exactly the accounts->billing edges (relative +
    package:<own> + export) and ignore dart:/third-party/part."""
    _build_violating_fixture(tmp_path)
    project = load_project(tmp_path)
    adapter = get_adapter("dart")
    accounts = project.by_name()["accounts"]
    acc_file = tmp_path / "lib/domains/accounts/service.dart"

    dt = adapter.disallowed_targets(project, accounts, acc_file, acc_file.read_text())
    check_v = [v for v in adapter.check(project, backend="builtin") if v.module == "accounts"]
    score_v = [v for v in count_violations(tmp_path, _dart_spec()) if v.module == "accounts"]

    # the disallowed target is `billing` for all three
    assert dt == {"billing"}
    assert {v.imported for v in score_v} == {"billing"}
    assert {v.module for v in check_v} == {"accounts"}
    assert all("billing" in v.message for v in check_v)
    # the two line-level graders agree on the count of offending directives:
    # relative import + package:<own> import + export == 3 (SDK/3rd-party/part excluded)
    assert len(check_v) == 3
    assert len(score_v) == 3


def test_three_way_agreement_on_clean_scaffold(tmp_path):
    init_project(tmp_path, language="dart")
    project = load_project(tmp_path)
    adapter = get_adapter("dart")
    billing = project.by_name()["billing"]
    bil_file = tmp_path / "lib/domains/billing/service.dart"
    # billing -> accounts is allowed; the scaffold is clean for all three graders.
    assert adapter.disallowed_targets(project, billing, bil_file, bil_file.read_text()) == set()
    assert adapter.check(project, backend="builtin") == []
    assert count_violations(tmp_path, _dart_spec()) == []
