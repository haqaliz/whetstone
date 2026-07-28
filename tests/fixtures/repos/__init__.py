"""Synthetic task repositories, built with real git, and the patches that act on them.

**Real git, not a hand-built tree.** ``verify_strict`` materialises a task by cloning
``repo_url`` and checking out ``base_commit``, so a fixture that faked the checkout would
leave that half of the verifier untested and would hand the later ingestion slice a surprise.
Every repository here is a genuine repository: ``git init``, one commit, a real SHA. The cost
is about 30ms per fixture, measured, and it buys a task whose `repo_url` and `base_commit`
mean what they say.

**Patches are generated, never hand-written.** ``make_patch`` clones the origin, applies the
edits, and asks git for the diff. A hand-written diff that failed to apply for a typo would
make a verifier test pass for the wrong reason — the patch-rejection tests especially, where
"rejected" is the expected outcome and a malformed patch is indistinguishable from a caught
cheat unless the diff is known-good.

**Tasks come from ``load_task``, never from the ``Task`` constructor.** The provenance
boundary says the only way to obtain a Task is an operator-controlled file; a test suite that
reached around it would be exercising a contract the product does not offer. So the fixture
writes a real manifest and loads it.

**Nothing here is collected by the outer suite.** The repositories exist as strings and are
materialised into ``tmp_path`` at test time. A checked-in ``tests/fixtures/repos/…/test_x.py``
would be picked up by ``testpaths = ["tests"]`` and run — as part of Whetstone's own suite —
which is exactly the confusion of "the tests under test" with "the tests" that this package is
about avoiding. Millisecond runtime, deterministic.

**One repository has a third-party dependency, and it is the exception that is the point.**
``GREETER`` imports ``whetstone_fixture_dep``, which is not installed in this project's
environment and never will be: it comes from the recorded local index at
``tests/fixtures/pkgindex`` and exists only so ``tests/test_environment_pins.py`` can resolve
it twice and watch the verdict move. Verifying ``GREETER`` under the verifier's own interpreter
is therefore a collection error, not a task — it must be handed a provisioned ``interpreter``.
Every other repository here imports nothing at all.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from whetstone.verify.task import Task, load_task

#: The bug. ``add`` subtracts, so the fail-to-pass test fails and the pass-to-pass test —
#: which only adds zero — does not notice.
CALC_BUGGY = "def add(a, b):\n    return a - b\n"

#: The genuine fix.
CALC_FIXED = "def add(a, b):\n    return a + b\n"

#: The cheat that no verifier can catch: right answer, wrong reason (roadmap cheat 6). Kept
#: here because both verifiers accept it and Phase 4 asserts that as the documented residual.
CALC_SPECIAL_CASED = (
    "def add(a, b):\n    if (a, b) == (2, 3):\n        return 5\n    return a - b\n"
)

_FAIL_TO_PASS_SOURCE = """\
from calc import add


def test_add_is_addition():
    assert add(2, 3) == 5
"""

_PASS_TO_PASS_SOURCE = """\
from calc import add


def test_adding_zero_is_the_identity():
    assert add(4, 0) == 4
"""


@dataclass(frozen=True)
class RepoSpec:
    """A repository, the node ids it declares, and which of its files the operator holds.

    ``held`` is what becomes ``test_blobs``: both the restore source and the rejection set.
    It is spelled out rather than inferred from the ``tests/`` prefix, because a task family
    where "the test files" is a guess is a task family with a hole in the boundary.

    ``problem_statement`` is carried here rather than passed to ``build_task`` so a repository
    and the sentence describing its bug cannot drift apart. It is a record — nothing in the
    reward reads it — but a manifest whose problem statement describes a different repository
    is a fixture that misleads whoever debugs against it next.
    """

    files: Mapping[str, str]
    fail_to_pass: tuple[str, ...]
    pass_to_pass: tuple[str, ...]
    held: tuple[str, ...]
    problem_statement: str = "add() subtracts."


#: One source file with a bug, the test that fails because of it, and a test that already
#: passes. ``from calc import add`` resolves because the verifier runs ``python -m pytest``
#: with the checkout as the working directory, which puts the checkout root on ``sys.path``.
BROKEN_ADDER = RepoSpec(
    files={
        "calc.py": CALC_BUGGY,
        "tests/test_addition.py": _FAIL_TO_PASS_SOURCE,
        "tests/test_identity.py": _PASS_TO_PASS_SOURCE,
    },
    fail_to_pass=("tests/test_addition.py::test_add_is_addition",),
    pass_to_pass=("tests/test_identity.py::test_adding_zero_is_the_identity",),
    held=("tests/test_addition.py", "tests/test_identity.py"),
)

#: The distribution the greeter repository needs, spelled the way a real repository spells it:
#: by name, with no upper bound. That spelling is the hole — ``pallets__flask-5063`` declares
#: ``click>=8.0`` and nothing else, so the version, and with it the verdict, is chosen by
#: whatever the index serves at resolution time. It resolves here against the recorded local
#: index at ``tests/fixtures/pkgindex``, never against PyPI.
FIXTURE_DEP = "whetstone-fixture-dep"

#: The exact pin that makes the greeter task verifiable. 1.0.0 is the version whose ``greet``
#: still accepts ``loud=``; 2.0.0 removed it, and 2.0.0 is what the unbounded requirement above
#: resolves to.
FIXTURE_DEP_PIN = f"{FIXTURE_DEP}==1.0.0"

#: The bug: ``announce`` accepts ``loud`` and then drops it on the floor.
GREETER_BUGGY = """\
from whetstone_fixture_dep import greet


