"""The control arm: proof that the harness could have reached PASS, taken in the same run.

Without it, **"all three candidates solved zero" and "the harness was broken" are the same
observation.** Both arrive as a column of zeroes; they have opposite meanings and opposite fixes;
and P1's pivot signal — whether to change base, change prompt, or change task family — rests
entirely on telling them apart (`docs/ROADMAP.md:387-389`). A bake-off that cannot distinguish
them publishes a number that means nothing, which is worse than publishing none.

So every candidate's run carries two probes per task, under the **same provisioning** the rollouts
get, using the **same shipped STRICT verifier**:

* `inert_patch()` — a real diff that changes nothing any test can read — must reach **FAIL**. If
  it reaches PASS the task was never red, and every policy graded against it is graded correct.
* the task's own reference patch, **re-derived from the donor**, must reach **PASS**. If it
  cannot, no patch could, and a zero says nothing about any model.

Either half wrong and the run is UNVERIFIED: the records are still findings, but nothing may be
ranked off them. UNVERIFIED never counts as a win, and it must never count as a loss either.

**The pre-flight is the subtle half.** A re-derived reference that touches an operator-held test
path is refused by STRICT before anything runs — correctly, that is the cheat-scope check doing
its job — and the refusal is indistinguishable from "the harness cannot reach PASS". That would
raise a false alarm about the very thing this arm exists to establish. It never fired across the
66 mined manifests and it costs one set comparison, so the reference is checked against
`task.test_blobs` before it is used, and a collision is a **skip with a reason** rather than a
control failure.

**No model, no `mlx`, no network.** The control arm never asks a base for anything — it is about
the harness — so nothing here needs a generator at all.
"""

from __future__ import annotations

from pathlib import Path

from fixtures.repos.mined import MINED_CALC_FIXED, MINED_README_AFTER, build_mined_task

from whetstone.bakeoff.control import Control, harness_status, probe, reference_patch
from whetstone.bakeoff.scoring import Interpreters
from whetstone.verify.verdict import Status

#: Generous enough that a two-commit donor with one module and one pytest file can never reach it,
#: so an UNVERIFIED in this file always means something went wrong rather than something ran slow.
TIMEOUT = 120.0


def test_the_control_arm_proves_the_harness_can_reach_both_verdicts(tmp_path: Path) -> None:
    """Inert patch FAILs, re-derived reference PASSes: the harness is provably intact.

    This is the assertion that gives an all-zero bake-off its meaning. With it, a column of
    zeroes is a statement about the bases; without it, the same column is consistent with a
    verifier that never applied a patch to the tree it verified — which is a defect this
    repository has already shipped once and closed (`tests/adversarial/test_inert_checkout.py`).
    """
    fixture = build_mined_task(tmp_path / "task")

    result = probe(
        candidate="any-base",
        task=fixture.task,
        sandbox_root=tmp_path / "control",
        timeout=TIMEOUT,
        interpreters=Interpreters(workspace=tmp_path / "envs"),
    )

    assert (result.control, result.without_patch, result.with_reference) == (
        Control.INTACT,
        Status.FAIL,
        Status.PASS,
    ), (
        "WHY THIS IS A FAILURE: the harness could not be shown to discriminate on this task — a "
        "patch that changes nothing must FAIL it and the commit's own fix must PASS it. Until "
        "both are observed in the same run, under the same provisioning, a candidate scoring "
        f"zero is indistinguishable from a harness that grades nothing. Got {result.control!r}, "
        f"without_patch={result.without_patch!r}, with_reference={result.with_reference!r}: "
        f"{result.detail}"
    )


