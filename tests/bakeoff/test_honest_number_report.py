"""The honest-number report: the § 4 shape, instantiated by a writer of its own.

`PREREGISTRATION.md:57-72, 140-167` fixes the P4 headline — `+a of b held-out tasks
(baseline c of b, final d of b) / coverage e of b / N: f at baseline, g at final` — and
`test_the_p4_headline_skeleton_is_refused` (tests/bakeoff/test_report.py:323) forbids the
bake-off report from instantiating it, so this suite holds the **new** writer pair
(`build_honest_number_report`/`write_honest_number_report`) to that shape instead. The
shape is instantiated exactly, whose counts are "final" is the decision's function
(promoted → candidate; rejected → incumbent with the candidate disclosed as the rejected
attempt; UNVERIFIED → no headline and no delta, with "no comparison was made"), source A
renders per-instance with its funnel and never as a rate, both sources always share the
document, a zero or negative delta renders as plainly as a positive one, and every figure
is rendered over the denominator it was counted on.

Nothing here runs a model, a sandbox, a verifier, or the network. Every count is derived
through `report.tally` over hand-built `Rollout` records — the single place each published
figure is defined — and the writer is exercised as a pure function of plain values.
"""

from __future__ import annotations

import dataclasses
import json
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from whetstone.bakeoff import report
from whetstone.bakeoff.report import (
    GenerationContract,
    HonestNumberInput,
    build_honest_number_report,
    write_honest_number_report,
)
from whetstone.bakeoff.scoring import Outcome, Rollout
from whetstone.verify.verdict import Status

#: The repository root, for the subprocess half of the determinism test.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: What each outcome implies about the two verifiers when a test does not say otherwise.
VERDICTS: dict[Outcome, tuple[Status | None, Status | None]] = {
    Outcome.SOLVED: (Status.PASS, Status.PASS),
    Outcome.NOT_SOLVED: (Status.FAIL, Status.FAIL),
    Outcome.OUT_OF_SCOPE: (Status.FAIL, Status.PASS),
    Outcome.UNVERIFIED: (Status.UNVERIFIED, Status.UNVERIFIED),
}

#: The held-out split's size in these tests — the document's own declared size is 12 of 66.
HELDOUT = 12

#: The one source-A instance that survived the four-gate filter (`tasks/README.md`).
FLASK = "pallets__flask-4045"

#: The funnel as the committed ledger declares it: 300 considered, 299 refused by gate.
FUNNEL: Mapping[str, object] = {
    "considered": 300,
    "eligible": [FLASK],
    "refused": 299,
    "by_gate": [("format", 192), ("environment", 106), ("collectability", 1)],
}

#: The series: the base identity and the held-out document digest — nothing else.
SERIES = {
    "repo_id": "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit",
    "revision": "main",
    "heldout_digest": "h" * 64,
}

#: The operator-declared date — an input, never the clock.
RECORDED_ON = "2026-08-27"

#: The loop's generation contract, in the bake-off's own published shape: the seeded
#: categorical sampler the § 10.9 amendment discloses, with the retry machinery on.
CONTRACT = GenerationContract(
    prompt_sha256="p" * 64,
    sampler=(
        "categorical: temperature 0.8, top-p 0.95 (mlx_lm.sample_utils.make_sampler), "
        "with mx.random.seed(attempt_seed(run_seed, task_id, attempt)) applied immediately "
        "before each draw and draws taken serially; k=1 decodes greedily, identically to "
        "the bake-off"
    ),
    max_tokens=8192,
    extractor_version="extractor-v1",
    dev_subset=("dev-a", "dev-b", "dev-c", "dev-d", "dev-e"),
    retry_budget=3,
    retry_template_sha256="r" * 64,
    diagnosis_vocabulary_version="v" * 64,
    retrieval="oracle",
)

#: The provenance the promotion record's fields plus what the record lacks, which the
#: door supplies — the writer renders what it is given.
PROVENANCE: Mapping[str, object] = {
    "seeds": "run seed 0x1234",
    "task_set": "the declared source-B set plus source A, scored in full",
    "tool_versions": {"python": "3.12.7", "uv": "0.5.18"},
    "base_sentence": (
        "The base is recorded as this series' pinned input; PREREGISTRATION.md § 7.3 "
        "stays open."
    ),
    "retry_count": 3,
    "retries": [
        {
            "task_id": "task-3",
            "before": "UNVERIFIED",
            "after": "SOLVED",
            "retries_used": 2,
        }
    ],
    "contract": CONTRACT,
}

#: The per-side record sets over the held-out split. The baseline and the incumbent share
#: a set — the incumbent is the previous night's candidate — and the candidate is strictly
#: better, so the promoted decision is the honest one over these counts.
BASELINE_HELDOUT = [
    Outcome.SOLVED,
    Outcome.SOLVED,
    Outcome.UNVERIFIED,
    Outcome.OUT_OF_SCOPE,
    *[Outcome.NOT_SOLVED] * 8,
]
CANDIDATE_HELDOUT = [
    *[Outcome.SOLVED] * 3,
    Outcome.OUT_OF_SCOPE,
    Outcome.OUT_OF_SCOPE,
    *[Outcome.NOT_SOLVED] * 7,
]
INCUMBENT_HELDOUT = list(BASELINE_HELDOUT)

