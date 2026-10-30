"""The stall supervisor: a parent that can kill an uninterruptible night.

The 8B night hit an MPS OOM on the public task after ~35 h and hung; a resume failed on a
corrupted attention mask and a second resume hung. The 14B pre-flight hung on the eighth draw in
an uninterruptible Metal wait, and the 900 s draw timeout could not fire. An in-process timeout
cannot break that; a parent process can kill the child's process group, record the stall, and let
the operator resume from the journals the night already writes.

Every test here uses a stub child (a `python -c` script), never a model. The supervisor's own
contract is the subject: the child's exit code passes through, a stalled child is killed and
marked, an old journal does not make a resumed run look stalled, and the child's argv cannot
recurse into the supervisor.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

from whetstone.bakeoff.run import TranscriptNotPrivate
from whetstone.loop import night
from whetstone.loop.supervise import (
    STALL_FILE,
    STALL_SCHEMA,
    child_command,
    supervise,
    without_supervise,
)

#: A child that writes one journal and exits cleanly.
_HEALTHY = (
    "import pathlib, sys, time\n"
    "run = pathlib.Path(sys.argv[1])\n"
    "draws = run / 'draws'\n"
    "draws.mkdir(parents=True, exist_ok=True)\n"
    "(draws / '0001.journal.jsonl').write_text('first', encoding='utf-8')\n"
    "time.sleep(0.05)\n"
    "(draws / '0002.journal.jsonl').write_text('second', encoding='utf-8')\n"
)

#: A child that never writes a journal — the shape of the Metal hang.
_STALLED = "import time\ntime.sleep(5)\n"

#: A child that fails with the run's own failure code.
_FAILED = "raise SystemExit(1)\n"

#: A child killed by something other than the supervisor (the OOM killer's shape).
_SIGNALLED = "import os, signal\nos.kill(os.getpid(), signal.SIGKILL)\n"

#: A resumed run: write a fresh journal shortly after spawn, despite an old one on disk.
_RESUMED = (
    "import pathlib, sys, time\n"
    "run = pathlib.Path(sys.argv[1])\n"
    "draws = run / 'draws'\n"
    "draws.mkdir(parents=True, exist_ok=True)\n"
    "time.sleep(0.05)\n"
    "(draws / '0002.journal.jsonl').write_text('fresh', encoding='utf-8')\n"
)


def _run(*, command: str, tmp_path: Path, stall_seconds: float = 1.0) -> tuple[int, Path]:
    run = tmp_path / "runs" / "probe-001"
    code = supervise(
        command=[sys.executable, "-c", command, str(run)],
        run=run,
        run_id="probe-001",
        recorded_on="2026-10-30",
        stall_seconds=stall_seconds,
        poll_seconds=0.01,
    )
    return code, run


def test_a_healthy_child_is_passed_through(tmp_path: Path) -> None:
    """A child that keeps writing journals and exits 0 is the ordinary run."""
    code, run = _run(command=_HEALTHY, tmp_path=tmp_path)

    assert code == 0
    assert (run / "draws" / "0002.journal.jsonl").is_file()
    assert not (run / STALL_FILE).exists(), (
        "WHY THIS IS A FAILURE: a healthy child wrote a stall marker"
    )


def test_a_stalled_child_is_killed_and_recorded(tmp_path: Path) -> None:
    """No journal write for the interval: kill the group, record it, and refuse to proceed.

    The marker is the operator's evidence: which run, which journal was last written, how long
    the gap was, and the child that was killed. It is written under the gitignored run home,
    never a published report.
    """
    code, run = _run(command=_STALLED, tmp_path=tmp_path, stall_seconds=0.2)

    assert code == 2
    payload = json.loads((run / STALL_FILE).read_text(encoding="utf-8"))
    assert payload["schema"] == STALL_SCHEMA
    assert payload["run_id"] == "probe-001"
    assert payload["recorded_on"] == "2026-10-30"
    assert payload["stall_seconds"] == 0.2
    assert payload["child_pid"] > 0
    assert payload["last_journal"] is None
    assert payload["last_write_ns"] == 0
    assert payload["observed_after_seconds"] >= 0.2
    assert payload["signal"] == "SIGKILL"

    with pytest.raises(ProcessLookupError):
        os.kill(payload["child_pid"], 0)


def test_a_failed_child_code_is_passed_through(tmp_path: Path) -> None:
    """A night that exits 1 is a failed night, not a stall; its code is the answer."""
    code, run = _run(command=_FAILED, tmp_path=tmp_path)

    assert code == 1
    assert not (run / STALL_FILE).exists()


def test_an_unrelated_signal_is_a_failure_not_a_stall(tmp_path: Path) -> None:
    """A child killed by the OS is not the supervisor's stall; no marker is written."""
    code, run = _run(command=_SIGNALLED, tmp_path=tmp_path)

    assert code == 1
    assert not (run / STALL_FILE).exists(), (
        "WHY THIS IS A FAILURE: the supervisor wrote a stall marker for a kill it did not do"
    )


