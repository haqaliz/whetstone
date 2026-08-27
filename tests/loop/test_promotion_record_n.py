"""Aspect 1 of the honest-number-report unit: the promotion record carries N_final, and a
reader refuses a doctored record by name.

The pre-registered shape needs `N: f at baseline, g at final` (`PREREGISTRATION.md:57-72`),
and the final side's `N` has no on-disk source anywhere: `SideCounts` in the promotion
record carries no `weaker_wins`, and the gate writes no per-rollout evidence. This aspect
records `weaker_wins` at scoring time — `report.tally`'s definition by identity (weak is
PASS and strict is FAIL over the same rollouts), never a copied formula, never a rate — and
ships the fail-closed reader the schema's own docstring anticipated (gate.py): unknown
fields, a wrong schema, unreadable JSON, counts that do not sum to their denominator,
`weaker_wins` over its denominator, and a record missing `weaker_wins` (written before the
field existed) are each refused by name — never defaulted, because zero is a measurement
and absence is a fact.

No model, no `mlx`, no network — the fixtures are mined tasks and hand-built rollouts, and
the record is written and read as JSON on disk.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from loop.harness import corpus
from whetstone.bakeoff import report
from whetstone.bakeoff.scoring import Outcome, Rollout
from whetstone.loop import gate
from whetstone.loop.gate import Exit, GateDecision, Retryable, RetryOutcome, Side, SideCounts
from whetstone.verify.task import Task
from whetstone.verify.verdict import Status

#: Six tasks: two true solves, two graded zeros, one no-verdict, one no-patch.
_IDS = ("t-01", "t-02", "t-03", "t-04", "t-05", "t-06")


def _rollout(
    task_id: str,
    outcome: Outcome,
    *,
    weak: Status | None,
    strict: Status | None,
) -> Rollout:
    """One hand-built rollout: the fields `_counts` and `tally` read, the rest inert."""
    return Rollout(
        candidate="candidate",
        task_id=task_id,
        outcome=outcome,
        strict=strict,
        weak=weak,
        verdict_kinds=(),
        executed=None,
        prompt_sha256="",
        detail="",
        generation_seconds=0.0,
        strict_seconds=0.0,
        weak_seconds=0.0,
    )


def _fixture_rollouts() -> tuple[Rollout, ...]:
    """Six rollouts with known weak/strict statuses: two weaker-wins among four verdicts.

    The fixture's ground truth is 2: `t-02` and `t-04` are the shape a weaker check would
    have scored as wins (weak PASS, strict FAIL); `t-03` is a genuine zero on both checks;
    `t-01` is a true solve; `t-05` is a no-verdict and `t-06` never reached a verifier.
    """
    return (
        _rollout("t-01", Outcome.SOLVED, weak=Status.PASS, strict=Status.PASS),
        _rollout("t-02", Outcome.NOT_SOLVED, weak=Status.PASS, strict=Status.FAIL),
        _rollout("t-03", Outcome.NOT_SOLVED, weak=Status.FAIL, strict=Status.FAIL),
        _rollout("t-04", Outcome.NOT_SOLVED, weak=Status.PASS, strict=Status.FAIL),
        _rollout("t-05", Outcome.UNVERIFIED, weak=Status.PASS, strict=Status.UNVERIFIED),
        _rollout("t-06", Outcome.NO_DIFF, weak=None, strict=None),
    )


def _tasks(tmp_path: Path) -> tuple[Task, ...]:
    """One mined task per fixture id — the real task objects `_counts` maps by id."""
    _directory, built = corpus(tmp_path / "corpus", "private", _IDS)
    return tuple(fixture.task for fixture in built)


def test_weaker_wins_is_the_tallys_definition_by_identity(tmp_path: Path) -> None:
    """The gate's scoring-time count equals `report.tally`'s over the same rollouts.

    `weaker_wins` is `N` at the final side (`PREREGISTRATION.md:57-72`): the rollouts a
    weaker check would have scored as wins — weak is PASS and strict is FAIL. The gate
    computes it by calling the tally over the same records, never by restating its
    predicate, so the record's `N` cannot drift from the published definition.
    """
    rollouts = _fixture_rollouts()

    counts = gate._counts(rollouts, _tasks(tmp_path))

    assert counts.weaker_wins == 2, counts
    assert counts.weaker_wins == report.tally("candidate", rollouts).weaker_wins


def test_the_gate_counts_weaker_wins_through_the_report_module_by_identity() -> None:
    """The tally the gate calls is `bakeoff.report`'s own — imported, never copied.

    A second implementation of "what counts as a weaker win" anywhere in the gate would be
    a second definition of `N` with nothing to say so; the module-level import pins that the
    gate reads the one tally.
    """
    assert gate.bakeoff_report is report


# --------------------------------------------------------------------------------------------
# The reader: `read_promotion_record` — write a legal record with the gate's own writer,
# read it back, and refuse every doctored shape by name. The fixture is the writer's own
# output, so a refusal is a statement about the file on disk, never about a hand-built
# approximation of it.
# --------------------------------------------------------------------------------------------


def _sides() -> dict[str, Side]:
    """Both sides over both sources, every count consistent with its denominator.

    `solved + failed + unverified == denominator` on all four blocks, and the incumbent's
    counts differ from the candidate's so a round-trip that swapped them would be caught.
    """
    return {
        "candidate": Side(
            private=SideCounts(
                denominator=10,
                solved=4,
                unverified=1,
                covered=9,
                failed=5,
                weaker_wins=2,
                status=Status.PASS,
            ),
            public=SideCounts(
                denominator=1,
                solved=1,
                unverified=0,
                covered=1,
                failed=0,
                weaker_wins=0,
                status=Status.PASS,
            ),
        ),
        "incumbent": Side(
            private=SideCounts(
                denominator=10,
                solved=3,
                unverified=1,
                covered=9,
                failed=6,
                weaker_wins=1,
                status=Status.FAIL,
            ),
            public=SideCounts(
                denominator=1,
                solved=0,
                unverified=0,
                covered=1,
                failed=1,
                weaker_wins=1,
                status=Status.FAIL,
            ),
        ),
    }


def _write_fixture_record(tmp_path: Path) -> Path:
    """A legal record as the gate's own writer emits it, under `tmp_path`."""
    sides = _sides()
    path = gate.write_promotion_record(
        path=tmp_path / "record.json",
        run_id="gate-001",
        recorded_on="2026-08-27",
        candidate_digest="c" * 64,
        incumbent_digest="i" * 64,
        heldout_digest="h" * 64,
        candidate=sides["candidate"],
        incumbent=sides["incumbent"],
        decision=GateDecision(
            exit=Exit.UNVERIFIED,
            denominator=10,
            solved_new=4,
            solved_old=3,
            regressed=0,
            unverified=1,
            detail="1 of 10 tasks reached no verdict, so no comparison was actually made",
        ),
        retries=(RetryOutcome(
            side="candidate",
            task_id="t-05",
            before=Outcome.UNVERIFIED,
            after=Outcome.SOLVED,
            retries_used=1,
            prompt_sha256="p" * 64,
            completion_sha256="q" * 64,
        ),),
        retryable=(Retryable(
            side="incumbent",
            task_id="t-06",
            outcome=Outcome.NO_ORACLE,
            prompt_sha256="",
            completion_sha256="",
        ),),
        retry_count=gate.RETRY_COUNT,
        tool_versions={"python": "3.12"},
    )
    return path


