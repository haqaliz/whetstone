"""What a mined task says it runs under, and why source B can answer that and source A cannot.

`environment` is required on every manifest and every pin in it must be an exact `==`
(`verify/task.py`), because a verdict decided by whatever the index served that morning is not
execution-grounded. That contract is easy to state and, for a public benchmark instance, hard to
satisfy: `pallets__flask-5063` declares `click>=8.0` and nothing else, so its era-pins had to be
found by hand.

**Source B does not have that problem, and this file is where the asymmetry is demonstrated
rather than asserted.** A donor with a `uv.lock` has already answered the question its own
`pyproject.toml` left open — the fixture below declares `whetstone-fixture-dep` unbounded, and
the lock decides which one. Provisioning against the lock and freezing the result is therefore a
*reading*, not a resolution, and that is decision D-B in one sentence.

What is asserted here:

- every captured pin is an exact `==`, and the **task loader itself** accepts the captured
  environment — the form is proved by the contract that consumes it, not by a second regex;
- the runner is inside the capture, because the pins describe the environment the tests actually
  ran in and a set of pins that cannot run pytest describes nothing;
- a donor with **no lockfile is refused by name**, and specifically is not reported as an empty
  environment: `pins: []` means "nothing third-party is installed", which for an unlocked donor
  would be a claim nobody checked;
- the recorded `python` is the interpreter that actually ran, asked directly;
- nothing reaches the network, asserted from the argv that actually ran rather than from a
  comment saying so.

Offline throughout, against the committed index at `tests/fixtures/pkgindex`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fixtures.repos.locked import INDEX, LOCKFILE, locked_project_files

from whetstone.tasks.environment import (
    Captured,
    NoLockfile,
    NotProvisionable,
    capture,
    pins_from_freeze,
)
from whetstone.verify.task import load_task

if shutil.which("uv") is None:  # pragma: no cover - the suite is run as `uv run pytest`
    raise RuntimeError(
        "uv is not on PATH, so no environment can be provisioned. This suite is run as "
        "`uv run pytest`; raising rather than skipping, because a silently skipped capture "
        "test is a capture nobody checked"
    )

#: The unbounded requirement the fixture donor declares, and the version its lock settles on.
#: 2.0.0 is the higher of the two wheels in the recorded index, so it is what an unbounded
#: requirement gets — which is precisely the hole a lockfile closes for free.
_DEPENDENCY = "whetstone-fixture-dep"
_LOCKED_VERSION = "2.0.0"


@pytest.fixture(scope="module")
def captured(tmp_path_factory: pytest.TempPathFactory) -> Captured:
    """Provision one locked project and read back what it resolved to. Paid once."""
    root = tmp_path_factory.mktemp("capture")
    project = root / "project"
    locked_project_files(project, dependencies=(_DEPENDENCY,))
    return capture(project, venv=root / "venv", index=INDEX)


def test_every_captured_pin_is_an_exact_equality_pin(captured: Captured) -> None:
    """The form, not merely the presence — and proved by the contract that has to accept it.

    `load_task` refuses a pin that is not `name==version`, so writing the captured environment
    into a manifest and loading it is a stronger statement than any assertion this file could
    make about the string: it is the shipped consumer agreeing.
    """
    assert captured.pins, "nothing was captured, so this file proves nothing about the form"
    for pin in captured.pins:
        assert "==" in pin, f"{pin!r} is not an exact pin"
        name, _, version = pin.partition("==")
        assert name and version, f"{pin!r} has an empty half"
        assert not any(
            character in pin for character in "<>~ ;[]"
        ), f"{pin!r} carries a range, a marker or an extra, so the index still decides"


def test_the_task_loader_accepts_the_captured_environment(
    captured: Captured, tmp_path: Path
) -> None:
    """Round trip: what the miner captures is what the contract admits.

    The failure this prevents is a miner that captures a perfectly reasonable environment the
    loader then rejects — discovered at mint time, one task at a time, with the whole donor
    already provisioned.
    """
    manifest = tmp_path / "task.json"
    manifest.write_text(
        json.dumps(
            {
                "task_id": "capture-round-trip",
                "source": "private",
                "repo_url": "/nowhere",
                "base_commit": "0" * 40,
                "environment": {"python": captured.python, "pins": list(captured.pins)},
                "problem_statement": "the environment round-trips",
                "fail_to_pass": ["tests/test_x.py::test_y"],
                "pass_to_pass": [],
                "test_blobs": {"tests/test_x.py": "ZGVmIHRlc3RfeSgpOiBwYXNz"},
                "provenance": {},
            }
        )
    )
    task = load_task(manifest)
    assert task.environment.pins == captured.pins
    assert task.environment.python == captured.python


def test_the_lock_answers_what_the_requirement_left_open(captured: Captured) -> None:
    """Anti-vacuity, and decision D-B in one assertion.

    The project declares `whetstone-fixture-dep` with no upper bound. If the capture came back
    without it, every assertion above would hold over an environment that resolved nothing.
    """
    assert f"{_DEPENDENCY}=={_LOCKED_VERSION}" in captured.pins, captured.pins


def test_the_runner_is_part_of_the_captured_environment(captured: Captured) -> None:
    """pytest is in the pins because the declared tests run under it.

    A captured environment that cannot run pytest describes an environment no task was ever
    verified in. The pins are a record of what executed the tests, not of what the donor's
    `[project.dependencies]` happened to name.
    """
    assert any(pin.startswith("pytest==") for pin in captured.pins), captured.pins


def test_the_recorded_python_is_the_interpreter_that_actually_ran(captured: Captured) -> None:
    """Asked of the interpreter itself, not read off the machine running this test."""
    reported = subprocess.run(
        [str(captured.interpreter), "-c", "import platform; print(platform.python_version())"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert captured.python == reported
    assert captured.interpreter != Path(sys.executable), (
        "the capture handed back this process's own interpreter, so the provisioned venv is "
        "not what the task would run under"
    )


def test_the_capture_refuses_the_network_in_the_command_it_actually_ran(
    captured: Captured,
) -> None:
    """The offline claim, asserted from the argv rather than from a docstring.

    `--offline` refuses the network wholesale, and it is asserted over **every** installing
    command rather than the first: a second invocation without it is exactly the shape a network
    dependency creeps back in through. A capture that quietly fetched would still produce exact
    pins, and they would be pins for an environment the operator never chose.

    `--no-index` is narrower on purpose and is asserted only of the lock's own sync, where it
    makes the given directory not merely preferred but the only place what the lock names can
    come from. It is deliberately not applied to the runner: measured here, `--no-index` makes
    pytest unresolvable even from a warm cache, and pytest is what runs the tests rather than one
    of the versions under study — the same line `tests/test_environment_pins.py` already draws.
    """
    assert captured.installs, "no installing command was recorded, so nothing is under assertion"
    for command in captured.installs:
        assert "--offline" in command, f"--offline missing from {command}"
    assert any("--no-index" in command for command in captured.installs), captured.installs
    assert any("--find-links" in command for command in captured.installs), captured.installs


def test_a_donor_without_a_lockfile_is_refused_by_name(tmp_path: Path) -> None:
    """The refusal that keeps an unprovisioned donor out of the corpus.

    The alternative — resolve from the declared requirements and record whatever came back — is
    the flask incident with extra steps. The alternative to *that* is worse: emitting `pins: []`
    would state that the donor has no third-party dependencies, which for anything with a
    `requirements.txt` is simply false.
    """
    project = tmp_path / "unlocked"
    project.mkdir()
    (project / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0.0.0"\n')
    (project / "requirements.txt").write_text("django\n")

    with pytest.raises(NoLockfile) as raised:
        capture(project, venv=tmp_path / "venv")

    message = str(raised.value)
    assert LOCKFILE in message, message
    assert str(project) in message, message


def test_an_unlocked_donor_is_never_reported_as_an_empty_environment(tmp_path: Path) -> None:
    """The distinction the refusal exists to draw, stated as its own test.

    `pins: []` is a legitimate environment — it says *nothing is installed, so nothing can
    drift*. It is the wrong answer for a donor nobody provisioned, because the two are
    indistinguishable in the manifest and only one of them is true.
    """
    project = tmp_path / "unlocked"
    project.mkdir()
    (project / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0.0.0"\n')

    with pytest.raises(NoLockfile):
        capture(project, venv=tmp_path / "venv")


def test_a_freeze_line_that_is_not_an_exact_pin_is_refused_by_name() -> None:
    """A direct-URL install is not a pin, and must not be written into a manifest as one.

    `name @ https://…` is pinned to a URL rather than to a version: the loader would reject it,
    and silently dropping it would produce a manifest claiming an environment smaller than the
    one the tests ran in.
    """
    with pytest.raises(NotProvisionable) as raised:
        pins_from_freeze("wheel @ https://example.invalid/wheel.whl\n")
    assert "wheel @ https://example.invalid/wheel.whl" in str(raised.value)


def test_a_path_install_is_recorded_rather_than_dropped() -> None:
    """The project itself, installed from the checkout, is not a pin and is not silently gone.

    A local path install cannot be served differently by an index, so it cannot move a verdict —
    but it is part of what was installed, and a capture that dropped it without saying so would
    describe an environment nobody could reconstruct.
    """
    pins, local = pins_from_freeze(
        "-e file:///donor\nattrs==25.1.0\ndonor @ file:///donor\n",
    )
    assert pins == ("attrs==25.1.0",)
    assert local == ("-e file:///donor", "donor @ file:///donor")
