"""Which paths a minted task holds — and the two ways a held set gets that wrong.

The held set becomes `test_blobs`, which is the whole boundary: the paths a patch may not
touch, and the files restored from golden before the reward runs. Both failure directions are
real and neither is visible from the verdict:

- **Too few** is cheat 10. A held test that depends on a `conftest.py` the manifest never
  declared can be made to pass by rewriting that conftest, and the reward is paid on a bug
  nobody fixed. `tests/adversarial/test_cheats.py:426` proves both verifiers accept exactly
  that, and it stays a documented residual; the floor asserted here NARROWS it.
- **Too many** is worse, and it is the one that is easy to add by accident. If a held path is
  one the gold patch must change, `strict.py:180-183`'s restore silently writes golden bytes
  over the fix. The task is then permanently unpassable and reports as an ordinary **FAIL** —
  no `UNVERIFIED`, no diagnostic, nothing in the verdict that points at the manifest.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from adversarial.corpus import BOTH_ACCEPT, CHEATS
from fixtures.repos.donor import build_donor

from whetstone.tasks.donor import Candidate, candidates, run_git
from whetstone.tasks.held import OverDeclaration, UnderDeclaration, check_held, held_paths


@pytest.fixture(scope="module")
def donor(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_donor(tmp_path_factory.mktemp("donor-held"))


def _candidate(donor: Path, subject: str) -> Candidate:
    found = {candidate.subject: candidate for candidate in candidates(donor)}
    assert subject in found, f"the donor no longer yields {subject!r}, so this test proves nothing"
    return found[subject]


def test_the_held_set_is_the_modified_tests_plus_every_conftest_above_them(donor: Path) -> None:
    """PRD D4/M5: the structural floor, root-downwards, for each held test's directory."""
    candidate = _candidate(donor, "Fix addition")

    assert held_paths(donor, candidate) == (
        "conftest.py",
        "tests/conftest.py",
        "tests/test_addition.py",
    )


def test_a_conftest_beside_the_held_tests_rather_than_above_them_is_not_held(
    donor: Path,
) -> None:
    """The floor is a path, not a glob.

    `other/conftest.py` cannot affect a test under `tests/`, and holding it would forbid the
    policy a file the task has no relationship to while adding a blob the manifest carries for
    nothing. A floor implemented as "every conftest in the repository" passes the test above and
    fails this one.
    """
    held = held_paths(donor, _candidate(donor, "Fix addition"))

    assert "other/conftest.py" not in held
    # Anti-vacuity: the file has to exist, or its absence from the held set says nothing.
    assert "other/conftest.py" in run_git(
        ["ls-tree", "-r", "--name-only", _candidate(donor, "Fix addition").parent], cwd=donor
    )


def test_a_conftest_absent_from_the_parent_is_not_held(donor: Path) -> None:
    """The floor is read at the PARENT, because that is the tree STRICT checks out.

    This commit adds `tests/unit/conftest.py` alongside the test it modifies. Reading the floor
    at the child would hold a path that does not exist at `base_commit`, and
    `strict.py:151-160` answers UNVERIFIED for exactly that — a task that could never be
    verified by anyone, minted without a word of complaint.
    """
    candidate = _candidate(donor, "Fix rounding and add a unit conftest")

    held = held_paths(donor, candidate)

    assert held == ("conftest.py", "tests/conftest.py", "tests/unit/test_edge.py")
    assert "tests/unit/conftest.py" not in held
    # Anti-vacuity: it is genuinely there at the child, so its absence above is the parent rule
    # doing work rather than the file never having existed.
    assert "tests/unit/conftest.py" in run_git(
        ["ls-tree", "-r", "--name-only", candidate.sha], cwd=donor
    )


def test_a_candidate_whose_gold_patch_touches_a_held_conftest_is_rejected(donor: Path) -> None:
    """**The over-declaration guard.** The dangerous one, and the reason it is a rejection.

    This commit fixes `subtract` and, in the same commit, adds a fixture to the root
    `conftest.py`. The conftest is on the path to the held test, so the floor would hold it —
    and the conftest is also in the gold patch, so STRICT's restore would write the parent's
    version back over it, taking the new fixture out and leaving the held test to fail on a
    missing name. A permanently unpassable task, reported as an ordinary FAIL.

    So the candidate is refused at mint time, and the refusal names the path: a rejection that
    said only "this candidate is unsuitable" would send whoever reads it looking at the patch.
    """
    candidate = _candidate(donor, "Fix subtraction and relax the conftest")

    with pytest.raises(OverDeclaration) as refusal:
        held_paths(donor, candidate)

    message = str(refusal.value)
    assert "conftest.py" in message
    assert candidate.sha in message
    assert "restore" in message


def test_a_held_set_that_omits_a_conftest_on_the_path_is_rejected_by_the_floor_rule(
    donor: Path,
) -> None:
    """**The cheat-10 differential.** The rejecter has to be M5's rule, named.

    The same held set that `tests/adversarial/test_cheats.py:426` runs through both verifiers —
    a held test whose `conftest.py` is not declared — is accepted by STRICT and by WEAK, and the
    reward is paid on a conftest the policy rewrote. Ingestion is the only layer that can see
    the omission, because "which files does this test depend on" is not a question a set
    comparison can answer.

    The assertion names the rule so that a rejection arriving for some unrelated reason — a
    typo'd path, a missing file — cannot be read as a defence that is not there.
    """
    candidate = _candidate(donor, "Fix addition")

    with pytest.raises(UnderDeclaration) as refusal:
        check_held(("tests/test_addition.py",), donor=donor, candidate=candidate)

    message = str(refusal.value)
    assert "conftest.py" in message
    assert "tests/test_addition.py" in message
    assert "cheat 10" in message
    assert CHEATS[10].differential == BOTH_ACCEPT, (
        "cheat 10 is no longer recorded as accepted by both verifiers, so either the residual "
        "was closed — in which case say where — or the corpus stopped telling the truth"
    )


def test_a_held_set_that_carries_the_whole_floor_is_accepted(donor: Path) -> None:
    """The anti-vacuity control for the rejecter above: it does not refuse everything."""
    candidate = _candidate(donor, "Fix addition")

    check_held(held_paths(donor, candidate), donor=donor, candidate=candidate)
