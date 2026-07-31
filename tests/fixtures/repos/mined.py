"""A task shaped like a MINED one: a donor with a parent and a child, and a manifest naming both.

``repos.__init__`` builds one-commit repositories, which is everything the verifier needs — it
only ever checks out ``base_commit``. The bake-off's control arm needs the other half: the
commit's own fix has to be **re-derivable**, which means the donor must still hold the child
commit the task was mined from, and the manifest must say which commit that was.

So this module writes the manifest the way ``whetstone.tasks.mine`` writes it, in the two respects
the control arm reads: ``repo_url`` is the donor's path on disk, and ``provenance`` carries
``donor`` / ``commit`` / ``parent``. Everything else is the smallest history that discriminates —
one bug, one fix, one held test file, and one non-``.py`` path in the same commit so the derived
reference patch has to carry something a source-only filter would drop.

**The two degenerate variants are the point of the file.** ``vacuous=True`` builds a task whose
bug was never there, so the no-patch arm PASSES — the control arm must refuse it loudly, because
that is the shape in which a broken checkout looks exactly like a competent model.
``held_conftest=True`` builds one whose commit also edits a root ``conftest.py`` the manifest
holds, so the re-derived reference would touch an operator-held path — STRICT refuses that
outright, and a control arm without a pre-flight would read its own refusal as "the harness
cannot reach PASS".

Nothing here is collected by the outer suite: the sources are strings, materialised into
``tmp_path`` at test time.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path

from fixtures.repos import _git
from whetstone.verify.task import Task, load_task

#: The bug at the parent: ``add`` subtracts.
MINED_CALC_BUGGY = "def add(a, b):\n    return a - b\n"

#: The fix the child commit makes, and therefore what the re-derived reference patch contains.
MINED_CALC_FIXED = "def add(a, b):\n    return a + b\n"

#: The held test file at the parent: one test, and it already passes. The task is not yet red.
MINED_TESTS_BEFORE = """\
from calc import add


def test_adding_zero_is_the_identity():
    assert add(4, 0) == 4
"""

#: The held test file at the child — the operator's artifact, and what STRICT restores. The
#: second test is the one that must flip red to green.
MINED_TESTS_AFTER = """\
from calc import add


def test_adding_zero_is_the_identity():
    assert add(4, 0) == 4


def test_add_is_addition():
    assert add(2, 3) == 5