#: Source A's single instance: solved only by the candidate.
CANDIDATE_PUBLIC = [Outcome.SOLVED]
BASELINE_PUBLIC = [Outcome.NOT_SOLVED]
INCUMBENT_PUBLIC = [Outcome.NOT_SOLVED]


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


def _counts(candidate: str, source: str, outcomes: Sequence[Outcome]) -> Mapping[str, int]:
    """One side's six fields over one source, derived through `report.tally` by identity."""
    records = [
        _rollout(candidate, f"{source}-{index}", outcome)
        for index, outcome in enumerate(outcomes, start=1)
    ]
    counted = report.tally(candidate, records)
    return {
        field: getattr(counted, field)
        for field in ("denominator", "solved", "unverified", "covered", "failed", "weaker_wins")
    }


def _sides(
    *,
    candidate_heldout: Sequence[Outcome] = CANDIDATE_HELDOUT,
    incumbent_heldout: Sequence[Outcome] = INCUMBENT_HELDOUT,
) -> Mapping[str, Mapping[str, Mapping[str, int]]]:
    """The three sides, each over both sources, every count through `report.tally`."""
    return {
        "baseline": {
            "source-b": _counts("baseline", "heldout", BASELINE_HELDOUT),
            "source-a": _counts("baseline", "public", BASELINE_PUBLIC),
        },
        "candidate": {
            "source-b": _counts("candidate", "heldout", candidate_heldout),
            "source-a": _counts("candidate", "public", CANDIDATE_PUBLIC),
        },
        "incumbent": {
            "source-b": _counts("incumbent", "heldout", incumbent_heldout),
            "source-a": _counts("incumbent", "public", INCUMBENT_PUBLIC),
        },
    }


def _input(
    decision: str,
    *,
    sides: Mapping[str, Mapping[str, Mapping[str, int]]] | None = None,
) -> HonestNumberInput:
    """The writer's input over the standard fixture: plain values, nothing else."""
    return HonestNumberInput(
        sides=_sides() if sides is None else sides,
        decision=decision,
        funnel=FUNNEL,
        series=SERIES,
        provenance=PROVENANCE,
        recorded_on=RECORDED_ON,
    )


def test_the_promoted_headline_instantiates_the_registered_shape() -> None:
    """A promoted decision renders the § 4 shape exactly, with the candidate as final.

    `PREREGISTRATION.md:57-72` fixes the headline: `+a of b held-out tasks (baseline c of
    b, final d of b) / coverage e of b / N: f at baseline, g at final`. `a` is the count
    change between baseline and candidate over the held-out denominator; `e` is the final
    side's covered count (gate-resolution 6) — the candidate here reaches every task, so
    the coverage line reads 12 of 12 rather than the baseline's 11 — and `f`/`g` are the
    baseline's and final side's `weaker_wins`.
    """
    document = build_honest_number_report(_input("promoted"))

    assert "+1 of 12 held-out tasks (baseline 2 of 12, final 3 of 12)" in document.markdown, (
        "WHY THIS IS A FAILURE: the headline does not instantiate the pre-registered shape "
        "with the candidate as the final side. `delta` is `solved_final - solved_baseline` "
        "over the held-out denominator, and the letters of PREREGISTRATION.md:69-72 are "
        "the shape, not a suggestion"
    )
    assert "coverage 12 of 12     N: 1 at baseline, 2 at final" in document.markdown, (
        "WHY THIS IS A FAILURE: the headline's coverage is not the final side's covered "
        "count (12 of 12 here, since the candidate reaches every task), and the two `N` "
        "values are not the baseline's and final side's `weaker_wins` published together"
    )


def test_a_rejected_decision_renders_the_incumbent_as_final_with_the_candidate_disclosed() -> (
    None
):
    """A rejected decision makes the incumbent's counts final; the candidate is disclosed.

    Nothing shipped under a rejection, so the headline's "final" is the incumbent's counts
    — the delta against the baseline is the honest zero here (equal solves reject by the
    `>` term) — and the candidate's counts render beside them labelled as the rejected
    attempt, never "final".
    """
    regressed = [Outcome.SOLVED, *[Outcome.NOT_SOLVED] * 11]
    document = build_honest_number_report(
        _input("rejected", sides=_sides(candidate_heldout=regressed))
    )

    assert "+0 of 12 held-out tasks (baseline 2 of 12, final 2 of 12)" in document.markdown, (
        "WHY THIS IS A FAILURE: a rejected decision must render the incumbent as final — "
        "the delta is the incumbent's against the baseline, rendered as plainly as a "
        "positive one"
    )
    assert "candidate (rejected attempt)" in document.markdown, (
        "WHY THIS IS A FAILURE: the candidate's counts are not labelled as the rejected "
        "attempt — an unlabelled candidate's counts next to the incumbent's read as a "
        "comparison that was never decided"
    )
    assert "incumbent (final)" in document.markdown, (
        "WHY THIS IS A FAILURE: the incumbent's counts are not labelled as final, but "
        "nothing shipped and its counts are the only ones the headline may be read against"
    )


