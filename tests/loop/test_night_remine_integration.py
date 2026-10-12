"""The re-mine end to end over a real synthetic donor, through the night's own path.

The unit tests inject the miner; this file pays for real mints so the two properties that only a
real `mine()` can expose are asserted:

* **the loaded root stays pure.** `mine()` writes its evidence into `tasks_root`, and the night's
  strict loader refuses any non-manifest entry; the re-mine's evidence goes to a sibling
  `<out>-evidence`, so `load_tasks(out)` accepts a root a real mint wrote into (the blocker this
  suite's first run found, guarded here for good);
* **the whole night works.** A donor's un-minted candidate becomes a manifest in the training-only
  root, is recorded in `task_set.remined`, and is drawn against — and a donor that mints nothing
  (nothing-new, absent, unprovisionable) is a no-op the night proceeds through.

Mining is macOS-only (its pytest runs inside the Seatbelt sandbox, the `tests/test_mine_cli.py`
precedent), so the whole file skips elsewhere. The night itself is `tests/loop/test_night.py`'s
`_night` helper — the injected engine/trainer/runtime — never a second harness.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fixtures.repos.donor import DONOR_HISTORY, build_donor
from fixtures.repos.locked import locked_history, locked_project_files

from loop.harness import TIMEOUT, corpus
from loop.test_night import _night
from whetstone.loop import ledger as run_ledger
from whetstone.loop import night as night_module
from whetstone.loop.remine import remine
from whetstone.tasks.manifest import load_tasks
from whetstone.tasks.mine import LEDGER_NAME

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin",
    reason="mining runs pytest inside the macOS-only Seatbelt sandbox",
)

#: The repository root, for the committed corpus ledger the re-mine must never touch.
REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def donor(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The mining donor, carrying packaging from its seed commit so every parent is lockable."""
    root = tmp_path_factory.mktemp("remine-donor")
    packaging = locked_project_files(root / "packaging", index=None)
    return build_donor(root, locked_history(packaging))


