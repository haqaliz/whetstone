"""The recorder that watches the model seam without widening it, and without editing what it sees.

`generator.Generator` is one method on purpose (`generator.py:33-40`): every method added to it is
another thing the real MLX adapter has to reproduce faithfully before the substitution stops being
a fiction. So the transcript is taken by *wrapping* that seam rather than by extending it — the
recorder is a `Generator` holding a `Generator`, and nothing downstream of it learns that a
transcript exists.

Two properties carry the whole slice, and both are about what the recorder must refuse to do:

* **The completion passes through byte-for-byte, and is stored byte-for-byte.** The transcript
  exists to re-derive offline what `extract_patch` did with the text live. A recorder that stripped
  whitespace, or normalised a trailing newline, would repair the exact defects under investigation
  and the replay would then report a cause the run never had. The returned text and the stored text
  are asserted separately, because a recorder can be honest about one and not the other.
* **A generation that did not happen is not recorded.** The inner generator raising is the shape of
  an interrupted run and of a prompt refused by the frozen contract's seal; a row written before
  delegating would leave a completion-less record in a file whose entire purpose is completions,
  and an offline replay counting rows would attribute a cause to a rollout that never occurred.

No model, no `mlx`, no network: the inner generator is a hand-written double in every test here.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from whetstone.bakeoff.generator import Generator
from whetstone.bakeoff.rendering import prompt_hash
from whetstone.bakeoff.transcript import RecordingGenerator, Transcript

#: A prompt shaped like the real one: a heading, a node id, and a trailing newline. Its exact bytes
#: are what `prompt_sha256` is taken over, so it is a constant rather than an inline literal.
PROMPT = "You are fixing a bug in a Python repository.\n\n# Problem\nAddition subtracts.\n"

#: The four completions a base actually produces, and every one of them is something a well-meaning
#: writer might tidy. A fenced diff with a trailing newline (the shape `extract_patch` reads), prose
#: with no diff at all (the commonest zero in `reports/baseline/`), the empty string (which is
#: charged FAIL at patch-apply and must stay distinguishable from a wrong fix), and a completion
#: whose leading and trailing whitespace is the whole difference between two extractions.
COMPLETIONS = {
    "a fenced diff": (
        "```diff\n"
        "--- a/calc.py\n"
        "+++ b/calc.py\n"
        "@@ -1,2 +1,2 @@\n"
        "-    return a - b\n"
        "+    return a + b\n"
        "```\n"
    ),
    "prose with no diff": "I could not work out what is wrong here, so I have made no change.",
    "nothing at all": "",
    "whitespace at both ends": "\n\n  ```diff\n--- a/calc.py\n```\n   \n",
}


class _Answers:
    """An inner generator that returns one fixed completion and records what it was asked.

    Deliberately not `StubGenerator`: that class refuses an unstubbed prompt, and several tests
    below want the inner generator to be indifferent to the prompt so that what is asserted is the
    recorder's behaviour rather than the double's table.
    """

    def __init__(self, completion: str) -> None:
        self.completion = completion
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.completion


class _Raises:
    """An inner generator that fails the way a real one does: an exception, and no text."""

    def generate(self, prompt: str) -> str:
        raise RuntimeError("the model process died mid-generation")


def _recorder(tmp_path: Path, inner: Generator, **overrides: str) -> RecordingGenerator:
    """A recorder over a transcript in `tmp_path`, keyed to one candidate and one task."""
    fields = {"candidate": "base-a", "task_id": "t1"} | overrides
    return RecordingGenerator(
        inner=inner,
        transcript=Transcript(path=tmp_path / "transcript.jsonl"),
        candidate=fields["candidate"],
        task_id=fields["task_id"],
    )


def test_the_recorder_is_a_generator_by_the_same_signature_the_protocol_declares(
    tmp_path: Path,
) -> None:
    """The wrapper substitutes for what it wraps, or the seam has been widened after all.

    `isinstance` against a `runtime_checkable` protocol asserts only that an attribute named
    `generate` exists — a wrapper whose method took `(prompt, task_id)` would pass it and fail at
    the call site. So the signature is compared to the protocol's own, which is what `sweep` and
    `score` actually depend on.
    """
    recorder = _recorder(tmp_path, _Answers("anything"))

    assert isinstance(recorder, Generator), (
        "WHY THIS IS A FAILURE: the recorder is not a Generator, so it cannot be handed to `sweep` "
        "in place of the base it wraps. Recording would then require a second parameter threaded "
        "through every layer between the driver and the model — which is the seam widening that "
        "`generator.py` exists to prevent"
    )

    expected = inspect.signature(Generator.generate)
    actual = inspect.signature(RecordingGenerator.generate)
    assert actual == expected, (
        f"WHY THIS IS A FAILURE: the recorder's generate{actual} does not match the protocol's "
        f"generate{expected}. isinstance above would still pass, and the mismatch would only "
        "surface at the call site inside a night's run"
    )


@pytest.mark.parametrize("description", sorted(COMPLETIONS))
def test_the_completion_passes_through_and_is_stored_byte_for_byte(
    tmp_path: Path, description: str
) -> None:
    """The honesty property of the recorder: it observes the generation, it does not edit it.

    Both halves are asserted because a recorder can be honest about one and not the other. The
    **returned** text is what `extract_patch` runs on live, so altering it would change the run's
    own result — the instrument would be affecting the measurement. The **stored** text is what the
    offline replay runs on, so altering that would make the replay disagree with the live run and
    report a cause that never occurred. Whitespace is the whole example: `extract_patch` reads a
    fenced block, and a leading newline or a stripped trailing one is the difference between two
    extractions.
    """
    completion = COMPLETIONS[description]
    recorder = _recorder(tmp_path, _Answers(completion))

    returned = recorder.generate(PROMPT)
    stored = recorder.transcript.replay()[("base-a", "t1")].completion

    assert returned == completion, (
        f"WHY THIS IS A FAILURE: the recorder changed the completion ({description}) on its way "
        f"back to the run. It returned {returned!r} where the base produced {completion!r}, so the "
        "instrument is altering what it was installed to observe and every verdict downstream is "
        "about text the base never wrote"
    )
    assert stored == completion, (
        f"WHY THIS IS A FAILURE: the completion stored for {description} is {stored!r} rather than "
        f"the {completion!r} the base produced. A transcript that tidies the text repairs the "
        "defect the replay exists to diagnose, and the replay then attributes a cause the live run "
        "never had — while looking like evidence"
    )


def test_one_call_writes_exactly_one_record_under_its_own_key(tmp_path: Path) -> None:
    """The record names the pair it belongs to and the question it answers, and there is one of it.

    `prompt_sha256` is asserted against `rendering.prompt_hash` rather than against a literal,
    because it is the field that ties a stored completion to the generation contract frozen for the
    run. A digest computed some other way would look fine on disk and match nothing in the
    provenance block, which is the one comparison it exists for.
    """
    inner = _Answers(COMPLETIONS["a fenced diff"])
    recorder = _recorder(tmp_path, inner, candidate="base-b", task_id="donor-b-7")

    recorder.generate(PROMPT)
    replayed = recorder.transcript.replay()

    assert list(replayed) == [("base-b", "donor-b-7")], (
        "WHY THIS IS A FAILURE: one generation did not produce exactly one record under the "
        f"(candidate, task) it was made for. Got {list(replayed)!r}. A record filed under the "
        "wrong key attributes one base's failure to another's run"
    )
    record = replayed[("base-b", "donor-b-7")]
    assert record.prompt == PROMPT, (
        "WHY THIS IS A FAILURE: the stored prompt is not the prompt that was sent. A completion "
        "cannot be re-extracted against anything without the question it answered, so a record "
        "carrying a different prompt is unattributable evidence"
    )
    assert record.prompt_sha256 == prompt_hash(PROMPT), (
        f"WHY THIS IS A FAILURE: the record's digest is {record.prompt_sha256!r} and the run's own "
        f"`prompt_hash` gives {prompt_hash(PROMPT)!r}. That digest is what ties this completion to "
        "the frozen generation contract; computed any other way it matches nothing in the "
        "provenance block and the record cannot be shown to belong to the run that published it"
    )
    assert inner.prompts == [PROMPT], (
        "WHY THIS IS A FAILURE: the inner generator was not asked exactly the prompt the caller "
        f"sent, once. Got {inner.prompts!r}. A recorder that re-asks doubles a night of compute; "
        "one that edits the prompt asks a question the contract never froze"
    )


def test_a_generation_that_raised_leaves_no_record_at_all(tmp_path: Path) -> None:
    """No completion, no row. The record follows the generation; it never anticipates one.

    This is the shape of both failures that matter: a model process that dies mid-run, and a prompt
    the frozen contract refuses (`run.Sealed` raises before delegating). A recorder that wrote the
    prompt first and the completion afterwards would leave a completion-less row behind in both,
    and an offline replay counting rows would report a rollout that never happened. The exception
    must also propagate untouched — `sweep` deliberately does not catch it, because an interrupted
    run has to stop rather than produce a full-looking record set with holes in it.
    """
    recorder = _recorder(tmp_path, _Raises())

    with pytest.raises(RuntimeError) as failure:
        recorder.generate(PROMPT)

    assert "died mid-generation" in str(failure.value), (
        "WHY THIS IS A FAILURE: the inner generator's exception did not reach the caller intact. "
        f"Got {str(failure.value)!r}. A recorder that swallowed or rewrapped it would turn an "
        "interrupted run into one that looks complete"
    )
    assert recorder.transcript.replay() == {}, (
        "WHY THIS IS A FAILURE: a generation that never produced text still left a record. The "
        "recorder is writing before it delegates, so every refused prompt and every crashed "
        "generation becomes a row in a file whose whole purpose is completions"
    )
    assert not recorder.transcript.path.exists(), (
        "WHY THIS IS A FAILURE: the transcript file was created for a generation that failed. An "
        "empty file on disk is indistinguishable from a run that recorded nothing, and the two "
        "have different explanations"
    )
