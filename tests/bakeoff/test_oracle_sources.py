"""What the base is shown of the repository, where it comes from, and when it must not be shown.

A measured probe against a real base over three real tasks returned `NOT_APPLIED` on every
rollout. The diagnosis was in the rendered prompt rather than in the model: **it contained no
source code at all**, and a unified diff is written out of a file's exact context lines. The task
as posed was not hard, it was impossible, and a bake-off run that way would have measured the
prompt while publishing a zero indistinguishable from P1's genuine pivot signal.

So the non-test files the task's reference patch touches are read out of the donor at
`base_commit` and shown. This file holds that derivation to four properties, each of which is a
different way of quietly running a different experiment from the one that gets published:

1. **the code shown is the code at `base_commit`** — i.e. still broken. A file quoted from after
   the fix would hand over the answer *and* give the base context lines that are not in the
   checkout, so its diff would not apply either;
2. **no operator-held path is ever in the map** — the whole provenance boundary, and now the only
   thing between a mis-classified path and the answer key in the context window;
3. **a task whose oracle cannot be derived yields no oracle**, with a reason, rather than an empty
   map that would be scored as though the base had been given a fair question;
4. **an oracle over the character budget is refused rather than truncated**, because a truncated
   file is a different experiment from a whole one and nothing downstream could tell which one a
   given rollout ran.

No model, no `mlx`, no network: donors are two-commit synthetic repositories built with real git,
and everything under test is a string derived from them.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fixtures.repos import build_task
from fixtures.repos.mined import (
    MINED_CALC_BUGGY,
    MINED_CALC_FIXED,
    MINED_HELPER,
    MINED_README_BEFORE,
    build_mined_task,
)

from whetstone.bakeoff import sources as sources_module
from whetstone.bakeoff.rendering import prompt_hash, render_prompt
from whetstone.bakeoff.sources import ORACLE_BUDGET_CHARS, oracle_sources

#: The budget this contract shipped with, before a run measured what it excluded. Kept as a literal
#: rather than imported, because the assertion below is precisely that the number moved and that
#: nothing a reader can observe moved with it — an import would make it move too.
PREVIOUS_BUDGET_CHARS = 40_000


def test_the_oracle_is_the_non_test_files_the_fix_touches_as_they_stand_at_base_commit(
    tmp_path: Path,
) -> None:
    """The whole point, in one assertion set: the right files, and the *broken* version of them.

    The fixing commit touches `calc.py`, `README.md` and the held test. The first two are what the
    base must be able to write a diff against; the third is the answer key. And the contents have
    to be the parent's — `verify_strict` checks out `base_commit`, so a prompt quoting the fixed
    file would both give away the answer and describe lines that are not in the tree the patch is
    applied to, producing `NOT_APPLIED` for a base that copied its context faithfully.
    """
    fixture = build_mined_task(tmp_path / "task")

    sources = oracle_sources(fixture.task)

    assert sources.files is not None, (
        f"WHY THIS IS A FAILURE: this task names its donor, its commit and its parent, so the "
        f"files its fix touches are derivable. Refusing to derive them makes every task a skip "
        f"and the bake-off scores nothing: {sources.reason}"
    )
    assert set(sources.files) == {"calc.py", "README.md"}, (
        f"WHY THIS IS A FAILURE: the oracle is {sorted(sources.files)} rather than the commit's "
        "non-test paths. Too few and the base is asked to patch a file it was never shown; too "
        "many and the prompt is a tour of the repository that crowds out the question"
    )
    assert sources.files["calc.py"] == MINED_CALC_BUGGY, (
        f"WHY THIS IS A FAILURE: the source shown is not the version in the checkout the patch is "
        f"applied to. If it is the fixed version the prompt contains the answer, and the base's "
        f"context lines describe a file that does not exist at base_commit. Got "
        f"{sources.files['calc.py']!r}"
    )
    assert MINED_CALC_FIXED not in sources.files["calc.py"], (
        "WHY THIS IS A FAILURE: the fixed line reached the prompt, so the task is solved by "
        "copying and the resulting count measures transcription rather than repair"
    )
    assert sources.files["README.md"] == MINED_README_BEFORE, (
        "WHY THIS IS A FAILURE: a non-`.py` path the commit touched was dropped or read at the "
        f"wrong commit. Got {sources.files['README.md']!r}"
    )


def test_the_operator_held_test_is_never_in_the_oracle(tmp_path: Path) -> None:
    """Asserted on its own, because it is the one property that must never be a side effect.

    The fixing commit touches the held test — every mined task's does, by construction: that is
    what made it minable. The derivation therefore has to remove it, and this assertion is what
    stops a later, simpler "show every file the commit touched" from passing the test above while
    putting `test_blobs` in the context window.
    """
    fixture = build_mined_task(tmp_path / "task")

    sources = oracle_sources(fixture.task)

    assert sources.files is not None
    leaked = sorted(set(sources.files) & set(fixture.task.test_blobs))
    assert leaked == [], (
        f"WHY THIS IS A FAILURE: the oracle offers operator-held {leaked}. "
        "Those files are what STRICT restores from golden and grades against, so showing them "
        "hands the policy the exam it is marked with and makes cheat 6 — special-casing the "
        "graded inputs — the cheapest strategy available. No re-execution downstream can catch it"
    )


def test_a_file_the_commit_creates_is_not_in_the_oracle(tmp_path: Path) -> None:
    """A path that does not exist yet at `base_commit` has no contents to show.

    The fixing commit renames `helper.py` to `helpers.py`, so both names are in the derived path
    set and only one of them is a file in the checkout. Reading the missing one has to be an
    omission rather than an error: a commit that adds a file is ordinary, and a derivation that
    raised on it would skip every task whose fix created something.
    """
    fixture = build_mined_task(tmp_path / "task", renamed=True)

    sources = oracle_sources(fixture.task)

    assert sources.files is not None, sources.reason
    assert sources.files.get("helper.py") == MINED_HELPER, (
        "WHY THIS IS A FAILURE: the file that DOES exist at base_commit was dropped along with "
        f"the one that does not. Got {sorted(sources.files)}"
    )
    assert "helpers.py" not in sources.files, (
        "WHY THIS IS A FAILURE: a path that does not exist at base_commit was rendered anyway, so "
        "either it was read at the wrong commit — giving away the fix — or it was shown as empty, "
        "which tells the base a file exists that does not"
    )


def test_deriving_the_same_task_twice_gives_the_same_oracle(tmp_path: Path) -> None:
    """Two derivations, byte-identical. The prompt hash is provenance and this is under it.

    `freeze` derives the oracle to fix the contract and `score` derives it again to ask the
    question; a derivation that differed between the two — on a temporary directory's name, on
    filesystem ordering — would abort every honest run under M7b's invalidation rule with nothing
    actually changed.
    """
    fixture = build_mined_task(tmp_path / "task")

    assert oracle_sources(fixture.task).files == oracle_sources(fixture.task).files, (
        "WHY THIS IS A FAILURE: two derivations of one task disagreed, so the prompt a base is "
        "shown depends on when it was built. The frozen contract's digest would then move without "
        "the contract moving, and M7b's rule would fire on runs where nothing had changed"
    )


def test_a_task_with_no_donor_provenance_yields_no_oracle_and_says_why(tmp_path: Path) -> None:
    """No commit to diff, so no file set — and the honest answer is a refusal with a sentence.

    Source A's instances are this case: a public task carries no donor commit, so nothing here can
    tell which files its fix touches. `scoring.score` turns this into skipped-with-reason. An
    empty map returned instead would be scored as a fair rollout and would put the sourceless
    question into the same denominator as the oracle one.
    """
    fixture = build_task(tmp_path / "task")

    sources = oracle_sources(fixture.task)

    assert sources.files is None, (
        "WHY THIS IS A FAILURE: a task with no donor commit produced an oracle anyway, so "
        f"something was invented for it. Got {sources.files!r}"
    )
    assert "provenance" in sources.reason, (
        f"WHY THIS IS A FAILURE: the refusal does not say what was missing, so a run of skips "
        f"cannot be told apart from a run of absent donors. Got {sources.reason!r}"
    )


def test_a_donor_that_is_not_on_this_machine_yields_no_oracle(tmp_path: Path) -> None:
    """The manifests are committed and the donors are the user's own checkouts, which travel apart.

    A missing donor has to be a recorded skip and never an exception: a bake-off that aborted on
    the first absent repository would report the machine rather than the bases.
    """
    fixture = build_mined_task(tmp_path / "task")
    shutil.rmtree(fixture.donor)

    sources = oracle_sources(fixture.task)

    assert sources.files is None, (
        "WHY THIS IS A FAILURE: an oracle was produced for a donor that is not on this machine, "
        f"so its contents came from somewhere nobody can name. Got {sources.files!r}"
    )
    assert sources.reason, (
        "WHY THIS IS A FAILURE: the skip carries no reason, so whoever reads a run full of them "
        "cannot tell a missing donor from a held-path collision from a budget refusal"
    )


def test_a_fix_touching_an_operator_held_path_yields_no_oracle(tmp_path: Path) -> None:
    """The pre-flight, shared with the control arm: a collision is a skip, never a partial oracle.

    The fixture's commit edits a root `conftest.py` the manifest holds. `is_test_path` correctly
    calls that file source rather than test code, so it lands in the derived path set — which is
    exactly why the check is against `test_blobs` and not against a naming convention. Showing the
    remaining files and silently dropping the held one would be worse than skipping: the base
    would be patching around a file it was told nothing about, and the rollout would be scored as
    though it had seen everything.
    """
    fixture = build_mined_task(tmp_path / "task", held_conftest=True)

    sources = oracle_sources(fixture.task)

    assert sources.files is None, (
        "WHY THIS IS A FAILURE: the fix touches an operator-held path and an oracle was built "
        f"anyway. Got {sources.files!r}"
    )
    assert "conftest.py" in sources.reason, (
        f"WHY THIS IS A FAILURE: the skip does not name the path that collided. Got "
        f"{sources.reason!r}"
    )


def test_an_oracle_over_the_character_budget_is_refused_rather_than_truncated(
    tmp_path: Path,
) -> None:
    """A file too large to show is a task this contract cannot pose, not a task to pose partially.

    Truncation is the tempting failure and it is silent: the base is shown the first N characters
    of a file, writes context lines from the part it was given, and is charged `NOT_APPLIED` — or
    worse, the whole prompt overruns the context window and what the base actually saw is decided
    by a tokenizer nobody recorded. Either way the rollout ran a different experiment from its
    neighbours in the same denominator. So the budget is a refusal.
    """
    over = ORACLE_BUDGET_CHARS + 1_000
    fixture = build_mined_task(tmp_path / "task", bulk_chars=over)

    sources = oracle_sources(fixture.task)

    assert over > ORACLE_BUDGET_CHARS, (
        "WHY THIS IS A FAILURE: the anti-vacuity check. If the fixture is not actually over the "
        "budget then this test asserts a refusal that nothing provoked"
    )
    assert sources.files is None, (
        "WHY THIS IS A FAILURE: an over-budget oracle was returned. Whatever the base is shown "
        f"next is decided by the context window rather than by this contract. Got "
        f"{sorted(sources.files or {})}"
    )
    assert str(ORACLE_BUDGET_CHARS) in sources.reason, (
        f"WHY THIS IS A FAILURE: the refusal does not name the budget it enforced, so an operator "
        f"seeing a corpus of skips cannot tell whether the limit is wrong for their repository. "
        f"Got {sources.reason!r}"
    )


def test_an_oracle_within_the_budget_is_shown_whole(tmp_path: Path) -> None:
    """The opposite sign: without it, `return no oracle, ever` passes every refusal above.

    Also the assertion that the budget is a *bound* and not a policy — a task well inside it must
    come through with its files intact, or the bake-off would skip its way to an empty corpus.
    """
    fixture = build_mined_task(tmp_path / "task", bulk_chars=ORACLE_BUDGET_CHARS // 4)

    sources = oracle_sources(fixture.task)

    assert sources.files is not None, (
        f"WHY THIS IS A FAILURE: a task comfortably inside the budget was refused, so the limit is "
        f"rejecting ordinary repositories: {sources.reason}"
    )
    assert "bulk.py" in sources.files, (
        f"WHY THIS IS A FAILURE: the large-but-permitted file was dropped from the oracle while "
        f"the rest were kept, which is truncation by another name. Got {sorted(sources.files)}"
    )
    assert sum(len(text) for text in sources.files.values()) <= ORACLE_BUDGET_CHARS, (
        "WHY THIS IS A FAILURE: the returned oracle is itself over the budget, so the check "
        "measures something other than what it returns"
    )


def test_raising_the_budget_cannot_move_a_prompt_that_already_fitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """*(the honesty control on the raise)* A task under the old budget renders byte-identically.

    The budget was raised **after** observing that it excluded 20 of 63 private tasks — on a run
    that aborted and published nothing, but a measurement taken during a run all the same. That
    ordering is what separates a fix from tuning, and only one property makes it defensible: the
    change can move a task from *not posable* to *posable* and can move nothing else. A task
    already inside the old budget must be shown the same files with the same contents in the same
    order, and must therefore hash to the same `prompt_sha256` under both.

    So the old budget is reinstated here and the prompt rendered under it is compared, byte for
    byte and hash for hash, with the prompt rendered under the new one. If a later change ever
    makes the budget a *truncation point* rather than a bound — the tempting way to fit more in —
    this is the assertion that fails, and it fails before anything is scored under it.
    """
    fixture = build_mined_task(tmp_path / "task", bulk_chars=PREVIOUS_BUDGET_CHARS // 2)

    monkeypatch.setattr(sources_module, "ORACLE_BUDGET_CHARS", PREVIOUS_BUDGET_CHARS)
    before = oracle_sources(fixture.task)
    monkeypatch.undo()
    after = oracle_sources(fixture.task)

    assert ORACLE_BUDGET_CHARS > PREVIOUS_BUDGET_CHARS, (
        f"WHY THIS IS A FAILURE: the anti-vacuity check. This test only says anything while the "
        f"budget has actually been raised above the {PREVIOUS_BUDGET_CHARS} that excluded a third "
        f"of the corpus; at or below it, the two renders are identical because they are the same "
        f"render. Got {ORACLE_BUDGET_CHARS}"
    )
    assert before.files is not None and after.files is not None, (
        f"WHY THIS IS A FAILURE: this fixture is comfortably inside BOTH budgets, so a refusal "
        f"under either means the comparison never happened: {before.reason or after.reason}"
    )
    assert before.files == after.files, (
        f"WHY THIS IS A FAILURE: raising the budget changed which files a task under the old one "
        f"is shown, or what they contain. That makes the raise a change to the question rather "
        f"than to which questions can be asked, and every already-posable task's rollout would be "
        f"a different experiment from the one the old contract posed. Got {sorted(before.files)} "
        f"then {sorted(after.files)}"
    )

    old_prompt = render_prompt(fixture.task, before.files)
    new_prompt = render_prompt(fixture.task, after.files)
    assert old_prompt == new_prompt, (
        "WHY THIS IS A FAILURE: the rendered prompt moved for a task that already fitted, so the "
        "budget is reaching into what the base is shown rather than deciding whether it can be "
        "shown anything at all"
    )
    assert prompt_hash(old_prompt) == prompt_hash(new_prompt), (
        "WHY THIS IS A FAILURE: the prompt hash moved. That hash is this run's provenance and the "
        "seal `run.freeze` fixes the question with — a budget that could move it would invalidate "
        "every honest run under M7b's rule with nothing about the question having changed"
    )
