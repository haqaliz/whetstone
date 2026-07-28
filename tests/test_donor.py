"""Which commits in a local repository could become tasks — and, mostly, which could not.

Source B mints a task from a commit that turned a failing test green. The selection rule is
four words long and every word of it is load-bearing, so each rule below is proved by a commit
in ``fixtures.repos.donor`` that is excluded for that reason and no other. The merge is the
sharpest of them: it modifies a test file and a source file, so it passes the content filter
outright, and the commit it merges IS selected — the only thing that separates them is the
merge rule.

The donor is synthetic, built by real git, and offline. Nothing here reaches the network, and
nothing here runs the donor's tests; that is `test_derive.py`'s job.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fixtures.repos.donor import build_donor, commit_shas

from whetstone.tasks.donor import Candidate, GitFailed, candidates, is_test_path


@pytest.fixture(scope="module")
def donor(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One donor for the module: building it is ~10 git invocations and nothing mutates it."""
    return build_donor(tmp_path_factory.mktemp("donor-history"))


def _by_subject(found: tuple[Candidate, ...]) -> dict[str, Candidate]:
    return {candidate.subject: candidate for candidate in found}


def test_a_commit_that_modifies_a_test_and_a_source_file_is_a_candidate(donor: Path) -> None:
    """The shape source B exists to find, and every field it has to carry to be mintable."""
    candidate = _by_subject(candidates(donor))["Fix addition"]

    assert candidate.held_tests == ("tests/test_addition.py",)
    assert candidate.source_paths == ("calc.py",)
    # The non-`.py` half of the same commit. It is not held and it is not a source file, and it
    # still belongs to the gold patch — which is exactly the cheat-10 residual the plan records
    # rather than closes.
    assert candidate.other_paths == ("README.md",)
    assert candidate.sha == commit_shas(donor)["Fix addition"]
    # `base_commit` is the PARENT. The child's test file is restored over it, and that restore
    # is the test patch.
    assert candidate.parent == commit_shas(donor)["Seed the calculator"]


def test_a_commit_that_only_adds_a_test_file_is_excluded(donor: Path) -> None:
    """PRD D2. `strict.py:151-160` refuses a task whose held paths are absent at `base_commit`.

    An added test file does not exist at the parent, so a task minted from this commit would be
    UNVERIFIED forever. Relaxing that guard is deliberately out of scope for this slice, so the
    commit is excluded at selection instead.
    """
    excluded = "Add a multiplication test"
    assert excluded not in _by_subject(candidates(donor))
    # And not because the commit is otherwise unremarkable: it does modify a source file.
    assert excluded in commit_shas(donor)


def test_a_merge_is_excluded_although_its_content_would_qualify(donor: Path) -> None:
    """The one exclusion that cannot be confused with the content filter.

    The merge carries the side-branch commit's modified test file and modified source file
    wholesale. If the merge rule were dropped, this commit would be selected — and the task
    minted from it would have a two-parent `base_commit`, which is not a state any checkout
    reproduces. The side-branch commit itself IS selected, and that is what makes this
    assertion about merges rather than about content.
    """
    found = _by_subject(candidates(donor))
    assert "Merge the sidecar" not in found
    assert "Fix division on the sidecar" in found
    assert found["Fix division on the sidecar"].held_tests == ("tests/test_division.py",)


def test_a_documentation_only_commit_is_excluded(donor: Path) -> None:
    """No `.py` at all: nothing to hold, nothing to fix."""
    assert "Document the calculator" not in _by_subject(candidates(donor))


def test_a_source_only_commit_is_excluded(donor: Path) -> None:
    """A fix with no test movement behind it. There is no `fail_to_pass` to derive."""
    assert "Add a doubling helper" not in _by_subject(candidates(donor))


def test_the_root_commit_is_excluded(donor: Path) -> None:
    """It has no parent, so it has no `base_commit` — before any content rule applies."""
    assert "Seed the calculator" not in _by_subject(candidates(donor))


def test_candidates_are_returned_in_history_order(donor: Path) -> None:
    """Oldest first, deterministically: a corpus whose order is `readdir`'s is one nobody diffs."""
    subjects = [candidate.subject for candidate in candidates(donor)]
    assert subjects == [
        "Fix addition",
        "Fix division on the sidecar",
        "Fix subtraction and relax the conftest",
        "Fix parity",
        "Fix rounding and add a unit conftest",
    ]


def test_a_path_that_is_not_a_repository_fails_by_name(tmp_path: Path) -> None:
    """git's own complaint, raised rather than swallowed into an empty candidate list.

    An empty tuple would be the same lie an empty task directory is: "no commits are mintable"
    and "you pointed me at the wrong directory" are different facts, and only the first is a
    finding about the donor.
    """
    with pytest.raises(GitFailed) as failure:
        candidates(tmp_path)
    assert "repository" in str(failure.value)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("tests/test_addition.py", True),
        ("test_addition.py", True),
        ("addition_test.py", True),
        ("tests/conftest.py", True),
        ("src/pkg/tests/helpers.py", True),
        ("test/test_x.py", True),
        ("conftest.py", False),
        ("calc.py", False),
        ("testing/util.py", False),
        ("src/contest.py", False),
        ("tests/data/fixture.json", False),
        ("README.md", False),
    ],
)
def test_the_test_file_predicate_classifies_by_name_and_position(path: str, expected: bool) -> None:
    """The judgement call the whole miner rests on, written out as a table.

    `conftest.py` at the ROOT is deliberately not a test file: it is a source file the gold
    patch may touch, and treating it as a test would silently move it from the gold patch into
    the held set — where `strict.py`'s restore would overwrite the very fix being verified.
    Under `tests/` it is a test file, because there the commit that modifies it is modifying
    the operator's own test scaffolding.
    """
    assert is_test_path(path) is expected
