"""A synthetic DONOR: a multi-commit repository the source-B miner is pointed at.

``__init__`` builds one-commit repositories, because the verifier only ever needs a
``base_commit`` to check out. The miner needs the opposite: a *history*, where some commits are
mintable and most are not, so that "this commit was selected" and "this commit was excluded"
are both observable facts rather than assertions about a filter nobody ran.

**Every exclusion below is a different rule.** The history is written so that no commit is
excluded for two reasons at once — otherwise a filter with a broken half would stay green. The
merge in particular carries a modified test *and* a modified source file, so it would be
selected on content alone; it is excluded only because it is a merge, and the side-branch commit
it merges IS selected, which is what proves that.

**Determinism.** ``_git`` pins identity and dates, so this repository has the same SHAs on every
machine and every run. Tests therefore name commits by SHA looked up through ``commit_shas``
rather than by hardcoded hash — the hashes are stable, but a hardcoded one records nothing about
*which* commit is meant.

Nothing here is collected by the outer suite: the sources are strings, materialised into
``tmp_path`` at test time.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from fixtures.repos import _git

#: The root ``conftest.py``. It is on the path from the repository root to every held test, so
#: it is what the cheat-10 structural floor has to hold; and it is load-bearing rather than
#: decorative — ``expected_sum`` is the value the addition test asserts against, so a policy that
#: could edit this file could make that test pass without touching ``calc.py``. That is cheat 10
#: in one file.
DONOR_CONFTEST = """\
import pytest


@pytest.fixture
def expected_sum():
    return 5
"""

#: A second conftest, one level down, so the floor has a *path* to walk rather than a single
#: root file. It is load-bearing too: ``expected_quotient`` is what the division test asserts
#: against.
DONOR_TESTS_CONFTEST = """\
import pytest


@pytest.fixture
def expected_quotient():
    return 2
"""

#: A conftest that is NOT on the path to any held test. A floor implemented as "every
#: ``conftest.py`` in the repository" would hold this one, and holding a file the task has no
#: relationship to is not free: it is one more path the policy may not touch and one more blob
#: the manifest carries, both justified by nothing.
DONOR_UNRELATED_CONFTEST = """\
import pytest


@pytest.fixture
def unrelated():
    return object()
"""

#: A conftest that exists at the CHILD and not at the parent — added by the same commit that
#: modifies the test below it. The floor is read at the parent, so this must not be held: a held
#: path absent from the checkout is exactly what ``strict.py:151-160`` answers UNVERIFIED for,
#: and a task that is UNVERIFIED forever is worse than one that was never minted.
DONOR_UNIT_CONFTEST = """\
import pytest


@pytest.fixture
def not_yet_used():
    return None
"""

#: The same file after the commit that (wrongly, for a miner) touches it: see
#: ``Fix subtraction and relax the conftest``, the over-declaration candidate.
DONOR_CONFTEST_TOUCHED = """\
import pytest


@pytest.fixture
def expected_sum():
    return 5


@pytest.fixture
def expected_difference():
    return 1
"""

#: The source module, respecified in full at every commit that changes it. Full contents rather
#: than diffs because git computes the diff — a fixture that carried hand-written hunks would be
#: asserting about its own patch format instead of about the miner.
DONOR_CALC_SEED = """\
def add(a, b):
    return a - b


def divide(a, b):
    return a * b


def subtract(a, b):
    return a + b


def is_even(n):
    return n % 2 == 1


def round_half(n):
    return int(n)
"""

DONOR_CALC_ADD_FIXED = DONOR_CALC_SEED.replace(
    "def add(a, b):\n    return a - b", "def add(a, b):\n    return a + b"
)

DONOR_CALC_WITH_MULTIPLY = DONOR_CALC_ADD_FIXED + """

def multiply(a, b):
    return a * b
"""

DONOR_CALC_WITH_DOUBLE = DONOR_CALC_WITH_MULTIPLY + """

def double(n):
    return multiply(n, 2)
"""

DONOR_CALC_DIVIDE_FIXED = DONOR_CALC_WITH_DOUBLE.replace(
    "def divide(a, b):\n    return a * b", "def divide(a, b):\n    return a / b"
)

DONOR_CALC_SUBTRACT_FIXED = DONOR_CALC_DIVIDE_FIXED.replace(
    "def subtract(a, b):\n    return a + b", "def subtract(a, b):\n    return a - b"
)

DONOR_CALC_PARITY_FIXED = DONOR_CALC_SUBTRACT_FIXED.replace(
    "def is_even(n):\n    return n % 2 == 1", "def is_even(n):\n    return n % 2 == 0"
)

DONOR_CALC_ROUNDING_FIXED = DONOR_CALC_PARITY_FIXED.replace(
    "def round_half(n):\n    return int(n)", "def round_half(n):\n    return int(n + 0.5)"
)

_ADDITION_SEED = """\
from calc import add


def test_adding_zero_is_the_identity():
    assert add(4, 0) == 4
