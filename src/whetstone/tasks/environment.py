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

**The donor's own project is deliberately NOT installed, and that is a correctness requirement
rather than a saving.** `uv sync --frozen` installs the project too, editable, rooted at
whatever checkout it was pointed at. For a `src`-layout donor that install answers `import
contig` — so every later run, in every other checkout, imports the *provisioning* tree. Measured
on the first real donor: a task PASSED with no patch applied, because the code deciding the
verdict was in a directory outside the run. `--no-install-project` is the fix at this end; the
matching half is `environment.import_roots`, which tells the reward where in the run's own
checkout the code is. The venv therefore carries **dependencies only**, and there is no copy of
the project anywhere for a verdict to leak into.

**Which is why this module also decides the import roots.** They are read from the donor's build
configuration, and a donor whose layout cannot be read is **rejected by name**. Guessing is not
available: a wrong import root does not fail loudly, it silently reintroduces the hole above.

**`tomllib` is imported inside the function that needs it, and that is not laziness for its own
sake.** It entered the stdlib in 3.11 while this package's `requires-python` is `>=3.10` — a
constraint `tests/test_packaging.py` records deliberately. A module-level import would make
`import whetstone.tasks.environment` fail outright on 3.10, and since the CLI reaches this module
through `mine`, it would take `whetstone verify` and `whetstone --version` down with it — a
supported interpreter silently dropped to add a parser. Scoped to the one function instead,
mining is **refused by name** on 3.10 while everything else keeps working, which is the same
direction every other refusal in this module fails in.

Zero runtime dependencies: `subprocess`, stdlib TOML and a parse. No model, no network, nothing
executed from the donor — the build configuration is read without running the backend.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

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

#: setuptools' declarative configuration, which is the only place many pre-2022 projects say
#: where their packages are. Read only when `pyproject.toml` does not answer.
SETUP_CFG = "setup.cfg"

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

#: The conventional directory a `src`-layout project keeps its packages in. Named because its
#: mere presence is what makes a silent build backend ambiguous rather than merely quiet.
_SRC = "src"

#: How a distribution name becomes the module it is imported as, for `_observed_root`. Only the
#: separators PEP 503 normalises; anything else in a name is left alone, because a rewrite this
#: function got wrong would answer an import with the wrong directory.
_NAME_TO_MODULE = re.compile(r"[-_.]+")

#: The import root of a project whose code sits at the repository root. `"."` rather than `""`
#: because the manifest requires a canonical relative path, and `""` is not one.
_ROOT = "."


class NotProvisionable(ValueError):
    """This donor cannot be provisioned into an environment a task could declare.

    Raised rather than returning a partial capture, because "the environment is empty" and "the
    environment could not be read" are different facts and only the first belongs in a manifest.
    """


class NoLockfile(NotProvisionable):
    """The donor carries no `uv.lock`, so nothing has answered what its requirements left open."""


class UnknownImportRoot(NotProvisionable):
    """The donor's layout could not be read, so where its code lives is not known.

    Its own class because the remedy is different from every other refusal here: a missing lock
    is fixed by locking the donor, while this is fixed by the donor's build configuration saying
    where its packages are. Both are refusals rather than guesses, and this one especially — a
    wrong import root produces a task that verifies against code outside the run and reports
    PASS for it, which is the one failure mode that does not announce itself.
    """


@dataclass(frozen=True)
class Captured:
    """One provisioned environment, and the evidence for how it was obtained.

    `pins` is what goes into the manifest. `local` carries the path installs that are not pins.
    It should now always be empty — the project itself is the only thing that was ever installed
    from a path, and `--no-install-project` means it no longer is — but the field and its parsing
    stay, because "no path install was reported" is a fact worth being able to **assert** rather
    than one to assume from a flag. `test_the_donor_project_is_never_installed…` is what asserts
    it. A path install cannot be served differently by an index, so it cannot move a verdict by
    *version*; what it can do is answer an import, which is exactly the hole this module's
    docstring records.

    `import_roots` is where the code under test lives inside the checkout, read from the donor's
    build configuration and written straight into the manifest's `environment`.

    `installs` is every command that could have fetched anything, kept so the offline claim can
    be asserted from what actually ran rather than from this docstring.
    """

    python: str
    pins: tuple[str, ...]
    local: tuple[str, ...]
    import_roots: tuple[str, ...]
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

    Raises `NoLockfile` if the donor was never locked, `UnknownImportRoot` if its layout cannot
    be read, and `NotProvisionable` if uv failed or if the resulting environment cannot be
    described as exact pins.
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

    # Read before anything is provisioned: a donor whose layout cannot be read is refused for the
    # price of one file read rather than after a whole venv has been built.
    roots = import_roots(location)

    environment = venv.resolve()
    sync = (
        "sync",
        "--frozen",
        "--no-progress",
        "--no-install-project",
        # DEPENDENCIES ONLY. Without this uv installs the donor's own project editable, rooted at
        # this checkout — and every later verification, in a different checkout, imports this one
        # instead of its own. See the module docstring; the observed symptom was a task that
        # passed with no patch applied.
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
        import_roots=roots,
        interpreter=interpreter,
        installs=(sync, runner),
    )


