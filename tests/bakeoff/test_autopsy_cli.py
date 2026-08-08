"""The autopsy's door: the CLI, the locality refusal, and the document it writes.

Phase 4 of the autopsy slice: the fine pass and the mapping are useless until somebody can run
them over a real run, and `python -m whetstone.bakeoff.autopsy` is that door. It reads a run's
transcript and its own `attribution.json`, classifies every stored completion, asserts each fine
verdict against the coarse cause the run recorded, and writes the `whetstone-autopsy/1` document.

Two contracts guard the door, and both are honesty properties, so both are pinned here.

**The locality refusal comes first.** The document is built from stored completions, and a
completion quotes the user's own private donor code back verbatim — the reason the transcripts
themselves are refused under a published output directory (`test_run_transcript.py:156-184`).
So `--out` must sit under one of the roots `.gitignore:20-24` reserves, enforced *before*
anything is read and *before* anything is written: the test below points the CLI at missing
transcript and attribution files and asserts the refusal still fires — only a check that runs
first can do that — and the git half of this file proves the roots are really ignored, with the
trailing-slash form that `tests/test_tasks_layout.py` pins as load-bearing.

**The input contracts are exit 2, named.** A missing transcript, a missing attribution, a
document that does not parse, a cause the replay has no member for: each is refused with the
path and the reason in the message, never joined loosely. A join against nothing would render
every record's recorded cause as `None`, which is a run with a hole in its attribution wearing
the shape of a clean one.

The determinism test is the slice's AC1 at the door: the same inputs must write byte-identical
documents on two invocations, because a breakdown that changed between reads of the same run is
evidence nobody can re-derive.

All fixtures are synthetic replicas of observed shapes with toy names — never verbatim
completions (`card.md:68-70`) — and the git invocations here scrub the developer's own
configuration exactly as `test_attribution.py:118-141` does.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from whetstone.bakeoff.autopsy import (
    IGNORED_OUT_ROOTS,
    OutNotPrivate,
    main,
    refuse_published_out,
)

#: The repository root, reached from `tests/bakeoff/`: the worktree the CLI's locality rule
#: resolves its roots against, and where the document-under-test is written.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: A complete, well-formed diff (the shape `test_attribution.py`'s `GOOD_DIFF` uses): fenced, it
#: must classify `well-formed`.
GOOD_DIFF = """diff --git a/adder.py b/adder.py
--- a/adder.py
+++ b/adder.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b
+    return a + b
"""

#: The 7B signature shape (a dig replica, `dig-transcripts.md` § 2 shape 1): chat-template
#: tokens dominate, so the fine pass must answer `im-start-loop` and the `loop-present` marker
#: must fire.
LOOP_COMPLETION = "\n".join(["<|im_start|>", "system"] * 6) + "\n"

#: The three transcript rows the fixtures are built from. Two agree with their recorded coarse
#: cause; the loop record contradicts its own run's attribution, so the document carries exactly
#: one mapping violation and the stderr stream says so.
TRANSCRIPT_LINES = (
    {
        "candidate": "base-a",
        "task_id": "t1",
        "prompt_sha256": "ab" * 32,
        "prompt": "fix t1\n",
        "completion": "no patch here, sorry\n",
    },
    {
        "candidate": "base-a",
        "task_id": "t2",
        "prompt_sha256": "ab" * 32,
        "prompt": "fix t2\n",
        "completion": LOOP_COMPLETION,
    },
    {
        "candidate": "base-a",
        "task_id": "t3",
        "prompt_sha256": "ab" * 32,
        "prompt": "fix t3\n",
        "completion": f"```diff\n{GOOD_DIFF}```\n",
    },
)

#: The coarse rows the run's own attribution document carries, in the shape `attribution.py`
#: writes them.
ATTRIBUTION_ROWS = (
    {
        "candidate": "base-a",
        "task_id": "t1",
        "cause": "NO_DIFF_HEADER",
        "detail": "the output is prose",
    },
    {
        "candidate": "base-a",
        "task_id": "t2",
        "cause": "WOULD_NOT_PARSE",
        "detail": "a diff was located and git would not parse it",
    },
    {"candidate": "base-a", "task_id": "t3", "cause": "APPLIED", "detail": ""},
)

#: The same, as a whole `whetstone-attribution/1` document — a synthetic replica of what the
#: run's own driver wrote (`attribution.py:498-517`).
ATTRIBUTION_DOCUMENT = {
    "schema": "whetstone-attribution/1",
    "transcript": "the run's transcript",
    "rollouts": 3,
    "compared_to": None,
    "breakdown": {"base-a": {"no_diff": 2, "not_applied": 1, "applied": 1}},
    "divergences": [],
    "attributions": list(ATTRIBUTION_ROWS),
}


def _write_fixtures(tmp_path: Path, *, orphan: bool = False) -> tuple[Path, Path]:
    """The synthetic transcript and attribution document on disk, ready to be pointed at."""
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        "".join(json.dumps(line, sort_keys=True) + "\n" for line in TRANSCRIPT_LINES),
        encoding="utf-8",
    )
    attribution = tmp_path / "attribution.json"
    rows = [dict(row) for row in ATTRIBUTION_ROWS]
    if orphan:
        rows.append(
            {
                "candidate": "base-b",
                "task_id": "ghost",
                "cause": "NO_DIFF_HEADER",
                "detail": "never transcribed",
            }
        )
    attribution.write_text(
        json.dumps({**ATTRIBUTION_DOCUMENT, "attributions": rows}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return transcript, attribution


def _out(tmp_path: Path) -> Path:
    """A document path under the worktree's gitignored `runs/`, unique per test."""
    return REPO_ROOT / "runs" / "autopsy-tests" / tmp_path.name / "document.json"


