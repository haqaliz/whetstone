"""The operator end of the attributor: a transcript in, a cause breakdown out, offline.

`attribution.py` is a library of pure functions, and until this entry point existed there was no
way to point it at a real run — the evidence a night produces would have sat on disk with nothing
able to read it. That is the gap this closes.

**No model is loaded and no network is touched.** The whole point of keeping the transcript is
that every later question about a run costs a file read rather than another night of generation,
so a driver that needed `mlx` would defeat the artifact it consumes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whetstone.bakeoff.attribution import Cause, main
from whetstone.bakeoff.transcript import Transcribed, Transcript

_DIFF = """diff --git a/calc.py b/calc.py
--- a/calc.py
+++ b/calc.py
@@ -1,2 +1,2 @@
-def add(a, b):
-    return a - b
+def add(a, b):
+    return a + b
"""


def _transcript(path: Path, rows: list[tuple[str, str, str]]) -> None:
    """Write a transcript of (candidate, task_id, completion) rows."""
    sink = Transcript(path)
    for candidate, task_id, completion in rows:
        sink.append(
            Transcribed(
                candidate=candidate,
                task_id=task_id,
                prompt_sha256="0" * 64,
                prompt="irrelevant to attribution",
                completion=completion,
                attempt=1,
                decision="graded",
            )
        )


def test_a_transcript_of_prose_is_attributed_without_any_checkout(tmp_path: Path) -> None:
    """The pure layer alone answers for output that never became a diff.

    Asserted with no `--tasks` at all, because needing a checkout to say "this was prose" would
    make the cheapest question in the breakdown depend on the most expensive machinery in it.
    """
    transcript = tmp_path / "t.jsonl"
    _transcript(
        transcript,
        [
            ("alpha", "task-1", "I think the bug is in calc.py. You should fix the operator."),
            ("alpha", "task-2", "   "),
        ],
    )
    out = tmp_path / "attribution.json"

    code = main(["--transcript", str(transcript), "--out", str(out)])
    assert code == 0, "attributing a transcript that needs no checkout should succeed"

    written = json.loads(out.read_text())
    causes = {row["task_id"]: row["cause"] for row in written["attributions"]}
    assert causes["task-1"] == Cause.NO_DIFF_HEADER.value, causes
    assert causes["task-2"] == Cause.NO_OUTPUT.value, causes


def test_the_breakdown_is_per_candidate_and_totals_the_transcript(tmp_path: Path) -> None:
    """Per candidate, because a pooled total is exactly what hides a difference between bases.

    And totalling the whole transcript, because a breakdown over a filtered subset is a breakdown
    whose denominator the reader cannot see.
    """
    transcript = tmp_path / "t.jsonl"
    _transcript(
        transcript,
        [
            ("alpha", "task-1", "prose, no diff here"),
            ("alpha", "task-2", "   "),
            ("beta", "task-1", "also prose"),
        ],
    )
    out = tmp_path / "attribution.json"
    assert main(["--transcript", str(transcript), "--out", str(out)]) == 0

    written = json.loads(out.read_text())
    assert written["breakdown"]["alpha"][Cause.NO_DIFF_HEADER.value] == 1
    assert written["breakdown"]["alpha"][Cause.NO_OUTPUT.value] == 1
    assert written["breakdown"]["beta"][Cause.NO_DIFF_HEADER.value] == 1

    total = sum(count for per in written["breakdown"].values() for count in per.values())
    assert total == 3, (
        f"the breakdown totals {total} over a transcript of 3 rollouts. A breakdown that does not "
        "total its input has silently dropped a rollout, and the reader has no way to see which"
    )


def test_a_missing_transcript_is_a_usage_error_rather_than_an_empty_breakdown(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An empty breakdown from an absent file is the vacuous-green shape at the report layer.

    It would render as "every rollout attributed, no causes found", which reads like a clean run
    and is in fact a run nobody measured.
    """
    code = main(
        ["--transcript", str(tmp_path / "absent.jsonl"), "--out", str(tmp_path / "out.json")]
    )
    assert code != 0, "attributing a transcript that does not exist reported success"
    assert "absent.jsonl" in capsys.readouterr().err


def test_the_comparison_runs_only_when_a_report_is_named(tmp_path: Path) -> None:
    """The reproduction check is opt-in, and its absence is visible in the output.

    A driver that silently omitted the comparison when `--report` was forgotten would produce a
    document that looks complete and answers a question nobody asked.
    """
    transcript = tmp_path / "t.jsonl"
    _transcript(transcript, [("alpha", "task-1", "prose")])
    out = tmp_path / "attribution.json"

    assert main(["--transcript", str(transcript), "--out", str(out)]) == 0
    assert json.loads(out.read_text())["compared_to"] is None

    report = tmp_path / "report.json"
    report.write_text(json.dumps({"source_b": [{"candidate": "alpha", "no_diff": 1}]}))
    assert main(
        ["--transcript", str(transcript), "--out", str(out), "--report", str(report)]
    ) == 0
    written = json.loads(out.read_text())
    assert written["compared_to"] == str(report)
    assert written["divergences"] == [], written["divergences"]


def test_a_divergence_from_the_record_is_reported_and_not_swallowed(tmp_path: Path) -> None:
    """PRD D2a: a divergence halts the slice, so it must reach the operator's eyes."""
    transcript = tmp_path / "t.jsonl"
    _transcript(transcript, [("alpha", "task-1", "prose")])
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"source_b": [{"candidate": "alpha", "no_diff": 7}]}))
    out = tmp_path / "attribution.json"

    assert main(
        ["--transcript", str(transcript), "--out", str(out), "--report", str(report)]
    ) == 0
    written = json.loads(out.read_text())
    assert written["divergences"], (
        "a count that disagreed with the record was reported as agreement"
    )
    assert written["divergences"][0]["field"] == "no_diff"
    assert written["divergences"][0]["recorded"] == 7
    assert written["divergences"][0]["replayed"] == 1
