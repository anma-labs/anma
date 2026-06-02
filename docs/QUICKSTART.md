# ANMA Quickstart

Get a working ANMA project in 5 minutes.

## Prerequisites

- Python 3.10+
- `pip install pyyaml`

## Step 1: Clone

```bash
git clone https://github.com/anma-labs/anma-scaffold my-project
cd my-project
```

## Step 2: Verify the scaffold

```bash
python3 tools/lint_contracts.py
```

Three example modules checked, 0 errors. Browse `domains/core/user-auth/CONTRACT.yaml` to see a full contract.

## Step 3: Design your contracts

Upload `CLAUDE.md` and `CONVENTIONS.yaml` to [Claude](https://claude.ai) and describe what you're building:

> "I uploaded my ANMA scaffold files. I want to build a URL shortener with
> auth, link management, analytics, and rate limiting."

Claude drafts contracts, asks clarifying questions, and iterates with you. When ready:

> "Give me all CONTRACT.yaml files so I can save them and run the linter."

Claude provides them as downloadable files.

## Step 4: Import and validate

```bash
python3 tools/init_project.py                                 # clear example modules
python3 tools/import_contracts.py ~/Downloads/*-CONTRACT.yaml  # import, sync, lint
```

One command creates module directories, copies contracts, generates supporting
files (STATE, MEMORY, TESTS, GRAPH, MANIFEST), and runs the linter. If there
are errors, fix the contracts and re-import. Target 0 errors before moving on.

## Step 5: Assign managers

Edit MANIFEST.yaml — add `manager: <name>` to each module entry and define
manager groups:

```yaml
modules:
  auth: { status: stable, manager: core }
  links: { status: stable, manager: features }

managers:
  core: { owns: [auth, rate-limiter] }
  features: { owns: [links, analytics] }
```

Run `python3 tools/lint_contracts.py --strict` — target 0 errors, 0 warnings.

## Step 6: Implement with Claude Code

```bash
claude
> Read all module contracts and implement them.
```

Claude Code reads CLAUDE.md, knows the architecture, and implements each
module. It handles dependency ordering, updates STATE.yaml with progress,
and captures decisions in MEMORY.yaml.

## Step 7: Discover and revise

If implementation surfaces contract gaps (undeclared dependencies, missing
error codes), revise the contracts and re-import:

```bash
python3 tools/import_contracts.py revised-CONTRACT.yaml --force
```

Then update the implementation. Contracts catching integration bugs is ANMA
working as designed.

## Step 8: Wire and ship

```bash
> Create app.py that wires all modules together.
```

## What's Next

- [Architecture Overview](ARCHITECTURE.md) — how ANMA works and the 7 design principles
- [Contract Guide](CONTRACT-GUIDE.md) — best practices for writing contracts
- [CONTRIBUTING.md](../CONTRIBUTING.md) — how to contribute
