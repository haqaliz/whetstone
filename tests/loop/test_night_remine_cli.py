"""The night door's re-mine flags: parsed, validated, and forwarded — or a usage error.

`whetstone run --night` gains `--remine` / `--remine-label` (paired by position), `--remine-out`
and `--remine-limit`. The door validates them **before** the loop runs: a mismatch or a missing
companion is `USAGE_ERROR` (exit 2) naming the offending flag, never a silent default. The flags
then reach `run_night` under the names the loop declares.

This file is separate from `tests/loop/test_night_cli.py` on purpose: that file is a byte-identity
tripwire and stays unedited. It borrows its invocation and loop-substitute helper by identity.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from loop.test_night_cli import INVOCATION, _Checkpoint, _Dataset, _Night, _substitute
from whetstone import cli


def test_a_remine_donor_without_a_label_is_a_usage_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The pairs are by position; a donor with no label has no position to pair with."""
    code = cli.main(
        [*INVOCATION, "--remine", "/tmp/d", "--remine-out", "/tmp/r", "--remine-limit", "1"]
    )

    assert code == cli.USAGE_ERROR
    err = capsys.readouterr().err
    assert "--remine-label" in err, err
    assert "paired" in err, err


def test_a_label_without_a_donor_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    """A label with no donor is the same mismatch from the other side."""
    code = cli.main(
        [*INVOCATION, "--remine-label", "donor-x", "--remine-out", "/tmp/r", "--remine-limit", "1"]
    )

    assert code == cli.USAGE_ERROR
    err = capsys.readouterr().err
    assert "--remine" in err and "paired" in err, err


def test_a_remine_without_an_out_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    """`--remine-out` is required with any donor: the training-only root has no default."""
    code = cli.main(
        [*INVOCATION, "--remine", "/tmp/d", "--remine-label", "donor-x", "--remine-limit", "1"]
    )

    assert code == cli.USAGE_ERROR
    err = capsys.readouterr().err
    assert "--remine-out" in err and "required" in err, err


def test_a_remine_without_a_limit_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    """`--remine-limit` is required with any donor: the cost bound is never inherited."""
    code = cli.main(
        [*INVOCATION, "--remine", "/tmp/d", "--remine-label", "donor-x", "--remine-out", "/tmp/r"]
    )

    assert code == cli.USAGE_ERROR
    err = capsys.readouterr().err
    assert "--remine-limit" in err and "required" in err, err


def test_a_remine_limit_below_one_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    """The `run_mine` precedent: a limit below one would claim a mint that never ran."""
    code = cli.main(
        [
            *INVOCATION,
            "--remine",
            "/tmp/d",
            "--remine-label",
            "donor-x",
            "--remine-out",
            "/tmp/r",
            "--remine-limit",
            "0",
        ]
    )

    assert code == cli.USAGE_ERROR
    err = capsys.readouterr().err
    assert "--remine-limit" in err and "at least 1" in err, err


def test_the_remine_flags_reach_the_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """The four flags reach `run_night` under the names the loop declares, not a dead flag."""
    calls = _substitute(monkeypatch, _Night(dataset=_Dataset(), checkpoint=_Checkpoint()))

    code = cli.main(
        [
            *INVOCATION,
            "--remine",
            "/tmp/d",
            "--remine-label",
            "donor-x",
            "--remine-out",
            "/tmp/r",
            "--remine-limit",
            "3",
        ]
    )

    assert code == cli.PASS_EXIT, code
    assert len(calls) == 1, calls
    passed: dict[str, Any] = calls[0]
    assert passed["remine_donors"] == [Path("/tmp/d")], passed.get("remine_donors")
    assert passed["remine_labels"] == ["donor-x"], passed.get("remine_labels")
    assert passed["remine_out"] == Path("/tmp/r"), passed.get("remine_out")
    assert passed["remine_limit"] == 3, passed.get("remine_limit")


def test_no_remine_flags_are_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """A night with no re-mine flags passes today's defaults: empty, and `None` for out/limit."""
    calls = _substitute(monkeypatch, _Night(dataset=_Dataset(), checkpoint=_Checkpoint()))

    cli.main(INVOCATION)

    passed = calls[0]
    assert passed["remine_donors"] == [], passed.get("remine_donors")
    assert passed["remine_labels"] == [], passed.get("remine_labels")
    assert passed["remine_out"] is None, passed.get("remine_out")
    assert passed["remine_limit"] is None, passed.get("remine_limit")
