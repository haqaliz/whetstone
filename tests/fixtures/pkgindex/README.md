# `tests/fixtures/pkgindex` — a recorded package index, for one test

**Not to be confused with `tests/fixtures/wheelhouse`.** This directory holds the versions
**under study**; that one holds `pytest`, which is how any declared test gets executed at all.
The two are separate directories, resolved by separate commands, and
`tests/test_runner_wheelhouse.py` asserts they share no distribution — a subject that could also
be answered from the scaffolding would make the test below prove nothing.

**Nothing in here is a dependency of Whetstone.** `whetstone-fixture-dep` is not on PyPI, is
never installed into this project's environment, and does nothing. It exists so that
`tests/test_environment_pins.py` can prove one claim: **`Task.environment.pins` decides the
verdict.**

## Why the wheels are committed

That test resolves a dependency twice — once with the task's exact pin, once unbounded — and
shows the same task and the same patch reaching *different verdicts*. To mean anything, the
two resolutions have to be reproducible on any machine on any day.

A test that reached PyPI to prove that would be **self-refuting**: its result would depend on
what an index served that morning, which is the exact failure `environment` exists to close
(see `src/whetstone/verify/task.py`'s module docstring, and the `pallets__flask-5063`
incident behind it). So the index is local, committed, and resolved against with
`uv pip install --offline --no-index --find-links <this directory>`. The bytes below are the
record; nothing is fetched.

Two wheels, ~1.5 KB each, pure Python, no compiled anything:

| File | What it is |
|---|---|
| `whetstone_fixture_dep-1.0.0-py3-none-any.whl` | `greet(name, *, loud=False)` |
| `whetstone_fixture_dep-2.0.0-py3-none-any.whl` | `greet(name)` — `loud` **removed** |

The removed keyword is a miniature of the real incident: click 8.2 removed
`CliRunner(mix_stderr=)`, flask declared `click>=8.0` with no upper bound, and four of that
task's `pass_to_pass` tests failed for a patch that was correct. A **false FAIL**, produced by
the calendar rather than by the code.

2.0.0 is the higher version, so an **unbounded** requirement resolves to it — which is what
makes "no pin" and "pinned to 1.0.0" land on different code, and therefore on different
verdicts. The break is at *call* time (`TypeError`), never at import time, so the declared
tests genuinely run and genuinely fail; a package that would not import would fail collection
instead, which is a different and far more obvious outcome, and would not demonstrate the hole.

## How they were built

`sources/1.0.0/` and `sources/2.0.0/` are the complete inputs — a `pyproject.toml` and a
single module each. They are committed so the artefacts are auditable and regenerable rather
than opaque:

```bash
# from the repository root; --out-dir is a scratch path on purpose (see below)
uv build --wheel --out-dir /tmp/pkgindex tests/fixtures/pkgindex/sources/1.0.0
uv build --wheel --out-dir /tmp/pkgindex tests/fixtures/pkgindex/sources/2.0.0
cp /tmp/pkgindex/*.whl tests/fixtures/pkgindex/
```

**Build to a scratch directory and copy the wheels in**, never straight into this one: `uv
build` writes a `.gitignore` containing `*` beside its output, which would silently un-commit
the very artefacts the test needs on a fresh checkout.

## If you are here because a test failed

`tests/test_environment_pins.py` asserts the contents of this directory before it asserts
anything about a verdict — that both versions are present, that 1.0.0 accepts `loud=` and
2.0.0 refuses it, and that the unbounded resolution really selected 2.0.0. If one of those
fired, the index is wrong, not the verifier. Rebuild it with the commands above.
