# ANMA — AI-Native Modular Architecture

**Structured contracts that let AI agents understand your codebase in ~250 tokens instead of 5,000-20,000.**

---

## The Problem

AI coding agents waste 70-80% of their context window just *understanding* your codebase before they write a single line of code. Every file read, every dependency traced, every interface guessed — it all burns tokens and produces hallucinations.

The result: expensive, slow, unreliable AI-assisted development.

## The Solution

ANMA replaces implicit knowledge with explicit YAML contracts. Each module declares exactly what it provides, what it consumes, its invariants, its errors, and its assumptions — in a format optimized for AI consumption.

```yaml
# ~30 lines. An AI agent knows everything it needs.
module: user-auth
version: 1
status: stable

provides:
  - id: register
    input: { email: string, password: string, display_name: string }
    output: { user_id: uuid, token: string }
    errors: [EMAIL_TAKEN, WEAK_PASSWORD, INVALID_EMAIL]
    invariants:
      - "auto-sends verification email"
      - "password must be at least 8 characters"
```

No ambiguity. No guessing. No wasted tokens.

## Getting Started

### Try it (1 minute)

```bash
git clone https://github.com/nxy/anma-scaffold my-project
cd my-project
python3 tools/lint_contracts.py
```

You'll see 3 example modules pass with 0 errors. Browse `modules/user-auth/CONTRACT.yaml` to see what a contract looks like.

### Start your project (5 minutes)

**1. Design your contracts with Claude.**

