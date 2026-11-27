"""The second repair trigger: a diff git refuses is re-asked, named by a finite class.

`torch-8b-pascal-4bit-003` cut `NO_DIFF` from 70.1% to 9.9% and raised `NOT_APPLIED` to 263 of
304 draws (86.5%): the model now writes a diff, and its context lines or paths do not match the
task's checkout. The existing repair fires only after a patch **applies** and its tests fail
(`scoring.py:477-499`), so those 263 draws are never re-asked.

This module pins the second trigger:

* **The class vocabulary is finite.** `git apply`'s refusal is classified into exactly
  `CONTEXT_MISMATCH`, `PATH_MISSING`, `MALFORMED` and the `UNRECOGNISED` catch-all, by fixed
  substrings over git's own message. The free-form stderr is never put into a prompt — that
  would make the prompt set unbounded and the seal unfreezable (spec B1).
* **Every class x task repair prompt is posed at freeze time** and filed under its task, and the
  seal accepts exactly those. An unfrozen one still raises `ContractChanged`, as before.
* **The budget is shared.** A `(candidate, task)` gets at most `repair` repair prompts in total,
  whether they answer a `NOT_SOLVED` or a `NOT_APPLIED` draw.
* **Every repair draw is recorded** by the existing `"repair"` row, and its prompt names the
  class, so the transcript says which failure was being answered.
* **Nothing is loosened.** A repaired diff is applied and verified by the same STRICT verifier
  as a first attempt; a repaired pass is a strict `PASS`.

No model, no `mlx`, no network: the engine is a `StubGenerator` and the fixture is a two-commit
synthetic donor.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fixtures.repos import make_patch
from fixtures.repos.mined import MINED_CALC_FIXED, build_mined_task

from bakeoff.test_scoring import STILL_BROKEN, TIMEOUT, WRONG_CONTEXT, posed
from whetstone.bakeoff import retry as retry_module
from whetstone.bakeoff.generator import StubGenerator
from whetstone.bakeoff.rendering import prompt_hash, render_prompt
from whetstone.bakeoff.retry import (
    APPLY_DIAGNOSES,
    APPLY_REPAIR_INSTRUCTION,
    FAILURE_OUTCOMES,
    REPAIR_INSTRUCTION,
    REPAIR_TEST_INSTRUCTION,
    ApplyFailure,
    Retry,
    apply_repair_prompt,
    classify_apply_failure,
    repair_prompt,
    repair_template_sha256,
)
from whetstone.bakeoff.run import ContractChanged, Recording, Sealed, freeze
from whetstone.bakeoff.scoring import Interpreters, Outcome, score
from whetstone.bakeoff.sources import oracle_sources
from whetstone.bakeoff.transcript import Transcript
from whetstone.verify.task import Task
from whetstone.verify.verdict import Status

#: A stand-in first-attempt prompt. The builders append to whatever they are handed.
FIRST = "Fix the bug.\n\nThe failing tests must pass.\n"

#: Real `git apply` stderr, captured on this machine. The classifier reads git's own message;
#: the wrapper STRICT adds around it (`the patch did not apply: …; an unusable patch is a wrong
#: answer`) travels with the sample in `test_the_classifier_reads_the_rolled_up_detail`.
GIT_STDERR = {
    ApplyFailure.CONTEXT_MISMATCH: (
        "error: patch failed: calc.py:1\nerror: calc.py: patch does not apply"
    ),
    ApplyFailure.PATH_MISSING: "error: calc.py: No such file or directory",
    ApplyFailure.MALFORMED: "error: corrupt patch at line 5",
}

#: A diff whose declared hunk counts are right but whose context line is not in the checkout.
#: `git apply --numstat` reads it and `git apply` refuses it at the preimage search.
CONTEXT_REFUSED = WRONG_CONTEXT

#: A well-formed diff aimed at a path the checkout does not carry. `--numstat` reports it and
#: `git apply` answers "No such file or directory".
MISSING_PATH = """\
```diff
--- a/nonexistent_module.py
+++ b/nonexistent_module.py
@@ -1,2 +1,2 @@
-def helper():
-    return 1
+def helper():
+    return 2
```
"""

#: A diff git cannot parse: the header promises five old lines and the body carries one.
MALFORMED_PATCH = """\
```diff
--- a/calc.py
+++ b/calc.py
@@ -1,5 +1,5 @@
 def add(a, b):
-    return a - b
+    return a + b
```
"""


class _Observed:
    """A `Generator` that logs every prompt, then answers from a stub table."""

    def __init__(self, answers: dict[str, str]) -> None:
        self.inner = StubGenerator(answers)
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.inner.generate(prompt)


def _task(tmp_path: Path, task_id: str = "alpha") -> Task:
    return build_mined_task(
        tmp_path / f"donor-{task_id}", task_id=task_id, subject=f"Fix addition ({task_id})"
    ).task


def _posed(task: Task) -> str:
    sources = oracle_sources(task, pool=None)
    assert sources.files is not None, sources.reason
    return render_prompt(task, sources.files)


def _records(transcript: Transcript) -> list[dict[str, object]]:
    return [json.loads(line) for line in transcript.path.read_text(encoding="utf-8").splitlines()]


# --------------------------------------------------------------------------------------------
# The class vocabulary: finite, total, deterministic, read from git's own stderr.
# --------------------------------------------------------------------------------------------


def test_the_apply_failure_vocabulary_is_finite_and_named() -> None:
    """Exactly four names, and every one of them is a class the freeze can pose."""
    assert {failure.value for failure in ApplyFailure} == {
        "CONTEXT_MISMATCH",
        "PATH_MISSING",
        "MALFORMED",
        "UNRECOGNISED",
    }, (
        "WHY THIS IS A FAILURE: the apply-failure vocabulary is not the declared finite set. "
        "A class the freeze cannot enumerate is a repair prompt the seal cannot accept"
    )
    assert set(APPLY_DIAGNOSES) == set(ApplyFailure), (
        "WHY THIS IS A FAILURE: a class has no fixed diagnosis sentence, so a repair for it "
        "cannot be pre-rendered at freeze time"
    )


@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        (GIT_STDERR[ApplyFailure.CONTEXT_MISMATCH], ApplyFailure.CONTEXT_MISMATCH),
        (
            "error: while searching for:\n    return a - b\n"
            "error: patch failed: calc.py:1\n"
            "error: calc.py: patch does not apply",
            ApplyFailure.CONTEXT_MISMATCH,
        ),
        (GIT_STDERR[ApplyFailure.PATH_MISSING], ApplyFailure.PATH_MISSING),
        (
            "error: calc.py: does not exist in index",
            ApplyFailure.PATH_MISSING,
        ),
        (GIT_STDERR[ApplyFailure.MALFORMED], ApplyFailure.MALFORMED),
        (
            'error: No valid patches in input (allow with "--allow-empty")',
            ApplyFailure.MALFORMED,
        ),
        (
            "the patch could not be parsed: error: git diff header lacks filename information "
            "when removing 1 leading pathname component",
            ApplyFailure.MALFORMED,
        ),
        (
            "error: calc.py: already exists in working directory",
            ApplyFailure.UNRECOGNISED,
        ),
        ("", ApplyFailure.UNRECOGNISED),
    ],
    ids=[
        "patch-failed",
        "while-searching",
        "no-such-file",
        "does-not-exist-in-index",
        "corrupt-patch",
        "no-valid-patches",
        "could-not-be-parsed",
        "already-exists",
        "empty",
    ],
)
def test_the_classifier_reads_real_git_apply_stderr(stderr: str, expected: ApplyFailure) -> None:
    """Every sample maps to its class, and to the same class twice.

    The classifier is a pure function of the message git emitted. It never runs git and never
    copies the message into a prompt; it picks one fixed class, which is what makes the prompt
    set finite.
    """
    assert classify_apply_failure(stderr) is expected, (
        f"WHY THIS IS A FAILURE: {stderr!r} classified as "
        f"{classify_apply_failure(stderr)!r}, not {expected!r}. The repair would name the wrong "
        "shape, and the class is the only thing the repair prompt may carry"
    )
    assert classify_apply_failure(stderr) is expected, (
        "WHY THIS IS A FAILURE: the classifier is not deterministic over the same stderr"
    )


def test_the_classifier_reads_the_rolled_up_detail() -> None:
    """STRICT wraps git's message; the classifier sees the same class through the wrapper."""
    detail = (
        "the patch did not apply: error: patch failed: calc.py:1\n"
        "error: calc.py: patch does not apply; an unusable patch is a wrong answer"
    )
    assert classify_apply_failure(detail) is ApplyFailure.CONTEXT_MISMATCH


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        (CONTEXT_REFUSED, ApplyFailure.CONTEXT_MISMATCH),
        (MISSING_PATH, ApplyFailure.PATH_MISSING),
        (MALFORMED_PATCH, ApplyFailure.MALFORMED),
    ],
    ids=["context", "path", "malformed"],
)
def test_a_real_refusal_reaches_its_class(
    tmp_path: Path, answer: str, expected: ApplyFailure
) -> None:
    """The live detail STRICT records classifies as the same class, through real git.

    The samples above are git's words; this runs the extractor and `git apply --numstat`/`apply`
    on three real diffs, so the classifier is exercised on the exact `detail` a run stores rather
    than only on strings copied out of a terminal.
    """
    fixture = build_mined_task(tmp_path / "task")
    record = score(
        candidate="refused",
        task=fixture.task,
        generator=StubGenerator({posed(fixture.task): answer}),
        sandbox_root=tmp_path / "runs" / "refused",
        timeout=TIMEOUT,
        interpreters=Interpreters(workspace=tmp_path / "envs"),
    )

    assert record.outcome is Outcome.NOT_APPLIED, (
        f"the fixture must reach git's refusal; got {record.outcome!r} ({record.detail!r})"
    )
    assert classify_apply_failure(record.detail) is expected, (
        f"WHY THIS IS A FAILURE: git refused with {record.detail!r}, which classified as "
        f"{classify_apply_failure(record.detail)!r}, not {expected!r}"
    )


