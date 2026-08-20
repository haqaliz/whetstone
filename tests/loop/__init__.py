"""Tests for the nightly improvement loop: the first code in this tree that produces training data.

A package rather than a bare directory, matching `tests/bakeoff/` and `tests/adversarial/`,
because the suite runs under pytest's prepend import mode: with an `__init__.py` here these
modules are imported as `loop.test_*` with `tests/` on `sys.path`, which is what lets them reach
the shared fixtures (`fixtures.repos`) and the guard modules one directory up.

Everything here runs with **no `mlx` installed** — CI's actual state (`.github/workflows/ci.yml`
runs the suite under a plain `uv sync`, which does not install the extra). The seeding, the
sampling wrapper, the selection, the ledger and the checkpoint are all exercised through injected
seams (`Seeder`, `Engine`, `Trainer`), which is exactly why those seams exist. The one test that
needs a real engine — the adapter round-trip — skips loudly, naming what is missing.
"""
