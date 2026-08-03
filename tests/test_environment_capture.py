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
  comment saying so;
- **the donor's own project is never installed**, asserted from real `uv pip freeze` output and
  from the interpreter failing to import it. That is the second half of the inert-checkout fix:
  a venv carrying an editable install of the project answers `import <pkg>` from the
  *provisioning* checkout, so every later verification grades a tree the patch never touched —
  observed as a task passing with no patch applied. The venv carries dependencies only;
- **where the donor keeps its code is read, never guessed**, and a donor whose layout cannot be
  read is refused by name. A wrong import root is the one mistake here that does not announce
  itself: it produces PASS.

Offline throughout, against the committed index at `tests/fixtures/pkgindex`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fixtures.repos.locked import INDEX, LOCKFILE, locked_project_files
from fixtures.repos.packaged import packaged_project

from whetstone.tasks.environment import (
    Captured,
    NoLockfile,
    NotProvisionable,
    UnknownImportRoot,
    capture,
    import_roots,
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
                "environment": {
                    "python": captured.python,
                    "pins": list(captured.pins),
                    "import_roots": list(captured.import_roots),
                },
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
    assert task.environment.import_roots == captured.import_roots


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
    """A path install is not a pin and must not be silently gone from the record.

    Nothing should produce one any more — `--no-install-project` means the donor's own project is
    never installed, and it was the only path install there ever was. The parsing stays anyway, so
    that "no path install was reported" is something the test below can **assert** from real
    freeze output rather than infer from a flag. A path install cannot be served differently by an
    index, so it cannot move a verdict by version; what it can do is answer an import, which is
    the whole subject of `tests/adversarial/test_inert_checkout.py`.
    """
    pins, local = pins_from_freeze(
        "-e file:///donor\nattrs==25.1.0\ndonor @ file:///donor\n",
    )
    assert pins == ("attrs==25.1.0",)
    assert local == ("-e file:///donor", "donor @ file:///donor")


@pytest.fixture(scope="module")
def packaged(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Captured]:
    """A real `src`-layout package, provisioned. The shape the flat fixtures could not exercise.

    `locked_project_files` declares `[tool.uv] package = false`, so nothing about it was ever
    installed under a package name — which is precisely why the defect below survived a whole
    slice of tests. This donor is built as a package, with its code under `src/`, exactly like
    the first real donor.
    """
    root = tmp_path_factory.mktemp("packaged")
    project = packaged_project(root / "project")
    return project, capture(project, venv=root / "venv")


def test_the_donor_project_is_never_installed_into_the_captured_environment(
    packaged: tuple[Path, Captured],
) -> None:
    """The evidence, read back out of `uv pip freeze` rather than asserted from the flag.

    `uv sync --frozen` installs the project **editable**, rooted at whatever checkout it was
    pointed at, and freeze reports that as `-e file:///…`. The consequence is not cosmetic: for a
    `src`-layout donor that install answers `import calc` from the provisioning checkout, so every
    later verification — in a different directory — grades a tree no patch was applied to.
    Observed on the first real donor as a task passing with **no patch applied**.

    Asserted three ways because each catches a different regression: the freeze output the capture
    itself parsed, a **fresh** freeze of the venv (so a change in when the capture reads it cannot
    hide anything), and the interpreter simply failing to import the project at all.
    """
    project, captured = packaged
    assert captured.pins, "nothing was provisioned, so this assertion has no environment to make"
    assert captured.local == (), (
        f"the capture reported path installs {captured.local}, so something was installed from a "
        f"directory. If it is the donor's own project, every task minted from it can be verified "
        f"against that directory instead of against its own checkout"
    )

    frozen = subprocess.run(
        ["uv", "pip", "freeze", "--python", str(captured.interpreter)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "-e file://" not in frozen, frozen
    assert str(project) not in frozen, (
        f"the provisioning checkout {project} appears in the venv's freeze, so the venv can "
        f"answer an import from it:\n{frozen}"
    )


def test_the_provisioned_interpreter_cannot_import_the_donor_at_all(
    packaged: tuple[Path, Captured],
) -> None:
    """The same claim stated as a behaviour, which is the form that cannot be satisfied by luck.

    A freeze assertion checks what uv *reports*; this checks what the interpreter *does*. If the
    project is unimportable from the venv alone, then whatever imports it during a reward run came
    from the run's own checkout — which is the invariant, stated from the other side.
    """
    _, captured = packaged
    completed = subprocess.run(
        [str(captured.interpreter), "-c", "import calc"],
        capture_output=True,
        text=True,
        cwd=str(Path(captured.interpreter).parent),
        check=False,
    )
    assert completed.returncode != 0, (
        "the provisioned venv can import the donor's project on its own, so a verification run "
        "need never touch its own checkout to satisfy the declared tests"
    )
    assert "ModuleNotFoundError" in completed.stderr, completed.stderr


def test_the_import_roots_of_a_src_layout_donor_are_read_from_its_build_configuration(
    packaged: tuple[Path, Captured],
) -> None:
    """`packages = ["src/calc"]` names the package; `src` is the import root.

    Read from the donor's own declaration rather than from the presence of a `src/` directory,
    because the declaration is what the donor's authors actually committed to. This is hatchling's
    spelling, and it is the one `donor A` — the first real donor — uses.
    """
    _, captured = packaged
    assert captured.import_roots == ("src",)


def test_a_donor_that_is_not_built_as_a_package_imports_from_its_root(tmp_path: Path) -> None:
    """`[tool.uv] package = false` means nothing was installed under a package name.

    Its code is therefore imported from the repository root, which is `["."]`. This is the flat
    donor the mining fixtures use, and the branch that keeps the common case from needing a
    declaration nobody would otherwise write.
    """
    project = tmp_path / "flat"
    locked_project_files(project, index=None)

    assert import_roots(project) == (".",)


def test_setuptools_src_layout_is_read_too(tmp_path: Path) -> None:
    """The second spelling in the wild, so the reader is not hatchling-only.

    Both `package-dir` and `packages.find.where` name the directory rather than the package, so
    neither takes the parent the hatchling form does — a difference worth having a test for,
    because getting it wrong yields `"."` for a `src` project, which fails silently by passing.
    """
    project = tmp_path / "setuptools"
    (project / "src").mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["setuptools"]\nbuild-backend = "setuptools.build_meta"\n'
        '[project]\nname = "x"\nversion = "0.0.0"\n'
        '[tool.setuptools]\npackage-dir = {"" = "src"}\n'
    )

    assert import_roots(project) == ("src",)


def test_a_packaged_donor_whose_layout_is_ambiguous_is_refused_by_name(tmp_path: Path) -> None:
    """The refusal that exists because the wrong answer here does not fail loudly.

    A project that is built as a package, has a `src/` directory, and whose build configuration
    says nothing about where its packages are could mean either layout. Guessing `["."]` would
    leave the declared tests importing whatever the interpreter has — the inert-checkout defect,
    reintroduced silently, reported as PASS. Losing a donor is cheap by comparison, and the mint
    records the rejection and moves on.
    """
    project = tmp_path / "ambiguous"
    (project / "src").mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n'
        '[project]\nname = "x"\nversion = "0.0.0"\n'
    )

    with pytest.raises(UnknownImportRoot) as raised:
        import_roots(project)

    message = str(raised.value)
    assert str(project) in message, message
    assert "ambiguous" in message, message


def test_a_declared_import_root_that_is_not_in_the_checkout_is_refused(tmp_path: Path) -> None:
    """A root that is not there adds nothing to the path, so the tests import something else.

    That is the same failure as declaring the wrong root, arriving through a stale declaration
    rather than a wrong one — and it is equally invisible, because an absent `PYTHONPATH` entry
    produces no error of its own.
    """
    project = tmp_path / "stale"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n'
        '[project]\nname = "x"\nversion = "0.0.0"\n'
        '[tool.hatch.build.targets.wheel]\npackages = ["lib/x"]\n'
    )

    with pytest.raises(UnknownImportRoot, match="not a directory in the checkout"):
        import_roots(project)