@pytest.fixture(scope="module")
def single_candidate_donor(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A donor whose history holds exactly one mintable candidate (seed + one fix).

    The full donor has several, so a one-mint limit would leave the rest un-minted and a second
    night would legitimately mint the next one. One candidate makes "nothing-new" deterministic.
    """
    root = tmp_path_factory.mktemp("remine-single-donor")
    packaging = locked_project_files(root / "packaging", index=None)
    return build_donor(root, locked_history(packaging, history=DONOR_HISTORY[:2]))


def _rollout_ids(night: night_module.Night) -> set[str]:
    """Every task id that reached a rollout record, across every draw and source."""
    return {
        record.task_id
        for draw in night.drawn
        for run in draw.runs.values()
        for record in run.rollouts
    }


def test_the_real_mine_root_loads_cleanly_with_evidence_in_the_sibling(
    tmp_path: Path, donor: Path
) -> None:
    """The regression guard: a real mint leaves `out` manifest-only, so the loader accepts it."""
    out = tmp_path / "remined"

    report = remine(
        (("donor-x", donor),),
        out=out,
        limit=1,
        scratch=tmp_path / "scratch",
        timeout=TIMEOUT,
        existing=frozenset(),
    )

    assert report.minted, "the synthetic donor minted nothing, so this proves nothing"
    loaded = load_tasks(out)
    assert {task.task_id for task in loaded} == {task_id for task_id, _ in report.minted}, (
        "WHY THIS IS A FAILURE: the night's strict loader refused the root a real mint wrote "
        "into, because the miner's ledger/recipes landed in the loaded root rather than a sibling"
    )
    assert not (out / LEDGER_NAME).exists(), "the miner's ledger is inside the loaded root"
    assert (tmp_path / "remined-evidence" / LEDGER_NAME).is_file(), (
        "WHY THIS IS A FAILURE: the re-mine's evidence is not in the sibling root"
    )


def test_a_remine_night_mints_records_and_draws_a_new_task(
    tmp_path: Path, donor: Path
) -> None:
    """AC1: a new task is minted into the training-only root, recorded, and drawn against."""
    existing_root, _ = corpus(tmp_path / "existing", "private", ("alpha",))
    committed = REPO_ROOT / "tasks" / LEDGER_NAME
    before = committed.read_bytes() if committed.is_file() else None

    night = _night(
        tmp_path,
        tasks=(existing_root,),
        answers={},
        remine_donors=(donor,),
        remine_labels=("donor-x",),
        remine_out=tmp_path / "remined",
        remine_limit=1,
    )

    recorded = run_ledger.read(night.ledger)
    remined = recorded["task_set"]["remined"]
    assert len(remined) == 1, remined
    assert remined[0]["donor"] == "donor-x", remined
    minted_id = remined[0]["task_id"]

    manifests = sorted((tmp_path / "remined").glob("donor-x-*.json"))
    assert len(manifests) == 1, manifests
    assert minted_id in {task.task_id for task in load_tasks(tmp_path / "remined")}, (
        "WHY THIS IS A FAILURE: the recorded task id is not the manifest that was minted"
    )
    assert minted_id in _rollout_ids(night), (
        f"WHY THIS IS A FAILURE: the minted task {minted_id!r} was recorded but never drawn "
        "against. The re-mine must grow the corpus the draws see, not only the ledger"
    )
    assert (tmp_path / "remined-evidence" / LEDGER_NAME).is_file()
    after = committed.read_bytes() if committed.is_file() else None
    assert after == before, (
        "WHY THIS IS A FAILURE: the re-mine wrote the committed corpus ledger "
        f"{str(committed)!r}; the training-only root must be the only evidence it touches"
    )


def test_a_second_night_over_the_same_donor_mints_nothing_and_proceeds(
    tmp_path: Path, single_candidate_donor: Path
) -> None:
    """AC2: a donor with no un-minted candidates is an empty delta, and the night completes."""
    first_root = tmp_path / "first"
    existing_root, _ = corpus(first_root / "existing", "private", ("alpha",))

    first = _night(
        first_root,
        tasks=(existing_root,),
        answers={},
        remine_donors=(single_candidate_donor,),
        remine_labels=("donor-x",),
        remine_out=first_root / "remined",
        remine_limit=1,
    )
    first_pairs = run_ledger.read(first.ledger)["task_set"]["remined"]
    assert len(first_pairs) == 1, first_pairs

    second = _night(
        tmp_path / "second",
        tasks=(existing_root, first_root / "remined"),
        answers={},
        remine_donors=(single_candidate_donor,),
        remine_labels=("donor-x",),
        remine_out=first_root / "remined",
        remine_limit=1,
    )

    assert run_ledger.read(second.ledger)["task_set"]["remined"] == [], (
        "WHY THIS IS A FAILURE: the second night re-minted a candidate the first already had"
    )
    assert second.ledger.is_file()


def test_an_absent_donor_is_a_reported_no_op(tmp_path: Path) -> None:
    """AC2 (M4): a donor that cannot be read as a repository does not fail the night.

    The `MintFailed` shape is a path that is not a git repository (the `tests/test_mine_cli.py`
    "not a repository" fixture), which is what `mine()` turns a git failure into.
    """
    existing_root, _ = corpus(tmp_path / "existing", "private", ("alpha",))
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()

    night = _night(
        tmp_path,
        tasks=(existing_root,),
        answers={},
        remine_donors=(not_a_repo,),
        remine_labels=("donor-x",),
        remine_out=tmp_path / "remined",
        remine_limit=1,
    )

    assert run_ledger.read(night.ledger)["task_set"]["remined"] == []


def test_an_unprovisionable_donor_is_a_reported_no_op(tmp_path: Path) -> None:
    """AC7 (M7): a donor whose every candidate is refused `NotProvisionable` is a no-op."""
    existing_root, _ = corpus(tmp_path / "existing", "private", ("alpha",))
    unlocked = build_donor(tmp_path / "unlocked-root", name="unlocked")

    night = _night(
        tmp_path,
        tasks=(existing_root,),
        answers={},
        remine_donors=(unlocked,),
        remine_labels=("donor-x",),
        remine_out=tmp_path / "remined",
        remine_limit=1,
    )

    assert run_ledger.read(night.ledger)["task_set"]["remined"] == [], (
        "WHY THIS IS A FAILURE: a cold-cache donor failed the night instead of being a no-op"
    )
    assert night.ledger.is_file(), "the night did not complete on the existing corpus"
