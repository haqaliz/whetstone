"""The difficulty rule: the reference fix's shape, measured a priori, never from a verdict.

`stratum.difficulty_of` computes the difficulty of a task as the shape of its own fix: the
non-test files the mined commit touched, and the hunks and added/deleted lines of the gold
patch derived from the donor at `provenance.commit`/`parent` — the same derivation the control
arm trusts, reused by identity and never redefined (`control.py:24-29`). The band (one
non-test file, at most two hunks, at most thirty changed lines) is pre-committed before any
run; widening it after seeing a corpus is post-hoc selection (`prd.md:218-221`).

The whole point of measuring the shape with the rule's own walk is that git does not report
hunk counts, and `verify.repo.declared_paths` drops the added/deleted counts even where it
agrees with the walk (`repo.py:87-95`). The walk's margin cases — binary payload, no-newline
markers, renames — are pinned here as fixtures, and the corpus test proves the walk and git
agree on all 66 real tasks.

Nothing here may read a verdict, a rollout record, or a report figure
(`PREREGISTRATION.md:171-177`): the axis is fixed at mint time, and the rule's path is walked
for inference imports at the bottom of this file.
"""

from __future__ import annotations

import ast
import base64
import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from fixtures.repos import _git
from fixtures.repos.mined import (
    MINED_TESTS_AFTER,
    MINED_TESTS_BEFORE,
    Mined,
    build_mined_task,
)

from whetstone.bakeoff import sources, stratum
from whetstone.bakeoff.control import reference_patch
from whetstone.tasks import derive
from whetstone.verify.task import load_task

#: The repository root, for the no-inference walk at the bottom of this file.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: The held test pair every synthetic donor here carries, in the mined shape: one test that
#: must flip red to green and one that stays green (`fixtures/repos/mined.py:43-63`).
_ADDITION_TESTS_BEFORE = MINED_TESTS_BEFORE
_ADDITION_TESTS_AFTER = MINED_TESTS_AFTER

#: A one-file bug/fix pair: `add` subtracts at the parent and adds at the child.
_CALC_BUGGY = "def add(a, b):\n    return a - b\n"
_CALC_FIXED = "def add(a, b):\n    return a + b\n"

#: A one-file fix editing three separate regions, so the hunks exceed the band while the
#: file count does not — the multi-hunk shape that must fall outside the band. The regions
#: are separated by twelve untouched lines each, so git's three-line hunk context cannot
#: merge them: three edits closer than seven unchanged lines apart are one hunk.
_MULTI_SEPARATOR = "# separator line, untouched\n" * 12
_MULTI_BUGGY = (
    "def add(a, b):\n    return a - b\n"
    + _MULTI_SEPARATOR
    + "def sub(a, b):\n    return a + b\n"
    + _MULTI_SEPARATOR
    + "def mul(a, b):\n    return a / b\n"
)
_MULTI_FIXED = (
    "def add(a, b):\n    return a + b\n"
    + _MULTI_SEPARATOR
    + "def sub(a, b):\n    return a - b\n"
    + _MULTI_SEPARATOR
    + "def mul(a, b):\n    return a * b\n"
)

#: The `\\ No newline` margin: the fixed file lacks the trailing newline its parent had, so the
#: diff carries git's no-newline marker lines, which are annotations, never content.
_NO_NEWLINE_FIXED = "def add(a, b):\n    return a + b"


