"""The before/after comparison: journals and autopsy documents against the pre-analysis.

The measured arm's post-run chain (`docs/planning/format-hardening-measurement/prd.md` D3, D4,
D6) is the deterministic read that turns the stored runs' journals, the stored
`whetstone-autopsy/1` documents, and the `whetstone-preanalysis/1` ceiling document into the
before/after breakdown. This file pins the comparison module that performs it.

Three contracts hold, and each is an honesty property, so each is pinned here.

**The assertion is re-derived, never trusted.** The pre-analysis document's `decisions` rows
record the trigger the mapping fired for every stored record, computed when the ceiling was
measured. The comparison re-derives `diffcheck.trigger_of_cause` and
`preanalysis.is_inferred_truncation` from the autopsy document's own records — by identity,
never reimplemented — and asserts agreement per record, in index order. A contradiction is a
named violation in the document and the CLI exits nonzero; nothing is reconciled. Nonzero
`mapping_violations` in an input autopsy document are surfaced the same way.

**The denominators are disclosed, never fused.** The journal's step count and the autopsy
document's classified-completion count measure different things about the same run; the
document reports both, side by side, and the tallies are counted over the journal's rollouts
alone (`report.tally` by identity — the single place each published figure is defined).

**The ceiling is carried, never recomputed.** The `whetstone-comparison/1` document takes the
ceiling from the pre-analysis document's own `combined.totals.ceiling`; a planted different
value must appear, and the document is byte-deterministic across invocations.

All fixtures are synthetic replicas of the stored artifacts' shapes (`runs/{arm-a,budget-2048}/
journal.jsonl`, `runs/diff-autopsy/{arm-a,budget-2048}.json`,
`runs/format-hardening-preanalysis/ceiling.json`), toy candidates and task ids, tiny — never
donor content (`card.md:68-70`).
"""

from __future__ import annotations

import ast
import json
import shutil
from pathlib import Path

import pytest

from whetstone.bakeoff import comparison, diffcheck, preanalysis
from whetstone.bakeoff.autopsy import IGNORED_OUT_ROOTS, FineCause
from whetstone.bakeoff.control import Control, Origin, Probe
from whetstone.bakeoff.diffcheck import trigger_of_cause
from whetstone.bakeoff.journal import Journal, Step
from whetstone.bakeoff.preanalysis import is_inferred_truncation
from whetstone.bakeoff.scoring import Outcome, Rollout
from whetstone.verify.verdict import Status

#: The repository root, reached from `tests/bakeoff/`: the worktree the CLI's locality rule
#: resolves its roots against, and where the document-under-test is written.
REPO_ROOT = Path(__file__).resolve().parents[2]

# --------------------------------------------------------------------------------------------
# Synthetic fixtures, shaped like the stored artifacts.
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


def _write_autopsy(
    tmp_path: Path,
    stem: str,
    records: list[dict[str, object]],
    *,
    mapping_violations: list[dict[str, object]] | None = None,
) -> Path:
    """A whole `whetstone-autopsy/1` document on disk, replicating the stored shape."""
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
                "mapping_violations": mapping_violations or [],
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


def _step(
    candidate: str,
    task_id: str,
    *,
    outcome: Outcome,
    generation_seconds: float,
    strict: Status | None = None,
    weak: Status | None = None,
    control: Control = Control.INTACT,
) -> Step:
    """One journal step, built through the real `Probe`/`Rollout` constructors.

    Built as objects and appended through the real `Journal.append` codec, so the fixture
    exercises the exact `journal._encode` field shape rather than a replica of it.
    """
    if control is Control.INTACT:
        without_patch: Status | None = Status.FAIL
        with_reference: Status | None = Status.PASS
        detail = ""
    else:
        without_patch, with_reference, detail = Status.PASS, None, "the inert patch did not fail"
    return Step(
        probe=Probe(
            candidate=candidate,
            task_id=task_id,
            control=control,
            without_patch=without_patch,
            with_reference=with_reference,
            origin=Origin.DONOR,
            detail=detail,
            seconds=1.0,
        ),
        rollout=Rollout(
            candidate=candidate,
            task_id=task_id,
            outcome=outcome,
            strict=strict,
            weak=weak,
            verdict_kinds=(),
            executed=None,
            prompt_sha256="0" * 64,
            detail="",
            generation_seconds=generation_seconds,
            strict_seconds=0.0,
            weak_seconds=0.0,
        ),
    )


def _write_journal(tmp_path: Path, stem: str, steps: list[Step]) -> Path:
    """A journal under `tmp/{stem}/journal.jsonl` — the stem is the parent directory's name.

    The stored corpus names its journals `runs/{arm-a,budget-2048}/journal.jsonl`, so a journal
    is keyed by its parent directory's name to match the autopsy document's stem (`arm-a`,
    `budget-2048`); `path.stem` of both stored journals would be `journal` for both.
    """
    path = tmp_path / stem / "journal.jsonl"
    journal = Journal(path)
    for step in steps:
        journal.append(step)
    return path


def _decision_row(record: dict[str, object]) -> dict[str, object]:
    """The pre-analysis document's decisions row for one record — the exact shape
    `preanalysis.main` writes (`preanalysis.py:510-525`), so a fixture can agree or disagree.
    """
    cause = FineCause(record["cause"])
    trigger = trigger_of_cause(cause, str(record["detail"]))
    return {
        "candidate": record["candidate"],
        "task_id": record["task_id"],
        "cause": record["cause"],
        "detail": record["detail"],
        "trigger": None if trigger is None else trigger.value,
        "inferred_truncation": (
            trigger is not None and is_inferred_truncation(str(record["detail"]))
        ),
    }


