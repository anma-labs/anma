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