def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Real git at the repository root, with the developer's own configuration switched off.

    The same environment scrubbing `test_attribution.py:118-141` uses: a machine-local
    `hooksPath` or `status.showUntrackedFiles` setting would change what the check-ignore and
    porcelain invocations answer.
    """
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_TERMINAL_PROMPT": "0",
            "HOME": str(REPO_ROOT),
        },
        check=False,
    )


# --------------------------------------------------------------------------------------------
# The locality refusal: before anything is read, nothing is written, and the path is named.
# --------------------------------------------------------------------------------------------


def test_an_out_outside_the_documented_roots_is_refused_before_anything_is_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--out` names where the document is published; a path git would commit is refused first.

    The document is built from stored completions, and a completion quotes the user's own
    private donor code back verbatim — the same reason transcripts are refused under a
    published output directory (`test_run_transcript.py:156-184`). So the refusal must arrive
    before ANY file is loaded: `tmp_path` is not under `runs/` or any other documented root,
    and here even the transcript and attribution do not exist — if the CLI had touched them
    first, this invocation would fail with a different error and the locality promise would be
    unenforced.
    """
    out = tmp_path / "out"

    exit_code = main(
        [
            "--transcript", str(tmp_path / "missing.jsonl"),
            "--attribution", str(tmp_path / "missing.json"),
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


def test_refuse_published_out_is_a_separate_testable_refusal(tmp_path: Path) -> None:
    """The refusal is its own function: it accepts the five documented roots, refuses the rest.

    A refusal embedded in `main` would be testable only through the CLI; this is the same
    `_refuse_published_transcript` discipline (`run.py:886-907`) split out so the rule and its
    message are checked directly, resolved on both sides.
    """
    with pytest.raises(OutNotPrivate) as refusal:
        refuse_published_out(tmp_path / "out")
    assert str(tmp_path / "out") in str(refusal.value)

    for root in IGNORED_OUT_ROOTS:
        refuse_published_out(REPO_ROOT / root / "any" / "depth" / "document.json")


# --------------------------------------------------------------------------------------------
# The input contracts: a missing file and a document that does not parse are exit 2, named.
# --------------------------------------------------------------------------------------------


def test_a_missing_transcript_exits_2_with_the_path_and_reason_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Classifying a transcript that is not there would report an empty run in a clean shape."""
    attribution = tmp_path / "attribution.json"
    attribution.write_text("{}", encoding="utf-8")

    exit_code = main(
        [
            "--transcript", str(tmp_path / "transcript.jsonl"),
            "--attribution", str(attribution),
            "--out", str(_out(tmp_path)),
        ]
    )

    assert exit_code == 2, exit_code
    message = capsys.readouterr().err
    assert str(tmp_path / "transcript.jsonl") in message and "not a file" in message, message


def test_a_missing_attribution_exits_2_with_the_path_and_reason_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The coarse causes come from the run's own attribution; without it there is no join."""
    transcript, _ = _write_fixtures(tmp_path)

    exit_code = main(
        [
            "--transcript", str(transcript),
            "--attribution", str(tmp_path / "no-attribution.json"),
            "--out", str(_out(tmp_path)),
        ]
    )

    assert exit_code == 2, exit_code
    message = capsys.readouterr().err
    assert str(tmp_path / "no-attribution.json") in message and "not a file" in message, message


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("not json at all {", "could not be read as JSON"),
        ("{}", "whetstone-attribution/1"),
        (json.dumps({"schema": "whetstone-attribution/1", "attributions": "nope"}), "attributions"),
    ],
)
def test_a_malformed_attribution_document_exits_2_naming_the_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], content: str, expected: str
) -> None:
    """A run whose attribution does not parse must be refused by name, never joined loosely."""
    transcript, _ = _write_fixtures(tmp_path)
    attribution = tmp_path / "attribution.json"
    attribution.write_text(content, encoding="utf-8")

    exit_code = main(
        [
            "--transcript", str(transcript),
            "--attribution", str(attribution),
            "--out", str(_out(tmp_path)),
        ]
    )

    assert exit_code == 2, exit_code
    message = capsys.readouterr().err
    assert expected in message, message