def test_the_reference_patch_is_the_commits_own_fix_without_its_tests(tmp_path: Path) -> None:
    """Re-derived from the donor: every non-test path the commit touched, and no other.

    Asserted separately from the verdict above because "the reference reached PASS" is also what
    a reference containing the *test* file would produce — the restore would simply overwrite it
    — so the PASS alone does not prove the derivation kept the right paths. A reference carrying
    the held test is a reference STRICT refuses as a cheat, and the pre-flight below depends on
    this derivation being the thing that decides.
    """
    fixture = build_mined_task(tmp_path / "task")

    reference = reference_patch(fixture.task)

    assert reference.diff is not None, (
        f"WHY THIS IS A FAILURE: the task names its donor, its commit and its parent, so its own "
        f"fix is re-derivable and the control arm has something to prove PASS with. Refusing to "
        f"derive it turns every task into a skip and leaves the run unproven: {reference.reason}"
    )
    # The lines the diff ADDS, with git's marker stripped. Compared against the fix's own changed
    # line rather than against the whole file, because the unchanged lines around it are context
    # and a diff that carried them as additions would be rewriting the file rather than fixing it.
    added = {line[1:] for line in reference.diff.splitlines() if line.startswith("+")}
    assert MINED_CALC_FIXED.splitlines()[-1] in added, (
        "WHY THIS IS A FAILURE: the re-derived reference does not add the line the commit's fix "
        f"added, so whatever it contains is not that commit's patch:\n{reference.diff}"
    )
    assert "README.md" in reference.diff and MINED_README_AFTER.splitlines()[-1] in added, (
        "WHY THIS IS A FAILURE: the commit also touched a non-`.py` file and the derivation "
        "dropped it. A reference patch that is not the whole commit minus its tests does not "
        f"reproduce the commit, and any verdict it earns is about a patch nobody wrote:\n"
        f"{reference.diff}"
    )
    assert "tests/test_addition.py" not in reference.diff, (
        "WHY THIS IS A FAILURE: the re-derived reference carries the operator-held test file. "
        "STRICT refuses a patch touching a held path before anything runs, so the control arm "
        "would read its own cheat-scope refusal as `the harness cannot reach PASS` — a false "
        f"alarm about the exact thing this arm exists to rule out:\n{reference.diff}"
    )


def test_a_task_that_passes_with_no_patch_breaks_the_control_arm_loudly(tmp_path: Path) -> None:
    """The inert patch reaching PASS is a fact about the task or the checkout, never about a base.

    This is the shape a broken harness wears in public. A task whose declared failing test already
    passes at `base_commit` grades *every* policy as correct — including one that emitted nothing
    — and it looks, from the outside, exactly like a base that solved it. `tests/adversarial/
    test_inert_checkout.py` records that this repository has already shipped one version of this
    defect: a task PASSED with no patch applied, because the tests imported an editable install
    rooted at a different checkout.

    So the response is BROKEN and not a quiet skip, and it takes the whole run's ranking with it.
    """
    fixture = build_mined_task(tmp_path / "task", vacuous=True)

    result = probe(
        candidate="any-base",
        task=fixture.task,
        sandbox_root=tmp_path / "control",
        timeout=TIMEOUT,
        interpreters=Interpreters(workspace=tmp_path / "envs"),
    )

    assert result.control is Control.BROKEN, (
        "WHY THIS IS A FAILURE: a task that passes with a patch changing nothing was accepted as "
        "a sound control. Every candidate would score a win on it, that win would be the "
        f"harness's rather than the base's, and the bake-off would report it as a base's. Got "
        f"{result.control!r} ({result.without_patch!r})"
    )
    assert result.without_patch is Status.PASS
    assert harness_status([result]) is Status.UNVERIFIED, (
        "WHY THIS IS A FAILURE: the run was not marked UNVERIFIED despite a broken control. "
        "UNVERIFIED never counts as a win — and a run whose harness grades nothing must not be "
        f"ranked in either direction. Got {harness_status([result])!r}"
    )
    assert "base_commit" in result.detail or "changes nothing" in result.detail, (
        "WHY THIS IS A FAILURE: the control failed without saying what to go and look at. The "
        "two candidate causes — a task that was never red, and a checkout the patch never "
        f"reached — have entirely different fixes. Got {result.detail!r}"
    )