def test_a_resumed_run_is_not_killed_for_old_journals(tmp_path: Path) -> None:
    """The spawn is the baseline; a run resuming over yesterday's journals is not 'stalled'.

    Without this, the first resumed night would be killed before it could replay its first
    completed draw — the exact moment the supervisor must not interfere.
    """
    run = tmp_path / "runs" / "probe-001"
    draws = run / "draws"
    draws.mkdir(parents=True)
    old = draws / "0001.journal.jsonl"
    old.write_text("yesterday", encoding="utf-8")
    hour_ago = time.time() - 3600
    os.utime(old, (hour_ago, hour_ago))

    code = supervise(
        command=[sys.executable, "-c", _RESUMED, str(run)],
        run=run,
        run_id="probe-001",
        recorded_on="2026-10-30",
        stall_seconds=0.5,
        poll_seconds=0.01,
    )

    assert code == 0
    assert not (run / STALL_FILE).exists()


def test_without_supervise_strips_both_flags() -> None:
    """The child must not see the supervisor flags, or it would recurse on `--supervise`."""
    assert without_supervise(
        ["run", "--night", "--supervise", "--stall-seconds", "12", "--run-id", "x"]
    ) == ["run", "--night", "--run-id", "x"]
    assert without_supervise(
        ["run", "--night", "--supervise", "--stall-seconds=12"]
    ) == ["run", "--night"]


def test_the_child_command_is_the_documented_form() -> None:
    """The child is a real `whetstone` invocation, not a copy of the night's logic."""
    assert child_command(["run", "--night", "--run-id", "x"]) == [
        sys.executable,
        "-c",
        "from whetstone.cli import main; raise SystemExit(main())",
        "run",
        "--night",
        "--run-id",
        "x",
    ]


def test_a_non_positive_stall_is_refused() -> None:
    """A zero or negative interval would kill every child immediately; refuse it."""
    with pytest.raises(ValueError):
        supervise(
            command=[sys.executable, "-c", "pass"],
            run=Path("/tmp/never-used"),
            run_id="x",
            recorded_on="2026-10-30",
            stall_seconds=0,
        )


def test_supervise_night_refuses_a_published_runs_root(tmp_path: Path) -> None:
    """A supervisor must not create a marker under `reports/`, even before the child refuses."""
    with pytest.raises(TranscriptNotPrivate):
        night.supervise_night(
            argv=["run", "--night", "--supervise"],
            runs=tmp_path / "reports" / "nightly",
            run_id="probe-001",
            recorded_on="2026-10-30",
            stall_seconds=1,
        )


def test_supervise_night_strips_the_flags_and_names_the_child(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The binding hands the pure supervisor a clean child command and the run identity."""
    seen: dict[str, object] = {}

    def fake(**kwargs: object) -> int:
        seen.update(kwargs)
        return 0

    monkeypatch.setattr(night, "supervise", fake)

    code = night.supervise_night(
        argv=[
            "run",
            "--night",
            "--supervise",
            "--stall-seconds",
            "12",
            "--run-id",
            "probe-001",
        ],
        runs=tmp_path / "runs",
        run_id="probe-001",
        recorded_on="2026-10-30",
        stall_seconds=12,
    )

    assert code == 0
    assert seen["run"] == tmp_path / "runs" / "probe-001"
    assert seen["run_id"] == "probe-001"
    assert seen["recorded_on"] == "2026-10-30"
    assert seen["stall_seconds"] == 12
    command = seen["command"]
    assert isinstance(command, list)
    assert "--supervise" not in command
    assert "--stall-seconds" not in command
    assert command[-1] == "probe-001"