"""

#: The child's version of the held test file for the one plainly mintable candidate. Three of
#: its four tests fail at the parent and pass after the fix; the fourth passes in both. Two of
#: the three are **parametrised**, because ``strict.py`` compares node ids by exact set equality
#: — a miner that minted the bare ``test_add_table`` would produce a task that can never pass,
#: and nothing about the task would say why.
_ADDITION_FIXED = """\
import pytest

from calc import add


def test_adding_zero_is_the_identity():
    assert add(4, 0) == 4


def test_add_is_addition(expected_sum):
    assert add(2, 3) == expected_sum


@pytest.mark.parametrize(("a", "b", "expected"), [(1, 2, 3), (3, 4, 7)])
def test_add_table(a, b, expected):
    assert add(a, b) == expected
"""

_DIVISION_SEED = """\
from calc import divide


def test_dividing_by_one_is_the_identity():
    assert divide(4, 1) == 4
"""

_DIVISION_FIXED = """\
from calc import divide


def test_dividing_by_one_is_the_identity():
    assert divide(4, 1) == 4


def test_division_halves(expected_quotient):
    assert divide(4, 2) == expected_quotient
"""

_EDGE_SEED = """\
from calc import round_half


def test_rounding_down_stays_down():
    assert round_half(1.2) == 1
"""

_EDGE_FIXED = """\
from calc import round_half


def test_rounding_down_stays_down():
    assert round_half(1.2) == 1


def test_rounding_up_rounds_up():
    assert round_half(1.6) == 2
"""

_SUBTRACTION_SEED = """\
from calc import subtract


def test_subtracting_zero_is_the_identity():
    assert subtract(4, 0) == 4
"""

_SUBTRACTION_FIXED = """\
from calc import subtract


def test_subtracting_zero_is_the_identity():
    assert subtract(4, 0) == 4


def test_subtraction_subtracts(expected_difference):
    assert subtract(4, 3) == expected_difference
"""

_PARITY_SEED = """\
from calc import is_even


def test_one_is_not_even():
    assert not is_even(2)
"""

#: The child's version of the parity test file, and the second test in it is **deliberately
#: flaky**: it fails, passes, fails, passes across successive runs in the same tree. The
#: derivation sees it flip ``failed``→``passed`` and would record it as a ``fail_to_pass`` — a
#: task whose verdict is a coin toss — unless the repeat run catches it. The counter is a file
#: next to the test because it has to survive across pytest processes, and it lands inside the
#: sandbox's write scope.
_PARITY_FIXED = """\
from pathlib import Path

from calc import is_even


def test_zero_is_even():
    assert is_even(0)


def test_parity_is_stable():
    marker = Path(__file__).with_name("parity-runs.txt")
    previous = marker.read_text() if marker.exists() else ""
    marker.write_text(previous + "x\\n")
    assert len(previous.split()) % 2 == 1
"""

_MULTIPLICATION_ADDED = """\
from calc import multiply


def test_multiplication_multiplies():
    assert multiply(2, 3) == 6
