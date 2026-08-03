"""A repository whose code is **not at the checkout root** — the layout that broke the reward.

Every other fixture in this package is flat: ``calc.py`` sits beside ``tests/``, so
``python -m pytest`` with the checkout as the working directory puts the code under test at
``sys.path[0]`` and nothing else can shadow it. That is a property of the fixtures, not of the
verifier, and it hid a defect for a whole slice.

**The defect.** A ``src``-layout project is imported by its package name (``import calc``), and
that name resolves through whatever the interpreter's ``sys.path`` offers. If a copy of the
project is installed in the interpreter's ``site-packages`` — which is exactly what
``uv sync`` used to leave behind, an editable install rooted at the **provisioning** checkout —
then the run's own checkout is never imported. The verdict is then decided by a directory
outside the run, and a policy that submitted nothing would still be paid.

**What this module builds, and why each half exists.**

- ``SRC_LAYOUT_CALC`` is ``BROKEN_ADDER`` moved under ``src/``, with the packaging that says so.
  Same bug, same tests, same node ids; the layout is the only difference, which is what makes it
  usable as a controlled comparison.
- ``stale_interpreter`` builds a venv that can run pytest and in which a **fixed** copy of the
  project is importable from outside any checkout. That is the condition under which the reward
  must still report FAIL for a run with no patch.

**The stale copy is installed as a ``.pth`` file rather than by ``uv pip install --editable``,
and the substitution is exact rather than convenient.** A modern editable install of a
``src``-layout project *is* a ``.pth`` naming the source directory (plus a finder that adds
nothing to this question); the ``.pth`` is the half that makes the stale tree importable. Writing
one directly means the fixture cannot fail for a reason that has nothing to do with what it
proves — a cold uv cache, a build backend that could not be fetched offline — and it puts the
stale directory at the *end* of ``sys.path``, which is the **weakest** position an install can
occupy. A defence that holds against a ``.pth`` holds against a wheel copied into
``site-packages`` too.

Offline throughout: ``uv venv`` against this process's own interpreter, and one ``uv pip
install --offline pytest``, resolved from the committed wheelhouse that ``tests/conftest.py``
puts on ``UV_FIND_LINKS`` rather than from whatever this machine's uv cache happens to hold.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fixtures.repos import (
    CALC_BUGGY,
    CALC_FIXED,
    FAIL_TO_PASS_SOURCE,
    PASS_TO_PASS_SOURCE,
    RepoSpec,
)
from fixtures.repos.donor import DonorCommit

#: The packaging that makes ``src`` the import root, spelled the way a real donor spells it.
#: ``packages = ["src/calc"]`` is hatchling's explicit form and is what ``donor A`` — the first
#: real donor, and the repository this defect was found against — declares.
SRC_LAYOUT_PYPROJECT = """\
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "calc"
version = "0.0.0"
requires-python = ">=3.10"
dependencies = []

[tool.hatch.build.targets.wheel]
packages = ["src/calc"]
"""

#: The module path the package lives at, named once because the origin repository, the stale
#: copy and the patches that act on either all have to agree on it.
SRC_MODULE = "src/calc/__init__.py"

#: ``BROKEN_ADDER`` with its module moved under ``src/`` and packaging added. The tests are the
#: shared sources rather than copies: ``from calc import add`` is written identically either way,
#: so the repository really is the flat one relocated and nothing else.
SRC_LAYOUT_CALC = RepoSpec(
    files={
        "pyproject.toml": SRC_LAYOUT_PYPROJECT,
        SRC_MODULE: CALC_BUGGY,
        "tests/test_addition.py": FAIL_TO_PASS_SOURCE,
        "tests/test_identity.py": PASS_TO_PASS_SOURCE,
    },
    fail_to_pass=("tests/test_addition.py::test_add_is_addition",),
    pass_to_pass=("tests/test_identity.py::test_adding_zero_is_the_identity",),
    held=("tests/test_addition.py", "tests/test_identity.py"),
    # The one line that is not shared with the flat repository, and the one that decides which
    # tree gets imported. Without it the declared tests reach whatever the interpreter has
    # installed, which is the whole subject of `tests/adversarial/test_inert_checkout.py`.
    import_roots=("src",),
)


#: The held test file at the CHILD of the mintable commit: the identity test that already passed
#: at the parent, plus the one the commit turned green. One file, so the derivation has both a
#: `fail_to_pass` and a `pass_to_pass` to find without needing a second held path.
_ADDITION_FIXED = """\
from calc import add


def test_adding_zero_is_the_identity():
    assert add(4, 0) == 4


def test_add_is_addition():
    assert add(2, 3) == 5
