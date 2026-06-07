# ANMA

**Boundary enforcement for AI coding agents.** ANMA turns plain-YAML module
contracts into the `CLAUDE.md`, hooks, and checks that keep Claude Code inside
your architecture — and it measurably works where it matters most.

In a controlled benchmark (Python), a cheaper/faster model (Claude Haiku 4.5)
violated a declared module boundary in **13 of 19** runs of a plain repo. With
ANMA, across 20 runs of the same task it violated it **0 times** (Fisher's exact
`p < 0.0001`). See [docs/BENCHMARKS.md](https://github.com/anma-labs/anma/blob/main/docs/BENCHMARKS.md) for the full study, including the
honest part: a frontier model (Opus 4.8) respected the boundary on its own, so
ANMA's value is **insurance for running cheaper agents** plus a CI/governance
guarantee — not making a frontier model smarter.

**Languages:** Python, Go, and TypeScript (`language:` in the root `anma.yaml`,
one per project). Go and TypeScript enforce module→module dependencies; interface
(`public:`) enforcement is Python-only today. The Go/TS adapters are validated
(`anma check` + the hook detect and block real cross-module violations), but
**whether ANMA changes model behavior in Go/TS is not established** — the benchmark
above is Python, and the Go/TS live run is a null/underpowered result that does not
transfer the Python numbers. Details: [CONCEPTS § Languages](https://github.com/anma-labs/anma/blob/main/docs/CONCEPTS.md#languages).

## What it does

You declare each module's public interface and what it may depend on. `anma sync`
compiles that into everything else, so the architecture the agent reads can never
drift from the rules CI enforces:

```
anma.yaml                       project config (schema_version, source_roots)
src/domains/billing/
  anma.yaml                     the module contract — see docs/CONCEPTS.md for all fields
  CLAUDE.md          (generated) loads when Claude opens billing/
CLAUDE.md            (generated) architecture map, between markers
.claude/rules/boundaries.md (generated) always-loaded imperative
.claude/hooks/anma_pretooluse.py (generated) blocks a boundary-breaking edit (exit 2)
tach.toml            (generated) engine config (Go: .go-arch-lint.yml; TS: .dependency-cruiser.cjs)
.github/workflows/anma.yml (generated) CI: drift check + boundary check
DECISIONS.md         append-only: why each boundary exists
```

## Quickstart (60 seconds)

```bash
pip install anma[tach]      # tach backend recommended; works without it too
anma init                   # scaffolds contracts + a worked accounts/billing example
anma sync                   # generates CLAUDE.md, nested docs, hooks, tach.toml, CI
anma check                  # ✓ boundaries respected
```

For Go or TypeScript, scaffold with `anma init --language go` /
`anma init --language typescript` (the external backends — `go-arch-lint`,
`dependency-cruiser` — are optional; a builtin scanner is the zero-dep fallback).

Full walkthrough: [docs/QUICKSTART.md](https://github.com/anma-labs/anma/blob/main/docs/QUICKSTART.md).

## Commands

```bash
anma init             # scaffold contracts + a worked example
anma sync             # regenerate all artifacts from contracts
anma sync --check     # CI guard: fail if generated artifacts drifted from contracts
anma check            # enforce boundaries (hook / pre-commit / CI)
anma check --warn     # report violations but exit 0 (incremental adoption)
anma check --json     # machine-readable output for pipelines
```

Exit codes: `0` ok · `1` violations, contract errors, or drift.

## Two layers: guidance and enforcement

ANMA works at two levels, and the benchmark shows they play different roles:

- **Guidance** — the generated root and per-module `CLAUDE.md` and `.claude/rules`
  put your architecture in the agent's context. This is what drove the 68% → 0
  result: the model was steered to the correct design and didn't attempt a bad
  edit.
- **Enforcement** — the `PreToolUse` hook judges the *proposed* edit and returns
  exit 2 to block any new disallowed import before it lands; the same check runs
  at pre-commit and in CI. This is the guarantee that holds for the edits guidance
  doesn't catch, and regardless of which model or human wrote the diff.

The enforcement hook is verified to fire (feed it a forbidden edit → `exit 2`); in
the benchmark it never needed to, because guidance pre-empted every bad edit. Both
matter; see the benchmarks for exactly what each one is shown to do.

## Who it's for

- Teams running **cheaper or faster agents** (cost-sensitive pipelines, bulk
  tasks, non-frontier or non-Claude models) that don't reliably respect an
  architecture on their own — this is where ANMA's steering is decisive.
- Anyone who wants an **enforced** architecture: a guarantee in CI/pre-commit that
  module boundaries hold no matter who or what wrote the change.
- Teams that want architecture as **governance**: declared interfaces, ownership →
  CODEOWNERS, and docs that can't silently drift from the rules.

If you only ever drive a frontier model on small, well-described tasks, ANMA may
add turns without changing outcomes — and the benchmarks say so plainly.

## Lightweight by design

~800 lines, no runtime, no DSL, **one small dependency** (PyYAML) — the builtin
engine needs nothing more, and the faster external backends (`tach` for Python,
`go-arch-lint` for Go, `dependency-cruiser` for TypeScript) are all optional. A
security team can read the whole tool in an afternoon.

## Enterprise

- **Drift detection** — `anma sync --check` fails CI if generated docs/config fall
  out of sync with the contracts.
- **Incremental adoption** — `anma check --warn` and per-module `deprecated_deps`
  let a large codebase adopt without a red build on day one.
- **Governance** — `owners:` per module generates `CODEOWNERS`; `source_roots:`
  supports monorepos.
- **Supply chain** — signed releases (PyPI Trusted Publishing + provenance + SBOM),
  `pip-audit` in CI, Apache-2.0. See [SECURITY.md](https://github.com/anma-labs/anma/blob/main/SECURITY.md).

## Documentation

- [docs/QUICKSTART.md](https://github.com/anma-labs/anma/blob/main/docs/QUICKSTART.md) — install to first blocked edit
- [docs/CONCEPTS.md](https://github.com/anma-labs/anma/blob/main/docs/CONCEPTS.md) — the model, the **contract schema reference**, generated artifacts, the engine
- [docs/BENCHMARKS.md](https://github.com/anma-labs/anma/blob/main/docs/BENCHMARKS.md) — the with/without study, methodology, and honest limits
- [CONTRIBUTING.md](https://github.com/anma-labs/anma/blob/main/CONTRIBUTING.md) — dev setup, tests, the dogfood, the schema-stability rule
- [SECURITY.md](https://github.com/anma-labs/anma/blob/main/SECURITY.md) · [RELEASE.md](https://github.com/anma-labs/anma/blob/main/RELEASE.md) · [CHANGELOG.md](https://github.com/anma-labs/anma/blob/main/CHANGELOG.md)

Apache-2.0 · ANMA Labs LLC
