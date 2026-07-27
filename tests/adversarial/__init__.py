"""The adversarial cheat corpus: the evidence that the differential is real.

Everything under `src/whetstone/verify/` is machinery. This package is the argument. Each
module here attacks the reward with a patch a policy could plausibly emit, and asserts what
**both** verifiers did with it — because "STRICT rejected it" on its own is compatible with
STRICT being broken, and only "WEAK accepted the same patch" shows the difference was the
strictness.

Nothing here is a fixture of the outer suite: no repository is checked in, every attack is a
string materialised into `tmp_path` at test time (see `tests/fixtures/repos`), and no file
under this package other than `test_cheats.py` is collected.
"""
