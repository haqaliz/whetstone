"""The adversarial cheat corpus: the evidence that the differential is real.

Everything under `src/whetstone/verify/` is machinery. This package is the argument.
`test_cheats.py` attacks the reward with patches a policy could plausibly emit, and asserts
what **both** verifiers did with each — because "STRICT rejected it" on its own is compatible
with STRICT being broken, and only "WEAK accepted the same patch" shows the difference was the
strictness.

**Not everything here is a cheat, and `test_inert_checkout.py` is the reason the distinction
is drawn.** A reward can be corrupted with nobody attacking it: if the code the tests import
is not the checkout the patch was applied to, the verdict is decided outside the run and an
empty submission is paid. No adversary authors that, so it is not in `CHEATS` and has no
differential to report — but it is a reward-integrity property, which is what this package is
for, so it lives here rather than among the unit tests.

Nothing here is a fixture of the outer suite: no repository is checked in, and every attack is
a string materialised into `tmp_path` at test time (see `tests/fixtures/repos`).
"""
