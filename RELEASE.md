# Release & migration runbook

Step-by-step to (A) rename the repo to `anma`, (B) claim the PyPI name and set up
keyless signed publishing, and (C) cut the first release. Browser-only until the
final tag — nothing here needs your Mini PC.

> Verified locally before writing this: `python -m build` succeeds and
> `twine check` PASSES on both the sdist and the wheel; the wheel installs in a
> clean venv and the `anma` CLI runs. So the package is publishable as-is.

---

## A. Rename `anma-scaffold` → `anma` (don't recreate)

Renaming preserves stars, issues, PRs, and history, and GitHub auto-redirects the
old URL (web + git, HTTP and SSH). Creating a fresh repo loses all of that.

1. GitHub → repo **Settings → General → Rename** to `anma`.
   (CLI equivalent: `gh repo rename anma -R anma-labs/anma-scaffold`.)
2. Update your local clone's remote:
   ```bash
   git remote set-url origin git@github.com:anma-labs/anma.git
   ```
3. Sanity-check references to the old name (most are already `anma-labs/anma`):
   ```bash
   grep -rn "anma-scaffold" . --exclude-dir=.git
   ```
   Fix any stragglers in README badges, docs, or the landing page, then commit.

The old `anma-labs/anma-scaffold` links keep redirecting, so existing stars and
inbound links survive.

---

## B. Claim the PyPI name + set up Trusted Publishing (keyless)

1. **Confirm the name is free:** open `https://pypi.org/project/anma/`. A 404 means
   it's available. (If taken, the package name must change — and then the repo,
   CLI, and `pip install` line should match it.)

2. **Create a "pending" Trusted Publisher** (works *before* the project exists):
   PyPI → **Your projects → Publishing → Add a pending publisher**. Enter:
   - PyPI Project Name: `anma`
   - Owner: `anma-labs`
   - Repository: `anma`
   - Workflow filename: `release.yml`
   - Environment name: `pypi`  *(optional but recommended — see step 3)*

   This is OIDC-based: no API tokens are ever stored. It matches the `id-token:
   write` permission already in `.github/workflows/release.yml`.

3. **(Recommended) Add a protected GitHub Environment** named `pypi`
   (repo Settings → Environments) so only reviewed tags can publish. If you use
   it, add `environment: pypi` to the `build-and-publish` job in `release.yml`.

4. **Dry-run on Test PyPI first (optional but wise):** repeat step 2 on
   `test.pypi.org`, then run the release flow once with the publish step pointed at
   Test PyPI:
   ```yaml
   - uses: pypa/gh-action-pypi-publish@release/v1
     with:
       repository-url: https://test.pypi.org/legacy/
   ```
   Verify `pip install -i https://test.pypi.org/simple anma` works, then revert.

---

## C. Cut the first release (v0.5.0)

Pre-flight (all already green locally — re-run after the rename commit):

```bash
python -m pytest tests/ -q          # 20 passed
anma sync --check .                 # generated artifacts current
anma check .                        # boundaries clean
pip install pip-audit && pip-audit  # no known vulns
python -m build && twine check dist/*   # build + metadata OK
```

Then:

1. Bump is already at `0.5.0` (`pyproject.toml` + `anma/__init__.py`). Add a
   `CHANGELOG.md` entry if you keep one.
2. Tag and push:
   ```bash
   git tag v0.5.0 && git push origin v0.5.0
   ```
3. GitHub → **Releases → Draft a new release** on `v0.5.0`, publish it. That
   `release: published` event triggers `release.yml`, which builds, attaches a
   CycloneDX SBOM, attests build provenance, and publishes to PyPI via the
   trusted publisher — no tokens.
4. Confirm `pip install anma` works from a clean machine.

---

## Where this sits relative to the benchmark

The live benchmark run (`python -m bench.run --runner claude-code`) is the
evidence step and needs your Mini PC. Do the rename + PyPI setup (browser) so the
canonical `anma` repo and a published v0.5.0 are in place; then run the live arm
at home and publish the numbers (see `docs/BENCHMARKS.md`). Order doesn't strictly
matter, but a published, renamed repo makes the launch post's links and
`pip install anma` correct on day one.
