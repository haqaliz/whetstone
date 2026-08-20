"""Selection: the one rule that decides what may be trained on, and the ways it could soften.

The project's central claim is that a policy cannot talk its way into the training set, because
selection reads the verifier's own record. Every way that claim fails is a way *this* module could
be wrong, and none of them look wrong in a diff:

* **a second definition of solved.** `report.tally` publishes `record.outcome is Outcome.SOLVED`;
  a re-derived "STRICT said PASS" here would be nearly the same thing, and the day they disagreed
  neither would say so. Asserted by identity.
* **an incomplete partition.** A member added to `Outcome` later must be classified by whoever
  adds it. Asserted as a set equality, so the build fails in this file first.
* **filtering instead of refusing.** Filtering says "the dataset holds only wins"; refusing says
  "nothing that was not a win was ever offered", and only the second survives a caller that
  assembles its own record list.
* **a validation split that is one example wide.** A checkpoint validated against it carries a
  claim nobody could defend, so below a declared floor there is *no* valid split and the
  provenance says so verbatim.
* **contents in a record.** A completion quotes the user's own private donor code back; the
  document that gets read, digested and (one day) shown to somebody must never hold it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whetstone.bakeoff import report
from whetstone.bakeoff.scoring import Outcome, Rollout
from whetstone.loop import dataset as training
from whetstone.verify.verdict import Status

#: A completion carrying text that could only have come from a donor. The canary below asserts
#: none of it reaches the record document — the same shape `tests/test_ledger.py` uses for the
#: committed mining evidence.
DONOR_SOURCE = "def add(a, b):\n    return a + b  # SECRET_DONOR_MARKER\n"


def _rollout(**overrides: object) -> Rollout:
    """A rollout that is a verified win unless an override makes it something else."""
    fields: dict[str, object] = {
        "candidate": "base",
        "task_id": "alpha",
        "outcome": Outcome.SOLVED,
        "strict": Status.PASS,
        "weak": Status.PASS,
        "verdict_kinds": ("fail-to-pass",),
        "executed": 2,
        "prompt_sha256": "a" * 64,
        "detail": "",
        "generation_seconds": 1.0,
        "strict_seconds": 1.0,
        "weak_seconds": 1.0,
    }
    fields.update(overrides)
    return Rollout(**fields)  # type: ignore[arg-type]


def _text(
    record: Rollout, *, attempt: int = 1, completion: str = DONOR_SOURCE
) -> training.TrainingText:
    return training.TrainingText(
        example=training.example_of(
            record,
            source="private",
            attempt=attempt,
            seed=99 + attempt,
            completion=completion,
            control=Status.PASS,
        ),
        prompt="fix the adder",
        completion=completion,
    )


def test_trainable_is_the_published_definition_of_solved_by_identity() -> None:
    """One definition, imported. Asserted `is`, because "the same value" is not the same claim.

    `report.tally` is where the published headline is defined. If this module held its own
    equivalent member — a string `"SOLVED"`, a locally-defined enum — the two could drift with
    both looking correct, and the dataset would be selected by whichever one ran.
    """
    assert training.TRAINABLE is Outcome.SOLVED, (
        "WHY THIS IS A FAILURE: the loop's notion of trainable is not the enum member the "
        "published headline is defined against. Two definitions of 'solved' is one definition "
        "too many, and the disagreement between them would be invisible"
    )
    # And the reverse direction, so this is not merely a statement about one constant: the
    # published tally counts the same member, so a change to either side breaks both.
    counted = report.tally("base", [_rollout(), _rollout(outcome=Outcome.NOT_SOLVED)])
    assert counted.solved == 1 and counted.denominator == 2, counted


def test_the_trainable_partition_covers_every_outcome_exactly_once() -> None:
    """A member added to `Outcome` later must be classified in a diff, not inherit a branch.

    Set equality in both directions: the trainable member and the not-trainable set must union to
    every member and share none. A test that only checked "UNVERIFIED is not trainable" would go
    on passing when a new outcome appeared and silently fell wherever an `if` happened to end.
    """
    assert training.NOT_TRAINABLE | {training.TRAINABLE} == set(Outcome), (
        "WHY THIS IS A FAILURE: the trainable/not-trainable partition does not cover Outcome. "
        f"Unclassified: {set(Outcome) - training.NOT_TRAINABLE - {training.TRAINABLE}}"
    )
    assert training.TRAINABLE not in training.NOT_TRAINABLE


@pytest.mark.parametrize("outcome", sorted(training.NOT_TRAINABLE, key=lambda one: one.value))
def test_no_outcome_but_solved_is_training_data(outcome: Outcome) -> None:
    """Every non-win, refused by name — with `UNVERIFIED` among them, which is the whole point.

    A task the harness could not grade is not a win, and a loop that trained on one would be
    training on its own inability to measure. The refusal is an exception rather than a `False`
    for the reason the module docstring gives: a caller that ignored a filter would assemble a
    shorter dataset and report it as the whole one.
    """
    with pytest.raises(training.NotTrainable) as refused:
        _text(_rollout(outcome=outcome, strict=Status.UNVERIFIED))
    assert outcome.value in str(refused.value), refused.value


def test_a_record_whose_two_verdicts_disagree_is_refused() -> None:
    """`SOLVED` with a strict FAIL is a defect, not a win — the shape a codec bug produces.

    The tag and the verdict come from different steps (`scoring._classify` and the verifier), so
    requiring both is not redundancy: it is the only place a record that lost one half on its way
    through a journal can be caught.
    """
    with pytest.raises(training.NotTrainable):
        _text(_rollout(outcome=Outcome.SOLVED, strict=Status.FAIL))


def test_a_win_from_an_unproven_harness_is_refused() -> None:
    """Nothing an unproven control arm measured is evidence about a base — or trainable.

    The control arm's status travels with the example rather than being checked somewhere else,
    so that this refusal cannot be bypassed by a caller that assembled records itself.
    """
    with pytest.raises(training.NotTrainable, match="control arm"):
        training.example_of(
            _rollout(),
            source="private",
            attempt=1,
            seed=1,
            completion="x",
            control=Status.UNVERIFIED,
        )


def test_the_record_document_holds_no_donor_source_text(tmp_path: Path) -> None:
    """The locality canary: hashes and verdicts, never contents.

    The completion quotes the user's own private donor code back verbatim. This document is the
    committed-*shaped* half — it is what gets digested, read and, one day, possibly shown to
    somebody — so the discipline holds even though it is written under a gitignored root. A
    document that never held the code is the only defence that survives a future decision to
    publish.
    """
    built = training.build([_text(_rollout())], denominator=4, unverified=1)
    path = training.write_document(tmp_path / "dataset.json", built)
    text = path.read_text(encoding="utf-8")

    assert "SECRET_DONOR_MARKER" not in text, (
        "WHY THIS IS A FAILURE: donor source text reached the dataset record document. A "
        "completion is the user's own private code; the record carries its digest, never it"
    )
    assert built.examples[0].completion_sha256 in text, (
        "WHY THIS IS A FAILURE: the record carries no completion digest, so it cannot be tied "
        "back to the transcript record it came from at all"
    )
    assert json.loads(text)["coverage"] == 3, (
        "WHY THIS IS A FAILURE: coverage is not the honest complement of the unverified count "
        "over the full denominator. Unverified tasks lower coverage; they never leave the "
        "denominator"
    )


def test_the_dataset_order_and_digest_do_not_depend_on_insertion_order() -> None:
    """The determinism criterion's foundation: the same examples, in any order, are one dataset.

    Insertion order follows whichever order the corpus directories happened to load in, so a
    dataset that preserved it would produce different bytes for the same night on two machines.
    """
    first = _text(_rollout(task_id="alpha"), attempt=1)
    second = _text(_rollout(task_id="beta"), attempt=2)
    forwards = training.build([first, second], denominator=2, unverified=0)
    backwards = training.build([second, first], denominator=2, unverified=0)

    assert training.document(forwards) == training.document(backwards), (
        "WHY THIS IS A FAILURE: the dataset document depends on the order examples were "
        "appended in. Two identical nights on two machines would then disagree byte for byte"
    )
    assert forwards.digest == backwards.digest


def test_a_valid_split_below_the_floor_is_declared_rather_than_silently_skipped() -> None:
    """The pre-committed degenerate rule: no valid split, said verbatim.

    A one-example validation set is not validation, it is a number that looks like validation.
    The alternative failure is worse than having no split at all: a checkpoint silent on the
    question reads exactly like a validated one, which is what `Split` refuses to construct.
    """
    tiny = [_text(_rollout(task_id=f"task-{index}"), attempt=index) for index in range(1, 4)]
    chosen = training.split(tiny, run_seed=5)

    assert chosen.valid == () and chosen.reason == training.NO_VALID_SPLIT, (
        "WHY THIS IS A FAILURE: a strict-PASS set of three produced a validation split. Below "
        f"the declared floor there is no valid split, stated verbatim. Got {chosen.reason!r}"
    )
    with pytest.raises(ValueError, match="verbatim"):
        training.Split(train=tuple(tiny), valid=(), reason="")


def test_a_valid_split_is_deterministic_under_the_run_seed() -> None:
    """Same seed, same split — and a different seed must actually move it.

    The second half is the anti-vacuity one: a "shuffle" that ignored its seed would satisfy
    determinism perfectly and would make the recorded seed meaningless.
    """
    many = [_text(_rollout(task_id=f"task-{index}"), attempt=index) for index in range(1, 41)]
    once = training.split(many, run_seed=5)
    again = training.split(many, run_seed=5)
    other = training.split(many, run_seed=6)

    assert [one.example.task_id for one in once.valid] == [
        one.example.task_id for one in again.valid
    ], "WHY THIS IS A FAILURE: the same run seed produced two different validation splits"
    assert once.valid and once.reason == "", once
    assert [one.example.task_id for one in once.valid] != [
        one.example.task_id for one in other.valid
    ], (
        "WHY THIS IS A FAILURE: two different run seeds produced the same split, so the split "
        "does not read its seed and the value recorded in the ledger explains nothing"
    )
    assert not set(once.valid) & set(once.train), (
        "WHY THIS IS A FAILURE: an example is in both halves of the split, so the validation set "
        "is partly the training set and any loss measured on it is not validation"
    )


def test_the_written_lines_map_back_to_strict_pass_records(tmp_path: Path) -> None:
    """mlx-lm's local format, read back the way the library reads it: one JSON object per line.

    Parsed with stdlib rather than by importing the library, because CI has no `mlx` — and the
    property under test is this repository's, not the library's. Every line must be the prompt
    and completion of a record the document also carries as a strict PASS.
    """
    texts = [_text(_rollout(task_id=f"task-{index}"), attempt=index) for index in range(1, 41)]
    chosen = training.split(texts, run_seed=5)
    written = training.write_local(tmp_path / "data", chosen)

    assert {path.name for path in written} == {training.TRAIN_FILE, training.VALID_FILE}
    known = {one.text for one in texts}
    for path in written:
        lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert lines, f"{path} is empty, so the trainer would read nothing"
        for line in lines:
            assert set(line) == {"text"}, (
                f"WHY THIS IS A FAILURE: {path.name} holds a key mlx-lm's `text` format does not "
                f"define: {sorted(line)}"
            )
            assert line["text"] in known, (
                "WHY THIS IS A FAILURE: a written training line does not correspond to any "
                "selected strict-PASS record, so something was assembled rather than selected"
            )


def test_no_test_split_is_written(tmp_path: Path) -> None:
    """`test.jsonl` is deliberately absent — held-out evaluation is P3's, and this is training data.

    A file named `test` written from the night's own training set is exactly the confusion
    `PREREGISTRATION.md` § 7.1 forbids: nothing trained on may later be quoted as held out.
    """
    texts = [_text(_rollout(task_id=f"task-{index}"), attempt=index) for index in range(1, 41)]
    training.write_local(tmp_path / "data", training.split(texts, run_seed=5))
    assert not (tmp_path / "data" / "test.jsonl").exists(), (
        "WHY THIS IS A FAILURE: a test.jsonl was written from training data. The held-out split "
        "does not exist until P3, and a file named `test` beside a training set is how a "
        "training example gets quoted as a held-out result"
    )
