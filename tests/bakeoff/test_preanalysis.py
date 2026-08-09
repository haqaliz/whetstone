"""The measured arm's pre-analysis: the retry-eligible ceiling, computed before the arm spends.

The measured arm (`spec.md`, D-arm1) is a GPU pass whose halt condition is a ceiling computed
**before** any GPU spend: of the stored runs' parse-refusal records, how many could a retry
plausibly convert? This file pins that computation — the module that performs it, the mapping it
must use, and the locality rule its document must obey.

Three contracts hold, and each is an honesty property, so each is pinned here.

**The ceiling is a pre-registered definition, not a number that gets discovered.** The
definition lives in `preanalysis.py`'s docstring and in the `CEILING_DEFINITION` constant the
document carries — written before the run, never edited after the numbers land (`spec.md`
D-arm1: the definition is a finding's property, never a promise). The tests pin that the
document carries exactly that constant and that the arithmetic is the definition's: retry-
eligible minus inferred truncation, where retry-eligible is the validator's own mapping
(`diffcheck.trigger_of_cause`, asserted *by identity* below — never reimplemented) and
inferred truncation is a retry-eligible record whose detail names the `end-of-output` death.

**The mapping is diffcheck's, not a copy.** `trigger_of` is refactored into a pure
`trigger_of_cause(cause, detail)` that `trigger_of` delegates to; the pre-analysis reads stored
autopsy documents, which carry `cause`/`detail` strings rather than `AutopsyResult` objects, so
it needs the verdict split into its two fields — and the split must never fork the decision.
The cross-product assertion below pins the delegation: for every cause and every observed
detail, `trigger_of(AutopsyResult(...))` and `trigger_of_cause(...)` answer the same trigger.

**The document is local evidence, refused under any published path.** The pre-analysis reads
stored autopsy outputs — which quote the user's own private donor code back verbatim — and its
document is the analysis of that private material, so it belongs only under the same gitignored
roots the autopsy's own document refuses to leave (`autopsy.py:727-745`): `--out` is checked
before anything is read, and the refusal is exit 2 with the path and the root rule named.

All fixtures are synthetic replicas of the stored autopsy documents' shape (`runs/diff-autopsy/
{arm-a,budget-2048}.json`), toy candidates and task ids, tiny — never donor content
(`card.md:68-70`).
"""

from __future__ import annotations

import ast
import json
import shutil
from pathlib import Path

import pytest

from whetstone.bakeoff import diffcheck, preanalysis
from whetstone.bakeoff.autopsy import (
    IGNORED_OUT_ROOTS,
    AutopsyResult,
    DeathKind,
    FineCause,
)
from whetstone.bakeoff.autopsy import (
    OutNotPrivate as AutopsyOutNotPrivate,
)
from whetstone.bakeoff.autopsy import (
    refuse_published_out as autopsy_refuse_published_out,
)
from whetstone.bakeoff.diffcheck import Trigger, trigger_of, trigger_of_cause

#: The repository root, reached from `tests/bakeoff/`: the worktree the CLI's locality rule
#: resolves its roots against, and where the document-under-test is written.
REPO_ROOT = Path(__file__).resolve().parents[2]

# --------------------------------------------------------------------------------------------
# Synthetic autopsy documents, fixture-shaped like the stored outputs (`runs/diff-autopsy/`).
# --------------------------------------------------------------------------------------------


def _record(candidate: str, task_id: str, cause: str, detail: str) -> dict[str, object]:
    """One `whetstone-autopsy/1` record row, in the stored shape."""
    return {
        "candidate": candidate,
        "task_id": task_id,
        "cause": cause,
        "detail": detail,
        "markers": [],
        "recorded_cause": "WOULD_NOT_PARSE",
        "coarse_agrees": True,
    }


