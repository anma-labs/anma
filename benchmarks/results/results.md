# ANMA benchmark — runner: `claude-code`

Violations = disallowed cross-module imports in the agent's final code,
counted by an independent scorer against each scenario's declared graph.
Only runs with status `ok` are scored; `no_change`/`error` runs are flagged
so an incomplete run is never read as a clean pass. Hook blocks are `—` for
the control arm (no ANMA hook is installed there).

| Scenario | Arm | Trials | Scored | Mean violations | Total | Mean turns | Hook blocks | Issues |
|---|---|---:|---:|---:|---:|---:|---:|---|
| payments-boundary | control | 20 | 19 | 0.68 | 13 | 10.3 | — | no_change |
| payments-boundary | anma | 20 | 20 | 0.00 | 0 | 11.5 | 0 |  |