def _commit_files(donor: Path, files: Mapping[str, str | bytes | None], *, subject: str) -> str:
    """Write ``files`` into ``donor`` (``None`` deletes), commit, and return the SHA.

    The same builder `build_mined_task` commits through (`fixtures/repos/mined.py:192-207`),
    extended for ``bytes`` so a binary fixture is possible. ``_git`` pins the identity and the
    dates, so a fixture repository has the same SHAs on every machine and every run.
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


def _build_variant(
    root: Path,
    task_id: str,
    before: Mapping[str, str | bytes],
    after: Mapping[str, str | bytes],
    *,
    subject: str = "Fix the bug",
) -> Mined:
    """A two-commit donor whose fixing commit touches exactly the given non-test files.

    Every variant carries the same held test pair as the mined fixture, so the manifest loads
    and the donor is a plausible mined task; the variant files are the whole non-test diff.
    """
    donor = Path(root) / "donor"
    donor.mkdir(parents=True)
    _git(["init", "--quiet", "--initial-branch=main"], cwd=donor)
    parent = _commit_files(
        donor, {"tests/test_addition.py": _ADDITION_TESTS_BEFORE, **before}, subject="Seed"
    )
    commit = _commit_files(
        donor, {"tests/test_addition.py": _ADDITION_TESTS_AFTER, **after}, subject=subject
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
                _ADDITION_TESTS_AFTER.encode("utf-8")
            ).decode("ascii")
        },
        "provenance": {"donor": donor.name, "commit": commit, "parent": parent},
    }
    manifest_path = Path(root) / f"{task_id}.json"
    manifest_path.write_text(json.dumps(manifest))
    return Mined(task=load_task(manifest_path), donor=donor, commit=commit, parent=parent)


def _single_file(root: Path, task_id: str, *, after: str = _CALC_FIXED) -> Mined:
    """The in-band shape: exactly one non-test file, one hunk, one line either way."""
    return _build_variant(
        root,
        task_id,
        {"calc.py": _CALC_BUGGY},
        {"calc.py": after},
    )


def _source_a_shaped(root: Path) -> tuple[Path, Mined]:
    """A mined fixture whose manifest is rewritten into source A's provenance shape.

    A SWE-bench instance carries an `instance_id` where a mined task carries `commit`/`parent`,
    so nothing can be re-derived from it (`control.py:209-211`) — the shape `difficulty_of`
    must refuse by name rather than measure.
    """
    fixture = build_mined_task(root / "task")
    manifest_path = Path(root) / "task" / f"{fixture.task.task_id}.json"
    raw = json.loads(manifest_path.read_text())
    raw["provenance"] = {"instance_id": "pallets__flask-4045"}
    manifest_path.write_text(json.dumps(raw))
    return manifest_path, fixture


def test_the_default_mined_fix_measures_two_files_and_two_hunks(tmp_path: Path) -> None:
    """The mined fixture's fixing commit touches `calc.py` AND `README.md` — 2 files, 2 hunks.

    Multi-file is the norm rather than the corner (`plan_20260814.md` edge cases): the default
    fixture is already out of the band on the files axis, which is why the band tests below
    need a dedicated single-file fixture. The tie-break fields are the manifest-structural
    counts present in every manifest (`understanding.md:31-38`).
    """
    fixture = build_mined_task(tmp_path / "task")

    difficulty = stratum.difficulty_of(fixture.task)

    assert isinstance(difficulty, stratum.Difficulty), (
        f"WHY THIS IS A FAILURE: the mined fixture names its donor, commit and parent, so its "
        f"fix shape is re-derivable and must measure rather than refuse: {difficulty}"
    )
    assert (difficulty.files, difficulty.hunks, difficulty.added, difficulty.deleted) == (
        2,
        2,
        3,
        1,
    ), (
        "WHY THIS IS A FAILURE: the fixing commit touches calc.py (1 hunk, -1/+1) and "
        "README.md (1 hunk, +2) — 2 files, 2 hunks, 3 added and 1 deleted line. A different "
        "count means the walk disagrees with the reference patch the control arm trusts."
    )
    assert (difficulty.f2p, difficulty.pins, difficulty.blobs) == (1, 0, 1)


def test_a_single_file_fix_is_in_the_band(tmp_path: Path) -> None:
    """One non-test file, one hunk, two changed lines: the band's exact home."""
    fixture = _single_file(tmp_path / "task", "synthetic-single-file")

    difficulty = stratum.difficulty_of(fixture.task)

    assert isinstance(difficulty, stratum.Difficulty)
    assert (difficulty.files, difficulty.hunks, difficulty.added, difficulty.deleted) == (
        1,
        1,
        1,
        1,
    )
    assert stratum.in_band(difficulty), (
        "WHY THIS IS A FAILURE: a one-file, one-hunk, two-line fix is the shape the band "
        "exists to select; refusing it makes the stratum empty by construction."
    )


