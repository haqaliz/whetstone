"""The filter end to end: what it mints, what it refuses, and the fact that nothing vanishes.

Three properties are asserted here, and they are the ones the published funnel rests on.

**Nothing vanishes.** Every instance handed to the filter comes out as either a manifest or a
ledgered rejection carrying the gate that made it. The loop is tested with a stub gate runner
rather than a stubbed network, so the conservation property is asserted about the real loop while
the gates keep their own tests: what is being checked here is bookkeeping, and bookkeeping is
exactly where a silent drop hides.

**The manifest a survivor produces round-trips through `load_task`.** Not "looks right" —
`load_task` is the loader the reward uses, it rejects unknown fields, non-canonical blob paths,
ranges in pins and nested provenance, and a manifest that only nearly satisfies it fails one
instance at a time, a whole filter run later.

**A test file the test patch ADDS is refused, by name.** SWE-bench's test patches frequently add
new files, and `strict.py` answers UNVERIFIED for a task whose `test_blobs` are not in the
checkout at `base_commit` — forever, for everyone. Relaxing that guard is explicitly out of
scope, so the honest move is to reject the instance at a gate and say why. Asserted against a
real git repository, because the check is a question about a tree.

Offline: a real local git repository, no clone from a network, no model.
"""

from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path

import pytest

from whetstone.tasks.fetch import Instance
from whetstone.tasks.gates import GATE_COLLECTABILITY, GATE_FORMAT, Ineligible, read_ineligible
from whetstone.tasks.public import declared, filter_instances, held_for, manifest_for
from whetstone.verify.task import load_task


def _instance(instance_id: str = "pallets__flask-5063", **overrides: object) -> Instance:
    fields: dict[str, object] = {
        "instance_id": instance_id,
        "repo": "pallets/flask",
        "base_commit": "0" * 40,
        "environment_setup_commit": "0" * 40,
        "problem_statement": "a statement",
        "patch": "diff --git a/src/flask/cli.py b/src/flask/cli.py\n",
        "test_patch": "diff --git a/tests/test_cli.py b/tests/test_cli.py\n",
        "fail_to_pass": ("tests/test_cli.py::test_new",),
        "pass_to_pass": ("tests/test_cli.py::test_old",),
    }
    fields.update(overrides)
    return Instance(**fields)  # type: ignore[arg-type]


def _git(args: list[str], *, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True
    ).stdout


def _repo(root: Path, files: dict[str, str]) -> tuple[Path, str]:
    """A real git repository with one commit, and that commit's sha."""
    repo = root / "repo"
    repo.mkdir(parents=True)
    for relative, contents in files.items():
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents)
    _git(["init", "--quiet", "--initial-branch=main"], cwd=repo)
    _git(["-c", "user.email=t@t", "-c", "user.name=t", "add", "--all"], cwd=repo)
    _git(
        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "--quiet", "-m", "base"],
        cwd=repo,
    )
    return repo, _git(["rev-parse", "HEAD"], cwd=repo).strip()


# --------------------------------------------------------------------------------------
# C4 — the declared sets are deduplicated and disjoint before anything is spent on them
# --------------------------------------------------------------------------------------


def test_an_id_listed_in_both_sets_is_kept_only_as_fail_to_pass() -> None:
    """SWE-bench's two lists commonly overlap, and `load_task` refuses an overlap outright.

    Resolved in favour of `fail_to_pass` because that is the stronger claim: a test that must go
    green is also a test that must end green, so dropping it from `pass_to_pass` loses nothing.
    The reverse would drop a required flip.
    """
    fail, passing = declared(
        _instance(
            fail_to_pass=("a.py::x",),
            pass_to_pass=("a.py::x", "a.py::y"),
        )
    )

    assert fail == ("a.py::x",)
    assert passing == ("a.py::y",)


def test_a_repeated_id_is_collapsed() -> None:
    """`load_task` rejects a duplicate, because it makes the executed-set comparison ambiguous."""
    fail, passing = declared(
        _instance(fail_to_pass=("a.py::x", "a.py::x"), pass_to_pass=("a.py::y", "a.py::y"))
    )

    assert fail == ("a.py::x",)
    assert passing == ("a.py::y",)


