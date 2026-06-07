# Concepts & reference

This is the **single source of truth** for the contract schema and what ANMA
generates. The README and quickstart only teaser these; if a fact about a field
or an artifact matters, it lives here.

## The model

Module **contracts** are the source of truth. `anma sync` compiles them into the
agent-facing docs *and* the machine-checked rules, so the architecture Claude
reads can never drift from the boundary CI enforces. You edit contracts; you
never hand-edit generated files.

A "module" is a directory containing an `anma.yaml` with a `name:`. Modules are
discovered by scanning each source root.

## Project config — root `anma.yaml`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `schema_version` | int | `1` | Contract schema version. ANMA refuses contracts newer than it understands. |
| `language` | str | `"python"` | One language per project: `python`, `go`, or `typescript`. Selects the adapter that derives import identity, the engine config, and CI. See [Languages](#languages). |
| `source_roots` | list[str] | `[src]` | One or more roots to scan for modules (monorepo-friendly). `source_root: "src"` (string) is also accepted. For Go this is the `go.mod` directory (commonly `.`). |
| `python_version` | str | `"3.10"` | Python adapter only: used in the generated Python CI workflow. (Go reads its version from `go.mod`; TypeScript's CI pins Node.) |
| `exclude` | list[str] | `[]` | Path prefixes/globs to skip during discovery (e.g. `benchmarks`). Common vendor/build dirs (`node_modules`, `.venv`, `build`, …) are always ignored. |

## Module contract — `<module>/anma.yaml`

| Field | Type | Meaning |
|---|---|---|
| `name` | str | Logical module name. Required (its presence marks a module). |
| `summary` | str | One line; shown in the generated architecture map. |
| `public` | list[str] | The module's interface surface — the symbols other modules are meant to import. Write members relative to the module name (`accounts.service.x`). **Interface-level *enforcement* is Python/tach-only**; under Go and TypeScript `public` drives guidance (it is rendered into `CLAUDE.md`) while enforcement is module→module. |
| `depends_on` | list[str] | Module names this module may import. Anything else is a violation. |
| `deprecated_deps` | list[str] | Allowed-but-warned dependencies. Surfaced as warnings (exit 0) for incremental adoption. |
| `invariants` | list[str] | Free-text rules an agent must not break; rendered into the module's `CLAUDE.md`. |
| `owners` | list[str] | Review owners; compiled into `CODEOWNERS`. |

Example:

```yaml
name: billing
summary: Invoices and payments.
public:
  - billing.service.create_invoice
depends_on: [accounts]
owners: ["@team-payments"]
invariants:
  - Never store raw card numbers.
```

## Generated artifacts (never hand-edit)

| Path | What it is |
|---|---|
| `CLAUDE.md` | Root architecture map, written between `<!-- ANMA:MAP -->` markers. Your prose around the markers is preserved across syncs. |
| `<module>/CLAUDE.md` | The module's contract rendered for the agent. Claude Code loads it on demand when it opens that folder. |
| `.claude/rules/boundaries.md` | The always-loaded imperative about respecting boundaries. |
| `.claude/hooks/anma_pretooluse.py` | PreToolUse hook; exit code 2 blocks a boundary-breaking edit in-session. |
| `.claude/settings.json` | Wires the hook (seeded once; not overwritten). |
| engine config | Language-native: `tach.toml` (Python), `.go-arch-lint.yml` (Go), or `.dependency-cruiser.cjs` (TypeScript). |
| `.github/workflows/anma.yml` | CI starting point (`anma sync --check` then `anma check`). Seeded once and customizable — not overwritten or drift-checked. |
| `.github/CODEOWNERS` | Generated only if any module declares `owners`. |
| `DECISIONS.md` | Append-only rationale (seeded once; you maintain it). |

## The engine

Boundary enforcement sits behind a swappable, **per-language** adapter. Each
language wraps a fast external tool and falls back to a zero-dependency builtin
scanner, so `anma check` always works with nothing extra installed:

| Language | External backend | Builtin fallback | Level |
|---|---|---|---|
| Python | `tach` (Rust) — `pip install anma[tach]` | `ast` checker | `depends_on` **and** `public` interface |
| Go | `go-arch-lint` (`go install …`) | import-block scanner | `depends_on` (module→module) |
| TypeScript | `dependency-cruiser` (npm; honors tsconfig paths/barrels/`import type`) | import/require scanner | `depends_on` (module→module) |

`anma check` auto-detects which backend is available and prints
`[engine: tach|go-arch-lint|dependency-cruiser|builtin]`. The builtin scanners
capture real line numbers. Interface-level (`public`) enforcement is Python/tach
only today; Go and TypeScript enforce module→module.

## How Claude Code uses it (the three enforcement points)

ANMA operates at two levels: **guidance** (the generated `CLAUDE.md` files and
rules that put your architecture in the agent's context) and **enforcement** (the
hook + pre-commit + CI that mechanically reject a violation). In practice guidance
prevents most bad edits before they happen; enforcement is the backstop for the
rest and the guarantee that holds regardless of model or author. See
[BENCHMARKS.md](BENCHMARKS.md) for what each layer is shown to do.

1. **In-session** — the root `CLAUDE.md` (loaded every session, reloaded after
   compaction), nested `CLAUDE.md` (loaded when Claude opens a module), and the
   PreToolUse hook that *blocks* a violating edit before it lands.
2. **Pre-commit** — `anma check` via the generated `.pre-commit-config.yaml`.
3. **CI** — `anma sync --check` (drift) + `anma check` (boundaries).

## Stability

The contract schema follows SemVer independently of the tool version. This build
supports `schema_version: 1`. Contracts written today keep working; a breaking
schema change bumps the major and ships a migration path. The tool will not
silently reinterpret your contracts.


## Languages

The boundary engine is dispatched per language behind a `LanguageAdapter`. The
contract *graph* — `name`, `depends_on`, `invariants`, `owners` — is the same in
any language and is what the generated guidance is built from. What's
language-native (and adapter-derived) is the import identity, the `public:`
surface, the generated engine config, and CI.

Set it once per project in the root `anma.yaml` (one language per project):

```yaml
language: python   # python (default) | go | typescript
```

Three adapters ship today:

- **Python** — `tach` backend (interface-aware) with a zero-dependency `ast`
  fallback. Import identity is the dotted path from the source root.
- **Go** — wraps `go-arch-lint` with a builtin import scanner. Import identity is
  the `go.mod` module path plus the package directory
  (`example.com/app/domains/billing`); `go.mod` is read at load (no subprocess).
- **TypeScript** — wraps `dependency-cruiser` (real tsconfig-path/barrel/`import
  type` resolution) with a builtin detector. Import identity is the
  tsconfig-resolved specifier; `tsconfig.json` is read at load (relative `extends`
  only in this release).

`anma init --language go|typescript` scaffolds a runnable worked example for each.
Any other `language:` value is rejected with a clear error.

**What's Python-only (be precise):** interface-level (`public:`) *enforcement* is
Python/tach-only; Go and TypeScript enforce module→module dependencies and use
`public:` for guidance. **Benchmark evidence is per language and not transferable:**
the headline Python result is Python-only; Go and TypeScript ship with their own
`go-payments` / `ts-payments` scenarios whose live run is an honest
null/underpowered result (see [BENCHMARKS.md](BENCHMARKS.md) and
[benchmarks/README.md](../benchmarks/README.md)). The polyglot monorepo (multiple
languages in one tree) is out of scope for this release.
