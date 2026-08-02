"""The extractor, and the two ways it could quietly make P1's headline unreadable.

This file guards one function, and it is worth stating plainly why one function gets this much
test. The bake-off's whole purpose is to answer *which open base do we start from* with a
measurement instead of a table of somebody else's scores. That answer is a comparison of
STRICT-PASS counts between candidate bases. Everything between "the model emitted some text" and
"the verifier graded a patch" is this function, so every way it can be wrong is a way the
comparison can be wrong while still looking like a result.

**Failure one: a no-diff response spelled as an empty patch.** `verify_strict(task, "")` does not
return "nothing to grade". It is charged `FAIL` at `kind="patch-apply"`
(`whetstone.tasks.liveness:14-20`; measured directly — `git apply` answers an empty patch with
*"No valid patches in input"*), which is the **same status a genuinely wrong fix gets**. So an
extractor that returned `""` when it found no diff would produce a run of honest-looking FAILs.
If it were broken enough to do that on every task, the run would read as *zero tasks solved by
every candidate base* — which is indistinguishable from P1's real pivot signal, the finding that
no candidate base solves any task (`docs/ROADMAP.md:387`). That finding tells the founder to
abandon expert iteration and change plan. A bug that can forge it is the most expensive bug
available in this slice, and it is PRD risk R1. The defence is that "no diff" is a **different
type**, carrying a reason, with no `.diff` attribute to hand on by accident.

**Failure two: an extractor that helps.** If a base emits a diff aimed at a path in the task's
`test_blobs` — the operator-held tests the reward is measured against — that is a caught
reward-hacking attempt: STRICT refuses it before anything runs, at `kind="patch-scope"`
(`strict.py:524-533`), and the count of such refusals is a published number. An extractor that
noticed the held path and helpfully dropped the hunk, or rewrote it, would convert a **caught**
cheat into an **uncaught** one: the patch would go on to be graded on its remaining hunks, and
the refusal that should have been counted would never have happened. That is a reward-hacking
mitigation implemented in the wrong layer, and its effect is to silently lower a number the
project publishes as evidence of its own honesty. So the adversarial test here feeds the
extractor a diff that edits a held test and asserts the held path comes back **verbatim**.

**What this function is therefore allowed to do:** *locate* a diff in a model's output and hand
it on unchanged, or say it found none and why. It never repairs what a diff says. The single
exception is documented in `patch.py` and asserted below — a final newline, without which `git
apply` refuses to parse a patch at all (measured: *"corrupt patch at line 8"*) — and it is safe
precisely because appending a line terminator cannot change which paths a diff touches.

Nothing here calls `verify_strict`; grading is aspect 2's job. The round-trip test shells out to
`git apply --check` against a temporary repository, which is the cheapest honest way to ask
whether the string we produced is the kind of string the reward path can actually use. No model,
no network.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from whetstone.bakeoff.patch import Extracted, NoDiff, extract_patch
from whetstone.verify.task import Environment, Task

#: The operator-held test path used by the adversarial case. Spelled the way a real manifest
#: spells it — repository-relative, forward slashes — because `test_blobs` keys are canonical
#: paths and the point of the test is that this exact string survives extraction.
HELD_TEST_PATH = "tests/test_addition.py"

#: A well-formed unified diff that touches ordinary source. Used wherever a test needs "a diff"
#: and does not care what it says. Kept as a module constant so that every assertion about
#: *where* a diff was found is comparing against one fixed body of text.
#:
#: The hunk header's counts are **correct**, and that is load-bearing rather than tidy: an
#: earlier draft declared `@@ -1,3 +1,3 @@` over a two-line hunk, and `test_an_extracted_diff_is
#: _accepted_by_git_apply` was the only thing in this file that noticed. A fixture that git
#: rejects cannot distinguish a working extractor from a broken one.
GOOD_DIFF = (
    "diff --git a/adder.py b/adder.py\n"
    "--- a/adder.py\n"
    "+++ b/adder.py\n"
    "@@ -1,2 +1,2 @@\n"
    " def add(a, b):\n"
    "-    return a - b\n"
    "+    return a + b\n"
)

#: A second, visibly different diff. Its whole job is to make "which one did you pick?" a
#: question with a checkable answer: a test that used `GOOD_DIFF` twice could not tell a
#: first-block rule from a last-block rule from a coin toss.
OTHER_DIFF = (
    "diff --git a/multiplier.py b/multiplier.py\n"
    "--- a/multiplier.py\n"
    "+++ b/multiplier.py\n"
    "@@ -1,2 +1,2 @@\n"
    " def multiply(a, b):\n"
    "-    return a + b\n"
    "+    return a * b\n"
)

#: A diff aimed at the operator-held test itself — the cheat. Not a hypothetical: rewriting the
#: assertion is the most obvious way to make a failing test pass, and it is cheat 1 of the
#: adversarial corpus. STRICT refuses it at `patch-scope`; this file's job is to prove the
#: extractor does not disarm that refusal on the way in.
HELD_TEST_DIFF = (
    f"diff --git a/{HELD_TEST_PATH} b/{HELD_TEST_PATH}\n"
    f"--- a/{HELD_TEST_PATH}\n"
    f"+++ b/{HELD_TEST_PATH}\n"
    "@@ -1,2 +1,2 @@\n"
    " def test_adds():\n"
    "-    assert add(2, 2) == 4\n"
    "+    assert True\n"
)

#: Inputs that contain no diff at all, each paired with the shape of model behaviour it stands
#: for. Parametrised together because AC4 is a statement about the whole class — *every* no-diff
#: input yields the no-diff outcome — and a class is not established by one example.
NO_DIFF_INPUTS = [
    pytest.param("", id="empty-string"),
    pytest.param("   \n\n\t\n  ", id="whitespace-only"),
    pytest.param(
        "I would fix this by changing the sign in `add`, which currently subtracts.\n"
        "The tests should then pass.\n",
        id="prose-only",
    ),
    pytest.param(
        "Here is the fixed function:\n\n```python\ndef add(a, b):\n    return a + b\n```\n",
        id="fenced-block-with-no-diff",
    ),
    pytest.param(
        "```diff\nI'll write the patch now.\n```\n",
        id="fence-labelled-diff-containing-none",
    ),
]


def held_task() -> Task:
    """A `Task` whose `test_blobs` holds `HELD_TEST_PATH`. Built, not mocked.

    The extractor never sees a `Task` — it takes text and returns text, which is exactly why it
    cannot be trusted to police scope. The task is constructed anyway so the adversarial test
    asserts against the *same string a real manifest would hold*, rather than against a literal
    that could drift away from what `test_blobs` is keyed by.
    """
    return Task(
        task_id="held-test-cheat",
        source="b",
        repo_url="/does/not/matter",
        base_commit="0" * 40,
        environment=Environment(python="python3.12", pins=(), import_roots=(".",)),
        problem_statement="add() subtracts instead of adding",
        fail_to_pass=(f"{HELD_TEST_PATH}::test_adds",),
        pass_to_pass=(),
        test_blobs={HELD_TEST_PATH: b"def test_adds():\n    assert add(2, 2) == 4\n"},
        provenance={},
    )


def git(
    args: list[str], *, cwd: Path, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Run git with the machine's configuration switched off, the way `repo.py` does.

    Same reasoning as `whetstone.verify.repo._git`: a developer's `~/.gitconfig` carrying
    `apply.whitespace=fix`, a `hooksPath`, or a clean/smudge filter would let this test answer a
    different question on a different laptop.
    """
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        input=stdin,
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_TERMINAL_PROMPT": "0",
            "HOME": str(cwd),
        },
        check=False,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A one-file git repository whose content `GOOD_DIFF` applies cleanly to.

    Real git, not a stub, because the question this fixture exists to answer — *would the reward
    path accept the string the extractor produced* — has exactly one authority, and it is the
    `git apply` that `whetstone.verify.repo` calls.
    """
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "adder.py").write_text("def add(a, b):\n    return a - b\n")
    assert git(["init", "--quiet", "."], cwd=checkout).returncode == 0
    assert git(["add", "adder.py"], cwd=checkout).returncode == 0
    committed = git(
        ["-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "base"],
        cwd=checkout,
    )
    assert committed.returncode == 0, committed.stderr
    return checkout


# --------------------------------------------------------------------------------------------
# AC4 — a non-diff response is reported as such, never as an empty patch.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("text", NO_DIFF_INPUTS)
def test_output_containing_no_diff_yields_the_no_diff_outcome(text: str) -> None:
    """Prose, emptiness, whitespace and diff-free fences all reach the same explicit outcome."""
    result = extract_patch(text)

    assert isinstance(result, NoDiff), (
        f"extraction of {text!r} returned {result!r} rather than a NoDiff.\n\n"
        "WHY THIS IS A FAILURE: there is no diff in that text, so any patch-shaped value handed"
        " on from here is one the harness invented. It would be graded — and whatever verdict it"
        " earned would be attributed to the base model, which never produced it."
    )


@pytest.mark.parametrize("text", NO_DIFF_INPUTS)
def test_a_no_diff_outcome_has_no_diff_to_hand_on(text: str) -> None:
    """The type-level assertion AC4 asks for: `NoDiff` cannot be mistaken for an empty patch.

    Distinctness of the two classes is necessary but not sufficient. What actually protects the
    number is that a caller which reaches for `.diff` on a no-diff outcome **crashes** instead of
    receiving `""` — so the confusion cannot be introduced later by a caller, only by rewriting
    this contract on purpose.
    """
    result = extract_patch(text)

    assert not hasattr(result, "diff"), (
        f"the no-diff outcome for {text!r} exposes a `.diff` attribute: {result!r}.\n\n"
        "WHY THIS IS A FAILURE: the moment a no-diff result can answer `.diff`, the answer is"
        " almost certainly the empty string, and `verify_strict(task, '')` is charged FAIL at"
        " patch-apply — the same status a wrong fix earns. A run where the extractor was broken"
        " would then be reported as a run where every base failed every task, which is exactly"
        " P1's pivot signal (docs/ROADMAP.md:387) forged by a bug."
    )
    assert Extracted is not NoDiff and not issubclass(NoDiff, Extracted), (
        "NoDiff and Extracted are not distinct types.\n\n"
        "WHY THIS IS A FAILURE: aspect 2 has to branch on which outcome it got in order to count"
        " no-diff responses separately from patch-apply failures (PRD M2). If one is a subclass"
        " of the other, an `isinstance` branch silently takes the wrong arm and the two counts"
        " merge — which is the visibility M2 exists to provide, destroyed at the source."
    )


@pytest.mark.parametrize("text", NO_DIFF_INPUTS)
def test_a_no_diff_outcome_carries_a_reason_a_human_can_act_on(text: str) -> None:
    """A reason, not a flag. Someone will read these when a candidate base scores zero.

    The realistic use is triage: a base produces no diffs at all, and the person looking at the
    report needs to know within seconds whether the model wrote prose, wrote a fenced block the
    extractor did not recognise, or wrote nothing — because those are a prompt problem, an
    extractor problem, and a model problem respectively.
    """
    result = extract_patch(text)
    assert isinstance(result, NoDiff)

    assert len(result.reason.split()) >= 4, (
        f"the reason for {text!r} is not a sentence: {result.reason!r}.\n\n"
        "WHY THIS IS A FAILURE: a one-word reason ('none', 'empty') costs the reader the whole"
        " debugging session the reason exists to save. When a candidate base scores zero, this"
        " string is the only evidence distinguishing a broken harness from a weak model."
    )


def test_the_no_diff_reasons_distinguish_the_cases_rather_than_being_one_constant() -> None:
    """Anti-vacuity for the reason: a single fixed sentence would satisfy every check above.

    The triage value of the reason is entirely in its varying. This asserts that the extractor
    actually tells the cases apart — empty output, prose, and a fence containing no diff are
    three different problems with three different fixes.
    """
    reasons = []
    for text in ["", "just some prose about adding numbers\n", "```python\nx = 1\n```\n"]:
        result = extract_patch(text)
        assert isinstance(result, NoDiff)
        reasons.append(result.reason)

    assert len(set(reasons)) == len(reasons), (
        f"different no-diff inputs produced the same reason: {reasons!r}.\n\n"
        "WHY THIS IS A FAILURE: a constant reason is a flag wearing a sentence. It passes every"
        " assertion about being actionable while telling the reader nothing they did not already"
        " know from the outcome type, and the three failures it collapses have three different"
        " fixes: change the prompt, fix the extractor, or change the base."
    )


def test_an_extracted_result_is_never_the_empty_string() -> None:
    """The other half of AC4: `Extracted` is a promise there is something to grade.

    Watched most easily as its opposite — an extractor that returned `Extracted("")` on failure
    would satisfy every `isinstance` check in this file and reintroduce the exact confusion the
    two-case result was built to prevent.
    """
    for text in [f"Here you go:\n\n```diff\n{GOOD_DIFF}```\n", GOOD_DIFF]:
        result = extract_patch(text)
        assert isinstance(result, Extracted)
        assert result.diff.strip() != "", (
            f"extraction of {text!r} returned an empty Extracted.\n\n"
            "WHY THIS IS A FAILURE: `Extracted` means 'a diff was found'. An empty one is the"
            " empty patch arriving under the outcome type that says it is safe to grade —"
            " AC4's confusion, laundered through the type system rather than prevented by it."
        )


# --------------------------------------------------------------------------------------------
# AC5 — extraction is not credulous. THE ADVERSARIAL CASE.
# --------------------------------------------------------------------------------------------


def test_a_diff_that_edits_a_held_test_survives_extraction_verbatim() -> None:
    """The caught cheat must still be catchable. The extractor may not disarm `patch-scope`.

    A base that rewrites the operator's test instead of fixing the code is the canonical
    reward-hacking attempt, and this project's answer is that STRICT refuses it before anything
    runs (`strict.py:524-533`) and the refusal is counted. Every part of that depends on the
    held path still being in the patch when the verifier sees it.
    """
    task = held_task()
    held = next(iter(task.test_blobs))
    text = (
        "The test asserts the wrong thing, so I fixed the test:\n\n"
        f"```diff\n{HELD_TEST_DIFF}```\n"
    )

    result = extract_patch(text)

    assert isinstance(result, Extracted), (
        f"a diff aimed at {held!r} was not extracted at all: {result!r}.\n\n"
        "WHY THIS IS A FAILURE: refusing it here would count the cheat as 'the model produced no"
        " diff'. The published caught-cheat count would fall, the no-diff count would rise, and"
        " the single most important thing the harness can observe — a base attempting to edit"
        " the tests it is graded by — would be recorded as the base saying nothing."
    )
    assert held in result.diff, (
        f"the held path {held!r} is missing from the extracted diff:\n{result.diff}\n\n"
        "WHY THIS IS A FAILURE: the extractor sanitised the cheat. STRICT can only refuse what it"
        " can see, so a patch with the held path stripped or rewritten is graded on its remaining"
        " hunks — a caught cheat converted into an uncaught one. That is a reward-hacking"
        " mitigation implemented in the wrong layer, and its measurable effect is to quietly"
        " lower a number this project publishes as evidence of its own honesty."
    )
    assert result.diff == HELD_TEST_DIFF, (
        f"the extracted diff is not the diff the model emitted:\n{result.diff!r}\n"
        f"expected:\n{HELD_TEST_DIFF!r}\n\n"
        "WHY THIS IS A FAILURE: containing the held path is not enough — a hunk reordered,"
        " re-indented or partially dropped is still a patch the model did not write. The"
        " extractor's contract is to locate a diff, never to edit one, and any edit at all means"
        " what gets graded is the harness's opinion of the model's answer."
    )


def test_a_mixed_patch_keeps_both_the_held_hunk_and_the_source_hunk() -> None:
    """The subtler shape of the same cheat: a real fix with a test edit smuggled alongside it.

    An extractor tempted to 'clean up' would most plausibly drop only the offending hunk here,
    leaving a patch that looks entirely legitimate and passes. That single dropped hunk is the
    difference between a refusal at `patch-scope` and an uncounted, undetected success.
    """
    mixed = GOOD_DIFF + HELD_TEST_DIFF
    result = extract_patch(f"```diff\n{mixed}```\n")

    assert isinstance(result, Extracted)
    assert result.diff == mixed, (
        f"a mixed patch was altered in extraction:\n{result.diff!r}\n\n"
        "WHY THIS IS A FAILURE: dropping the held hunk turns a patch STRICT would refuse into a"
        " patch STRICT would grade — and possibly pass. The cheat then never appears in the"
        " caught-cheat count, and the base is credited with a task it solved by editing the test."
    )


# --------------------------------------------------------------------------------------------
# Locating the diff: fences, bare output, ordering, trailing prose.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("info", ["diff", "patch", ""])
def test_a_fenced_diff_is_extracted_whatever_the_fence_is_labelled(info: str) -> None:
    """Models label the fence `diff`, `patch`, or nothing at all. All three are the same event."""
    result = extract_patch(f"Here is the patch:\n\n```{info}\n{GOOD_DIFF}```\n")

    assert isinstance(result, Extracted) and result.diff == GOOD_DIFF, (
        f"a diff in a ```{info} fence was not extracted cleanly: {result!r}.\n\n"
        "WHY THIS IS A FAILURE: the fence's info string is decoration the model chose. Keying"
        " extraction on it makes the measured score of a base partly a measure of its formatting"
        " habits, which is not what the bake-off is comparing."
    )


def test_a_bare_diff_with_no_fence_at_all_is_extracted() -> None:
    """Plenty of models answer with the raw diff and nothing else. That is a valid answer."""
    result = extract_patch(GOOD_DIFF)

    assert isinstance(result, Extracted) and result.diff == GOOD_DIFF, (
        f"an unfenced diff was not extracted: {result!r}.\n\n"
        "WHY THIS IS A FAILURE: requiring a fence would score a base on whether it wraps its"
        " output in markdown. A base that answers with the patch and nothing else has done the"
        " task perfectly, and recording that as 'no diff' understates it by every task it solved."
    )


def test_prose_after_a_diff_is_not_part_of_the_extracted_patch() -> None:
    """Models explain themselves afterwards. The explanation is not part of the patch.

    Note the reason this is worth an assertion even though `git apply` tolerates trailing text
    (measured: a patch with a paragraph appended still passes `--check`): what follows a diff is
    often a markdown bullet list, and a line beginning `- ` is indistinguishable from a deletion
    line to anything that is not counting hunk lines. Ending the diff where the hunk's declared
    line count ends is what makes that safe.
    """
    text = (
        f"{GOOD_DIFF}\n"
        "That fixes the sign error.\n"
        "- I also considered renaming the function\n"
        "- but that would break callers\n"
    )

    result = extract_patch(text)

    assert isinstance(result, Extracted) and result.diff == GOOD_DIFF, (
        f"trailing prose was absorbed into the patch: {result!r}.\n\n"
        "WHY THIS IS A FAILURE: a bullet list after a diff reads as extra deletion lines. git"
        " then rejects the patch as corrupt, the task is charged FAIL at patch-apply, and a base"
        " that produced a correct fix is scored as having produced a broken one — a formatting"
        " habit converted into a capability difference."
    )


def test_multiple_fenced_blocks_take_the_first_well_formed_diff() -> None:
    """The documented, deterministic choice: **the first well-formed diff, in document order**.

    Justification: it is the only rule that needs no judgement about which of two diffs is
    better. Any 'best' rule is the harness choosing the model's answer for it, and a 'last'
    rule rewards a model for restating itself. Asserted rather than assumed, because an
    implementation that happened to pick the last one would pass every other test in this file.
    """
    text = (
        f"First attempt:\n\n```diff\n{GOOD_DIFF}```\n\n"
        f"Actually, this one:\n\n```diff\n{OTHER_DIFF}```\n"
    )

    result = extract_patch(text)

    assert isinstance(result, Extracted) and result.diff == GOOD_DIFF, (
        f"the first fenced diff was not the one extracted: {result!r}.\n\n"
        "WHY THIS IS A FAILURE: with two diffs present, an unpinned rule makes the graded patch"
        " an implementation detail. Two candidate bases could then be separated by which one"
        " restated its answer, and the bake-off's whole output is a comparison between bases."
    )


def test_a_diff_free_block_before_a_diff_block_does_not_stop_extraction() -> None:
    """'First well-formed diff' means first *diff*, not first fenced block.

    The common real shape: a model shows the offending function in a ```python block, then the
    patch. A rule that took the first fence and gave up would report no diff for one of the most
    ordinary answers a model can give.
    """
    text = (
        "The current implementation is:\n\n```python\ndef add(a, b):\n    return a - b\n```\n\n"
        f"Here is the fix:\n\n```diff\n{OTHER_DIFF}```\n"
    )

    result = extract_patch(text)

    assert isinstance(result, Extracted) and result.diff == OTHER_DIFF, (
        f"a leading non-diff code block defeated extraction: {result!r}.\n\n"
        "WHY THIS IS A FAILURE: showing the broken code and then the patch is standard model"
        " behaviour. Recording it as 'no diff' would understate every base that explains itself"
        " and would flatter whichever base happens to be tersest."
    )


def test_a_bare_diff_before_a_fenced_diff_wins_because_it_comes_first() -> None:
    """Document order is over *all* candidates, not fences first and bare text second.

    This pins the rule where the two plausible readings disagree. It matters because 'fences
    first' is the easier implementation, and nothing else in this file would notice it.
    """
    text = f"{GOOD_DIFF}\nOn reflection, maybe:\n\n```diff\n{OTHER_DIFF}```\n"

    result = extract_patch(text)

    assert isinstance(result, Extracted) and result.diff == GOOD_DIFF, (
        f"document order was not honoured across fenced and unfenced candidates: {result!r}.\n\n"
        "WHY THIS IS A FAILURE: 'the first well-formed diff' is the published rule, and a reader"
        " reproducing a result has to be able to apply it by eye. An implementation that quietly"
        " preferred fenced candidates would follow a different rule than the one written down."
    )


def test_extraction_is_deterministic_for_the_same_text() -> None:
    """Same input, same output, every time — the property the whole comparison rests on.

    A generator is held to determinism (`test_generator_contract.py`); an extractor that reached
    for a set, a dict ordering or a regex cache would undo that one layer later, and the run's
    score would depend on the order tasks happened to be processed in.
    """
    text = f"Two options:\n\n```diff\n{GOOD_DIFF}```\n\n```diff\n{OTHER_DIFF}```\n"
    results = [extract_patch(text) for _ in range(5)]

    assert all(result == results[0] for result in results), (
        f"repeated extraction of one input disagreed: {results!r}.\n\n"
        "WHY THIS IS A FAILURE: the bake-off compares bases by counting PASSes. If the same model"
        " output can be turned into two different patches, the difference between two candidate"
        " bases is partly a difference between two runs of this function."
    )


# --------------------------------------------------------------------------------------------
# Malformed and awkward output — the decisions, each with its justification.
# --------------------------------------------------------------------------------------------


def test_crlf_output_is_extracted_and_its_line_endings_are_left_alone() -> None:
    """DECISION: CRLF is extracted **verbatim**; the extractor does not rewrite line endings.

    Measured, so the consequence is stated rather than guessed: `git apply` parses a CRLF patch
    without complaint and then fails to match context against an LF working tree — *"patch does
    not apply"*, which STRICT charges as `FAIL` at `patch-apply`. Normalising would make such a
    patch apply, and that is exactly the argument against it: `\\r\\n` at the end of an added
    line is part of what the patch writes into the file, so converting it is the extractor
    deciding what the model meant to write. The contract is to locate a diff, not to author one.

    The failure stays **visible** rather than silent, which is what PRD M2 requires and what R1's
    mitigation actually is: a base emitting CRLF wholesale appears in the report as a cliff in
    the `patch-apply` count, not as a base that solved nothing.
    """
    result = extract_patch(f"```diff\r\n{GOOD_DIFF.replace(chr(10), chr(13) + chr(10))}```\r\n")

    assert isinstance(result, Extracted), (
        f"CRLF output was reported as containing no diff: {result!r}.\n\n"
        "WHY THIS IS A FAILURE: there is plainly a diff there. Calling it 'no diff' would file a"
        " line-ending problem under the one outcome that means the model said nothing, and PRD"
        " M2's separation of no-diff responses from patch failures would be reporting a fiction."
    )
    assert "\r\n" in result.diff, (
        f"the extracted diff had its line endings rewritten: {result.diff!r}.\n\n"
        "WHY THIS IS A FAILURE: this is sanitising, in the mildest-looking possible costume. The"
        " terminator of an added line is content the patch writes to disk, so rewriting it makes"
        " the graded patch one the model did not emit — and once this layer is willing to repair"
        " content, the argument against repairing a held-test hunk is only a matter of degree."
    )


def test_absolute_paths_are_extracted_rather_than_refused_or_rewritten() -> None:
    """DECISION: a diff with absolute paths is `Extracted`, unchanged. It is a diff, aimed wrong.

    Measured: git parses it and then reports *"No such file or directory"* — because `git apply`
    runs with `cwd=checkout` and strips one leading component (`repo.py`), so `/Users/me/repo/x.py`
    becomes `Users/me/repo/x.py` and matches nothing. STRICT charges `FAIL` at `patch-apply`.

    Why not `NoDiff`: the two outcomes answer different questions. `NoDiff` means *the model
    produced no patch*; this model produced a patch and got the root wrong. Filing it as `NoDiff`
    would corrupt the one distinction AC4 exists to protect. Why not rewrite the paths to
    `a/…`/`b/…`: the extractor does not know the checkout root, so it would be guessing which
    prefix to strip — and a wrong guess produces a patch that applies **somewhere else in the
    tree**, which is worse than one that does not apply at all.
    """
    absolute = GOOD_DIFF.replace("a/adder.py", "/Users/me/repo/adder.py").replace(
        "b/adder.py", "/Users/me/repo/adder.py"
    )

    result = extract_patch(f"```diff\n{absolute}```\n")

    assert isinstance(result, Extracted) and result.diff == absolute, (
        f"an absolute-path diff was not passed through unchanged: {result!r}.\n\n"
        "WHY THIS IS A FAILURE: either half of the alternative is wrong. Reporting NoDiff records"
        " a model that wrote a patch as one that wrote nothing, blurring the AC4 distinction."
        " Rewriting the paths has the extractor guessing a checkout root it was never told, and"
        " a lucky guess is worse than an honest patch-apply failure — it grades a patch aimed"
        " somewhere the model never aimed it."
    )


def test_output_truncated_mid_hunk_is_extracted_rather_than_reported_as_no_diff() -> None:
    """DECISION: a hunk that stops early is `Extracted`. The model hit its token limit.

    Measured: git answers a short hunk with *"corrupt patch at line 8"*, so STRICT charges `FAIL`
    at `patch-apply`. That is the honest record — the model attempted a patch and ran out of
    budget — and it is separable in the report from a model that produced no patch at all. An
    extractor that repaired the hunk by padding it would be inventing context lines, which is
    authoring a patch and grading the harness.
    """
    truncated = (
        "diff --git a/adder.py b/adder.py\n"
        "--- a/adder.py\n"
        "+++ b/adder.py\n"
        "@@ -1,4 +1,4 @@\n"
        " def add(a, b):\n"
        "-    return a - b\n"
    )

    result = extract_patch(f"```diff\n{truncated}")

    assert isinstance(result, Extracted), (
        f"truncated output was reported as containing no diff: {result!r}.\n\n"
        "WHY THIS IS A FAILURE: 'ran out of tokens mid-patch' and 'wrote prose instead of a"
        " patch' have different fixes — a longer generation budget versus a different prompt or"
        " a different base. Collapsing them into one outcome hides which one is happening."
    )
    assert "return a - b" in result.diff, (
        f"the truncated hunk was altered on the way out: {result.diff!r}.\n\n"
        "WHY THIS IS A FAILURE: padding or trimming a short hunk means the graded patch contains"
        " lines the model never emitted. git's refusal is the correct outcome here, and it is"
        " only correct if what git sees is what the model wrote."
    )