def _write_preanalysis(
    tmp_path: Path,
    *,
    decisions: dict[str, list[dict[str, object]]],
    ceiling: int = 99,
) -> Path:
    """A whole `whetstone-preanalysis/1` document on disk.

    The ceiling defaults to a planted 99 — never a value any recomputation would land on, so
    a test that asserts the document carries it proves the comparison copied it rather than
    recomputed it.
    """
    records = sum(len(rows) for rows in decisions.values())
    path = tmp_path / "ceiling.json"
    path.write_text(
        json.dumps(
            {
                "schema": "whetstone-preanalysis/1",
                "ceiling_definition": preanalysis.CEILING_DEFINITION,
                "autopsy_documents": [],
                "runs": {},
                "combined": {
                    "per_candidate": {},
                    "totals": {
                        "records": records,
                        "retry_eligible": 0,
                        "inferred_truncation": 0,
                        "ceiling": ceiling,
                        "flippable_candidates": 0,
                    },
                },
                "dev_subset_candidates": [],
                "decisions": decisions,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


#: Run 1's autopsy records: a 14B-like candidate and a 3B-like candidate, covering every shape
#: the trigger mapping decides on — including the inferred-truncation detail inside a
#: `hunk-count-mismatch` and the non-trigger `end-of-output` first-hunk death.
ARM_A_RECORDS: list[dict[str, object]] = [
    _record("base-14b", "t-01", "hunk-count-mismatch", "hunk 1 body exceeds its declared counts"),
    _record("base-14b", "t-02", "hunk-count-mismatch", "hunk 2 dies early: end-of-output"),
    _record("base-14b", "t-03", "hunk-dies-early", "bare-line"),
    _record("base-14b", "t-04", "hunk-dies-early", "end-of-output"),
    _record("base-14b", "t-05", "well-formed", "all 1 hunks complete"),
    _record(
        "base-3b", "t-06", "header-without-hunk",
        "a diff header was found but no hunk followed",
    ),
    _record(
        "base-3b", "t-07", "im-start-loop",
        "loop-dominated: 0.875 of non-blank lines are tokens",
    ),
    _record("base-3b", "t-08", "hunk-count-mismatch", "hunk 3 dies early: fence-cut"),
    _record("base-3b", "t-09", "hunk-dies-early", "fence-cut"),
]

#: Run 2's autopsy records: the 14B-like candidate alone — the budget-2048 shape.
BUDGET_2048_RECORDS: list[dict[str, object]] = [
    _record("base-14b", "t-01", "hunk-count-mismatch", "hunk 1 body exceeds its declared counts"),
    _record("base-14b", "t-02", "hunk-dies-early", "bare-line"),
    _record("base-14b", "t-03", "well-formed", "all 1 hunks complete"),
    _record("base-14b", "t-04", "hunk-count-mismatch", "hunk 4 dies early: fence-cut"),
]

#: Run 1's journal: 6 steps for 9 autopsy records — the D6 denominators differ on purpose.
ARM_A_STEPS: list[Step] = [
    _step("base-14b", "t-01", outcome=Outcome.SOLVED, generation_seconds=1.25,
          strict=Status.PASS, weak=Status.PASS),
    _step("base-14b", "t-02", outcome=Outcome.NOT_APPLIED, generation_seconds=2.5,
          strict=Status.FAIL, weak=Status.FAIL),
    _step("base-14b", "t-03", outcome=Outcome.NOT_APPLIED, generation_seconds=3.75,
          strict=Status.FAIL, weak=Status.PASS),
    _step("base-14b", "t-05", outcome=Outcome.NO_DIFF, generation_seconds=0.5),
    _step("base-3b", "t-06", outcome=Outcome.OUT_OF_SCOPE, generation_seconds=4.0,
          strict=Status.FAIL, weak=Status.FAIL),
    _step("base-3b", "t-07", outcome=Outcome.UNVERIFIED, generation_seconds=0.25,
          strict=Status.UNVERIFIED, weak=Status.UNVERIFIED),
]

#: Run 2's journal: 3 steps for 4 autopsy records — the denominators differ again.
BUDGET_2048_STEPS: list[Step] = [
    _step("base-14b", "t-01", outcome=Outcome.NOT_SOLVED, generation_seconds=1.0,
          strict=Status.FAIL, weak=Status.FAIL),
    _step("base-14b", "t-02", outcome=Outcome.NOT_APPLIED, generation_seconds=2.0,
          strict=Status.FAIL, weak=Status.FAIL),
    _step("base-14b", "t-03", outcome=Outcome.SOLVED, generation_seconds=3.0,
          strict=Status.PASS, weak=Status.PASS),
]


def _out(tmp_path: Path) -> Path:
    """A document path under the worktree's gitignored `runs/`, unique per test."""
    return REPO_ROOT / "runs" / "comparison-tests" / tmp_path.name / "comparison.json"


def _fixture(tmp_path: Path) -> dict[str, object]:
    """The two synthetic runs, whole: autopsies, journals, and the pre-analysis document."""
    arm_a_autopsy = _write_autopsy(tmp_path, "arm-a", ARM_A_RECORDS)
    budget_autopsy = _write_autopsy(tmp_path, "budget-2048", BUDGET_2048_RECORDS)
    arm_a_journal = _write_journal(tmp_path, "arm-a", ARM_A_STEPS)
    budget_journal = _write_journal(tmp_path, "budget-2048", BUDGET_2048_STEPS)
    preanalysis_document = _write_preanalysis(
        tmp_path,
        decisions={
            "arm-a": [_decision_row(record) for record in ARM_A_RECORDS],
            "budget-2048": [_decision_row(record) for record in BUDGET_2048_RECORDS],
        },
        ceiling=99,
    )
    return {
        "arm_a_autopsy": arm_a_autopsy,
        "budget_autopsy": budget_autopsy,
        "arm_a_journal": arm_a_journal,
        "budget_journal": budget_journal,
        "preanalysis": preanalysis_document,
    }


def _argv(fixture: dict[str, object], tmp_path: Path) -> list[str]:
    """The breakdown-mode invocation over the fixture."""
    return [
        "--journal", str(fixture["arm_a_journal"]),
        "--journal", str(fixture["budget_journal"]),
        "--autopsy", str(fixture["arm_a_autopsy"]),
        "--autopsy", str(fixture["budget_autopsy"]),
        "--preanalysis", str(fixture["preanalysis"]),
        "--out", str(_out(tmp_path)),
    ]


def _run_main(argv: list[str], tmp_path: Path) -> tuple[int, dict[str, object] | None]:
    """Drive the CLI, return (exit code, document), and always clean the document up.

    The document is read before the cleanup runs, so a test can assert on it; a failed
    invocation returns `None` for the document. The cleanup runs even when a test fails
    mid-way, so the gitignored `runs/` test home never accumulates.
    """
    out = Path(argv[argv.index("--out") + 1])
    try:
        exit_code = comparison.main(argv)
        document: dict[str, object] | None = None
        if exit_code in (0, 1) and out.is_file():
            document = json.loads(out.read_bytes())
        return exit_code, document
    finally:
        shutil.rmtree(out.parent, ignore_errors=True)


# --------------------------------------------------------------------------------------------
# The breakdown: per-run, per-candidate cause counts, tallies, denominators, generation seconds.
# --------------------------------------------------------------------------------------------


def test_per_run_per_candidate_blocks_carry_cause_counts_tallies_and_both_denominators(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole breakdown over two synthetic runs: counts, tallies, side-by-side denominators.

    The journal's step count and the autopsy's classified-completion count are different
    measurements of the same run (D6) and must appear side by side, never fused: 6 vs 9 for
    arm-a, 3 vs 4 for budget-2048.
    """
    exit_code, document = _run_main(_argv(_fixture(tmp_path), tmp_path), tmp_path)

    assert exit_code == 0, exit_code
    assert document is not None

    runs = document["runs"]
    assert set(runs) == {"arm-a", "budget-2048"}, runs
    arm_a = runs["arm-a"]
    assert arm_a["control_proven"] is True, arm_a
    assert arm_a["rollout_records"] == 6 and arm_a["autopsy_records"] == 9, arm_a

    fourteen_b = arm_a["per_candidate"]["base-14b"]
    assert fourteen_b["cause_counts"] == {
        "hunk-count-mismatch": 2,
        "hunk-dies-early": 2,
        "well-formed": 1,
    }, fourteen_b
    assert fourteen_b["tally"] == {
        "candidate": "base-14b",
        "denominator": 4,
        "solved": 1,
        "covered": 4,
        "unverified": 0,
        "failed": 3,
        "weaker_wins": 1,
        "no_diff": 1,
        "not_applied": 2,
        "out_of_scope": 0,
        "not_solved": 0,
    }, fourteen_b
    assert fourteen_b["generation_seconds"] == 8.0, fourteen_b

    three_b = arm_a["per_candidate"]["base-3b"]
    assert three_b["cause_counts"] == {
        "hunk-count-mismatch": 1,
        "hunk-dies-early": 1,
        "header-without-hunk": 1,
        "im-start-loop": 1,
    }, three_b
    assert three_b["tally"]["denominator"] == 2, three_b
    assert three_b["tally"]["unverified"] == 1, three_b
    assert three_b["tally"]["out_of_scope"] == 1, three_b

    budget = runs["budget-2048"]
    assert budget["rollout_records"] == 3 and budget["autopsy_records"] == 4, budget
    assert set(budget["per_candidate"]) == {"base-14b"}, budget
    budget_block = budget["per_candidate"]["base-14b"]
    assert budget_block["cause_counts"] == {
        "hunk-count-mismatch": 2,
        "hunk-dies-early": 1,
        "well-formed": 1,
    }, budget_block
    assert budget_block["tally"] == {
        "candidate": "base-14b",
        "denominator": 3,
        "solved": 1,
        "covered": 3,
        "unverified": 0,
        "failed": 2,
        "weaker_wins": 0,
        "no_diff": 0,
        "not_applied": 1,
        "out_of_scope": 0,
        "not_solved": 1,
    }, budget_block

    captured = capsys.readouterr()
    assert "arm-a" in captured.out and "budget-2048" in captured.out, captured.out
    assert "wrote " in captured.out and str(_out(tmp_path)) in captured.out, captured.out


def test_generation_seconds_are_summed_per_candidate_per_run(tmp_path: Path) -> None:
    """The journal's `generation_seconds` are summed, per candidate, per run."""
    exit_code, document = _run_main(_argv(_fixture(tmp_path), tmp_path), tmp_path)

    assert exit_code == 0, exit_code
    assert document is not None
    runs = document["runs"]
    assert runs["arm-a"]["per_candidate"]["base-14b"]["generation_seconds"] == 8.0, runs
    assert runs["arm-a"]["per_candidate"]["base-3b"]["generation_seconds"] == 4.25, runs
    assert runs["budget-2048"]["per_candidate"]["base-14b"]["generation_seconds"] == 6.0, runs


def test_the_ceiling_is_carried_from_the_preanalysis_document_never_recomputed(
    tmp_path: Path,
) -> None:
    """`ceiling` is the pre-analysis document's own number — a planted value must appear.

    The fixture's pre-analysis document plants a ceiling of 99, which no recomputation from
    the fixture's records could land on; the comparison must copy it verbatim.
    """
    fixture = _fixture(tmp_path)
    exit_code, document = _run_main(_argv(fixture, tmp_path), tmp_path)

    assert exit_code == 0, exit_code
    assert document is not None
    assert document["ceiling"] == 99, document
    assert document["preanalysis_document"] == str(fixture["preanalysis"]), document


def test_before_after_renders_each_runs_cause_counts_with_the_delta_against_the_named_before(
    tmp_path: Path,
) -> None:
    """The before/after: per candidate, per run, side by side — never pooled (autopsy.py:676-677).

    The named `before` run is `arm-a`; each run's delta is computed against it, per cause, and
    absent candidates are absent (budget-2048's per-candidate set keeps only base-14b).
    """
    exit_code, document = _run_main(_argv(_fixture(tmp_path), tmp_path), tmp_path)

    assert exit_code == 0, exit_code
    assert document is not None

    before_after = document["before_after"]
    assert before_after["before"] == "arm-a", before_after
    per_candidate = before_after["per_candidate"]

    fourteen_b = per_candidate["base-14b"]
    assert fourteen_b["runs"]["arm-a"] == {
        "hunk-count-mismatch": 2,
        "hunk-dies-early": 2,
        "well-formed": 1,
    }, fourteen_b
    assert fourteen_b["runs"]["budget-2048"] == {
        "hunk-count-mismatch": 2,
        "hunk-dies-early": 1,
        "well-formed": 1,
    }, fourteen_b
    assert fourteen_b["delta_vs_before"]["arm-a"] == {
        "hunk-count-mismatch": 0,
        "hunk-dies-early": 0,
        "well-formed": 0,
    }, fourteen_b
    assert fourteen_b["delta_vs_before"]["budget-2048"] == {
        "hunk-count-mismatch": 0,
        "hunk-dies-early": -1,
        "well-formed": 0,
    }, fourteen_b

    three_b = per_candidate["base-3b"]
    assert set(three_b["runs"]) == {"arm-a"}, three_b
    assert set(per_candidate) == {"base-14b", "base-3b"}, per_candidate


def test_the_denominator_disclosure_is_written(tmp_path: Path) -> None:
    """The D6 disclosure sentence is part of the document, naming both denominators."""
    exit_code, document = _run_main(_argv(_fixture(tmp_path), tmp_path), tmp_path)

    assert exit_code == 0, exit_code
    assert document is not None
    sentence = document["disclosures"]["denominators"]
    assert isinstance(sentence, str)
    assert "rollout_records" in sentence and "autopsy_records" in sentence, sentence


# --------------------------------------------------------------------------------------------
# The assertion: a planted disagreement is a named violation and a nonzero exit.
# --------------------------------------------------------------------------------------------


def test_a_planted_trigger_mismatch_is_a_named_violation_with_a_nonzero_exit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """D4: the comparison re-derives the mapping and asserts agreement — a contradiction is
    reported, never smoothed, and the run exits nonzero with the document still written.

    The trigger of record 0 is planted as `hunk-dies-early` (re-derivation says
    `hunk-count-mismatch`), and record 2's `inferred_truncation` is flipped to `True`
    (re-derivation says `False`). Both are mismatches, both must be named.
    """
    fixture = _fixture(tmp_path)
    decisions = {
        "arm-a": [_decision_row(record) for record in ARM_A_RECORDS],
        "budget-2048": [_decision_row(record) for record in BUDGET_2048_RECORDS],
    }
    decisions["arm-a"][0]["trigger"] = "hunk-dies-early"
    decisions["arm-a"][2]["inferred_truncation"] = True
    fixture["preanalysis"] = _write_preanalysis(tmp_path, decisions=decisions, ceiling=99)

    exit_code, document = _run_main(_argv(fixture, tmp_path), tmp_path)

    assert exit_code == 1, exit_code
    assert document is not None
    violations = document["violations"]
    assert len(violations) == 2, violations

    first = violations[0]
    assert first["kind"] == "trigger-mismatch", first
    assert first["stem"] == "arm-a" and first["index"] == 0, first
    assert first["candidate"] == "base-14b" and first["task_id"] == "t-01", first
    assert first["expected_trigger"] == "hunk-count-mismatch", first
    assert first["actual_trigger"] == "hunk-dies-early", first
    assert first["expected_inferred_truncation"] is False, first

    second = violations[1]
    assert second["stem"] == "arm-a" and second["index"] == 2, second
    assert second["expected_trigger"] == "hunk-dies-early", second
    assert second["expected_inferred_truncation"] is False, second
    assert second["actual_inferred_truncation"] is True, second

    message = capsys.readouterr().err
    assert "arm-a" in message, message


def test_autopsy_mapping_violations_are_surfaced_with_their_stem(
    tmp_path: Path,
) -> None:
    """An input autopsy document that already carries mapping violations surfaces them.

    The autopsy's own fine→coarse assertion contract (`autopsy.py:644-667`) says a
    contradiction is reported, never reconciled; the comparison carries that forward by name.
    """
    fixture = _fixture(tmp_path)
    fixture["arm_a_autopsy"] = _write_autopsy(
        tmp_path,
        "arm-a",
        ARM_A_RECORDS,
        mapping_violations=[
            {
                "candidate": "base-14b",
                "task_id": "t-01",
                "fine_cause": "hunk-count-mismatch",
                "recorded_cause": "NOT_APPLIED",
            }
        ],
    )

    exit_code, document = _run_main(_argv(fixture, tmp_path), tmp_path)

    assert exit_code == 1, exit_code
    assert document is not None
    violations = document["violations"]
    assert len(violations) == 1, violations
    surfaced = violations[0]
    assert surfaced["kind"] == "autopsy-mapping-violation", surfaced
    assert surfaced["stem"] == "arm-a", surfaced
    assert surfaced["candidate"] == "base-14b" and surfaced["task_id"] == "t-01", surfaced
    assert surfaced["fine_cause"] == "hunk-count-mismatch", surfaced
    assert surfaced["recorded_cause"] == "NOT_APPLIED", surfaced


def test_a_decisions_list_shorter_than_the_autopsy_records_is_refused(tmp_path: Path) -> None:
    """Decisions and records must cover the same record set; a length disagreement is refused.

    The pre-analysis CLI writes exactly one decisions row per autopsy record in order; a
    different length means the two documents were not written over the same bytes, and nothing
    between them may be compared.
    """
    fixture = _fixture(tmp_path)
    decisions = {
        "arm-a": [_decision_row(record) for record in ARM_A_RECORDS[:-1]],
        "budget-2048": [_decision_row(record) for record in BUDGET_2048_RECORDS],
    }
    fixture["preanalysis"] = _write_preanalysis(tmp_path, decisions=decisions, ceiling=99)

    exit_code = comparison.main(_argv(fixture, tmp_path))

    assert exit_code == 2, exit_code


# --------------------------------------------------------------------------------------------
# The refusals: missing inputs, stem discipline, control discipline, locality.
# --------------------------------------------------------------------------------------------


def test_a_missing_journal_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """An arm that has not run must not read as zero rollouts — a missing journal is refused."""
    fixture = _fixture(tmp_path)
    missing = tmp_path / "never-ran" / "journal.jsonl"

    exit_code = comparison.main(
        [
            "--journal", str(missing),
            "--journal", str(fixture["budget_journal"]),
            "--autopsy", str(fixture["arm_a_autopsy"]),
            "--autopsy", str(fixture["budget_autopsy"]),
            "--preanalysis", str(fixture["preanalysis"]),
            "--out", str(_out(tmp_path)),
        ]
    )

    assert exit_code == 2, exit_code
    message = capsys.readouterr().err
    assert str(missing) in message and "not a file" in message, message


def test_a_missing_autopsy_document_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing autopsy document is refused the same way a missing journal is."""
    fixture = _fixture(tmp_path)
    missing = tmp_path / "no-such-run.json"

    exit_code = comparison.main(
        [
            "--journal", str(fixture["arm_a_journal"]),
            "--journal", str(fixture["budget_journal"]),
            "--autopsy", str(fixture["arm_a_autopsy"]),
            "--autopsy", str(missing),
            "--preanalysis", str(fixture["preanalysis"]),
            "--out", str(_out(tmp_path)),
        ]
    )

    assert exit_code == 2, exit_code
    message = capsys.readouterr().err
    assert str(missing) in message and "not a file" in message, message


def test_a_stem_mismatch_between_journal_and_autopsy_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Every journal stem must have an autopsy and vice versa; a missing half is exit 2.

    Checked in both directions: a journal without an autopsy, then an autopsy without a journal.
    """
    fixture = _fixture(tmp_path)

    journal_without_autopsy = [
        "--journal", str(fixture["arm_a_journal"]),
        "--journal", str(fixture["budget_journal"]),
        "--autopsy", str(fixture["arm_a_autopsy"]),
        "--preanalysis", str(fixture["preanalysis"]),
        "--out", str(_out(tmp_path)),
    ]
    exit_code = comparison.main(journal_without_autopsy)
    assert exit_code == 2, exit_code
    message = capsys.readouterr().err
    assert "budget-2048" in message, message

    autopsy_without_journal = [
        "--journal", str(fixture["arm_a_journal"]),
        "--autopsy", str(fixture["arm_a_autopsy"]),
        "--autopsy", str(fixture["budget_autopsy"]),
        "--preanalysis", str(fixture["preanalysis"]),
        "--out", str(_out(tmp_path)),
    ]
    exit_code = comparison.main(autopsy_without_journal)
    assert exit_code == 2, exit_code
    message = capsys.readouterr().err
    assert "budget-2048" in message, message


def test_duplicate_journal_stems_are_refused_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two journals whose run keys collide would fuse two runs under one key.

    The journal's key is its parent directory's name, so two journals under same-named
    directories in different parents collide and are refused rather than fused.
    """
    fixture = _fixture(tmp_path)
    elsewhere = tmp_path / "elsewhere" / "arm-a"
    duplicate = _write_journal(elsewhere, "arm-a", ARM_A_STEPS)

    exit_code = comparison.main(
        [
            "--journal", str(fixture["arm_a_journal"]),
            "--journal", str(duplicate),
            "--autopsy", str(fixture["arm_a_autopsy"]),
            "--autopsy", str(fixture["budget_autopsy"]),
            "--preanalysis", str(fixture["preanalysis"]),
            "--out", str(_out(tmp_path)),
        ]
    )

    assert exit_code == 2, exit_code
    message = capsys.readouterr().err
    assert "arm-a" in message and "twice" in message, message


def test_duplicate_autopsy_stems_are_refused_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two autopsy documents with the same path stem would merge two runs under one key."""
    fixture = _fixture(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    duplicate = elsewhere / "arm-a.json"
    duplicate.write_text(
        fixture["arm_a_autopsy"].read_text(encoding="utf-8"), encoding="utf-8"
    )

    exit_code = comparison.main(
        [
            "--journal", str(fixture["arm_a_journal"]),
            "--journal", str(fixture["budget_journal"]),
            "--autopsy", str(fixture["arm_a_autopsy"]),
            "--autopsy", str(duplicate),
            "--preanalysis", str(fixture["preanalysis"]),
            "--out", str(_out(tmp_path)),
        ]
    )

    assert exit_code == 2, exit_code
    message = capsys.readouterr().err
    assert "arm-a" in message and "twice" in message, message


def test_a_run_without_an_intact_probe_is_refused_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A run whose journal never proved the harness yields no counts (control.py:492 discipline).

    budget-2048's steps carry only BROKEN probes; nothing from such a run may become a count,
    and the refusal names the run.
    """
    fixture = _fixture(tmp_path)
    fixture["budget_journal"] = _write_journal(
        tmp_path / "elsewhere",
        "budget-2048",
        [
            _step(
                "base-14b", "t-01", outcome=Outcome.NOT_SOLVED, generation_seconds=1.0,
                strict=Status.FAIL, weak=Status.FAIL, control=Control.BROKEN,
            ),
            _step(
                "base-14b", "t-02", outcome=Outcome.NOT_SOLVED, generation_seconds=2.0,
                strict=Status.FAIL, weak=Status.FAIL, control=Control.BROKEN,
            ),
        ],
    )

    exit_code = comparison.main(_argv(fixture, tmp_path))

    assert exit_code == 2, exit_code
    message = capsys.readouterr().err
    assert "budget-2048" in message and "INTACT" in message, message


def test_an_out_git_would_commit_is_refused_before_anything_is_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--out` outside the documented roots is refused first, with the missing inputs untouched.

    The comparison document is the analysis of stored completions — the user's own private
    donor code — so a path git would commit is a usage error, named, with nothing read and
    nothing written. The autopsy and journal inputs deliberately do not exist: if the CLI had
    looked at them first, this invocation would fail with a different error and the locality
    promise would be unenforced.
    """
    out = tmp_path / "comparison.json"

    exit_code = comparison.main(
        [
            "--journal", str(tmp_path / "missing" / "journal.jsonl"),
            "--autopsy", str(tmp_path / "missing.json"),
            "--preanalysis", str(tmp_path / "missing-ceiling.json"),
            "--out", str(out),
        ]
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
    """`reports/` is where the published report goes; the breakdown never lands there."""
    out = REPO_ROOT / "reports" / "format-hardening" / "comparison.json"

    exit_code = comparison.main(
        [
            "--journal", str(tmp_path / "missing" / "journal.jsonl"),
            "--autopsy", str(tmp_path / "missing.json"),
            "--preanalysis", str(tmp_path / "missing-ceiling.json"),
            "--out", str(out),
        ]
    )

    assert exit_code == 2, exit_code
    message = capsys.readouterr().err
    assert str(out) in message, message


# --------------------------------------------------------------------------------------------
# The input contracts: a wrong pre-analysis schema, missing totals — each exit 2, named.
# --------------------------------------------------------------------------------------------


def test_a_wrong_preanalysis_schema_is_refused_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A document that is not `whetstone-preanalysis/1` is not the ceiling document."""
    fixture = _fixture(tmp_path)
    fixture["preanalysis"].write_text(
        json.dumps({"schema": "whetstone-preanalysis/9", "combined": {}, "decisions": {}}),
        encoding="utf-8",
    )

    exit_code = comparison.main(_argv(fixture, tmp_path))

    assert exit_code == 2, exit_code
    message = capsys.readouterr().err
    assert "whetstone-preanalysis/1" in message, message


def test_a_preanalysis_document_without_totals_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`combined.totals` is where the ceiling lives; a document without it carries no ceiling."""
    fixture = _fixture(tmp_path)
    fixture["preanalysis"].write_text(
        json.dumps(
            {
                "schema": "whetstone-preanalysis/1",
                "combined": {"per_candidate": {}},
                "decisions": {},
            }
        ),
        encoding="utf-8",
    )

    exit_code = comparison.main(_argv(fixture, tmp_path))

    assert exit_code == 2, exit_code
    message = capsys.readouterr().err
    assert "totals" in message, message


def test_a_wrong_autopsy_schema_is_refused_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A document that is not `whetstone-autopsy/1` is not the run's own autopsy output."""
    fixture = _fixture(tmp_path)
    fixture["arm_a_autopsy"].write_text(
        json.dumps({"schema": "whetstone-autopsy/9", "records": []}), encoding="utf-8"
    )

    exit_code = comparison.main(_argv(fixture, tmp_path))

    assert exit_code == 2, exit_code
    message = capsys.readouterr().err
    assert "whetstone-autopsy/1" in message, message


# --------------------------------------------------------------------------------------------
# The document: schema, determinism, and the door used by identity.
# --------------------------------------------------------------------------------------------


def test_the_document_carries_its_schema_and_is_byte_identical_across_invocations(
    tmp_path: Path,
) -> None:
    """The same inputs must write byte-identical documents (spec AC2's determinism)."""
    fixture = _fixture(tmp_path)
    argv = _argv(fixture, tmp_path)
    try:
        first = comparison.main(argv)
        first_bytes = Path(argv[argv.index("--out") + 1]).read_bytes()
        second = comparison.main(argv)
        second_bytes = Path(argv[argv.index("--out") + 1]).read_bytes()
    finally:
        shutil.rmtree(_out(tmp_path).parent, ignore_errors=True)

    assert first == 0 and second == 0
    assert first_bytes == second_bytes, (
        "WHY THIS IS A FAILURE: two invocations over the same inputs wrote different bytes. A "
        "before/after that changes between reads of the same runs is evidence nobody can "
        "re-derive"
    )

    document = json.loads(first_bytes)
    assert document["schema"] == "whetstone-comparison/1", document
    assert set(document) >= {
        "schema",
        "preanalysis_document",
        "ceiling",
        "runs",
        "before_after",
        "assertion",
        "violations",
        "disclosures",
    }, document


def test_refuse_published_out_is_the_preanalysis_door_by_identity() -> None:
    """The locality door is `preanalysis.refuse_published_out` itself — one door, one opinion."""
    assert comparison.refuse_published_out is preanalysis.refuse_published_out, (
        "WHY THIS IS A FAILURE: the comparison does not use preanalysis.refuse_published_out "
        "by identity. A second spelling of the locality rule is a second opinion about what is "
        "private"
    )


def test_refuse_published_out_matches_the_preanalysis_door_on_every_documented_root(
    tmp_path: Path,
) -> None:
    """The door accepts exactly the documented gitignored roots and refuses everything else."""
    accepted = [
        REPO_ROOT / root / "any" / "depth" / "comparison.json" for root in IGNORED_OUT_ROOTS
    ]
    refused = [
        tmp_path / "comparison.json",
        REPO_ROOT / "reports" / "format-hardening" / "comparison.json",
    ]

    for path in accepted:
        comparison.refuse_published_out(path)
    for path in refused:
        with pytest.raises(preanalysis.OutNotPrivate):
            comparison.refuse_published_out(path)


# --------------------------------------------------------------------------------------------
# The markdown render: deterministic, from the document's own numbers, violations included.
# --------------------------------------------------------------------------------------------


def _render_fixture(tmp_path: Path) -> str:
    """The fixture document rendered to markdown — the fixture must build clean first."""
    exit_code, document = _run_main(_argv(_fixture(tmp_path), tmp_path), tmp_path)
    assert exit_code == 0, exit_code
    assert document is not None
    return comparison.render_markdown(document)


def test_render_markdown_is_byte_deterministic(tmp_path: Path) -> None:
    """The same document renders the same string, invocation after invocation.

    The markdown is a pure function of the document: no clock, no environment, no
    iteration order that is not sorted — two invocations over the same inputs must render
    byte-identically, or the before/after changes between reads of the same runs.
    """
    first = _render_fixture(tmp_path)
    second = _render_fixture(tmp_path)

    assert first == second, (
        "WHY THIS IS A FAILURE: the same document rendered to two different strings. A "
        "breakdown that changes between reads of the same runs is evidence nobody can "
        "re-derive"
    )


def test_the_render_heads_with_the_document_name_and_its_gitignored_home(
    tmp_path: Path,
) -> None:
    """The header names the document and states where the breakdown lives (runbook.md:136-138)."""
    render = _render_fixture(tmp_path)

    assert "# Before/after breakdown (whetstone-comparison/1)" in render, render
    assert "runs/format-hardening-preanalysis/comparison.md" in render, render


def test_the_ceiling_and_the_denominators_appear_in_the_render(tmp_path: Path) -> None:
    """The ceiling is rendered from the document and the D6 denominators sit side by side."""
    render = _render_fixture(tmp_path)

    assert (
        "Ceiling (carried from the pre-analysis document, never recomputed): 99" in render
    ), render
    assert "## Denominators" in render, render
    assert "| arm-a | 6 | 9 |" in render, render
    assert "| budget-2048 | 3 | 4 |" in render, render
    assert "rollout_records" in render and "autopsy_records" in render, render


def test_only_observed_causes_become_rows_and_only_carried_candidates_appear(
    tmp_path: Path,
) -> None:
    """Rows are the union of observed causes; absent causes are absent, never zero-filled.

    `im-start-loop` and `header-without-hunk` were observed only for base-3b, so they must
    appear only inside base-3b's table; `no-diff` and `unrecognised-shape` were observed by
    nobody and must not appear anywhere. budget-2048 never carried base-3b, so base-3b's
    table has no budget-2048 column.
    """
    render = _render_fixture(tmp_path)

    fourteen_b = render.split("## Candidate: base-14b")[1].split("## Candidate: base-3b")[0]
    assert "| hunk-count-mismatch | 2 | 0 | 2 | 0 |" in fourteen_b, fourteen_b
    assert "| hunk-dies-early | 2 | 0 | 1 | -1 |" in fourteen_b, fourteen_b
    assert "im-start-loop" not in fourteen_b, fourteen_b
    assert "header-without-hunk" not in fourteen_b, fourteen_b

    three_b = render.split("## Candidate: base-3b")[1].split("## Violations")[0]
    assert "| im-start-loop |" in three_b, three_b
    assert "| header-without-hunk |" in three_b, three_b
    assert "budget-2048" not in three_b, three_b

    assert "| no-diff |" not in render, render
    assert "| unrecognised-shape |" not in render, render


def test_a_planted_violation_is_rendered_never_smoothed(tmp_path: Path) -> None:
    """A violation the document carries is listed verbatim — the render hides nothing."""
    exit_code, document = _run_main(_argv(_fixture(tmp_path), tmp_path), tmp_path)
    assert exit_code == 0, exit_code
    assert document is not None
    document["violations"].append(
        {
            "kind": "trigger-mismatch",
            "stem": "arm-a",
            "index": 0,
            "candidate": "base-14b",
            "task_id": "t-01",
            "expected_trigger": "hunk-count-mismatch",
            "actual_trigger": "hunk-dies-early",
        }
    )

    render = comparison.render_markdown(document)

    assert "## Violations" in render, render
    assert "1 violation(s)" in render, render
    assert "rendered, never smoothed" in render, render
    assert "kind='trigger-mismatch'" in render, render
    assert "actual_trigger='hunk-dies-early'" in render, render


def test_the_cli_writes_the_markdown_beside_the_document(tmp_path: Path) -> None:
    """The CLI writes `comparison.md` beside the document it names, byte-identical to the render."""
    fixture = _fixture(tmp_path)
    argv = _argv(fixture, tmp_path)
    out = _out(tmp_path)
    try:
        exit_code = comparison.main(argv)
        assert exit_code == 0, exit_code
        document = json.loads(out.read_bytes())
        markdown_out = out.with_suffix(".md")
        assert markdown_out.is_file(), markdown_out
        assert markdown_out.read_text(encoding="utf-8") == comparison.render_markdown(document), (
            "WHY THIS IS A FAILURE: the markdown file differs from render_markdown(document). "
            "The bytes on disk must be the render, so what the file says is what the render says"
        )
    finally:
        shutil.rmtree(out.parent, ignore_errors=True)


# --------------------------------------------------------------------------------------------
# The identity discipline: the mapping and the truncation read are the seams' own.
# --------------------------------------------------------------------------------------------


def test_the_comparison_uses_diffcheck_s_own_trigger_mapping() -> None:
    """`trigger_of_cause` is diffcheck's own function, imported, never reimplemented."""
    assert comparison.trigger_of_cause is diffcheck.trigger_of_cause, (
        "WHY THIS IS A FAILURE: the comparison does not use diffcheck.trigger_of_cause. The "
        "assertion would then check the pre-analysis against a second mapping, and the one "
        "that disagreed would be the one nobody looked at"
    )


def test_the_comparison_uses_preanalysis_s_own_truncation_read() -> None:
    """`is_inferred_truncation` is preanalysis's own function, imported, never reimplemented."""
    assert comparison.is_inferred_truncation is preanalysis.is_inferred_truncation, (
        "WHY THIS IS A FAILURE: the comparison reimplemented the truncation read. Two "
        "spellings of 'does this detail name the end-of-output death' would disagree exactly "
        "at the margin the ceiling depends on"
    )


# --------------------------------------------------------------------------------------------
# The offline guard: the comparison path imports no inference library, and no `run.py`.
# --------------------------------------------------------------------------------------------

#: Import roots that would mean a model was consulted on the comparison path — the same set
#: the pre-analysis's own guard forbids (`test_preanalysis.py`): the driver `run.py` included,
#: since the breakdown must be computable without the generation machinery existing.
FORBIDDEN_IMPORT_ROOTS = frozenset({"mlx", "mlx_lm", "torch", "transformers", "run"})

#: The paths the no-inference walk covers: the module and the test that proves it honest.
COMPARISON_PATHS = (
    "src/whetstone/bakeoff/comparison.py",
    "tests/bakeoff/test_comparison.py",
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


@pytest.mark.parametrize("relative", COMPARISON_PATHS)
def test_the_comparison_path_imports_no_inference_library(relative: str) -> None:
    """The breakdown costs no compute; an import here would spend some.

    The comparison runs offline, after the arm, on stored bytes — it must be instantaneous
    and stdlib-only, or the post-run analysis chain would need the GPU back. The test file is
    covered too, because a fixture that generated its own completions would make the module's
    own guarantee untestable.
    """
    path = REPO_ROOT / relative
    if not path.is_file():
        pytest.skip(f"{relative} does not exist yet — walked when it lands")

    roots = _imported_roots(path.read_bytes())

    assert not roots & FORBIDDEN_IMPORT_ROOTS, (
        f"{relative} imports {sorted(roots & FORBIDDEN_IMPORT_ROOTS)}.\n\n"
        "WHY THIS IS A FAILURE: the comparison exists to render the before/after offline. An "
        "inference import here means the measurement needs the model back, and the post-run "
        "chain would cost a GPU pass to run."
    )
    assert roots, (
        f"{relative} contains no import at all, so the assertion above holds for a file "
        "nothing was checked against. A guard that walks a set of files must find imports "
        "in them (`CONTRIBUTING.md:60`)."
    )