def test_an_unverified_decision_renders_no_headline_and_no_delta() -> None:
    """UNVERIFIED renders the decision and both sides' counts, and never a delta.

    No comparison was actually made (`PREREGISTRATION.md:111-114`), so the document holds
    no `+a of b held-out tasks` line, no coverage line, no `N at baseline/at final` line,
    and the word "final" nowhere — the candidate's counts are not final, the incumbent's
    are not final, and a line that reads as a win is the one thing this document may not
    be.
    """
    document = build_honest_number_report(_input("UNVERIFIED"))

    assert "UNVERIFIED" in document.markdown, (
        "WHY THIS IS A FAILURE: the decision is not stated — a reader could not tell this "
        "document from one that made a comparison"
    )
    assert "no comparison was made" in document.markdown.lower(), (
        "WHY THIS IS A FAILURE: the document does not state that no comparison was made — "
        "the sentence is the whole reason the headline is absent"
    )
    assert not re.search(r"\+?\s*-?\d+\s+of\s+\d+\s+held-out tasks", document.markdown), (
        "WHY THIS IS A FAILURE: the document renders a headline for an evaluation that "
        "never compared anything. A delta is a comparison, and none was made"
    )
    assert not re.search(r"coverage\s+\d+\s+of\s+\d+", document.markdown), (
        "WHY THIS IS A FAILURE: the headline's coverage line renders where the headline "
        "is forbidden"
    )
    assert "at baseline" not in document.markdown and "at final" not in document.markdown, (
        "WHY THIS IS A FAILURE: the headline's `N: f at baseline, g at final` line "
        "renders — but without a comparison there is no final side and no paired `N`"
    )
    for banned in ("final counts", "final side", "(final)", "at final"):
        assert banned not in document.markdown, (
            "WHY THIS IS A FAILURE: "
            f"{banned!r} appears in a document whose evaluation made no comparison — "
            "either side's counts reading as final is a win that was never measured. "
            "(The delta *definition*'s `solved_final` is a denial, not a win, and is "
            "allowed exactly because it is one.)"
        )
    assert "candidate" in document.markdown and "incumbent" in document.markdown, (
        "WHY THIS IS A FAILURE: the decision's counts — both sides' — are not rendered"
    )


def test_source_a_renders_per_instance_with_the_funnel_never_as_a_rate() -> None:
    """Source A's single instance renders with the funnel beside it, over its denominator.

    `PREREGISTRATION.md:140-155`: source A is the outcome of the named instance with the
    filter's funnel first — the eligibility and the refusals by gate, every count over its
    denominator — and it is never a rate and never a benchmark set. Both sources share the
    document, and each side's result is the instance's outcome.
    """
    document = build_honest_number_report(_input("promoted"))
    markdown = document.markdown

    assert f"Eligible: 1 of 300 instances — `{FLASK}`" in markdown, (
        "WHY THIS IS A FAILURE: the funnel's eligibility is not rendered per-instance — "
        "a reader must see the denominator before the result"
    )
    assert "Refused: 299 of 300, by gate: format 192 of 299, environment 106 of 299, " in (
        markdown
    ), (
        "WHY THIS IS A FAILURE: the refusals are not rendered against the gate that made "
        "each one, each over the refused denominator"
    )
    assert "collectability 1 of 299" in markdown, (
        "WHY THIS IS A FAILURE: the last gate's refusal is missing from the funnel line"
    )
    assert (
        "- **baseline — Result for `pallets__flask-4045`:** not solved under STRICT (0 of 1)."
        in markdown
    ), "WHY THIS IS A FAILURE: the baseline side's per-instance result does not render"
    assert "- **candidate — Result for `pallets__flask-4045`:** solved under STRICT (1 of 1)." in (
        markdown
    ), "WHY THIS IS A FAILURE: the candidate side's per-instance result does not render"
    assert "%" not in markdown, (
        "WHY THIS IS A FAILURE: source A renders as a rate — a single instance's result "
        "is a count over its denominator, never a proportion"
    )
    assert "not quoted as one" in markdown, (
        "WHY THIS IS A FAILURE: the document does not deny quoting source A as a public "
        "benchmark set — one instance is not a measurement"
    )


def test_the_headline_renders_a_zero_or_negative_delta_plainly() -> None:
    """A zero or negative delta renders in the headline's place with the same shape.

    `PREREGISTRATION.md:157-159`: a zero or negative delta is published as plainly as a
    positive one, in the same place, with the same prominence — the sign is the delta's
    own, never a softening.
    """
    equal = _sides(incumbent_heldout=BASELINE_HELDOUT)
    worse = _sides(incumbent_heldout=[Outcome.SOLVED, *[Outcome.NOT_SOLVED] * 11])

    zero = build_honest_number_report(_input("rejected", sides=equal))
    negative = build_honest_number_report(_input("rejected", sides=worse))

    assert "+0 of 12 held-out tasks (baseline 2 of 12, final 2 of 12)" in zero.markdown, (
        "WHY THIS IS A FAILURE: a zero delta renders with different prominence — the "
        "pre-registered shape carries the sign of the delta it reports"
    )
    assert "-1 of 12 held-out tasks (baseline 2 of 12, final 1 of 12)" in negative.markdown, (
        "WHY THIS IS A FAILURE: a negative delta renders with different prominence — the "
        "shape carries the sign, and a negative one is a publishable outcome"
    )


