# Architecture decisions (ANMA)

Append-only. Each entry explains *why* a boundary is the way it is, so neither
you nor Claude relitigates it next session. Newest on top.

## 2026-06-05 — Adopted ANMA contracts
Module boundaries are now declared in per-module `anma.yaml` files and enforced
by `anma check` (pre-commit + CI + Claude Code PreToolUse hook).

## 2026-06-06 — Multi-language: contract graph is neutral, paths are native

When adding Go and TypeScript, the contract **graph layer** (`name`,
`depends_on`, `invariants`, `owners`) is language-neutral and shared — it uses
module *names*, so "orders depends on [billing]" reads identically everywhere and
gives the author one mental model and uniform guidance prose.

**Import identity and the `public:` surface are language-native and
adapter-derived**, not a forced shared dotted convention. Reason: Go import paths
contain dots inside segments (`github.com/org/app/billing`), so a dotted
separator is ambiguous for the prefix-matching resolver; and the wrapped engines
(`dependency-cruiser`, `go list`/`go-arch-lint`) work in native path spaces.
Forcing dotted paths would mean a lossy transform in every adapter.

**The import→module resolver is per-language and lives in the adapter**
(`LanguageAdapter`), not in `engine.py`: dotted `.`-boundary for Python,
`/`-boundary for Go, resolved-specifier equality for TypeScript.

Consequence: symbol-level `public:` enforcement is Python-only at first (tach
enforces interfaces; dependency-cruiser/go-arch-lint enforce module→module). For
Go/TS, `public:` drives guidance and module-level enforcement until symbol-level
lands. Docs must not imply symbol-level enforcement that isn't shipped.

## 2026-06-06 — Import-identity derivation timing (two tiers, never in the hot path)

Resolved before the Go/TS fan-out because it lives in `load_project`, a shared
seam every adapter, the hook, compile, and the harness call.

1. `import_identity` is PURE and dependency-free — it derives the native path from
   the module location plus cached project metadata (Go: `go.mod` module path; TS:
   tsconfig `baseUrl`/`paths`), NOT by invoking `go list` or `dependency-cruiser`.
2. Metadata is read ONCE at load into `Project.metadata` via the adapter's
   `load_metadata` — plain file reads of small declarative files, no tools.
3. The external resolvers (`go list`, `dependency-cruiser`) are confined to
   `check()` (the deliberate full scan), never `load_project` or the hook. The
   hook's `disallowed_targets` uses pure import-statement detection.

INVARIANT: `load_project` must never spawn a subprocess. It runs on every edit via
the PreToolUse hook; shelling out per edit would be slow and would break the
zero-dependency guarantee when `go`/`node` are absent. Guarded by
`test_load_project_never_spawns_subprocess`.

## 2026-06-06 — Phase 1 scope: one language per project

`language` is set once in the root `anma.yaml` and applies to the whole project.
Validated by dry-run: throwaway Go and TypeScript adapters slot into the v0.6.0
`LanguageAdapter` interface with ZERO changes (including tsconfig alias + relative
resolution and go.mod module paths), but a single tree cannot mix languages —
one root config means one language.

This is sufficient for single-language projects and single-target migrations,
which are the Phase-1 goal. Per-source-root / polyglot-monorepo language (e.g. a
Go backend and a TS frontend in one tree) is explicitly OUT of Phase 1 — a later
phase with its own design, likely language declared per `source_root`. Adapters
must not add per-module language handling in Phase 1.
