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
    status: str = "ok"
    has_hook: bool = False


def aggregate(records: list[TrialRecord]) -> dict:
    groups: dict[tuple[str, str], list[TrialRecord]] = {}
    for r in records:
        groups.setdefault((r.scenario, r.arm), []).append(r)
    agg = {}
    for key, rs in groups.items():
        ok = [r for r in rs if r.status == "ok"]
        v = [r.violations for r in ok]
        has_hook = any(r.has_hook for r in rs)
        agg[key] = {
            "n": len(rs),
            "n_scored": len(ok),
            "violations_mean": (statistics.mean(v) if v else None),
            "violations_total": sum(v),
            "turns_mean": statistics.mean([r.turns for r in rs]) if rs else 0,
            "blocked_total": sum(r.blocked for r in rs),
            "has_hook": has_hook,
            "non_ok": sorted({r.status for r in rs if r.status != "ok"}),
        }
    return agg


def to_markdown(agg: dict, runner_name: str) -> str:
    scenarios = sorted({s for (s, _a) in agg})
    lines = [
        f"# ANMA benchmark — runner: `{runner_name}`",
        "",
        "Violations = disallowed cross-module imports in the agent's final code,",
        "counted by an independent scorer against each scenario's declared graph.",
        "Only runs with status `ok` are scored; `no_change`/`error` runs are flagged",
        "so an incomplete run is never read as a clean pass. Hook blocks are `—` for",
        "the control arm (no ANMA hook is installed there).",
        "",
        "| Scenario | Arm | Trials | Scored | Mean violations | Total | Mean turns | Hook blocks | Issues |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for s in scenarios:
        for a in ("control", "anma"):
            d = agg.get((s, a))
            if d:
                mean = "—" if d["violations_mean"] is None else f"{d['violations_mean']:.2f}"
                blocks = str(d["blocked_total"]) if d["has_hook"] else "—"
                issues = ", ".join(d["non_ok"]) if d["non_ok"] else ""
                lines.append(
                    f"| {s} | {a} | {d['n']} | {d['n_scored']} | {mean} | "
                    f"{d['violations_total']} | {d['turns_mean']:.1f} | "
                    f"{blocks} | {issues} |")
    return "\n".join(lines) + "\n"


def to_json(records: list[TrialRecord], agg: dict) -> str:
    return json.dumps({
        "trials": [r.__dict__ for r in records],
        "aggregate": {f"{s}/{a}": d for (s, a), d in agg.items()},
    }, indent=2)
