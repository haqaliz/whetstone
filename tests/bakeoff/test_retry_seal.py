"""The seal-held proof: every retry prompt is frozen before anything runs, and an edit aborts.

PRD D8 makes the retry prompt a pure function of `(first-attempt prompt, trigger)` so that
`freeze` can pre-render **every** retry prompt a run may issue into the same `posed` map the
first-attempt prompts live in. Then the seal does the rest: `Sealed` refuses any prompt whose
hash is not in the frozen map, so a retry prompt that was never posed aborts the run as
`ContractChanged` — the same discipline a mid-run template edit gets, applied to the retry
vocabulary.

Everything asserted here follows from that contract:

* **Seal-held:** freeze a task set with retries on, compose `Retry(Sealed(engine))`, run it —
  every prompt the engine is actually asked (first attempt and each retry) has its hash in
  `contract.posed`, asserted by instrumenting the stub. The retry prompts map to the same
  task the first-attempt prompt maps to, so every attempt of a task files under that task.
* **A mid-run retry-template edit aborts.** The vocabulary is mutated after the freeze (the
  same shape as the first-attempt seal test, `test_run.py:261-307`), the retried prompt's
  hash is no longer in `posed`, and `Sealed` raises `ContractChanged` — the run stops, as a
  run whose contract moved must.
* **A recorded retry run replays the decided attempt.** Three attempts, one key: the
  transcript holds three records with attempts 1..3, decisions retry/retry/graded, each with
  its own `prompt_sha256`; `Transcript.replay()` returns the last — the graded one — whose
  completion is exactly what the composed generator returned.
* **Determinism:** one stub table, two composed wrappers, byte-identical transcript files.

No model, no `mlx`, no network: the tasks are two-commit synthetic donors, the engine is a
`StubGenerator`, and the freeze is the real `run.freeze` over real tasks.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fixtures.repos.mined import build_mined_task

from bakeoff.test_diffcheck import COUNT_MISMATCH, WELL_FORMED
from whetstone.bakeoff import diffcheck
from whetstone.bakeoff.diffcheck import Trigger
from whetstone.bakeoff.generator import Generator, StubGenerator
from whetstone.bakeoff.rendering import prompt_hash, render_prompt
from whetstone.bakeoff.retry import Retry, retry_prompt
from whetstone.bakeoff.run import Contract, ContractChanged, Sealed, freeze
from whetstone.bakeoff.sources import oracle_sources
from whetstone.bakeoff.transcript import Transcript
from whetstone.verify.task import Task

#: The candidate the records are filed under. The same spelling `test_run_transcript.py` uses,
#: so a key asserted here is the key the rest of the suite means by it.
CANDIDATE = "mlx-community/Qwen2.5-Coder-3B-Instruct-4bit"


def _task(tmp_path: Path, task_id: str) -> Task:
    """One two-commit synthetic donor, loaded as the task the miner would have mined."""
    return build_mined_task(
        tmp_path / f"donor-{task_id}", task_id=task_id, subject=f"Fix addition ({task_id})"
    ).task


def _posed(task: Task) -> str:
    """The exact prompt `score` would render for `task`, oracle sources included."""
    sources = oracle_sources(task, pool=None)
    assert sources.files is not None, sources.reason
    return render_prompt(task, sources.files)


def _composed(
    tmp_path: Path,
    contract: Contract,
    answers: dict[str, str],
    *,
    transcript: Transcript,
) -> Retry:
    """The retried, sealed, recorded generator this file's tests run.

    Composed exactly as `run.conduct` composes it when retries are enabled: `Retry` around
    `Sealed` around the engine, with the recording pieces the wrapper writes its
    per-attempt records with.
    """
    return Retry(
        inner=Sealed(inner=StubGenerator(answers), contract=contract),
        transcript=transcript,
        candidate=CANDIDATE,
        contract=contract.posed,
    )


class _Seen:
    """The instrumented engine: records every prompt it is asked, then answers from the table.

    "Asserted by instrumenting the stub" — the seal-held claim is that everything *actually
    asked* was frozen, and the only honest witness of that is the engine's own log.
    """

    def __init__(self, inner: Generator, log: list[str]) -> None:
        self.inner = inner
        self.log = log

    def generate(self, prompt: str) -> str:
        self.log.append(prompt)
        return self.inner.generate(prompt)


def _records(transcript: Transcript) -> list[dict[str, object]]:
    """The transcript's lines as decoded JSON objects, in written order."""
    return [
        json.loads(line) for line in transcript.path.read_text(encoding="utf-8").splitlines()
    ]


