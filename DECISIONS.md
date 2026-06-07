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
