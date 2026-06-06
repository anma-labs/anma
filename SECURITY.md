# Security Policy

## Reporting a vulnerability
Email **security@anmalabs.dev** (or open a private GitHub security advisory).
We aim to acknowledge within 3 business days. Please do not open public issues
for security reports.

## Security model — what ANMA does and does not do
ANMA is designed to be trivial to review. The entire tool is a few hundred lines
of Python and pulls in **no required third-party runtime dependency** (the
optional `tach` backend is the only extra, and the builtin engine works without
it).

- **ANMA never executes your application code.** The builtin engine parses files
  with Python's `ast` (static analysis only); the `tach` backend likewise does
  static import analysis. Neither imports or runs your modules.
- **The PreToolUse hook only blocks — it never edits.** On a boundary violation
  it returns exit code 2 so Claude Code rejects the edit. It does not modify
  files, call the network, or run your code.
- **All generated artifacts are plain text** (`CLAUDE.md`, `tach.toml`,
  `CODEOWNERS`, YAML, shell-free Python hook) and are meant to be committed and
  reviewed like any other source.
- **No telemetry, no network calls** in `init`, `sync`, or `check`.

## Supply chain
- Releases are published via **PyPI Trusted Publishing** (OIDC, no long-lived
  tokens) with **build provenance attestations**.
- A **CycloneDX SBOM** is attached to every release.
- `pip-audit` runs in CI on every push and pull request.
- Runtime dependencies are pinned to a major version (`pyyaml>=6.0,<7`).

## Supported versions
The latest minor release receives security fixes. The **contract schema**
(`schema_version`) follows SemVer independently — see README "Stability".
