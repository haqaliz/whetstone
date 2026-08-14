"""Hand-built mined-shaped donors for the difficulty-shape fixtures.

``build_mined_task`` (`fixtures/repos/mined.py`) covers the shapes the control arm needs; the
difficulty rule additionally needs donors whose fixing commit touches *exactly* the files a
test wants — one file, several hunks in one file, a binary literal, a no-newline file. Each
is a real two-commit repository built through the same ``_git`` helper
``build_mined_task`` commits through (`fixtures/repos/mined.py:192-207`), extended for
``bytes`` so a binary fixture is possible, with the manifest written in the mined shape
(`provenance` carries ``commit``/``parent``).

Nothing here is collected by the outer suite: the sources are strings, materialised into
``tmp_path`` at test time.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from pathlib import Path

from fixtures.repos import _git
from fixtures.repos.mined import MINED_TESTS_AFTER, MINED_TESTS_BEFORE, Mined
from whetstone.verify.task import load_task

#: A one-file bug/fix pair: `add` subtracts at the parent and adds at the child.
CALC_BUGGY = "def add(a, b):\n    return a - b\n"
CALC_FIXED = "def add(a, b):\n    return a + b\n"

#: A one-file fix editing three separate regions, so the hunks exceed the band while the
#: file count does not. The regions are separated by twelve untouched lines each, so git's
#: three-line hunk context cannot merge them — three edits closer than seven unchanged
#: lines apart are one hunk.
_MULTI_SEPARATOR = "# separator line, untouched\n" * 12
MULTI_BUGGY = (
    "def add(a, b):\n    return a - b\n"
    + _MULTI_SEPARATOR
    + "def sub(a, b):\n    return a + b\n"
    + _MULTI_SEPARATOR
    + "def mul(a, b):\n    return a / b\n"
)
MULTI_FIXED = (
    "def add(a, b):\n    return a + b\n"
    + _MULTI_SEPARATOR
    + "def sub(a, b):\n    return a - b\n"
    + _MULTI_SEPARATOR
    + "def mul(a, b):\n    return a * b\n"
)

#: The `\\ No newline` margin: the fixed file lacks the trailing newline its parent had, so
#: the diff carries git's no-newline marker lines, which are annotations, never content.
NO_NEWLINE_FIXED = "def add(a, b):\n    return a + b"


def commit_files(donor: Path, files: Mapping[str, str | bytes | None], *, subject: str) -> str:
    """Write ``files`` into ``donor`` (``None`` deletes), commit, and return the SHA.

    The same builder `build_mined_task` commits through (`fixtures/repos/mined.py:192-207`),
    extended for ``bytes`` so a binary fixture is possible. ``_git`` pins the identity and
    the dates, so a fixture repository has the same SHAs on every machine and every run.
    """
    for relative, contents in files.items():
        target = donor / relative
        if contents is None:
            target.unlink()
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(contents, bytes):
            target.write_bytes(contents)
        else:
            target.write_text(contents)
    _git(["add", "--all"], cwd=donor)
    _git(["commit", "--quiet", "--message", subject], cwd=donor)
    return _git(["rev-parse", "HEAD"], cwd=donor).strip()


def build_variant_task(
    root: Path,
    task_id: str,
    before: Mapping[str, str | bytes],
    after: Mapping[str, str | bytes],
    *,
    subject: str = "Fix the bug",
) -> Mined:
    """A two-commit donor whose fixing commit touches exactly the given non-test files.

    Every variant carries the same held test pair as the mined fixture, so the manifest
    loads and the donor is a plausible mined task; the variant files are the whole
    non-test diff. The manifest is written to ``root / "<task_id>.json"`` beside the
    ``donor/`` repository, matching `build_mined_task`'s layout.
    """
    donor = Path(root) / "donor"
    donor.mkdir(parents=True)
    _git(["init", "--quiet", "--initial-branch=main"], cwd=donor)
    parent = commit_files(
        donor, {"tests/test_addition.py": MINED_TESTS_BEFORE, **before}, subject="Seed"
    )
    commit = commit_files(
        donor, {"tests/test_addition.py": MINED_TESTS_AFTER, **after}, subject=subject
    )

    manifest = {
        "task_id": task_id,
        "source": "private",
        "repo_url": str(donor),
        "base_commit": parent,
        "environment": {"python": "3.12", "pins": [], "import_roots": ["."]},
        "problem_statement": subject,
        "fail_to_pass": ["tests/test_addition.py::test_add_is_addition"],
        "pass_to_pass": ["tests/test_addition.py::test_adding_zero_is_the_identity"],
        "test_blobs": {
            "tests/test_addition.py": base64.b64encode(
                MINED_TESTS_AFTER.encode("utf-8")
            ).decode("ascii")
        },
        "provenance": {"donor": donor.name, "commit": commit, "parent": parent},
    }
    manifest_path = Path(root) / f"{task_id}.json"
    manifest_path.write_text(json.dumps(manifest))
    return Mined(task=load_task(manifest_path), donor=donor, commit=commit, parent=parent)


def single_file_task(root: Path, task_id: str, *, after: str = CALC_FIXED) -> Mined:
    """The in-band shape: exactly one non-test file, one hunk, one line either way."""
    return build_variant_task(
        root,
        task_id,
        {"calc.py": CALC_BUGGY},
        {"calc.py": after},
    )


__all__ = [
    "CALC_BUGGY",
    "CALC_FIXED",
    "MULTI_BUGGY",
    "MULTI_FIXED",
    "NO_NEWLINE_FIXED",
    "build_variant_task",
    "commit_files",
    "single_file_task",
]
