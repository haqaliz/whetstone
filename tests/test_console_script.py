"""Runs the installed `whetstone` binary in a real subprocess.

The failure this prevents: a package that is importable but not *installable as a command*.
An in-process call to ``main()`` cannot tell a wired `[project.scripts]` entry point from a
module that merely happens to be on ``sys.path`` — which is exactly the mistake this file
exists to catch. So these tests spend the cost of a subprocess deliberately.
"""

import shutil
import subprocess
import sys
from pathlib import Path

from whetstone import __version__


def console_script() -> Path:
    """The installed `whetstone` executable, or a failure naming why it is missing."""
    candidate = Path(sys.executable).parent / "whetstone"
    if candidate.exists():
        return candidate
    found = shutil.which("whetstone")
    if found is None:
        raise AssertionError(
            "the `whetstone` console script is not installed; run `uv sync`. "
            "This means [project.scripts] is unwired, not that the test is broken."
        )
    return Path(found)


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(console_script()), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_console_script_help_exits_zero() -> None:
    result = run("--help")
    assert result.returncode == 0, result.stderr
    assert "whetstone" in result.stdout


def test_console_script_version_matches_the_installed_package() -> None:
    result = run("--version")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == __version__


def test_console_script_bare_invocation_exits_nonzero() -> None:
    result = run()
    assert result.returncode != 0
    assert "usage:" in result.stderr
