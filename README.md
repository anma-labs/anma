# ANMA — AI-Native Modular Architecture

**Plain-YAML module contracts that help AI coding agents understand your codebase in ~350 tokens instead of 5,000–20,000.**

No hallucinated interfaces. No undeclared dependencies. No silent integration bugs.

ANMA is a lightweight scaffold for AI-assisted software development. It gives every module a small, machine-readable contract that defines what the module provides, what it consumes, which errors it can raise, and which behaviors must never change.

Built for **Claude Code**. Contracts are plain YAML, so any AI tool can read them, but the full design → contract → implementation workflow is optimized for Claude Code.

---

## Why ANMA Exists

AI coding agents often spend most of their context window trying to understand a codebase before they can safely change it.

Without ANMA, an agent may need to inspect controllers, models, serializers, routes, middleware, tests, settings, exceptions, and dependencies just to infer what one module is supposed to do:

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

That gives the agent a complete module-level interface without forcing it to reverse-engineer the implementation first.

---

## What ANMA Gives You

- **Explicit module boundaries** — every interface, dependency, error, and invariant is declared.
- **Lower token usage** — agents read compact contracts instead of entire implementation trees.
- **Less hallucination** — agents do not have to invent missing interfaces or guess error names.
- **Safer implementation** — the linter checks contracts before code gets written.
- **Recoverable AI sessions** — each module carries its own state and memory.
- **Clean continuation** — stop mid-project and let Claude resume from project state later.
- **Change impact analysis** — see what breaks before modifying a contract.
- **AI-friendly architecture** — small files, clear conventions, and dependency-aware workflows.

---

## Claude Alone vs. Claude + ANMA

Claude is already excellent for small scripts, isolated files, and fast prototypes. ANMA is for the point where your project has enough moving parts that an agent needs stable architecture, not just raw source code.

| Scenario | Claude alone | Claude + ANMA |
|---|---|---|
| **1–3 files** | Works great | Usually overkill |
| **5+ modules** | May lose coherence or infer interfaces differently across sessions | Reads explicit contracts with declared inputs, outputs, errors, and dependencies |
| **Adding a feature later** | Re-reads source code and re-infers architecture | Reads contracts and runs impact analysis before changing behavior |
| **Stopping mid-project** | Often requires re-explaining context | Reads `STATE.yaml` and `MEMORY.yaml` to resume work |
| **Integration bugs** | Can stay hidden until runtime or production | Caught earlier through declared dependencies, errors, events, and invariants |
| **Token usage at scale** | Thousands of tokens per module to orient | Hundreds of tokens per module to understand the contract |

Use Claude alone for quick scripts and small experiments. Use ANMA when your project has multiple modules that depend on each other and you want AI-assisted development to stay coherent over time.

---

## Quickstart

Choose the workflow that matches how much control you want.

| Path | Best for | Summary |
|---|---|---|
| **Path 1: Conversational** | Founders, product builders, and non-specialists | Claude designs and implements the project with you in one conversation. |
| **Path 2: Terminal** | Developers who want control | You manage the repo locally and use Claude Code to implement from contracts. |

---

## Path 1: Conversational Workflow

Use this path if you want Claude to handle the design and implementation flow.

