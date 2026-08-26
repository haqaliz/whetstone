"""The § 3 baseline's committed artifact: the writer and its declaration state.

`PREREGISTRATION.md` § 3 fixes the baseline protocol — the untrained base scored on the
held-out split, measured once, re-measured never, with provenance beside it — and this
suite holds `build_baseline_report`/`write_baseline_report` to that. The measured
document must carry both sources over their own denominators with the pre-registered
`N` sentence **by identity**, the series and base identities with the § 7.3-open
sentence, the retry facts and the evidence pointer; the declaration state — what the
committed artifacts must look like before the operator spends the measurement — must
carry the "No count is measured here" sentence and no figure in any spelling; and both
states must be pure functions of their inputs, with `recorded_on` declared by the
operator, never read from a clock.

Nothing here runs a model, a sandbox, a verifier, or the network. Every `Rollout` is
constructed by hand and counted through `report.tally` — the single place each
published figure is defined — and nothing is written outside `tmp_path`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path

from whetstone.bakeoff import report
from whetstone.bakeoff.scoring import Outcome, Rollout
from whetstone.loop import baseline as baseline_module
from whetstone.loop.baseline import SeriesIdentity
from whetstone.loop.gate import RetryOutcome
from whetstone.verify.verdict import Status

#: What each outcome implies about the two verifiers when a test does not say otherwise.
VERDICTS: dict[Outcome, tuple[Status | None, Status | None]] = {
    Outcome.SOLVED: (Status.PASS, Status.PASS),
    Outcome.NOT_SOLVED: (Status.FAIL, Status.FAIL),
    Outcome.OUT_OF_SCOPE: (Status.FAIL, Status.PASS),
    Outcome.UNVERIFIED: (Status.UNVERIFIED, Status.UNVERIFIED),
}

#: The held-out membership's size in these tests — the document's own declared size is
#: 12 of 66, four per band; the synthetic set below mirrors that count, not the ids.
HELDOUT_DENOMINATOR = 12

#: The fabricated series: two digests, nothing else — the measured-once guard's key.
SERIES = SeriesIdentity(checkpoint_digest="c" * 64, heldout_digest="h" * 64)

#: The pinned base input: a repo id and a revision, stated with § 7.3 open.
BASE = {"repo_id": "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit", "revision": "main"}

#: The operator-declared date — an input, never the clock.
RECORDED_ON = "2026-08-26"

#: The sha256 of the evidence document's bytes — a pointer, never contents.
EVIDENCE_DIGEST = "e" * 64

TOOL_VERSIONS = {"python": "3.12.7", "uv": "0.5.18"}


def _rollout(candidate: str, task_id: str, outcome: Outcome) -> Rollout:
    """One synthetic record, with the verdict pair its outcome implies."""
    strict, weak = VERDICTS[outcome]
    return Rollout(
        candidate=candidate,
        task_id=task_id,
        outcome=outcome,
        strict=strict,
        weak=weak,
        verdict_kinds=("tests",),
        executed=3,
        prompt_sha256="0" * 64,
        detail="",
        generation_seconds=2.0,
        strict_seconds=4.0,
        weak_seconds=1.0,
    )


def _heldout_records() -> list[Rollout]:
    """Twelve held-out records: two solved, one unverified, one `N`, eight not solved."""
    return [
        _rollout("baseline", "task-1", Outcome.SOLVED),
        _rollout("baseline", "task-2", Outcome.SOLVED),
        _rollout("baseline", "task-3", Outcome.UNVERIFIED),
        _rollout("baseline", "task-4", Outcome.OUT_OF_SCOPE),
        *[
            _rollout("baseline", f"task-{index}", Outcome.NOT_SOLVED)
            for index in range(5, HELDOUT_DENOMINATOR + 1)
        ],
    ]


def _public_records() -> list[Rollout]:
    """Source A's single instance, solved."""
    return [_rollout("baseline", "pallets__flask-4045", Outcome.SOLVED)]


def _retries() -> tuple[RetryOutcome, ...]:
    """One held-out task that wobbled: UNVERIFIED first, converted to SOLVED on retry 2."""
    return (
        RetryOutcome(
            side="baseline",
            task_id="task-3",
            before=Outcome.UNVERIFIED,
            after=Outcome.SOLVED,
            retries_used=2,
            prompt_sha256="a" * 64,
            completion_sha256="b" * 64,
        ),
    )


