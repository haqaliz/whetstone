# `tests/fixtures/wheelhouse` — the test runner, committed

**This directory is scaffolding, never a subject.** It holds `pytest` and the distributions
`pytest` requires, so that a throwaway venv built by this suite can *run a fixture repository's
tests at all*. Nothing in here is under study, and nothing in here is a dependency of Whetstone
— the project itself declares zero runtime dependencies.

Keep the distinction in view, because the suite rests on it:

| Directory | What it holds | Whose result depends on it |
|---|---|---|
| `tests/fixtures/pkgindex` | the two `whetstone-fixture-dep` wheels | **the claim** — `environment.pins` decides the verdict |
| `tests/fixtures/wheelhouse` | `pytest` and its requirements | **the plumbing** — how any declared test gets executed |

A resolution that reached into this directory for a *version under study* would be a test
grading itself; that is why `pkgindex` is separate and why the two resolutions never share a
`--find-links`. `tests/test_runner_wheelhouse.py` asserts that this directory holds nothing
`pkgindex` holds.

## Why the wheels are committed

Several tests build a throwaway venv and verify a task inside it, and the reward runs the
declared tests as `<that venv>/bin/python -m pytest`. So each venv needs its own `pytest`,
installed **offline** — every provisioning command in this suite carries `--offline`, because a
suite that fetched from an index would make its own results depend on what that index served
that morning.

Before this directory existed, those installs were `uv pip install --offline pytest` and nothing
else, which resolves only from uv's own cache. That worked on a developer machine — whose cache
already held pytest's registry metadata from some earlier resolution — and **failed on a cold CI
runner**, where `uv sync` populates the cache from a lockfile and never performs the resolution
that would cache what `pytest` (unpinned, unlocked) needs:

```
× No solution found when resolving dependencies:
╰─▶ Because pytest was not found in the cache and you require pytest, we can
    conclude that your requirements are unsatisfiable.
hint: Packages were unavailable because the network was disabled.
```

A green suite that is green only because of the developer's cache is not a result. So the runner
is committed, `tests/conftest.py` points every `uv` invocation in the session at this directory
via `UV_FIND_LINKS`, and `tests/test_runner_wheelhouse.py` reproduces the cold-cache condition
inside the suite — an empty `UV_CACHE_DIR`, with a control that shows the same install failing
without this directory. That test is the reason the failure cannot come back silently.

## What is here, and why each file

Eight pure-Python wheels (`py3-none-any`), no compiled anything:

| File | Why |
|---|---|
| `pytest-9.1.1-py3-none-any.whl` | the runner |
| `iniconfig-*.whl`, `packaging-*.whl`, `pluggy-*.whl`, `pygments-*.whl` | required by `pytest` on every supported Python |
| `exceptiongroup-*.whl`, `tomli-*.whl`, `typing_extensions-*.whl` | required by `pytest` on Python 3.10 only, which this package still supports (`requires-python = ">=3.10"`) |

The `pytest` version is the one this project's own `uv.lock` pins, and
`tests/test_runner_wheelhouse.py` asserts that equality. That is deliberate: a fixture venv
running a pytest two releases behind the one the suite runs under would be exercising the
reward's report parsing against a runner nobody ships, and the drift would be invisible.

## Refreshing it

After a `pytest` bump in `uv.lock`, the version assertion fails by name. Rebuild from PyPI:

```bash
# from the repository root, with the network available — this is a maintenance step, never
# something a test does
uv run python - <<'PY'
import json, pathlib, urllib.request
out = pathlib.Path("tests/fixtures/wheelhouse")
for old in out.glob("*.whl"):
    old.unlink()
# the version pytest resolves to here must match uv.lock; the rest follow from its metadata
for name, version in [
    ("pytest", "9.1.1"),
    ("iniconfig", "2.3.0"),
    ("packaging", "26.2"),
    ("pluggy", "1.6.0"),
    ("pygments", "2.20.0"),
    ("exceptiongroup", "1.3.1"),
    ("tomli", "2.4.1"),
    ("typing_extensions", "4.16.0"),
]:
    data = json.load(urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json"))
    wheel = next(u for u in data["urls"] if u["filename"].endswith("-py3-none-any.whl"))
    (out / wheel["filename"]).write_bytes(urllib.request.urlopen(wheel["url"]).read())
PY
```

Only pure-Python wheels belong here. A wheel with a platform tag would make this directory a
statement about one machine, and the suite would then be provisionable on that machine alone.
