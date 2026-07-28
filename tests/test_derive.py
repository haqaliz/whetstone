"""Turning a candidate commit into the node ids a task declares, by running it three times.

`fail_to_pass` is not something a commit states; it is something a commit *does*, and the only
way to know it is to run the tests at the parent with the child's test files in place, run them
again with the fix applied, and diff the outcomes. Everything asserted here is about that diff
being honest:

- the ids are minted through `strict.py`'s own `read_report`/`node_id`, never hand-built, so the
  set the miner writes and the set the reward compares are produced by one implementation;
- a **parametrised** id survives whole, because `strict.py:321-348` compares by exact set
  equality plus a count and a bare `test_x` in place of `test_x[1-2]` is a task that can never
  pass;
- an id whose outcome is not reproducible is **discarded**, because a task built on it has a
  verdict decided by a coin toss;
- a candidate with nothing that flips is refused rather than minted empty.

Three sandboxed pytest runs per candidate, on a synthetic donor. Offline throughout.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest
from fixtures.repos.donor import build_donor

from whetstone.tasks.derive import Derived, NotDerivable, derive, gold_patch
from whetstone.tasks.donor import Candidate, candidates

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin",
    reason="the derivation runs its pytest inside the Seatbelt sandbox, which is macOS-only",
)

#: Generous: three pytest runs on a four-file suite, and a ceiling rather than an expectation.
_TIMEOUT = 120.0


@pytest.fixture(scope="module")
def donor(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_donor(tmp_path_factory.mktemp("donor-derive"))


def _candidate(donor: Path, subject: str) -> Candidate:
    found = {candidate.subject: candidate for candidate in candidates(donor)}
    assert subject in found, f"the donor no longer yields {subject!r}, so this test proves nothing"
    return found[subject]


@pytest.fixture(scope="module")
def addition(donor: Path, tmp_path_factory: pytest.TempPathFactory) -> Derived:
    """The plainly mintable candidate, derived once and asserted on from several angles."""
    return derive(
        donor,
        _candidate(donor, "Fix addition"),
        scratch=tmp_path_factory.mktemp("derive-addition"),
        timeout=_TIMEOUT,
    )


def test_a_candidate_yields_exactly_the_ids_that_flipped(addition: Derived) -> None:
    """`fail_to_pass` is failed→passed; `pass_to_pass` is passed in both. Nothing else is either."""
    assert addition.fail_to_pass == (
        "tests/test_addition.py::test_add_is_addition",
        "tests/test_addition.py::test_add_table[1-2-3]",
        "tests/test_addition.py::test_add_table[3-4-7]",
    )
    assert addition.pass_to_pass == (
        "tests/test_addition.py::test_adding_zero_is_the_identity",
    )
    assert addition.discarded == ()


def test_a_parametrised_test_yields_a_fully_parametrised_id(addition: Derived) -> None:
    """The bare id must not appear, and the case ids must.

    `strict.py:321-348` compares the executed set against the declared one by exact set equality
    plus a count. A task declaring `test_add_table` would see two ids run that it never declared
    and one declared id never run — a FAIL on every patch, correct or not, with nothing about the
    task to explain it. This is why the ids are minted through the verifier's own reader rather
    than through `--collect-only` or a second implementation.
    """
    assert "tests/test_addition.py::test_add_table" not in addition.fail_to_pass
    assert "tests/test_addition.py::test_add_table" not in addition.pass_to_pass
    assert sum("test_add_table[" in node_id for node_id in addition.fail_to_pass) == 2


def test_a_flaky_id_is_discarded_rather_than_recorded(
    donor: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """The repeat run, and the reason there is one.

    `test_parity_is_stable` fails, passes, then fails again across successive runs in the same
    tree. Seen twice it looks exactly like a genuine fix — failed at the parent, passed after the
    patch — and a task built on it would pay reward for a coin toss and would tell whoever read
    the report that the model had got better. The third run is what tells the two apart.

    The genuine `fail_to_pass` in the same file survives, so this is the flake being singled out
    rather than the candidate being thrown away.
    """
    derived = derive(
        donor,
        _candidate(donor, "Fix parity"),
        scratch=tmp_path_factory.mktemp("derive-parity"),
        timeout=_TIMEOUT,
    )

    assert derived.discarded == ("tests/test_parity.py::test_parity_is_stable",)
    assert derived.fail_to_pass == ("tests/test_parity.py::test_zero_is_even",)
    assert "tests/test_parity.py::test_parity_is_stable" not in derived.pass_to_pass


def test_a_candidate_with_nothing_that_flips_is_refused(
    donor: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Selected by the commit filter, and still not a task.

    "Tidy the edge tests" modifies a test file and a source file, so it passes selection, and its
    new test passes on both sides of its own commit. An empty `fail_to_pass` is a task that
    rewards a patch which changed nothing — `load_task` refuses one too — so it is refused here,
    before three suite runs' worth of evidence is thrown away silently.
    """
    with pytest.raises(NotDerivable) as refusal:
        derive(
            donor,
            _candidate(donor, "Tidy the edge tests"),
            scratch=tmp_path_factory.mktemp("derive-tidy"),
            timeout=_TIMEOUT,
        )

    assert "fail_to_pass" in str(refusal.value)


