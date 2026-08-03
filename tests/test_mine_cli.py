"""`whetstone mine`: a local repository in, a proven corpus out, offline.

The operator-facing end of source B. Everything the earlier phases refuse is refused through
this surface too, so what is asserted here is the wiring and the two properties the surface
itself owns:

- **end to end, the manifests it writes are ones `load_task` accepts** — a miner whose output
  the shipped loader rejects would be discovered one task at a time, after a whole donor had
  been provisioned;
- **the evidence is written where `tasks/README.md` says it is** — the ledger and the recipe,
  which are the committed half of a corpus whose instances never leave the machine;
- **`--limit 0` is a usage error**, not a silent empty corpus. Exit 0 with nothing minted is the
  vacuous-green shape at the level of a whole run;
- **the same seed mints the same tasks, byte for byte** (PRD G4).

**No fifth exit code.** `tests/test_verify_cli.py` asserts the four are exactly four distinct
values, and a mint that invented a fifth would put a new meaning in a caller's `rc` check.

The donor is the synthetic one from `tests/fixtures/repos/donor.py`, extended with a real
`uv.lock` so it can be provisioned. Offline throughout: git reads a local repository, uv resolves
from a local lock with `--offline`, and every pytest run is inside the Seatbelt sandbox.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fixtures.repos.donor import build_donor
from fixtures.repos.locked import locked_history, locked_project_files
from fixtures.repos.packaged import src_layout_history

from whetstone.cli import FAIL_EXIT, PASS_EXIT, USAGE_ERROR, main
from whetstone.tasks.donor import Candidate
from whetstone.tasks.manifest import load_tasks
from whetstone.tasks.mine import LEDGER_NAME, select

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin",
    reason="mining runs its pytest inside the Seatbelt sandbox, which is macOS-only",
)

@pytest.fixture(scope="module")
def donor(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The mining donor, carrying packaging from its seed commit so every parent is lockable."""
    root = tmp_path_factory.mktemp("mine-donor")
    packaging = locked_project_files(root / "packaging", index=None)
    return build_donor(root, locked_history(packaging))


