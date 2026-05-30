# ANMA — AI-Native Modular Architecture

**Plain-YAML module contracts that help AI coding agents understand your codebase in ~350 tokens instead of 5,000–20,000.**

No hallucinated interfaces. No undeclared dependencies. No silent integration bugs.

ANMA is a lightweight scaffold for AI-assisted software development. Each module gets a compact, machine-readable contract that declares what it provides, what it consumes, which errors it can raise, and which behaviors must never change.

Built for **Claude Code**. Contracts are plain YAML, so any AI tool can read them, but the full design → contract → implementation workflow is optimized for Claude Code.

---

## Why ANMA Exists

AI coding agents often waste context reverse-engineering a codebase before they can safely change it. For a single auth module, an agent may need to inspect controllers, models, serializers, routes, middleware, tests, settings, exceptions, and dependencies just to infer the real interface.

```text
Agent reads auth/controllers/user.py          → 850 tokens
Agent reads auth/models/user.py               → 420 tokens
Agent reads auth/serializers.py               → 380 tokens
Agent reads auth/urls.py                      → 120 tokens
Agent reads auth/middleware.py                → 290 tokens
Agent reads auth/tests/test_user.py           → 640 tokens
Agent reads auth/exceptions.py                → 180 tokens
Agent reads requirements.txt (partial)        → 200 tokens
Agent reads settings.py (partial)             → 350 tokens
Agent infers error types                      → hallucination risk
                                             Total: ~3,400+ tokens
```

ANMA replaces that discovery step with one explicit contract:

```yaml
module: user-auth
version: 1
status: draft

provides:
  - id: register
    input:
      email: string
      password: string
      display_name: string
    output:
      user_id: uuid
      token: string
    errors:
      - EMAIL_TAKEN
      - WEAK_PASSWORD
      - INVALID_EMAIL
    invariants:
      - "auto-sends verification email"
      - "password must be at least 8 characters"

  - id: login
    input:
      email: string
      password: string
    output:
      user_id: uuid
      token: string
    errors:
      - INVALID_CREDENTIALS
      - ACCOUNT_LOCKED
    invariants:
      - "same error for wrong password and non-existent email"

consumes: []
```

```text
Agent reads modules/user-auth/CONTRACT.yaml   → ~350 tokens
                                             Total: ~350 tokens
```

The result: the agent sees the module’s inputs, outputs, errors, invariants, and dependencies without guessing from implementation details.

---

## What ANMA Gives You

- **Explicit module boundaries** — every interface, dependency, error, and invariant is declared.
- **Lower token usage** — agents read compact contracts instead of entire implementation trees.
- **Less hallucination** — agents do not invent missing interfaces or guess error names.
- **Safer implementation** — the linter checks contracts before code gets written.
- **Recoverable AI sessions** — modules carry enough state for Claude to resume later.
- **Change impact analysis** — see what breaks before modifying a contract.
- **Parallel AI work** — different agents can work on different modules because contracts define clear ownership and boundaries.
- **Automatic scaling structure** — as projects grow, ANMA keeps related modules organized so the architecture stays understandable without extra planning overhead.

---

## When to Use ANMA

Use Claude alone for quick scripts, isolated files, and small prototypes.

Use **Claude + ANMA** when your project has multiple modules that depend on each other and you want AI-assisted development to stay coherent across sessions, features, and implementation passes.

| Scenario | Claude alone | Claude + ANMA |
|---|---|---|
| **1–3 files** | Works great | Usually overkill |
| **5+ modules** | May re-infer interfaces differently across sessions | Reads declared contracts |
| **Adding a feature later** | Re-reads source and guesses architecture | Reads contracts and checks impact |
| **Stopping mid-project** | Requires re-explaining context | Resumes from `STATE.yaml` and `MEMORY.yaml` |
| **Integration bugs** | Often found at runtime | Caught earlier by linted contracts |
| **Token usage at scale** | Thousands of tokens per module | Hundreds of tokens per module |

ANMA is best for projects with enough moving parts to need architectural memory — roughly **5+ modules**, multiple interacting features, or a team that expects to use AI agents beyond the first implementation pass. For tiny scripts or one-off prototypes, it is probably more structure than you need.

---

## Quickstart

Choose the workflow that matches how much control you want.

| Path | Best for | Summary |
|---|---|---|
| **Path 1: Conversational** | Founders, product builders, and non-specialists | Claude designs and implements the project with you in one conversation. |
| **Path 2: Terminal** | Developers who want local control | You manage the repo and use Claude Code to implement from contracts. |

### Path 1: Conversational Workflow

