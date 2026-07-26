# Releasing Whetstone

> **Nothing has been released yet.** There are no git tags, no PyPI project, and **no
> `.github/workflows/release.yml` on this branch** — the release workflow described below is the
> intended mechanism, not a running one. Until that file exists and has been watched succeeding,
> pushing a tag does nothing but create a tag. This document exists so the first release is cut
> deliberately rather than improvised; do not read any step below as already working.

Releases are cut by **pushing a version tag** — tag-push is the entire release mechanism. There
is no manual upload step and no `gh release create` by hand: when the workflow lands, the
GitHub Release is owned by the repository (via its `GITHUB_TOKEN`), not by whatever account the
local `gh` CLI happens to be logged into.

The PyPI distribution is **`whetstonehq`** (the name `whetstone` is already taken on PyPI); the
import package and the `whetstone` command are unchanged. Anything that reads the version at
runtime looks up `whetstonehq` metadata — the distribution name, not the import name.

> **No container channel.** Whetstone's local runtime is MLX (`mlx-lm`), which is
> Apple-Silicon-only, so a Linux container cannot run the loop's main job. A container channel is
> deliberately deferred rather than shipping an image that can't train anything. Linux
> portability is named as post-horizon in `docs/ROADMAP.md` § 9.

## Versioning

`0.x.0` minor bumps, one per shipped capability/milestone. Patch releases (`0.x.y`) batch fixes.
Whetstone is pre-1.0: a `0.x` bump may include changes that would be breaking under strict
semver. The tag **must** match the `version` in `pyproject.toml`, and the release workflow is
expected to validate that rather than trust it.

Tags are `vX.Y.Z` (e.g. `v0.1.0`).

## Cut a release

1. Bump `version` in `pyproject.toml` and move the `[Unreleased]` notes into a dated version
   section in `CHANGELOG.md`.
2. Commit to `master` and make sure CI is green (`.github/workflows/ci.yml`).
3. Confirm the tree is clean from a fresh clone: `uv sync`, then `uv run pytest`,
   `uv run ruff check .`, `uv run mypy src/`, `uv run whetstone --help` — all exit 0.
4. Tag and push the tag — a plain `git push`, using the repo's git identity:

   ```bash
   git tag -a v0.1.0 -m "whetstone 0.1.0"
   git push origin v0.1.0
   ```

5. The `release` workflow then, in independent parallel jobs:
   - builds the wheel and sdist and **publishes `whetstonehq` to PyPI** (via trusted
     publishing — see below),
   - **creates the GitHub Release** from the matching `CHANGELOG.md` section and attaches the
     wheel + sdist.

   Each channel is a separate job, so one failing does not block the others. Watch it with
   `gh run watch` or the Actions tab.

## Before the first release can happen

These are prerequisites, none of them done yet:

1. **Write `.github/workflows/release.yml`** — triggered on `v*` tags, validating the tag against
   the `pyproject.toml` version, with least-privilege `permissions` and `id-token: write` on the
   PyPI job only. The `whetstone-end-fast` skill already references this path, so its absence is
   a gap rather than a decision.
2. **Register `whetstonehq` on PyPI** and configure trusted publishing (below).
3. **Cut `v0.1.0` only after CI has been green on `master`** — a release from a red or unproven
   tree contradicts the project's own promotion rule.

## One-time setup per channel

### GitHub Release

Nothing to set up — it uses the repo `GITHUB_TOKEN`.

### PyPI (trusted publishing, no stored token)

Publish with [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) so no API token
is stored in the repo. One time:

1. Create the project **`whetstonehq`** on PyPI (or reserve it by uploading the first build
   manually once), owned by the account that should own the package.
2. In the project's **Publishing** settings on PyPI, add a GitHub Actions trusted publisher:
   - Owner: `haqaliz`
   - Repository: `whetstone`
   - Workflow: `release.yml`
   - Environment: `pypi`
3. The `pypi` job runs in the `pypi` GitHub environment and requests the `id-token: write`
   permission the workflow declares. No secrets needed.

If trusted publishing is not yet configured, the PyPI job fails (harmlessly — the other channels
still publish); configure it and re-run just that job, or cut a patch release.

## Release identity

The release belongs to the **haqaliz** account and the **haqaliz/whetstone** repository. Any
manual asset handling must run with `gh` active as `haqaliz`
(`gh auth switch --user haqaliz`). Commit as `aliz@foresightanalytics.ca` (maps to haqaliz) —
the identity this repo's history already uses.
