"""The structural predicate: does this task's oracle fit the budget, without a checkout.

`oracle_sources` answers that question by materialising the repository and reading files out
of a checkout — a cost paid per task per candidate, and one the held-out derivation (aspect 2
of this unit) must not pay just to decide whether a task belongs in the draw. This file holds
the predicate that decides the same question on immutable git objects only: the path set at
the mined commit, and the blobs at `base_commit`.

The contract is the spec's AC1, AC4-AC8. Structural classes — a commit that touched no
non-test path, an operator-held collision, an oracle over the budget, nothing readable —
return `fits=False` carrying the bakeoff's own sentences, so the two records name the same
class. Machine state — an unreadable donor, a missing commit — raises, because an exclusion
from the held-out draw must never be caused by a transient condition. The budget is a
parameter defaulting to `ORACLE_BUDGET_CHARS`, and the reason a refusal leaves behind names
the budget actually enforced.

Two derivations of one task must agree byte for byte: the predicate is a pure function of the
manifest and git objects, with no checkout, no network and no clock.

The donors are the same two-commit synthetic repositories the sibling file builds
(`build_mined_task`), plus one hand-built shape for the nothing-readable class: a binary file
present at both commits and a source file the fix creates. Everything under test is a string
derived from those.
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from fixtures.repos import _git
from fixtures.repos.mined import (
    MINED_TESTS_AFTER,
    MINED_TESTS_BEFORE,
    _commit,
    build_mined_task,
)

from whetstone.bakeoff import sources as sources_module
from whetstone.bakeoff.sources import ORACLE_BUDGET_CHARS, oracle_fittable, oracle_sources
from whetstone.tasks.donor import GitFailed
from whetstone.verify.task import Task, load_task

#: The budget this contract shipped with, before a run measured what it excluded. The
#: historical boundary: the same task fits at 80,000 and refuses at 40,000, and the reason
#: names the budget that was in force. Kept as a literal for the same reason the sibling file
#: keeps its own: the assertion is precisely that the predicate honours the parameter.
PREVIOUS_BUDGET_CHARS = 40_000


def test_a_task_whose_oracle_the_bakeoff_builds_fits(tmp_path: Path) -> None:
    """The predicate's positive direction, pinned against the bakeoff's own build.

    The task the bakeoff can pose must be the task the predicate admits: if `oracle_sources`
    builds an oracle and the predicate still refuses, the held-out draw excludes a task the
    bakeoff could have asked — a selection no stronger than the old one.
    """
    fixture = build_mined_task(tmp_path / "task")

    sources = oracle_sources(fixture.task)
    fit = oracle_fittable(fixture.task)

    assert sources.files is not None, (
        f"WHY THIS IS A FAILURE: the fixture task itself refuses to build an oracle, so this "
        f"test asserts a fit nothing provokes: {sources.reason}"
    )
    assert fit.fits is True, (
        f"WHY THIS IS A FAILURE: a task the bakeoff builds was refused by the predicate, so "
        f"the held-out draw would exclude a task that was posable: {fit.reason}"
    )
    assert fit.reason == "", (
        f"WHY THIS IS A FAILURE: a fit carries a reason, so on the record a fit and a refusal "
        f"cannot be told apart. Got {fit.reason!r}"
    )


def test_a_task_over_the_cumulative_budget_does_not_fit_and_names_the_budget_passed(
    tmp_path: Path,
) -> None:
    """Over the budget under a custom limit: refused, naming that limit, not the module one.

    `oracle_fittable` must classify under the budget it was *given*: the reason a refusal
    leaves behind names the passed budget, so an operator reading a corpus of skips can tell
    which limit excluded each task.
    """
    over = PREVIOUS_BUDGET_CHARS + 1_000
    fixture = build_mined_task(tmp_path / "task", bulk_chars=over)

    fit = oracle_fittable(fixture.task, budget=PREVIOUS_BUDGET_CHARS)

    assert over > PREVIOUS_BUDGET_CHARS, (
        "WHY THIS IS A FAILURE: the anti-vacuity check. If the fixture is not actually over "
        "the budget then this test asserts a refusal that nothing provoked"
    )
    assert fit.fits is False, (
        "WHY THIS IS A FAILURE: a set over the passed budget was admitted, so the predicate "
        "classifies on a boundary other than the one its caller set"
    )
    assert str(PREVIOUS_BUDGET_CHARS) in fit.reason and "bulk.py" in fit.reason, (
        f"WHY THIS IS A FAILURE: the refusal names neither the budget that was enforced nor the "
        f"file that tipped it. Got {fit.reason!r}"
    )
    assert str(ORACLE_BUDGET_CHARS) not in fit.reason, (
        f"WHY THIS IS A FAILURE: the refusal names the module constant rather than the budget "
        f"the caller passed, so a custom limit cannot be told apart from the default on the "
        f"record. Got {fit.reason!r}"
    )


def test_a_file_too_large_to_read_refuses_by_its_byte_size_alone(tmp_path: Path) -> None:
    """A blob of more than `budget * 4` bytes cannot fit even at one character per byte.

    UTF-8's maximum is four bytes per character, so a path whose size alone exceeds four times
    the budget can never fit it — and refusing it by size alone is what keeps a pathological
    blob from being read into memory to be measured and discarded, on the predicate's reader
    exactly as on `_read`'s.
    """
    over = ORACLE_BUDGET_CHARS * 4 + 1
    fixture = build_mined_task(tmp_path / "task", bulk_chars=over)

    fit = oracle_fittable(fixture.task)

    assert over > ORACLE_BUDGET_CHARS * 4, (
        "WHY THIS IS A FAILURE: the anti-vacuity check. If the fixture file is not actually "
        "over the byte pre-check threshold then this test asserts a refusal that nothing "
        "provoked"
    )
    assert fit.fits is False, (
        "WHY THIS IS A FAILURE: a file whose bytes alone exceed the budget was admitted, so "
        "the predicate measures something other than what the bakeoff refuses"
    )
    assert "bulk.py" in fit.reason and str(ORACLE_BUDGET_CHARS) in fit.reason, (
        f"WHY THIS IS A FAILURE: the refusal names neither the file nor the limit it was "
        f"judged against. Got {fit.reason!r}"
    )


def test_a_task_with_nothing_readable_at_base_commit_does_not_fit(tmp_path: Path) -> None:
    """Every non-test path missing at `base_commit` or not UTF-8 is the same refusal as `_read`'s.

    The fix creates `brand_new.py` — a commit that creates a file is ordinary, so the path is
    omitted, exactly as `_read` treats it — and it mutates `payload.bin`, which is not UTF-8
    text in either commit. With nothing readable left, the predicate must say `fits=False`
    with the bakeoff's own nothing-readable sentence, because an empty oracle is the sourceless
    question wearing the oracle's name.
    """
    donor = tmp_path / "donor"
    donor.mkdir(parents=True)
    _git(["init", "--quiet", "--initial-branch=main"], cwd=donor)
    (donor / "payload.bin").write_bytes(b"\xff\xfe\x00")
    parent = _commit(
        donor, {"tests/test_addition.py": MINED_TESTS_BEFORE}, subject="Seed the calculator"
    )
    (donor / "payload.bin").write_bytes(b"\xff\xfe\x00\x01")
    commit = _commit(
        donor,
        {"tests/test_addition.py": MINED_TESTS_AFTER, "brand_new.py": "FRESH = 1\n"},
        subject="Fix addition",
    )
    task = _donor_task(donor, parent=parent, commit=commit, task_id="synthetic-unreadable")

    fit = oracle_fittable(task)

    assert fit.fits is False, (
        "WHY THIS IS A FAILURE: a task whose every non-test path is unreadable at base_commit "
        "was admitted, so the predicate can classify a file the bakeoff could never show"
    )
    assert fit.reason == (
        f"none of the 2 non-test paths of task 'synthetic-unreadable' could be read at "
        f"{parent}: every one is either created by the fix or not UTF-8 text, so there is no "
        f"source to show and the prompt would ask for a diff against files the base has never "
        f"seen"
    ), (
        f"WHY THIS IS A FAILURE: the nothing-readable refusal moved. It is the bakeoff's "
        f"sentence as well as the predicate's, so the two records would stop naming the same "
        f"class. Got {fit.reason!r}"
    )


def test_a_commit_touching_only_held_tests_does_not_fit_with_the_exact_structural_sentence(
    tmp_path: Path,
) -> None:
    """A mined commit can be all held tests: structural, so `fits=False`, never a raise.

    `git apply` refuses an empty diff, so a task whose fix touched nothing but held tests is
    not a task this contract can pose — and the predicate has to return that as a refusal with
    the bakeoff's exact sentence, because the held-out draw must exclude it permanently, the
    same way the bakeoff skips it.
    """
    fixture = build_mined_task(tmp_path / "task")
    test_file = fixture.donor / "tests" / "test_addition.py"
    test_file.write_text(MINED_TESTS_AFTER + "\n# only held tests in this commit\n")
    _git(["add", "--all"], cwd=fixture.donor)
    _git(["commit", "--quiet", "--message", "touch only held tests"], cwd=fixture.donor)
    only_tests = _git(["rev-parse", "HEAD"], cwd=fixture.donor).strip()
    task = replace(fixture.task, provenance={**fixture.task.provenance, "commit": only_tests})

    fit = oracle_fittable(task)

    assert fit.fits is False, (
        "WHY THIS IS A FAILURE: a commit that touched nothing but held tests was admitted, so "
        "the predicate invented a scope the commit never stated"
    )
    assert fit.reason == (
        f"commit {only_tests} of task {task.task_id!r} touched no non-test path, so there is "
        f"neither a reference patch to apply — `git apply` refuses an empty diff — nor a "
        f"file to show the base"
    ), (
        f"WHY THIS IS A FAILURE: the no-non-test-path refusal sentence moved. It is the "
        f"predicate's `fits=False` reason as well as the bakeoff's skip, so the two records "
        f"would stop naming the same class. Got {fit.reason!r}"
    )


def test_a_fix_touching_an_operator_held_path_does_not_fit_with_the_exact_sentence(
    tmp_path: Path,
) -> None:
    """A path the operator holds is a permanent property, so it refuses rather than raises.

    No machine state can make a held path un-held, so the predicate must return `fits=False`
    with the bakeoff's exact vouched sentence: showing the operator's assertions to a base
    would hand over the exam it is marked with.
    """
    fixture = build_mined_task(tmp_path / "task", held_conftest=True)

    fit = oracle_fittable(fixture.task)

    assert fit.fits is False, (
        "WHY THIS IS A FAILURE: a fix touching an operator-held path was admitted, so the "
        "answer key could reach the context window"
    )
    assert fit.reason == (
        f"the fix for task {fixture.task.task_id!r} touches operator-held ['conftest.py'], "
        f"which STRICT refuses as a cheat before anything runs. Using it as a reference would "
        f"report the reward's own scope check as `the harness cannot reach PASS`, and "
        f"showing it to a base would hand over the assertions the reward is computed from"
    ), (
        f"WHY THIS IS A FAILURE: the vouched refusal sentence moved. It is the predicate's "
        f"`fits=False` reason as well as the bakeoff's skip, so the two records would stop "
        f"naming the same class. Got {fit.reason!r}"
    )


def test_a_task_whose_donor_cannot_be_read_raises_instead_of_classifying(
    tmp_path: Path,
) -> None:
    """Machine state never classifies: an unreadable donor raises, it does not return `fits=False`.

    An exclusion from the held-out draw must never be caused by a transient condition, so a
    task whose donor cannot be read is a raise for the caller to refuse by name — the
    `GitFailed`/`SubprocessError`/`OSError` family `_structural_paths` documents. A predicate
    that answered `fits=False` here would exclude the task permanently for a reason that
    vanishes the moment the donor comes back.
    """
    fixture = build_mined_task(tmp_path / "task")
    shutil.rmtree(fixture.donor)

    with pytest.raises((GitFailed, subprocess.SubprocessError, OSError)):
        oracle_fittable(fixture.task)


def test_the_budget_parameter_moves_the_boundary_for_one_task(tmp_path: Path) -> None:
    """The historical boundary as a predicate: fits at 80,000, refuses at 40,000.

    The same task, the same tree, two budgets: 60,000 characters is inside the limit this
    contract ships with and outside the one it shipped with. Refusing at 40,000 while
    admitting at the default is the whole point of the parameter — a held-out derivation that
    classifies under a budget the bakeoff never sees must move the boundary with it.
    """
    fixture = build_mined_task(tmp_path / "task", bulk_chars=60_000)

    at_default = oracle_fittable(fixture.task)
    at_old = oracle_fittable(fixture.task, budget=PREVIOUS_BUDGET_CHARS)

    assert at_default.fits is True, (
        f"WHY THIS IS A FAILURE: a task comfortably inside the default budget was refused, so "
        f"the limit is rejecting ordinary repositories: {at_default.reason}"
    )
    assert at_old.fits is False, (
        "WHY THIS IS A FAILURE: the same task fits under the old budget too, so the parameter "
        "does not move the boundary and the historical boundary is not being exercised"
    )
    assert str(PREVIOUS_BUDGET_CHARS) in at_old.reason, (
        f"WHY THIS IS A FAILURE: the refusal does not name the 40,000-character budget it "
        f"enforced. Got {at_old.reason!r}"
    )


def test_deriving_the_same_task_twice_is_identical(tmp_path: Path) -> None:
    """Two derivations, identical records — a pure function of the manifest and git objects.

    The held-out derivation and the bakeoff derive the same task from the same manifest, and
    a predicate that differed between two derivations would make the draw depend on when it
    was computed. No checkout, no network, no clock: nothing but the manifest and immutable
    git objects, so the refusal reasons must come back byte-identical too.
    """
    fixture = build_mined_task(tmp_path / "task", bulk_chars=60_000)

    assert oracle_fittable(fixture.task) == oracle_fittable(fixture.task), (
        "WHY THIS IS A FAILURE: two derivations of one task disagreed on whether it fits, so "
        "the held-out draw depends on when it was computed"
    )
    refused = oracle_fittable(fixture.task, budget=PREVIOUS_BUDGET_CHARS)
    assert oracle_fittable(fixture.task, budget=PREVIOUS_BUDGET_CHARS) == refused, (
        "WHY THIS IS A FAILURE: two derivations of one refusal disagreed on the reason, so "
        "the record of why a task was excluded depends on when it was computed"
    )


def test_the_predicate_reaches_the_budget_rule_and_the_path_derivation_by_identity() -> None:
    """`oracle_fittable` classifies through the same two objects the bakeoff enforces.

    Two pins, one per shared rule: the budget rule `_read` feeds and the path derivation
    `_from_donor` feeds must be the very objects the predicate resolves, asserted `is` —
    "one rule by identity" is the aspect's spec, and a predicate that reached a second
    implementation of either would classify on a boundary the bakeoff does not enforce.
    """
    assert (
        sources_module.oracle_fittable.__globals__["_budget_rule"]
        is sources_module._budget_rule
    ), (
        "WHY THIS IS A FAILURE: `oracle_fittable` resolves a budget rule that is not the "
        "module's own object, so the held-out predicate could classify on a boundary the "
        "bakeoff does not enforce"
    )
    assert (
        sources_module.oracle_fittable.__globals__["_structural_paths"]
        is sources_module._structural_paths
    ), (
        "WHY THIS IS A FAILURE: `oracle_fittable` derives its path set through a function "
        "that is not the module's own `_structural_paths`, so a second derivation of the "
        "donor route exists and the predicate could classify on a path set the bakeoff never "
        "derived"
    )


def _donor_task(donor: Path, *, parent: str, commit: str, task_id: str) -> Task:
    """The task mined from a hand-built two-commit donor, written and loaded like `mine` would.

    The manifest mirrors `fixtures.repos.mined.build_mined_task`'s, minus the parameters this
    file's shapes do not need. The held test is read at the child, the way
    `whetstone.tasks.mine._manifest` reads it.
    """
    manifest = {
        "task_id": task_id,
        "source": "private",
        "repo_url": str(donor),
        "base_commit": parent,
        "environment": {"python": "3.12", "pins": [], "import_roots": ["."]},
        "problem_statement": "Fix addition",
        "fail_to_pass": ["tests/test_addition.py::test_add_is_addition"],
        "pass_to_pass": ["tests/test_addition.py::test_adding_zero_is_the_identity"],
        "test_blobs": {
            "tests/test_addition.py": base64.b64encode(MINED_TESTS_AFTER.encode()).decode(
                "ascii"
            )
        },
        "provenance": {"donor": donor.name, "commit": commit, "parent": parent},
    }
    manifest_path = donor.parent / f"{task_id}.json"
    manifest_path.write_text(json.dumps(manifest))
    return load_task(manifest_path)