def test_a_multi_hunk_single_file_fix_is_outside_the_band(tmp_path: Path) -> None:
    """Three hunks in one file: inside on files, outside on hunks — the band must reject it."""
    fixture = _build_variant(
        tmp_path / "task",
        "synthetic-multi-hunk",
        {"calc.py": _MULTI_BUGGY},
        {"calc.py": _MULTI_FIXED},
    )

    difficulty = stratum.difficulty_of(fixture.task)

    assert isinstance(difficulty, stratum.Difficulty)
    assert difficulty.files == 1, "the multi-hunk fixture must stay single-file"
    assert difficulty.hunks >= 3, (
        "the fixture fixes three separate regions, so the walk must count at least three hunks; "
        "a lower count means the walk is not counting @@ headers"
    )
    assert not stratum.in_band(difficulty), (
        "WHY THIS IS A FAILURE: three hunks exceed the pre-committed band of two. A fix that "
        "edits several regions of one file is not the smallest-shape stratum."
    )


def test_a_rename_counts_both_halves(tmp_path: Path) -> None:
    """Both halves of a rename are non-test paths, so both count (`sources.py:512-515`)."""
    fixture = build_mined_task(tmp_path / "task", renamed=True)

    difficulty = stratum.difficulty_of(fixture.task)

    assert isinstance(difficulty, stratum.Difficulty)
    assert difficulty.files == 4, (
        "the renamed fixture's fixing commit touches calc.py, README.md, helper.py AND "
        f"helpers.py, so files must be 4, got {difficulty.files}"
    )


def test_a_held_conftest_is_refused_by_the_changed_paths_preflight(tmp_path: Path) -> None:
    """A fix touching an operator-held path is refused before the walk — never measured."""
    fixture = build_mined_task(tmp_path / "task", held_conftest=True)

    result = stratum.difficulty_of(fixture.task)

    assert isinstance(result, stratum.Refusal), (
        "WHY THIS IS A FAILURE: the re-derived fix touches the operator-held conftest.py, "
        "which STRICT refuses as a cheat. The rule must carry the changed_paths refusal "
        "through with its reason, exactly as the control arm does (`control.py:242-252`)."
    )
    assert "conftest.py" in result.reason, (
        "the refusal must carry the changed_paths reason naming the collision, not a "
        f"generic one: {result.reason}"
    )


def test_a_vacuous_task_is_still_measured(tmp_path: Path) -> None:
    """The rule is shape-only: vacuity is the control arm's concern, never this axis's."""
    fixture = build_mined_task(tmp_path / "task", vacuous=True)

    assert isinstance(stratum.difficulty_of(fixture.task), stratum.Difficulty)


def test_a_task_without_a_donor_commit_is_refused_by_name(tmp_path: Path) -> None:
    """Source A has no difficulty, by construction: nothing to derive from (spec D8)."""
    manifest_path, fixture = _source_a_shaped(tmp_path)
    task = load_task(manifest_path)
    assert fixture.task.provenance.get("commit"), "the control fixture must start mined-shaped"

    result = stratum.difficulty_of(task)

    assert isinstance(result, stratum.Refusal), (
        "WHY THIS IS A FAILURE: a task carrying an instance_id instead of commit/parent has "
        "no donor commit, so there is no reference fix to measure. Measuring it would be "
        "inventing a shape out of nothing (`control.py:209-211`)."
    )
    assert "no donor commit" in result.reason, (
        f"the refusal must name the missing donor commit: {result.reason}"
    )