@pytest.fixture(scope="module")
def mined(donor: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One real end-to-end mint of a single task. Paid once; asserted from several angles."""
    root = tmp_path_factory.mktemp("mine-run")
    code = main(
        [
            "mine",
            "--donor",
            str(donor),
            "--label",
            "donor-x",
            "--out",
            str(root / "local" / "donor"),
            "--tasks-root",
            str(root),
            "--limit",
            "1",
            "--seed",
            "7",
        ]
    )
    assert code == PASS_EXIT, "the mint did not succeed, so nothing below is asserting on a corpus"
    return root


def test_the_minted_manifests_are_ones_the_shipped_loader_accepts(mined: Path) -> None:
    """`load_tasks` reads the whole output directory, refusing to skip anything in it.

    Which makes this the strongest available statement about the mint: not "a file was written"
    but "the corpus directory is one the verifier would run".
    """
    tasks = load_tasks(mined / "local" / "donor")
    assert len(tasks) == 1
    task = tasks[0]
    assert task.source == "private"
    assert task.fail_to_pass, "a task with nothing that must go green rewards changing nothing"
    assert task.test_blobs, "a task with no held tests has no boundary at all"
    assert task.environment.pins, "the task declares no pins, so its verdict moves with the index"


def test_the_minted_task_records_what_its_pass_to_pass_is_scoped_to(mined: Path) -> None:
    """Decision D-A, carried in the task rather than in a document nobody reads with it.

    Each mint runs the held test files only, so `pass_to_pass` means "the other tests in these
    same files". A reader who assumed the donor's whole suite would overstate what the corpus
    catches, and nothing in the manifest would correct them.
    """
    task = load_tasks(mined / "local" / "donor")[0]
    assert task.provenance["pass_to_pass_scope"] == "held-files"
    assert task.provenance["commit"], task.provenance


def test_the_ledger_and_the_recipe_are_written_where_the_readme_says(mined: Path) -> None:
    """The committed half of a corpus whose instances are gitignored."""
    ledger = json.loads((mined / LEDGER_NAME).read_text())
    assert len(ledger["tasks"]) == 1
    entry = ledger["tasks"][0]
    assert entry["without_patch"] == "FAIL"
    assert entry["with_patch"] == "PASS"
    assert entry["executed_matches_declared"] is True
    assert entry["skipped"] == 0
    assert entry["manifest_sha256"]

    recipes = sorted((mined / "recipes").glob("*.json"))
    assert len(recipes) == 1, recipes
    recipe = json.loads(recipes[0].read_text())
    assert recipe["pass_to_pass_scope"] == "held-files"
    assert recipe["donor_head"]
    assert recipe["selection"]["seed"] == "7"


def test_the_recipe_names_the_donor_by_label_and_never_by_path(donor: Path, mined: Path) -> None:
    """The recipe is committed; the donor is one of the user's private repositories.

    An earlier version recorded the donor's resolved path, which put an absolute path from the
    author's machine — and the private repository's name — into a file this project publishes.
    Neither is usable by a reader re-deriving the corpus against their own donor, so nothing was
    bought with the disclosure. The label is asserted in **both** places it appears, because the
    filename leaked the same name as the field and fixing one alone would look fixed.
    """
    recipes = sorted((mined / "recipes").glob("*.json"))
    assert [path.name for path in recipes] == ["donor-x.json"], (
        "the recipe is named after something other than the operator's label; if that is the "
        "donor's directory name, the private name is back in a committed filename"
    )

    recipe = json.loads(recipes[0].read_text())
    assert recipe["donor"] == "donor-x", recipe["donor"]

    # The donor's resolved path is what the leak actually was, and it is asserted against the
    # whole document rather than against the one field: a path that reappeared under some other
    # key would be exactly as published. A bare-name check is not available here — this suite's
    # fixture donor is *called* `donor`, which is also the field's name.
    written = recipes[0].read_text()
    assert str(donor) not in written, "the donor's absolute path appears in the committed recipe"
    assert "/Users/" not in written, "an absolute home path appears in the committed recipe"


def test_the_ledger_entry_is_the_hash_of_the_manifest_that_was_written(mined: Path) -> None:
    """The evidence has to be about the file that is actually there.

    A ledger whose hash is of a staged copy rather than of the manifest in the corpus would let
    the two drift, and the hash is the whole substitute for the data a reader does not have.
    """
    import hashlib

    manifest = next((mined / "local" / "donor").glob("*.json"))
    entry = json.loads((mined / LEDGER_NAME).read_text())["tasks"][0]
    assert entry["manifest_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert entry["task_id"] == manifest.stem


def test_a_src_layout_donor_mints_a_task_that_declares_where_its_code_is(
    tmp_path: Path,
) -> None:
    """The layout the flat donor above cannot exercise, mined end to end through the CLI.

    Every other fixture in this suite keeps its code at the repository root, where
    ``python -m pytest`` puts it at ``sys.path[0]`` and nothing can shadow it. That is a property
    of the fixtures, not of the miner, and it hid a real defect: ``uv sync`` installed the donor's
    project **editable at the provisioning checkout**, so a ``src``-layout donor's tests imported
    that directory rather than the one under verification — and a task PASSED with no patch
    applied. See ``tests/adversarial/test_inert_checkout.py``.

    **The strongest assertion here is that the mint produced anything at all**, because every
    minted task goes through ``liveness.prove_live``, which runs the shipped reward twice and
    demands FAIL with no patch and PASS with the reference one. A miner that recorded the wrong
    import roots, or that provisioned in one checkout and derived in another, cannot get a task
    past that: the no-patch arm would find the fix somewhere else and the task would be discarded
    as vacuous. The manifest assertions below say *why* it worked; the exit code says *that* it
    did.
    """
    donor = build_donor(tmp_path, src_layout_history(tmp_path / "scratch"), name="src-donor")
    out = tmp_path / "local" / "src-donor"

    code = main(
        [
            "mine",
            "--donor",
            str(donor),
            "--label",
            "donor-x",
            "--out",
            str(out),
            "--tasks-root",
            str(tmp_path / "tasks"),
            "--limit",
            "1",
        ]
    )

    assert code == PASS_EXIT, "the src-layout donor minted nothing, so nothing below is asserted"
    task = load_tasks(out)[0]
    assert task.environment.import_roots == ("src",), (
        f"the minted task declares {task.environment.import_roots}, so the reward would not put "
        f"this checkout's code ahead of anything installed"
    )
    assert task.fail_to_pass == ("tests/test_addition.py::test_add_is_addition",)
    assert task.pass_to_pass == ("tests/test_addition.py::test_adding_zero_is_the_identity",)


def test_the_same_seed_mints_the_same_tasks() -> None:
    """Byte for byte, PRD G4. Asserted on the selection rather than on two full mints.

    `select` is where the determinism lives — it sorts before it shuffles, so the draw depends on
    the seed and not on history order, on a set's iteration order, or on the machine. Two full
    mints would assert the same property at ten sandboxed pytest runs apiece; this asserts it on
    the function that owns it, and the end-to-end fixture above proves that function is wired in.
    """
    pool = [
        Candidate(
            sha=f"{index:040x}",
            parent=f"{index - 1:040x}",
            subject=f"commit {index}",
            held_tests=("tests/test_x.py",),
            source_paths=("x.py",),
            other_paths=(),
        )
        for index in range(1, 12)
    ]

    assert select(pool, limit=3, seed=7) == select(pool, limit=3, seed=7)
    assert select(list(reversed(pool)), limit=3, seed=7) == select(pool, limit=3, seed=7)
    assert select(pool, limit=3, seed=8) != select(pool, limit=3, seed=7), (
        "two different seeds drew the same order, so the seed is not deciding anything"
    )


def test_an_unseeded_selection_is_deterministic_too() -> None:
    """No seed is not "arbitrary order": it is the oldest first, by sha, every time."""
    pool = [
        Candidate(
            sha=f"{index:040x}",
            parent="",
            subject="",
            held_tests=(),
            source_paths=(),
            other_paths=(),
        )
        for index in (3, 1, 2)
    ]
    assert [candidate.sha for candidate in select(pool, limit=3)] == [
        f"{index:040x}" for index in (1, 2, 3)
    ]


def test_a_limit_of_zero_is_a_usage_error(
    donor: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Not a silent empty corpus. Mining nothing and exiting 0 claims a corpus that is not there.

    It is the same refusal `load_task_directory` makes about an empty directory, made one step
    earlier: a set with nothing in it that reduces to success is the cheapest way to fake a
    perfect night.
    """
    code = main(
        [
            "mine",
            "--donor",
            str(donor),
            "--label",
            "donor-x",
            "--out",
            str(tmp_path / "out"),
            "--tasks-root",
            str(tmp_path),
            "--limit",
            "0",
        ]
    )
    assert code == USAGE_ERROR
    # Named, so the assertion cannot be satisfied by argparse rejecting something else — an
    # exit-code test that passes because the subcommand does not exist yet tests nothing.
    assert "--limit" in capsys.readouterr().err
    assert not (tmp_path / LEDGER_NAME).exists(), "a rejected invocation still wrote evidence"


def test_a_donor_that_is_not_a_repository_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """"You pointed me at the wrong directory" is a typo, not a finding about a corpus."""
    empty = tmp_path / "not-a-repo"
    empty.mkdir()
    code = main(
        [
            "mine",
            "--donor",
            str(empty),
            "--label",
            "donor-x",
            "--out",
            str(tmp_path / "out"),
            "--tasks-root",
            str(tmp_path),
            "--limit",
            "1",
        ]
    )
    assert code == USAGE_ERROR
    assert str(empty) in capsys.readouterr().err


def test_a_donor_with_no_lockfile_mints_nothing_and_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A mint that produced no task must not exit 0.

    The donor here is mintable in every other respect and simply cannot be provisioned, which is
    the shape `environment.capture` refuses by name. Exiting 0 would tell a caller a corpus
    exists; the reason is printed so the operator knows it is the lockfile and not their history.
    """
    donor = build_donor(tmp_path)
    code = main(
        [
            "mine",
            "--donor",
            str(donor),
            "--label",
            "donor-x",
            "--out",
            str(tmp_path / "out"),
            "--tasks-root",
            str(tmp_path),
            "--limit",
            "1",
        ]
    )
    assert code == FAIL_EXIT
    assert "uv.lock" in capsys.readouterr().out
    assert not (tmp_path / LEDGER_NAME).exists(), "an empty mint still wrote a ledger"
