# Quickstart

From install to watching Claude Code get blocked at a boundary. ~5 minutes.
For the full field reference, see [CONCEPTS.md](CONCEPTS.md).

## 1. Install

```bash
pip install anma[tach]   # tach backend (interface-level checks); plain `anma` also works
anma --version
```

## 2. Scaffold

```bash
anma init
```

This drops a root `anma.yaml` and a worked example under `src/domains/`: an
`accounts` module and a `billing` module, where `billing` may depend on
`accounts` but **not** the reverse.

This walkthrough is Python. For Go or TypeScript, run `anma init --language go`
or `anma init --language typescript` — the same `accounts`/`billing` boundary in
that language. The flow below is identical; only the source files and the engine
config differ (`.go-arch-lint.yml` / `.dependency-cruiser.cjs` instead of
`tach.toml`). Go and TypeScript enforce module→module dependencies (interface-level
`public:` enforcement is Python-only today). See
[CONCEPTS § Languages](CONCEPTS.md#languages).

## 3. Generate the guardrails

```bash
anma sync
```

You now have a generated root `CLAUDE.md` (architecture map), a per-module
`CLAUDE.md` in each module folder, a `PreToolUse` hook under `.claude/`, a
`tach.toml`, and a CI workflow. Look at `src/domains/accounts/CLAUDE.md` — that's
what Claude Code loads the moment it opens the `accounts` folder.

## 4. See enforcement, three ways

**At the command line:**

```bash
anma check          # ✓ All module boundaries respected
```

Now add a forbidden import to `src/domains/accounts/service.py`:

```python
from domains.billing.service import total_invoiced   # accounts may not use billing
```

```bash
anma check          # ✗ 1 boundary violation(s) — points at the file:line
```

**In Claude Code (the part that matters):** open the project and ask Claude to
add that same `billing` import to `accounts`. The PreToolUse hook returns exit
code 2 and Claude Code blocks the edit before it lands, with a message telling it
to fix the import or update the contract.

**In CI:** the generated `.github/workflows/anma.yml` runs `anma sync --check`
(catches docs/config that drifted from the contracts) and `anma check`.

## 5. Change a boundary the right way

Boundaries aren't sacred — they're just *explicit*. To let `accounts` use
something new, don't work around the check: edit the module's `anma.yaml`
(`depends_on`), then:

```bash
anma sync           # regenerate the docs + config from the new contract
```

and add a one-line entry to `DECISIONS.md` saying why. Now the new boundary is
real, enforced, and preserved for the next session.

## Adopting an existing codebase

A large repo won't be clean on day one. Two levers:

- `anma check --warn` reports violations but exits 0, so the build stays green
  while you fix them.
- Mark a not-yet-removable dependency as `deprecated_deps:` in the contract — it
  warns instead of failing, so you can ratchet toward compliance.

## Where ANMA helps most

The benchmark ([../docs/BENCHMARKS.md](../docs/BENCHMARKS.md)) shows the effect is
model-dependent: a frontier model tends to respect a documented architecture on
its own, while a cheaper/faster model violated a boundary ~68% of the time in a
plain repo and 0/20 with ANMA (Python). So you'll see the biggest difference when
driving cheaper or weaker agents — and the enforcement hook plus CI gate hold
regardless of which model or human wrote the change. (The Go/TS scenarios are a
weaker discriminator for that model so far — an honest null; see BENCHMARKS.)

## Next

- [CONCEPTS.md](CONCEPTS.md) — every field, every generated file, the engine.
- [../benchmarks/README.md](../benchmarks/README.md) — measure the with/without
  difference on your own machine.
