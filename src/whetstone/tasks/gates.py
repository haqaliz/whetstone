"""The four eligibility gates, and the ledger of everything they turned away.

**The filter is the deliverable, not the instances.** Source A is far narrower than the roadmap
assumed — measured over the real 300 rows of SWE-bench-Lite, 192 are not addressable as pytest
node ids at all, 61 need a compiled scientific stack, 12 carry node ids SWE-bench itself has
corrupted, and 11 sit in an interpreter era that is verified dead on anything modern. What
survives is a ceiling of 24, of which one is proven end to end. A corpus that small is only worth
publishing if the *reason* each instance is in or out is proven per instance rather than assumed,
and that is what this module does.

**Each gate proves. None assumes.**

1. **Format** — every declared id parses as a pytest node id. This is the one gate that is a pure
   string question, and it is deliberately narrow: it kills django's unittest-runner form and
   sympy's bare names, and it lets SWE-bench's 12 truncated parametrised ids **through**. A
   bracket-balance rule would catch those and would be a guess wearing a gate's clothes; the only
   assumption-free detector is asking pytest to find them.
2. **Collectability** — every id is collectable in the **real checkout**. This is where the
   truncated ids die, by execution rather than by pattern. It matters more than it sounds: an
   unfindable id makes pytest exit 4, which `strict.py` maps to UNVERIFIED, and an UNVERIFIED
   aborts the whole run rather than grading anything.
3. **Environment** — the pinned set resolves **and imports** on the nominated interpreter.
   **Install-exit-0 is not evidence**, and that is measured rather than feared: `sphinx==3.5.4`,
   `pytest==4.6.9`, `pylint==2.13.9` and `requests==2.4.0` all install cleanly on arm64 CPython
   3.12, and two of them cannot be imported there. It is the same false green the CI `mlx` step
   already guards against.
4. **Liveness** — the two-run FAIL-then-PASS proof, which is `liveness.prove_live` unchanged. A
   second implementation of that check would be a second definition of what a task is.

**The gates are numbered in the order the PRD defines them and executed in a different order,
which is stated here rather than left for a reader to discover.** Proving an id collectable *in
the real checkout* requires the checkout to be importable, and that is gate 3's answer. Run
before it, gate 2 would report every instance uncollectable for a reason that has nothing to do
with its ids — an assumption dressed as a proof, which is exactly what these gates exist to
refuse. So the execution order is format, environment, collectability, liveness, and the ledger
records the gate that decided, never the position it ran in.

**Era-pins are not derivable, and are therefore not guessed.** A repository declares ranges —
flask says `click>=8.0` at every commit it has ever had — so `environment_setup_commit` cannot
answer which versions the era used. Source B escapes this because a donor's `uv.lock` is its
owner's own recorded resolution; source A has no such artifact. The pins come from a committed,
hand-determined table, and an instance with no entry is **rejected at gate 3 and ledgered**,
never resolved on the day the filter happened to run.

**Nothing vanishes.** Every refusal is a `Rejection` carrying the gate that made it, and
`write_ineligible` refuses to write a ledger whose counts do not account for every input. That
arithmetic is what makes "24 of 300 were eligible" evidence rather than a claim.

**Where the network is, stated plainly.** Gates 2 and 4 execute inside the Seatbelt sandbox,
which denies the network outright. Gate 3 **may reach an index**, because an era-pinned
environment cannot be provisioned out of nothing the first time it is built, and the checkout the
gates run against is cloned from GitHub. That is why the whole filter — like the fetch — is a
**human-run step whose output is committed**, and why what every later verification runs from is
the exact pin set the gate recorded, not a resolution repeated on the night. No test in this
suite runs the filter: the tests resolve from a committed local index with `--no-index
--find-links`, or hand the gate an installer that does nothing at all.

Zero runtime dependencies. No model anywhere.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# Imported rather than restated, on the same principle as `environment` importing `_PIN` from the
# loader and `derive` importing the reward's pytest flags: these are the predicate and the
# provisioning front door that already exist, and a second spelling of either would be a second
# thing to keep in step — with the drifted one discovered a whole filter run later.
from whetstone.tasks.environment import (
    NotProvisionable as _NotProvisionable,
)
from whetstone.tasks.environment import (
    _uv,
    pins_from_freeze,
)
from whetstone.verify.sandbox import run_confined
from whetstone.verify.strict import _PYTEST_CONFIG
from whetstone.verify.task import _PIN
from whetstone.verify.verdict import Status

#: The four gates, named. The ledger's `gate` field is only meaningful against a closed set:
#: a typo'd value would silently create a fifth category nobody could count.
GATE_FORMAT = "format"
GATE_COLLECTABILITY = "collectability"
GATE_ENVIRONMENT = "environment"
GATE_LIVENESS = "liveness"
GATES = (GATE_FORMAT, GATE_COLLECTABILITY, GATE_ENVIRONMENT, GATE_LIVENESS)

#: The order the gates actually run in, recorded in the ledger so the discrepancy with the
#: numbering above is published rather than discovered. See the module docstring.
EXECUTION_ORDER = (GATE_FORMAT, GATE_ENVIRONMENT, GATE_COLLECTABILITY, GATE_LIVENESS)

#: Names the shape of the committed rejection ledger.
INELIGIBLE_SCHEMA = "whetstone-source-a-ineligible/1"

#: The separator that makes a string addressable by pytest at all. Everything before the first
#: one is a file path; everything after is a chain of classes and a test name.
_SEPARATOR = "::"

#: A python module pytest can import. Checked rather than assumed because sympy's declarations
#: name no file at all and django's name a dotted module, and neither is a path.
_SUFFIX = ".py"

#: Leading or trailing whitespace on a declared id. Rejected rather than stripped, exactly as
#: `task._check_blob_path` refuses to normalise a path on the operator's behalf: an id the
#: manifest carries is compared literally against what pytest reports.
_UNTRIMMED = re.compile(r"^\s|\s$")


class Ineligible(ValueError):
    """One instance did not clear a gate, and the gate is part of the exception.

    The gate is carried on the exception rather than parsed back out of the message, because the
    ledger records it as a field and a message is prose. A rejection whose gate a reader has to
    infer is a rejection they cannot count.
    """

    def __init__(self, gate: str, message: str) -> None:
        if gate not in GATES:
            raise ValueError(f"unknown gate {gate!r}; the gates are {list(GATES)}")
        super().__init__(message)
        self.gate = gate


@dataclass(frozen=True)
class Rejection:
    """One instance the filter turned away, and the gate that turned it away.

    Frozen and validated in `__post_init__` so a rejection cannot be constructed under a gate
    name that exists nowhere else — the same fail-closed posture `load_task` takes towards an
    unknown field.
    """

    instance_id: str
    gate: str
    reason: str

    def __post_init__(self) -> None:
        if self.gate not in GATES:
            raise ValueError(f"unknown gate {self.gate!r}; the gates are {list(GATES)}")


@dataclass(frozen=True)
class Ineligibility:
    """The rejection ledger as read back: the counts, and every refusal behind them."""

    counts: Mapping[str, int]
    rejections: tuple[Rejection, ...]


def check_format(node_ids: Sequence[str]) -> None:
    """Gate 1. Every declared id must parse as a pytest node id, or `Ineligible`.

    **What this gate is for.** django declares its tests in the form its own unittest runner
    prints — `test_ticket_11293 (queries.tests.Queries1Tests)` — and sympy declares bare function
    names with no file path at all. Between them that is 192 of Lite's 300 instances. Neither is
    a node id, and neither becomes one by parsing harder: addressing them would mean a second
    execution path with its own adversarial-corpus obligation, which is out of scope by name.

    **What this gate deliberately is not for.** SWE-bench itself carries 12 parametrised ids
    split on whitespace, of the shape
    `tests/test_cli.py::test_locate_app[cliapp.factory-create_app2("foo",`. A bracket-balance
    rule would reject them here and would look like a stronger gate. It would be a string
    heuristic standing in for a proof — and the day the corruption takes another shape, it passes
    silently. Those ids leave here intact and die at gate 2, where pytest is asked to find them.

    Every offending id is reported, not just the first: a rejection naming one of three makes a
    three-line problem look like a one-line one.
    """
    if not node_ids:
        raise Ineligible(
            GATE_FORMAT,
            "the instance declares no tests at all. Every id check would pass vacuously — there "
            "is nothing to check — and the resulting task would have nothing that must go green",
        )

    offenders = [(node_id, reason) for node_id in node_ids if (reason := _malformed(node_id))]
    if offenders:
        detail = "; ".join(f"{node_id!r} ({reason})" for node_id, reason in offenders)
        raise Ineligible(
            GATE_FORMAT,
            f"{len(offenders)} of {len(node_ids)} declared test(s) are not addressable as pytest "
            f"node ids: {detail}. An id pytest cannot address is not a test this reward can be "
            f"grounded on, and there is no parse that turns one into one",
        )


def _malformed(node_id: str) -> str | None:
    """Why this id is not a pytest node id, or `None` if it is one.

    Returns the reason rather than a boolean so the rejection can say which of six problems it
    hit. A gate that reports "malformed" gets "fixed" by whatever silences it.
    """
    if not node_id:
        return "empty"
    if _UNTRIMMED.search(node_id):
        return "leading or trailing whitespace, which is not stripped on the caller's behalf"
    if _SEPARATOR not in node_id:
        return (
            "no '::' separator — this is django's unittest-runner form or a bare sympy test "
            "name, neither of which names a file pytest can address"
        )

    file_part, _, remainder = node_id.partition(_SEPARATOR)
    if not file_part.endswith(_SUFFIX):
        return f"the part before '::' is not a {_SUFFIX} file"

    pure = PurePosixPath(file_part)
    if pure.is_absolute() or file_part.startswith("/"):
        return "an absolute path, which names a checkout other than the one under test"
    if ".." in pure.parts:
        return "a path escaping the repository under test"
    if str(pure) != file_part:
        return f"a non-canonical path; write it as {str(pure)!r}"

    if not remainder or any(not part for part in remainder.split(_SEPARATOR)):
        return "an empty component after '::', which addresses nothing"
    return None


# --------------------------------------------------------------------------------------
# Gate 2 — the ids are collectable in the real checkout
# --------------------------------------------------------------------------------------

#: The config file the collection run is given, written into the workspace. Named separately from
#: `derive`'s so two runs sharing a workspace cannot overwrite each other's.
_COLLECT_CONFIG_NAME = "whetstone-collect.ini"

#: pytest's exit status for "you gave me something I cannot address". It is the one that matters
#: here: `strict.py` maps it to UNVERIFIED, and an UNVERIFIED aborts the run rather than grading
#: it, so a single unfindable id costs the verdict of everything the run was reducing.
_USAGE_ERROR = 4


def check_collectable(
    node_ids: Sequence[str],
    *,
    checkout: Path,
    workspace: Path,
    timeout: float,
    interpreter: Path | str | None = None,
    import_roots: Sequence[str] = (),
) -> tuple[str, ...]:
    """Gate 2. Ask pytest to find exactly these ids in `checkout`, and compare what it found.

    **Two failures, and only one of them announces itself.**

    The loud one is an id pytest cannot address — SWE-bench's own 12 whitespace-split
    parametrised ids, and any instance whose declared file the base commit does not carry. pytest
    exits `4`, and that exit is the evidence. Nothing here counts brackets or matches patterns: if
    the dataset's corruption ever takes a different shape, this still catches it and a string rule
    would not.

    The quiet one is an id that collects into **more than one**. A parametrised id declared bare
    — `test_p` rather than `test_p[1]` — expands, so the executed set never equals the declared
    set and STRICT answers FAIL for every patch forever, with nothing in the verdict pointing at
    the manifest. Exit code 0 is therefore a precondition and the set comparison is the gate.

    Returns the collected ids, so a caller can see what was found rather than assume it — and so
    the anti-vacuity control has something to assert against.

    The flags mirror `derive._run` and `strict._run_and_judge`, with `_PYTEST_CONFIG` and the
    rootdir handling **imported** rather than restated: ids collected under a different
    configuration than the reward runs under can differ in exactly the ways `node_id` exists to
    prevent. `--collect-only` is right here and wrong in `derive` for the same reason — this gate
    asks what pytest *would* run, which is precisely the question, while a declaration has to be
    what pytest *did* run.
    """
    if not node_ids:
        raise Ineligible(
            GATE_COLLECTABILITY,
            "the instance declares no tests, so there is nothing to collect. Handing pytest no "
            "ids would collect the whole suite, which answers a different question",
        )

    root = Path(checkout).resolve()
    scope = Path(workspace)
    scope.mkdir(parents=True, exist_ok=True)
    scope = scope.resolve()

    config = scope / _COLLECT_CONFIG_NAME
    config.write_text(_PYTEST_CONFIG)

    sandbox = run_confined(
        [
            str(interpreter) if interpreter else _current(),
            "-m",
            "pytest",
            "-c",
            str(config),
            "--rootdir",
            str(root),
            "-p",
            "no:cacheprovider",
            "-q",
            "--collect-only",
            *node_ids,
        ],
        scope=scope,
        timeout=timeout,
        cwd=root,
        python_path=tuple(str((root / entry).resolve()) for entry in import_roots),
    )
    output = sandbox.stdout.decode(errors="replace")
    errors = sandbox.stderr.decode(errors="replace")

    if sandbox.verdict.status is not Status.PASS:
        raise Ineligible(
            GATE_COLLECTABILITY,
            f"the collection run did not complete: {sandbox.verdict.message}",
        )
    if sandbox.rc != 0:
        raise Ineligible(
            GATE_COLLECTABILITY,
            f"pytest exited {sandbox.rc} collecting {list(node_ids)} in the real checkout"
            + (
                " — it could not address at least one of them. That exit is mapped to UNVERIFIED "
                "by strict.py, and an UNVERIFIED aborts the whole run rather than grading it, so "
                "one such instance costs the verdict of everything the run was reducing"
                if sandbox.rc == _USAGE_ERROR
                else ""
            )
            + f". pytest said: {(errors or output).strip()[:600]}",
        )

    collected = _collected(output)
    if not collected:
        raise Ineligible(
            GATE_COLLECTABILITY,
            f"pytest exited 0 collecting {list(node_ids)} but reported no node ids at all, so "
            f"there is no evidence the declared tests are there. Output: {output.strip()[:600]}",
        )

    missing = sorted(set(node_ids) - set(collected))
    extra = sorted(set(collected) - set(node_ids))
    if missing or extra:
        raise Ineligible(
            GATE_COLLECTABILITY,
            f"collecting {list(node_ids)} did not produce that set: {missing} were not collected "
            f"and {extra} were collected but not declared. An id that expands — a parametrised "
            f"test declared bare — makes the executed set differ from the declared set on every "
            f"run, so STRICT answers FAIL for every patch forever with nothing in the verdict "
            f"pointing at the manifest",
        )
    return collected


def _collected(output: str) -> tuple[str, ...]:
    """The node ids `--collect-only -q` listed, and nothing else it printed.

    Read as "every line that is itself a node id" rather than "every line before the first blank
    one". The blank-line rule is the shape the output happens to have today; this one is a
    statement about what a collected id looks like, and it survives a warning or a plugin banner
    landing in the middle of the listing.
    """
    return tuple(
        line
        for raw in output.splitlines()
        if (line := raw.rstrip()) and not _malformed(line)
    )


# --------------------------------------------------------------------------------------
# Gate 3 — the environment resolves AND imports
# --------------------------------------------------------------------------------------

#: Names the shape of the committed, hand-determined era-pin table.
ERA_PINS_SCHEMA = "whetstone-source-a-era-pins/1"

#: Where uv puts a venv's interpreter. macOS/Linux, which is where the reward runs at all.
_INTERPRETER = ("bin", "python")

#: Asked of the provisioned interpreter itself, never of the process doing the filtering: the
#: manifest's `environment.python` is a claim about the interpreter the tests will run under.
_VERSION_PROBE = "import platform; print(platform.python_version())"

#: Long enough for a cold venv on a slow disk, short enough that a wedged uv is an error.
_PROBE_TIMEOUT = 900.0

#: The import probe, run **inside** the provisioned interpreter. It derives each distribution's
#: top-level modules from that distribution's own metadata rather than from a name table: the
#: mapping from `Jinja2` to `jinja2` and from `MarkupSafe` to `markupsafe` is not guessable, and
#: a guess here would silently check nothing for exactly the packages most likely to break.
#:
#: `top_level.txt` first, because setuptools writes it and it is unambiguous. Otherwise the
#: installed file list, with the metadata and data directories skipped — everything left whose
#: first path component is an identifier is something an importer could be asked for.
_IMPORT_PROBE = """
import importlib
import json
import sys
from importlib import metadata

