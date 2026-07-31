"""Tests for the bake-off harness: the first code in this tree that will consult a model.

A package rather than a bare directory, matching `tests/adversarial/`, because the suite runs
under pytest's prepend import mode: with an `__init__.py` here these modules are imported as
`bakeoff.test_*` with `tests/` on `sys.path`, which is what lets them import the guard modules
that live one directory up (`test_no_inference_on_reward_path`) the way
`tests/test_reward_path_scope_is_partitioned.py` already does.

Everything here runs with **no `mlx` installed** — that is CI's actual state
(`.github/workflows/ci.yml:32` runs `uv run pytest` under a plain `uv sync`, which does not
install the `mlx` extra), so it is the state these tests are written against rather than an
environment someone has to remember to reproduce.
"""