def test_every_prompt_a_retry_run_issues_was_frozen_into_the_contract(tmp_path: Path) -> None:
    """Seal-held (PRD AC8): first attempts and every retry are in the frozen `posed` map.

    The contract is frozen with retries on, so it carries the first-attempt prompt and all
    three retry prompts for the task; the run then issues the first prompt and — because
    every draw triggers — the same retry prompt twice more. Each hash must be in `posed`,
    and each retry prompt must map to the *same task* the first prompt maps to, so the
    recorder files every attempt under that task.
    """
    task = _task(tmp_path, "alpha")
    contract = freeze([task], retry=True)
    first = _posed(task)
    retried = retry_prompt(first, Trigger.HUNK_COUNT_MISMATCH)
    log: list[str] = []
    engine = _Seen(StubGenerator({first: COUNT_MISMATCH, retried: COUNT_MISMATCH}), log)
    composed = Retry(
        inner=Sealed(inner=engine, contract=contract),
        transcript=Transcript(path=tmp_path / "t.jsonl"),
        candidate=CANDIDATE,
        contract=contract.posed,
    )

    decided = composed.generate(first)

    assert log == [first, retried, retried], (
        f"WHY THIS IS A FAILURE: the run asked {log!r}. The seal-held claim is about what "
        "the run actually asks, so the engine's log must contain the first prompt and the "
        "retries this test then checks against the contract"
    )
    assert {prompt_hash(prompt) for prompt in log} <= set(contract.prompts), (
        f"WHY THIS IS A FAILURE: the run asked prompts whose hashes are not in the frozen "
        f"contract: {sorted({prompt_hash(p) for p in log} - set(contract.prompts))!r}. The "
        "seal accepted them, so the freeze did not pre-render the retry vocabulary (PRD D8)"
    )
    assert contract.posed[prompt_hash(retried)] == task.task_id, (
        f"WHY THIS IS A FAILURE: the retry prompt maps to {contract.posed[prompt_hash(retried)]!r} "
        f"rather than the task that posed it ({task.task_id!r}). A retry prompt under the "
        "wrong task would file one task's attempts under another's key"
    )
    assert decided == COUNT_MISMATCH, (
        "WHY THIS IS A FAILURE: the decided completion is not the last attempt's"
    )


