"""Exercises the CLI's observable behaviour: exit codes and what it writes to the streams.

The failure this prevents: a scaffold that satisfies "there is a test suite" with an import
smoke test. Every test here calls ``main(argv)`` and asserts on a return code AND on output,
because a CLI that exits 0 while printing nothing useful is indistinguishable from one that
works.

``test_the_parser_actually_exposes_help_and_version`` is the anti-vacuity control: the other
tests would still pass if the parser silently lost a flag and argparse errored its way to a
plausible-looking code, so one test observes the flags themselves.
"""

import argparse

import pytest

from whetstone import __version__
from whetstone.cli import build_parser, main


def option_strings(parser: argparse.ArgumentParser) -> set[str]:
    """Every flag the parser actually knows about, e.g. ``{"-h", "--help", "--version"}``."""
    return {option for action in parser._actions for option in action.option_strings}


def test_help_returns_zero_and_names_the_program(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--help"]) == 0
    assert "whetstone" in capsys.readouterr().out


def test_version_flag_prints_the_resolved_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_bare_invocation_returns_nonzero_and_prints_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    returncode = main([])
    assert returncode != 0
    captured = capsys.readouterr()
    assert "usage:" in captured.err
    assert "whetstone" in captured.err


def test_unknown_flag_returns_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--not-a-flag"]) != 0
    capsys.readouterr()


def test_the_parser_actually_exposes_help_and_version() -> None:
    """Anti-vacuity control — watched failing against an empty parser before being trusted."""
    flags = option_strings(build_parser())
    assert flags, "the introspection observed no flags at all, so it proves nothing"
    assert "--help" in flags
    assert "--version" in flags