def test_the_payload_carries_the_counts_the_decision_was_read_from() -> None:
    """The sidecar: both sources' six fields, the decision, the headline, `N`, provenance.

    The machine-readable half mirrors the evidence documents' shapes: each side carries
    exactly the six fields the sealed documents carry, the headline block carries the
    delta with the counts it was read from and whose side is final, the `n` block carries
    both `N` values with the pre-registered `_N_SENTENCE` **by identity**, and the
    provenance carries the pinned inputs and the generation contract in the report's own
    published shape.
    """
    payload = json.loads(build_honest_number_report(_input("promoted")).payload)

    assert payload["schema"] == report.HONEST_NUMBER_REPORT_SCHEMA, payload
    assert payload["measured"] is True, payload
    assert payload["decision"] == "promoted", payload
    assert payload["sides"]["baseline"]["source-b"] == {
        "denominator": HELDOUT,
        "solved": 2,
        "unverified": 1,
        "covered": 11,
        "failed": 9,
        "weaker_wins": 1,
    }, "WHY THIS IS A FAILURE: source B's six tally fields over its own denominator"
    assert set(payload["sides"]["candidate"]["source-b"]) == {
        "denominator",
        "solved",
        "unverified",
        "covered",
        "failed",
        "weaker_wins",
    }, (
        "WHY THIS IS A FAILURE: a side carries a field the evidence documents do not "
        "carry — a published count a later reader cannot place is worse than an absent "
        "one"
    )
    assert payload["headline"] == {
        "delta": 1,
        "denominator": HELDOUT,
        "baseline_solved": 2,
        "final_solved": 3,
        "coverage": 12,
        "final_side": "candidate",
    }, (
        "WHY THIS IS A FAILURE: the headline block does not carry the delta with every "
        "count it was read from and whose side is final"
    )
    assert payload["n"]["baseline"] == {
        "count": 1,
        "denominator": HELDOUT,
        "sentence": report._N_SENTENCE,
    }, "WHY THIS IS A FAILURE: the baseline `N` block is not the count, denominator and "
    "pre-registered sentence"
    assert payload["n"]["final"]["count"] == 2, payload["n"]
    assert payload["n"]["final"]["sentence"] == report._N_SENTENCE, (
        "WHY THIS IS A FAILURE: `N`'s sentence is a re-spelling, not the pre-registered "
        "constant — a second spelling could soften or sharpen what the number claims"
    )
    assert payload["provenance"]["generation_contract"]["sampler"] == CONTRACT.sampler, (
        "WHY THIS IS A FAILURE: the sidecar's contract block is not the generation "
        "contract's own published shape"
    )


def test_the_declaration_holds_no_count_in_any_spelling(tmp_path: Path) -> None:
    """The committed state before the first evaluation: declared, holding no figure.

    The report has not run, so the artifacts cannot carry a figure — neither the
    report's own (none exists) nor any existing home's (restating one is forbidden). The
    declaration says exactly that in the writer's own sentence, renders no contract
    fields, no per-side counts and no series, and holds no `N of M` figure anywhere in
    the three artifacts.
    """
    document = build_honest_number_report(_input("promoted"), measured=False)
    written = write_honest_number_report(document, tmp_path / "declaration")

    assert "No count is measured here: the report has not run." in Path(written[0]).read_text(
        encoding="utf-8"
    ), (
        "WHY THIS IS A FAILURE: a directory whose report has not run says nothing about "
        "that. A reader finding counts here later could not tell when they appeared"
    )
    payload = json.loads(Path(written[1]).read_text(encoding="utf-8"))
    assert payload["measured"] is False, payload
    assert payload["schema"] == report.HONEST_NUMBER_REPORT_SCHEMA, payload
    for name in (
        "sides",
        "headline",
        "n",
        "funnel",
        "series",
        "provenance",
        "generation_contract",
    ):
        assert name not in payload, (
            f"WHY THIS IS A FAILURE: the declaration carries {name}, but no measurement "
            "exists"
        )
    for artifact in written:
        text = Path(artifact).read_text(encoding="utf-8")
        assert not re.search(r"\d+ of \d+", text), (
            f"WHY THIS IS A FAILURE: {artifact.name} renders a figure, but no "
            "measurement exists. A count here would be a restated figure from another "
            "home or an invented one"
        )
        assert "retry budget" not in text, (
            f"WHY THIS IS A FAILURE: {artifact.name} renders contract fields, but no "
            "count was measured under any contract"
        )


def test_the_declaration_is_writer_generated_not_hand_typed(tmp_path: Path) -> None:
    """The declaration's sentence is the writer's own constant — never a hand edit.

    The committed declaration's provenance is the writer: the sentence is a module
    constant of `report.py`, and the same constant is what the written artifacts carry,
    in the JSON document and in the human render alike — a hand-typed twin that drifted
    from the register would fail these identity assertions.
    """
    document = build_honest_number_report(_input("promoted"), measured=False)
    assert document.payload and "No count is measured here: the report has not run." in (
        document.markdown
    )
    assert json.loads(document.payload)["declaration"] == report._HONEST_NUMBER_DECLARATION, (
        "WHY THIS IS A FAILURE: the declaration document does not carry the writer's own "
        "constant — a hand-typed sentence could drift from the register"
    )
    written = write_honest_number_report(document, tmp_path / "declaration")
    assert report._HONEST_NUMBER_DECLARATION in Path(written[0]).read_text(
        encoding="utf-8"
    ), "WHY THIS IS A FAILURE: the human render does not state the declaration sentence"
    cost = json.loads(Path(written[2]).read_text(encoding="utf-8"))
    assert cost["recorded_on"] == RECORDED_ON, (
        "WHY THIS IS A FAILURE: the cost sidecar does not carry the declared date"
    )
    assert cost["cost"] == "no cost is measured here", (
        "WHY THIS IS A FAILURE: the cost sidecar states a cost where none was measured"
    )


