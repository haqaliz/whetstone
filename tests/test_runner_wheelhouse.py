"""The suite's own scaffolding, held to the standard the suite holds everything else to.

This file exists because of a green run that meant nothing. Several tests build a throwaway venv
and install `pytest` into it with `uv pip install --offline pytest`, which resolves from uv's
cache and from nowhere else. On a developer machine that cache already holds pytest's registry
metadata, so the suite was **378 passed**. On a cold CI runner it does not — `uv sync` installs
what a lock decided and never performs the resolution that would cache an unpinned requirement —
so the same commit was **1 failed, 352 passed, 25 errors**, every one of them the same line:

    No solution found when resolving dependencies: because pytest was not
    found in the cache and you require pytest, we can conclude that your
    requirements are unsatisfiable.

The local green was the wrong answer, and nothing in the repository could tell. So the runner is
committed (`tests/fixtures/wheelhouse`), `tests/conftest.py` points every `uv` invocation at it,
and **this file reproduces the cold-cache condition inside the suite** — an empty `UV_CACHE_DIR`,
with a control showing the same install failing when the wheelhouse is taken away. A regression
here fails on the machine of whoever caused it rather than twenty minutes later in CI.

`pytest` is scaffolding and never a subject: no claim anywhere in this suite is about which
pytest ran, only that the declared tests were executed by one. The versions that *are* under
study live in `tests/fixtures/pkgindex`, are resolved by a different command, and — asserted
below — cannot be answered from here.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fixtures.runner import FIND_LINKS, RUNNER, WHEELHOUSE, uv_environment

#: The wheels the recorded index holds. Named here so "the scaffolding cannot supply a subject"
#: is asserted against the real directory rather than against a spelling typed twice.
_PKGINDEX = Path(__file__).parent / "fixtures" / "pkgindex"

#: Long enough for a cold resolution on a slow disk, short enough that a wedged uv is an error.
_TIMEOUT = 300.0

if shutil.which("uv") is None:  # pragma: no cover - the suite is run as `uv run pytest`
    raise RuntimeError(
        "uv is not on PATH, so no environment can be provisioned. This suite is run as "
        "`uv run pytest`; raising rather than skipping, because a silently skipped test of the "
        "suite's own provisioning is a green run that proves nothing about it"
    )


def test_every_uv_command_in_this_session_is_pointed_at_the_wheelhouse() -> None:
    """The fixture is in force, and observable.

    `runner_wheelhouse` is autouse, which makes it invisible: nothing in any other file mentions
    it, and a deletion would surface as an unrelated provisioning failure on somebody else's cold
    machine. Asserted here so the mechanism has one place that names it.
    """
    assert os.environ.get(FIND_LINKS) == str(WHEELHOUSE), (
        f"{FIND_LINKS} is {os.environ.get(FIND_LINKS)!r}, not the committed wheelhouse. Every "
        f"throwaway venv in this suite would then resolve {RUNNER} from whatever this machine's "
        f"uv cache happens to hold"
    )


def test_the_wheelhouse_holds_the_same_runner_the_suite_itself_runs_under() -> None:
    """The fixture venvs and this process run the *same* pytest, and drift is loud.

    The wheelhouse is a set of files and will not update itself. Without this, a `pytest` bump in
    `uv.lock` would leave every throwaway venv running the older release indefinitely: the reward
    parses pytest's junit report, so the suite would be exercising that parsing against a runner
    nobody ships, and no test would say so.

    The remedy when this fires is in the wheelhouse README — refresh it — never to relax the
    assertion.
    """
    running = pytest.__version__
    assert (WHEELHOUSE / f"{RUNNER}-{running}-py3-none-any.whl").is_file(), (
        f"the wheelhouse has no {RUNNER} {running} wheel, so the venvs this suite builds run a "
        f"different {RUNNER} from the one running this test: "
        f"{sorted(path.name for path in WHEELHOUSE.glob(f'{RUNNER}-*.whl'))}. Refresh it"
    )


def test_the_wheelhouse_holds_nothing_that_is_under_study() -> None:
    """Scaffolding and subject are different directories, and this is what keeps them apart.

    `tests/test_environment_pins.py` rests on `whetstone-fixture-dep` being resolvable **only**
    from the recorded index — that is how "the pin decided the verdict" is a statement about the
    pin rather than about what some other directory happened to offer. A runner wheelhouse that
    also carried a copy of a subject would be a second answer to the same question, sitting in a
    directory nobody looks at.

    Stated as a property of the two directories rather than of one package name, so a subject
    added to `pkgindex` later inherits the guarantee without anyone remembering to.
    """
    scaffolding = {_distribution(path.name) for path in WHEELHOUSE.glob("*.whl")}
    subjects = {_distribution(path.name) for path in _PKGINDEX.glob("*.whl")}
    assert subjects, f"{_PKGINDEX} holds no wheels, so this test is comparing against nothing"
    assert not scaffolding & subjects, (
        f"{WHEELHOUSE} holds {sorted(scaffolding & subjects)}, which {_PKGINDEX} also holds. The "
        f"versions under study must come from the recorded index and from nowhere else"
    )


def test_the_runner_installs_from_the_wheelhouse_with_a_completely_empty_cache(
    tmp_path: Path,
) -> None:
    """**The criterion.** What CI does, done here: provision the runner against an empty cache.

    `UV_CACHE_DIR` is pointed at a fresh directory, which is the cold runner in one flag. If this
    passes, the suite's provisioning is a property of the repository; if it fails, the suite is
    green only for whoever already had the right cache — which is the state this file was written
    to end.
    """
    interpreter = _venv(tmp_path / "warm", cache=tmp_path / "cache")
    completed = _install(interpreter, cache=tmp_path / "cache", find_links=str(WHEELHOUSE))

    assert completed.returncode == 0, (
        f"the runner could not be provisioned from the committed wheelhouse against an empty "
        f"cache, which is exactly what a CI runner offers: {completed.stderr.strip()}"
    )
    reported = subprocess.run(
        [str(interpreter), "-c", "import pytest; print(pytest.__version__)"],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
        check=False,
    )
    assert reported.returncode == 0, (
        f"uv reported success but the venv cannot import {RUNNER}: {reported.stderr.strip()}"
    )
    assert reported.stdout.strip() == pytest.__version__


def test_without_the_wheelhouse_that_same_install_fails_on_an_empty_cache(
    tmp_path: Path,
) -> None:
    """The control, and the half that makes the test above mean something.

    Without it, an empty `UV_CACHE_DIR` that uv quietly ignored would leave the test above
    passing from the developer's warm cache — a proof of provisioning that proves the machine.
    So the identical command is run with the wheelhouse taken away, and it must fail. This is the
    verbatim CI failure, reproduced locally on demand.
    """
    interpreter = _venv(tmp_path / "cold", cache=tmp_path / "cache")
    completed = _install(interpreter, cache=tmp_path / "cache", find_links="")

    assert completed.returncode != 0, (
        f"{RUNNER} installed offline with an empty cache and no wheelhouse, so this machine is "
        f"answering from somewhere neither the empty cache nor the committed wheels, and the "
        f"test above was not proving what it claims"
    )
    assert "not found in the cache" in completed.stderr, (
        f"the install failed for some reason other than a cold cache, so the condition under "
        f"reproduction is not the one CI hit: {completed.stderr.strip()}"
    )


def _distribution(wheel: str) -> str:
    """The normalised distribution name a wheel filename carries, for comparing two directories."""
    return wheel.split("-")[0].replace("_", "-").lower()


def _venv(location: Path, *, cache: Path) -> Path:
    """A throwaway venv built from this process's interpreter, against `cache`."""
    _uv(["venv", "--quiet", "--python", sys.executable, str(location)], cache=cache)
    return location / "bin" / "python"


def _install(
    interpreter: Path, *, cache: Path, find_links: str
) -> subprocess.CompletedProcess[str]:
    """The suite's own runner install, run with `cache` and `find_links` chosen by the caller.

    Deliberately the same shape as the installs in `tests/fixtures/repos/packaged.py` and
    `tests/test_strict.py`: `--offline`, an unpinned `pytest`, and no `--find-links` on the
    command line — so what is under assertion is the environment the session provides, which is
    the thing that broke.
    """
    return subprocess.run(
        ["uv", "pip", "install", "--quiet", "--offline", "--python", str(interpreter), RUNNER],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
        env=uv_environment(UV_CACHE_DIR=str(cache), UV_FIND_LINKS=find_links),
        check=False,
    )


def _uv(args: list[str], *, cache: Path) -> None:
    """uv, with its failure surfaced in full — a half-built venv fails later and opaquely."""
    completed = subprocess.run(
        ["uv", *args],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
        env=uv_environment(UV_CACHE_DIR=str(cache)),
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"uv {' '.join(args)} failed: {completed.stderr.strip()}")
