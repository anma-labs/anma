"""Scenario discovery and result reporting."""
from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path


def discover_scenarios(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.iterdir()
                  if (p / "task.md").exists() and (p / "boundaries.yaml").exists())


def load_task(scenario_dir: Path) -> str:
    return (scenario_dir / "task.md").read_text().strip()


@dataclass
class TrialRecord:
    scenario: str
    arm: str
    trial: int
    violations: int
    turns: int
    blocked: int


def aggregate(records: list[TrialRecord]) -> dict:
    groups: dict[tuple[str, str], list[TrialRecord]] = {}
    for r in records:
        groups.setdefault((r.scenario, r.arm), []).append(r)
    agg = {}
    for key, rs in groups.items():
        v = [r.violations for r in rs]
        agg[key] = {
            "n": len(rs),
            "violations_mean": statistics.mean(v),
            "violations_total": sum(v),
            "turns_mean": statistics.mean([r.turns for r in rs]) if rs else 0,
            "blocked_total": sum(r.blocked for r in rs),
        }
    return agg


def to_markdown(agg: dict, runner_name: str) -> str:
    scenarios = sorted({s for (s, _a) in agg})
    lines = [
        f"# ANMA benchmark — runner: `{runner_name}`",
        "",
        "Violations = disallowed cross-module imports in the agent's final code,",
        "counted by an independent scorer against each scenario's declared graph.",
        "",
        "| Scenario | Arm | Trials | Mean violations | Total | Mean turns | Hook blocks |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for s in scenarios:
        for a in ("control", "anma"):
            d = agg.get((s, a))
            if d:
                lines.append(
                    f"| {s} | {a} | {d['n']} | {d['violations_mean']:.2f} | "
                    f"{d['violations_total']} | {d['turns_mean']:.1f} | {d['blocked_total']} |")
    return "\n".join(lines) + "\n"


def to_json(records: list[TrialRecord], agg: dict) -> str:
    return json.dumps({
        "trials": [r.__dict__ for r in records],
        "aggregate": {f"{s}/{a}": d for (s, a), d in agg.items()},
    }, indent=2)