def test_measuring_the_same_task_twice_is_equal(tmp_path: Path) -> None:
    """The axis is a pure function of the manifest plus the pinned donor state."""
    fixture = build_mined_task(tmp_path / "task")
    assert stratum.difficulty_of(fixture.task) == stratum.difficulty_of(fixture.task)


def test_the_band_constants_are_the_pre_committed_numbers() -> None:
    """The band is fixed here, before any run: 1 file, 2 hunks, 30 lines (spec D4).

    A change to either requires a spec amendment first, never a silent test edit
    (`plan_20260814.md` agent notes). Widening after seeing the corpus is post-hoc selection.
    """
    assert stratum.BAND_MAX_NON_TEST_FILES == 1
    assert stratum.BAND_MAX_HUNKS == 2
    assert stratum.BAND_MAX_CHANGED_LINES == 30


def test_in_band_accepts_the_band_and_rejects_both_other_axes(tmp_path: Path) -> None:
    """Membership is `files == 1 and hunks <= 2 and added + deleted <= 30`, no exceptions."""
    in_band = _single_file(tmp_path / "in-band", "synthetic-in-band")
    multi = _build_variant(
        tmp_path / "multi",
        "synthetic-multi-hunk",
        {"calc.py": _MULTI_BUGGY},
        {"calc.py": _MULTI_FIXED},
    )
    out_files = build_mined_task(tmp_path / "out-files")

    assert stratum.in_band(stratum.difficulty_of(in_band.task)) is True
    assert stratum.in_band(stratum.difficulty_of(multi.task)) is False
    assert stratum.in_band(stratum.difficulty_of(out_files.task)) is False


def test_a_binary_gold_patch_counts_zero_added_and_deleted(tmp_path: Path) -> None:
    """A `GIT binary patch` literal is not content lines: the walk must count nothing for it.

    `gold_patch` runs `--binary` (`derive.py:201-208`), so a fix touching a binary file puts a
    base85 literal into the diff. Payload lines are never `+`/`-` unified content; counting
    them would report a binary-only fix as a many-line edit.
    """
    fixture = _build_variant(
        tmp_path / "task",
        "synthetic-binary",
        {"data.bin": b"\x00\x01\x02\x03"},
        {"data.bin": b"\x00\x01\x02\x03\x04"},
    )

    difficulty = stratum.difficulty_of(fixture.task)

    assert isinstance(difficulty, stratum.Difficulty)
    assert (difficulty.files, difficulty.hunks, difficulty.added, difficulty.deleted) == (
        1,
        0,
        0,
        0,
    ), (
        "WHY THIS IS A FAILURE: the only change is a binary literal, which carries no unified "
        "hunks and no added/deleted content lines. Any count means the walk is reading "
        "base85 payload as diff content (spec D3)."
    )


def test_the_no_newline_marker_is_never_counted(tmp_path: Path) -> None:
    """`\\ No newline at end of file` annotates a hunk; it is not a content line."""
    fixture = _single_file(tmp_path / "task", "synthetic-no-newline", after=_NO_NEWLINE_FIXED)

    difficulty = stratum.difficulty_of(fixture.task)

    assert isinstance(difficulty, stratum.Difficulty)
    assert (difficulty.files, difficulty.hunks, difficulty.added, difficulty.deleted) == (
        1,
        1,
        1,
        1,
    ), (
        "WHY THIS IS A FAILURE: the marker line would add one phantom count per side if the "
        "walk treated it as content. numstat never counts it either — the corpus "
        "cross-assertion would catch a walk that did (spec D3)."
    )


def test_changed_paths_is_the_sources_module_function_by_identity() -> None:
    """Imported, never copied: one derivation of the task's scope, the oracle's own (spec D2)."""
    assert stratum.changed_paths is sources.changed_paths


def test_gold_patch_is_the_derive_module_function_by_identity() -> None:
    """Imported, never copied: one definition of "the commit's own fix" (spec D2)."""
    assert stratum.gold_patch is derive.gold_patch


