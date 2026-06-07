# ANMA benchmark harness

A reproducible, with/without-ANMA comparison that **counts architectural
violations** in the code an AI agent produces — the direct test of the claim
"with ANMA, Claude Code respects module boundaries and makes fewer architectural
mistakes."

## What it measures

For each scenario the agent is given the **same task** in two arms:

- **control** — a plain repo whose architecture is documented in prose
  (`README.md`). This is the *fair* baseline: "a normal repo that told the model
  the rules," not an empty repo.
- **anma** — the same repo plus ANMA contracts, the generated nested `CLAUDE.md`,
  and the `PreToolUse` hook.

The agent's final code is then scored by an **independent** counter
(`bench/scorer.py`) that does **not** import `anma`. It counts disallowed
cross-module imports against the scenario's declared graph
(`boundaries.yaml`) — so the benchmark is not graded by the tool it measures.
This independence holds **per language**: Python is scored with `ast`, Go and
TypeScript with small stdlib-`re` scanners that are separate implementations from
anma's adapters, so a parsing bug in anma cannot hide itself in the score.

Reported per arm: mean/total violations, mean turns, and (live runner only) the
number of edits the ANMA hook blocked.

## Run it

Deterministic self-test of the instrument (no API key, fully offline):

```bash
cd benchmarks
python -m bench.run                 # runner: replay
```

Replay applies pre-recorded agent edits from `scenarios/*/replay/<arm>/`. It
proves the scorer and pipeline work; it is **not** a measurement of a live model.

Real measurement (requires the `claude` CLI on PATH + credentials):

```bash
python -m bench.run --runner claude-code --trials 5 --model <model-id>
```

This stages each arm in a temp dir and runs `claude` headlessly with that dir as
cwd, so the repo's `.claude/settings.json` hook and `CLAUDE.md` load for real.
Because models are stochastic, run several trials; every transcript and the
final code state are recorded so results are auditable, not asserted.

> CLI flags evolve — the exact `claude` invocation lives in one place
> (`ClaudeCodeRunner` in `bench/runner.py`). Confirm against your `claude --help`.

Outputs land in `results/` as `results.md` (table) and `results.json` (raw
trials + aggregates).

## Add a scenario

Create `scenarios/<name>/` with:

- `task.md` — the prompt given to the agent (identical across arms).
- `boundaries.yaml` — the ground-truth allowed dependency graph (the scorer's
  judge). Optional `language:` (`python` default, or `go` / `typescript`); for Go
  also set `module_prefix:` (the `go.mod` module path) so import paths reduce to
  the slash-style `path:` values.
- `control/` and `anma/` — the two repo arms (same source; `anma/` adds contracts
  + `anma sync` output, which is the language's native engine config —
  `.go-arch-lint.yml` / `.dependency-cruiser.cjs` instead of `tach.toml`).
- `replay/<arm>/` — optional recorded edits for the offline self-test.

Design tasks that *tempt* a boundary crossing — where the easy path violates the
architecture and the correct path respects it. That is where ANMA either helps
or it doesn't, and the harness will tell you which.

The bundled language scenarios mirror the same accounts/billing boundary:
`payments-boundary` (Python), `go-payments` (Go), `ts-payments` (TypeScript). Each
tempts the agent to add a forbidden `accounts → billing` import.

## Honest limits

- Replay numbers validate the instrument, not the model.
- Live numbers depend on model, version, and prompt; report the distribution
  across trials and publish the transcripts rather than a single figure.
