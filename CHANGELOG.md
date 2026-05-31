# Changelog

All notable changes to this project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [0.3.0] - 2026-05-30

### Added
- **Domain scaling** — modules can be grouped into `domains/<domain>/` with GATEWAY.yaml boundary enforcement (Check 24)
- **Multi-agent coordination** — claims system (`anma claim/release/claims`), git hooks (post-merge, pre-commit)
- **Incremental sync** — hash-based change detection skips unchanged TESTS.yaml (8.8x speedup at 200 modules)
- **Accurate token counting** — tiktoken support with `len//4` fallback via `tools/tokenizer.py`
- `tools/discover.py` — module and domain discovery across flat and domain layouts
- `tools/claims.py` — lightweight module ownership coordination
- `--domain` flag on `new_module.py` and `import_contracts.py`
- `--regenerate-only` and `--force` flags on `sync_all.py`
- `sync` command in `anma.py` CLI
- Retrofit support — `init_project.py` and `sync_all.py` create missing project files
- Scaling benchmark (`tools/benchmark/bench_scaling.py`) — 39 tests across 3 features
- Architectural quality comparison tool (`tools/benchmark/compare_quality.py`)

### Fixed
- 17 bugs found via dynamic workflow bug hunt (command injection, YAML corruption, silent drops)
- 3 security findings (path traversal validation, domain kebab-case check, claims YAML injection)
- `smoke_test.py` — SCAFFOLD_ROOT split, missing tools, stale module names, dependency-order removal
- `init_project.py` — missing `main()` function (pre-existing `anma init` crash)
- `check_principles.py` — domain modules silently skipped by P1-P7 checks

### Changed
- License changed from BSL 1.1 to Apache 2.0
- Linter check count: 22 → 24
- Test count: 91 → 218 (189 linter + 29 regression)
- `CONVENTIONS.yaml` bumped to v3 with domain_scaling section
- `CLAUDE.md` instructs agents to always use domain layout
- Performance: eliminated subprocess spawns in sync_all (3.1x overall, 11.9x sync)

## [0.2.0] - 2026-05-23

### Added
- Initial scaffold with 22 linter checks and 7 principle enforcement checks
- 91 unit tests and 83 smoke tests
- Core tools: linter, scaffolding, graph generation, dashboard, impact analysis
- 3 example modules (user-auth, todo-api, notifications)
- CLAUDE.md agent instructions
- CONVENTIONS.yaml (v2)

[Unreleased]: https://github.com/anma-labs/anma-scaffold/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/anma-labs/anma-scaffold/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/anma-labs/anma-scaffold/releases/tag/v0.2.0
