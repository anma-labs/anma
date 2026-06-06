# Changelog

All notable changes to ANMA are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); the **contract schema**
(`schema_version`) is versioned independently of the tool — see
[docs/CONCEPTS.md](docs/CONCEPTS.md#stability).

## [Unreleased]

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