"""


def packaged_project(root: Path, *, name: str = "calc") -> Path:
    """A locked ``src``-layout project on disk — what ``environment.capture`` is pointed at.

    Distinct from ``SRC_LAYOUT_CALC`` because provisioning takes a *directory* while
    ``build_task`` takes file contents, and because this one carries a real ``uv.lock``: a
    hand-authored lock would be this suite asserting about its own idea of uv's format.

    No dependencies are declared, so ``uv lock`` reads the project's static metadata and never
    builds it. That matters offline — a build would need hatchling from somewhere — and it is
    also the honest shape: what is under test here is whether the **project itself** ends up
    installed, not whether its dependencies do.
    """
    project = Path(root)
    project.mkdir(parents=True, exist_ok=True)
    (project / "pyproject.toml").write_text(SRC_LAYOUT_PYPROJECT.replace('"calc"', f'"{name}"'))
    module = project / "src" / name
    module.mkdir(parents=True, exist_ok=True)
    (module / "__init__.py").write_text(CALC_BUGGY)
    _uv(["lock", "--project", str(project), "--python", sys.executable, "--offline"])
    return project


def src_layout_history(scratch: Path) -> tuple[DonorCommit, ...]:
    """The smallest mintable history whose code is under ``src/``: seed, then one red→green fix.

    Deliberately not ``DONOR_HISTORY`` relocated. That history exists to prove one selection rule
    per commit and is flat throughout; a second copy of it under ``src/`` would be eleven commits
    of duplication to exercise one property. Two commits are enough to be *mintable* — an existing
    test file modified, a non-test ``.py`` touched — which is all this fixture is for.

    The packaging is committed at the **seed**, because the miner provisions at a candidate's
    parent: a ``uv.lock`` arriving later would leave the only candidate unprovisionable, and the
    fixture rather than the miner would have decided what could be mined.
    """
    project = packaged_project(Path(scratch) / "packaging")
    return (
        DonorCommit(
            subject="Seed the calculator",
            changes={
                "pyproject.toml": (project / "pyproject.toml").read_text(),
                "uv.lock": (project / "uv.lock").read_text(),
                SRC_MODULE: CALC_BUGGY,
                "tests/test_addition.py": PASS_TO_PASS_SOURCE,
            },
        ),
        DonorCommit(
            subject="Fix addition",
            changes={SRC_MODULE: CALC_FIXED, "tests/test_addition.py": _ADDITION_FIXED},
        ),
    )


def stale_interpreter(root: Path) -> Path:
    """A python that can run pytest and in which a **fixed** ``calc`` is already importable.

    The fixed copy is the point. If it carried the bug, a FAIL would prove nothing — the run
    would reach the same answer whichever tree it imported. Handing the interpreter a *passing*
    version of the code under test is what makes "the reward said FAIL" a statement about which
    checkout was imported.

    Returns the interpreter path. The stale tree is left at ``root / "stale"`` so a test can
    assert it is genuinely importable before concluding anything from a verdict.
    """
    root = Path(root)
    stale = root / "stale" / "src" / "calc"
    stale.mkdir(parents=True, exist_ok=True)
    (stale / "__init__.py").write_text(CALC_FIXED)

    venv = root / "venv"
    _uv(["venv", "--offline", "--python", sys.executable, str(venv)])
    interpreter = venv / "bin" / "python"
    _uv(["pip", "install", "--quiet", "--python", str(interpreter), "--offline", "pytest"])

    site_packages = next(venv.glob("lib/python*/site-packages"))
    (site_packages / "_calc_stale.pth").write_text(f"{stale.parent}\n")
    return interpreter


def can_import_calc(interpreter: Path, *, cwd: Path) -> bool:
    """Does this interpreter import a ``calc`` at all, and does its ``add`` actually add?

    The anti-vacuity control for every assertion built on ``stale_interpreter``. A venv that
    could not import ``calc`` — a mistyped ``.pth``, a site-packages directory that moved —
    would make the reward FAIL for a reason with nothing to do with the checkout, and the test
    resting on it would pass while proving the opposite of what it claims.
    """
    probe = "from calc import add; raise SystemExit(0 if add(2, 3) == 5 else 1)"
    completed = subprocess.run(
        [str(interpreter), "-c", probe],
        cwd=str(cwd),
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def _uv(args: list[str]) -> None:
    """uv, with its failure surfaced in full — a half-built venv fails later and opaquely."""
    completed = subprocess.run(["uv", *args], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"uv {' '.join(args)} failed: {completed.stderr.strip()}")


__all__ = [
    "SRC_LAYOUT_CALC",
    "SRC_LAYOUT_PYPROJECT",
    "SRC_MODULE",
    "can_import_calc",
    "packaged_project",
    "src_layout_history",
    "stale_interpreter",
]