def test_a_donor_with_no_project_file_has_no_readable_layout(tmp_path: Path) -> None:
    """Nothing declares where the code is, so nothing here will decide it.

    Unreachable through `capture`, which refuses a donor with no lockfile first — and asserted
    anyway, because `import_roots` is public and the mint's ordering is not a property this
    function gets to depend on.
    """
    project = tmp_path / "bare"
    project.mkdir()

    with pytest.raises(UnknownImportRoot, match=re.escape("pyproject.toml")):
        import_roots(project)


def test_a_donor_that_declares_its_layout_in_setup_cfg_is_read_rather_than_refused(
    tmp_path: Path,
) -> None:
    """setuptools' declarative config is a build configuration too, and it is often the only one.

    Public benchmark instances predate `pyproject.toml` as often as not — `pallets__flask-4045`
    sits at a 2021 commit carrying `setup.py` and `setup.cfg` and nothing else — and its
    `[options] package_dir = = src` says exactly what the pyproject spelling would. Refusing it
    would be refusing a declaration for the file it happens to live in, which is not a fact about
    the layout. Parsed with the stdlib `configparser`; the build backend is never invoked.
    """
    project = tmp_path / "cfg"
    (project / "src" / "thing").mkdir(parents=True)
    (project / "setup.py").write_text("from setuptools import setup\n\nsetup()\n")
    (project / "setup.cfg").write_text(
        "[metadata]\nname = thing\n\n[options]\npackages = find:\npackage_dir =\n    = src\n"
        "\n[options.packages.find]\nwhere = src\n"
    )

    assert import_roots(project) == ("src",)


def test_a_donor_with_no_build_configuration_at_all_is_still_refused(tmp_path: Path) -> None:
    """The refusal has to survive the widening above, or the widening removed a guard.

    A project with a `src/` directory and nothing anywhere saying what is in it is exactly the
    ambiguous case: guessing `["."]` leaves the declared tests importing whatever the interpreter
    has, which reports PASS for a patch nobody applied.
    """
    project = tmp_path / "silent"
    (project / "src").mkdir(parents=True)
    (project / "setup.py").write_text("from setuptools import setup\n\nsetup()\n")

    with pytest.raises(UnknownImportRoot):
        import_roots(project)