1. Open [Claude](https://claude.ai) with Claude Opus 4.6+.
2. Upload any research files, product specs, design docs, wireframes, or reference material.
3. Start with this prompt:

```text
Clone https://github.com/nxy/anma-scaffold and read CLAUDE.md and CONVENTIONS.yaml.
Let me know when you're ready to build a project with me.
```

Claude will read the architecture rules and become your contract architect.

Then describe what you want to build:

```text
I want to build a URL shortener. Users create API keys, shorten URLs with
custom slugs, track clicks with analytics, and use rate limiting.
```

Claude will identify module boundaries, draft contracts, define interfaces, list inputs and outputs, declare errors, and capture behavioral invariants.

When the contracts look right, say:

```text
Set up the project and implement all modules.
```

Claude will clear the examples, import contracts, validate them, implement each module, update state files, and flag contract gaps as they appear.

When implementation is complete, say:

```text
Create app.py that wires all modules together.
```

---

## Path 2: Terminal Workflow

Use this path if you want to manage each step yourself.

### 1. Clone the scaffold

```bash
git clone https://github.com/nxy/anma-scaffold my-project
cd my-project
pip install pyyaml
```

### 2. Design contracts

Upload `CLAUDE.md` and `CONVENTIONS.yaml` to [Claude](https://claude.ai), then describe the project you want to build.

Claude drafts ANMA contracts and provides them as downloadable YAML files.

### 3. Import and validate contracts

```bash
python3 tools/init_project.py
python3 tools/import_contracts.py ~/Downloads/*-CONTRACT.yaml
```

The import step creates module directories, copies contracts, generates supporting files, and runs the linter.

Target **0 errors** before implementation.

### 4. Implement with Claude Code

```bash
claude
```

Then prompt Claude Code:

```text
Read all module contracts and implement them.
```

Claude Code reads `CLAUDE.md`, follows the architecture rules, implements modules in dependency order, updates `STATE.yaml`, and records decisions in `MEMORY.yaml`.

### 5. Revise contracts when needed

If implementation reveals a missing dependency, missing error code, or unclear invariant, update the contract and re-import it:

```bash
python3 tools/import_contracts.py revised-CONTRACT.yaml --force
```

Contract gaps are not failures. They are ANMA doing its job before integration bugs become silent runtime problems.

### 6. Wire the application

```text
Create app.py that wires all modules together.
```

Both workflows produce the same result: explicit contracts, validated dependencies, and code that matches the spec.

---

## Working on Existing Projects

ANMA is not only for greenfield builds. You can also use it to add features later.

For example:

```text
I want to add a waitlist to my event RSVP project. When an event is full,
guests join a queue and get notified when a spot opens.
```

Claude reads the existing contracts, understands the current modules and their dependencies, designs the new feature to fit the architecture, updates the relevant contracts, and implements the change without guessing at hidden interfaces.

This is where ANMA becomes especially useful: the architecture remains understandable months after the original implementation session.

---

## Resuming After a Break

If you stop mid-project, you do not need to write a handoff note.

Start Claude Code again and say:

```text
Continue where we left off.
```

Claude can read the project state, inspect what is done and what is blocked, recover module-level context from `STATE.yaml` and `MEMORY.yaml`, and continue from the last known implementation point.

---

## Real-World Results

In a [4-module URL shortener demo](https://github.com/nxy/anma-demo-url-shortener), contracts caught 5 integration bugs during implementation, including undeclared dependencies, missing error codes, and absent BUS events.

A larger production test scaffolded 18 modules with 104 interfaces in one Claude Code session:

| Metric | Result |
|---|---:|
| Modules scaffolded | 18 |
| Interfaces implemented | 104 |
| Tests generated | 239 |
| Input tokens per session | ~14,600 |
| Total API cost | $31 |
| Time | 91 minutes |

This repository includes 3 example modules with 14 interfaces so you can inspect the format immediately.

---

## Project Structure

Each ANMA module is a directory with six small files. An agent recovering a module usually reads only `CONTRACT.yaml`, `STATE.yaml`, and `MEMORY.yaml`.

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

Contracts define **what the code must do**.

Assumptions describe **how the current implementation does it**.

That separation makes it easier to replace implementation details without breaking dependent modules.

---

## Contract Lifecycle

ANMA contracts move through three stages:

```text
draft → stable → frozen
```

| Status | Meaning |
|---|---|
| `draft` | The contract is still being designed and may change. |
| `stable` | The contract is ready for implementation and dependency use. |
| `frozen` | The contract can only be extended, not modified. |

Frozen contracts protect modules that already depend on them.

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

## When to Use ANMA

ANMA is designed for projects with:

- 5–80 modules
- 1–4 developers
- Frequent AI-assisted implementation
- Clear module boundaries
- A need for safer agent handoffs and recoverable sessions

It is especially useful when a project is too large for an AI agent to understand comfortably from raw source files, but not large enough to justify heavyweight internal platform tooling.

ANMA is probably overkill for:

- One-off scripts
- Small prototypes with only a few files
- Projects where modules do not depend on each other
- Teams that do not plan to use AI agents during design or implementation

---

## FAQ

### Why not just use Claude directly?

Use Claude directly when the project is small, temporary, or contained in a few files.

Use ANMA when the project has enough modules, dependencies, and future changes that Claude needs a stable architectural map instead of repeatedly re-reading and re-inferring the codebase.

ANMA does not replace Claude. It gives Claude a contract-first structure that keeps implementation coherent across modules, sessions, and future feature work.

### How is ANMA different from OpenAPI or Swagger?

OpenAPI describes HTTP endpoints.

ANMA describes internal module boundaries: interfaces, invariants, errors, dependencies, state, memory, assumptions, and change impact.

You can use both. Use OpenAPI for your public API and ANMA for your internal architecture.

### Do I have to use Claude?

The full workflow is built and tested for Claude Code.

The contract format is plain YAML, so other LLMs can read it, but the end-to-end design and implementation workflow is optimized for Claude Code.

### Is this just documentation?

No.

Documentation describes what code does. ANMA contracts prescribe what code must do.

Because contracts are machine-readable and linted, they can break the build when interfaces, errors, dependencies, or invariants are inconsistent.

### Is ANMA a framework?

No.

ANMA is a convention plus a set of scripts. It does not replace your web framework, database, runtime, or deployment stack.

### What size projects is ANMA best for?

ANMA is best suited for projects with roughly 5–80 modules and 1–4 developers.

Most real software products fit this range: too complex for an AI agent to understand safely from raw files alone, but small enough to benefit from lightweight architecture contracts instead of heavyweight platform governance.

### How do I add a feature months later?

Open Claude and describe the feature in normal language:

```text
I want to add a waitlist to my event RSVP project. When an event is full,
guests join a queue and get notified when a spot opens.
```

Claude reads the existing contracts, understands how the modules connect, designs the new behavior to fit the current architecture, and updates the implementation without breaking existing contracts.

### What if I stop mid-project?

Just stop.

Next time, open Claude Code and say:

```text
Continue where we left off.
```

Claude reads the project state, checks what is done and what remains blocked, and resumes from the existing contracts, state files, and memory files.

---

## Requirements

- Python 3.8+
- PyYAML

Install PyYAML:

```bash
pip install pyyaml
```

No other dependencies are required.

---

## Documentation

- [Architecture Overview](docs/ARCHITECTURE.md) — the 7 design principles
- [Contract Guide](docs/CONTRACT-GUIDE.md) — writing effective contracts
- [Quickstart Guide](docs/QUICKSTART.md) — detailed setup walkthrough

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

[BSL 1.1](LICENSE) — free to use for any project. You cannot use it to build a competing scaffold product.

The license converts to Apache 2.0 on May 23, 2029.