def test_the_order_the_dataset_declared_is_preserved() -> None:
    """Sorted output would be tidier and would lose a fact the dataset carries for free."""
    fail, _ = declared(_instance(fail_to_pass=("b.py::x", "a.py::y")))

    assert fail == ("b.py::x", "a.py::y")


# --------------------------------------------------------------------------------------
# The held set, and the test patch that adds a file
# --------------------------------------------------------------------------------------


def test_a_test_patch_that_only_modifies_existing_files_is_held(tmp_path: Path) -> None:
    """The ordinary case: the touched test files, plus the conftest floor above them."""
    repo, sha = _repo(
        tmp_path,
        {
            "conftest.py": "",
            "tests/conftest.py": "",
            "tests/test_cli.py": "def test_old():\n    assert True\n",
            "src/flask/__init__.py": "",
        },
    )
    patch = (
        "diff --git a/tests/test_cli.py b/tests/test_cli.py\n"
        "--- a/tests/test_cli.py\n"
        "+++ b/tests/test_cli.py\n"
        "@@ -1,2 +1,4 @@\n"
        " def test_old():\n"
        "     assert True\n"
        "+def test_new():\n"
        "+    assert True\n"
    )

    held = held_for(repo, sha, patch)

    assert held == ("conftest.py", "tests/conftest.py", "tests/test_cli.py")


def test_a_test_patch_that_adds_a_new_test_file_is_rejected_by_name(tmp_path: Path) -> None:
    """The instance class SWE-bench is full of, refused rather than relaxed.

    `strict.py` answers UNVERIFIED for a task declaring `test_blobs` that are not in the checkout
    at `base_commit` — there is nothing to restore them over, and the task is malformed rather
    than the patch being wrong. Relaxing that guard is out of scope by name: it is a fail-closed
    guard on the reward path. So the instance is refused, at a gate, with the added paths in the
    message.
    """
    repo, sha = _repo(tmp_path, {"tests/test_cli.py": "def test_old():\n    assert True\n"})
    patch = (
        "diff --git a/tests/test_new_feature.py b/tests/test_new_feature.py\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/tests/test_new_feature.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+def test_new():\n"
        "+    assert True\n"
    )

    with pytest.raises(Ineligible) as raised:
        held_for(repo, sha, patch)

    assert raised.value.gate == GATE_COLLECTABILITY
    assert "tests/test_new_feature.py" in str(raised.value)
    assert "base_commit" in str(raised.value)


# --------------------------------------------------------------------------------------
# The manifest a survivor produces
# --------------------------------------------------------------------------------------


def test_the_manifest_round_trips_through_the_reward_s_own_loader(tmp_path: Path) -> None:
    """`load_task` is the check, because `load_task` is what the reward will use.

    A manifest that only nearly satisfies it fails one instance at a time, a whole filter run
    later, with a message about a file rather than about the ingester that wrote it.
    """
    repo, sha = _repo(tmp_path, {"tests/test_cli.py": "def test_old():\n    assert True\n"})
    document = manifest_for(
        _instance(base_commit=sha),
        checkout=repo,
        held=("tests/test_cli.py",),
        python="3.12",
        pins=("click==8.1.3",),
        import_roots=("src",),
        filtered_at="2026-07-28T00:00:00Z",
    )
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")

    task = load_task(path)

    assert task.task_id == "pallets__flask-5063"
    assert task.source == "public"
    assert task.repo_url == "https://github.com/pallets/flask.git"
    assert task.environment.pins == ("click==8.1.3",)
    assert task.environment.import_roots == ("src",)