def _document() -> Mapping[str, object]:
    """The measured document over the synthetic records — every figure through `tally`."""
    return report.build_baseline_report(
        series=SERIES,
        heldout_tally=report.tally("baseline", _heldout_records()),
        public_tally=report.tally("baseline", _public_records()),
        retries=_retries(),
        retry_count=3,
        evidence_digest=EVIDENCE_DIGEST,
        base=BASE,
        recorded_on=RECORDED_ON,
        tool_versions=TOOL_VERSIONS,
    )


def _declaration() -> Mapping[str, object]:
    """The declaration state over the same inputs: the writer's, never a hand edit."""
    return report.build_baseline_report(
        series=SERIES,
        heldout_tally=report.tally("baseline", _heldout_records()),
        public_tally=report.tally("baseline", _public_records()),
        retries=_retries(),
        retry_count=3,
        evidence_digest=EVIDENCE_DIGEST,
        base=BASE,
        recorded_on=RECORDED_ON,
        tool_versions=TOOL_VERSIONS,
        measured=False,
    )


def test_the_measured_document_carries_both_sources_and_n() -> None:
    """The measured document: both sources, `N` with its own sentence, retries, evidence.

    `PREREGISTRATION.md:142-143` fixes that both sources are always published together,
    each over its own denominator; `N` is the report's own pre-registered sentence **by
    identity**, not a second spelling; the retry facts are the declared `R` and what was
    actually spent, per task; and the evidence pointer is a digest, never contents.
    """
    document = _document()

    assert document["schema"] == report.BASELINE_REPORT_SCHEMA, (
        "WHY THIS IS A FAILURE: the artifact declares a schema other than the one the "
        "measured-once guard reads — a reader could not tell this document from any other"
    )
    assert document["schema"] == baseline_module.BASELINE_SCHEMA, (
        "WHY THIS IS A FAILURE: the writer's schema constant and the door's are the same "
        "schema under two names; a drift would let the guard and the writer disagree"
    )
    assert document["measured"] is True, (
        "WHY THIS IS A FAILURE: the measured document does not state that it is measured"
    )
    assert document["recorded_on"] == RECORDED_ON, (
        "WHY THIS IS A FAILURE: the declared date is not what the document carries — "
        "`recorded_on` must be an input, never the clock"
    )

    heldout = document["sides"]["source-b"]
    public = document["sides"]["source-a"]
    assert heldout == {
        "denominator": HELDOUT_DENOMINATOR,
        "solved": 2,
        "unverified": 1,
        "covered": 11,
        "failed": 9,
        "weaker_wins": 1,
    }, "WHY THIS IS A FAILURE: source B's six tally fields over its own denominator"
    assert public == {
        "denominator": 1,
        "solved": 1,
        "unverified": 0,
        "covered": 1,
        "failed": 0,
        "weaker_wins": 0,
    }, "WHY THIS IS A FAILURE: source A's six tally fields over its own denominator"

    n = document["n"]
    assert n["count"] == 1 and n["denominator"] == HELDOUT_DENOMINATOR, (
        "WHY THIS IS A FAILURE: `N` must be the held-out set's `weaker_wins` over the "
        "held-out denominator"
    )
    assert n["sentence"] is report._N_SENTENCE, (
        "WHY THIS IS A FAILURE: `N`'s sentence is a copy, not the pre-registered constant "
        "by identity — a second spelling could soften or sharpen what the number claims"
    )

    retries = document["retries"]
    assert retries["retry_count"] == 3, (
        "WHY THIS IS A FAILURE: the declared `R` is not recorded — the retry budget is "
        "part of what the `N` and the coverage are interpretable against"
    )
    assert retries["spent"] == 2, (
        "WHY THIS IS A FAILURE: the retries actually spent are not the sum of the "
        "per-task record"
    )
    assert retries["tasks"] == [
        {
            "task_id": "task-3",
            "before": "UNVERIFIED",
            "after": "SOLVED",
            "retries_used": 2,
        }
    ], "WHY THIS IS A FAILURE: the per-task retry facts are not recorded verbatim"

    assert document["evidence"] == {
        "schema": baseline_module.EVIDENCE_SCHEMA,
        "digest": EVIDENCE_DIGEST,
    }, (
        "WHY THIS IS A FAILURE: the evidence pointer must name aspect 2's own schema and "
        "a digest — never contents"
    )
    assert document["series"] == {
        "checkpoint_digest": SERIES.checkpoint_digest,
        "heldout_digest": SERIES.heldout_digest,
    }, "WHY THIS IS A FAILURE: the series identity is not the two digests"
    assert document["base"]["repo_id"] == BASE["repo_id"] and document["base"]["revision"] == BASE[
        "revision"
    ], "WHY THIS IS A FAILURE: the pinned base input is not recorded"
    assert document["non_comparable"] is True, (
        "WHY THIS IS A FAILURE: the sidecar does not declare the baseline's figures "
        "non-comparable — the machine-readable half of the changed-series ground"
    )
    assert document["tool_versions"] == dict(sorted(TOOL_VERSIONS.items())), (
        "WHY THIS IS A FAILURE: the tool versions are not sorted, so the document is not "
        "byte-identical across renders"
    )