def test_the_writer_is_deterministic_in_process(tmp_path: Path) -> None:
    """Identical inputs render byte-identical artifacts; `recorded_on` is an input.

    The committed artifact must be regenerable byte-for-byte — a reader who regenerates
    it and gets different bytes cannot tell a re-render from a re-measurement — and the
    date must come from the operator's declaration, never from a clock, so two renders
    of the same documented command agree.
    """
    first = write_honest_number_report(
        build_honest_number_report(_input("promoted")), tmp_path / "one"
    )
    second = write_honest_number_report(
        build_honest_number_report(_input("promoted")), tmp_path / "two"
    )
    for one, two in zip(first, second, strict=True):
        assert one.read_bytes() == two.read_bytes(), (
            f"WHY THIS IS A FAILURE: {one.name} differs between two renders of the same "
            "inputs — the committed document could not be regenerated byte-for-byte"
        )

    different_date = dataclasses.replace(_input("promoted"), recorded_on="2026-08-28")
    third = write_honest_number_report(
        build_honest_number_report(different_date), tmp_path / "three"
    )
    for one, three in zip(first, third, strict=True):
        assert one.read_bytes() != three.read_bytes(), (
            f"WHY THIS IS A FAILURE: {one.name} ignores the declared date — "
            "`recorded_on` must be an input, never a clock reading, and a changed input "
            "must change the bytes"
        )


def _payload() -> str:
    """The JSON sidecar for the standard promoted fixture. Called in and out of process."""
    return build_honest_number_report(_input("promoted")).payload


def test_the_same_inputs_produce_a_byte_identical_payload_across_processes() -> None:
    """Twice in this process, and twice more in fresh ones under different hash seeds.

    A report that differs run to run cannot be the committed evidence for a decision,
    because a reader who regenerates it and gets different bytes has no way to tell a
    re-render from a re-measurement. The subprocess half is not ceremony: mapping
    iteration order and set iteration order are the two things that vary across
    processes and not within one, and `PYTHONHASHSEED` is what makes that variation
    actually happen rather than merely be possible.
    """
    program = (
        f"import sys; sys.path.insert(0, {str(REPO_ROOT / 'tests')!r});"
        "from bakeoff.test_honest_number_report import _payload; sys.stdout.write(_payload())"
    )
    outputs = {
        seed: subprocess.run(
            [sys.executable, "-c", program],
            capture_output=True,
            check=True,
            text=True,
            env={"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": seed},
        ).stdout
        for seed in ("0", "1")
    }
    assert outputs["0"] == outputs["1"] == _payload(), (
        "WHY THIS IS A FAILURE: the sidecar's bytes depend on the process that produced "
        "them, so some mapping or set is being serialised in iteration order. Sort it: "
        "the report is a committed artefact and its diff must mean something"
    )