# --------------------------------------------------------------------------------------------
# The prompt: first prompt + fixed instruction + one fixed class sentence. No stderr, no holes.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("failure", ApplyFailure)
def test_apply_repair_prompt_is_the_first_prompt_and_one_fixed_sentence(
    failure: ApplyFailure,
) -> None:
    repaired = apply_repair_prompt(FIRST, failure)

    assert repaired == (
        FIRST + "\n\n" + APPLY_REPAIR_INSTRUCTION + "\n" + APPLY_DIAGNOSES[failure]
    ), (
        f"WHY THIS IS A FAILURE: apply_repair_prompt({FIRST!r}, {failure!r}) returned "
        f"{repaired!r}. The repair prompt must be the first prompt plus the fixed apply "
        "instruction plus exactly one class sentence, or the freeze cannot pre-render it"
    )
    assert apply_repair_prompt(FIRST, failure) == repaired, (
        "WHY THIS IS A FAILURE: the apply repair prompt is not a pure function of its two "
        "arguments, so the runtime prompt cannot be the one frozen before the run"
    )
    assert "patch failed" not in repaired and "No such file" not in repaired, (
        "WHY THIS IS A FAILURE: the repair prompt copied free-form stderr. That makes the "
        "prompt set unbounded and the seal unfreezable (spec B1)"
    )


