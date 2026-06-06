# ANMA

**Architecture contracts that keep Claude Code inside the lines.**

With ANMA, Claude Code makes fewer architectural mistakes, preserves your
architecture across sessions, respects module boundaries, and coordinates
parallel work better than a plain repo — because the boundaries are *declared
once* and then **generated into the agent's context and enforced** at three
points (in-session hook, pre-commit, CI).

ANMA is deliberately lightweight. It does not invent a runtime, a DSL, or a pile
of "principles." It is a thin layer over primitives that already exist:

- **Claude Code's own memory + hooks** — a root `CLAUDE.md` is loaded every
  session, nested `CLAUDE.md` files load when Claude opens that folder, and a
  `PreToolUse` hook can *block* a bad edit before it lands.
- **A real boundary engine** — [`tach`](https://github.com/tach-org/tach)
  (Rust, fast, interface-aware) when installed, with a zero-dependency builtin
  fallback so ANMA keeps working regardless.

## The one idea

Your module contracts are the single source of truth. `anma sync` compiles them
into everything else, so the docs the agent reads can never drift from the rules
the CI enforces.

```
anma.yaml                       project config (schema_version, source_roots)
src/domains/billing/
  anma.yaml                     the module contract — see docs/CONCEPTS.md for all fields
  CLAUDE.md          (generated) loads when Claude opens billing/
CLAUDE.md            (generated) architecture map, between markers
.claude/rules/boundaries.md (generated) the imperative, always loaded
.claude/hooks/anma_pretooluse.py (generated) blocks boundary-breaking edits
.claude/settings.json (generated) wires the hook
tach.toml            (generated) engine config
.github/workflows/anma.yml (generated) CI
DECISIONS.md         append-only: why each boundary exists
```

## Quickstart (60 seconds)

```bash
pip install anma[tach]      # tach backend recommended; works without it too
anma init                   # scaffolds contracts + a worked accounts/billing example
anma sync                   # generates CLAUDE.md, nested docs, hooks, tach.toml, CI
anma check                  # ✓ boundaries respected
```

Now open the project in Claude Code and ask it to make `accounts` import
`billing` (which the example forbids): the `PreToolUse` hook returns exit code 2
and the edit is blocked. Full walkthrough in [docs/QUICKSTART.md](docs/QUICKSTART.md).

## Three commands

```bash
anma init             # scaffold contracts + a worked two-module example
anma sync             # contracts -> CLAUDE.md, nested CLAUDE.md, rules, hooks, tach.toml, CI
anma sync --check     # CI guard: fail if generated artifacts drifted from the contracts
anma check            # enforce module boundaries (used by the hook, pre-commit, and CI)
anma check --warn     # report violations but exit 0 (incremental adoption)
anma check --json     # machine-readable output for pipelines
```

Exit codes: `0` ok · `1` violations, contract errors, or drift.

## How it hits each goal

| Goal | Mechanism |
|---|---|
| Fewer architectural mistakes | Generated architecture map in root `CLAUDE.md` + per-module nested `CLAUDE.md` that loads exactly when Claude works there. |
| Preserved across sessions | `CLAUDE.md` survives compaction and reloads every session; `DECISIONS.md` records *why*, so boundaries aren't relitigated. |
| Respects module boundaries | Contracts declare `public` + `depends_on`; enforced in-session (PreToolUse hook, exit 2 = blocked), at pre-commit, and in CI. |
| Coordinates parallel work | Declared public interfaces let parallel agents build against a stable contract, not internals; pairs with Claude Code git worktrees. |

## Install

```bash
pip install anma          # builtin engine
pip install anma[tach]    # recommended: tach engine (interface-level checks)
```

## Enterprise-ready by being small

ANMA's enterprise story is not a feature list — it's that the whole tool is a
few hundred lines a security team can read in an afternoon, with **zero required
runtime dependencies** (the builtin engine needs nothing; `tach` is optional).

- **Drift detection** — `anma sync --check` fails CI if the committed `CLAUDE.md`
  / `tach.toml` ever fall out of sync with the contracts, so the docs the agent
  reads can't silently diverge from the rules CI enforces.
- **Incremental adoption** — `anma check --warn` and per-module `deprecated_deps`
  let a large existing codebase adopt without turning the build red on day one.
- **Governance** — `owners:` per module generates `CODEOWNERS`; pair with branch
  protection for review gates that match real boundaries.
- **Monorepos** — `source_roots:` accepts multiple roots.
- **Supply chain** — releases via PyPI Trusted Publishing with build-provenance
  attestations and a CycloneDX SBOM; `pip-audit` in CI. See `SECURITY.md` for the
  full model (ANMA never executes your code; the hook only blocks, never edits).

## Stability

The **contract schema** (`schema_version`) is your real API and follows SemVer
independently of the tool version. This build supports `schema_version: 1`.
Contracts written today keep working; breaking schema changes bump the major and
ship a migration path.

## Engine note

`tach` is the default backend. If it is ever unavailable, ANMA falls back to a
small `ast`-based dependency checker automatically — your contracts and the
agent-facing layer don't change. The fork `dtach` is a drop-in alternative.

## Documentation

- [docs/QUICKSTART.md](docs/QUICKSTART.md) — install to first blocked edit, step by step
- [docs/CONCEPTS.md](docs/CONCEPTS.md) — the model, the **contract schema reference**, generated artifacts, the engine
- [docs/BENCHMARKS.md](docs/BENCHMARKS.md) — methodology + results for the with/without comparison
- [CONTRIBUTING.md](CONTRIBUTING.md) — dev setup, tests, the dogfood, the schema-stability rule
- [SECURITY.md](SECURITY.md) — security model and disclosure
- [RELEASE.md](RELEASE.md) — rename + publishing runbook
- [CHANGELOG.md](CHANGELOG.md) — release history

Apache-2.0 · ANMA Labs LLC