def announce(name, *, loud=False):
    return greet(name)
"""

#: The genuine fix — and it is the same fix under either resolved version of the dependency,
#: which is what makes the greeter task a clean instrument: nothing about the patch changes
#: between the two arms, so nothing about the patch can explain the two verdicts.
GREETER_FIXED = """\
from whetstone_fixture_dep import greet


def announce(name, *, loud=False):
    return greet(name, loud=loud)
"""

_GREETER_TEST_SOURCE = """\
from greeter import announce
from whetstone_fixture_dep import greet


def test_announcing_loudly_shouts():
    assert announce("world", loud=True) == "HELLO, WORLD"


def test_the_dependency_greets_quietly():
    assert greet("world", loud=False) == "hello, world"
"""

#: A task that can only be verified once its dependency has been resolved — and that reaches a
#: different verdict depending on WHICH resolution it got. Both declared tests call
#: ``greet(..., loud=...)``, the keyword ``whetstone-fixture-dep`` 2.0.0 removed, so under the
#: unpinned resolution both fail with ``TypeError`` at call time while the module still imports
#: and pytest still collects exactly the declared set. That shape is deliberate: the failure has
#: to be the declared tests FAILING, not the suite failing to start, or the demonstration would
#: be of a broken install rather than of a corrupted reward.
GREETER = RepoSpec(
    files={
        "greeter.py": GREETER_BUGGY,
        "requirements.txt": f"{FIXTURE_DEP}\n",
        "tests/test_announce.py": _GREETER_TEST_SOURCE,
    },
    fail_to_pass=("tests/test_announce.py::test_announcing_loudly_shouts",),
    pass_to_pass=("tests/test_announce.py::test_the_dependency_greets_quietly",),
    held=("tests/test_announce.py",),
    problem_statement="announce() ignores loud=.",
)

#: A conftest that removes the failing test from the run WITHOUT skipping it and WITHOUT
#: touching a test file. pytest then exits 0 having reported zero skipped — the exit status
#: the reward would otherwise be read from is a clean pass. This is cheat 7's shape, and the
#: reason the executed-set assertion exists. It arrives as a ``conftest.py`` rather than as
#: ``[tool.pytest.ini_options] addopts`` because STRICT passes an explicit ``-c``, which
#: already blocks the config-file route; a root conftest is loaded regardless.
DESELECTING_CONFTEST = """\
def pytest_collection_modifyitems(config, items):
    doomed = [item for item in items if "test_add_is_addition" in item.nodeid]
    kept = [item for item in items if item not in doomed]
    config.hook.pytest_deselected(items=doomed)
    items[:] = kept
"""

#: The same idea one step less subtle: the failing test is marked skipped rather than
#: deselected, so pytest still exits 0. Caught by the skipped-count assertion.
SKIPPING_CONFTEST = """\
import pytest


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "test_add_is_addition" in item.nodeid:
            item.add_marker(pytest.mark.skip(reason="not today"))