def test_the_apply_repair_vocabulary_is_finite_fixed_and_constant() -> None:
    """No format hole, no digit, no empty sentence — the same rule the retry vocabulary holds."""
    material = [APPLY_REPAIR_INSTRUCTION, *APPLY_DIAGNOSES.values()]
    for part in material:
        assert part.strip() == part and len(part) > 20, (
            f"WHY THIS IS A FAILURE: a fixed part of the apply repair prompt is empty or "
            f"degenerate: {part!r}"
        )
        assert "{" not in part and "}" not in part, (
            f"WHY THIS IS A FAILURE: {part!r} carries a format placeholder, which is a template "
            "for an unbounded prompt set"
        )
        assert not any(char.isdigit() for char in part), (
            f"WHY THIS IS A FAILURE: {part!r} carries a number. A number would have to be "
            "derived from the failure, which makes the prompt unfreezable"
        )

    rendered = {apply_repair_prompt(FIRST, failure) for failure in ApplyFailure}
    assert len(rendered) == len(ApplyFailure), (
        "WHY THIS IS A FAILURE: two classes share a repair prompt, so the model is told to fix "
        "a shape it was not shown and the digest cannot tell them apart"
    )


def test_the_repair_template_digest_covers_the_apply_vocabulary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The published repair digest is the digest of both repair vocabularies."""
    material = "\n".join(
        (
            REPAIR_INSTRUCTION,
            REPAIR_TEST_INSTRUCTION,
            *FAILURE_OUTCOMES,
            APPLY_REPAIR_INSTRUCTION,
            *(sorted(APPLY_DIAGNOSES.values())),
        )
    )
    assert repair_template_sha256() == hashlib.sha256(material.encode("utf-8")).hexdigest(), (
        "WHY THIS IS A FAILURE: repair_template_sha256 is not the digest of the failure-class "
        "and apply-class material, so a run's published repair digest would not cover the "
        "prompts it actually posed"
    )

    before = repair_template_sha256()
    edited = {**APPLY_DIAGNOSES, ApplyFailure.MALFORMED: "git could not read it; rewrite it."}
    monkeypatch.setattr(retry_module, "APPLY_DIAGNOSES", edited)
    assert repair_template_sha256() != before, (
        "WHY THIS IS A FAILURE: editing an apply-class sentence did not move the repair "
        "template digest, so a template edit would not void the run (PRD M7b)"
    )


# --------------------------------------------------------------------------------------------
# The freeze: every class x task is posed under its task; the seal accepts those and only those.
# --------------------------------------------------------------------------------------------


def test_freeze_poses_every_apply_repair_class_for_every_task(tmp_path: Path) -> None:
    tasks = [_task(tmp_path, "alpha"), _task(tmp_path, "beta")]
    contract = freeze(tasks, repair=True)

    for task in tasks:
        first = _posed(task)
        for failure in ApplyFailure:
            repaired = apply_repair_prompt(first, failure)
            assert prompt_hash(repaired) in contract.posed, (
                f"WHY THIS IS A FAILURE: the frozen contract does not carry the {failure.value} "
                "repair prompt. The seal would refuse it at the first NOT_APPLIED, after the "
                "draws are already paid for"
            )
            assert contract.posed[prompt_hash(repaired)] == task.task_id, (
                f"WHY THIS IS A FAILURE: the {failure.value} repair prompt is filed under a "
                "different task, so the recorded completion would be attributed to a question "
                "it did not answer"
            )


def test_the_seal_accepts_frozen_apply_repairs_and_refuses_an_unfrozen_one(
    tmp_path: Path,
) -> None:
    task = _task(tmp_path)
    first = _posed(task)
    contract = freeze([task], repair=True)

    for failure in ApplyFailure:
        repaired = apply_repair_prompt(first, failure)
        sealed = Sealed(inner=StubGenerator({repaired: "ok"}), contract=contract)
        assert sealed.generate(repaired) == "ok", (
            f"WHY THIS IS A FAILURE: the sealed engine refused the frozen {failure.value} "
            "repair prompt"
        )

    unfrozen = freeze([task], repair=False)
    repaired = apply_repair_prompt(first, ApplyFailure.CONTEXT_MISMATCH)
    assert prompt_hash(repaired) not in unfrozen.posed, (
        "WHY THIS IS A FAILURE: the repair-disabled fixture froze an apply repair prompt, so "
        "this test would not exercise the refusal it claims to"
    )
    with pytest.raises(ContractChanged):
        Sealed(inner=StubGenerator({repaired: "ok"}), contract=unfrozen).generate(repaired)


# --------------------------------------------------------------------------------------------
# The score loop: NOT_APPLIED triggers the pre-posed repair, with a shared budget.
# --------------------------------------------------------------------------------------------


def test_a_not_applied_draw_is_repaired_and_a_repaired_pass_is_strict_pass(
    tmp_path: Path,
) -> None:
    fixture = build_mined_task(tmp_path / "task")
    prompt = posed(fixture.task)
    right = make_patch(fixture.donor, {"calc.py": MINED_CALC_FIXED}, at=fixture.parent)
    repaired = apply_repair_prompt(prompt, ApplyFailure.CONTEXT_MISMATCH)

    record = score(
        candidate="apply-repair",
        task=fixture.task,
        generator=StubGenerator({prompt: CONTEXT_REFUSED, repaired: right}),
        sandbox_root=tmp_path / "runs" / "apply-repair",
        timeout=TIMEOUT,
        interpreters=Interpreters(workspace=tmp_path / "envs"),
        repair=1,
    )

    assert record.outcome is Outcome.SOLVED, (
        "WHY THIS IS A FAILURE: the first diff was refused, the repair returned a passing "
        f"patch, and the record is {record.outcome!r}. A NOT_APPLIED draw must be re-asked "
        "instead of being graded as the final answer"
    )
    assert record.strict is Status.PASS, (
        "WHY THIS IS A FAILURE: a repaired pass is not a strict PASS under the same verifier. "
        "The repair must not loosen the reward (spec: no loosened verifier)"
    )
    assert "fail-to-pass" in record.verdict_kinds, (
        "WHY THIS IS A FAILURE: the repaired patch never reached the declared tests, so the "
        "verifier was not the one that graded a first attempt"
    )


def test_a_not_applied_draw_spends_at_most_r_repairs(tmp_path: Path) -> None:
    fixture = build_mined_task(tmp_path / "task")
    prompt = posed(fixture.task)
    repaired = apply_repair_prompt(prompt, ApplyFailure.CONTEXT_MISMATCH)
    observed = _Observed({prompt: CONTEXT_REFUSED, repaired: CONTEXT_REFUSED})

    record = score(
        candidate="always-refused",
        task=fixture.task,
        generator=observed,
        sandbox_root=tmp_path / "runs" / "always-refused",
        timeout=TIMEOUT,
        interpreters=Interpreters(workspace=tmp_path / "envs"),
        repair=2,
    )

    assert observed.prompts == [prompt, repaired, repaired], (
        f"WHY THIS IS A FAILURE: the loop asked {observed.prompts!r} for a NOT_APPLIED draw "
        "whose repair was refused twice. It must issue exactly 1 + R generations, and the "
        "repair prompt must be the pre-posed one for the class"
    )
    assert record.outcome is Outcome.NOT_APPLIED, (
        f"WHY THIS IS A FAILURE: an exhausted NOT_APPLIED rollout is {record.outcome!r}; the "
        "last draw was still refused by git and must be recorded as such"
    )


def test_the_repair_budget_is_shared_between_not_solved_and_not_applied(
    tmp_path: Path,
) -> None:
    """One budget, two triggers: 1 + R generations in total, never 1 + 2R."""
    fixture = build_mined_task(tmp_path / "task")
    prompt = posed(fixture.task)
    applies_and_fails = make_patch(fixture.donor, {"calc.py": STILL_BROKEN}, at=fixture.parent)
    node = "tests/test_addition.py::test_add_is_addition"
    test_repair = repair_prompt(prompt, node, "failed")
    apply_repair = apply_repair_prompt(prompt, ApplyFailure.CONTEXT_MISMATCH)
    observed = _Observed(
        {
            prompt: applies_and_fails,
            test_repair: CONTEXT_REFUSED,
            apply_repair: CONTEXT_REFUSED,
        }
    )

    record = score(
        candidate="mixed-repairs",
        task=fixture.task,
        generator=observed,
        sandbox_root=tmp_path / "runs" / "mixed-repairs",
        timeout=TIMEOUT,
        interpreters=Interpreters(workspace=tmp_path / "envs"),
        repair=2,
    )

    assert observed.prompts == [prompt, test_repair, apply_repair], (
        f"WHY THIS IS A FAILURE: the mixed trigger sequence asked {observed.prompts!r}. The "
        "budget is per (candidate, task) and shared by both triggers: a NOT_SOLVED repair "
        "followed by a NOT_APPLIED repair exhausts R = 2, never 1 + 2R"
    )
    assert record.outcome is Outcome.NOT_APPLIED


def test_every_apply_repair_is_recorded_with_its_class(tmp_path: Path) -> None:
    """The transcript row says `"repair"`, attempt 1, and carries the class prompt."""
    fixture = build_mined_task(tmp_path / "task")
    task = fixture.task
    prompt = posed(task)
    right = make_patch(fixture.donor, {"calc.py": MINED_CALC_FIXED}, at=fixture.parent)
    repaired = apply_repair_prompt(prompt, ApplyFailure.CONTEXT_MISMATCH)
    contract = freeze([task], repair=True)
    transcript = Transcript(path=tmp_path / "transcript.jsonl")
    generator = Retry(
        inner=Sealed(
            inner=StubGenerator({prompt: CONTEXT_REFUSED, repaired: right}),
            contract=contract,
        ),
        transcript=transcript,
        candidate="recorded",
        contract=contract.posed,
    )

    record = score(
        candidate="recorded",
        task=task,
        generator=generator,
        sandbox_root=tmp_path / "runs" / "recorded",
        timeout=TIMEOUT,
        interpreters=Interpreters(workspace=tmp_path / "envs"),
        repair=1,
    )

    rows = _records(transcript)
    assert record.outcome is Outcome.SOLVED, (
        f"WHY THIS IS A FAILURE: the recorded repair did not produce a pass ({record.outcome!r})"
    )
    assert [(row["decision"], row["attempt"]) for row in rows] == [
        ("graded", 1),
        ("repair", 1),
    ], (
        f"WHY THIS IS A FAILURE: the transcript rows are "
        f"{[(row['decision'], row['attempt']) for row in rows]!r}. The repair draw must be one "
        '`"repair"` row with attempt 1, so a reader can see a repair happened'
    )
    assert rows[-1]["prompt"] == repaired, (
        "WHY THIS IS A FAILURE: the repair row's prompt is not the class-specific apply repair "
        "prompt, so the transcript no longer records which failure class was answered"
    )
    assert rows[-1]["prompt_sha256"] == prompt_hash(repaired), (
        "WHY THIS IS A FAILURE: the repair row's digest does not tie it to the frozen class prompt"
    )
    assert rows[-1]["task_id"] == task.task_id


def test_the_non_retry_recorder_also_records_the_apply_repair(tmp_path: Path) -> None:
    """`Recording` is the non-retry writer; it must file the apply repair as `"repair"` too."""
    fixture = build_mined_task(tmp_path / "task")
    task = fixture.task
    prompt = posed(task)
    right = make_patch(fixture.donor, {"calc.py": MINED_CALC_FIXED}, at=fixture.parent)
    repaired = apply_repair_prompt(prompt, ApplyFailure.CONTEXT_MISMATCH)
    contract = freeze([task], repair=True)
    transcript = Transcript(path=tmp_path / "transcript.jsonl")
    generator = Recording(
        inner=Sealed(
            inner=StubGenerator({prompt: CONTEXT_REFUSED, repaired: right}),
            contract=contract,
        ),
        transcript=transcript,
        candidate="recorded",
        contract=contract,
    )

    record = score(
        candidate="recorded",
        task=task,
        generator=generator,
        sandbox_root=tmp_path / "runs" / "recorded",
        timeout=TIMEOUT,
        interpreters=Interpreters(workspace=tmp_path / "envs"),
        repair=1,
    )

    rows = _records(transcript)
    assert record.outcome is Outcome.SOLVED
    assert rows[-1]["decision"] == "repair" and rows[-1]["prompt"] == repaired, (
        "WHY THIS IS A FAILURE: the non-retry recorder filed the apply repair as something "
        'other than the class-specific `"repair"` row'
    )
