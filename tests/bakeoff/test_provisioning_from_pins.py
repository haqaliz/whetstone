"""A task that declares its own pins must be provisionable, lockfile or no lockfile.

The failure this prevents was found by running the bake-off, not by reading it.
`provision_from_lock` builds an environment by handing the checkout to `environment.capture`,
which reads that checkout's `uv.lock`. Every source-B donor has one, because the miner refused a
donor that did not — `rereflect` was turned away for exactly that reason (`tasks/README.md`).
**Source A has none and never will**:
`pallets__flask-4045` sits at a 2021 commit of a project that did not use uv, so the run refused it
with `NoLockfile`, its control arm skipped, and `rankable` — correctly — would not rank a candidate
whose harness had proved nothing. The whole night aborted on the last task.

The refusal was right about the donor and wrong about the task. A manifest **declares its
environment**: `pallets__flask-4045` carries nine exact `==` pins and a nominated interpreter,
which is the entire point of the `environment` contract — the verdict must not depend on what an
index served that morning (`whetstone/verify/task.py`). A lockfile is one way to have answered
that question. The manifest having answered it directly is another, and it is the authoritative
one at verification time: `capture` exists to *derive* pins when a task is minted, not to
re-derive them when one is graded.

So provisioning prefers the task's declared pins and falls back to the donor's lock only when
the task declares none. Source B is unaffected in substance — its pins were captured from that
same lock at mint time — but nothing about source B's route changes here, because a change to the
path that produced 66 proven-live tasks has to earn its way in on its own evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fixtures.repos import build_task

from whetstone.bakeoff.scoring import provision
from whetstone.tasks.gates import Ineligible
from whetstone.verify.task import load_task


def _repin(source: Path, pins: tuple[str, ...], *, python: str = "3.12") -> Path:
    """Rewrite a fixture manifest's declared environment, leaving everything else alone."""
    manifest = json.loads(source.read_text())
    manifest["environment"] = {"python": python, "pins": list(pins), "import_roots": ["."]}
    rewritten = source.parent / "repinned.json"
    rewritten.write_text(json.dumps(manifest))
    return rewritten


def test_a_task_that_declares_pins_is_provisioned_without_any_lockfile(tmp_path: Path) -> None:
    """The source-A case, reduced to its essentials: pins declared, no `uv.lock` anywhere.

    The fixture donor has no lockfile, so the lock route raises `NoLockfile` on it — which is what
    the real run hit. The declared pins are enough to build an environment, and an interpreter comes
    back.
    """
    fixture = build_task(tmp_path)
    # Pinned to a wheel the committed wheelhouse holds, so the install is offline: `conftest.py`
    # points every `uv` subprocess in this suite at it, on the stated ground that a suite fetching
    # from a registry would make its own results depend on what that registry served that morning.
    repinned = load_task(_repin(tmp_path / "task.json", ("iniconfig==2.3.0",)))

    interpreter = provision(repinned, tmp_path / "env")

    assert interpreter is not None and interpreter.exists(), (
        "a task declaring exact pins could not be provisioned.\n\n"
        "WHY THIS IS A FAILURE: the manifest already answered the question a lockfile answers, and "
        "refusing it means the one eligible public instance can never be graded — its control arm "
        "skips, its candidate is unrankable, and the whole run aborts on the last task."
    )
    assert fixture.task.environment.pins == (), "fixture drift: the base fixture should be unpinned"


def test_a_task_declaring_no_pins_still_uses_the_donors_lock(tmp_path: Path) -> None:
    """The anti-vacuity control: the lock route must still exist and still be the fallback.

    If this passed by having deleted the lock route, source B would silently move onto a different
    provisioning path than the one its 66 tasks were proven live under — and the failure would look
    like nothing at all until a verdict disagreed.
    """
    fixture = build_task(tmp_path)
    assert fixture.task.environment.pins == ()

    with pytest.raises((Ineligible, RuntimeError, ValueError)) as raised:
        provision(fixture.task, tmp_path / "env-lock")

    assert "uv.lock" in str(raised.value), (
        "a task declaring no pins did not reach the lockfile route.\n\n"
        f"WHY THIS IS A FAILURE: the fallback is gone, so source B's provisioning has silently "
        f"changed path. Got: {raised.value}"
    )


def test_the_real_public_instance_declares_what_provisioning_needs() -> None:
    """The committed artifact, asserted rather than assumed.

    A test that only exercised a fixture would prove the mechanism and not the case it was written
    for. This reads the instance that actually aborted the run.
    """
    root = Path(__file__).resolve().parents[2]
    instance = root / "tasks/public/instances/pallets__flask-4045.json"
    task = load_task(instance)

    assert task.environment.pins, (
        "the one eligible public instance declares no pins.\n\n"
        "WHY THIS IS A FAILURE: with neither pins nor a lockfile there is nothing to build an "
        "environment from, and the fix in this module cannot help it."
    )
    assert all("==" in pin for pin in task.environment.pins), task.environment.pins
    assert any(pin.startswith("pytest==") for pin in task.environment.pins), (
        "the public instance pins no pytest.\n\n"
        "WHY THIS IS A FAILURE: provisioning installs exactly what is declared, so a missing test "
        "runner surfaces as a sandbox that cannot start rather than as a task that failed."
    )
