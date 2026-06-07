# Benchmarks: when does ANMA keep an agent inside the lines?

**It depends on the model — and the data is now clear.** A cheaper/faster model
violates a documented architecture routinely, and ANMA drives that to zero. A
frontier model respects the architecture on its own, so ANMA adds no benefit
there (and adds turns). ANMA's value is **insurance for running cheaper agents**
plus a CI/governance guarantee — not making a frontier model smarter.

Every number here is reproducible with the commands at the bottom.

> **Scope:** all the headline/two-tier numbers below are **Python** (`tach`/`ast`
> engine). Go and TypeScript ship their own scenarios with their own live run,
> reported separately under [Other languages](#other-languages--go-and-typescript)
> — those numbers are an honest null and are **not** the Python result.

## Method

Each scenario gives the agent the **same task** in two arms:

- **control** — a plain repo whose architecture is documented in prose (README).
  The fair baseline: "a normal repo that told the model the rules."
- **anma** — the same repo plus ANMA contracts, the generated nested `CLAUDE.md`,
  and the `PreToolUse` hook.

The agent's final code is scored by an **independent** counter (`bench/scorer.py`)
that does not import `anma`; it counts disallowed cross-module imports against the
scenario's declared graph. Runs that errored or changed no code are marked
`no_change`/`error` and excluded from scoring, so an incomplete run never reads as
a clean pass. Hook blocks are attributed to ANMA only in arms where the hook is
installed (control shows `-`).

## Headline result — Claude Haiku 4.5, `payments-boundary`, n=20

| Arm | Trials | Scored | Violations | Mean | Mean turns |
|---|---:|---:|---:|---:|---:|
| control | 20 | 19 | **13** | **0.68** | 10.3 |
| anma    | 20 | 20 | **0**  | **0.00** | 11.5 |

Same model, same task, 20 trials each. ANMA eliminated boundary violations:
**0 of 20** versus a **~68%** violation rate without it. Fisher's exact test on
13/19 vs 0/20 gives `p < 0.0001` — not noise at this n. (We report "0 of 20," not
"0%": by the rule of three the true rate could be up to ~15%.) The turn-count cost
is small (11.5 vs 10.3). One control run did not complete (`no_change`) and is
excluded, so control is scored n=19.

## Two-tier picture (preliminary, n=5)

### Frontier — Claude Opus 4.8

| Scenario | control | anma | mean turns (ctrl -> anma) |
|---|---:|---:|---|
| payments-boundary (n=1)    | 0.00 | 0.00 | 18 -> 21 |
| orders-inventory           | 0.00 | 0.00 | 9.0 -> 33.8 |
| cross-session-persistence  | 0.00 | 0.00 | 15.6 -> 25.6 |

Opus 4.8 never violated, with or without ANMA, and the anma arm used more turns.
At the frontier, ANMA shows no benefit on this axis.

### Cheaper — Claude Haiku 4.5 (other scenarios)

| Scenario | control | anma | notes |
|---|---:|---:|---|
| orders-inventory          | 0.40 (2/5) | 0.00 (0/3) | anma n=3 (2 `no_change`) |
| cross-session-persistence | 0.00 (0/5) | 0.00 (0/5) | neither violated |

`orders-inventory` points the same way as the headline (2/5 -> 0/5).
`cross-session-persistence` did not induce a violation in either arm at this n, so
it neither supports nor refutes the persistence claim — stated plainly rather than
spun.

## Other languages — Go and TypeScript

The Go and TypeScript adapters ship with their own boundary scenarios
(`go-payments`, `ts-payments`) that mirror the Python `payments-boundary`
temptation, scored by the **same independent, per-language scorer**. Live run on
Claude Haiku 4.5 (`claude-haiku-4-5-20251001`), n=10 per arm, 2026-06-07:

| Scenario | control | anma | mean turns (ctrl -> anma) |
|---|---:|---:|---|
| go-payments | 0.10 (1/10) | 0.00 (0/10) | 8.9 -> 11.9 |
| ts-payments | 0.10 (1/10) | 0.00 (0/10) | 7.8 -> 10.5 |

**This is a null/underpowered result, stated plainly.** The direction matches
Python (anma 0, control > 0) but it is **not significant**: Fisher's exact is
`p = 1.0` per language and `p ≈ 0.49` pooled. Haiku violated these control arms
only ~10% of the time — far below the ~68% on the Python scenario — so there was
little for ANMA to prevent here. The strong Python numbers are **not** transferred
to Go/TS; a harder scenario and/or larger n is needed to measure a real effect.
Backends exercised: TypeScript via `dependency-cruiser`; Go via the builtin scanner
(no Go toolchain on the bench host — `go-arch-lint` is implemented, not exercised).
Hook blocks were 0 (the agent never attempted a forbidden edit). Full method and
the reproduce command are in [benchmarks/README.md](../benchmarks/README.md).

## Two layers, both verified

ANMA has a **guidance** layer (contracts + nested `CLAUDE.md`) and an
**enforcement** layer (the PreToolUse hook).

- **Across all ANMA runs, hook blocks = 0.** The violations were prevented by
  *guidance* — the model was steered to the decoupled solution and never attempted
  a forbidden edit (consistent with the higher anma turn counts).
- **The enforcement layer is verified separately to fire.** Feeding the hook a
  proposed forbidden edit blocks it:

  ```
  $ echo '{"tool_name":"Edit","tool_input":{"file_path":".../accounts/service.py",
      "old_string":"def get_user","new_string":"from domains.billing.service import total_invoiced\ndef get_user"}}' \
    | python3 .claude/hooks/anma_pretooluse.py ; echo "exit: $?"
  ANMA: this edit makes module 'accounts' import [billing], which its contract does not allow.
  exit: 2          # exit 2 => Claude Code blocks the edit
  ```

So: in practice guidance did the work; enforcement is the verified backstop for
edits guidance doesn't catch, and the CI/pre-commit gate is the guarantee
independent of model or author.

## Positioning the evidence supports

- Frontier models already respect documented architecture; don't claim ANMA makes
  them better — it doesn't here, and it adds turns.
- Cheaper/faster models violate routinely (68%), and ANMA prevents it (0/20).
  **ANMA is insurance for running cheaper agents safely**, plus a governance/CI
  guarantee that holds regardless of who or what wrote the diff.
- Publishing the frontier null result next to the Haiku win is the point, not a
  weakness.

## Reproduce

```bash
# headline: 20 trials, cleanest scenario, cheaper model
python -m bench.run --runner claude-code --trials 20 \
  --scenario payments-boundary --model claude-haiku-4-5-20251001

# frontier comparison
python -m bench.run --runner claude-code --trials 20 \
  --scenario payments-boundary --model claude-opus-4-8
```

Provenance:

```
claude --version : 2.1.167 (Claude Code)
models           : claude-haiku-4-5-20251001, claude-opus-4-8
trials per arm   : 20 (payments-boundary headline); 5 (other scenarios)
date             : 2026-06-06
```

Commit the per-trial raw data (`benchmarks/results/results.json` from the headline
run) into the repo so the table is auditable, not asserted.

## Honest limits

- The headline is n=20 on one scenario with one cheaper model; broaden across more
  boundary shapes and other agents to generalize.
- Single model family (Claude). The headline is Python; the Go/TS scenarios are
  wired and runnable but are a weak discriminator for Haiku 4.5 (low control
  violation rate), so their numbers are a null result, not a measured Go/TS benefit.
- The hook was never exercised *in the suite* (guidance pre-empted every bad
  edit); its blocking behavior is verified by the direct test above, not by the
  benchmark runs. A scenario that defeats guidance to force a live hook block is
  future work.
- `no_change` trials are excluded from scoring (1 in the headline control arm).

## Not benchmarked here

Goal #4 (parallel coordination) is a git-worktree demo, not a single-agent
benchmark — tracked separately.