def test_the_honest_number_writer_reuses_the_shared_helpers_by_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The writer renders through the report module's own helpers — a copy would not feel a patch.

    The by-identity discipline asserted `is`: `build_honest_number_report` calls the
    report module's own `_row`, `_over`, `_contract_fields` and `_contract_block` by
    name, so a re-implementation (a copy) could never have been swapped for the module's
    own objects. The patch is the proof: replacing one helper's binding at the module
    changes the writer's output, which only holds when the writer resolves the helper
    from the module rather than carrying a copy of it.
    """
    import whetstone.bakeoff.report as report_module

    helpers = {
        "_row": lambda label, counts, pick: "| patched-row |",
        "_over": lambda count, denominator: "patched-over",
        "_contract_fields": lambda contract: "patched-fields",
        "_contract_block": lambda contract: {"patched": True},
    }
    for name, replacement in helpers.items():
        monkeypatch.setattr(report_module, name, replacement)
        document = build_honest_number_report(_input("promoted"))
        assert "patched" in document.markdown or "patched" in document.payload, (
            f"WHY THIS IS A FAILURE: patching the module's own {name} did not change "
            "the writer's output, so the writer carries a copy of the helper rather "
            "than resolving it by identity"
        )
        monkeypatch.undo()


def test_the_n_counts_are_the_tally_definition_by_identity() -> None:
    """The `N` figures are `report.tally`'s `weaker_wins`, never a re-implementation.

    `PREREGISTRATION.md:96-100` defines `N` as `count(rollouts where WEAK == PASS and
    STRICT == FAIL)`, and `tally` is the single place that count is defined — the
    fixture derives every side's counts through it over the same synthetic records, and
    the document renders exactly those `weaker_wins` values with the pre-registered
    sentence, never a re-derived number and never a new spelling.
    """
    counted = report.tally(
        "candidate",
        [
            _rollout("candidate", f"n-{index}", outcome)
            for index, outcome in enumerate(CANDIDATE_HELDOUT, start=1)
        ],
    )
    document = build_honest_number_report(_input("promoted"))
    assert counted.weaker_wins == 2, (
        "WHY THIS IS A FAILURE: the fixture's `N` is not what `tally` counts over the "
        "same records — the test's own definition has drifted from the single one"
    )
    assert "N: 1 at baseline, 2 at final" in document.markdown, (
        "WHY THIS IS A FAILURE: the headline's `N` figures are not the tally definition's "
        "`weaker_wins` for the baseline and the final side"
    )
    assert (
        "- final: 2 rollouts a weaker check would have scored as wins. (2 of 12)"
        in document.markdown
    ), (
        "WHY THIS IS A FAILURE: the final `N` sentence is not the pre-registered one "
        "over its denominator"
    )


def test_the_locality_canary_holds_donor_text_out_of_every_artifact(tmp_path: Path) -> None:
    """Planted donor source text reaches no artifact: counts, verdicts, provenance only.

    The document may carry counts, verdicts and provenance — never task contents, never
    patch content. The canary plants a distinctive donor source line into the input's
    three most plausible smuggling vectors — an extra key in a side's counts, an extra
    key in the provenance, an extra key in a retry fact — and asserts the line reaches
    none of the three written artifacts.
    """
    donor = "def donor_kept_out_of_the_report(): return 0xC0FFEE  # donor-a only"
    sides = _sides()
    smuggled_sides = {
        "baseline": {
            "source-b": {**sides["baseline"]["source-b"], "task_contents": donor},
            "source-a": sides["baseline"]["source-a"],
        },
        "candidate": sides["candidate"],
        "incumbent": sides["incumbent"],
    }
    smuggled_provenance = {
        **PROVENANCE,
        "donor_note": donor,
        "retries": [{**PROVENANCE["retries"][0], "completion_sha256": donor}],
    }
    smuggled = dataclasses.replace(
        _input("promoted", sides=smuggled_sides), provenance=smuggled_provenance
    )
    written = write_honest_number_report(
        build_honest_number_report(smuggled), tmp_path / "home"
    )

    for artifact in written:
        assert donor not in Path(artifact).read_text(encoding="utf-8"), (
            f"WHY THIS IS A FAILURE: {artifact.name} carries the planted donor source "
            "line — a document that can hold task contents is a document that will "
            "eventually publish one"
        )


def _figures(text: str) -> set[tuple[str, str]]:
    """Every `N of M` figure in the text, as the scan of the one-home guard reads it."""
    return {pair for pair in re.findall(r"\b(\d+) of (\d+)\b", text)}


def _baseline_artifact() -> Mapping[str, object]:
    """The sealed § 3 baseline artifact the door would read — the fixture's own.

    The writer's baseline-side counts must equal this artifact's figures byte-for-byte:
    the door feeds the writer the artifact's values, never a copy, and the disjointness
    exception admits exactly those figures.
    """
    baseline = _counts("baseline", "heldout", BASELINE_HELDOUT)
    public = _counts("baseline", "public", BASELINE_PUBLIC)
    return {
        "schema": "whetstone-baseline/1",
        "measured": True,
        "recorded_on": "2026-08-26",
        "series": dict(SERIES),
        "sides": {
            "source-b": dict(baseline),
            "source-a": dict(public),
        },
        "n": {
            "count": baseline["weaker_wins"],
            "denominator": baseline["denominator"],
            "sentence": report._N_SENTENCE,
        },
        "retries": {
            "retry_count": PROVENANCE["retry_count"],
            "spent": 2,
            "tasks": list(PROVENANCE["retries"]),
        },
        "evidence": {"schema": "whetstone-baseline-run/1", "digest": "e" * 64},
        "tool_versions": dict(PROVENANCE["tool_versions"]),
        "non_comparable": True,
    }


def _artifact_derived_figures(artifact: Mapping[str, object]) -> set[tuple[str, str]]:
    """Every figure the sealed artifact's sides carry — the exception's admitted set."""
    figures: set[tuple[str, str]] = set()
    for source in ("source-b", "source-a"):
        counts = artifact["sides"][source]
        for field in ("solved", "covered", "unverified", "failed", "weaker_wins"):
            figures.add((str(counts[field]), str(counts["denominator"])))
    return figures


def _baseline_rendered_figures(artifact: Mapping[str, object]) -> set[tuple[str, str]]:
    """The baseline-side figures the writer's markdown renders from the artifact's values.

    Source B renders its five count fields over the held-out denominator; source A
    renders the named instance's solved count over its own denominator.
    """
    rendered: set[tuple[str, str]] = set()
    source_b = artifact["sides"]["source-b"]
    for field in ("solved", "covered", "unverified", "failed", "weaker_wins"):
        rendered.add((str(source_b[field]), str(source_b["denominator"])))
    source_a = artifact["sides"]["source-a"]
    rendered.add((str(source_a["solved"]), str(source_a["denominator"])))
    return rendered


def _build_homes(root: Path) -> None:
    """The four existing homes' artifacts in a synthetic tree, with known figures.

    The figures mirror the committed homes' denominators (63, 20, 62, 64 — the real
    artifacts' own), minus the funnel figures the honest-number document is pre-registered
    to render: the eligibility and refusal counts belong to the committed rejection
    ledger, and the aspect-4 guard decides how the ledger-derived exception is argued.
    The one figure that deliberately collides with the writer's document is `0 of 1` —
    the bake-off's own source-A result — because it equals the sealed baseline artifact's
    source-A figure, the loader-by-identity exception this suite asserts by name.
    """
    figures = {
        "baseline": ["0 of 1", "0 of 63", "42 of 63", "189 of 189"],
        "format-hardening": ["0 of 20", "4 of 20", "10 of 20"],
        "easier-stratum": ["0 of 62", "31 of 62", "37 of 62"],
        "larger-base": ["0 of 64", "43 of 64", "50 of 64"],
    }
    for directory, home_figures in figures.items():
        home = root / "reports" / directory
        home.mkdir(parents=True)
        for name in ("report.md", "report.json", "cost.json"):
            (home / name).write_text(" ".join(home_figures), encoding="utf-8")


def _homes_figures(root: Path) -> set[tuple[str, str]]:
    """Every figure in the four synthetic homes' twelve artifacts."""
    figures: set[tuple[str, str]] = set()
    for directory in ("baseline", "format-hardening", "easier-stratum", "larger-base"):
        for name in ("report.md", "report.json", "cost.json"):
            figures |= _figures(
                (root / "reports" / directory / name).read_text(encoding="utf-8")
            )
    return figures