Open [Claude](https://claude.ai) with Claude Opus 4.6+. Upload any product specs, design docs, wireframes, research files, or reference material, then start with:

```text
Clone https://github.com/anma-labs/anma-scaffold and read CLAUDE.md and CONVENTIONS.yaml.
Let me know when you're ready to build a project with me.
```

Claude reads the architecture rules and becomes your contract architect. Then describe what you want to build:

```text
I want to build a URL shortener. Users create API keys, shorten URLs with
custom slugs, track clicks with analytics, and use rate limiting.
```

Claude identifies module boundaries, drafts contracts, defines interfaces, declares errors, and captures invariants. When the contracts look right, continue with:

```text
Set up the project and implement all modules.
```

When implementation is complete:

```text
Create app.py that wires all modules together.
```

### Path 2: Terminal Workflow

Clone the scaffold and install the only dependency:

```bash
git clone https://github.com/anma-labs/anma-scaffold my-project
cd my-project
pip install pyyaml
```

Ask Claude to draft contracts from `CLAUDE.md`, `CONVENTIONS.yaml`, and your project description. Then import and validate them:

```bash
python3 tools/init_project.py
python3 tools/import_contracts.py ~/Downloads/*-CONTRACT.yaml
```

Target **0 errors** before implementation. Then run Claude Code:

```bash
claude
```

Prompt it to implement from the contracts:

```text
Read all module contracts and implement them.
```

If implementation reveals a missing dependency, missing error code, or unclear invariant, revise the contract and re-import it:

```bash
python3 tools/import_contracts.py revised-CONTRACT.yaml --force
```

Contract gaps are not failures. They are ANMA catching integration problems before they become silent runtime bugs.

---

## Working Over Time

ANMA is useful after the first implementation, not just during project setup.

To add a feature months later, describe the change normally:

```text
I want to add a waitlist to my event RSVP project. When an event is full,
guests join a queue and get notified when a spot opens.
```

Claude reads the existing contracts, understands how the current modules fit together, updates the relevant contracts, and implements the change without guessing at hidden interfaces.

To resume after a break, start Claude Code again and say:

```text
Continue where we left off.
```

Claude can recover from `STATE.yaml`, `MEMORY.yaml`, and the existing contracts instead of needing you to re-explain the project from scratch.

### Parallel AI Work

ANMA also fits naturally with Claude Code's dynamic workflows. Because each module has its own contract, state, and assumptions, Claude can split larger builds into module-sized implementation tasks instead of forcing one long sequential pass.

For larger projects, you can ask Claude Code to design the contracts first, then parallelize implementation across subagents:

```text
Read CLAUDE.md and CONVENTIONS.yaml. I want to build [description].

Design the contracts first. Then create a dynamic workflow where each
subagent implements one module from its contract. Each subagent should
read CLAUDE.md and CONVENTIONS.yaml plus its assigned contract. After
all modules are implemented, run the linter and verify everything integrates.
```

For teams running multiple agents on the same repo, use claims to coordinate:

```bash
anma claim user-auth payments       # reserve modules before launching agents
anma claims                          # see who owns what
anma release user-auth payments     # release when done
```

For most projects, keep this simple: use dynamic workflows when the project has multiple independent modules, and always run the ANMA linter before merging changes.

---

## Project Structure

Each ANMA module is a directory with six small files. An agent usually needs only `CONTRACT.yaml`, `STATE.yaml`, and `MEMORY.yaml` to recover module context.

```text
your-project/
  CONVENTIONS.yaml      # Universal rules: naming, errors, budgets, architecture
  MANIFEST.yaml         # Module registry with status and ownership
  GRAPH.yaml            # Auto-generated dependency graph
  CLAUDE.md             # Agent instructions auto-read by Claude Code

  modules/
    user-auth/
      CONTRACT.yaml     # What this module provides and consumes
      STATE.yaml        # Current work status and blockers
      MEMORY.yaml       # Short institutional memory
      CHANGELOG.yaml    # Version history
      TESTS.yaml        # Contract-derived test cases
      ASSUMPTIONS.yaml  # Implementation details outside the contract

  BUS/                  # Async inter-module communication
  tools/                # Scripts for linting, scaffolding, and analysis
```

For larger projects, Claude organizes modules into domains with gateway-controlled boundaries:

```text
your-project/
  domains/
    backend/
      GATEWAY.yaml        # Declares which interfaces other domains can use
      user-auth/
      payments/
    frontend/
      GATEWAY.yaml
      web-ui/
```

Contracts define **what the code must do**. Assumptions describe **how the current implementation does it**. That separation lets you replace implementation details without breaking dependent modules.

Contracts move through a simple lifecycle:

```text
draft → stable → frozen
```

Frozen contracts can only be extended, not modified, which protects modules that already depend on them.

---

## CLI Tools

```bash
python3 tools/anma.py init                       # Clear examples and start fresh
python3 tools/anma.py import contracts/*.yaml    # Import contract files
python3 tools/anma.py lint                       # Validate contracts
python3 tools/anma.py lint --strict              # Require zero warnings
python3 tools/anma.py module add billing         # Scaffold a new module
python3 tools/anma.py graph                      # Regenerate dependency graph
python3 tools/anma.py dashboard                  # Show project health
python3 tools/anma.py impact user-auth           # Show what changes if auth changes
```

Run the full CLI help:

```bash
python3 tools/anma.py
```

Standalone scripts are also available, for example:

```bash
python3 tools/lint_contracts.py
```

---

## Real-World Results

We built 3 projects three ways each — without ANMA, with ANMA (sequential), and with ANMA + dynamic workflows — to measure what contracts actually cost and what they give you.

### Benchmark: 3 projects, 9 builds

| | Control | ANMA Sequential | ANMA + Dynamic Workflows |
|---|---:|---:|---:|
| **Project 1: Finance Tracker (4 modules)** | | | |
| Cost | $1.30 | $1.69 | $3.16 |
| API time | 6m 1s | 6m 32s | 15m 26s |
| Runs first try | No | Yes | Yes |
| Tests passing | 32 | 35 | 25 |
| **Project 2: Task Manager (8 modules)** | | | |
| Cost | $1.53 | $2.40 | $8.64 |
| API time | 7m 28s | 11m 29s | 31m 32s |
| Runs first try | Yes | Yes | Yes |
| Tests passing | 42 | 75 | 60 |
| **Project 3: E-commerce (12 modules, 3 domains)** | | | |
| Cost | $2.00 | $3.39 | $5.36 |
| API time | 6m 45s | 12m 24s | 22m 36s |
| Runs first try | Yes | Yes | Yes |
| Tests passing | 42 | 35 | 29 |

All builds used Claude Opus 4.6 on Claude Max. Costs reflect API pricing, not subscription.

### What the data shows

**ANMA costs more on the first build** — 1.3–1.7x for sequential, 2.4–3.6x for dynamic workflows. The overhead is real: designing contracts, running the linter, and reading CONVENTIONS.yaml adds work before implementation starts.

**ANMA runs correctly on first try.** The control failed on Project 1 (wrong entry point, manual fix needed). All 6 ANMA builds ran with `uvicorn app:app` on first attempt.

**ANMA produces more thorough tests at medium scale.** Project 2 (8 modules): 75 tests with ANMA vs 42 without — 78% more coverage from the same prompt.

**ANMA produces architecture, not just code.** Every ANMA build generates contracts, dependency graphs, BUS event wiring, and domain boundaries that persist across sessions. The control produces working code with no architectural documentation.

### Where ANMA pays for itself

The benchmark measures the first build. It does not measure what happens 3 months later when you need to add a feature.

Without ANMA, the agent re-reads your entire codebase to understand what exists (Project 3: 58 Python files). With ANMA, the agent reads 12 contracts (~6,000 tokens) and knows every interface, dependency, and invariant.

ANMA is not a tool for building faster on day one. It is a tool for building correctly across sessions, features, and team members.

Inspect the benchmark projects yourself:
- [Finance Tracker](https://github.com/anma-labs/anma-demo-finance-tracker) — 4 modules
- [Task Manager](https://github.com/anma-labs/anma-demo-task-manager) — 8 modules, BUS events
- [E-commerce Backend](https://github.com/anma-labs/anma-demo-ecommerce) — 12 modules, 3 domains, GATEWAY enforcement

---

## FAQ

### How is ANMA different from OpenAPI or Swagger?

OpenAPI describes HTTP endpoints. ANMA describes internal module boundaries: interfaces, invariants, errors, dependencies, state, memory, assumptions, and change impact. Use OpenAPI for your public API and ANMA for your internal architecture.

### Do I have to use Claude?

The full workflow is built and tested for Claude Code. The contract format is plain YAML, so other LLMs can read it, but the end-to-end workflow is optimized for Claude Code.

### Is this just documentation?

No. Documentation describes what code does. ANMA contracts prescribe what code must do. Because contracts are machine-readable and linted, they can break the build when interfaces, errors, dependencies, or invariants are inconsistent.

### Is ANMA a framework?

No. ANMA is a convention plus a set of scripts. It does not replace your web framework, database, runtime, or deployment stack.

### What is ANMA probably overkill for?

One-off scripts, tiny prototypes, projects with only a few files, and teams that do not plan to use AI agents during design or implementation.

---

## Requirements

- Python 3.8+
- PyYAML

Install PyYAML:

```bash
pip install pyyaml
```

Optional: `pip install tiktoken` for accurate token counting (falls back to estimate otherwise).

---

## Documentation

- [Architecture Overview](docs/ARCHITECTURE.md) — the 7 design principles
- [Contract Guide](docs/CONTRACT-GUIDE.md) — writing effective contracts
- [Quickstart Guide](docs/QUICKSTART.md) — detailed setup walkthrough

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

