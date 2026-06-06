"""Run the with/without-ANMA boundary benchmark.

    python -m bench.run                      # deterministic replay self-test
    python -m bench.run --runner claude-code --trials 5 --model <id>
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .report import (TrialRecord, aggregate, discover_scenarios, load_task,
                     to_json, to_markdown)
from .runner import build_runner
from .scorer import count_violations, load_spec

ARMS = ("control", "anma")


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(prog="bench",
                                description="ANMA with/without boundary-violation benchmark")
    p.add_argument("--scenarios-dir", default=str(here / "scenarios"))
    p.add_argument("--scenario", action="append", default=None,
                   help="only run scenarios with this directory name (repeatable)")
    p.add_argument("--runner", default="replay", choices=["replay", "claude-code"])
    p.add_argument("--trials", type=int, default=1)
    p.add_argument("--model", default=None)
    p.add_argument("--out", default=str(here / "results"))
    a = p.parse_args(argv)

    scen_paths = discover_scenarios(Path(a.scenarios_dir))
    if not scen_paths:
        raise SystemExit(f"no scenarios under {a.scenarios_dir}")
    if a.scenario:
        wanted = set(a.scenario)
        available = {p.name for p in scen_paths}
        missing = wanted - available
        if missing:
            raise SystemExit(f"unknown scenario(s): {sorted(missing)}; "
                             f"available: {sorted(available)}")
        scen_paths = [p for p in scen_paths if p.name in wanted]
    if a.runner == "replay":
        print("=== REPLAY MODE: validates the harness + scorer, NOT a live-model result ===\n")

    records: list[TrialRecord] = []
    for spath in scen_paths:
        task = load_task(spath)
        spec = load_spec(spath / "boundaries.yaml")
        runner = build_runner(a.runner, spath, a.model)
        for arm in ARMS:
            arm_dir = spath / arm
            if not arm_dir.exists():
                continue
            for t in range(a.trials):
                res = runner.run(arm_dir, task, arm)
                v = count_violations(res.workdir, spec)
                records.append(TrialRecord(spath.name, arm, t, len(v),
                                           res.turns, res.blocked, res.status,
                                           res.has_hook))
                flag = "" if res.status == "ok" else f"  <{res.status}>"
                print(f"  {spath.name}/{arm} trial {t}: "
                      f"{len(v)} violation(s), {res.blocked} hook block(s), "
                      f"{res.turns} turns{flag}")

    agg = aggregate(records)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    md = to_markdown(agg, a.runner)
    (out / "results.md").write_text(md)
    (out / "results.json").write_text(to_json(records, agg))
    print("\n" + md)
    print(f"Wrote {out / 'results.md'} and {out / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
