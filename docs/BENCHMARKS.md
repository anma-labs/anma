# Benchmarks: does ANMA actually keep Claude Code inside the lines?

> **Status: awaiting live data.** The numbers below are placeholders. They are
> filled by running the harness with the real Claude Code runner on a machine
> with the `claude` CLI + credentials. Until then, treat this page as the
> methodology + the slots the evidence drops into. See `benchmarks/README.md`.

## What's measured

Each scenario gives the agent the **same task** in two arms:

- **control** — a plain repo with the architecture documented in prose.
- **anma** — the same repo plus ANMA contracts, the generated nested `CLAUDE.md`,
  and the `PreToolUse` hook.

The agent's final code is scored by an **independent** counter that does not
import `anma`; it counts disallowed cross-module imports against each scenario's
declared boundary graph. Lower is better. (`hook blocks` is how many edits the
ANMA hook rejected live — a direct signal the guardrail fired.)

## How these numbers were produced

```
claude --version   : <fill in, e.g. 2.1.x>
model              : <fill in, e.g. claude-...>
trials per arm     : <fill in, e.g. 5>
command            : python -m bench.run --runner claude-code --trials 5 --model <id>
date               : <fill in>
```

Each run's full transcript and final code state are committed under
`benchmarks/results/` so every number here is auditable, not asserted.

## Results

### Goal: respects module boundaries (single session) — `payments-boundary`

| Arm | Trials | Mean violations | Hook blocks | Notes |
|---|---:|---:|---:|---|
| control | _ | _ | n/a | |
| anma | _ | _ | _ | |

### Goal: preserves architecture across sessions — `cross-session-persistence`

A fresh session is asked to extend code a prior session deliberately decoupled.
Control's rationale lived only in prose; ANMA's lived in `DECISIONS.md` + nested
`CLAUDE.md`, which Claude Code reloads each session.

| Arm | Trials | Mean violations (regressions) | Hook blocks | Notes |
|---|---:|---:|---:|---|
| control | _ | _ | n/a | |
| anma | _ | _ | _ | |

## Reading the result honestly

- If `anma` violations < `control` violations across trials, that is the claim
  demonstrated. Report the spread across trials, not just the mean.
- If `hook blocks` is 0 in the anma arm, the in-session guardrail did **not**
  fire — investigate hook wiring (`.claude/settings.json`, exit code 2) before
  drawing conclusions.
- If the two arms are equal, that is a real and publishable finding too: it means
  the value is in persistence/governance, not single-session steering. Say so.

## Not benchmarked here

Goal #4 (parallel coordination) is not a single-agent benchmark — it's shown as a
git-worktree demo (two agents, disjoint modules, clean merge via the declared
interfaces), tracked separately.