def _write_autopsy(tmp_path: Path, stem: str, records: list[dict[str, object]]) -> Path:
    """A whole `whetstone-autopsy/1` document on disk, replicating the stored documents' shape."""
    path = tmp_path / f"{stem}.json"
    path.write_text(
        json.dumps(
            {
                "schema": "whetstone-autopsy/1",
                "transcript": f"{stem}.jsonl",
                "attribution": f"{stem}-attribution.json",
                "rollouts": len(records),
                "breakdown": {},
                "marker_counts": {},
                "mapping_violations": [],
                "orphan_attribution_rows": [],
                "records": records,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


#: Run 1's records, a synthetic replica of arm-a's shape: a 14B-like candidate dominated by
#: `hunk-count-mismatch` with one end-of-output death inside it, a 3B-like candidate with a
#: first-hunk bare-line death plus the header-without-hunk and loop shapes, and nothing that
#: triggers for the 7B-like loop candidate.
ARM_A_RECORDS: list[dict[str, object]] = [
    _record("base-14b", "t-01", "hunk-count-mismatch", "hunk 1 body exceeds its declared counts"),
    _record("base-14b", "t-02", "hunk-count-mismatch", "hunk 2 dies early: bare-line"),
    _record("base-14b", "t-03", "hunk-count-mismatch", "hunk 3 dies early: end-of-output"),
    _record("base-14b", "t-04", "hunk-dies-early", "bare-line"),
    _record("base-14b", "t-05", "hunk-dies-early", "fence-cut"),
    _record("base-14b", "t-06", "well-formed", "all 1 hunks complete"),
    _record("base-3b", "t-07", "hunk-dies-early", "end-of-output"),
    _record(
        "base-3b", "t-08", "header-without-hunk",
        "a diff header was found but no hunk followed",
    ),
    _record(
        "base-3b", "t-09", "im-start-loop",
        "loop-dominated: 0.875 of non-blank lines are tokens",
    ),
]

#: Run 2's records, a synthetic replica of budget-2048's shape: the 14B-like candidate alone.
BUDGET_2048_RECORDS: list[dict[str, object]] = [
    _record("base-14b", "t-01", "hunk-count-mismatch", "hunk 1 body exceeds its declared counts"),
    _record("base-14b", "t-02", "hunk-count-mismatch", "hunk 4 dies early: fence-cut"),
    _record("base-14b", "t-03", "hunk-dies-early", "bare-line"),
    _record("base-14b", "t-06", "well-formed", "all 1 hunks complete"),
]

#: The expected per-candidate analysis of run 1 — the arithmetic the ceiling definition makes.
ARM_A_EXPECTED: dict[str, object] = {
    "records": 9,
    "per_candidate": {
        "base-14b": {
            "cause_counts": {
                "hunk-count-mismatch": 3,
                "hunk-dies-early": 2,
                "well-formed": 1,
            },
            "trigger_counts": {"hunk-count-mismatch": 3, "hunk-dies-early": 2},
            "retry_eligible": 5,
            "inferred_truncation": 1,
            "ceiling": 4,
            "non_trigger_remainder": {
                "im-start-loop": 0,
                "hunk-dies-early/end-of-output": 0,
                "well-formed": 1,
                "no-diff": 0,
                "header-without-hunk": 0,
                "unrecognised-shape": 0,
            },
            "flippable_candidates": 0,
        },
        "base-3b": {
            "cause_counts": {
                "hunk-dies-early": 1,
                "header-without-hunk": 1,
                "im-start-loop": 1,
            },
            "trigger_counts": {},
            "retry_eligible": 0,
            "inferred_truncation": 0,
            "ceiling": 0,
            "non_trigger_remainder": {
                "im-start-loop": 1,
                "hunk-dies-early/end-of-output": 1,
                "well-formed": 0,
                "no-diff": 0,
                "header-without-hunk": 1,
                "unrecognised-shape": 0,
            },
            "flippable_candidates": 1,
        },
    },
    "totals": {
        "records": 9,
        "retry_eligible": 5,
        "inferred_truncation": 1,
        "ceiling": 4,
        "flippable_candidates": 1,
    },
}


def _out(tmp_path: Path) -> Path:
    """A document path under the worktree's gitignored `runs/`, unique per test."""
    return REPO_ROOT / "runs" / "preanalysis-tests" / tmp_path.name / "ceiling.json"


def _run_main(argv: list[str], tmp_path: Path) -> tuple[int, dict[str, object] | None]:
    """Drive the CLI, return (exit code, document), and always clean the document up.

    The document is read before the cleanup runs, so a test can assert on it; a failed
    invocation returns `None` for the document. The cleanup runs even when a test fails
    mid-way, so the gitignored `runs/` test home never accumulates.
    """
    out = Path(argv[argv.index("--out") + 1])
    try:
        exit_code = preanalysis.main(argv)
        document: dict[str, object] | None = None
        if exit_code == 0 and out.is_file():
            document = json.loads(out.read_bytes())
        return exit_code, document
    finally:
        shutil.rmtree(out.parent, ignore_errors=True)


# --------------------------------------------------------------------------------------------
# The measurement: the trigger mapping applied to stored records, per candidate, per run.
# --------------------------------------------------------------------------------------------


def test_the_trigger_mapping_counts_are_correct_per_candidate_and_per_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The ceiling arithmetic over two synthetic runs, whole: counts, per candidate, per run.

    This is the slice's AC1 at the door: the validator's own mapping applied to stored
    autopsy records, counting retry-eligible, inferred truncation, the ceiling, the non-trigger
    remainder per cause, and the header-without-hunk flippable candidates — per candidate, per
    run, and combined.
    """
    arm_a = _write_autopsy(tmp_path, "arm-a", ARM_A_RECORDS)
    budget = _write_autopsy(tmp_path, "budget-2048", BUDGET_2048_RECORDS)
    out = _out(tmp_path)
    argv = [
        "--autopsy", str(arm_a),
        "--autopsy", str(budget),
        "--out", str(out),
    ]

    exit_code, document = _run_main(argv, tmp_path)

    assert exit_code == 0, exit_code
    assert document is not None

    runs = document["runs"]
    assert set(runs) == {"arm-a", "budget-2048"}, runs
    arm_a_block = runs["arm-a"]
    assert arm_a_block["records"] == 9, arm_a_block
    assert arm_a_block["per_candidate"] == ARM_A_EXPECTED["per_candidate"], arm_a_block
    assert arm_a_block["totals"] == ARM_A_EXPECTED["totals"], arm_a_block

    budget_block = runs["budget-2048"]
    assert budget_block["records"] == 4, budget_block
    assert budget_block["per_candidate"]["base-14b"]["retry_eligible"] == 3, budget_block
    assert budget_block["per_candidate"]["base-14b"]["inferred_truncation"] == 0, budget_block
    assert budget_block["per_candidate"]["base-14b"]["ceiling"] == 3, budget_block
    assert budget_block["totals"] == {
        "records": 4,
        "retry_eligible": 3,
        "inferred_truncation": 0,
        "ceiling": 3,
        "flippable_candidates": 0,
    }, budget_block

    combined = document["combined"]
    assert combined["totals"] == {
        "records": 13,
        "retry_eligible": 8,
        "inferred_truncation": 1,
        "ceiling": 7,
        "flippable_candidates": 1,
    }, combined
    assert combined["per_candidate"]["base-14b"]["ceiling"] == 7, combined
    assert combined["per_candidate"]["base-3b"]["ceiling"] == 0, combined

    captured = capsys.readouterr()
    assert "arm-a base-14b: retry-eligible=5, inferred-truncation=1, ceiling=4" in captured.out
    assert "arm-a base-3b: retry-eligible=0, inferred-truncation=0, ceiling=0" in captured.out
    assert (
        "budget-2048 base-14b: retry-eligible=3, inferred-truncation=0, ceiling=3"
        in captured.out
    )
    assert "combined: retry-eligible=8, inferred-truncation=1, ceiling=7" in captured.out
    assert "wrote " in captured.out and str(out) in captured.out, captured.out


def test_a_near_zero_ceiling_is_distinguishable_from_a_real_one(tmp_path: Path) -> None:
    """A run no retry could help must read as ceiling 0, never as a quiet small number.

    The halt condition (PRD R5) is a ceiling near zero; the near-zero shape — a loop-dominated
    candidate, or a run whose only parse refusals are truncation-inferred — must be
    distinguishable in the document from a run with real retry-eligible records. The 7B-like
    candidate in the synthetic corpus above is exactly that shape: 52 stored rollouts of which
    none is retry-eligible (`dig-transcripts.md` § 2 shape 1).
    """
    near_zero = _write_autopsy(
        tmp_path,
        "near-zero",
        [
            _record("base-7b", "t-10", "im-start-loop", "loop-dominated: 0.9 of non-blank lines"),
            _record("base-7b", "t-11", "well-formed", "all 1 hunks complete"),
            _record("base-7b", "t-12", "no-diff", "the output is prose"),
        ],
    )
    real = _write_autopsy(tmp_path, "real", ARM_A_RECORDS)
    out = _out(tmp_path)

    exit_code, document = _run_main(
        ["--autopsy", str(near_zero), "--autopsy", str(real), "--out", str(out)],
        tmp_path,
    )

    assert exit_code == 0, exit_code
    assert document is not None
    assert document["runs"]["near-zero"]["totals"]["retry_eligible"] == 0, document
    assert document["runs"]["near-zero"]["totals"]["inferred_truncation"] == 0, document
    assert document["runs"]["near-zero"]["totals"]["ceiling"] == 0, document
    assert (
        document["runs"]["near-zero"]["per_candidate"]["base-7b"]["trigger_counts"]
        == {}
    ), document
    assert document["runs"]["real"]["totals"]["ceiling"] == 4, document


def test_header_without_hunk_is_counted_as_a_named_flippable_candidate(tmp_path: Path) -> None:
    """The shape the arm may enable is counted by name, not folded into a generic remainder.

    Whether `header-without-hunk` becomes a trigger is the measured arm's open question
    (`spec.md` D-arm1 open question; the mapping's one parameter exists for exactly that). The
    pre-analysis reports it as a named count — per candidate, per run, and in the run's total —
    so the decision the arm makes has a number behind it.
    """
    arm_a = _write_autopsy(tmp_path, "arm-a", ARM_A_RECORDS)
    out = _out(tmp_path)

    exit_code, document = _run_main(["--autopsy", str(arm_a), "--out", str(out)], tmp_path)

    assert exit_code == 0, exit_code
    assert document is not None
    three_b = document["runs"]["arm-a"]["per_candidate"]["base-3b"]
    assert three_b["flippable_candidates"] == 1, three_b
    assert three_b["non_trigger_remainder"]["header-without-hunk"] == 1, three_b
    assert document["runs"]["arm-a"]["totals"]["flippable_candidates"] == 1, document
    assert (
        document["runs"]["arm-a"]["per_candidate"]["base-14b"]["flippable_candidates"]
        == 0
    ), document


def test_the_dev_subset_candidates_are_the_retry_eligible_intersection_across_runs(
    tmp_path: Path,
) -> None:
    """The ids the runbook may pick from: retry-eligible in every stored run (spec D-arm2).

    A task the arm excludes via `--dev-subset` is one both stored runs would have retried —
    the tasks whose prompts the retry template was tuned against. The intersection is computed
    from the documents, deterministically, and an empty intersection is a named empty list,
    not a missing field.
    """
    arm_a = _write_autopsy(tmp_path, "arm-a", ARM_A_RECORDS)
    budget = _write_autopsy(tmp_path, "budget-2048", BUDGET_2048_RECORDS)
    out = _out(tmp_path)

    exit_code, document = _run_main(
        ["--autopsy", str(arm_a), "--autopsy", str(budget), "--out", str(out)],
        tmp_path,
    )

    assert exit_code == 0, exit_code
    assert document is not None
    assert document["dev_subset_candidates"] == ["t-01", "t-02", "t-03"], document


def test_an_empty_retry_eligible_intersection_is_a_named_empty_list(tmp_path: Path) -> None:
    """No task retried by both runs means an empty dev-subset candidate list, spelled as such."""
    first = _write_autopsy(
        tmp_path,
        "first",
        [_record("base-14b", "t-20", "hunk-count-mismatch", "hunk 1 body exceeds its counts")],
    )
    second = _write_autopsy(
        tmp_path,
        "second",
        [_record("base-14b", "t-21", "hunk-count-mismatch", "hunk 1 body exceeds its counts")],
    )
    out = _out(tmp_path)

    exit_code, document = _run_main(
        ["--autopsy", str(first), "--autopsy", str(second), "--out", str(out)],
        tmp_path,
    )

    assert exit_code == 0, exit_code
    assert document is not None
    assert document["dev_subset_candidates"] == [], document


# --------------------------------------------------------------------------------------------
# The locality refusal: before anything is read, and the path and the rule are named.
# --------------------------------------------------------------------------------------------


def test_an_out_git_would_commit_is_refused_before_anything_is_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--out` outside the documented roots is refused first, with the missing inputs untouched.

    The ceiling document is the analysis of stored completions — the user's own private donor
    code — so a path git would commit is a usage error, named, with nothing read and nothing
    written. The autopsy inputs deliberately do not exist: if the CLI had looked at them first,
    this invocation would fail with a different error and the locality promise would be
    unenforced.
    """
    out = tmp_path / "ceiling.json"

    exit_code = preanalysis.main(
        ["--autopsy", str(tmp_path / "missing.json"), "--out", str(out)]
    )

    assert exit_code == 2, exit_code
    message = capsys.readouterr().err
    assert str(out) in message and "runs/" in message, (
        f"WHY THIS IS A FAILURE: the refusal names neither the path nor the root rule. Got "
        f"{message!r}. An operator cannot fix a path they are not shown"
    )
    assert not out.exists(), (
        "WHY THIS IS A FAILURE: the refusal arrived after the document was written. The check "
        "costs nothing and must happen before anything is loaded, let alone published"
    )


def test_an_out_under_reports_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`reports/` is where the arm's published report goes; the ceiling never lands there.

    `reports/local/` is a documented gitignored root, but `reports/format-hardening/` is
    committed — the one-home guard's own distinction (`CLAUDE.md` docs structure). A ceiling
    document under it would be a private measurement wearing a published shape.
    """
    out = REPO_ROOT / "reports" / "format-hardening" / "ceiling.json"

    exit_code = preanalysis.main(
        ["--autopsy", str(tmp_path / "missing.json"), "--out", str(out)]
    )

    assert exit_code == 2, exit_code
    message = capsys.readouterr().err
    assert str(out) in message, message


def test_refuse_published_out_matches_the_autopsy_door_on_every_documented_root(
    tmp_path: Path,
) -> None:
    """The refusal is the autopsy's own pattern — same roots, same verdicts, by comparison.

    `preanalysis` reuses the autopsy's documented roots by identity (`IGNORED_OUT_ROOTS`) and
    its `resolve` + `is_relative_to` pattern (`autopsy.py:727-745`); a path accepted by one
    door and refused by the other would be a second, drifting opinion of what is private.
    """
    accepted = [REPO_ROOT / root / "any" / "depth" / "ceiling.json" for root in IGNORED_OUT_ROOTS]
    refused = [
        tmp_path / "ceiling.json",
        REPO_ROOT / "reports" / "format-hardening" / "ceiling.json",
    ]

    for path in accepted:
        preanalysis.refuse_published_out(path)
        autopsy_refuse_published_out(path)
    for path in refused:
        with pytest.raises(preanalysis.OutNotPrivate):
            preanalysis.refuse_published_out(path)
        with pytest.raises(AutopsyOutNotPrivate):
            autopsy_refuse_published_out(path)


# --------------------------------------------------------------------------------------------
# The input contracts: a missing document, a wrong schema, an unknown cause — each exit 2, named.
# --------------------------------------------------------------------------------------------


def test_a_missing_autopsy_document_exits_2_with_the_path_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A ceiling computed over documents that are not there would measure a run nobody made."""
    missing = tmp_path / "no-such-run.json"

    exit_code = preanalysis.main(
        ["--autopsy", str(missing), "--out", str(_out(tmp_path))]
    )

    assert exit_code == 2, exit_code
    message = capsys.readouterr().err
    assert str(missing) in message and "not a file" in message, message


def test_a_wrong_autopsy_schema_is_refused_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A document that is not `whetstone-autopsy/1` is not the run's own autopsy output."""
    path = tmp_path / "not-an-autopsy.json"
    path.write_text(
        json.dumps({"schema": "whetstone-autopsy/9", "records": []}, sort_keys=True),
        encoding="utf-8",
    )

    exit_code = preanalysis.main(["--autopsy", str(path), "--out", str(_out(tmp_path))])

    assert exit_code == 2, exit_code
    message = capsys.readouterr().err
    assert "whetstone-autopsy/1" in message, message


def test_an_unknown_cause_string_is_an_error_naming_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A cause the taxonomy has no member for must be named, never mapped to a neighbour.

    The alternative is an unknown cause drifting into whichever bucket happens to match — the
    invented-taxonomy failure the whole slice exists to refuse (`prd.md` § 8).
    """
    path = _write_autopsy(
        tmp_path,
        "arm-a",
        [_record("base-14b", "t-01", "not-a-cause", "some detail")],
    )

    exit_code = preanalysis.main(["--autopsy", str(path), "--out", str(_out(tmp_path))])

    assert exit_code == 2, exit_code
    message = capsys.readouterr().err
    assert "not-a-cause" in message, message


def test_duplicate_run_stems_are_refused_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two documents with the same path stem would merge two runs under one key.

    The document keys each run by its autopsy document's path stem — deterministic for the
    stored corpus (`arm-a`, `budget-2048`) — and a stem collision would silently fuse two
    runs' numbers, so it is refused by name instead.
    """
    first = _write_autopsy(tmp_path, "arm-a", ARM_A_RECORDS)
    second_dir = tmp_path / "elsewhere"
    second_dir.mkdir()
    second = second_dir / "arm-a.json"
    second.write_text(first.read_text(encoding="utf-8"), encoding="utf-8")

    exit_code = preanalysis.main(
        ["--autopsy", str(first), "--autopsy", str(second), "--out", str(_out(tmp_path))]
    )

    assert exit_code == 2, exit_code
    message = capsys.readouterr().err
    assert "arm-a" in message and "twice" in message, message


# --------------------------------------------------------------------------------------------
# The document: schema, determinism, and the pre-registered ceiling definition it carries.
# --------------------------------------------------------------------------------------------


def test_the_document_carries_its_schema_and_is_byte_identical_across_invocations(
    tmp_path: Path,
) -> None:
    """The same inputs must write byte-identical documents — a ceiling that moved between reads
    of the same runs would be evidence nobody can re-derive (spec AC1's determinism).
    """
    arm_a = _write_autopsy(tmp_path, "arm-a", ARM_A_RECORDS)
    budget = _write_autopsy(tmp_path, "budget-2048", BUDGET_2048_RECORDS)
    out = _out(tmp_path)
    argv = [
        "--autopsy", str(arm_a),
        "--autopsy", str(budget),
        "--out", str(out),
    ]
    try:
        first = preanalysis.main(argv)
        first_bytes = out.read_bytes()
        second = preanalysis.main(argv)
        second_bytes = out.read_bytes()
    finally:
        shutil.rmtree(out.parent, ignore_errors=True)

    assert first == 0 and second == 0
    assert first_bytes == second_bytes, (
        "WHY THIS IS A FAILURE: two invocations over the same inputs wrote different bytes. A "
        "ceiling that changes between reads of the same runs is evidence nobody can re-derive"
    )

    document = json.loads(first_bytes)
    assert document["schema"] == "whetstone-preanalysis/1", document
    assert document["autopsy_documents"] == [str(arm_a), str(budget)], document
    assert document["ceiling_definition"] == preanalysis.CEILING_DEFINITION, document
    assert "retry-eligible" in preanalysis.CEILING_DEFINITION, preanalysis.CEILING_DEFINITION
    assert "inferred truncation" in preanalysis.CEILING_DEFINITION, preanalysis.CEILING_DEFINITION
    assert "runs" in document and "combined" in document and "dev_subset_candidates" in document


# --------------------------------------------------------------------------------------------
# The identity discipline: the mapping is diffcheck's own, and the delegation cannot fork it.
# --------------------------------------------------------------------------------------------


def test_the_preanalysis_uses_diffcheck_s_own_trigger_mapping() -> None:
    """`trigger_of_cause` is diffcheck's own function, imported, never reimplemented.

    The pre-analysis reads stored documents, which carry `cause`/`detail` strings rather than
    `AutopsyResult` objects, so it must call the verdict split into its two fields — and the
    split must be the validator's own. A second implementation would start as a faithful copy
    and end as a second opinion on the same margin the autopsy already settled
    (`finding.md:69-71`).
    """
    assert preanalysis.trigger_of_cause is diffcheck.trigger_of_cause, (
        "WHY THIS IS A FAILURE: the pre-analysis does not use diffcheck.trigger_of_cause. The "
        "ceiling would then be computed by a mapping that is not the one the arm retries under"
    )


#: The detail strings that decide the death: the three first-hunk deaths, the mismatch detail
#: carrying each death kind, and the overrun detail. The cross-product pins the delegation for
#: every cause, so a future fourth death cannot fork the two spellings of the mapping.
_DETAILS = (
    DeathKind.BARE_LINE.value,
    DeathKind.FENCE_CUT.value,
    DeathKind.END_OF_OUTPUT.value,
    "hunk 1 body exceeds its declared counts",
    "hunk 2 dies early: bare-line",
    "hunk 3 dies early: end-of-output",
)


def test_trigger_of_delegates_to_trigger_of_cause_over_the_whole_cross_product() -> None:
    """`trigger_of(AutopsyResult(...))` and `trigger_of_cause(...)` are the same decision.

    The refactor that split the mapping must not have moved the decision: for every cause and
    every observed detail, the record-shaped call and the field-shaped call answer the same
    trigger. If they ever diverge, an online verdict and the offline pre-analysis would
    disagree about the same record.
    """
    for cause in FineCause:
        for detail in _DETAILS:
            result = AutopsyResult(cause, detail, frozenset())
            assert trigger_of(result) is trigger_of_cause(cause, detail), (
                f"WHY THIS IS A FAILURE: trigger_of({result!r}) answered {trigger_of(result)!r} "
                f"while trigger_of_cause({cause!r}, {detail!r}) answered "
                f"{trigger_of_cause(cause, detail)!r}. The delegation forked the mapping, so "
                "the online verdict and the offline pre-analysis can disagree about the same "
                "record without any test noticing"
            )


def test_header_without_hunk_stays_a_non_trigger_in_the_pre_analysis() -> None:
    """The arm has not run; the pre-analysis measures the shape as a candidate, not a retry.

    `header_without_hunk` is the mapping's one parameterised member — a trigger only when the
    measured arm flips it, on this pre-analysis's evidence (spec D-arm1 open question). Until
    then the pre-analysis counts it as a flippable candidate and never as retry-eligible.
    """
    for detail in ("a diff header was found but no hunk followed", "another no-hunk reason"):
        assert trigger_of_cause(FineCause.HEADER_WITHOUT_HUNK, detail) is None
        assert (
            trigger_of_cause(
                FineCause.HEADER_WITHOUT_HUNK, detail, header_without_hunk_is_trigger=True
            )
            is Trigger.HEADER_WITHOUT_HUNK
        )


# --------------------------------------------------------------------------------------------
# The offline guard: the pre-analysis path imports no inference library, and no `run.py`.
# --------------------------------------------------------------------------------------------

#: Import roots that would mean a model was consulted on the pre-analysis path — the same set
#: the validator's own guard forbids (`test_diffcheck.py`): the driver `run.py` included, since
#: the ceiling must be computable without the generation machinery existing.
FORBIDDEN_IMPORT_ROOTS = frozenset({"mlx", "mlx_lm", "torch", "transformers", "run"})

#: The paths the no-inference walk covers: the module and the test that proves it honest.
PREANALYSIS_PATHS = (
    "src/whetstone/bakeoff/preanalysis.py",
    "tests/bakeoff/test_preanalysis.py",
)


def _imported_roots(source: bytes) -> set[str]:
    """The top-level package of every import in `source`, function-local ones included.

    `ast.walk` rather than a top-of-file read: an import moved inside a function would
    otherwise be invisible — which is exactly where a "just this once" model call would go.
    Relative imports are invisible too, by `node.level == 0`, and this path is first-party
    code that imports by absolute name.
    """
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source, filename="<source>")):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_the_walk_reports_an_import_it_is_given() -> None:
    """Anti-vacuity control: the walk must actually observe imports (`CONTRIBUTING.md:60`)."""
    assert "json" in _imported_roots(b"import json\n"), (
        "the AST walk did not see the stdlib import it was handed, so the no-inference "
        "assertions below would pass by seeing nothing at all."
    )


def test_a_planted_inference_import_is_seen_and_flagged() -> None:
    """The guard's predicate, watched failing: a planted inference import must be flagged."""
    roots = _imported_roots(b"import json\n\nfrom mlx_lm import load\n")
    assert roots & FORBIDDEN_IMPORT_ROOTS == {"mlx_lm"}, roots


@pytest.mark.parametrize("relative", PREANALYSIS_PATHS)
def test_the_preanalysis_path_imports_no_inference_library(relative: str) -> None:
    """The ceiling costs no compute; an import here would spend some.

    The pre-analysis runs before the arm, as the halt decision's evidence — it must be offline
    and instantaneous, or the decision to run a GPU pass would itself need the GPU back. The
    test files are covered too, because a fixture that generated its own completions would make
    the module's own guarantee untestable.

    Files that have not landed yet are skipped, not silently dropped — walked the moment they
    exist.
    """
    path = REPO_ROOT / relative
    if not path.is_file():
        pytest.skip(f"{relative} does not exist yet — walked when it lands")

    roots = _imported_roots(path.read_bytes())

    assert not roots & FORBIDDEN_IMPORT_ROOTS, (
        f"{relative} imports {sorted(roots & FORBIDDEN_IMPORT_ROOTS)}.\n\n"
        "WHY THIS IS A FAILURE: the pre-analysis exists to compute the ceiling before the arm "
        "spends. An inference import here means the measurement needs the model back, and the "
        "halt decision would cost a GPU pass to make."
    )
    assert roots, (
        f"{relative} contains no import at all, so the assertion above holds for a file "
        "nothing was checked against. A guard that walks a set of files must find imports "
        "in them (`CONTRIBUTING.md:60`)."
    )