def test_a_diff_header_with_no_hunk_is_a_no_diff_that_says_so() -> None:
    """A patch with zero hunks changes nothing — but the reason must name what was seen.

    The boundary case for the decision above: truncation *before* the first `@@` leaves a file
    header and nothing else. There is no hunk to grade, so this is `NoDiff` — but a reason that
    said only 'no diff found' would send the reader looking at the prompt when the actual problem
    is the generation budget.
    """
    result = extract_patch("```diff\ndiff --git a/adder.py b/adder.py\n--- a/adder.py\n")

    assert isinstance(result, NoDiff), (
        f"a hunkless diff header was extracted as a patch: {result!r}.\n\n"
        "WHY THIS IS A FAILURE: a patch with no hunks instructs git to change nothing. Handing"
        " one on as `Extracted` means the harness asserted there was something to grade when"
        " there was not."
    )
    assert "hunk" in result.reason or "@@" in result.reason, (
        f"the reason does not say what was missing: {result.reason!r}.\n\n"
        "WHY THIS IS A FAILURE: the model started a patch and stopped. That is a token-budget"
        " problem, and a reason indistinguishable from 'the model wrote prose' points whoever"
        " reads it at the prompt instead."
    )


# --------------------------------------------------------------------------------------------
# Round-trip realism: is the string we produce the kind of string the reward path can use?
# --------------------------------------------------------------------------------------------


