# Changelog

All notable changes to ANMA are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); the **contract schema**
(`schema_version`) is versioned independently of the tool — see
[docs/CONCEPTS.md](docs/CONCEPTS.md#stability).

## [Unreleased]

### Added
- **Go language adapter** (`anma/lang_go.py`): first-class `language: go` support
  for `init` / `sync` / `check`, plugged into the v0.6.0 `LanguageAdapter` seam
  with **no changes to the neutral layers**. Import identity is the `go.mod`
  module path plus the package directory (`example.com/app/domains/billing`);
  the import→module resolver uses a `/`-boundary and lives in the adapter.
- Go enforcement wraps `go-arch-lint` as the external backend and falls back to a
  zero-dependency builtin import scanner (real line numbers) when the Go toolchain
  is absent — mirroring the tach/builtin pattern. Enforcement is **module→module
  only** (symbol-level `public:` remains Python/tach-only).
- `anma init --language go` scaffolds a runnable Go worked example; `sync`
  generates `.go-arch-lint.yml` (in place of `tach.toml`) and a Go-flavored CI
  workflow. `go.mod` is read with a plain file read at load (no subprocess), so the
  per-edit hook path stays pure (guarded by a Go `test_load_project_never_spawns_subprocess`).
- `pyproject` optional-dependency group `[go]` (empty: `go-arch-lint` is a Go
  binary, not a PyPI package — the builtin fallback needs nothing).
- **TypeScript language adapter** (`anma/lang_ts.py`): first-class
  `language: typescript` support for `init` / `sync` / `check`, plugged into the
  v0.6.0 `LanguageAdapter` seam with **no changes to the neutral layers**. Import
  identity is the tsconfig-resolved specifier (`baseUrl`/`paths`, e.g.
  `@app/billing`); the import→module resolver uses resolved-specifier equality and
  lives in the adapter.
- TS enforcement **wraps dependency-cruiser** for real resolution (tsconfig paths,
  barrels, `import type`) and falls back to a zero-dependency builtin import
  detector (real line numbers) when node/dependency-cruiser is absent — or when
  dependency-cruiser can't parse (no `typescript` peer), guarded against a
  false-clean. `import type` is treated as a real boundary edge. Enforcement is
  **module→module only**.
- `anma init --language typescript` scaffolds a runnable TS worked example; `sync`
  generates `.dependency-cruiser.cjs` (in place of `tach.toml`) and a Node-flavored
  CI workflow. `tsconfig.json` is read with a plain file read at load (relative
  `extends` only; no subprocess), keeping the per-edit hook path pure (guarded by a
  TS `test_load_project_never_spawns_subprocess`).
- `pyproject` optional-dependency group `[ts]` (empty: dependency-cruiser is an npm
  package, not a PyPI one — the builtin fallback needs nothing).

## [0.6.0] — 2026-06-06

### Added
- **Language-adapter seam** (`anma/adapters.py`): the boundary engine is now
  dispatched per language behind a `LanguageAdapter` protocol + registry. Python
  ships today (delegating to `anma.engine`); Go and TypeScript adapters plug in
  without touching the neutral layers. Contracts gain an optional `language:`
  field (defaults to `python`; existing contracts are unaffected).
- Per-language metadata is read once at load into `Project.metadata` (plain file
  reads — `go.mod`, `tsconfig.json`; no tools). `import_identity` is a pure
  derivation from that cache, so `load_project` (which runs in the per-edit hook)
  never spawns a subprocess; heavy resolution stays in `check()`. Guarded by test.
- The contract *graph* (`name`, `depends_on`, `invariants`, `owners`) is
  language-neutral; import identity, the `public:` surface, engine config, and CI
  are language-native and adapter-derived (see DECISIONS.md).

### Changed
- `compile`, `cli check`, and the PreToolUse hook route through
  `adapters.get_adapter(project.language)`. Python behavior is unchanged.

## [0.5.6] — 2026-06-06

### Fixed
- README doc links are now absolute GitHub URLs so they resolve on the PyPI
  project page (relative links rendered as dead text there, hiding the benchmark
  study and quickstart from readers who land on PyPI first).
- Package `description` metadata updated to the current positioning ("Boundary
  enforcement for AI coding agents…"); the old summary still described the
  pre-pivot framing.

## [0.5.5] — 2026-06-06

### Fixed
- The generated CI workflow (`.github/workflows/anma.yml`) is now **seed-once and
  not drift-checked**, like `settings.json` and `.pre-commit-config.yaml`. It is a
  starting point users customize (e.g. the install path), so regenerating and
  drift-checking it was wrong — a hand-edited CI file no longer fails
  `anma sync --check`.

## [0.5.4] — 2026-06-06

### Changed
- Documentation rewritten around the first hardened result (Claude Haiku 4.5,
  `payments-boundary`, n=20: control 13/19 violations vs ANMA 0/20,
  Fisher `p < 0.0001`). README, QUICKSTART, CONCEPTS, and BENCHMARKS now lead with
  the evidence-backed, two-tier positioning — ANMA as insurance for cheaper agents
  plus a CI/governance guarantee — and explicitly separate the benchmarked
  *guidance* win from the separately-verified *enforcement* hook. The frontier
  (Opus 4.8) null result is published rather than hidden.

## [0.5.3] — 2026-06-06

### Added
- `--scenario NAME` filter on the benchmark runner (repeatable) so a focused run
  (e.g. 20 trials on one scenario) doesn't spend tokens on the whole suite.

### Changed
- `docs/BENCHMARKS.md` rewritten around the first real results: a two-tier
  finding (frontier models respect documented architecture unaided; cheaper
  models violate routinely and ANMA drives that to zero), with the enforcement
  layer verified by a direct hook test. Positions ANMA as insurance for cheaper
  agents plus a CI/governance guarantee, and publishes the frontier null result.

## [0.5.2] — 2026-06-06

Follow-ups from the second live run (which showed the harness mis-attributing a
control-arm permission denial as an ANMA hook block, and both arms tying at 0
violations because a strong model passed the easy scenarios).

### Fixed
- Harness attributes hook blocks to ANMA **only when the ANMA hook is installed**
  in that arm; the control arm now reports `—` for hook blocks instead of a
  misleading count.

### Added
- `orders-inventory` adversarial scenario: the easy implementation crosses the
  forbidden `orders → inventory` boundary and the correct path (caller-injected
  callback) is non-obvious — designed so a capable model tends to slip in the
  control arm, giving ANMA something to prevent.

## [0.5.1] — 2026-06-06

Fixes from the first live `claude-code` benchmark run, which surfaced two real
enforcement bugs and a harness that mis-scored blocked runs.

### Fixed
- **Hook now judges the proposed edit, not the project's current state.** The
  PreToolUse hook reconstructs the post-edit content and blocks (exit 2) only
  when *that edit* introduces a new disallowed import. This fixes a deadlock
  (a project red for any reason blocked every edit, including the fix) and makes
  the headline claim true (a violating edit is blocked as it is made, not on the
  next edit). Hook logic moved into the package (`anma.hook`) so it is tested and
  upgradable via `pip install -U`; the generated hook is a thin shim that fails
  open with a warning if `anma` isn't importable.
- **`anma sync` now qualifies `public` interface paths** to the module's import
  path in `tach.toml` (e.g. `accounts.service.get_user` →
  `domains.accounts.service.get_user`). Previously these were emitted verbatim,
  so `tach check` failed out of the box for any module nested under a source
  root. (The single-module-at-root dogfood had masked this.)

### Changed
- Benchmark harness parses `claude --output-format json`: real `num_turns`, hook
  blocks counted from `permission_denials`, and a per-trial `status`
  (`ok`/`no_change`/`error`). Runs that changed no code or errored are flagged
  and excluded from violation scoring, so an incomplete run can no longer be read
  as a clean pass.

## [0.5.0] — 2026-06-05

Ground-up rewrite around a single goal: *with ANMA, Claude Code makes fewer
architectural mistakes, preserves architecture across sessions, respects module
boundaries, and coordinates parallel work better than a normal repo.* The
previous "7 principles / 24 linter checks" framing is gone; ANMA is now a thin
layer over Claude Code's native memory + hooks plus a real boundary engine.

### Added
- `anma sync --check` — drift detection; fails if generated artifacts no longer
  match the contracts (for CI).
- `anma check --warn` and per-module `deprecated_deps` — incremental adoption
  without a red build on day one.
- `anma check --json` — machine-readable output, with documented exit codes.
- Monorepo support via `source_roots:` (multiple roots).
- `schema_version` with a SemVer stability promise; contracts newer than the
  tool are rejected rather than misread.
- `owners:` per module → generated `.github/CODEOWNERS`.
- `exclude:` in project config plus a default-ignore set (`node_modules`,
  `.venv`, build dirs, …) so discovery skips non-source trees.
- Security model + disclosure policy (`SECURITY.md`), a signed-release pipeline
  (PyPI Trusted Publishing + build-provenance attestations + CycloneDX SBOM),
  and `pip-audit` in CI.
- A reproducible benchmark harness (`benchmarks/`) with an independent violation
  scorer and a deterministic replay mode; scenarios for the boundary and
  cross-session-persistence goals.
- ANMA dogfoods itself: the repo carries its own contracts, enforced in CI.

### Changed
- Single source of truth: contracts compile to `CLAUDE.md`, nested `CLAUDE.md`,
  rules, the PreToolUse hook, `tach.toml`, and CI.
- Boundary engine is swappable: `tach` (default, interface-aware) with a
  zero-dependency builtin `ast` fallback.
- Apache-2.0; the published wheel ships only the `anma` package.

### Removed
- The "7 architectural principles" and the legacy multi-check linter.
