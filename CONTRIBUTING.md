# Contributing to ANMA

## Getting Started

1. Fork the repository
2. Clone your fork
3. Create a feature branch: `git checkout -b feature/my-change`
4. Make your changes
5. Run the linter: `python3 tools/lint_contracts.py --strict`
6. Commit and push
7. Open a pull request

## What to Contribute

### High-value contributions

- **New tools** — scripts that solve real problems in contract-driven development
- **Linter rules** — additional checks for `lint_contracts.py`
- **Documentation improvements** — clearer explanations, better examples, fixed typos
- **Bug fixes** — in tools, linter, or scaffolding scripts
- **Example modules** — well-designed contracts that demonstrate patterns

### Before starting large changes

Open an issue first. Describe what you want to change and why. This avoids duplicate work and ensures your approach aligns with the project direction.

## Code Standards

### Python scripts (tools/)

- Python 3.10+ compatible
- No external dependencies beyond PyYAML
- Include docstrings for public functions
- Run `python3 tools/test_linter.py` to verify linter changes

### YAML files

- Follow CONVENTIONS.yaml naming rules
- Module names: `kebab-case`
- Interface names: `snake_case`
- Error codes: `SCREAMING_SNAKE_CASE`

### Contracts

- Every interface must have at least one invariant
- Invariants describe behavior, not implementation
- Implementation details go in ASSUMPTIONS.yaml
- Lint with `--strict` before submitting

## Pull Request Guidelines

- Keep PRs focused — one logical change per PR
- Include a clear description of what changed and why
- If adding a tool, include usage examples in the PR description
- If changing the linter, include test cases
- If adding a convention, explain the reasoning

## Commit Messages

Use imperative mood: "Add feature" not "Added feature" or "Adds feature".

```
Add contract versioning validation to linter

The linter now checks that contract versions are positive integers
and that version bumps accompany breaking changes.
```

## Running Tests

```bash
# Lint all contracts
python3 tools/lint_contracts.py --strict

# Test the linter itself
python3 tools/test_linter.py

# Smoke test all tools
python3 tools/smoke_test.py
```

## Architecture Decisions

If your change affects how ANMA works conceptually (new file types, changed conventions, modified lifecycle), open a discussion issue first. These changes affect every project using ANMA and need careful consideration.