checked = []
failures = []
for dist in metadata.distributions():
    try:
        name = dist.metadata["Name"]
    except Exception:
        continue
    if not name:
        continue
    declared = (dist.read_text("top_level.txt") or "").split()
    if not declared:
        tops = set()
        for entry in dist.files or ():
            head = entry.parts[0]
            if head.endswith((".dist-info", ".egg-info", ".data")) or head == "__pycache__":
                continue
            if len(entry.parts) == 1:
                if head.endswith(".py"):
                    tops.add(head[:-3])
            else:
                tops.add(head)
        declared = sorted(tops)
    for module in sorted({m for m in declared if m.isidentifier()}):
        checked.append(module)
        try:
            importlib.import_module(module)
        except BaseException as exc:
            failures.append(
                {"module": module, "distribution": name, "error": f"{type(exc).__name__}: {exc}"}
            )
print(json.dumps({"checked": sorted(set(checked)), "failures": failures}))
"""

#: What `check_environment` is handed to do the installing. Injected so the false-green arm can
#: pass an installer that trivially succeeds — which is the strongest possible statement of
#: "install exited 0" and the only way to assert that exit 0 alone does not pass this gate.
Installer = Callable[[list[str], Path], None]


@dataclass(frozen=True)
class ImportFailure:
    """One module that could not be imported in the provisioned interpreter."""

    module: str
    distribution: str
    error: str


@dataclass(frozen=True)
class ImportProbe:
    """What the probe found. A measurement, not a verdict.

    `checked` is carried as well as `failures` because a probe that imported nothing would report
    no failures and look like a pass. The anti-vacuity control in
    `tests/test_public_environment_gate.py` asserts against this field, and it is the reason the
    probe returns rather than raising.
    """

    checked: tuple[str, ...]
    failures: tuple[ImportFailure, ...]


@dataclass(frozen=True)
class EraPins:
    """One instance's hand-determined install set, and how it was determined.

    `determined_by` is required rather than optional. The difference between "found by hand, one
    incident at a time" and "whatever the resolver returned" is the difference between a pinned
    corpus and a pinned-looking one, and only the first is worth committing.
    """

    python: str
    requirements: tuple[str, ...]
    determined_by: str


@dataclass(frozen=True)
class Provisioned:
    """The environment gate 3 proved, in the shape the manifest carries.

    `pins` is read from the freeze rather than echoed back from the requirements: what a task
    must declare is the environment its tests actually ran in, transitive dependencies included.
    Echoing the request would describe a smaller environment than the one that was measured.
    """

    python: str
    pins: tuple[str, ...]
    interpreter: Path


def read_era_pins(path: Path) -> Mapping[str, EraPins]:
    """Read the committed era-pin table, validating every requirement against the loader.

    Validated here rather than at manifest time because a range in the table would fail one
    instance at a time, a whole filter run later, with a message about a manifest rather than
    about the table that produced it.
    """
    location = Path(path)
    try:
        raw = json.loads(location.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"era-pin table {str(location)!r} could not be read: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema") != ERA_PINS_SCHEMA:
        raise ValueError(
            f"era-pin table {str(location)!r} is not one: expected an object whose schema is "
            f"{ERA_PINS_SCHEMA!r}"
        )
    instances = raw.get("instances")
    if not isinstance(instances, dict):
        raise ValueError(f"era-pin table {str(location)!r} carries no 'instances' object")

    table: dict[str, EraPins] = {}
    for instance_id, entry in instances.items():
        if not isinstance(entry, dict):
            raise ValueError(f"era-pin table {str(location)!r} has a malformed {instance_id!r}")
        requirements = entry.get("requirements")
        if not isinstance(requirements, list) or not requirements:
            raise ValueError(
                f"era-pin table {str(location)!r} records no requirements for {instance_id!r}"
            )
        for requirement in requirements:
            if not isinstance(requirement, str) or not _PIN.match(requirement):
                raise ValueError(
                    f"era-pin table {str(location)!r} records {requirement!r} for "
                    f"{instance_id!r}, which is not an exact '==' requirement. A range here "
                    f"reopens the hole the table exists to close: the version, and with it the "
                    f"verdict, goes back to whatever the index serves at resolution time"
                )
        table[instance_id] = EraPins(
            python=str(entry.get("python") or ""),
            requirements=tuple(requirements),
            determined_by=str(entry.get("determined_by") or ""),
        )
    return table


def era_pins(table: Mapping[str, EraPins], instance_id: str) -> EraPins:
    """This instance's install set, or `Ineligible` at gate 3.

    **The refusal is the honest branch, and it is the common one.** A repository declares ranges
    — flask says `click>=8.0` at every commit it has ever had — so `environment_setup_commit`
    cannot answer which versions the era used. Source B escapes this because a donor's `uv.lock`
    is its owner's own recorded resolution, made when the commit was written; source A has no
    such artifact anywhere. Resolving anyway would hand the verdict to whatever the index served
    that morning. So an instance with no entry is rejected and ledgered, never guessed at.
    """
    pins = table.get(instance_id)
    if pins is None:
        raise Ineligible(
            GATE_ENVIRONMENT,
            f"no era-pins are recorded for {instance_id!r}. Its repository declares ranges, so "
            f"nothing in the dataset or in the checkout answers which versions its era used, and "
            f"resolving them at filter time would decide the verdict by the calendar. Determine "
            f"them by hand, add them to tasks/public/era-pins.json with how they were "
            f"determined, and re-run — the instance is refused rather than guessed at",
        )
    return pins


def probe_imports(interpreter: Path) -> ImportProbe:
    """Import every installed distribution's top-level modules, inside `interpreter`.

    Returns rather than raises, because this is a measurement and the gate is what turns it into
    a refusal. A probe that raised would make "and what *did* you check" unanswerable in exactly
    the failing case where it matters.
    """
    completed = subprocess.run(
        [str(interpreter), "-c", _IMPORT_PROBE],
        capture_output=True,
        text=True,
        timeout=_PROBE_TIMEOUT,
        check=False,
    )
    if completed.returncode != 0:
        raise Ineligible(
            GATE_ENVIRONMENT,
            f"the provisioned interpreter {str(interpreter)!r} could not run the import probe "
            f"at all: {completed.stderr.strip() or completed.stdout.strip()}",
        )
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise Ineligible(
            GATE_ENVIRONMENT,
            f"the import probe produced no readable result in {str(interpreter)!r}: {exc}",
        ) from exc

    return ImportProbe(
        checked=tuple(payload.get("checked") or ()),
        failures=tuple(
            ImportFailure(
                module=str(entry["module"]),
                distribution=str(entry["distribution"]),
                error=str(entry["error"]),
            )
            for entry in payload.get("failures") or ()
        ),
    )


def check_environment(
    requirements: Sequence[str],
    *,
    venv: Path,
    python: Path | str | None = None,
    index: Path | None = None,
    install: Installer | None = None,
) -> Provisioned:
    """Gate 3. Provision `requirements` into `venv`, then prove the result **imports**.

    **Install-exit-0 is not evidence, and that is measured rather than feared.**
    `sphinx==3.5.4`, `pytest==4.6.9`, `pylint==2.13.9` and `requests==2.4.0` all install cleanly
    on arm64 CPython 3.12; two of them cannot be imported there. An environment that admitted
    them would hand the corpus tasks that die at collection, reported as ordinary rejections with
    nothing pointing at the interpreter. So the installer's exit code is a precondition and the
    import probe is the gate.

    `install` is injected so the false-green arm can pass an installer that trivially succeeds —
    the strongest possible "exit 0" — and watch the gate reject anyway. Production passes `None`
    and gets uv.

    `index` makes a local directory the only place a distribution may come from
    (`--no-index --find-links`), which is how the suite resolves a real dependency without a
    network. Production passes `None`, and **this is the one step of the filter that may reach an
    index**: era-pins cannot be provisioned from nothing the first time. That is why the filter is
    a human-run step alongside the fetch, and why its output — the exact pins in each manifest —
    is what every later verification runs from.
    """
    environment = Path(venv).resolve()
    interpreter = environment.joinpath(*_INTERPRETER)

    installer = install if install is not None else _uv_installer(python=python, index=index)
    try:
        installer(list(requirements), environment)
    except _NotProvisionable as exc:
        raise Ineligible(
            GATE_ENVIRONMENT,
            f"the era-pinned environment {list(requirements)} could not be provisioned: {exc}",
        ) from exc

    if not interpreter.is_file():
        raise Ineligible(
            GATE_ENVIRONMENT,
            f"provisioning reported success but left no interpreter at {str(interpreter)!r}, so "
            f"there is nothing to verify the instance under",
        )

    probe = probe_imports(interpreter)
    if probe.failures:
        detail = "; ".join(
            f"{failure.distribution} -> import {failure.module}: {failure.error}"
            for failure in probe.failures
        )
        raise Ineligible(
            GATE_ENVIRONMENT,
            f"the environment installed cleanly and {len(probe.failures)} of "
            f"{len(probe.checked)} checked module(s) cannot be imported on this interpreter: "
            f"{detail}. Install-exit-0 is not evidence — this is the interpreter-era failure "
            f"that kills requests==2.4.0 on >=3.10 and pytest==4.6.9 on 3.12",
        )

    try:
        pins, _ = pins_from_freeze(_uv(("pip", "freeze", "--python", str(interpreter))))
    except _NotProvisionable as exc:
        raise Ineligible(
            GATE_ENVIRONMENT, f"the provisioned environment cannot be described as pins: {exc}"
        ) from exc
    return Provisioned(python=_probe_version(interpreter), pins=pins, interpreter=interpreter)


def _uv_installer(*, python: Path | str | None, index: Path | None) -> Installer:
    """The production installer: `uv venv` then `uv pip install`, both against a local python.

    A closure rather than a method so the injected test double and the real thing have the same
    two-argument shape, and so nothing in `check_environment` has to branch on which it holds.
    """

    def install(requirements: list[str], environment: Path) -> None:
        # `--allow-existing` so the step is idempotent: a filter run that was interrupted after
        # the venv and before the install must be resumable, and a caller that made the venv
        # itself is exercising the same code path production does rather than a second one.
        _uv(
            (
                "venv",
                "--allow-existing",
                "--python",
                str(python) if python else _current(),
                str(environment),
            )
        )
        interpreter = environment.joinpath(*_INTERPRETER)
        constrained: tuple[str, ...] = ()
        if index is not None:
            constrained = ("--no-index", "--find-links", str(Path(index)), "--offline")
        _uv(
            (
                "pip",
                "install",
                "--quiet",
                "--python",
                str(interpreter),
                *constrained,
                *requirements,
            )
        )

    return install


def _current() -> str:
    """This process's own interpreter, named rather than imported at module scope.

    `sys` is only needed here, and keeping it local mirrors the discipline the rest of the
    package applies to imports that exist for one branch.
    """
    import sys

    return sys.executable


def _probe_version(interpreter: Path) -> str:
    """The interpreter's own version, asked of the interpreter."""
    completed = subprocess.run(
        [str(interpreter), "-c", _VERSION_PROBE],
        capture_output=True,
        text=True,
        timeout=_PROBE_TIMEOUT,
        check=False,
    )
    if completed.returncode != 0:
        raise Ineligible(
            GATE_ENVIRONMENT,
            f"the provisioned interpreter {str(interpreter)!r} could not report its own version: "
            f"{completed.stderr.strip()}",
        )
    return completed.stdout.strip()