def test_the_composed_diff_is_byte_identical_to_the_control_arms(tmp_path: Path) -> None:
    """The rule composes the gold diff exactly as `control._from_donor` does (spec D2).

    A second composition that disagreed with the control arm's would be a second definition
    of "the commit's own fix" with only one of them reviewed (`control.py:24-29`).
    """
    fixture = build_mined_task(tmp_path / "task")

    reference = reference_patch(fixture.task)
    assert reference.diff is not None, reference.reason

    composed = stratum._gold_diff(fixture.task)
    assert isinstance(composed, str), composed

    assert composed == reference.diff


# --------------------------------------------------------------------------------------------
# The offline guard: the rule's path imports no inference library, and no `run.py`.
# --------------------------------------------------------------------------------------------

#: Import roots that would mean a model was consulted on the difficulty rule's path. The
#: diffcheck root set, applied to this module's path (`test_diffcheck.py:382-386`).
FORBIDDEN_IMPORT_ROOTS = frozenset({"mlx", "mlx_lm", "torch", "transformers", "run"})

#: The paths the no-inference walk covers: the rule module and its three test files. The
#: document and corpus tests land in later phases; the walk skips them until they exist,
#: then covers them forever after.
STRATUM_PATHS = (
    "src/whetstone/bakeoff/stratum.py",
    "tests/bakeoff/test_stratum_rule.py",
    "tests/bakeoff/test_stratum_document.py",
    "tests/bakeoff/test_stratum_corpus.py",
)


def _imported_roots(source: bytes) -> set[str]:
    """The top-level package of every import in `source`, function-local ones included.

    `ast.walk` rather than a top-of-file read: an import moved inside a function would
    otherwise be invisible — which is exactly where a "just this once" model call would go.
    Relative imports are invisible too, by `node.level == 0`: the documented porting-trap
    shape, and this path is first-party code that imports by absolute name.
    """
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source, filename="<source>")):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_the_walk_reports_an_import_it_is_given() -> None:
    """Anti-vacuity control: the walk must actually observe imports."""
    assert "json" in _imported_roots(b"import json\n"), (
        "the AST walk did not see the stdlib import it was handed, so the no-inference "
        "assertions below would pass by seeing nothing at all."
    )


def test_a_planted_inference_import_is_seen_and_flagged() -> None:
    """The guard's predicate, watched failing: a planted inference import must be flagged."""
    roots = _imported_roots(b"import json\n\nfrom mlx_lm import load\n")
    assert roots & FORBIDDEN_IMPORT_ROOTS == {"mlx_lm"}, roots


@pytest.mark.parametrize("relative", STRATUM_PATHS)
def test_the_rule_path_imports_no_inference_library(relative: str) -> None:
    """The difficulty axis is fixed before any rollout and never costs compute.

    A rule that read a verdict or consulted a model would make the stratum a function of the
    run it is supposed to predate (`PREREGISTRATION.md:171-177`). The test files are covered
    too, because a fixture that generated its own verdicts would make the module's own
    guarantee untestable.

    Files that have not landed yet are skipped, not silently dropped — walked the moment they
    exist.
    """
    path = REPO_ROOT / relative
    if not path.is_file():
        pytest.skip(f"{relative} does not exist yet — walked when it lands")

    roots = _imported_roots(path.read_bytes())

    assert not roots & FORBIDDEN_IMPORT_ROOTS, (
        f"{relative} imports {sorted(roots & FORBIDDEN_IMPORT_ROOTS)}.\n\n"
        "WHY THIS IS A FAILURE: the stratum is the pre-committed selection the probe runs "
        "over. An inference import here means the membership depends on the model it is "
        "supposed to select for."
    )
    assert roots, (
        f"{relative} contains no import at all, so the assertion above holds for a file "
        "nothing was checked against. A guard that walks a set of files must find imports in "
        "them (`CONTRIBUTING.md:60`)."
    )
