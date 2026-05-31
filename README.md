# ANMA — AI-Native Modular Architecture

[![CI](https://github.com/anma-labs/anma-scaffold/actions/workflows/lint.yml/badge.svg)](https://github.com/anma-labs/anma-scaffold/actions/workflows/lint.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-218%20passing-brightgreen)](#)

Plain-YAML module contracts that give AI coding agents your full architecture in ~350 tokens per module — instead of re-reading thousands of lines of source code every session.


![ANMA Demo](docs/assets/demo.gif)


## Get Started

```bash
git clone https://github.com/anma-labs/anma-scaffold my-project
cd my-project
pip install pyyaml
```

Then open Claude Code and tell it what to build:

```bash
claude --permission-mode auto
```

```text
Read CLAUDE.md and CONVENTIONS.yaml. I want to build [describe your project].
Design the contracts first, then implement each module from its contracts.
Run the linter to verify 0 errors before and after implementation.
```

That's it. Claude reads the conventions, designs contracts for your modules, validates them with the 24-check linter, and implements from the contracts.

## Add to an Existing Project

Already have a codebase? Point Claude Code at it:

```bash
cd your-existing-project
claude --permission-mode auto
```

```text
Clone https://github.com/anma-labs/anma-scaffold to a temp directory.
Copy its tools/, checks/, CONVENTIONS.yaml, and CLAUDE.md into this project
without overwriting any existing files. Run python3 tools/init_project.py
to create the project structure. Then analyze my codebase and create ANMA
contracts for each module you find using python3 tools/new_module.py with
--domain. Create GATEWAY.yaml for each domain. Match the contracts to the
actual interfaces, dependencies, and error types in the code. Run
python3 tools/sync_all.py then python3 tools/lint_contracts.py to verify.
```

From this point on, every future session reads contracts first — no more re-inferring architecture from source files.

## Why ANMA

If you're shipping with Claude Code, you've hit these problems:

**"Read the codebase first"** — Every new session re-reads your entire project. At 50+ files, that's thousands of tokens before any work begins. ANMA contracts give Claude the full architecture in ~350 tokens per module.

**"It broke my other module"** — Claude adds a feature and silently breaks another module's interface. ANMA's 24-check linter catches undeclared dependencies, missing error codes, and gateway violations before implementation starts.

**"I can't run agents in parallel"** — Two Claude Code instances cause merge conflicts. ANMA's [claims system](docs/MULTI-AGENT.md) coordinates ownership, domain gateways prevent cross-boundary violations, and derived files regenerate automatically on merge.

**"The architecture is in my head"** — You know the dependencies, but Claude doesn't. Every session you re-explain the same constraints. Contracts externalize those decisions into machine-readable files that every agent reads automatically.

## What a Contract Looks Like

```yaml
module: user-auth
version: 1
purpose: "Handle registration, login, and token verification"

provides:
  - id: register
    input: { email: string, password: string }
    output: { user_id: uuid }
    errors: [EMAIL_TAKEN, WEAK_PASSWORD]
    invariants:
      - "auto-sends verification email"
      - "publishes user_registered event via BUS"

consumes:
  - module: notifications
    interface: send_email
```

~350 tokens. Claude reads this instead of 500+ lines of source code and knows every interface, dependency, error type, and behavioral invariant.

## How It Works

```text
your-project/
  CLAUDE.md                  ← agent instructions (read first every session)
  CONVENTIONS.yaml           ← rules all contracts follow
  MANIFEST.yaml              ← module registry with ownership
  GRAPH.yaml                 ← auto-generated dependency graph
  domains/
    backend/
      GATEWAY.yaml           ← declares public interfaces for this domain
      user-auth/
        CONTRACT.yaml        ← what the module does (interfaces, deps, errors)
        STATE.yaml           ← current status and work-in-progress
        TESTS.yaml           ← auto-generated test cases from contract
      payments/
        ...
    frontend/
      GATEWAY.yaml
      web-ui/
        ...
  tools/                     ← 28 Python tools (linter, scaffolding, analysis)
```

**Contracts** describe what modules do. **Domains** group related modules. **Gateways** control which interfaces are visible across domains. The **linter** enforces all of it — 24 structural checks plus 7 architectural principles.

## Benchmarks

We built 3 projects (4, 8, and 12 modules) with and without ANMA, then added features to each. Key findings:

| | Control | ANMA |
|---|---:|---:|
| Runs correctly first try | 5/6 | 6/6 |
| Tests generated (8-module project) | 42 | 75 |
| Declared interfaces (12-module project) | 0 | 36 |
| BUS event connections | 0 | 17 |
| Architecture documentation | 0 lines | 1,000+ lines |

ANMA costs 1.3–1.7x more on the first build. Adding features later costs the same. The advantage is architectural visibility that compounds across sessions.

Full benchmark data, methodology, and demo repos: **[docs/BENCHMARKS.md](docs/BENCHMARKS.md)**

## CLI Tools

```bash
anma lint --strict          # 24-check linter + 7 principle checks
anma module add <name>      # scaffold a new module
anma module remove <name>   # remove with dependency checks
anma sync                   # regenerate derived files (incremental by default)
anma claim <modules>        # reserve modules for parallel agent work
anma claims                 # see who owns what
anma release <modules>      # release when done
anma dashboard              # project overview
```

Full tool reference: **[docs/WORKFLOWS.md](docs/WORKFLOWS.md)**

## FAQ

**How is ANMA different from OpenAPI or Swagger?**
OpenAPI describes HTTP endpoints. ANMA describes module behavior — interfaces, dependencies, error types, invariants, and BUS events. It's an architecture contract, not an API spec.

**Do I have to use Claude?**
The contracts are plain YAML. Any LLM can read them. The tooling runs with standard Python. Claude Code is recommended because CLAUDE.md is optimized for it.

**Is ANMA a framework?**
No. It's a set of conventions and a linter. There's no runtime, no imports, no lock-in. Delete the tools/ directory and your code still runs.

**What is ANMA overkill for?**
Single-file scripts, throwaway prototypes, and projects where you don't use AI agents for implementation. If you write all the code yourself, contracts add overhead without payoff.

## Requirements

- Python 3.10+
- `pip install pyyaml`
- Optional: `pip install tiktoken` for accurate token counting (falls back to estimate)

## Documentation

| Doc | Description |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Agent instructions — read by Claude every session |
| [CONVENTIONS.yaml](CONVENTIONS.yaml) | Rules all contracts follow |
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | Step-by-step first project guide |
| [docs/WORKFLOWS.md](docs/WORKFLOWS.md) | Detailed terminal and conversational workflows |
| [docs/MULTI-AGENT.md](docs/MULTI-AGENT.md) | Parallel agents, claims, dynamic workflows |
| [docs/BENCHMARKS.md](docs/BENCHMARKS.md) | Full benchmark data and demo repos |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 7 principles and design rationale |
| [docs/CONTRACT-GUIDE.md](docs/CONTRACT-GUIDE.md) | How to write good contracts |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All PRs must pass `python3 tools/lint_contracts.py --strict` and `python3 -m unittest tools.test_linter`.
