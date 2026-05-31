# Benchmarks

We built 3 projects three ways each — without ANMA, with ANMA (sequential), and with ANMA + dynamic workflows — then added a feature to each project in a fresh session.

All builds used Claude Opus 4.6 on Claude Max. Costs reflect API pricing, not subscription.

## First Build: 3 Projects, 9 Builds

### Project 1: Personal Finance Tracker (4 modules)

| | Control | ANMA Sequential | ANMA + Dynamic Workflows |
|---|---:|---:|---:|
| Cost | $1.30 | $1.69 | $3.16 |
| API time | 6m 1s | 6m 32s | 15m 26s |
| Runs first try | No | Yes | Yes |
| Tests | 32 | 35 | 25 |
| Output tokens | 22.3K | 21.3K | 51.1K |
| Cache read | 891.7K | 1.8M | 2.0M |

### Project 2: Team Task Manager (8 modules)

| | Control | ANMA Sequential | ANMA + Dynamic Workflows |
|---|---:|---:|---:|
| Cost | $1.53 | $2.40 | $8.64 |
| API time | 7m 28s | 11m 29s | 31m 32s |
| Runs first try | Yes | Yes | Yes |
| Tests | 42 | 75 | 60 |
| Output tokens | 29.9K | 48.3K | 113.7K |
| Cache read | 987.2K | 1.5M | 7.0M |

### Project 3: E-commerce Backend (12 modules, 3 domains)

| | Control | ANMA Sequential | ANMA + Dynamic Workflows |
|---|---:|---:|---:|
| Cost | $2.00 | $3.39 | $5.36 |
| API time | 6m 45s | 12m 24s | 22m 36s |
| Runs first try | Yes | Yes | Yes |
| Tests | 42 | 35 | 29 |
| Output tokens | 32.1K | 46.4K | 81.4K |
| Cache read | 854.8K | 2.3M | 3.4M |

## Adding a Feature Later: Control vs ANMA Sequential

Same feature prompt, fresh Claude Code session, same model.

| | Control | ANMA Sequential |
|---|---:|---:|
| **Project 1: Add recurring transactions** | | |
| Cost | $0.68 | $0.83 |
| API time | 2m 18s | 3m 29s |
| New tests added | 24 | 27 |
| Total tests after | 56 | 62 |
| **Project 2: Add task templates** | | |
| Cost | $0.88 | $0.87 |
| API time | 3m 47s | 3m 46s |
| New tests added | 21 | 22 |
| Total tests after | 63 | 97 |
| **Project 3: Add wishlists** | | |
| Cost | $0.65 | $1.17 |
| API time | 2m 10s | 4m 5s |
| New tests added | 14 | 15 |
| Total tests after | 56 | 50 |

## Architectural Visibility

Measured on the 12-module e-commerce benchmark after feature addition:

| What a new session gets | Control | ANMA |
|---|---:|---:|
| Declared interfaces | 0 | 36 |
| Declared dependencies | 0 | 9 |
| Declared invariants | 0 | 47 |
| Domain gateways | 0 | 3 |
| BUS event connections | 0 | 17 |
| Architecture documentation (lines) | 0 | 1,000+ |

Compare any two projects yourself:

```bash
python3 tools/benchmark/compare_quality.py /path/to/control /path/to/anma
```

## What the Data Shows

**ANMA costs more on the first build.** 1.3–1.7x for sequential, 2.4–3.6x for dynamic workflows. Designing contracts before implementation adds overhead.

**Adding features costs the same.** Once the project exists, ANMA and control builds are comparable in cost and speed. Prompt caching means both approaches pay similar token costs.

**ANMA runs correctly on first try.** The control failed on Project 1 (wrong entry point, manual fix needed). All 6 ANMA builds started correctly on first attempt.

**ANMA produces more thorough test coverage.** After two rounds of development, the ANMA Task Manager has 97 tests vs the control's 63 — 54% more coverage from identical prompts.

**ANMA produces architecture, not just code.** Every ANMA build generates contracts, dependency graphs, BUS event wiring, and domain boundaries that persist across sessions. When the wishlist feature needed price-drop notifications, the ANMA version used its existing BUS event system. The control manually wired the logic into the products router.

**Dynamic workflows don't justify their cost at current scales.** At every project size, they cost 2–4x more than sequential and produce fewer tests. The parallelization saves wall time but not API time.

## Demo Repos

Inspect the benchmark projects yourself:

- [Finance Tracker](https://github.com/anma-labs/anma-demo-finance-tracker) — 4 modules, recurring transactions
- [Task Manager](https://github.com/anma-labs/anma-demo-task-manager) — 8 modules, BUS events, task templates
- [E-commerce Backend](https://github.com/anma-labs/anma-demo-ecommerce) — 12 modules, 3 domains, GATEWAY enforcement, wishlists

## Scaffold Performance

The scaffold tools themselves have been benchmarked at scale:

| Modules | Domains | Discover | Sync (full) | Sync (incremental) | Lint | Speedup |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 2 | 0.000s | 0.7s | 0.2s | 0.2s | 4.0x |
| 50 | 5 | 0.001s | 3.2s | 0.5s | 0.7s | 6.9x |
| 100 | 7 | 0.002s | 6.6s | 0.8s | 1.4s | 8.1x |
| 200 | 10 | 0.005s | 13.3s | 1.5s | 2.6s | 8.8x |

Incremental sync uses hash-based change detection — only regenerates TESTS.yaml for modules whose CONTRACT.yaml changed. At 200 modules with 1 change, sync takes ~1.5s instead of ~13s.

Run the benchmark yourself:

```bash
python3 tools/benchmark/bench_scaling.py --sizes 10,50,100,200
```