def test_the_honest_number_report_restates_no_figure_from_an_existing_home(
    tmp_path: Path,
) -> None:
    """*(adversarial)* No rendered figure lives in any of the four existing homes' artifacts.

    The honest-number home joins the guard on the same rule the earlier homes joined it
    on, asserted the strongest way available: every `N of M` figure the writer renders is
    disjoint from every `N of M` figure the four existing homes' artifacts render —
    except the loader-derived baseline figures. The pre-registered shape requires the
    baseline's counts (`baseline c of b`); those figures are the sealed § 3 artifact's
    own (the fixture provides the artifact-derived values, asserted byte-equal to what
    the writer renders); and the exception is exercised and admitted by name — the one
    overlap, `0 of 1`, is exactly the artifact's source-A figure.
    """
    _build_homes(tmp_path)
    honest = tmp_path / "honest-number"
    write_honest_number_report(build_honest_number_report(_input("promoted")), honest)

    writer = _figures(
        " ".join(
            (honest / name).read_text(encoding="utf-8")
            for name in ("report.md", "report.json", "cost.json")
        )
    )
    assert writer, (
        "WHY THIS IS A FAILURE: the report renders no figures at all, so this test's "
        "disjointness assertion would pass vacuously over an empty document"
    )
    existing = _homes_figures(tmp_path)
    assert existing, (
        "WHY THIS IS A FAILURE: none of the synthetic homes renders an `N of M` figure, "
        "so the disjointness guard has nothing to guard against"
    )

    artifact = _baseline_artifact()
    allowed = _artifact_derived_figures(artifact)
    rendered_baseline = _baseline_rendered_figures(artifact)
    assert rendered_baseline <= writer, (
        "WHY THIS IS A FAILURE: the baseline-side figures the writer renders are not "
        "the sealed artifact's own, byte-equal — the loader-by-identity claim is the "
        "whole ground the exception stands on"
    )
    assert rendered_baseline <= allowed, (
        "WHY THIS IS A FAILURE: the exception admits figures the artifact does not "
        "carry — the admitted set must be exactly the artifact-derived one"
    )

    overlap = writer & existing
    assert overlap, (
        "WHY THIS IS A FAILURE: the exception is not exercised — no loader-derived "
        "figure collides with a home, so nothing proves the guard admits it"
    )
    assert overlap <= allowed, (
        f"WHY THIS IS A FAILURE: the report restates {sorted(overlap - allowed)}, which "
        "already lives in one of the existing homes' artifacts. A figure quoted twice "
        "is a figure that can disagree with itself, and the one-home rule exists so "
        "that cannot happen"
    )
    assert overlap == {("0", "1")}, (
        "WHY THIS IS A FAILURE: the loader-by-identity exception is not admitted by "
        "name — the only overlap must be the artifact's source-A figure, and nothing else"
    )


def _committed_home_figures() -> set[tuple[str, str]]:
    """Every `N of M` figure in the five committed homes' fifteen artifacts."""
    figures: set[tuple[str, str]] = set()
    for directory in (
        "baseline",
        "format-hardening",
        "easier-stratum",
        "larger-base",
        "baseline-measurement",
    ):
        for name in ("report.md", "report.json", "cost.json"):
            artifact = (REPO_ROOT / "reports" / directory / name).read_text(
                encoding="utf-8"
            )
            figures |= _figures(artifact)
    return figures


def _ledger_derived_figures(counts: Mapping[str, int]) -> set[tuple[str, str]]:
    """Every figure the committed rejection ledger's counts carry — the exception's admitted set.

    The ledger's own counts are the denominators the § 4 funnel renders over: the
    eligibility and the refusals by gate. The exception admits exactly these figures —
    anything else overlapping a committed home is a figure with two homes.
    """
    return {
        (str(counts["eligible"]), str(counts["input"])),
        (str(counts["ineligible"]), str(counts["input"])),
        (str(counts["format"]), str(counts["ineligible"])),
        (str(counts["environment"]), str(counts["ineligible"])),
        (str(counts["collectability"]), str(counts["ineligible"])),
    }


def _funnel_rendered_figures(counts: Mapping[str, int]) -> set[tuple[str, str]]:
    """The funnel figures the § 4 shape renders from the ledger's own counts.

    The writer renders `input.funnel`; this is what those values must be — the ledger's
    own, so a writer that recomputed them (or a fixture that drifted from the ledger)
    fails the byte-equality assertion below.
    """
    return {
        (str(counts["eligible"]), str(counts["input"])),
        (str(counts["ineligible"]), str(counts["input"])),
        (str(counts["format"]), str(counts["ineligible"])),
        (str(counts["environment"]), str(counts["ineligible"])),
        (str(counts["collectability"]), str(counts["ineligible"])),
    }


