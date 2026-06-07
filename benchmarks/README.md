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

## Multi-language live results (Go, TypeScript)

Real `claude-code` runs on **Claude Haiku 4.5** (`claude-haiku-4-5-20251001`),
`claude` CLI `2.1.168`, 2026-06-07, **n=10 per arm**. All 40 runs completed with
status `ok` and were scored by the independent per-language scorer (Go via its own
import scanner; TypeScript likewise). ANMA's own enforcement backend in the anma
arm was **dependency-cruiser** for TS and the **builtin** scanner for Go (no Go
toolchain on the bench host — go-arch-lint is implemented but not exercised here).

| Scenario | Arm | n | Violations | Mean | Mean turns | Hook blocks |
|---|---|---:|---:|---:|---:|---:|
| go-payments | control | 10 | 1 | 0.10 | 8.9 | — |
| go-payments | anma | 10 | 0 | 0.00 | 11.9 | 0 |
| ts-payments | control | 10 | 1 | 0.10 | 7.8 | — |
| ts-payments | anma | 10 | 0 | 0.00 | 10.5 | 0 |

**Read this honestly — it is a null/underpowered result, not a Go/TS "win":**

- The direction matches Python (anma 0, control > 0), but the effect is **not
  statistically significant**: Fisher's exact is `p = 1.0` per language (1/10 vs
  0/10) and `p ≈ 0.49` pooled (2/20 vs 0/20).
- Haiku violated the boundary only **~10%** of the time in these control arms, far
  below the **~68%** it showed on the Python `payments-boundary` scenario. So the
  temptation these specific Go/TS scenarios create is weak for this model — there
  was little for ANMA to prevent. This is **not** evidence of parity with the
  Python result, and the strong Python numbers are **not** transferred to Go/TS.
- **Hook blocks = 0** in every anma run: the agent, guided by the generated
  `CLAUDE.md`, did not *attempt* a forbidden import, so the hook had nothing to
  block. The enforcement layer (hook exit 2 on a forbidden Go/TS edit) is verified
  separately by unit tests and a direct invocation, not by these runs.
- ANMA added a few turns (Go 8.9→11.9, TS 7.8→10.5), consistent with prior runs.

To get a discriminating Go/TS number you would need a harder scenario (one where
Haiku slips more often in control) and/or a larger n. Reproduce:

```bash
cd benchmarks
python -m bench.run --runner claude-code --model claude-haiku-4-5-20251001 \
  --trials 10 --scenario go-payments --scenario ts-payments
```

## Honest limits

- Replay numbers validate the instrument, not the model.
- Live numbers depend on model, version, and prompt; report the distribution
  across trials and publish the transcripts rather than a single figure.
- The Go/TS scenarios above are weak discriminators for Haiku 4.5 (low control
  violation rate); treat their numbers as a wired-and-runnable instrument plus a
  null result, not as a measured ANMA benefit for Go/TS.