def test_an_extracted_diff_is_accepted_by_git_apply(repo: Path) -> None:
    """The end-to-end shape of the happy path, checked by the only authority that matters.

    Every other test in this file compares strings. This one asks `git apply --check` — the same
    program `whetstone.verify.repo.apply_patch` calls — whether the extracted text is a patch it
    will accept against a real checkout. Without this, the extractor could satisfy every equality
    assertion above and still produce something the reward path refuses.
    """
    result = extract_patch(f"Here is the fix:\n\n```diff\n{GOOD_DIFF}```\n\nHope that helps!\n")
    assert isinstance(result, Extracted)

    checked = git(["apply", "--check", "-"], cwd=repo, stdin=result.diff)

    assert checked.returncode == 0, (
        f"git refused the extracted patch: {checked.stderr.strip()!r}\n{result.diff!r}\n\n"
        "WHY THIS IS A FAILURE: `whetstone.verify.repo` applies patches with this exact program."
        " A string that satisfies every assertion in this file but that git will not accept is a"
        " harness that scores every task FAIL at patch-apply — the all-zero run that PRD risk R1"
        " names, produced by the harness and attributed to the model."
    )


def test_a_real_multi_file_diff_survives_prose_and_bullet_points_around_it(tmp_path: Path) -> None:
    """The realistic shape, with the patch produced by `git diff` rather than by hand.

    Every other fixture here is hand-written, and this file has already been bitten once by that:
    the constants above originally declared hunk counts that did not match their bodies, and only
    the `git apply` round trip noticed. So this case takes git's own output — two files, three
    hunks, real `index` lines — wraps it the way a model would, and asserts three things at once:
    the extracted region is byte-identical to what git produced, git will apply it, and **both**
    files are still in it.

    The bullet list is the adversarial part. `- the sign in add() was wrong` is a deletion line to
    any parser that follows prefixes rather than counting, so a naive extractor absorbs the
    explanation into the final hunk and git rejects the whole patch as corrupt — turning a base
    that produced a correct two-file fix into a base that scored zero on the task.
    """
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    broken = "def add(a, b):\n    return a - b\n\n\ndef mul(a, b):\n    return a + b\n"
    (checkout / "m.py").write_text(broken)
    (checkout / "n.py").write_text("x = 1\ny = 2\nz = 3\n")
    assert git(["init", "--quiet", "."], cwd=checkout).returncode == 0
    assert git(["add", "-A"], cwd=checkout).returncode == 0
    committed = git(
        ["-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "base"],
        cwd=checkout,
    )
    assert committed.returncode == 0, committed.stderr

    fixed = "def add(a, b):\n    return a + b\n\n\ndef mul(a, b):\n    return a * b\n"
    (checkout / "m.py").write_text(fixed)
    (checkout / "n.py").write_text("x = 1\ny = 22\nz = 3\n")
    genuine = git(["diff"], cwd=checkout).stdout
    assert git(["checkout", "--", "."], cwd=checkout).returncode == 0
    assert genuine.count("diff --git") == 2, genuine

    result = extract_patch(
        f"I found two bugs. Here is the patch:\n\n```diff\n{genuine}```\n\n"
        "Notes:\n- the sign in add() was wrong\n- mul() was adding instead of multiplying\n"
    )

    assert isinstance(result, Extracted) and result.diff == genuine, (
        f"a real git diff did not survive extraction unchanged:\n{result!r}\n\n"
        "WHY THIS IS A FAILURE: this is the ordinary case, not an edge case — a multi-file patch"
        " with prose around it is what a base model's answer looks like. If the harness cannot"
        " carry that from the model to the verifier byte-for-byte, every number the bake-off"
        " produces is a measurement of the harness."
    )

    checked = git(["apply", "--check", "-"], cwd=checkout, stdin=result.diff)
    assert checked.returncode == 0, (
        f"git refused the extracted multi-file patch: {checked.stderr.strip()!r}\n\n"
        "WHY THIS IS A FAILURE: the trailing bullet list reads as deletion lines to a parser that"
        " goes by prefixes. Absorbing it corrupts the patch, and a base that wrote a correct fix"
        " and then explained itself is scored FAIL at patch-apply for the explanation."
    )

    numstat = git(["apply", "--numstat", "-"], cwd=checkout, stdin=result.diff).stdout
    assert "m.py" in numstat and "n.py" in numstat, (
        f"the extracted patch does not touch both files git's diff touched: {numstat!r}\n\n"
        "WHY THIS IS A FAILURE: losing the second file is the silent version of this bug — the"
        " patch still applies, so nothing complains, and the task is graded on half the fix. That"
        " is the same failure mode as dropping a held-test hunk, with the same cause: a harness"
        " that edits what the model wrote."
    )


def test_a_diff_the_model_left_unterminated_is_still_accepted_by_git(repo: Path) -> None:
    """THE ONE REPAIR: a missing final newline is supplied. Measured, not assumed.

    Models routinely stop generating without a trailing newline, and the round-trip consequence
    is severe: git answers an unterminated final line with *"corrupt patch at line 8"* and
    refuses to parse the patch at all. So the extracted diff is terminated if it is not already.

    This is the only edit this function makes to a diff's bytes, and it is defensible on exactly
    the ground that the ban on sanitising is about: appending a line terminator cannot change
    which paths a diff touches, cannot drop a hunk, and therefore cannot turn a patch STRICT
    would refuse at `patch-scope` into one it would grade.
    """
    unterminated = GOOD_DIFF.rstrip("\n")
    rejected = git(["apply", "--check", "-"], cwd=repo, stdin=unterminated)
    assert rejected.returncode != 0, (
        "git accepted a patch with no final newline, so this test proves nothing.\n\n"
        "WHY THIS IS A FAILURE: the repair below is justified by git's refusal of unterminated"
        " patches. If git no longer refuses them, the repair is unmotivated and this test has"
        " become a tautology — which is the same class of silent lie as a vacuous assertion."
    )

    result = extract_patch(f"```diff\n{unterminated}")
    assert isinstance(result, Extracted)

    checked = git(["apply", "--check", "-"], cwd=repo, stdin=result.diff)

    assert checked.returncode == 0, (
        f"git refused the extracted patch: {checked.stderr.strip()!r}\n{result.diff!r}\n\n"
        "WHY THIS IS A FAILURE: a model that stops one newline early has written a correct fix."
        " Charging it FAIL at patch-apply for a missing line terminator measures the model's"
        " stopping condition rather than its ability, and would do so for every task it solved."
    )
    assert result.diff.rstrip("\n") == unterminated, (
        f"more than the terminator changed: {result.diff!r} vs {unterminated!r}.\n\n"
        "WHY THIS IS A FAILURE: the newline is the only repair this function is permitted. Any"
        " other difference means the extractor edited the patch's content, and the argument that"
        " it never disarms a patch-scope refusal rests on it doing nothing of the kind."
    )
