# Contributing

ANMA is deliberately small (~780 lines). The bar for new code is high: prefer
making the existing primitives sharper over adding surface area. If a change
grows the tool a lot, it probably belongs in a plugin or a separate scenario, not
the core.

## Dev setup

```bash
git clone https://github.com/anma-labs/anma
cd anma
pip install -e .[dev]      # pytest + pip-audit; add [tach] for the tach engine
python -m pytest tests/ -q
```

## ANMA dogfoods itself

The repo carries its own contracts, so the same checks you ship run here:

```bash
anma sync --check .        # generated docs/config are current with the contracts
anma check .               # internal boundaries respected
```

Both must pass before a PR merges (CI enforces them in the `dogfood` job).

## PR checklist

- [ ] `python -m pytest tests/ -q` green (and `benchmarks/` tests if you touched the harness)
- [ ] `anma sync --check .` and `anma check .` clean — if you changed a contract or a template, re-run `anma sync .` and commit the regenerated files
- [ ] `pip-audit` clean
- [ ] New behavior has a test; new contract fields are documented in `docs/CONCEPTS.md`
- [ ] `CHANGELOG.md` updated under "Unreleased"

## The schema-stability rule (read before touching contracts)

The contract schema is ANMA's real public API — users commit to it. Treat it like
one:

- Adding an **optional** field with a safe default is a minor change.
- Removing or renaming a field, changing a field's meaning, or making a field
  required is a **breaking** change: bump `SUPPORTED_SCHEMA` in
  `anma/contracts.py`, bump the tool's major version, and ship a migration path.
- Never make the tool silently reinterpret existing contracts.

## Code shape

- Keep `cli.py` as the only place argparse/IO wiring lives; core modules
  (`contracts`, `engine`, `compile`, `templates`, `scaffold`) must not import it.
- `tach` stays optional — `engine.py` must keep working via the builtin checker
  with zero extra dependencies.
- Generated artifacts are produced by pure `render_*` functions in `compile.py`
  so `anma sync` and `anma sync --check` share one code path. Keep them pure.

## Reporting security issues

See [SECURITY.md](SECURITY.md) — do not open public issues for vulnerabilities.