def test_an_unknown_cause_string_is_an_error_naming_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A cause the replay has no member for must be named, never mapped to a neighbour.

    The alternative is an unknown cause drifting into whichever bucket happens to match —
    the invented-taxonomy failure the whole slice exists to refuse (`prd.md` § 8).
    """
    transcript, _ = _write_fixtures(tmp_path)
    attribution = tmp_path / "attribution.json"
    rows = [dict(row) for row in ATTRIBUTION_ROWS]
    rows[1]["cause"] = "NOT_A_CAUSE"
    attribution.write_text(
        json.dumps({**ATTRIBUTION_DOCUMENT, "attributions": rows}, sort_keys=True),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--transcript", str(transcript),
            "--attribution", str(attribution),
            "--out", str(_out(tmp_path)),
        ]
    )

    assert exit_code == 2, exit_code
    message = capsys.readouterr().err
    assert "NOT_A_CAUSE" in message, message


# --------------------------------------------------------------------------------------------
# The document: what a good run writes, deterministically.
# --------------------------------------------------------------------------------------------


def test_the_document_round_trips_and_two_invocations_are_byte_identical(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A synthetic run, whole: the document carries the join, and the same input writes it twice.

    Determinism is an acceptance criterion (spec AC1): the same transcript and attribution must
    produce byte-identical documents on any number of invocations, because a breakdown that
    changed between reads of the same run would be evidence nobody can re-derive.
    """
    transcript, attribution = _write_fixtures(tmp_path)
    out = _out(tmp_path)
    args = [
        "--transcript", str(transcript),
        "--attribution", str(attribution),
        "--out", str(out),
    ]
    try:
        first = main(args)
        first_bytes = out.read_bytes()
        second = main(args)
        second_bytes = out.read_bytes()
    finally:
        shutil.rmtree(out.parent, ignore_errors=True)

    assert first == 0 and second == 0
    assert first_bytes == second_bytes, (
        "WHY THIS IS A FAILURE: two invocations over the same inputs wrote different bytes. A "
        "document that changes between reads of the same run is evidence nobody can re-derive"
    )

    document = json.loads(first_bytes)
    assert document["schema"] == "whetstone-autopsy/1", document
    assert document["rollouts"] == 3, document
    assert document["breakdown"] == {
        "base-a": {"im-start-loop": 1, "no-diff": 1, "well-formed": 1}
    }, document
    assert document["marker_counts"] == {"base-a": {"loop-present": 1}}, document
    assert document["mapping_violations"] == [
        {
            "candidate": "base-a",
            "task_id": "t2",
            "fine_cause": "im-start-loop",
            "recorded_cause": "WOULD_NOT_PARSE",
        }
    ], document
    assert document["orphan_attribution_rows"] == [], document

    records = document["records"]
    assert [record["candidate"] for record in records] == ["base-a", "base-a", "base-a"]
    assert [record["task_id"] for record in records] == ["t1", "t2", "t3"]
    assert [record["cause"] for record in records] == ["no-diff", "im-start-loop", "well-formed"]
    assert all(record["detail"] for record in records), "every record must carry its detail"
    assert [record["markers"] for record in records] == [[], ["loop-present"], []]
    assert [record["recorded_cause"] for record in records] == [
        "NO_DIFF_HEADER",
        "WOULD_NOT_PARSE",
        "APPLIED",
    ]
    assert [record["coarse_agrees"] for record in records] == [True, False, True]

    captured = capsys.readouterr()
    assert "base-a: im-start-loop=1, no-diff=1, well-formed=1" in captured.out, captured.out
    assert "wrote " in captured.out and str(out) in captured.out, captured.out
    assert (
        "base-a t2: fine=im-start-loop recorded=WOULD_NOT_PARSE" in captured.err
    ), captured.err