def test_an_unresolved_scratch_path_still_yields_repository_relative_ids(
    donor: Path, tmp_path: Path
) -> None:
    """A symlinked scratch directory must not change a single node id.

    Found by running it, not by reading it. macOS hands out `/var/...` paths that resolve to
    `/private/var/...`; pytest resolves the test file and then reports it relative to an
    unresolved `--rootdir`, producing an eighty-character `../../../..` path from which
    `node_id` can reconstruct nothing. Every derivation against an unresolved scratch directory
    failed with "the reported classname does not sit under the reported file" — which reads like
    a corrupt report and is really a symlink, and which would have surfaced on somebody's machine
    rather than in the suite.
    """
    (tmp_path / "real").mkdir()
    linked = tmp_path / "link"
    linked.symlink_to(tmp_path / "real", target_is_directory=True)

    derived = derive(
        donor, _candidate(donor, "Fix addition"), scratch=linked, timeout=_TIMEOUT
    )

    assert derived.fail_to_pass[0] == "tests/test_addition.py::test_add_is_addition"


def test_the_gold_patch_is_the_commit_without_its_test_files(donor: Path) -> None:
    """The test patch is the restore, so the gold patch must not carry the test files.

    A gold patch that included the child's test file would be applying the test patch a second
    time — and, worse, would make the reference patch touch a held path, which STRICT refuses
    outright before anything runs.
    """
    candidate = _candidate(donor, "Fix addition")

    patch = gold_patch(donor, candidate)

    assert "calc.py" in patch
    assert "README.md" in patch
    assert "tests/test_addition.py" not in patch


def test_the_ids_are_minted_through_the_verifiers_own_reader() -> None:
    """M4, asserted structurally rather than trusted.

    Ids minted by a second implementation drift in exactly the ways `node_id` exists to prevent —
    where a module path ends and a class begins, whether a `[1-2]` suffix survives — and the
    drift does not present as a bug in the miner. It presents as every ingested task failing the
    executed-set check with nothing about the task to explain it.

    So: the module must import the reader from `whetstone.verify.strict`, and no string it
    *executes* may contain `::` (the only way to hand-build a node id) or `collect-only` (the
    other route to a set of ids, and one that reports what pytest **would** run rather than what
    it did).

    Docstrings are excluded from the census and comments never enter the AST at all, which is the
    same line `test_no_inference_on_reward_path.py` draws: prose may discuss a thing the code may
    not do, and a guard that cannot tell the two apart is one that gets satisfied by rewording.
    """
    source = (Path(__file__).resolve().parent.parent / "src/whetstone/tasks/derive.py").read_text()
    tree = ast.parse(source)

    imported = {
        (node.module, alias.name)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert ("whetstone.verify.strict", "read_report") in imported

    documented = {
        node.body[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    executed = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node not in documented
    ]
    assert executed, "the census found no executable string at all, so it proves nothing"
    assert not [text for text in executed if "::" in text]
    assert not [text for text in executed if "collect-only" in text]