def import_roots(project: Path) -> tuple[str, ...]:
    """Where a donor keeps the code its tests import, relative to the repository root.

    The manifest's `environment.import_roots`, and the reason the reward can be sure it is
    grading the checkout the patch was applied to. Reading it is a parse of `pyproject.toml`,
    never a build: the backend is not invoked, so nothing from the donor executes.

    **The decision, in order, and every branch is a refusal or a fact:**

    1. the build configuration says where its packages are — hatchling's `packages`, setuptools'
       `package-dir` or `packages.find.where`. That is the answer, and each named directory must
       actually be in the checkout or the donor is refused: a root that is not there is a
       manifest that would put a non-existent directory on the import path and change nothing;
    2. otherwise, the project is not built as a package at all (`[tool.uv] package = false`, or
       no `[build-system]`), so nothing was ever installed under a package name and its code is
       imported from the repository root. `["."]`;
    3. otherwise it **is** a package and its backend did not say. If there is a `src/` directory
       the layout is genuinely ambiguous — a backend's auto-discovery could mean either — and the
       donor is **refused**. This is the branch that exists to be a refusal: a guess of `["."]`
       for a `src` project leaves the tests importing whatever is installed, which is precisely
       the defect this field was added to close, and it fails *silently* by passing;
    4. otherwise there is no `src/` and the code is at the root. `["."]`.

    Refusal is `UnknownImportRoot`, which the miner records as a rejected candidate and moves on
    from. Losing a donor is cheap; minting one whose verdicts come from somewhere else is not.
    """
    location = Path(project)
    file = location / PROJECT_FILE
    data = _read_project_file(file, where=str(location)) if file.is_file() else {}

    declared = _declared_roots(data) or _setup_cfg_roots(location)
    if declared is None and not file.is_file():
        raise UnknownImportRoot(
            f"donor {str(location)!r} carries neither a {PROJECT_FILE} nor a {SETUP_CFG} that "
            f"declares its layout, so nothing says where the code its tests import lives. "
            f"Guessing would risk verifying against a copy of the project installed somewhere "
            f"else, which reports PASS for a patch nobody applied"
        )
    if declared is not None:
        for root in declared:
            if not (location / root).is_dir():
                raise UnknownImportRoot(
                    f"donor {str(location)!r} declares the import root {root!r}, which is not a "
                    f"directory in the checkout. An import root that is not there adds nothing "
                    f"to the path, so the tests would import whatever else can answer them"
                )
        return declared

    if not _is_packaged(data):
        return (_ROOT,)

    observed = _observed_root(location, data)
    if observed is not None:
        return observed

    if (location / _SRC).is_dir():
        raise UnknownImportRoot(
            f"donor {str(location)!r} is built as a package and has a {_SRC!r} directory, but "
            f"its build configuration does not say which directories hold its packages. The "
            f"layout is therefore ambiguous, and the wrong answer does not fail loudly — it "
            f"leaves the declared tests importing a copy of the project from outside the run "
            f"and reporting PASS. Declare it (for example hatchling's "
            f"[tool.hatch.build.targets.wheel] packages) and re-mint"
        )
    return (_ROOT,)


def _observed_root(location: Path, data: dict[str, object]) -> tuple[str, ...] | None:
    """Where the project's own declared name is actually laid out, or None if it is not.

    **This reads the layout; it does not guess at it.** A backend that discovers its package by
    convention — flit, and setuptools' automatic discovery — says nothing in the build table, so
    `_declared_roots` returns nothing and the caller is left with a genuinely ambiguous `src/`.
    But the ambiguity is only genuine when the layout does not answer: if `[project] name` is
    `Flask` and `src/flask/__init__.py` is a file in the checkout, then `src` **is** the import
    root, as a fact about the tree rather than as an inference about the backend.

    Both layouts are checked, `src/` first, and neither is invented: each requires an
    `__init__.py` to actually be there. When neither is, this returns None and the caller
    refuses — which is the branch that matters, because a wrong import root does not fail
    loudly, it leaves the declared tests importing a copy of the project from outside the run
    and reporting PASS.

    Added for source A, where a public benchmark instance is whatever upstream chose to build
    with, and shared with source B rather than duplicated: one project must not resolve to two
    different import roots depending on which ingester asked.
    """
    name = _table(data, "project").get("name")
    if not isinstance(name, str) or not name:
        return None
    module = _NAME_TO_MODULE.sub("_", name).lower()
    if (location / _SRC / module / "__init__.py").is_file():
        return (_SRC,)
    if (location / module / "__init__.py").is_file():
        return (_ROOT,)
    return None


