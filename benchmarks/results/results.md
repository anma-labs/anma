# ANMA benchmark — runner: `claude-code`

Violations = disallowed cross-module imports in the agent's final code,
counted by an independent scorer against each scenario's declared graph.
Only runs with status `ok` are scored; `no_change`/`error` runs are flagged
so an incomplete run is never read as a clean pass. Hook blocks are `—` for
the control arm (no ANMA hook is installed there).

| Scenario | Arm | Trials | Scored | Mean violations | Total | Mean turns | Hook blocks | Issues |
|---|---|---:|---:|---:|---:|---:|---:|---|
| ts-payments-v2 | control | 10 | 10 | 0.90 | 9 | 8.0 | — |  |
