"""Tests for the task-format machinery that stands between the corpus and the loop.

A package rather than a bare directory, matching `tests/loop/` and `tests/bakeoff/`, because
the suite runs under pytest's prepend import mode: with an `__init__.py` here these modules
are imported as `tasks.test_*` with `tests/` on `sys.path`, which is what lets them import
the guard modules that live one directory up and the shared fixtures (`fixtures.repos`).

Everything here runs with **no `mlx` installed** — CI's actual state — and offline: the
apply-step machinery reads git only through the doors it drives, never through a model.
"""