Upload `CLAUDE.md` and `CONVENTIONS.yaml` to [Claude](https://claude.ai) and describe what you're building:

> "I uploaded my ANMA scaffold files. I want to build a project management tool.
> Teams can create projects, add tasks with deadlines, assign them to people,
> and get notified when things change."

Claude acts as a contract architect — it asks questions, drafts contracts, and iterates with you. When the contracts look right:

> "Give me all CONTRACT.yaml files so I can save them and run the linter."

Save each file as `<module-name>-CONTRACT.yaml` (e.g. `user-auth-CONTRACT.yaml`).

**2. Set up your project.**

```bash
cd my-project
python3 tools/init_project.py                          # clear example modules
python3 tools/import_contracts.py ~/Downloads/*-CONTRACT.yaml  # import your contracts
```

`import_contracts.py` creates the module directories, copies contracts into place, generates all supporting files (STATE, MEMORY, TESTS, GRAPH, MANIFEST), and runs the linter. One command.

**3. Implement with Claude Code.**

```bash
claude
```

> "Read the user-auth module CONTRACT.yaml and ASSUMPTIONS.yaml.
> Implement all interfaces."

Claude Code reads the contract (~250 tokens), knows every interface, input, output, error, and invariant, and implements the module. No guessing. No hallucinating interfaces that don't exist.

Repeat for each module. The contracts are the spec — Claude Code follows them.

## Real Numbers

This repo ships with 3 example modules (14 interfaces, ~350 tokens each) so you can explore the contract format and run the linter immediately.

At scale, a production test scaffolded 18 modules with 104 interfaces in a single Claude Code session:

| Metric | Value |
|--------|-------|
| Input tokens per session | ~14,600 |
| Cache read tokens | ~32.8M |
| Total API cost | $31 |
| Modules scaffolded | 18 |
| Interfaces implemented | 104 |
| Tests generated | 239 |
| Time (API) | 91 minutes |

The contracts themselves are ~250 tokens each. A traditional codebase of comparable size would require 5,000-20,000 tokens per module just for an agent to orient itself.

## How It Works

```
your-project/
  CONVENTIONS.yaml      # Universal rules (error format, naming, lifecycle)
  MANIFEST.yaml         # Module registry with status and ownership
  GRAPH.yaml            # Auto-generated dependency graph
  CLAUDE.md             # AI agent instructions
  modules/
    user-auth/
      CONTRACT.yaml     # What this module provides and consumes
      STATE.yaml        # Current work status and blockers
      MEMORY.yaml       # Accumulated knowledge (max 20 entries)
      CHANGELOG.yaml    # Version history
      TESTS.yaml        # Contract-derived test cases
      ASSUMPTIONS.yaml  # Implementation details (separate from contract)
  BUS/                  # Inter-module communication
  tools/                # Linting, scaffolding, analysis scripts
```

An agent picking up any module reads 6 files and has full context. No history needed. No onboarding. Design for replacement, not continuity.

CLAUDE.md works with Claude Code, Cursor, Copilot, or any LLM that reads project files.

## Before/After: Token Cost

### Before ANMA (traditional codebase)

```
Agent reads auth/controllers/user.py          → 850 tokens
Agent reads auth/models/user.py               → 420 tokens
Agent reads auth/serializers.py               → 380 tokens
Agent reads auth/urls.py                      → 120 tokens
Agent reads auth/middleware.py                → 290 tokens
Agent reads auth/tests/test_user.py           → 640 tokens
Agent reads auth/exceptions.py               → 180 tokens
Agent reads requirements.txt (partial)        → 200 tokens
Agent reads settings.py (partial)             → 350 tokens
Agent infers error types (hallucination risk) → ???
                                    Total: ~3,400+ tokens (one module)
```

### After ANMA

```
Agent reads modules/user-auth/CONTRACT.yaml   → 250 tokens
                                    Total: 250 tokens (complete understanding)
```

**~14x reduction per module.** For 18 modules, that's ~61,000 tokens saved per session.

## Tools

Essential commands:

```bash
python3 tools/init_project.py                    # Clear examples, start fresh
python3 tools/import_contracts.py *.yaml         # Import contract files
python3 tools/lint_contracts.py                  # Validate contracts (23 checks)
python3 tools/lint_contracts.py --strict         # Zero-warning builds
```

The `tools/anma.py` CLI wraps all 24 tools:

```bash
python3 tools/anma.py init                       # Clear examples
python3 tools/anma.py import contracts/*.yaml    # Import contracts
python3 tools/anma.py lint                       # Validate
python3 tools/anma.py lint --strict              # Strict mode
python3 tools/anma.py module add billing         # Scaffold a new module
python3 tools/anma.py graph                      # Regenerate dependency graph
python3 tools/anma.py dashboard                  # Project health overview
python3 tools/anma.py impact user-auth           # What breaks if auth changes?
```

Run `python3 tools/anma.py` for the full list.

## Core Concepts

**Contracts over code.** CONTRACT.yaml is the single source of truth. Agents read contracts, not source code.

**Design for replacement.** Any agent can take over any module by reading its 6 files. No onboarding, no tribal knowledge.

**Explicit dependencies.** GRAPH.yaml shows exactly what depends on what. No hidden imports, no circular dependencies.

**Memory with limits.** MEMORY.yaml keeps institutional knowledge — capped at 20 entries, 100 chars each. Forces curation over accumulation.

**Contract lifecycle.** Modules progress: `draft` → `stable` → `frozen`. Frozen contracts can only be extended, never modified.

See [Architecture Overview](docs/ARCHITECTURE.md) for the full design and the 7 principles.

## Designed For

- **5-80 modules.** Small enough to hold the full graph in your head. Large enough that unstructured projects fall apart.
- **1-4 developers.** Teams where everyone touches multiple modules and nobody has time for onboarding docs. The contracts *are* the docs.
- **AI agents as primary code consumers.** Token budgets, the 6-file recovery pattern, and the explicit dependency graph exist because agents need them.

ANMA is not for monoliths, microservice meshes with hundreds of services, or projects where humans never use AI tooling.

## Requirements

- Python 3.8+
- PyYAML (`pip install pyyaml`)

No other dependencies. ANMA is a convention and a set of scripts, not a framework you install.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Documentation

- [Architecture Overview](docs/ARCHITECTURE.md) — How ANMA works and the 7 design principles
- [Contract Guide](docs/CONTRACT-GUIDE.md) — Writing effective contracts
- [Quickstart Guide](docs/QUICKSTART.md) — Detailed setup walkthrough