def test_an_orphan_attribution_row_is_listed_in_the_document_never_dropped(
    tmp_path: Path,
) -> None:
    """A coarse cause with no transcript record is reported, because dropping it would hide a hole.

    The transcript and the attribution are different files written at different times; a row
    present in one and absent from the other is a fact about the run, not a defect to tidy. The
    document lists it under its own key so the operator can see the join is partial — and the
    record count stays the transcript's, so the document never pretends the ghost was graded.
    """
    transcript, attribution = _write_fixtures(tmp_path, orphan=True)
    out = _out(tmp_path)
    try:
        assert main(
            [
                "--transcript", str(transcript),
                "--attribution", str(attribution),
                "--out", str(out),
            ]
        ) == 0
        document = json.loads(out.read_bytes())
    finally:
        shutil.rmtree(out.parent, ignore_errors=True)

    assert document["orphan_attribution_rows"] == [
        {"candidate": "base-b", "task_id": "ghost", "cause": "NO_DIFF_HEADER"}
    ], document
    assert document["rollouts"] == 3, document


# --------------------------------------------------------------------------------------------
# The git half: the documented roots are really ignored, and a document written there stays out.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("root", IGNORED_OUT_ROOTS)
def test_every_documented_breakdown_root_is_ignored_by_git(root: str) -> None:
    """The private half: a document written here can never reach a commit.

    Trailing-slash form, deliberately: these are directory-only patterns and `git check-ignore`
    answers differently without the slash — the trap `tests/test_tasks_layout.py` pins.
    """
    result = _git(["check-ignore", "-v", root])
    assert result.returncode == 0, (
        f"git would NOT ignore {root!r}, which is a documented home for an autopsy document. "
        f"The document quotes stored completions — the user's own private code — so a plain "
        f"`git add -A` would commit it: {result.stdout}{result.stderr}"
    )
    assert ".gitignore" in result.stdout, result.stdout


def test_a_document_written_under_runs_is_not_staged_by_git(tmp_path: Path) -> None:
    """The guarantee the guard above only implies, and the CLI's own output in the bargain.

    The document is written by the CLI itself, under the worktree's `runs/`, and git must
    report nothing: porcelain status lists any staged or untracked file, and the whole point of
    the locality rule is that this exact file cannot be committed by accident.
    """
    transcript, attribution = _write_fixtures(tmp_path)
    out = _out(tmp_path)
    try:
        assert main(
            [
                "--transcript", str(transcript),
                "--attribution", str(attribution),
                "--out", str(out),
            ]
        ) == 0
        assert out.is_file()

        status = _git(["status", "--porcelain", "--", "runs/"])
        assert status.stdout == "", (
            f"WHY THIS IS A FAILURE: a document under the documented breakdown root is "
            f"trackable: {status.stdout!r}. The locality rule exists to make this impossible"
        )
    finally:
        shutil.rmtree(out.parent, ignore_errors=True)