# --------------------------------------------------------------------------------------
# The rejection ledger
# --------------------------------------------------------------------------------------


def write_ineligible(
    path: Path,
    rejections: Sequence[Rejection],
    *,
    eligible: Sequence[str],
    input_count: int,
) -> None:
    """Write the rejection ledger, refusing any ledger that does not account for every input.

    **The arithmetic is enforced here rather than reviewed.** The failure it prevents is
    invisible in a diff: a run that lost three instances between the draw and the gates writes a
    perfectly well-formed ledger describing a smaller world, and every rate computed over it is
    correct about the wrong denominator.

    Identity is checked as well as the totals, because the totals alone can be satisfied by an
    instance counted twice — one rejection that is also in the eligible set balances the sum
    while an input has still disappeared.
    """
    ineligible = [rejection.instance_id for rejection in rejections]
    overlap = sorted(set(ineligible) & set(eligible))
    if overlap:
        raise ValueError(
            f"{overlap} are recorded as both eligible and rejected. The counts would still add "
            f"up, and an input would still have vanished"
        )
    if len(ineligible) + len(eligible) != input_count:
        raise ValueError(
            f"the ledger does not account for every input: {len(eligible)} eligible plus "
            f"{len(ineligible)} rejected is not {input_count}. A silently dropped instance is a "
            f"denominator nobody chose, and the whole value of this file is that it has none"
        )

    document = {
        "schema": INELIGIBLE_SCHEMA,
        "gates": list(GATES),
        "execution_order": list(EXECUTION_ORDER),
        "counts": {
            "input": input_count,
            "eligible": len(eligible),
            "ineligible": len(ineligible),
            **{
                gate: sum(1 for rejection in rejections if rejection.gate == gate)
                for gate in GATES
            },
        },
        "eligible": sorted(eligible),
        "instances": [
            {
                "instance_id": rejection.instance_id,
                "gate": rejection.gate,
                "reason": rejection.reason,
            }
            for rejection in sorted(rejections, key=lambda rejection: rejection.instance_id)
        ],
    }
    location = Path(path)
    location.parent.mkdir(parents=True, exist_ok=True)
    location.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")