def test_the_base_sentence_states_section_7_3_open(tmp_path: Path) -> None:
    """The base is recorded as this series' pinned input, and § 7.3 stays open.

    The bake-off selected no base, so the base this series measured is evidence, not
    closure — the artifact must say so in its own words, and the same words must reach
    the written artifacts, not just the in-memory document.
    """
    document = _document()
    assert "§ 7.3" in document["base"]["sentence"] and "stays open" in document["base"][
        "sentence"
    ], (
        "WHY THIS IS A FAILURE: the artifact does not state that PREREGISTRATION.md § 7.3 "
        "stays open — a reader would take the recorded base for a closure"
    )

    written = report.write_baseline_report(document, tmp_path / "home")
    markdown = Path(written[0]).read_text(encoding="utf-8")
    assert "§ 7.3" in markdown and "stays open" in markdown, (
        "WHY THIS IS A FAILURE: the human render does not carry the § 7.3-open sentence"
    )
    payload = json.loads(Path(written[1]).read_text(encoding="utf-8"))
    assert "§ 7.3" in payload["base"]["sentence"] and "stays open" in payload["base"][
        "sentence"
    ], (
        "WHY THIS IS A FAILURE: the sidecar's base block does not carry the § 7.3-open "
        "sentence (JSON escapes `§` as `\\u00a7`, so the check reads the parsed value)"
    )


def test_the_non_comparability_sentence_names_the_existing_homes(tmp_path: Path) -> None:
    """The baseline is the § 3 anchor, and its figures are a new series beside four homes.

    The document must name every existing home and state what it itself is — the
    measured-once anchor — without restating a figure from any of them.
    """
    document = _document()
    written = report.write_baseline_report(document, tmp_path / "home")
    text = Path(written[0]).read_text(encoding="utf-8")

    for home in (
        "reports/baseline/",
        "reports/format-hardening/",
        "reports/easier-stratum/",
        "reports/larger-base/",
    ):
        assert home in text, (
            f"WHY THIS IS A FAILURE: the non-comparability sentence does not name "
            f"{home} — a reader could not see which directories' figures this one does "
            "not restate"
        )
    assert "non-comparable" in text, (
        "WHY THIS IS A FAILURE: the document does not state that the five homes are "
        "declared non-comparable — the argument the directory's existence rests on"
    )
    assert "§ 3" in text and "measured once, re-measured never" in text, (
        "WHY THIS IS A FAILURE: the document does not state what the baseline is — the § "
        "3 anchor, measured once, re-measured never"
    )
    assert document["non_comparable"] is True, document