"""

#: Kills the interpreter during collection with a zero exit status, so there is a return code
#: to read and no report behind it. The honest reading is UNVERIFIED, never a default PASS.
EXITING_CONFTEST = "import os\n\nos._exit(0)\n"

#: Hangs, so the sandbox has to kill the run. A run that did not finish is not a run that
#: failed.
HANGING_CONFTEST = "import time\n\ntime.sleep(120)\n"


@dataclass(frozen=True)
class Fixture:
    """A materialised task: the origin repository on disk, and the loaded ``Task``."""

    task: Task
    origin: Path
    spec: RepoSpec = field(repr=False)


def build_task(
    root: Path,
    spec: RepoSpec = BROKEN_ADDER,
    *,
    task_id: str = "synthetic-broken-adder",
    extra_blobs: Mapping[str, bytes] | None = None,
    pins: tuple[str, ...] = (),
) -> Fixture:
    """Create the origin repository under ``root`` and load a Task pointing at it.

    ``extra_blobs`` adds operator-held paths that are NOT in the repository, which is how the
    malformed-task case ("a ``test_blobs`` path is missing from the checkout") is provoked
    without hand-editing a manifest.

    ``pins`` becomes ``environment.pins``. It defaults to empty because almost every repository
    here imports nothing, and ``[]`` says exactly that; ``GREETER`` is the one that needs it.
    The manifest is written to ``root / "task.json"``, and that path is part of this fixture's
    contract — ``tests/test_environment_pins.py`` re-reads it to derive a second task that
    differs from the first in the pins and in nothing else.
    """
    origin = Path(root) / "origin"
    origin.mkdir(parents=True)
    for relative, contents in spec.files.items():
        destination = origin / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(contents)

    _git(["init", "--quiet", "--initial-branch=main"], cwd=origin)
    _git(["add", "--all"], cwd=origin)
    _git(["commit", "--quiet", "--message", "the known-broken commit"], cwd=origin)
    base_commit = _git(["rev-parse", "HEAD"], cwd=origin).strip()

    blobs = {path: (origin / path).read_bytes() for path in spec.held}
    blobs.update(extra_blobs or {})

    manifest = {
        "task_id": task_id,
        "source": "private",
        "repo_url": str(origin),
        "base_commit": base_commit,
        # Usually no third-party dependency, so nothing to pin — and `[]` says exactly that,
        # which is why the loader allows it. Most of these repositories are one module and two
        # pytest files; anything installed there would be a version this fixture could drift on
        # for no gain.
        "environment": {"python": "3.12", "pins": list(pins)},
        "problem_statement": spec.problem_statement,
        "fail_to_pass": list(spec.fail_to_pass),
        "pass_to_pass": list(spec.pass_to_pass),
        "test_blobs": {
            path: base64.b64encode(contents).decode("ascii") for path, contents in blobs.items()
        },
        "provenance": {"origin": "synthetic fixture"},
    }
    manifest_path = Path(root) / "task.json"
    manifest_path.write_text(json.dumps(manifest))
    return Fixture(task=load_task(manifest_path), origin=origin, spec=spec)


def make_patch(origin: Path, changes: Mapping[str, str | None]) -> str:
    """A real unified diff against the origin's HEAD. ``None`` deletes the path.

    Produced by git rather than written by hand: the tests that expect a patch to be
    *rejected* cannot tell a caught cheat from a diff that never applied, so the diff has to
    be known-good by construction.
    """
    with tempfile.TemporaryDirectory() as scratch:
        clone = Path(scratch) / "clone"
        _git(["clone", "--quiet", "--no-hardlinks", str(origin), str(clone)], cwd=Path(scratch))
        for relative, contents in changes.items():
            target = clone / relative
            if contents is None:
                target.unlink()
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(contents)
        _git(["add", "--all"], cwd=clone)
        return _git(["diff", "--cached"], cwd=clone)


def rename_patch(origin: Path, source: str, destination: str) -> str:
    """A patch that moves ``source`` to ``destination``.

    Its own fixture because git reports a rename by its DESTINATION only in the dry-run path
    STRICT checks first, so this is the shape that proves the second, post-apply check is
    doing work rather than repeating the first.
    """
    contents = (Path(origin) / source).read_text()
    return make_patch(origin, {source: None, destination: contents})


def _git(args: list[str], *, cwd: Path) -> str:
    """git with the machine's configuration switched off.

    ``GIT_CONFIG_GLOBAL``/``SYSTEM`` pointed at ``/dev/null`` so a developer's ``~/.gitconfig``
    — commit signing, hooks path, clean/smudge filters, a different default branch — cannot
    change what a fixture builds. The identity and the dates are pinned for the same reason:
    a fixture repository must have the same SHA on every machine and every run.
    """
    environment = dict(os.environ)
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_AUTHOR_NAME": "Whetstone Fixtures",
            "GIT_AUTHOR_EMAIL": "fixtures@whetstone.invalid",
            "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
            "GIT_COMMITTER_NAME": "Whetstone Fixtures",
            "GIT_COMMITTER_EMAIL": "fixtures@whetstone.invalid",
            "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
        }
    )
    completed = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout


__all__ = [
    "BROKEN_ADDER",
    "CALC_BUGGY",
    "CALC_FIXED",
    "CALC_SPECIAL_CASED",
    "DESELECTING_CONFTEST",
    "EXITING_CONFTEST",
    "FIXTURE_DEP",
    "FIXTURE_DEP_PIN",
    "GREETER",
    "GREETER_BUGGY",
    "GREETER_FIXED",
    "HANGING_CONFTEST",
    "SKIPPING_CONFTEST",
    "Fixture",
    "RepoSpec",
    "build_task",
    "make_patch",
    "rename_patch",
]
