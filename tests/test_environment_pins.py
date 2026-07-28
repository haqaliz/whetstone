"""`environment.pins` decides the verdict. Demonstrated, not asserted.

This is the one file in the suite where the adversary is a **calendar**. Nothing here cheats:
the task is honest, the patch is correct, the verifier is the shipped one, and the reward still
comes out wrong — because the dependency was resolved without the pin the manifest carries.

The incident it miniaturises is real. SWE-bench's ``pallets__flask-5063`` declares
``click>=8.0`` and nothing more. Resolved today that is a click which removed
``CliRunner(mix_stderr=)``, so four of the task's ``pass_to_pass`` tests failed and STRICT
returned FAIL for a patch that was correct — a **false FAIL**, produced by the resolution date.
Pinning click 8.1.3 turned the same task fully green. A reward that moves with the index is not
execution-grounded, whatever else is true of it.

**The claim, and it is a claim about a verdict.** The same task, the same patch, the same
verifier, resolved two ways:

- with ``environment.pins == ("whetstone-fixture-dep==1.0.0",)`` -> **PASS**
- with ``environment.pins == ()``, so the repository's own unbounded requirement decides -> **FAIL**

The two tasks are compared field by field first, so "the same task" is a fact rather than a
claim: they differ in ``environment`` and in nothing else.

**Offline, and asserted so.** The two versions come from a committed local index
(``tests/fixtures/pkgindex``), resolved with ``--offline --no-index --no-cache --find-links``.
A test that reached PyPI to prove this would be **self-refuting** — its own result would depend
on what an index served that morning, which is precisely the failure it claims to guard. The
flags are asserted from the argv actually invoked, and a control resolution proves the index is
genuinely the only source: a package absent from it cannot be installed.

**Provisioning happens outside the sandbox; execution happens inside it.** The venvs are built
by ``uv`` in the test, and only the resolved interpreter crosses into ``verify_strict``. That
is the shipped design, not a shortcut: ``strict.py`` resolves nothing and installs nothing, on
purpose — a reward path that can install packages is a reward path whose verdict depends on a
resolver, a cache and a network.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as distribution_version
from pathlib import Path

import pytest
from fixtures.repos import (
    FIXTURE_DEP,
    FIXTURE_DEP_PIN,
    GREETER,
    GREETER_FIXED,
    build_task,
    make_patch,
)
from fixtures.runner import WHEELHOUSE

from whetstone.verify.strict import StrictResult, read_report, verify_strict
from whetstone.verify.task import Task, load_task
from whetstone.verify.verdict import Status

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin",
    reason="the reward runs inside the Seatbelt sandbox, which is macOS-only",
)

#: The recorded index. Two wheels of one package, committed; see its README for why.
INDEX = Path(__file__).parent / "fixtures" / "pkgindex"

#: What each arm's resolution is expected to select. 2.0.0 is the higher version, so it is what
#: an unbounded requirement gets — which is the whole mechanism of the hole.
_PINNED_VERSION = "1.0.0"
_UNPINNED_VERSION = "2.0.0"

#: As in `tests/test_strict.py`: long enough that a slow machine is not misreported as an
#: unverifiable task, short enough that a hung run does not hold the suite.
_TIMEOUT = 120.0

#: Asks the installed package the one question the whole file rests on, and prints the answer.
_KEYWORD_PROBE = (
    "from whetstone_fixture_dep import greet\n"
    "try:\n"
    "    greet('world', loud=True)\n"
    "except TypeError:\n"
    "    print('TypeError')\n"
    "else:\n"
    "    print('accepted')\n"
)


@dataclass(frozen=True)
class Arm:
    """One resolution of the greeter task's dependency, and what it decided.

    ``install_argv`` is kept so the offline claim is asserted from the command that actually
    ran rather than from a comment saying it did. ``report`` is pytest's own junit output for
    the run, read back through the verifier's own ``read_report`` — the reward's grounding
    names *which* checks failed, and the report is how "and these declared tests are the ones
    that failed" is shown rather than inferred.
    """

    task: Task
    requirement: str
    interpreter: Path
    resolved_version: str
    install_argv: tuple[str, ...]
    result: StrictResult
    report: Path


@pytest.fixture(scope="module")
def arms(tmp_path_factory: pytest.TempPathFactory) -> tuple[Arm, Arm]:
    """Verify one task and one patch twice, under two resolutions of one dependency.

    Module-scoped because it builds two venvs and runs pytest twice inside the sandbox; paying
    that once and asserting on it from several named tests is the difference between a test
    someone keeps and a test someone deletes. It returns ``(pinned, unpinned)``.

    Both arms share the origin repository, the base commit, the golden test blobs and the
    patch — all of them built once, above the split. The only input that differs is the
    manifest's ``environment.pins``, and everything downstream of it follows from that one
    difference.
    """
    if shutil.which("uv") is None:
        raise RuntimeError(
            "uv is not on PATH, so no environment can be provisioned. This suite is run as "
            "`uv run pytest`; raising rather than skipping, because a silently skipped test of "
            "the pins contract is a green suite that proves nothing about it."
        )

    root = tmp_path_factory.mktemp("environment-pins")
    fixture = build_task(root, GREETER, task_id="synthetic-greeter", pins=(FIXTURE_DEP_PIN,))
    patch = make_patch(fixture.origin, {"greeter.py": GREETER_FIXED})

    unpinned_task = _without_pins(root / "task.json", root / "task-unpinned.json")
    sandbox_root = root / "sandbox"

    return (
        _verify(
            fixture.task,
            patch,
            requirement=_requirement(fixture.task, fixture.origin),
            venv=root / "venv-pinned",
            sandbox_root=sandbox_root,
            run_id="pinned",
        ),
        _verify(
            unpinned_task,
            patch,
            requirement=_requirement(unpinned_task, fixture.origin),
            venv=root / "venv-unpinned",
            sandbox_root=sandbox_root,
            run_id="unpinned",
        ),
    )


def _verify(
    task: Task,
    patch: str,
    *,
    requirement: str,
    venv: Path,
    sandbox_root: Path,
    run_id: str,
) -> Arm:
    """Provision `requirement` into `venv`, then verify `task` under that interpreter."""
    interpreter, install_argv = _provision(venv, requirement)
    result = verify_strict(
        task,
        patch,
        sandbox_root=sandbox_root,
        timeout=_TIMEOUT,
        run_id=run_id,
        interpreter=interpreter,
    )
    return Arm(
        task=task,
        requirement=requirement,
        interpreter=interpreter,
        resolved_version=_resolved_version(interpreter),
        install_argv=install_argv,
        result=result,
        report=sandbox_root / run_id / "report.xml",
    )


def _requirement(task: Task, origin: Path) -> str:
    """What a provisioner installs for this task: the manifest's pin, or the repository's word.

    The fallback is deliberately the repository's own ``requirements.txt`` line rather than a
    string typed into this test. That is what an ingester without pins would have to fall back
    to, and it is what flask-5063 fell back to: a requirement with a floor and no ceiling.
    """
    if task.environment.pins:
        assert len(task.environment.pins) == 1, (
            f"the greeter task is meant to pin exactly one package; got "
            f"{task.environment.pins!r}, so this helper is resolving less than the manifest says"
        )
        return task.environment.pins[0]
    declared = (origin / "requirements.txt").read_text().strip()
    assert declared, (
        f"{origin / 'requirements.txt'} is empty, so the unpinned arm would install nothing and "
        f"would prove nothing"
    )
    return declared


def _without_pins(manifest: Path, destination: Path) -> Task:
    """The same manifest with ``environment.pins`` emptied, loaded through ``load_task``.

    A *copy of the manifest* rather than a second ``build_task`` call, because the claim is
    about one task resolved two ways. Rebuilding would give a second origin repository at a
    second path, and "the same task" would then be an approximation. Here every other byte of
    the manifest is carried over verbatim, and
    ``test_the_two_tasks_differ_only_in_their_pins`` checks that on the loaded objects.

    It still goes through ``load_task``: the provenance boundary says a Task comes from an
    operator file and nothing else, and a test that reached for the constructor would be
    exercising a contract the product does not offer.
    """
    raw = json.loads(manifest.read_text())
    assert raw["environment"]["pins"], (
        f"{manifest} was expected to carry pins to remove; it carries "
        f"{raw['environment']['pins']!r}, so this fixture would be comparing a task with itself"
    )
    raw["environment"] = {**raw["environment"], "pins": []}
    destination.write_text(json.dumps(raw))
    return load_task(destination)


def _provision(venv: Path, requirement: str) -> tuple[Path, tuple[str, ...]]:
    """Build a venv and resolve `requirement` into it from the recorded index only.

    Four flags, each doing separate work, and the reason each is here rather than implied:

    - ``--no-index`` removes PyPI from the resolution outright, so the local directory is not
      merely *preferred*, it is the only place a distribution can come from.
    - ``--offline`` refuses the network wholesale, so a stray index URL from a config file or
      an environment variable cannot reintroduce one.
    - ``--no-cache`` keeps uv's cache out of the answer. Without it a previously unpacked
      ``whetstone-fixture-dep`` could satisfy the install and the committed wheel would never
      be read — the test would still be offline and would no longer be testing the index.
    - ``--find-links`` is the index itself.

    ``pytest`` is a second, separate install and deliberately *not* constrained to the index:
    it is the runner, not the thing under test. It comes from the committed wheelhouse that
    ``tests/conftest.py`` names, offline, and never from this index — see
    ``test_the_scaffolding_cannot_supply_the_subject`` below, which is what keeps that a fact.
    Nothing about which pytest runs is what this file is measuring; the two arms get the same
    one. It is a separate command for the same reason it is a separate directory: the
    ``--find-links`` above is spelled on the command line, which **overrides** the wheelhouse
    outright, so the two resolutions cannot borrow from each other in either direction.
    """
    _uv(["venv", "--quiet", "--python", sys.executable, str(venv)])
    interpreter = venv / "bin" / "python"
    install_argv = (
        "pip",
        "install",
        "--quiet",
        "--python",
        str(interpreter),
        "--offline",
        "--no-index",
        "--no-cache",
        "--find-links",
        str(INDEX),
        requirement,
    )
    _uv(list(install_argv))
    _uv(["pip", "install", "--quiet", "--offline", "--python", str(interpreter), "pytest"])
    return interpreter, install_argv


def _resolved_version(interpreter: Path) -> str:
    """The version the resolver actually chose, read from the installed distribution metadata.

    The *distribution's* version, not the module's ``VERSION`` constant: what is under
    assertion is what the resolver picked, and a constant inside the package could agree with
    the metadata while the wrong wheel was installed.
    """
    return _python(
        interpreter,
        "from importlib.metadata import version\nprint(version('whetstone-fixture-dep'))",
    )


def _python(interpreter: Path, source: str) -> str:
    """Run `source` under `interpreter` and return its stdout, stripped."""
    completed = subprocess.run(
        [str(interpreter), "-c", source], capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise RuntimeError(f"{interpreter} failed on {source!r}: {completed.stderr.strip()}")
    return completed.stdout.strip()


def _uv(args: list[str]) -> None:
    """uv, with its failure surfaced in full — a half-built venv fails later and opaquely."""
    completed = subprocess.run(["uv", *args], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"uv {' '.join(args)} failed: {completed.stderr.strip()}")


def _verdict_of(result: StrictResult, kind: str) -> tuple[Status, str]:
    """The status and message a named sub-check produced, so a test can assert WHY."""
    matching = [verdict for verdict in result.verdicts if verdict.kind == kind]
    assert matching, f"no {kind!r} verdict in {[verdict.kind for verdict in result.verdicts]}"
    return matching[0].status, matching[0].message


def test_the_recorded_index_holds_both_versions() -> None:
    """Anti-vacuity, first half: the index is not empty, and it holds exactly the two wheels.

    Without this the whole file could pass against an index containing nothing at all — every
    resolution would fail, both arms would come out UNVERIFIED, and the "the verdicts differ"
    assertion would be the only thing standing between that and a green run. Asserted here on
    the committed bytes, before any verdict is looked at.
    """
    wheels = sorted(path.name for path in INDEX.glob("*.whl"))
    assert wheels == [
        f"whetstone_fixture_dep-{_PINNED_VERSION}-py3-none-any.whl",
        f"whetstone_fixture_dep-{_UNPINNED_VERSION}-py3-none-any.whl",
    ], f"{INDEX} does not hold the two recorded versions; it holds {wheels}"


def test_the_scaffolding_cannot_supply_the_subject() -> None:
    """Nothing outside the recorded index can answer for ``whetstone-fixture-dep``.

    The arms below resolve the subject with ``--offline --no-index --no-cache --find-links
    <index>``, which is already narrow. This closes the question from the other side, on the two
    places a copy could plausibly sit and be inherited rather than resolved:

    - the **environment this suite runs in**. Provisioning the runner necessarily widens what a
      throwaway venv can reach — a wheelhouse it may resolve from, and, were a venv ever built
      with ``--system-site-packages``, an outer ``site-packages`` it could import from outright.
      That widening must not be able to supply the thing under study, so the outer environment
      is asserted not to carry it at all;
    - the **runner wheelhouse**, which is on ``UV_FIND_LINKS`` for every ``uv`` command in the
      session. ``tests/test_runner_wheelhouse.py`` asserts the two directories share no
      distribution; this states the half that matters here by name.

    Neither is hypothetical bookkeeping. If either could answer, ``resolved_version`` would be
    reporting whatever was inherited, and "the pin decided the verdict" would be a claim about
    this machine.
    """
    with pytest.raises(PackageNotFoundError):
        distribution_version(FIXTURE_DEP)

    assert not list(WHEELHOUSE.glob(f"{FIXTURE_DEP.replace('-', '_')}-*.whl")), (
        f"{WHEELHOUSE} carries a {FIXTURE_DEP} wheel. It is on UV_FIND_LINKS for the whole "
        f"session, so the versions under study would have a second source and the two arms "
        f"below could resolve from it"
    )


def test_the_two_recorded_versions_really_differ_in_the_keyword(
    arms: tuple[Arm, Arm],
) -> None:
    """Anti-vacuity, second half: the two wheels differ in the way the claim needs.

    "Two versions are installed" is not the claim; "the declared tests break under one of them"
    is. So the API difference is exercised directly, in each provisioned environment, before any
    verdict is read: 1.0.0 accepts ``loud=`` and 2.0.0 raises. If a future rebuild of the index
    ever made the two wheels identical, this fires here rather than making the verdict test
    quietly unfalsifiable.
    """
    pinned, unpinned = arms

    assert _python(pinned.interpreter, _KEYWORD_PROBE) == "accepted", (
        f"{_PINNED_VERSION} was expected to accept loud=; the recorded wheel does not, so the "
        f"pinned arm proves nothing"
    )
    assert _python(unpinned.interpreter, _KEYWORD_PROBE) == "TypeError", (
        f"{_UNPINNED_VERSION} was expected to reject loud=; the recorded wheel accepts it, so "
        f"the unpinned arm would pass for the wrong reason"
    )


def test_the_resolution_never_reached_the_network(arms: tuple[Arm, Arm]) -> None:
    """The offline claim, read off the argv that actually ran.

    A comment saying "this is offline" is not a guarantee; a flag in the invoked command is.
    Both arms are checked, because it is the *unpinned* one that would otherwise be tempted to
    ask an index for "the latest".
    """
    for arm in arms:
        assert "--offline" in arm.install_argv, (
            f"the {arm.requirement!r} resolution was not offline: {arm.install_argv}. A pins "
            f"test whose result depends on what an index served that morning refutes itself"
        )
        assert "--no-index" in arm.install_argv, (
            f"the {arm.requirement!r} resolution did not remove the registry: "
            f"{arm.install_argv}"
        )
        assert "--find-links" in arm.install_argv and str(INDEX) in arm.install_argv, (
            f"the {arm.requirement!r} resolution did not point at the recorded index: "
            f"{arm.install_argv}"
        )


def test_the_recorded_index_is_the_only_place_a_package_can_come_from(tmp_path: Path) -> None:
    """The control for the flags above: they constrain resolution, they do not merely decorate it.

    ``--no-index --find-links`` could be present and still be satisfiable from somewhere else —
    a cache, a configured extra index. So a distribution that is *not* in the recorded index is
    installed the same way, and the install must fail. If it succeeds, the two arms above were
    resolving against something this test cannot see, and their versions were never guaranteed.

    **``pytest`` is a particularly sharp choice of absent distribution now, and deliberately
    kept.** It is not only unmistakably present on PyPI; it is also sitting in the committed
    wheelhouse that ``tests/conftest.py`` puts on ``UV_FIND_LINKS`` for this entire session. So
    this control additionally establishes the property the whole arrangement rests on — a
    ``--find-links`` spelled on the command line **replaces** that variable rather than adding
    to it — and it establishes it the only way worth having: by failing loudly the day it stops
    being true.
    """
    venv = tmp_path / "control"
    _uv(["venv", "--quiet", "--python", sys.executable, str(venv)])
    completed = subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(venv / "bin" / "python"),
            "--offline",
            "--no-index",
            "--no-cache",
            "--find-links",
            str(INDEX),
            # A distribution that is absent from the index and unmistakably present on PyPI,
            # so a resolution that leaked back to a registry would succeed rather than fail.
            "pytest",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0, (
        "a package absent from the recorded index installed anyway, so the resolutions in this "
        "file were not constrained to it and the versions they reported were not guaranteed"
    )


def test_the_two_tasks_differ_only_in_their_pins(arms: tuple[Arm, Arm]) -> None:
    """Two tasks, one difference — so "the same task" is a fact here, not a figure of speech.

    Every other field — the repository, the base commit, the declared node ids, the golden test
    blobs — is compared for equality, so when the verdicts diverge below there is exactly one
    input that could have caused it. Without this the file would be demonstrating that two
    different tasks reach two different verdicts, which is not news.
    """
    pinned, unpinned = arms

    assert pinned.task.environment.pins == (FIXTURE_DEP_PIN,)
    assert unpinned.task.environment.pins == ()
    assert (
        dataclasses.replace(unpinned.task, environment=pinned.task.environment) == pinned.task
    ), "the two tasks differ somewhere other than their pins, so the comparison is not clean"


def test_the_pinned_and_unpinned_resolutions_selected_different_versions(
    arms: tuple[Arm, Arm],
) -> None:
    """Anti-vacuity: the unbounded requirement really did pick up the later version.

    If the resolver had happened to choose 1.0.0 for the unpinned arm — a mirror of the index, a
    stray constraint file — both arms would run the same code and the verdict difference below
    could only come from somewhere this file does not control.
    """
    pinned, unpinned = arms

    assert pinned.requirement == FIXTURE_DEP_PIN
    assert unpinned.requirement == FIXTURE_DEP, (
        f"the unpinned arm resolved {unpinned.requirement!r}, which is not the unbounded "
        f"requirement the repository declares; it must carry no ceiling or there is no hole"
    )
    assert pinned.resolved_version == _PINNED_VERSION
    assert unpinned.resolved_version == _UNPINNED_VERSION, (
        f"the unbounded requirement {unpinned.requirement!r} resolved to "
        f"{unpinned.resolved_version}, not {_UNPINNED_VERSION}; the two arms are running the "
        f"same code and the verdicts below would not be about pins"
    )
    assert pinned.resolved_version != unpinned.resolved_version


def test_the_pins_decide_the_verdict(arms: tuple[Arm, Arm]) -> None:
    """**The criterion.** One task, one patch, one verifier, two resolutions, two verdicts.

    The patch is a genuine, complete fix — the same bytes in both arms. The pinned arm is paid
    for it. The unpinned arm is charged a FAIL for it, and nothing about the patch changed. That
    FAIL is the false FAIL flask-5063 produced, reproduced here from a committed index instead
    of from a calendar.

    The inequality is the assertion. PASS-and-FAIL is stated as well, because "they differ"
    would also be satisfied by a pair that is UNVERIFIED and PASS — a broken provisioning step
    rather than a demonstration.
    """
    pinned, unpinned = arms

    assert pinned.result.status is Status.PASS, (
        f"the task with its pins did not pass, so this file has nothing to compare: "
        f"{[(v.kind, v.status, v.message) for v in pinned.result.verdicts]}"
    )
    assert unpinned.result.status is Status.FAIL, (
        f"the task resolved without its pins did not fail: "
        f"{[(v.kind, v.status, v.message) for v in unpinned.result.verdicts]}"
    )
    assert pinned.result.status is not unpinned.result.status


def test_the_unpinned_failure_is_the_declared_tests_failing(arms: tuple[Arm, Arm]) -> None:
    """A rejection for the wrong reason is not a demonstration.

    An unresolvable import, a collection error, an empty run — each of those would also produce
    a not-PASS, and none of them would show a *reward* being corrupted. So the FAIL is pinned to
    the specific shape the flask incident had: pytest ran, it ran **exactly** the declared set,
    nothing was skipped, and the declared tests themselves reported failed.

    ``executed-set`` passing is the load-bearing half. It says the two arms collected the same
    tests, which is what rules out "the suite could not start" and leaves only "the tests ran
    and the answers changed".
    """
    unpinned = arms[1]

    assert _verdict_of(unpinned.result, "executed-set")[0] is Status.PASS, (
        "the unpinned run did not execute the declared set, so its FAIL is a collection "
        "problem rather than the declared tests failing"
    )
    assert _verdict_of(unpinned.result, "skipped")[0] is Status.PASS
    pytest_status, pytest_message = _verdict_of(unpinned.result, "pytest")
    assert pytest_status is Status.FAIL, (
        f"pytest did not reach a conclusion in the unpinned run ({pytest_message}); an "
        f"UNVERIFIED here would mean the harness broke, not that the reward was corrupted"
    )

    fail_to_pass_status, fail_to_pass_message = _verdict_of(unpinned.result, "fail-to-pass")
    assert fail_to_pass_status is Status.FAIL
    assert unpinned.task.fail_to_pass[0] in fail_to_pass_message, (
        f"the grounding does not name the failing declared test: {fail_to_pass_message}"
    )

    # And the `pass_to_pass` half, which no verdict names on its own — flask-5063's four
    # casualties were all pass_to_pass, so it is the half most worth showing explicitly.
    outcomes = {case.node_id: case.outcome for case in read_report(unpinned.report)}
    assert outcomes[unpinned.task.pass_to_pass[0]] == "failed", (
        f"the pass-to-pass test did not fail under the unpinned resolution ({outcomes}), so "
        f"the shape being demonstrated is not the one flask-5063 had"
    )
    assert outcomes[unpinned.task.fail_to_pass[0]] == "failed"


def test_the_pinned_run_is_clean_all_the_way_down(arms: tuple[Arm, Arm]) -> None:
    """The other side of the control: the pinned arm is not passing by an accident of absence.

    Every sub-check PASSes, and pytest reports both declared tests as ``passed``. A pinned arm
    that reached PASS by running nothing would satisfy ``test_the_pins_decide_the_verdict`` just
    as well and would mean the opposite of what it says.
    """
    pinned = arms[0]

    assert [verdict.status for verdict in pinned.result.verdicts] == [Status.PASS] * len(
        pinned.result.verdicts
    ), f"{[(v.kind, v.status) for v in pinned.result.verdicts]}"
    assert pinned.result.executed == (
        *pinned.task.fail_to_pass,
        *pinned.task.pass_to_pass,
    )
    outcomes = {case.node_id: case.outcome for case in read_report(pinned.report)}
    assert set(outcomes.values()) == {"passed"}, outcomes