def _doctored(path: Path, where: str, value: Any) -> Path:
    """`path` with one field replaced — the edit a doctoring hand would make, not re-sealed."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    node = raw
    parts = where.split(".")
    for part in parts[:-1]:
        node = node[part]
    node[parts[-1]] = value
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def test_a_written_record_round_trips_through_the_reader_verbatim(tmp_path: Path) -> None:
    """The reader returns exactly what the writer wrote — every count, no re-derivation.

    The record's own docstring names this reader ("the later reader has one answer to what
    shape is this file"); a reader that rounded, re-derived or defaulted any count would
    make the report writer's figures a different document's figures.
    """
    sides = _sides()
    read = gate.read_promotion_record(_write_fixture_record(tmp_path))

    assert read.schema == gate.PROMOTION_SCHEMA
    assert read.run_id == "gate-001" and read.recorded_on == "2026-08-27"
    assert read.candidate_digest == "c" * 64
    assert read.incumbent_digest == "i" * 64
    assert read.heldout_digest == "h" * 64
    assert read.sides["candidate"].private == sides["candidate"].private
    assert read.sides["candidate"].public == sides["candidate"].public
    assert read.sides["incumbent"].private == sides["incumbent"].private
    assert read.sides["incumbent"].public == sides["incumbent"].public
    assert read.decision["exit"] == "UNVERIFIED"
    assert read.decision["denominator"] == 10
    assert read.decision["solved_new"] == 4 and read.decision["solved_old"] == 3
    assert read.decision["regressed"] == 0 and read.decision["unverified"] == 1
    assert read.retry_count == gate.RETRY_COUNT and read.retries_used == 1
    assert read.retries[0]["task_id"] == "t-05" and read.retries[0]["retries_used"] == 1
    assert read.unverified_after_retries[0]["task_id"] == "t-06"
    assert read.tool_versions == {"python": "3.12"}


def test_an_unreadable_record_is_refused_by_name(tmp_path: Path) -> None:
    """A missing file is refused, naming the file — never treated as an empty record."""
    missing = tmp_path / "missing.json"
    with pytest.raises(ValueError) as refused:
        gate.read_promotion_record(missing)
    assert str(missing) in str(refused.value), refused.value


def test_invalid_json_is_refused_by_name(tmp_path: Path) -> None:
    """Bytes that are not JSON are refused, naming the file — never parsed leniently."""
    broken = tmp_path / "broken.json"
    broken.write_text('{"schema": "whetstone-promotion/1", ', encoding="utf-8")
    with pytest.raises(ValueError) as refused:
        gate.read_promotion_record(broken)
    assert str(broken) in str(refused.value), refused.value


@pytest.mark.parametrize(
    "schema",
    ["whetstone-promotion/2", None],
    ids=["wrong", "missing"],
)
def test_a_record_with_a_wrong_or_missing_schema_is_refused_by_name(
    tmp_path: Path, schema: Any
) -> None:
    """The schema is the record's one answer to "what shape is this file" — refused if else.

    A record declaring a schema this module does not read, or none at all, fails decode
    rather than defaulting: reading an old-schema record as today's would silently trust
    fields the writer never wrote.
    """
    path = _doctored(_write_fixture_record(tmp_path), "schema", schema)
    with pytest.raises(ValueError) as refused:
        gate.read_promotion_record(path)
    assert gate.PROMOTION_SCHEMA in str(refused.value), refused.value


@pytest.mark.parametrize(
    "where",
    ["sneaky", "sides.candidate.private.sneaky", "decision.sneaky"],
    ids=["top-level", "counts-block", "decision-block"],
)
def test_an_unknown_field_is_refused_by_name(tmp_path: Path, where: str) -> None:
    """A field this module does not read is refused by name — trusted by nobody, read by no one.

    The doctored record's planted field is the edit nobody checks: a reader that skipped it
    would accept a document whose shape is not the shape it validates.
    """
    path = _doctored(_write_fixture_record(tmp_path), where, 1)
    with pytest.raises(ValueError) as refused:
        gate.read_promotion_record(path)
    assert "sneaky" in str(refused.value), refused.value


@pytest.mark.parametrize(
    "where",
    ["sides.candidate.private.solved", "sides.incumbent.private.failed"],
    ids=["candidate", "incumbent"],
)
def test_counts_that_do_not_sum_to_the_denominator_are_refused_by_name(
    tmp_path: Path, where: str
) -> None:
    """`solved + failed + unverified != denominator` is a doctored record, never a rounding.

    The record's counts are the evidence the report re-derives; a side whose counts cannot
    sum is a side nobody can reproduce, and the reader names the block that broke it.
    """
    path = _doctored(_write_fixture_record(tmp_path), where, 5)
    with pytest.raises(ValueError) as refused:
        gate.read_promotion_record(path)
    message = str(refused.value)
    assert "denominator" in message and "private" in message, message


def test_weaker_wins_above_the_denominator_is_refused_by_name(tmp_path: Path) -> None:
    """A side cannot have more weaker-wins than tasks — the bound is the denominator itself.

    `weaker_wins` is a count over the side's own denominator; a value above it is a count
    that could not have been observed, refused by name rather than trusted.
    """
    path = _doctored(_write_fixture_record(tmp_path), "sides.candidate.private.weaker_wins", 11)
    with pytest.raises(ValueError) as refused:
        gate.read_promotion_record(path)
    message = str(refused.value)
    assert "weaker_wins" in message and "denominator" in message, message


def test_a_record_missing_weaker_wins_is_refused_never_defaulted(tmp_path: Path) -> None:
    """A pre-field record fails decode by name — zero is a measurement, absence is a fact.

    Records written before `weaker_wins` existed carry no value for the final side's `N`.
    A reader that read them as zero would publish "no weaker wins" for a run that never
    measured it, which is a figure no document supports.
    """
    path = _write_fixture_record(tmp_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["sides"]["candidate"]["private"]["weaker_wins"]
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError) as refused:
        gate.read_promotion_record(path)
    message = str(refused.value)
    assert "weaker_wins" in message and "candidate" in message, message


@pytest.mark.parametrize(
    "where",
    ["sides.candidate.private.solved", "decision.denominator", "retry_count"],
    ids=["side-count", "decision-count", "retry-budget"],
)
def test_boolean_counts_are_refused_by_name(tmp_path: Path, where: str) -> None:
    """`bool` is an `int` subclass in Python — a count field that is a boolean is refused.

    The baseline loader's posture, applied to every count field the record carries: a
    boolean would pass an `isinstance(value, int)` check and then be summed as 0 or 1, so
    the reader rejects the class, never the value.
    """
    path = _doctored(_write_fixture_record(tmp_path), where, True)
    with pytest.raises(ValueError) as refused:
        gate.read_promotion_record(path)
    message = str(refused.value)
    assert where.split(".")[-1] in message, message