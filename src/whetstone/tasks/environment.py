"""What a mined task runs under: provision from the donor's own lock, then record what resolved.

Every manifest must carry exact `==` pins and a nominated interpreter (`verify/task.py`), because
a reward whose dependencies are chosen at resolution time is a reward decided by the calendar.
This module is how source B satisfies that contract.

**The asymmetry with source A, which is the whole reason source B is cheap (decision D-B).** A
public benchmark instance declares what its repository declared, and repositories declare ranges:
`pallets__flask-5063` says `click>=8.0` with no upper bound, so its era-pins had to be found by
hand, one incident at a time. A donor with a `uv.lock` has **already answered that question** —
the lock is the operator's own recorded resolution, made when the commit was written and by the
people who wrote it. So provisioning here is a *reading*, not a resolution: `uv sync --frozen`
installs what the lock already decided, and `uv pip freeze` reports what is now there. Nothing in
this module picks a version.

**Nothing here reaches the network, and the flags say so rather than the comment.** Every
installing command carries `--offline`, so uv may use its own on-disk cache and a local
`--find-links` directory and nothing else. The consequence is deliberate and is the direction to
fail in: a donor whose wheels are not already cached fails **loudly**, and the operator warms the
cache by running `uv sync` in their own repository — which is a thing they do anyway — rather
than a mint quietly fetching from an index at 3am and pinning whatever came back.

**Exactly what uv touches:** the donor's `pyproject.toml` and `uv.lock` (read), the venv it is
told to build, uv's own cache, and a `--find-links` directory when one is given. No index, no
network.

**A donor with no lockfile is refused by name, never captured as empty.** The two repairs both
lose: resolving from unbounded requirements *is* the flask incident, and emitting `pins: []`
states that the donor has no third-party dependencies — a sentence that is legitimate for a
single-module project and simply false for anything with a `requirements.txt`. The manifest
cannot tell those two apart, so the refusal happens here, where it can still name the donor.

**The runner is part of the captured environment.** pytest is installed before the freeze,
because the pins describe the environment the declared tests actually ran in and a pinned set
that cannot run pytest describes an environment no task was ever verified in.

Zero runtime dependencies: `subprocess` and a parse. No model, no network, nothing executed from
the donor.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Imported rather than restated, exactly as `derive.py` imports the reward path's pytest flags:
# this is the predicate `load_task` will apply to whatever is written into a manifest, and two
# spellings of it would be two things to keep in step — with the drifted one discovered a whole
# donor later, at load time, one task at a time.
from whetstone.verify.task import _PIN

#: Long enough for a cold venv on a slow disk, short enough that a wedged uv is an error rather
#: than an overnight mint that never returns. Matches the discipline in `donor.run_git`.
_UV_TIMEOUT = 900.0

#: The two files a provisionable donor carries. The lock is the one that matters; the project
#: file is named too so the refusal can tell "this is not a uv project" from "this project was
#: never locked".
PROJECT_FILE = "pyproject.toml"
LOCKFILE = "uv.lock"

#: The test runner, installed before the freeze. Named rather than inlined because it is the one
#: package this module adds to what the lock asked for, and that deserves to be visible.
_RUNNER = "pytest"

#: Where uv puts a venv's interpreter. macOS/Linux only, which is where the reward runs at all
#: (the Seatbelt sandbox is macOS-only).
_INTERPRETER = ("bin", "python")

#: Asked of the provisioned interpreter itself. Reading `sys.version` of the process doing the
#: mining would record the miner's python, which is not necessarily the one the tests will run
#: under — and the manifest's `environment.python` is a claim about the latter.
_VERSION_PROBE = "import platform; print(platform.python_version())"

#: A freeze line for something installed from a local path. Not a pin — there is no version for
#: an index to disagree about — and not discardable either; see `pins_from_freeze`.
_EDITABLE_PREFIX = "-e "
_PATH_MARKER = " @ file://"


class NotProvisionable(ValueError):
    """This donor cannot be provisioned into an environment a task could declare.

    Raised rather than returning a partial capture, because "the environment is empty" and "the
    environment could not be read" are different facts and only the first belongs in a manifest.
    """


class NoLockfile(NotProvisionable):
    """The donor carries no `uv.lock`, so nothing has answered what its requirements left open."""


@dataclass(frozen=True)
class Captured:
    """One provisioned environment, and the evidence for how it was obtained.

    `pins` is what goes into the manifest. `local` carries the path installs that are not pins —
    a `src`-layout donor installs itself, and freeze reports that as a path rather than a
    version. They are recorded rather than dropped: a path install cannot be served differently
    by an index, so it cannot move a verdict, but a capture that silently omitted it would
    describe an environment nobody could reconstruct.

    `installs` is every command that could have fetched anything, kept so the offline claim can
    be asserted from what actually ran rather than from this docstring.
    """

    python: str
    pins: tuple[str, ...]
    local: tuple[str, ...]
    interpreter: Path
    installs: tuple[tuple[str, ...], ...]


def capture(
    project: Path,
    *,
    venv: Path,
    python: Path | str | None = None,
    index: Path | None = None,
) -> Captured:
    """Provision `project` from its own lock into `venv`, and record what resolved.

    `python` is the interpreter the venv is built from; `None` means this process's own, which
    records that nobody chose — the same distinction `verify_strict` draws for its `timeout` and
    `run_id`. A lock whose `requires-python` excludes it fails loudly here, which is the honest
    outcome: that donor cannot be mined on this machine, and saying so is better than mining it
    under an interpreter its own authors excluded.

    `index` is a local directory that becomes the **only** place a distribution may come from
    (`--no-index --find-links`). It exists for a suite that must resolve a real dependency
    without a network; production passes `None` and uv falls back to its own cache, still
    offline.

    Raises `NoLockfile` if the donor was never locked, and `NotProvisionable` if uv failed or if
    the resulting environment cannot be described as exact pins.
    """
    location = Path(project)
    lock = location / LOCKFILE
    if not lock.is_file():
        raise NoLockfile(
            f"donor {str(location)!r} carries no {LOCKFILE}, so nothing has answered what its "
            f"requirements left open. Resolving them here would choose versions by the date the "
            f"mint ran — the failure `environment` exists to close — and recording no pins at "
            f"all would state that the donor has no third-party dependencies, which is a claim "
            f"about the donor that nobody checked. The donor is refused instead"
        )

    # `--offline` is the claim — the network is refused, on every command that could fetch.
    # `--no-index` is narrower and is applied only to the lock's own sync: it removes the
    # registry outright, so what the lock names can come from nowhere but the given directory.
    # The runner is deliberately not constrained that way (measured: `--no-index` makes pytest
    # unresolvable even from a warm cache), which is the same line `tests/test_environment_pins`
    # draws — pytest is the thing that runs the tests, not one of the versions under study.
    offline: tuple[str, ...] = ("--offline",)
    locked = offline
    if index is not None:
        offline += ("--find-links", str(Path(index)))
        locked = ("--offline", "--no-index", "--find-links", str(Path(index)))

    environment = venv.resolve()
    sync = (
        "sync",
        "--frozen",
        "--no-progress",
        "--project",
        str(location),
        "--python",
        str(python) if python else sys.executable,
        *locked,
    )
    # `UV_PROJECT_ENVIRONMENT` rather than a `.venv` inside the checkout: the checkout is a
    # scratch clone the miner also runs pytest in, and a venv sitting inside it is one more
    # directory every later step has to remember not to collect.
    _uv(sync, environment={"UV_PROJECT_ENVIRONMENT": str(environment)})

    interpreter = environment.joinpath(*_INTERPRETER)
    if not interpreter.is_file():
        raise NotProvisionable(
            f"uv sync reported success for {str(location)!r} but left no interpreter at "
            f"{str(interpreter)!r}, so there is nothing to verify the task under"
        )

    runner = ("pip", "install", "--quiet", "--python", str(interpreter), *offline, _RUNNER)
    _uv(runner)

    pins, local = pins_from_freeze(_uv(("pip", "freeze", "--python", str(interpreter))))
    return Captured(
        python=_probe(interpreter),
        pins=pins,
        local=local,
        interpreter=interpreter,
        installs=(sync, runner),
    )


def pins_from_freeze(output: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split `uv pip freeze` output into the exact pins and the path installs.

    Three outcomes and no fourth, because the fourth would be a silent drop:

    - `name==version` — a pin, validated against the **loader's own** predicate so a manifest
      cannot be written carrying something `load_task` will refuse;
    - a path or editable install — recorded in the second half, not a pin;
    - anything else, `name @ https://…` in particular — `NotProvisionable`, naming the line. A
      direct URL is pinned to a URL rather than to a version, which the contract does not accept
      and which this module has no business rewriting into something that looks like it does.

    Sorted, so a re-mint of the same donor produces the same manifest bytes.
    """
    pins: list[str] = []
    local: list[str] = []
    for raw in output.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(_EDITABLE_PREFIX) or _PATH_MARKER in line:
            local.append(line)
            continue
        if not _PIN.match(line):
            raise NotProvisionable(
                f"the provisioned environment reports {line!r}, which is not an exact '==' "
                f"requirement and is not a local path install. It cannot go into a manifest — "
                f"the loader refuses it — and dropping it would describe an environment smaller "
                f"than the one the tests ran in"
            )
        pins.append(line)
    return tuple(sorted(pins)), tuple(sorted(local))


