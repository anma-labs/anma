# Changelog

All notable changes to ANMA are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); the **contract schema**
(`schema_version`) is versioned independently of the tool — see
[docs/CONCEPTS.md](docs/CONCEPTS.md#stability).

## [Unreleased]

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