"""

_README_SEED = "# donor\n\nA calculator with four bugs in it.\n"
_README_ADDITION = _README_SEED + "\n- addition adds again\n"
_README_DOCUMENTED = _README_ADDITION + "\nUsage: `from calc import add`.\n"


@dataclass(frozen=True)
class DonorCommit:
    """One commit in the donor's history.

    ``changes`` maps a repository-relative path to its full new contents, or to ``None`` to
    delete it. ``branch`` cuts a side branch from the current HEAD, commits there, and returns
    to ``main``; ``merge`` merges a named branch back with ``--no-ff``, which is the only way to
    get a real merge commit out of a trivially-ahead branch.
    """

    subject: str
    changes: Mapping[str, str | None] = field(default_factory=dict)
    branch: str | None = None
    merge: str | None = None


#: The history, and what each commit is here to prove. Read this table before changing it: every
#: entry is the sole evidence for one rule in ``whetstone.tasks.donor.candidates``.
#:
#: | Commit | Miner's answer | Why |
#: |---|---|---|
#: | Seed the calculator | excluded | the root commit has no parent, so no `base_commit` |
#: | Fix addition | **selected** | modifies a test file and a source file |
#: | Document the calculator | excluded | touches no `.py` at all |
#: | Add a multiplication test | excluded | the test file is ADDED, not modified (PRD D2) |
#: | Add a doubling helper | excluded | touches no test file |
#: | Fix division on the sidecar | **selected** | an ordinary commit that sits on a branch |
#: | Merge the sidecar | excluded | it is a merge — its content would otherwise qualify |
#: | Fix subtraction and relax the conftest | **rejected in Phase 2** | its gold patch
#:   touches the root `conftest.py`, which the conftest floor would hold |
#: | Fix parity | **selected** | modifies a test file and a source file; its test is flaky |
#: | Fix rounding and add a unit conftest | **selected** | its added `tests/unit/conftest.py`
#:   is absent from the parent, so the floor must not hold it |
DONOR_HISTORY: tuple[DonorCommit, ...] = (
    DonorCommit(
        subject="Seed the calculator",
        changes={
            "README.md": _README_SEED,
            "calc.py": DONOR_CALC_SEED,
            "conftest.py": DONOR_CONFTEST,
            "tests/conftest.py": DONOR_TESTS_CONFTEST,
            "other/conftest.py": DONOR_UNRELATED_CONFTEST,
            "tests/test_addition.py": _ADDITION_SEED,
            "tests/test_division.py": _DIVISION_SEED,
            "tests/test_subtraction.py": _SUBTRACTION_SEED,
            "tests/test_parity.py": _PARITY_SEED,
            "tests/unit/test_edge.py": _EDGE_SEED,
        },
    ),
    DonorCommit(
        subject="Fix addition",
        changes={
            "calc.py": DONOR_CALC_ADD_FIXED,
            "tests/test_addition.py": _ADDITION_FIXED,
            # A non-`.py` file in the same commit, because real red→green commits carry them:
            # it is what `other_paths` records, and it goes into the gold patch.
            "README.md": _README_ADDITION,
        },
    ),
    DonorCommit(
        subject="Document the calculator",
        changes={"README.md": _README_DOCUMENTED},
    ),
    DonorCommit(
        subject="Add a multiplication test",
        changes={
            "calc.py": DONOR_CALC_WITH_MULTIPLY,
            "tests/test_multiplication.py": _MULTIPLICATION_ADDED,
        },
    ),
    DonorCommit(
        subject="Add a doubling helper",
        changes={"calc.py": DONOR_CALC_WITH_DOUBLE},
    ),
    DonorCommit(
        subject="Fix division on the sidecar",
        branch="sidecar",
        changes={
            "calc.py": DONOR_CALC_DIVIDE_FIXED,
            "tests/test_division.py": _DIVISION_FIXED,
        },
    ),
    DonorCommit(subject="Merge the sidecar", merge="sidecar"),
    DonorCommit(
        subject="Fix subtraction and relax the conftest",
        changes={
            "calc.py": DONOR_CALC_SUBTRACT_FIXED,
            "conftest.py": DONOR_CONFTEST_TOUCHED,
            "tests/test_subtraction.py": _SUBTRACTION_FIXED,
        },
    ),
    DonorCommit(
        subject="Fix parity",
        changes={
            "calc.py": DONOR_CALC_PARITY_FIXED,
            "tests/test_parity.py": _PARITY_FIXED,
        },
    ),
    DonorCommit(
        subject="Fix rounding and add a unit conftest",
        changes={
            "calc.py": DONOR_CALC_ROUNDING_FIXED,
            "tests/unit/test_edge.py": _EDGE_FIXED,
            # ADDED by this commit, so it is not in the parent's tree. The floor is read at the
            # parent; a floor read at the child would hold this and mint a task STRICT can only
            # ever call UNVERIFIED.
            "tests/unit/conftest.py": DONOR_UNIT_CONFTEST,
        },
    ),
)


def build_donor(
    root: Path,
    commits: Sequence[DonorCommit] = DONOR_HISTORY,
    *,
    name: str = "donor",
) -> Path:
    """Materialise a donor repository under ``root`` and return its path."""
    donor = Path(root) / name
    donor.mkdir(parents=True)
    _git(["init", "--quiet", "--initial-branch=main"], cwd=donor)

    for commit in commits:
        if commit.merge is not None:
            _git(
                ["merge", "--quiet", "--no-ff", "--message", commit.subject, commit.merge],
                cwd=donor,
            )
            continue
        if commit.branch is not None:
            _git(["checkout", "--quiet", "-b", commit.branch], cwd=donor)
        for relative, contents in commit.changes.items():
            target = donor / relative
            if contents is None:
                target.unlink()
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(contents)
        _git(["add", "--all"], cwd=donor)
        _git(["commit", "--quiet", "--message", commit.subject], cwd=donor)
        if commit.branch is not None:
            _git(["checkout", "--quiet", "main"], cwd=donor)
    return donor


def commit_shas(donor: Path) -> dict[str, str]:
    """Subject -> SHA, over the whole history including merges and side branches.

    Tests name commits by subject: a hardcoded hash would be stable (the identity and dates are
    pinned) and would say nothing about which commit was meant.
    """
    raw = _git(["log", "--all", "--format=%H %s"], cwd=Path(donor))
    shas: dict[str, str] = {}
    for line in raw.splitlines():
        sha, _, subject = line.partition(" ")
        shas[subject] = sha
    return shas


__all__ = [
    "DONOR_CALC_ADD_FIXED",
    "DONOR_CALC_PARITY_FIXED",
    "DONOR_CALC_ROUNDING_FIXED",
    "DONOR_CALC_SEED",
    "DONOR_CONFTEST",
    "DONOR_CONFTEST_TOUCHED",
    "DONOR_HISTORY",
    "DONOR_TESTS_CONFTEST",
    "DONOR_UNIT_CONFTEST",
    "DONOR_UNRELATED_CONFTEST",
    "DonorCommit",
    "build_donor",
    "commit_shas",
]