def _probe(interpreter: Path) -> str:
    """The interpreter's own version, asked of the interpreter."""
    completed = subprocess.run(
        [str(interpreter), "-c", _VERSION_PROBE],
        capture_output=True,
        text=True,
        timeout=_UV_TIMEOUT,
        check=False,
    )
    if completed.returncode != 0:
        raise NotProvisionable(
            f"the provisioned interpreter {str(interpreter)!r} could not report its own "
            f"version: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def _uv(args: tuple[str, ...], *, environment: dict[str, str] | None = None) -> str:
    """uv, with its failure surfaced in full. Raises `NotProvisionable` on a non-zero exit.

    A half-built venv fails much later and much more opaquely — as a task whose declared tests
    cannot be collected — so the failure is reported here, where the command that produced it is
    still in hand.
    """
    context = dict(os.environ)
    context.update(environment or {})
    completed = subprocess.run(
        ["uv", *args],
        capture_output=True,
        text=True,
        env=context,
        timeout=_UV_TIMEOUT,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise NotProvisionable(f"uv {' '.join(args)} failed: {detail}")
    return completed.stdout


__all__ = [
    "LOCKFILE",
    "PROJECT_FILE",
    "Captured",
    "NoLockfile",
    "NotProvisionable",
    "capture",
    "pins_from_freeze",
]