def read_ineligible(path: Path) -> Ineligibility:
    """Read the rejection ledger back, or raise `ValueError` naming the file."""
    location = Path(path)
    try:
        raw = json.loads(location.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"ledger {str(location)!r} could not be read: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema") != INELIGIBLE_SCHEMA:
        raise ValueError(
            f"ledger {str(location)!r} is not a source-A rejection ledger: expected an object "
            f"whose schema is {INELIGIBLE_SCHEMA!r}"
        )
    counts = raw.get("counts")
    instances = raw.get("instances")
    if not isinstance(counts, dict) or not isinstance(instances, list):
        raise ValueError(f"ledger {str(location)!r} carries no counts or no instances")

    try:
        rejections = tuple(
            Rejection(
                instance_id=str(entry["instance_id"]),
                gate=str(entry["gate"]),
                reason=str(entry["reason"]),
            )
            for entry in instances
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"ledger {str(location)!r} carries a malformed rejection: {exc}") from exc
    return Ineligibility(counts=dict(counts), rejections=rejections)


__all__ = [
    "ERA_PINS_SCHEMA",
    "EXECUTION_ORDER",
    "GATES",
    "GATE_COLLECTABILITY",
    "GATE_ENVIRONMENT",
    "GATE_FORMAT",
    "GATE_LIVENESS",
    "INELIGIBLE_SCHEMA",
    "EraPins",
    "ImportFailure",
    "ImportProbe",
    "Ineligibility",
    "Ineligible",
    "Installer",
    "Provisioned",
    "Rejection",
    "check_collectable",
    "check_environment",
    "check_format",
    "era_pins",
    "probe_imports",
    "read_era_pins",
    "read_ineligible",
    "write_ineligible",
]
