# Workflows

## Path 1: Terminal Workflow (Recommended)

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
claude --permission-mode auto
```

Prompt it to implement from the contracts:

```text
Read all module contracts and implement them.
```

If implementation reveals a missing dependency, missing error code, or unclear invariant, revise the contract and re-import it:

```bash
python3 tools/import_contracts.py ~/Downloads/updated-CONTRACT.yaml
python3 tools/lint_contracts.py --strict
```

## Path 2: Conversational Workflow

For quick prototyping in the browser. Open [Claude](https://claude.ai) with Claude Opus 4.6+ (enable Code Execution and File Creation in Settings if not already on).

Prompt sequence:

```text
1. Clone https://github.com/anma-labs/anma-scaffold and read CLAUDE.md and CONVENTIONS.yaml.

2. I want to build [describe your project with key features and user interactions].

3. Design the contracts. Run the linter to verify 0 errors.

4. Set up the project and implement all modules.

5. Create app.py that wires all modules together.

6. Package the entire project as a zip file I can download.
```

## Working Over Time

When starting a new session on an existing ANMA project, Claude Code automatically reads `CLAUDE.md` which loads all contracts. No need to re-explain your architecture.

To continue where you left off:

```text
Read all module contracts and STATE.yaml files.
Continue implementing — pick up from where STATE.yaml says current_work.
```

## Contract Lifecycle

Modules move through statuses:

- **draft** — actively being designed, interfaces may change
- **stable** — interfaces locked, implementation underway or complete
- **frozen** — no changes allowed, depended on by many modules

The linter enforces frozen contracts — `removing_interface` must be `forbidden` for frozen modules.

## CLI Reference

### Scaffolding

```bash
anma module add <name> [--domain <domain>] [--type regular|infrastructure]
anma module remove <name> [--confirm] [--force]
anma init                                    # reset project to clean state
anma import <files...> [--domain <domain>]   # import contract files
```

### Validation

```bash
anma lint [--strict] [--module <name>]       # 24 checks + 7 principles
anma sync [--force] [--regenerate-only]      # regenerate derived files
```

### Analysis

```bash
anma dashboard                               # project overview
anma diff <module>                           # show contract changes
anma impact <module>                         # downstream impact analysis
anma compat                                  # compatibility matrix
anma viz                                     # dependency graph (DOT format)
```

### Multi-Agent

```bash
anma claim <modules...>                      # reserve for exclusive work
anma claims                                  # show current claims
anma release <modules...>                    # release when done
```

### Generation

```bash
anma gentests                                # regenerate test specs
anma claude                                  # regenerate CLAUDE.md
anma spec                                    # generate product spec
anma rename <new-name>                       # rename the project
```