def test_editing_the_retry_vocabulary_after_freeze_aborts_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mid-run diagnosis edit is a template edit: `ContractChanged`, and the run stops.

    The first attempt passes the seal — its prompt was frozen — and triggers a retry; the
    retried prompt is built with the *edited* sentence, whose hash was never posed, and
    `Sealed` refuses it. The abort must arrive before the base is asked the changed
    question, mirroring the first-attempt seal test's shape (`test_run.py:261-307`).
    """
    task = _task(tmp_path, "alpha")
    contract = freeze([task], retry=True)
    first = _posed(task)
    retried = retry_prompt(first, Trigger.HUNK_COUNT_MISMATCH)
    answers = {first: COUNT_MISMATCH, retried: COUNT_MISMATCH}
    composed = _composed(
        tmp_path, contract, answers, transcript=Transcript(path=tmp_path / "t.jsonl")
    )
    edited = {
        **diffcheck.DIAGNOSES,
        Trigger.HUNK_COUNT_MISMATCH: "The patch's hunks are miscounted; rewrite it.",
    }
    monkeypatch.setattr(diffcheck, "DIAGNOSES", edited)

    with pytest.raises(ContractChanged) as refusal:
        composed.generate(first)

    message = str(refusal.value)
    assert "M7b" in message, (
        f"WHY THIS IS A FAILURE: the abort does not cite the rule it is enforcing, so an "
        f"operator reads it as a harness crash. Got {message!r}"
    )
    records = _records(Transcript(path=tmp_path / "t.jsonl"))
    assert len(records) == 1, (
        f"WHY THIS IS A FAILURE: the refused retry left a record behind ({records!r}). A "
        "prompt the frozen contract refuses is not a generation, and the "
        "record-follows-generation rule means no record for it — the transcript must hold "
        "only the one attempt that actually completed"
    )
    assert records[0]["prompt_sha256"] == prompt_hash(first), (
        "WHY THIS IS A FAILURE: the surviving record is not the honest first attempt's, so "
        "the attempts already recorded did not stay (append-only)"
    )
    assert records[0]["decision"] == "retry", (
        "WHY THIS IS A FAILURE: the first attempt's record does not declare the retry that "
        "was about to follow it"
    )


def test_a_recorded_retry_run_replays_the_decided_attempt(tmp_path: Path) -> None:
    """Three attempts, one key: decisions retry/retry/graded, replay returns the decided one.

    Every attempt gets its own record with its own `prompt_sha256`, its one-based `attempt`,
    and its `decision`; the last record — the one the run carried forward — is `"graded"`,
    and its completion is byte-for-byte what the composed generator returned. The earlier
    attempts survive on disk (append-only) as the evidence that the retry happened.
    """
    task = _task(tmp_path, "alpha")
    contract = freeze([task], retry=True)
    first = _posed(task)
    retried = retry_prompt(first, Trigger.HUNK_COUNT_MISMATCH)
    transcript = Transcript(path=tmp_path / "t.jsonl")
    composed = _composed(
        tmp_path,
        contract,
        {first: COUNT_MISMATCH, retried: COUNT_MISMATCH},
        transcript=transcript,
    )

    decided = composed.generate(first)

    records = _records(transcript)
    assert [record["attempt"] for record in records] == [1, 2, 3], (
        f"WHY THIS IS A FAILURE: the attempts are numbered {[r['attempt'] for r in records]!r} "
        "rather than 1, 2, 3. Each attempt must be numbered within its run"
    )
    assert [record["decision"] for record in records] == ["retry", "retry", "graded"], (
        f"WHY THIS IS A FAILURE: the decisions are {[r['decision'] for r in records]!r} "
        "rather than retry/retry/graded. Every record but the last for a key must declare "
        "itself a retry, and the decided record must declare itself graded"
    )
    assert all(
        record["prompt_sha256"] in contract.prompts for record in records
    ), (
        "WHY THIS IS A FAILURE: a stored prompt digest is not one the frozen contract "
        "carries, so the record cannot be tied to the run that produced it"
    )
    replayed = transcript.replay()
    assert set(replayed) == {(CANDIDATE, task.task_id)}, (
        f"WHY THIS IS A FAILURE: replay returned {sorted(replayed)!r} rather than exactly "
        "the one (candidate, task) key the run generated for"
    )
    decided_record = replayed[(CANDIDATE, task.task_id)]
    assert decided_record.completion == decided, (
        "WHY THIS IS A FAILURE: the decided record's completion is not the completion the "
        "run returned, so replay would attribute a different text to the run"
    )
    assert decided_record.prompt_sha256 == prompt_hash(retried), (
        "WHY THIS IS A FAILURE: the decided record is not the last attempt's — its prompt "
        "is not the retried prompt"
    )


def test_two_runs_over_one_stub_table_record_byte_identical_transcripts(
    tmp_path: Path,
) -> None:
    """Determinism through the seal: same table, two wrappers, identical records.

    The replay test above asserts the shape; this asserts the run-to-run identity — the
    decided completions and the transcript records (attempt indices, decisions, prompts)
    must be byte-identical across two runs over the same stub table, which is the property
    that makes a stored transcript replayable (PRD R3).
    """
    task = _task(tmp_path, "alpha")
    contract = freeze([task], retry=True)
    first = _posed(task)
    retried = retry_prompt(first, Trigger.HUNK_COUNT_MISMATCH)
    answers = {first: COUNT_MISMATCH, retried: WELL_FORMED}
    first_transcript = Transcript(path=tmp_path / "first.jsonl")
    second_transcript = Transcript(path=tmp_path / "second.jsonl")

    first_decided = _composed(tmp_path, contract, answers, transcript=first_transcript).generate(
        first
    )
    second_decided = _composed(tmp_path, contract, answers, transcript=second_transcript).generate(
        first
    )

    assert first_decided == second_decided, (
        "WHY THIS IS A FAILURE: two runs over one stub table decided different completions, "
        "so the wrapper's decisions are not a pure function of the completions"
    )
    assert first_transcript.path.read_text(encoding="utf-8") == second_transcript.path.read_text(
        encoding="utf-8"
    ), (
        "WHY THIS IS A FAILURE: two runs over one stub table wrote different transcripts, so "
        "a stored transcript could not be re-derived byte-for-byte (PRD R3)"
    )


def test_a_single_attempt_without_a_transcript_still_retries_but_records_nothing(
    tmp_path: Path,
) -> None:
    """The recording pieces are optional: the wrapper retries and records nothing without them.

    The driver composes the wrapper only when `--transcript` names a file, but the wrapper's
    own contract is that the pieces are optional — a decide-loop that records nothing is the
    same loop. This pins that the recording is a wrapper concern, not a seam change.
    """
    task = _task(tmp_path, "alpha")
    contract = freeze([task], retry=True)
    first = _posed(task)
    retried = retry_prompt(first, Trigger.HUNK_COUNT_MISMATCH)
    engine = StubGenerator({first: COUNT_MISMATCH, retried: WELL_FORMED})
    wrapper = Retry(inner=Sealed(inner=engine, contract=contract))

    decided = wrapper.generate(first)

    assert decided == WELL_FORMED, (
        "WHY THIS IS A FAILURE: the wrapper did not retry without a transcript. Retries are "
        "the wrapper's; the transcript is an operator choice"
    )