def test_the_held_blob_carries_the_checkout_s_bytes_exactly(tmp_path: Path) -> None:
    """The blob is read from the checkout the test patch was applied to, byte for byte.

    Not decoded and re-encoded on the way: `test_blobs` is compared byte-for-byte downstream, and
    a round trip through this process's text handling would translate a line ending the reward
    would then report as a difference nobody made.
    """
    contents = "def test_old():\r\n    assert True\r\n"
    repo, sha = _repo(tmp_path, {"tests/test_cli.py": contents})
    document = manifest_for(
        _instance(base_commit=sha),
        checkout=repo,
        held=("tests/test_cli.py",),
        python="3.12",
        pins=(),
        import_roots=(),
        filtered_at="2026-07-28T00:00:00Z",
    )

    blobs = document["test_blobs"]
    assert isinstance(blobs, dict)
    assert base64.b64decode(blobs["tests/test_cli.py"]) == (repo / "tests/test_cli.py").read_bytes()


def test_the_manifest_records_where_it_came_from(tmp_path: Path) -> None:
    """Provenance is what makes P3's train/held-out split auditable later, and it is flat.

    `load_task` rejects a nested provenance value outright, so the shape is asserted here rather
    than discovered when the first manifest fails to load.
    """
    repo, sha = _repo(tmp_path, {"tests/test_cli.py": "def test_old():\n    assert True\n"})
    document = manifest_for(
        _instance(base_commit=sha),
        checkout=repo,
        held=("tests/test_cli.py",),
        python="3.12",
        pins=(),
        import_roots=(),
        filtered_at="2026-07-28T00:00:00Z",
    )

    provenance = document["provenance"]
    assert isinstance(provenance, dict)
    assert provenance["dataset"].startswith("princeton-nlp/")
    assert provenance["instance_id"] == "pallets__flask-5063"
    assert provenance["filtered_at"] == "2026-07-28T00:00:00Z"
    assert all(isinstance(value, str) for value in provenance.values())


# --------------------------------------------------------------------------------------
# The loop: nothing vanishes
# --------------------------------------------------------------------------------------


def test_every_input_is_either_minted_or_ledgered(tmp_path: Path) -> None:
    """The conservation property, asserted about the real loop with the gates stubbed out.

    Stubbing the gates rather than the network is the point: what is under test here is the
    bookkeeping, and bookkeeping is exactly where an instance disappears without anybody's
    assertion firing. The gates keep their own tests, where they are run for real.
    """
    instances = [_instance(f"a__b-{index}") for index in range(5)]

    def run(instance: Instance, **_: object) -> Path:
        if instance.instance_id.endswith(("1", "3")):
            raise Ineligible(GATE_FORMAT, "django form")
        target = tmp_path / "instances" / f"{instance.instance_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}")
        return target

    report = filter_instances(
        instances, out=tmp_path / "instances", tasks_root=tmp_path, run=run
    )

    assert len(report.eligible) == 3
    assert len(report.rejected) == 2
    assert report.ledger is not None

    ledger = read_ineligible(report.ledger)
    assert ledger.counts["input"] == 5
    assert ledger.counts["eligible"] + ledger.counts["ineligible"] == 5


def test_a_rejection_carries_the_gate_that_made_it(tmp_path: Path) -> None:
    """"192 were excluded" is a claim; "192 were excluded at the format gate" is evidence."""

    def run(instance: Instance, **_: object) -> Path:
        raise Ineligible(GATE_COLLECTABILITY, "pytest could not address it")

    report = filter_instances(
        [_instance("a__b-1")], out=tmp_path / "instances", tasks_root=tmp_path, run=run
    )

    assert report.rejected[0].gate == GATE_COLLECTABILITY
    assert "could not address" in report.rejected[0].reason


def test_a_run_in_which_nothing_survives_still_writes_the_ledger(tmp_path: Path) -> None:
    """The empty corpus is the most important one to publish, not the least.

    If source A yields nothing, the ledger of 300 refusals is the entire result — and a filter
    that wrote no file when it minted no task would leave that result nowhere.
    """

    def run(instance: Instance, **_: object) -> Path:
        raise Ineligible(GATE_FORMAT, "django form")

    report = filter_instances(
        [_instance("a__b-1")], out=tmp_path / "instances", tasks_root=tmp_path, run=run
    )

    assert not report.eligible
    assert report.ledger is not None and report.ledger.is_file()
    assert read_ineligible(report.ledger).counts["input"] == 1
