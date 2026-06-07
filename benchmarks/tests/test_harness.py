"""Tests proving the benchmark instrument is correct and deterministic."""
from __future__ import annotations

import json
from pathlib import Path

from bench.report import aggregate, discover_scenarios
from bench.run import main
from bench.scorer import BoundarySpec, count_violations, load_spec

SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios"


def _spec():
    return BoundarySpec(source_root="src", modules={
        "accounts": {"path": "domains.accounts", "allow": []},
        "billing": {"path": "domains.billing", "allow": ["accounts"]},
    })


def _make_repo(tmp_path: Path, accounts_body: str) -> Path:
    for mod in ("accounts", "billing"):
        d = tmp_path / "src" / "domains" / mod
        d.mkdir(parents=True)
        (d / "__init__.py").write_text("")
    (tmp_path / "src/domains/accounts/service.py").write_text(accounts_body)
    (tmp_path / "src/domains/billing/service.py").write_text(
        "from domains.accounts.service import get_user\n")  # allowed
    return tmp_path


def test_scorer_flags_disallowed_import(tmp_path):
    repo = _make_repo(tmp_path, "from domains.billing.service import total_invoiced\n")
    v = count_violations(repo, _spec())
    assert len(v) == 1
    assert v[0].module == "accounts" and v[0].imported == "billing"


def test_scorer_clean_when_decoupled(tmp_path):
    repo = _make_repo(tmp_path, "def get_user(x):\n    return {}\n")
    assert count_violations(repo, _spec()) == []


def test_allowed_direction_is_not_flagged(tmp_path):
    # billing -> accounts is allowed; should never be a violation
    repo = _make_repo(tmp_path, "def get_user(x):\n    return {}\n")
    assert count_violations(repo, _spec()) == []


def test_scenario_fixture_discovered():
    found = discover_scenarios(SCENARIOS)
    assert any(p.name == "payments-boundary" for p in found)


def test_replay_pipeline_discriminates_arms(tmp_path):
    out = tmp_path / "results"
    rc = main(["--runner", "replay", "--trials", "1", "--out", str(out)])
    assert rc == 0
    data = json.loads((out / "results.json").read_text())
    agg = data["aggregate"]
    assert agg["payments-boundary/control"]["violations_total"] >= 1
    assert agg["payments-boundary/anma"]["violations_total"] == 0


def test_runner_flags_blocked_no_change_run(monkeypatch):
    """A run that errored/blocked and changed nothing must NOT score as clean."""
    import types, json as _json
    import bench.runner as R

    canned = _json.dumps({
        "is_error": False, "num_turns": 25, "subtype": "success",
        "permission_denials": [{"tool_name": "Edit"}],
    })
    monkeypatch.setattr(R.subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(
                            stdout=canned, stderr="", returncode=0))
    arm = SCENARIOS / "payments-boundary" / "anma"
    res = R.ClaudeCodeRunner().run(arm, "task", "anma")
    assert res.turns == 25
    assert res.blocked == 1          # the hook block, counted from permission_denials
    assert res.status == "no_change" # nothing was modified -> not a clean pass


def test_runner_marks_missing_cli_as_error(monkeypatch):
    import bench.runner as R
    def boom(*a, **k):
        raise FileNotFoundError("claude")
    monkeypatch.setattr(R.subprocess, "run", boom)
    res = R.ClaudeCodeRunner().run(SCENARIOS / "payments-boundary" / "anma", "t", "anma")
    assert res.status == "error"


def test_control_arm_blocks_not_attributed_to_anma(monkeypatch):
    """A permission denial in the control arm (no hook) must NOT count as an ANMA block."""
    import types, json as _json
    import bench.runner as R
    canned = _json.dumps({"is_error": False, "num_turns": 12,
                          "permission_denials": [{"tool_name": "Edit"}]})
    monkeypatch.setattr(R.subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(
                            stdout=canned, stderr="", returncode=0))
    res = R.ClaudeCodeRunner().run(SCENARIOS / "payments-boundary" / "control", "t", "control")
    assert res.has_hook is False
    assert res.blocked == 0          # denial exists but is NOT attributed to ANMA


def test_adversarial_scenario_discriminates():
    from bench.scorer import load_spec, count_violations
    from bench.runner import ReplayRunner
    sc = SCENARIOS / "orders-inventory"
    spec = load_spec(sc / "boundaries.yaml")
    r = ReplayRunner(sc)
    ctrl = count_violations(r.run(sc / "control", "t", "control").workdir, spec)
    anma = count_violations(r.run(sc / "anma", "t", "anma").workdir, spec)
    assert len(ctrl) >= 1 and len(anma) == 0


def test_scenario_filter_runs_only_named(tmp_path):
    out = tmp_path / "r"
    rc = main(["--runner", "replay", "--scenario", "orders-inventory", "--out", str(out)])
    assert rc == 0
    data = json.loads((out / "results.json").read_text())
    scenarios = {r["scenario"] for r in data["trials"]}
    assert scenarios == {"orders-inventory"}


def test_scenario_filter_rejects_unknown(tmp_path):
    import pytest
    with pytest.raises(SystemExit):
        main(["--runner", "replay", "--scenario", "does-not-exist", "--out", str(tmp_path)])


# ---- multi-language scenarios: language-aware scorer discriminates arms ----- #
def test_go_scenario_discriminates():
    from bench.scorer import load_spec, count_violations
    from bench.runner import ReplayRunner
    sc = SCENARIOS / "go-payments"
    spec = load_spec(sc / "boundaries.yaml")
    assert spec.language == "go"
    r = ReplayRunner(sc)
    ctrl = count_violations(r.run(sc / "control", "t", "control").workdir, spec)
    anma = count_violations(r.run(sc / "anma", "t", "anma").workdir, spec)
    assert len(ctrl) >= 1 and len(anma) == 0
    assert ctrl[0].module == "accounts" and ctrl[0].imported == "billing"


def test_ts_scenario_discriminates():
    from bench.scorer import load_spec, count_violations
    from bench.runner import ReplayRunner
    sc = SCENARIOS / "ts-payments"
    spec = load_spec(sc / "boundaries.yaml")
    assert spec.language == "typescript"
    r = ReplayRunner(sc)
    ctrl = count_violations(r.run(sc / "control", "t", "control").workdir, spec)
    anma = count_violations(r.run(sc / "anma", "t", "anma").workdir, spec)
    assert len(ctrl) >= 1 and len(anma) == 0
    assert ctrl[0].module == "accounts" and ctrl[0].imported == "billing"


def test_scorer_stays_independent_of_anma():
    """The scorer must NOT import anma — it grades against boundaries.yaml with its
    own parsers, so the tool under measurement cannot grade itself. Checked in a
    fresh interpreter so an unrelated earlier import can't mask a regression."""
    import subprocess
    import sys
    code = (
        "import bench.scorer, sys; "
        "leaked = sorted(m for m in sys.modules if m == 'anma' or m.startswith('anma.')); "
        "assert not leaked, leaked; print('ok')"
    )
    proc = subprocess.run([sys.executable, "-c", code],
                          cwd=str(Path(__file__).resolve().parents[1]),
                          capture_output=True, text=True)
    assert proc.returncode == 0, (proc.stdout + proc.stderr)