def _read_project_file(file: Path, *, where: str) -> dict[str, object]:
    """Parse one `pyproject.toml`, with the stdlib TOML parser imported here and not at the top.

    `tomllib` is 3.11+ and this package supports 3.10 (`tests/test_packaging.py` records why).
    Importing it at module scope would make the whole module — and therefore the CLI that reaches
    it — unimportable on a supported interpreter, so a 3.10 operator would lose `whetstone verify`
    to a feature they were not using. Scoped here, they lose only mining, and they are told so by
    name rather than by a traceback.
    """
    try:
        import tomllib
    except ModuleNotFoundError as exc:  # pragma: no cover - only reachable on Python 3.10
        raise UnknownImportRoot(
            f"reading donor {where!r}'s layout needs the stdlib TOML parser, which is Python "
            f"3.11+; this interpreter is {sys.version.split()[0]}. Mining is refused rather than "
            f"guessing where the donor's code lives — the rest of whetstone is unaffected"
        ) from exc

    try:
        return tomllib.loads(file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise UnknownImportRoot(
            f"donor {where!r} has a {PROJECT_FILE} that could not be read: {exc}"
        ) from exc


def _declared_roots(data: dict[str, object]) -> tuple[str, ...] | None:
    """The import roots a build backend states outright, or None if none of them did.

    Only the spellings that name a **directory** are read. A backend that lists modules or
    globs is left to the caller's ambiguity branch rather than interpreted here: a half-understood
    declaration is worse than an unread one, because it produces an answer.
    """
    tool = _table(data, "tool")
    wheel = _table(_table(_table(_table(tool, "hatch"), "build"), "targets"), "wheel")
    packages = wheel.get("packages")
    if isinstance(packages, list):
        # `packages = ["src/contig"]` names the package; its PARENT is the import root.
        return _roots(
            str(PurePosixPath(entry).parent) for entry in packages if isinstance(entry, str)
        )

    setuptools = _table(tool, "setuptools")
    package_dir = setuptools.get("package-dir")
    if isinstance(package_dir, dict) and isinstance(package_dir.get(""), str):
        return _roots([package_dir[""]])
    where = _table(_table(setuptools, "packages"), "find").get("where")
    if isinstance(where, list):
        return _roots(entry for entry in where if isinstance(entry, str))
    return None


def _setup_cfg_roots(location: Path) -> tuple[str, ...] | None:
    """setuptools' declarative layout, read from `setup.cfg`, or None if it says nothing.

    **Added because a public benchmark instance is whatever upstream chose to build with, and
    often that predates `pyproject.toml` entirely.** `pallets__flask-4045` sits at a 2021 commit
    carrying `setup.py` and `setup.cfg` and nothing else, and its `[options] package_dir = = src`
    says exactly what the pyproject spelling would. Refusing it would be refusing a declaration
    for the file it happens to live in, which is not a fact about the layout.

    Read with the stdlib `configparser`: this is a parse, and the build backend is never invoked,
    so nothing from the repository under test executes. Only the two spellings that name a
    **directory** are read — `package_dir`'s root entry and `packages.find`'s `where` — for the
    same reason `_declared_roots` reads only those: a half-understood declaration is worse than
    an unread one, because it produces an answer.
    """
    file = location / SETUP_CFG
    if not file.is_file():
        return None

    import configparser

    parser = configparser.ConfigParser()
    try:
        parser.read_string(file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, configparser.Error) as exc:
        raise UnknownImportRoot(
            f"donor {str(location)!r} has a {SETUP_CFG} that could not be read: {exc}"
        ) from exc

    # `package_dir = \n    = src` is setuptools' spelling for "the root package lives in src".
    # Any other key names a single package's directory, which is not the import root.
    raw = parser.get("options", "package_dir", fallback="")
    roots: list[str] = []
    for line in raw.splitlines():
        key, separator, value = line.partition("=")
        if separator and not key.strip() and value.strip():
            roots.append(value.strip())
    if not roots:
        roots = [
            entry.strip()
            for entry in parser.get("options.packages.find", "where", fallback="").split()
            if entry.strip()
        ]
    return _roots(roots) if roots else None


def _is_packaged(data: dict[str, object]) -> bool:
    """Is this project built and installed under a package name at all?

    `[tool.uv] package = false` says outright that it is not, and is checked first because it
    overrides the presence of a build system. Otherwise a `[build-system]` table is what makes
    uv build and install it.
    """
    package = _table(_table(data, "tool"), "uv").get("package")
    if package is False:
        return False
    return "build-system" in data


def _table(data: dict[str, object], key: str) -> dict[str, object]:
    """One nested TOML table, or an empty one. Never a `KeyError`, never a wrong-typed value."""
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def _roots(candidates: Iterable[str]) -> tuple[str, ...]:
    """Normalise declared directories into canonical, deduplicated, order-preserving roots.

    `""` and `"./src"` are both spellings the loader refuses, so they are canonicalised here
    rather than written into a manifest that would then fail to load. Order is preserved because
    it is the order the interpreter will search; duplicates are dropped because a repeated entry
    searches the same directory twice and says nothing.
    """
    seen: dict[str, None] = {}
    for entry in candidates:
        seen.setdefault(str(PurePosixPath(entry)), None)
    return tuple(seen)


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
    "SETUP_CFG",
    "Captured",
    "NoLockfile",
    "NotProvisionable",
    "UnknownImportRoot",
    "capture",
    "import_roots",
    "pins_from_freeze",
]
