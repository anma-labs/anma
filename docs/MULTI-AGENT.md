# Multi-Agent Coordination

ANMA supports multiple AI agents working on the same project simultaneously. Each agent owns specific modules — contracts are in separate directories, so there are no file conflicts.

## Claims System

Before launching parallel agents, claim the modules each agent will work on:

```bash
anma claim user-auth payments         # agent A's scope
anma claim web-ui admin-panel         # agent B's scope
anma claims                           # see who owns what
```

If someone tries to modify a claimed module:
- `remove_module` warns and requires `--force`
- The pre-commit git hook blocks commits to claimed modules
- Claims are stored in `.anma/claims.yaml` (git-tracked so the team sees them)

When done:

```bash
anma release user-auth payments
```

## Parallel Claude Code Agents

Launch each agent in its own terminal with a scoped prompt:

**Terminal 1:**
```bash
claude --permission-mode auto
```
```text
You own ONLY modules: user-auth, payments. Do not touch any other module.
Read their contracts and implement them.
```

**Terminal 2:**
```bash
claude --permission-mode auto
```
```text
You own ONLY modules: web-ui, admin-panel. Do not touch any other module.
Read their contracts and implement them.
```

After both finish, merge and regenerate:

```bash
python3 tools/sync_all.py              # regenerates MANIFEST + GRAPH
python3 tools/lint_contracts.py --strict  # verify cross-module consistency
```

## Git Hooks

Install ANMA's git hooks for automatic coordination:

```bash
git config core.hooksPath .githooks
```

**post-merge**: Automatically runs `sync_all --regenerate-only` after any merge, so MANIFEST and GRAPH stay in sync without manual intervention.

**pre-commit**: Blocks commits that modify modules claimed by another user. Override with `git commit --no-verify` if needed.

## Domain Gateways

Domains provide team-level boundaries. Each domain declares which interfaces are visible to other domains via `GATEWAY.yaml`:

```yaml
domain: backend
version: 1
exports:
  - module: user-auth
    interfaces: [verify_token, get_user]
  - module: payments
    interfaces: [process_payment]
```

Modules within the same domain can consume each other freely. Cross-domain consumption must go through exported interfaces. The linter enforces this — if `frontend/web-ui` tries to consume `backend/payments.refund` and `refund` isn't exported in the backend gateway, the linter reports an error.

This means team A can refactor their domain's internals without breaking team B, as long as the gateway exports don't change.

## Dynamic Workflows

For larger projects, Claude Code's dynamic workflows can parallelize implementation:

```text
Read CLAUDE.md and CONVENTIONS.yaml. I want to build [description].
Design the contracts first. Then create a dynamic workflow where each
subagent implements one module from its contract. Each subagent should
read CLAUDE.md and CONVENTIONS.yaml plus its assigned contract. After
all modules are implemented, run the linter and verify everything integrates.
```

Each subagent reads one contract (~350 tokens) instead of the full codebase. Claude decides how to partition the work based on the dependency graph.

**When to use dynamic workflows:** Projects with 8+ independent modules where implementation tasks don't depend on each other.

**When to use sequential:** Projects under 8 modules, or when modules have complex interdependencies that require sequential implementation. Our benchmarks show sequential is more cost-effective at current scales — see [BENCHMARKS.md](BENCHMARKS.md).

## Incremental Sync

When multiple agents modify contracts, `sync_all` uses hash-based change detection to avoid unnecessary regeneration:

```bash
python3 tools/sync_all.py              # only regenerates changed modules
python3 tools/sync_all.py --force      # full regeneration
python3 tools/sync_all.py --regenerate-only  # only MANIFEST + GRAPH
```

At 200 modules with 1 change, incremental sync takes ~1.5s instead of ~13s (8.8x speedup).
