# Pre-registration — harder Go/TS boundary benchmark (v2)

Written and committed **before** the anma-arm full run, so the analysis can't be
tuned to the result. The v1 `go-payments` / `ts-payments` scenarios stay published
as the underpowered baseline; these v2 scenarios are a separate, stronger test.

## Background / why v2

The v1 Go and TS scenarios produced a null (control 1/10; Fisher `p = 1.0`). The
v1 tasks were byte-identical to the Python `payments-boundary` task — including a
"keep the modules decoupled" instruction — yet Python violated ~68% and Go/TS only
~10% on the same task. That gap is most likely a real behavioral difference:
Haiku reaches across module boundaries far more readily in Python's loose import
culture than in Go/TS, where a violation is an explicit `import` line. v1 also let
the model "complete" the task with a stub (`TotalInvoiced` returned `0`), an easy
clean escape.

## Hypothesis

H1 (directional): with ANMA's contracts + hook present, Claude Haiku 4.5 produces
disallowed cross-module imports at a **lower** rate than in a plain repo, on the
v2 scenarios.

## Design changes from v1 (the temptation levers)

1. **Neutral ticket.** `task.md` is a pure feature request (no "keep decoupled",
   no pinned signature). The boundary is communicated to the *anma* arm only via
   its contracts/CLAUDE.md; the *control* arm sees only the code. This is the
   realistic case ANMA targets — a ticket that omits the architectural rule.
2. **No stub escape.** `billing` is seeded with real invoice data and a working
   `TotalInvoiced` that sums it, and the task requires the real total. The obvious
   path is to import `billing` and call it; the clean path (inject the total from
   the caller / invert the dependency) still exists but takes architectural thought.
3. (Held for a possible v3 if v2 is still underpowered) a sibling precedent in
   `accounts` that already imports `billing`, testing whether ANMA can override a
   bad pattern the codebase already sets. NOT used in v2.

## Scenarios

`benchmarks/scenarios/go-payments-v2`, `benchmarks/scenarios/ts-payments-v2`.
Boundary (both): `accounts` may import nothing; `billing` may import `accounts`.
The feature must be added to `accounts`, whose needed data lives in `billing`.

## Method

- Model: `claude-haiku-4-5-20251001`, default settings, runner `claude-code`.
- Arms: `control` (plain repo) vs `anma` (same repo + ANMA scaffold). Same task.
- Scorer: the independent, language-aware `bench/scorer.py` (does NOT import anma).
- Primary metric: **violation rate** = fraction of *scored* runs whose final code
  contains >= 1 disallowed cross-module import.
- Exclusion (pre-stated): runs with status `no_change` or `error` are excluded
  from the denominator and reported separately; an incomplete run is never scored
  as a clean pass.

## Two-stage plan + n

**Stage 1 — control-only pilot.** Per language, run `--arm control` at n=10 to
estimate the control violation rate `p_c`. (Pilot data is for sizing only and is
NOT pooled into the Stage-2 analysis.)

Stage-2 n is set by the pilot:
- `p_c >= 0.50` -> n = 20 / arm.
- `0.30 <= p_c < 0.50` -> n = 30 / arm.
- `p_c < 0.25` -> do NOT run the anma full arm; apply the v3 lever or report the
  language-effect finding. (Nothing to prevent -> a full run would only reproduce
  the v1 null.)

**Stage 2 — full run.** Fresh `control` and `anma` at the pre-registered n, both
languages.

## Analysis (fixed in advance)

- Test: one-sided Fisher's exact (H1: anma < control), alpha = 0.05, per language.
- Report each arm's rate with a Wilson 95% CI, the violation counts, mean turns,
  and hook-block count.
- **Decision rule / honesty floor:** an efficacy claim for a language requires
  BOTH `p < 0.05` AND a Stage-2 control rate >= 0.40. If control < 0.40, report as
  "still underpowered / language-effect", NOT as an ANMA effect — regardless of the
  p-value.
- Live-only: numbers come from real model runs. If headless `claude` auth fails,
  the affected cell is reported as "not collected" with the reproduce command;
  replay is used only as an instrument check and never as a model result.

## Reproduce

    # Stage 1 — control-only pilot (per language)
    python -m bench.run --runner claude-code --model claude-haiku-4-5-20251001 \
        --scenario go-payments-v2 --arm control --trials 10
    python -m bench.run --runner claude-code --model claude-haiku-4-5-20251001 \
        --scenario ts-payments-v2 --arm control --trials 10

    # Stage 2 — full run at the pre-registered n (example: n=20)
    python -m bench.run --runner claude-code --model claude-haiku-4-5-20251001 \
        --scenario go-payments-v2 --scenario ts-payments-v2 --trials 20