def test_the_funnel_figures_are_the_corpus_ledgers_own_and_are_admitted_by_name() -> None:
    """*(adversarial)* Source A's funnel figures are the rejection ledger's own — never recomputed.

    The § 4 shape renders the four-gate funnel beside source A's instance
    (`PREREGISTRATION.md:140-155`), and the same counts are committed facts in
    `tasks/public/ineligible.json` — and in `reports/baseline/`'s own funnel line. So
    the honest-number home admits a second, ledger-derived exception, mirrored on the
    loader-by-identity baseline exception: the funnel figures the report renders are
    asserted equal to the corpus ledger's own counts — never recomputed, exactly as the
    loader exception asserts the baseline figures byte-equal to the sealed artifact —
    and the only figures the writer may share with a committed home are exactly the two
    admitted sets: the sealed baseline artifact's and the rejection ledger's, named
    here and in `PREREGISTRATION.md` § 10.9.
    """
    document = build_honest_number_report(_input("promoted"))
    writer = _figures(" ".join((document.markdown, document.payload, document.cost)))
    assert writer, (
        "WHY THIS IS A FAILURE: the report renders no figures at all, so this test's "
        "disjointness assertion would pass vacuously over an empty document"
    )

    ledger = json.loads(
        (REPO_ROOT / "tasks" / "public" / "ineligible.json").read_text(encoding="utf-8")
    )
    counts = ledger["counts"]
    allowed = _ledger_derived_figures(counts)
    rendered_funnel = _funnel_rendered_figures(counts)
    assert rendered_funnel <= writer, (
        "WHY THIS IS A FAILURE: the funnel figures the § 4 shape renders from the "
        "ledger's own counts are not what the writer renders — the report's funnel was "
        "recomputed, or the fixture drifted from the ledger. The ledger-derived "
        "exception admits the ledger's own figures, byte-equal, never a re-derivation"
    )
    assert rendered_funnel <= allowed, (
        "WHY THIS IS A FAILURE: the exception admits figures the ledger does not "
        "carry — the admitted set must be exactly the ledger-derived one"
    )

    existing = _committed_home_figures()
    assert existing, (
        "WHY THIS IS A FAILURE: none of the committed homes renders an `N of M` "
        "figure, so the disjointness guard has nothing to guard against"
    )
    overlap = writer & existing
    assert overlap, (
        "WHY THIS IS A FAILURE: neither exception is exercised — no ledger-derived or "
        "loader-derived figure collides with a committed home, so nothing proves the "
        "guard admits them"
    )
    baseline_allowed = _artifact_derived_figures(_baseline_artifact())
    unadmitted = sorted(overlap - (allowed | baseline_allowed))
    assert overlap <= allowed | baseline_allowed, (
        f"WHY THIS IS A FAILURE: the report restates {unadmitted}, "
        "which already lives in one of the committed homes' artifacts and is admitted "
        "by neither exception. A figure quoted twice is a figure that can disagree "
        "with itself, and the one-home rule exists so that cannot happen"
    )
    assert overlap == {("0", "1")} | allowed, (
        "WHY THIS IS A FAILURE: the two exceptions are not admitted by name — the only "
        "overlaps with the committed homes must be the sealed artifact's source-A "
        "figure (the loader-by-identity exception) and the rejection ledger's funnel "
        "counts (the ledger-derived exception), and nothing else"
    )


def test_the_honest_number_disjointness_guard_catches_a_planted_figure(
    tmp_path: Path,
) -> None:
    """*(adversarial)* The scan above can see a planted collision with an existing home.

    The synthetic homes' figures are disjoint from the writer's by construction — the
    only overlap is the loader-derived baseline figure, admitted by the exception. A
    planted `10 of 20` — a figure the format-hardening home actually renders — added to
    a copy of the new home's sidecar must be found by the same scan. A collision the
    guard cannot see is a figure with two homes.
    """
    _build_homes(tmp_path)
    honest = tmp_path / "honest-number"
    write_honest_number_report(build_honest_number_report(_input("promoted")), honest)

    artifact = _baseline_artifact()
    allowed = _artifact_derived_figures(artifact)
    existing = _homes_figures(tmp_path)
    clean = _figures((honest / "report.json").read_text(encoding="utf-8")) & existing
    assert clean <= allowed, (
        "WHY THIS IS A FAILURE: the clean render already collides with a home beyond "
        "the loader-derived exception, so the planted half of this control is not "
        "testing the guard's logic"
    )

    planted = honest / "report.json"
    planted.write_text(
        planted.read_text(encoding="utf-8") + '"planted": "10 of 20"\n', encoding="utf-8"
    )
    overlap = _figures(planted.read_text(encoding="utf-8")) & existing
    assert ("10", "20") in overlap and ("10", "20") not in allowed, (
        "WHY THIS IS A FAILURE: the planted `10 of 20` was absorbed by the guard's "
        "scan. A collision the guard cannot see is a figure with two homes, and the "
        "next reader has no way to tell which of two disagreeing numbers is the real one"
    )

