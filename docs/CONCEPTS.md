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
| `source_roots` | list[str] | `[src]` | One or more roots to scan for modules (monorepo-friendly). `source_root: "src"` (string) is also accepted. |
| `python_version` | str | `"3.10"` | Used in the generated CI workflow. |
| `exclude` | list[str] | `[]` | Path prefixes/globs to skip during discovery (e.g. `benchmarks`). Common vendor/build dirs (`node_modules`, `.venv`, `build`, …) are always ignored. |

## Module contract — `<module>/anma.yaml`

| Field | Type | Meaning |
|---|---|---|
| `name` | str | Logical module name. Required (its presence marks a module). |
| `summary` | str | One line; shown in the generated architecture map. |
| `public` | list[str] | The module's interface surface — the only symbols other modules may import. Enforced at interface level by the `tach` engine. |
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
| `tach.toml` | Engine config for the `tach` backend. |
| `.github/workflows/anma.yml` | CI: `anma sync --check` then `anma check`. |
| `.github/CODEOWNERS` | Generated only if any module declares `owners`. |
| `DECISIONS.md` | Append-only rationale (seeded once; you maintain it). |

## The engine

Boundary enforcement sits behind a swappable adapter:

- **`tach`** (default when installed) — Rust, fast, enforces both `depends_on`
  and the `public` interface. `pip install anma[tach]`.
- **builtin** (fallback) — a small `ast` dependency checker with zero extra
  deps. Enforces `depends_on` (dependency level), not interface level.

`anma check` auto-detects which is available and prints `[engine: tach|builtin]`.

## How Claude Code uses it (the three enforcement points)

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