def test_a_reference_that_touches_a_held_test_is_skipped_with_a_reason(tmp_path: Path) -> None:
    """The pre-flight: a collision is a skip, never a control failure and never a silent use.

    STRICT refuses any patch touching an operator-held path before a single test runs — the
    cheat-scope check doing its job. A control arm that handed such a reference to STRICT would
    read that refusal as "the harness cannot reach PASS" and mark the entire run UNVERIFIED, which
    is a false alarm about the one thing the arm exists to rule out.

    The fixture's commit edits a root `conftest.py` the manifest holds as its cheat-10 floor.
    `is_test_path` correctly calls that file source rather than test code, so it lands in the
    derived path set — which is exactly why the check is against `test_blobs` and not against a
    naming convention.
    """
    fixture = build_mined_task(tmp_path / "task", held_conftest=True)

    reference = reference_patch(fixture.task)
    result = probe(
        candidate="any-base",
        task=fixture.task,
        sandbox_root=tmp_path / "control",
        timeout=TIMEOUT,
        interpreters=Interpreters(workspace=tmp_path / "envs"),
    )

    assert reference.diff is None, (
        "WHY THIS IS A FAILURE: a reference patch touching an operator-held path was handed back "
        "for use. STRICT would refuse it as a cheat before anything ran, and the control arm "
        f"would record the reward working correctly as the harness being broken:\n{reference.diff}"
    )
    assert "conftest.py" in reference.reason, (
        "WHY THIS IS A FAILURE: the skip does not name the path that collided, so nobody can "
        f"tell a held-path collision from a missing donor. Got {reference.reason!r}"
    )
    assert (result.control, result.with_reference) == (Control.SKIPPED, None), (
        "WHY THIS IS A FAILURE: a task the harness could not be checked on was recorded as "
        "something other than a skip. A skip is an ordinary gap the remaining tasks close; a "
        f"BROKEN stops the whole run being ranked. Got {result.control!r}"
    )
    assert harness_status([result]) is Status.UNVERIFIED, (
        "WHY THIS IS A FAILURE: a run in which every probe was skipped established nothing about "
        "the harness, and `nothing went wrong` is not proof that anything went right. It has to "
        f"fall to UNVERIFIED. Got {harness_status([result])!r}"
    )


def test_a_renamed_path_carries_both_of_its_names_into_the_reference(tmp_path: Path) -> None:
    """git reports a rename as ONE record with TWO paths, and both halves are needed.

    Every other name-status record is a status and one path, so a parser consuming a fixed number
    of fields desynchronises the moment a commit contains a rename: it would read the destination
    path as the next record's status letter and mis-parse every remaining file in that commit.
    Silently — the derived patch would simply be missing files, and the control arm would report
    "the harness cannot reach PASS" for a commit whose fix it had itself truncated.

    Both names are kept because a rename is a deletion and a creation: a reference patch carrying
    only one of them does not apply.
    """
    fixture = build_mined_task(tmp_path / "task", renamed=True)

    reference = reference_patch(fixture.task)
    result = probe(
        candidate="any-base",
        task=fixture.task,
        sandbox_root=tmp_path / "control",
        timeout=TIMEOUT,
        interpreters=Interpreters(workspace=tmp_path / "envs"),
    )

    assert reference.diff is not None, (
        f"WHY THIS IS A FAILURE: a commit containing a rename produced no reference patch at "
        f"all: {reference.reason}"
    )
    assert "helper.py" in reference.diff and "helpers.py" in reference.diff, (
        "WHY THIS IS A FAILURE: the reference patch names only one side of the rename, so it "
        "either deletes a file without creating its replacement or creates one without removing "
        f"the original. Neither applies:\n{reference.diff}"
    )
    assert result.control is Control.INTACT, (
        "WHY THIS IS A FAILURE: a commit whose fix included a rename could not be replayed, so "
        "the harness would be reported broken on every such task — and roughly a fifth of real "
        f"red-to-green commits touch more than a single source file. Got {result.control!r}: "
        f"{result.detail}"
    )