def test_the_writer_is_pure_and_deterministic(tmp_path: Path) -> None:
    """Identical inputs render byte-identical artifacts; `recorded_on` is an input.

    The committed artifact must be regenerable byte-for-byte — a reader who regenerates
    it and gets different bytes cannot tell a re-render from a re-measurement — and the
    date must come from the operator's declaration, never from a clock, so two renders
    of the same documented command agree.
    """
    first = report.write_baseline_report(_document(), tmp_path / "one")
    second = report.write_baseline_report(_document(), tmp_path / "two")
    for one, two in zip(first, second, strict=True):
        assert one.read_bytes() == two.read_bytes(), (
            f"WHY THIS IS A FAILURE: {one.name} differs between two renders of the same "
            "inputs — the committed document could not be regenerated byte-for-byte"
        )

    different_date = report.build_baseline_report(
        series=SERIES,
        heldout_tally=report.tally("baseline", _heldout_records()),
        public_tally=report.tally("baseline", _public_records()),
        retries=_retries(),
        retry_count=3,
        evidence_digest=EVIDENCE_DIGEST,
        base=BASE,
        recorded_on="2026-08-27",
        tool_versions=TOOL_VERSIONS,
    )
    third = report.write_baseline_report(different_date, tmp_path / "three")
    for one, three in zip(first, third, strict=True):
        assert one.read_bytes() != three.read_bytes(), (
            f"WHY THIS IS A FAILURE: {one.name} ignores the declared date — `recorded_on` "
            "must be an input, never a clock reading, and a changed input must change "
            "the bytes"
        )
    assert RECORDED_ON in first[0].read_text(encoding="utf-8"), (
        "WHY THIS IS A FAILURE: the operator-declared date does not appear in the "
        "artifact — the reader cannot see which render this is"
    )


def test_the_declaration_carries_no_count_in_any_spelling(tmp_path: Path) -> None:
    """The committed state before the measurement: declared, holding no figure.

    The baseline has not run, so the artifacts cannot carry a figure — neither the
    baseline's own (none exists) nor any existing home's (restating one is forbidden).
    The declaration says exactly that, renders no contract fields, and holds no `N of M`
    figure anywhere in the three artifacts.
    """
    document = _declaration()
    written = report.write_baseline_report(document, tmp_path / "declaration")

    assert "No count is measured here: the baseline has not run." in Path(written[0]).read_text(
        encoding="utf-8"
    ), (
        "WHY THIS IS A FAILURE: a directory whose baseline has not run says nothing "
        "about that. A reader finding counts here later could not tell when they appeared"
    )
    payload = json.loads(Path(written[1]).read_text(encoding="utf-8"))
    assert payload["measured"] is False, payload
    assert payload["schema"] == report.BASELINE_REPORT_SCHEMA, payload
    for name in (
        "sides",
        "n",
        "retries",
        "evidence",
        "base",
        "series",
        "tool_versions",
        "generation_contract",
    ):
        assert name not in payload, (
            f"WHY THIS IS A FAILURE: the declaration carries {name}, but no measurement "
            "exists"
        )
    for artifact in written:
        text = Path(artifact).read_text(encoding="utf-8")
        assert not re.search(r"\d+ of \d+", text), (
            f"WHY THIS IS A FAILURE: {artifact.name} renders a figure, but no measurement "
            "exists. A count here would be a restated figure from another home or an "
            "invented one"
        )
        assert "retry budget" not in text, (
            f"WHY THIS IS A FAILURE: {artifact.name} renders contract fields, but no "
            "count was measured under any contract"
        )


def test_the_declaration_is_generated_not_hand_typed(tmp_path: Path) -> None:
    """The declaration's sentence is the writer's own constant — never a hand edit.

    The committed declaration's provenance is the writer: the sentence is a module
    constant of `report.py`, and the same constant is what the written artifacts carry,
    in the JSON document and in the human render alike.
    """
    document = _declaration()
    assert document["declaration"] == report._BASELINE_DECLARATION, (
        "WHY THIS IS A FAILURE: the declaration document does not carry the writer's own "
        "constant — a hand-typed sentence could drift from the register"
    )
    written = report.write_baseline_report(document, tmp_path / "declaration")
    assert report._BASELINE_DECLARATION in Path(written[0]).read_text(encoding="utf-8"), (
        "WHY THIS IS A FAILURE: the human render does not state the declaration sentence"
    )
    payload = json.loads(Path(written[1]).read_text(encoding="utf-8"))
    assert payload["declaration"] == report._BASELINE_DECLARATION, payload
    cost = json.loads(Path(written[2]).read_text(encoding="utf-8"))
    assert cost["recorded_on"] == RECORDED_ON, (
        "WHY THIS IS A FAILURE: the cost sidecar does not carry the declared date"
    )
    assert "no cost is measured here" in Path(written[2]).read_text(encoding="utf-8"), (
        "WHY THIS IS A FAILURE: the cost sidecar states a cost where none was measured"
    )