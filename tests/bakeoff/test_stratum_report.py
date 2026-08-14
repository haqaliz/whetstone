"""The easier-stratum probe's report: a changed task set, declared non-comparable.

The probe scores a different task set — a pre-committed difficulty stratum of the
declared source-B set — under the same hardened contract, so its figures are a **new
series**, declared non-comparable to both existing homes (`PREREGISTRATION.md` § 10.5):
`reports/baseline/` remains the only home of the baseline's figures,
`reports/format-hardening/` the only home of the hardened arm's, and
`reports/easier-stratum/` the only home of the probe's. This file holds the writer that
renders the probe's home — `build_stratum_report` / `write_stratum_report` in
`whetstone.bakeoff.report` — the same three-artifact layout a reader learns once, and the
declaration-only state the committed directory holds until the probe runs.

**Nothing here runs a model, a sandbox, a verifier, or the network.** Every `Rollout`
below is constructed by hand. Nothing is written outside `tmp_path`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path

from whetstone.bakeoff.report import (
    GenerationContract,
    StratumReport,
    build_stratum_report,
    tally,
    write_stratum_report,
)
from whetstone.bakeoff.scoring import Outcome, Rollout
from whetstone.verify.verdict import Status

#: What each outcome implies about the two verifiers when a test does not say otherwise.
VERDICTS: dict[Outcome, tuple[Status | None, Status | None]] = {
    Outcome.SOLVED: (Status.PASS, Status.PASS),
    Outcome.NOT_SOLVED: (Status.FAIL, Status.FAIL),
    Outcome.NOT_APPLIED: (Status.FAIL, Status.FAIL),
    Outcome.OUT_OF_SCOPE: (Status.FAIL, Status.PASS),
    Outcome.NO_DIFF: (None, None),
    Outcome.UNVERIFIED: (Status.UNVERIFIED, Status.UNVERIFIED),
    Outcome.UNPROVISIONED: (Status.UNVERIFIED, None),
    Outcome.NO_ORACLE: (Status.UNVERIFIED, Status.UNVERIFIED),
}


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


def _records(candidate: str, outcomes: Sequence[Outcome]) -> list[Rollout]:
    """A record per outcome, task ids numbered from one so two candidates cannot collide."""
    return [
        _rollout(candidate, f"task-{index}", outcome)
        for index, outcome in enumerate(outcomes, start=1)
    ]


#: The stratum's contract: the hardened shape — retry budget, retry template digest,
#: diagnosis vocabulary digest, retrieval oracle, a declared dev subset.
STRATUM_CONTRACT = GenerationContract(
    prompt_sha256="a" * 64,
    sampler="greedy",
    max_tokens=600,
    extractor_version="1",
    dev_subset=("dev-a", "dev-b"),
    retry_budget=2,
    retry_template_sha256="b" * 64,
    diagnosis_vocabulary_version="c" * 64,
    retrieval="oracle",
)

#: The committed stratum document the probe scores — named as a pointer, never parsed.
STRATUM_DOC = "tasks/stratum/easier.json"

#: The gitignored home of the probe's classifier counts — the runbook's declared home,
#: named as a pointer, never parsed.
BREAKDOWN_HOME = "runs/easier-stratum-arm/"

#: A declared-not-yet-measured date for the stratum document. An input, never the clock.
RECORDED_ON = "2026-08-14"


def _stratum_tallies():
    """Two synthetic candidates over denominators that collide with nothing committed.

    The six existing artifacts' figures use denominators 1, 62, 63, 64, 189, 299 and 300,
    so 37 and 41 keep the disjointness guard honest without arithmetic acrobatics.
    """
    return (
        tally("one", _records("one", [Outcome.SOLVED] * 5 + [Outcome.NOT_SOLVED] * 32)),
        tally(
            "two",
            _records(
                "two",
                [Outcome.SOLVED] * 7
                + [Outcome.OUT_OF_SCOPE] * 3
                + [Outcome.NO_DIFF] * 5
                + [Outcome.NOT_SOLVED] * 26,
            ),
        ),
    )


def _stratum_document() -> StratumReport:
    """The rendered stratum document for the synthetic tallies, and its sidecars."""
    return build_stratum_report(
        tallies=_stratum_tallies(),
        contract=STRATUM_CONTRACT,
        stratum_doc=STRATUM_DOC,
        breakdown_home=BREAKDOWN_HOME,
        recorded_on=RECORDED_ON,
        generation_seconds=333.0,
    )


def test_the_stratum_writer_writes_the_three_artifacts_and_nothing_else(
    tmp_path: Path,
) -> None:
    """report.md, report.json and cost.json — the same shape every home has.

    A reader learns one layout for all three report directories; a fourth file in any of
    them is a stray with a figure-shaped home. Nothing is written outside the destination.
    """
    into = tmp_path / "easier-stratum"
    written = write_stratum_report(_stratum_document(), into)

    assert {path.name for path in written} == {"report.md", "report.json", "cost.json"}, (
        f"WHY THIS IS A FAILURE: the writer produced {[path.name for path in written]}. "
        "The directory's committed shape is the same three artifacts as every other home"
    )
    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")) == [
        "easier-stratum",
        "easier-stratum/cost.json",
        "easier-stratum/report.json",
        "easier-stratum/report.md",
    ], "WHY THIS IS A FAILURE: the writer touched a path outside the destination it was given"


def test_the_stratum_document_is_a_pure_function_of_its_inputs() -> None:
    """The same inputs render byte-identical output, like every other report.

    The stratum report is committed evidence once the probe runs; a reader who
    regenerates it and gets different bytes cannot tell a re-render from a re-measurement.
    The three strings are asserted together, so no half of the document can drift alone.
    """
    first = _stratum_document()
    second = _stratum_document()
    assert (first.markdown, first.payload, first.cost) == (
        second.markdown,
        second.payload,
        second.cost,
    ), (
        "WHY THIS IS A FAILURE: two renders of the same inputs differ, so the committed "
        "document could not be regenerated byte-for-byte and its diff would mean nothing"
    )


def test_the_declaration_only_state_carries_no_count_and_no_contract() -> None:
    """The committed state of the home: declared, not yet measured, holding no figure.

    The probe has not run, so the committed artifacts cannot carry a figure — neither the
    probe's own (none exists) nor any existing home's (restating one is forbidden). The
    declaration says exactly that, names the three homes non-comparable, renders no
    contract fields, and holds no `N of M` figure anywhere in the three artifacts.
    """
    document = build_stratum_report(
        tallies=(),
        contract=None,
        stratum_doc=STRATUM_DOC,
        breakdown_home=BREAKDOWN_HOME,
        recorded_on=RECORDED_ON,
    )
    payload = json.loads(document.payload)

    assert "No count is measured here: the probe has not run." in document.markdown, (
        "WHY THIS IS A FAILURE: a directory whose probe has not run says nothing about "
        "that. A reader finding counts here later could not tell when they appeared"
    )
    assert "non-comparable" in document.markdown, (
        "WHY THIS IS A FAILURE: the declaration does not state that the three homes are "
        "declared non-comparable — the argument the directory's existence rests on"
    )
    assert "reports/baseline/" in document.markdown, (
        "WHY THIS IS A FAILURE: the declaration does not name which directories' figures "
        "it does not restate"
    )
    assert "reports/format-hardening/" in document.markdown, (
        "WHY THIS IS A FAILURE: the declaration does not name which directories' figures "
        "it does not restate"
    )
    assert "retry budget" not in document.markdown, (
        "WHY THIS IS A FAILURE: the declaration renders contract fields, but no count was "
        "measured under any contract. The format-hardening declaration renders none either"
    )
    written = " ".join((document.markdown, document.payload, document.cost))
    assert not re.search(r"\d+ of \d+", written), (
        "WHY THIS IS A FAILURE: the declaration renders a figure, but no measurement "
        "exists. A count here would be a restated figure from another home or an invented "
        "one"
    )
    assert payload["non_comparable"] is True, (
        "WHY THIS IS A FAILURE: the sidecar does not declare the probe's figures "
        "non-comparable — the machine-readable half of the changed-task-set ground"
    )
    assert payload["generation_contract"] is None, payload
    assert payload["per_candidate"] is None, payload


def test_the_stratum_report_renders_every_contract_field_and_all_eight_rows() -> None:
    """The rendered report: the hardened contract's fields, the rows, the declaration.

    Every figure sits under the contract that produced it — retry budget, retry template
    digest, diagnosis vocabulary digest, retrieval, dev subset — in the per-candidate
    table's eight rows over the harness's own denominators, with the non-comparability
    sentence beside the changed-task-set declaration, both pointers, and the token spend.
    """
    document = _stratum_document()
    markdown = document.markdown
    payload = json.loads(document.payload)

    assert "retry budget 2" in markdown and ("b" * 64) in markdown and ("c" * 64) in markdown, (
        "WHY THIS IS A FAILURE: the hardened contract's retry fields — budget, retry "
        "template digest, diagnosis vocabulary digest — are not stated beside the figures"
    )
    assert "retrieval oracle" in markdown, (
        "WHY THIS IS A FAILURE: the retrieval setting is missing from the contract block, "
        "so the contract cannot be told apart from a different one programmatically"
    )
    assert "`dev-a`" in markdown and "`dev-b`" in markdown, (
        "WHY THIS IS A FAILURE: the development subset is not stated, so a reader cannot "
        "see which tasks were excluded from every count"
    )
    for row in (
        "solved",
        "coverage",
        "unverified",
        "N",
        "no diff",
        "patch apply",
        "patch scope",
        "not solved",
    ):
        assert f"| `{row}` |" in markdown, (
            f"WHY THIS IS A FAILURE: the {row!r} row is missing from the per-candidate "
            "table. The stratum report carries the same eight rows as the other homes"
        )
    assert "5 of 37" in markdown and "7 of 41" in markdown, (
        "WHY THIS IS A FAILURE: the per-candidate cells do not render the count over its "
        "denominator — PREREGISTRATION.md:157 refuses a bare proportion"
    )
    assert (
        "A figure measured on one side of a changed pinned input may not be compared with "
        "one measured on the other." in markdown
    ), (
        "WHY THIS IS A FAILURE: PREREGISTRATION.md:136-137's sentence does not sit beside "
        "the changed-task-set declaration. The probe differs from both existing homes in "
        "a pinned input — the task set — and the report must say the figures are not "
        "comparable"
    )
    assert "different task set" in markdown, (
        "WHY THIS IS A FAILURE: the changed-task-set ground is not stated. The whole "
        "argument the directory exists on is that the probe scores a different task set"
    )
    assert STRATUM_DOC in markdown, (
        "WHY THIS IS A FAILURE: the report names no stratum document. The changed-task-set "
        "claim must be checkable in the published document, and the pointer is how"
    )
    assert BREAKDOWN_HOME in markdown, (
        "WHY THIS IS A FAILURE: the report names no home for the classifier counts behind "
        "its figures. A count without a stated home is a count the next reader cannot check"
    )
    assert "never restates" in markdown.lower(), (
        "WHY THIS IS A FAILURE: a pointer does not say that this document does not restate "
        "what it points at. An unnamed prohibition is a prohibition nobody can check"
    )
    assert "333.0" in markdown, (
        "WHY THIS IS A FAILURE: the token-spend disclosure is missing. The probe's spend "
        "must be stated, like every other home's"
    )
    assert payload["stratum_doc"] == STRATUM_DOC, payload
    assert payload["breakdown_home"] == BREAKDOWN_HOME, payload
    assert payload["recorded_on"] == RECORDED_ON, payload
    assert payload["schema"] == "whetstone-stratum-report/1", payload
    assert payload["generation_contract"]["retry_budget"] == 2, payload
    assert payload["generation_contract"]["retrieval"] == "oracle", payload
    assert [one["candidate"] for one in payload["per_candidate"]] == ["one", "two"], payload
    assert payload["per_candidate"][0]["solved"] == 5, payload
    assert payload["per_candidate"][0]["denominator"] == 37, payload
    assert payload["per_candidate"][1]["weaker_wins"] == 3, payload
    assert payload["per_candidate"][1]["denominator"] == 41, payload
    cost = json.loads(document.cost)
    assert cost["kind"] == "stratum-report", cost
    assert cost["generation_seconds"] == 333.0, cost


def test_the_stratum_report_refuses_figures_without_a_contract() -> None:
    """A count and the contract that produced it belong together — a table without one refused.

    The door always passes the sidecar's contract; a direct writer invocation that passes
    tallies without one is refused by name rather than rendered as a contract-less count.
    """
    import pytest

    with pytest.raises(ValueError, match="tallies"):
        build_stratum_report(
            tallies=_stratum_tallies(),
            contract=None,
            stratum_doc=STRATUM_DOC,
            breakdown_home=BREAKDOWN_HOME,
            recorded_on=RECORDED_ON,
        )
