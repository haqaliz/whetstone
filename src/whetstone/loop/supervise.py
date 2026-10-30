"""A parent process that can stop a night the runtime cannot interrupt.

The night writes one journal per completed draw. When a Metal call hangs, the process is in an
uninterruptible wait: an in-process timeout never runs, and no ledger is written. The only
reliable breaker is a **parent** that owns the child's process group, watches the journal
mtimes, and sends `SIGKILL` when the gap crosses the declared interval. The completed draws are
already on disk, so the operator resumes with the same command and the night replays them.

This module is deliberately stdlib-only and model-free. It knows a command, a run directory, a
stall interval and an operator-declared date; it knows nothing about MLX, Torch, a verifier or a
reward. The stall marker is local evidence under the gitignored runs home, never a published
report and never a verdict about a model.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path

#: The marker's schema — one shape for every stall, read by a human or a future tool.
STALL_SCHEMA = "whetstone-stall/1"

#: The marker's name inside the run directory.
STALL_FILE = "stalled.json"

#: The declared interval. A legitimate verification can spend `--timeout 900` per retry with
#: `R = 3`, and a repair adds further attempts; ninety minutes clears the worst case, and the
#: operator can raise it.
DEFAULT_STALL_SECONDS = 5400.0

#: How often the parent looks. The child's own draws are minutes apart; five seconds is cheap.
POLL_SECONDS = 5.0

#: The worker's argv must be a real `whetstone` invocation. There is no `__main__.py`; the
#: console script is `whetstone.cli:main`, and `-c` keeps the child independent of PATH.
_CHILD_CODE = "from whetstone.cli import main; raise SystemExit(main())"


def child_command(argv: Sequence[str]) -> list[str]:
    """The child command for a night's argv — the shipped CLI, in this interpreter."""
    return [sys.executable, "-c", _CHILD_CODE, *argv]


def without_supervise(argv: Sequence[str]) -> list[str]:
    """`argv` without the supervisor's own flags, so the child cannot recurse or refuse them.

    Both spellings of `--stall-seconds` are removed; `--supervise` is a store-true flag and
    carries no value.
    """
    stripped: list[str] = []
    skip_value = False
    for token in argv:
        if skip_value:
            skip_value = False
            continue
        if token == "--supervise":
            continue
        if token == "--stall-seconds":
            skip_value = True
            continue
        if token.startswith("--stall-seconds="):
            continue
        stripped.append(token)
    return stripped


def last_write(draws: Path) -> tuple[int, Path | None]:
    """The newest journal/transcript mtime and its path; `(0, None)` before the first draw.

    The ledger is written at the end and is not a liveness signal; the per-draw journals and
    transcripts are. A transcript is written as a generation completes, so it also catches a
    draw that hangs after its transcript (a verifier stall) only as far as the last write.
    """
    newest = 0
    newest_path: Path | None = None
    if not draws.is_dir():
        return newest, newest_path
    for pattern in ("*.journal.jsonl", "*.transcript.jsonl"):
        for path in draws.glob(pattern):
            try:
                mtime = path.stat().st_mtime_ns
            except OSError:
                continue
            if mtime > newest:
                newest = mtime
                newest_path = path
    return newest, newest_path


def _terminate(process: subprocess.Popen[bytes]) -> None:
    """Kill the child's whole process group; the verifier subprocesses are in it."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _write_marker(
    *,
    run: Path,
    run_id: str,
    recorded_on: str,
    stall_seconds: float,
    child_pid: int,
    last_write_ns: int,
    last_journal: Path | None,
    observed_after_seconds: float,
) -> Path:
    """Write the marker atomically under the run home, and return its path."""
    run.mkdir(parents=True, exist_ok=True)
    marker = run / STALL_FILE
    document = {
        "schema": STALL_SCHEMA,
        "run_id": run_id,
        "recorded_on": recorded_on,
        "stall_seconds": stall_seconds,
        "child_pid": child_pid,
        "last_journal": str(last_journal) if last_journal is not None else None,
        "last_write_ns": last_write_ns,
        "observed_after_seconds": round(observed_after_seconds, 3),
        "signal": "SIGKILL",
    }
    temporary = run / f".{STALL_FILE}.tmp"
    temporary.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, marker)
    return marker


def supervise(
    *,
    command: Sequence[str],
    run: Path,
    run_id: str,
    recorded_on: str,
    stall_seconds: float = DEFAULT_STALL_SECONDS,
    poll_seconds: float = POLL_SECONDS,
) -> int:
    """Run `command` as a child and return its code, or stop it after a journal stall.

    The spawn's wall time is the baseline, never an existing journal's mtime: a resumed run
    carries yesterday's journals and must not be killed before it can replay its first draw.
    The child's exit code is the answer when it exits; an unrelated signal is a failure (1),
    not a stall. Only this supervisor's own interval writes `stalled.json` and returns 2.
    """
    if stall_seconds <= 0:
        raise ValueError(
            f"stall_seconds must be positive, got {stall_seconds!r}; a zero or negative "
            "interval would kill every child before its first draw"
        )
    if poll_seconds <= 0:
        raise ValueError(f"poll_seconds must be positive, got {poll_seconds!r}")

    started = time.monotonic()
    spawn_ns = time.time_ns()
    process = subprocess.Popen(list(command), start_new_session=True)
    try:
        while True:
            code = process.poll()
            if code is not None:
                return code if code >= 0 else 1
            write_ns, journal = last_write(run / "draws")
            baseline = max(write_ns, spawn_ns)
            idle = (time.time_ns() - baseline) / 1_000_000_000
            if idle >= stall_seconds:
                _terminate(process)
                marker = _write_marker(
                    run=run,
                    run_id=run_id,
                    recorded_on=recorded_on,
                    stall_seconds=stall_seconds,
                    child_pid=process.pid,
                    last_write_ns=write_ns,
                    last_journal=journal,
                    observed_after_seconds=time.monotonic() - started,
                )
                print(
                    f"whetstone run: no journal write for {stall_seconds:g}s; stopped the "
                    f"night and wrote {str(marker)!r}. The completed draws replay on the "
                    "same command.",
                    file=sys.stderr,
                )
                return 2
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        _terminate(process)
        raise
