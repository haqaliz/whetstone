"""The run ledger's two obligations: record the pinned inputs, and never record the user's code.

The first is P2's fourth exit criterion and is asserted end to end in `test_night.py`, where a real
night writes one. This file holds the two properties that are easier to break in isolation and
harder to notice:

* **the locality canary.** A ledger is evidence, and evidence is the kind of file that later gets
  attached to something. `tasks/ledger.py` established the rule — hashes and verdicts, never
  contents — and the only defence that survives a future decision to publish is a document that
  never held the code. So a completion carrying an unmistakable donor marker is pushed all the way
  through and the marker is looked for in the bytes.
* **the schema refusal.** Every field this reader needs is one an optimistic parse would default,
  and a defaulted seed map or task set records nothing while returning successfully — the shape of
  every silent failure this repository has already found.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whetstone.bakeoff import run as bakeoff_run
from whetstone.bakeoff.report import GenerationContract
from whetstone.bakeoff.scoring import Outcome, Rollout
from whetstone.loop import dataset as training
from whetstone.loop import ledger as run_ledger
from whetstone.loop.sampling import Applied
from whetstone.verify.verdict import Status

#: Text that could only have come from a donor's working tree.
DONOR_SOURCE = "def add(a, b):\n    return a + b  # SECRET_DONOR_MARKER\n"


def _rollout(outcome: Outcome = Outcome.SOLVED, strict: Status = Status.PASS) -> Rollout:
    return Rollout(
        candidate="base",
        task_id="alpha",
        outcome=outcome,
        strict=strict,
        weak=strict,
        verdict_kinds=("fail-to-pass",),
        executed=2,
        prompt_sha256="a" * 64,
        detail="",
        generation_seconds=1.0,
        strict_seconds=1.0,
        weak_seconds=1.0,
    )


def _ledger() -> run_ledger.Ledger:
    example = training.example_of(
        _rollout(),
        source="private",
        attempt=1,
        seed=1234,
        completion=DONOR_SOURCE,
        control=Status.PASS,
    )
    return run_ledger.Ledger(
        run_id="night-001",
        recorded_on="2026-08-20",
        run_seed=20260820,
        draws=8,
        model=run_ledger.Model(repo_id="mlx-community/base-32B", revision="d1e3b69"),
        contract=GenerationContract(
            prompt_sha256="p" * 64,
            sampler="categorical",
            max_tokens=1024,
            extractor_version="extract_patch@abc",
            dev_subset=("dev-1",),
            retry_budget=2,
            retry_template_sha256="r" * 64,
            diagnosis_vocabulary_version="v" * 64,
            retrieval="oracle",
        ),
        task_set=run_ledger.TaskSet(
            private=61, public=1, roots=2, dev_subset=("dev-1",), probe=None
        ),
        tool_versions={"python": "3.12.0", "mlx-lm": "0.31.3"},
        seeds=(Applied(task_id="alpha", attempt=1, seed=1234),),
        draws_recorded=(
            run_ledger.DrawRecord(
                attempt=1,
                harness={"private": Status.PASS},
                counts={"private": (61, 7, 1)},
            ),
        ),
        dataset=training.build(
            [training.TrainingText(example=example, prompt="fix it", completion=DONOR_SOURCE)],
            denominator=61,
            unverified=7,
        ),
        valid_split=training.NO_VALID_SPLIT,
        checkpoint_digest="c" * 64,
        checkpoint_absent="",
        capacity={"iters": 8, "peak_bytes": 1},
    )


def test_the_ledger_holds_no_donor_source_text(tmp_path: Path) -> None:
    """The canary: a completion's text must not survive the trip into the ledger.

    Planted rather than argued. Every layer between a completion and this document is supposed to
    carry only a digest, and a single field added later that carried the text instead would be
    invisible in review — the file would still be full of hashes.
    """
    path = run_ledger.write(tmp_path / "ledger.json", _ledger())
    text = path.read_text(encoding="utf-8")

    assert "SECRET_DONOR_MARKER" not in text, (
        "WHY THIS IS A FAILURE: donor source text reached the run ledger. This document is the "
        "night's evidence, and evidence is the kind of file that later gets attached to "
        "something. Hashes and verdicts, never contents"
    )
    assert "fix it" not in text, (
        "WHY THIS IS A FAILURE: a prompt reached the run ledger. The prompt quotes the donor's "
        "own files back — that is what the oracle retrieval setting means"
    )


def test_the_ledger_records_the_environment_pins_by_identity() -> None:
    """The fifth pinned input, described in the bake-off's own words rather than a second time.

    The pins themselves are per task and already committed in the manifests; a copy here would be
    a second version of them that can drift. The sentence is imported, so the two documents cannot
    describe the same mechanism in two ways.
    """
    assert run_ledger.ENVIRONMENT_PINS is bakeoff_run._ENVIRONMENT_PINS
    assert run_ledger.ENVIRONMENT_PINS in run_ledger.document(_ledger())


def test_the_tool_versions_come_from_the_bakeoffs_own_function() -> None:
    """One answer to "what was this measured under", not two that can disagree in silence."""
    assert run_ledger.tool_versions() == bakeoff_run._tool_versions()


def test_a_document_of_another_schema_is_refused(tmp_path: Path) -> None:
    """Refused rather than parsed optimistically — a defaulted seed map records nothing."""
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps({"schema": "something-else/1", "run_seed": 1}), encoding="utf-8")
    with pytest.raises(run_ledger.LedgerUnreadable, match=run_ledger.LEDGER_SCHEMA):
        run_ledger.read(path)

    path.write_text("not json at all", encoding="utf-8")
    with pytest.raises(run_ledger.LedgerUnreadable):
        run_ledger.read(path)


def test_the_counts_use_the_published_definitions(tmp_path: Path) -> None:
    """`solved` and `unverified` are the report's own, so the ledger cannot disagree with a tally.

    The unverified side is the one worth asserting: `UNPROVISIONED` and `NO_ORACLE` are *not*
    the candidate's failures and lower coverage rather than counting as losses. A ledger that
    counted only `Outcome.UNVERIFIED` would report a coverage this project's own report would
    contradict.
    """
    records = [
        _rollout(),
        _rollout(Outcome.NOT_SOLVED, Status.FAIL),
        _rollout(Outcome.UNVERIFIED, Status.UNVERIFIED),
        _rollout(Outcome.UNPROVISIONED, Status.UNVERIFIED),
        _rollout(Outcome.NO_ORACLE, Status.UNVERIFIED),
    ]
    assert run_ledger.counts_of(records) == (5, 3, 1), (
        "WHY THIS IS A FAILURE: the ledger's counts do not match the report's definitions. "
        "UNPROVISIONED is a fact about the machine and NO_ORACLE a fact about the corpus; both "
        "lower coverage and neither is the candidate's loss"
    )


def test_the_written_document_round_trips(tmp_path: Path) -> None:
    """Written by hand field by field, so a field added later breaks the codec first."""
    path = run_ledger.write(tmp_path / "ledger.json", _ledger())
    recorded = run_ledger.read(path)

    assert recorded["seeds"] == [{"task_id": "alpha", "attempt": 1, "seed": 1234}]
    assert recorded["draws_recorded"][0]["counts"]["private"]["unverified"] == 7
    assert recorded["dataset"]["valid_split"] == training.NO_VALID_SPLIT
    assert recorded["generation_contract"]["retry_budget"] == 2
    assert run_ledger.document(_ledger()) == path.read_text(encoding="utf-8"), (
        "WHY THIS IS A FAILURE: the bytes on disk are not the bytes the document function "
        "produces, so nothing that digests or compares two ledgers is comparing what was written"
    )
