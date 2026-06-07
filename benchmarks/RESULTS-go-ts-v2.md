# Results — harder Go/TS boundary benchmark (v2)

Outcome of the pre-registered study in
[`PREREGISTRATION-go-ts-v2.md`](PREREGISTRATION-go-ts-v2.md). Analysis fixed before
the data; reported here exactly as specified, including the floor that Go did not
clear.

## Setup as run

- Model: `claude-haiku-4-5-20251001`, runner `claude-code`, 2026-06-07.
- Scorer: independent per-language `bench/scorer.py` (does not import `anma`).
- Stage-1 control-only pilot (sizing only, NOT pooled below): Go 4/10, TS 9/10 →
  Go in the 0.30–0.50 band → n=30; TS well above floor → n=20.
- Stage 2 run in chunks (a mid-run reboot ate an earlier attempt; chunking caps the
  loss). All runs scored `ok`; none excluded.

## Stage-2 data (pooled from chunks)

Go (n=30/arm): control 3+4+3 = **10/30**; anma 0+0+0 = **0/30**
(chunks `results/go-1`, `go-2`, `go-3`).
TS (n=20/arm): control 10+8 = **18/20**; anma 0+0 = **0/20**
(chunks `results/ts-1`, `ts-2`).

| Scenario | arm | n | violations | rate | 95% CI (Wilson) | mean turns |
|---|---|---:|---:|---:|---|---:|
| ts-payments-v2 | control | 20 | 18 | 0.90 | 70%–97% | 8.1 |
| ts-payments-v2 | anma | 20 | 0 | 0.00 | 0%–16% | 12.5 |
| go-payments-v2 | control | 30 | 10 | 0.33 | 19%–51% | 9.2 |
| go-payments-v2 | anma | 30 | 0 | 0.00 | 0%–11% | 13.7 |

Hook blocks: 0 across all 50 ANMA runs (guidance layer steered the model; the
enforcement hook was never invoked).

## Test and decision (per pre-registration)

One-sided Fisher's exact (H1: anma < control), α = 0.05. Efficacy claim requires
**both** p < 0.05 **and** control rate ≥ 0.40.

- **TypeScript:** p < 0.00001; control 0.90 ≥ 0.40 → **efficacy claim met.** ANMA
  eliminates the cross-module violations the bare model commits ~90% of the time.
- **Go:** p = 0.0004 (significant and directional), but control 0.33 < 0.40 →
  **floor NOT met → reported as suggestive / underpowered, not efficacy.** Holding
  to the pre-registered floor despite the small p-value is deliberate.

## Reading

The same task drew TS control 90% vs Go control 33% — strong evidence that import
explicitness drives how often this model crosses a boundary. ANMA's value
concentrates where the language permits casual cross-module imports (TypeScript;
Python ~68% in the main report) and is smaller where the language already imposes
friction (Go). The Python result is not extrapolated to either language.

## Next (optional)

A higher-base-rate Go scenario (e.g. the held v3 sibling-precedent lever) and/or
larger Go n would let Go clear the 0.40 floor if the effect is real; this is left
as future work, not claimed here.
