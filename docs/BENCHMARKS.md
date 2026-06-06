# Benchmarks: when does ANMA keep an agent inside the lines?

**Short answer from the data so far: it depends on the model.** A frontier model
respects a documented architecture on its own; a cheaper/faster model does not,
and ANMA drives its violation rate to zero. ANMA's value is *insurance for
running cheaper agents* plus a CI/governance guarantee — not making a strong
model smarter.

These are preliminary numbers (n=5). The headline figure needs n>=20 — see
"Reproduce" below. Every claim here is something you can re-run.

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

## Results (preliminary, n=5 per arm)

### Frontier model — Claude Opus 4.8

| Scenario | control violations | anma violations | mean turns (ctrl -> anma) |
|---|---:|---:|---|
| payments-boundary (dagger) | 0.00 | 0.00 | 18 -> 21 |
| orders-inventory           | 0.00 | 0.00 | 9.0 -> 33.8 |
| cross-session-persistence  | 0.00 | 0.00 | 15.6 -> 25.6 |

(dagger) payments-boundary at frontier is n=1 so far; others n=5. **Finding:**
Opus 4.8 never violated, with or without ANMA — and the anma arm used noticeably
more turns. At the frontier, ANMA shows no benefit on this axis and adds cost.

### Cheaper model — Claude Haiku 4.5

| Scenario | control violations | anma violations | scored | mean turns (ctrl -> anma) |
|---|---:|---:|---|---|
| payments-boundary         | **1.00 (5/5)** | **0.00 (0/5)** | 5/5 | 9.4 -> 10.4 |
| orders-inventory          | 0.40 (2/5)     | 0.00 (0/3)     | anma 3/5 (2 no_change) | 9.0 -> 12.6 |
| cross-session-persistence | 0.00 (0/5)     | 0.00 (0/5)     | 5/5 | 8.2 -> 13.2 |

**Finding:** on `payments-boundary`, Haiku violated the boundary in **every**
control trial and in **none** of the ANMA trials. `orders-inventory` points the
same way (2/5 -> 0/5). Same model, same task — the only difference is ANMA.

## Two layers, both verified

ANMA has a **guidance** layer (contracts + nested `CLAUDE.md` steering the model)
and an **enforcement** layer (the PreToolUse hook that hard-blocks a bad edit).

- **Hook blocks in the suite were 0.** The violations were prevented by
  *guidance* — the model was steered to the decoupled solution and never attempted
  a forbidden edit. (Consistent with the higher anma turn counts: it did the
  decoupled work.)
- **The enforcement layer is verified separately to fire.** Feeding the hook a
  proposed forbidden edit blocks it:

  ```
  $ echo '{"tool_name":"Edit","tool_input":{"file_path":".../accounts/service.py",
      "old_string":"def get_user","new_string":"from domains.billing.service import total_invoiced\ndef get_user"}}' \
    | python3 .claude/hooks/anma_pretooluse.py ; echo "exit: $?"
  ANMA: this edit makes module 'accounts' import [billing], which its contract does not allow.
  exit: 2          # exit 2 => Claude Code blocks the edit
  ```

So: guidance does most of the work in practice; enforcement is the backstop for
the edits guidance doesn't catch, and the CI/pre-commit gate is the guarantee
independent of model or author.

## What this means for positioning

- Frontier models already respect documented architecture. Don't claim ANMA makes
  them better — it doesn't here, and it adds turns.
- Cheaper/faster models — which many teams run for cost — violate routinely, and
  ANMA prevents it. **ANMA is insurance for running cheaper agents safely**, plus
  a governance/CI guarantee that holds regardless of who or what wrote the diff.
- Publishing the frontier null result next to the Haiku win is the point, not a
  weakness: "no help for frontier, decisive for cheap models" is more credible and
  more useful than a vague "fewer mistakes."

## Reproduce

```bash
# headline number: 20 trials on the cleanest scenario, cheaper model
python -m bench.run --runner claude-code --trials 20 \
  --scenario payments-boundary --model claude-haiku-4-5-20251001

# frontier comparison
python -m bench.run --runner claude-code --trials 20 \
  --scenario payments-boundary --model claude-opus-4-8
```

Provenance for the numbers above:

```
claude --version : 2.1.167 (Claude Code)
models           : claude-opus-4-8, claude-haiku-4-5-20251001
trials per arm   : 5 (preliminary)
date             : 2026-06-06
```

## Honest limits

- n=5 is enough to see the effect, not to quantify it. Run >=20 for a headline.
- Single model family (Claude) and three hand-built scenarios. Broader coverage
  (more boundary shapes, other agents) would strengthen the claim.
- The hook was never exercised *in the suite* (guidance pre-empted every bad
  edit); its blocking behavior is verified by the direct test above, not by the
  benchmark runs. A scenario that defeats guidance to force a live hook block is
  future work.
- `no_change` trials (2 on Haiku `orders-inventory`) are excluded from scoring,
  so that arm is n=3, not 5.

## Not benchmarked here

Goal #4 (parallel coordination) is a git-worktree demo, not a single-agent
benchmark — tracked separately.