"""

#: A non-``.py`` file the fixing commit also touches. Real red-to-green commits carry them, and a
#: reference derivation that kept only source files would produce a patch that does not reproduce
#: the commit.
MINED_README_BEFORE = "# donor\n\nA calculator with one bug in it.\n"
MINED_README_AFTER = MINED_README_BEFORE + "\n- addition adds again\n"

#: A root ``conftest.py``, held by the manifest as the cheat-10 floor. ``is_test_path`` correctly
#: calls it source rather than test code, so a commit that edits it puts a held path into the
#: re-derived reference — the exact collision the control arm's pre-flight exists to catch.
MINED_CONFTEST_BEFORE = "COLLECTED = True\n"
MINED_CONFTEST_AFTER = "COLLECTED = True\nRELAXED = True\n"

#: A source file the fixing commit RENAMES. git reports a rename as one name-status record with
#: two paths where every other record carries one, so a commit containing one is the only thing
#: that exercises that branch of the derivation's parser.
MINED_HELPER = "def describe():\n    return 'a calculator'\n"


@dataclass(frozen=True)
class Mined:
    """A materialised mined task: the loaded ``Task``, its donor, and the two commits behind it.

    ``commit`` and ``parent`` are handed back explicitly rather than left to be read out of
    ``task.provenance``, so a test can assert about the reference derivation without going
    through the same mapping the code under test reads.
    """

    task: Task
    donor: Path
    commit: str
    parent: str


def build_mined_task(
    root: Path,
    *,
    task_id: str = "synthetic-mined-adder",
    subject: str = "Fix addition",
    renamed: bool = False,
    vacuous: bool = False,
    held_conftest: bool = False,
) -> Mined:
    """Build a two-commit donor under ``root`` and load the task mined from its second commit.

    ``subject`` is the fixing commit's message and, following ``whetstone.tasks.mine``, the task's
    ``problem_statement``. It is a parameter because ``render_prompt`` reads exactly the problem
    statement and the failing node ids: two fixtures differing only in ``task_id`` render the
    **same prompt**, so a test wanting several distinguishable tasks has to vary this.

    ``renamed`` has the fixing commit also move a source file, so its name-status record carries
    two paths rather than one.

    ``vacuous`` puts the fix in at the parent as well, so the declared failing test already passes
    with nothing applied. Such a task grades every policy as correct — including one that emitted
    nothing — and the control arm is the thing that has to notice.

    ``held_conftest`` adds a root ``conftest.py`` to both commits, lets the child edit it, and
    holds it in ``test_blobs``. The re-derived reference then touches an operator-held path.
    """
    donor = Path(root) / "donor"
    donor.mkdir(parents=True)
    _git(["init", "--quiet", "--initial-branch=main"], cwd=donor)

    before: dict[str, str | None] = {
        "calc.py": MINED_CALC_FIXED if vacuous else MINED_CALC_BUGGY,
        "tests/test_addition.py": MINED_TESTS_BEFORE,
        "README.md": MINED_README_BEFORE,
    }
    after: dict[str, str | None] = {
        "calc.py": MINED_CALC_FIXED,
        "tests/test_addition.py": MINED_TESTS_AFTER,
        "README.md": MINED_README_AFTER,
    }
    if held_conftest:
        before["conftest.py"] = MINED_CONFTEST_BEFORE
        after["conftest.py"] = MINED_CONFTEST_AFTER
    if renamed:
        before["helper.py"] = MINED_HELPER
        # Moved with its contents untouched, so git reports `R100` rather than a delete and an
        # add — the shape a parser matching the bare status letter would mis-consume.
        after["helper.py"] = None
        after["helpers.py"] = MINED_HELPER

    parent = _commit(donor, before, subject="Seed the calculator")
    commit = _commit(donor, after, subject=subject)

    # The held test file is read at the CHILD — the child's tests are the ones that must go green
    # and STRICT's restore is what applies them. The conftest floor is read at the PARENT, which
    # is the tree STRICT checks out. Both mirror `whetstone.tasks.mine._manifest`.
    blobs = {"tests/test_addition.py": MINED_TESTS_AFTER.encode()}
    if held_conftest:
        blobs["conftest.py"] = MINED_CONFTEST_BEFORE.encode()

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
            path: base64.b64encode(contents).decode("ascii") for path, contents in blobs.items()
        },
        "provenance": {"donor": donor.name, "commit": commit, "parent": parent},
    }
    manifest_path = Path(root) / f"{task_id}.json"
    manifest_path.write_text(json.dumps(manifest))
    return Mined(task=load_task(manifest_path), donor=donor, commit=commit, parent=parent)


def _commit(donor: Path, files: dict[str, str | None], *, subject: str) -> str:
    """Write ``files`` into ``donor``, commit them, and return the resulting SHA.

    ``None`` deletes the path, which is how a rename is expressed: the old name removed and the
    new one written in the same commit.
    """
    for relative, contents in files.items():
        target = donor / relative
        if contents is None:
            target.unlink()
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents)
    _git(["add", "--all"], cwd=donor)
    _git(["commit", "--quiet", "--message", subject], cwd=donor)
    return _git(["rev-parse", "HEAD"], cwd=donor).strip()


__all__ = [
    "MINED_CALC_BUGGY",
    "MINED_CALC_FIXED",
    "MINED_CONFTEST_AFTER",
    "MINED_CONFTEST_BEFORE",
    "MINED_HELPER",
    "MINED_README_AFTER",
    "MINED_README_BEFORE",
    "MINED_TESTS_AFTER",
    "MINED_TESTS_BEFORE",
    "Mined",
    "build_mined_task",
]
