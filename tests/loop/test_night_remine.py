"""The night re-mines before it draws: the block, the root union, and the record.

`run_night` gains four re-mine parameters and, when donors are given, runs the re-mine at the
**top** — after the offline pin and before `load_task_roots(tasks)` — so the grown corpus is what
`freeze()` computes the contract over and what the draws see. The properties asserted here, with
the miner injected (a real mint is hours), are the ones the night owns:

* the minted `(task_id, donor)` pairs reach the ledger's `task_set.remined`;
* the re-mine is handed the **existing** corpus's sha12 set;
* a `remine_out` already among `--tasks` is not loaded twice (`roots` counts the deduplicated
  union, and no task is drawn twice);
* a night with no re-mine flags records **no** `remined` key (the no-flag path; `record` owns the
  byte-identity proof).

The night is `tests/loop/test_night.py`'s `_night` helper — the same injected engine/trainer/
runtime — never a second harness.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from fixtures.repos.mined import build_mined_task

from loop.test_night import _night
from whetstone.bakeoff.run import load_task_roots
from whetstone.loop import ledger as run_ledger
from whetstone.loop import night as night_module
from whetstone.loop.remine import DonorOutcome, RemineReport, corpus_shas


def _rollout_ids(night: night_module.Night) -> set[str]:
    """Every task id that reached a rollout record, across every draw and source."""
    return {
        record.task_id
        for draw in night.drawn
        for run in draw.runs.values()
        for record in run.rollouts
    }


class _FakeRemine:
    """A stand-in for `whetstone.loop.remine.remine` that copies a real manifest into `out`.

    The donor the manifest names stays on disk under `tmp_path`, so the night's control arm can
    re-derive its reference patch exactly as it does for the harness's own fixtures. Every call's
    arguments are recorded, so a test can assert what the night handed the re-mine.
    """

    def __init__(self, manifest: Path, minted_id: str) -> None:
        self.manifest = manifest
        self.minted_id = minted_id
        self.calls: list[dict[str, Any]] = []

    def __call__(self, donors: Any, **arguments: Any) -> RemineReport:
        self.calls.append({"donors": donors, **arguments})
        out = Path(arguments["out"])
        out.mkdir(parents=True, exist_ok=True)
        shutil.copy(self.manifest, out / self.manifest.name)
        return RemineReport(
            minted=((self.minted_id, "donor-x"),),
            donors=(DonorOutcome("donor-x", Path("/d"), (self.minted_id,), ()),),
        )


def _manifest_writer(tmp_path: Path, minted_id: str) -> _FakeRemine:
    """Build a real mined manifest under `tmp_path` and return a fake re-mine that copies it in."""
    build_mined_task(
        tmp_path / "remine-mined", task_id=minted_id, subject=f"Fix addition ({minted_id})"
    )
    return _FakeRemine(tmp_path / "remine-mined" / f"{minted_id}.json", minted_id)


def test_a_remine_night_records_the_minted_pairs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC1: the minted pair lands in `task_set.remined`, and the minted task reaches a rollout."""
    minted_id = "donor-x-" + "a" * 12
    fake = _manifest_writer(tmp_path, minted_id)
    monkeypatch.setattr(night_module, "remine", fake)

    night = _night(
        tmp_path,
        answers={},
        remine_donors=(Path("/tmp/donor"),),
        remine_labels=("donor-x",),
        remine_out=tmp_path / "remined",
        remine_limit=1,
    )

    recorded = run_ledger.read(night.ledger)
    assert recorded["task_set"]["remined"] == [{"task_id": minted_id, "donor": "donor-x"}], (
        f"WHY THIS IS A FAILURE: the ledger's task_set.remined is "
        f"{recorded['task_set'].get('remined')!r}, not the minted pair. The re-mine delta is the "
        "one record of what the night added, and the record aspect serializes what the night "
        "computes here"
    )
    assert minted_id in _rollout_ids(night), (
        f"WHY THIS IS A FAILURE: the minted task {minted_id!r} was recorded but never drawn "
        "against. The re-mine must grow the corpus the draws see, not merely the ledger"
    )


def test_remine_receives_the_existing_corpus_shas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The re-mine is incremental against exactly the corpus `--tasks` loaded."""
    minted_id = "donor-x-" + "b" * 12
    fake = _manifest_writer(tmp_path, minted_id)
    monkeypatch.setattr(night_module, "remine", fake)

    _night(
        tmp_path,
        answers={},
        remine_donors=(Path("/tmp/donor"),),
        remine_labels=("donor-x",),
        remine_out=tmp_path / "remined",
        remine_limit=1,
    )

    assert len(fake.calls) == 1, fake.calls
    expected = corpus_shas(load_task_roots((tmp_path / "corpus" / "private",)))
    assert fake.calls[0]["existing"] == expected, (
        f"WHY THIS IS A FAILURE: the re-mine's existing set is {fake.calls[0]['existing']!r}, "
        f"not the loaded corpus's {expected!r}. The skip-set is the held-out invariant — every "
        "held-out member's sha is in it — so a wrong set is a hole in that guarantee"
    )


def test_remine_out_is_not_loaded_twice_when_already_listed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-R3: `remine_out` already among `--tasks` is not double-loaded; `roots` is the union."""
    minted_id = "donor-x-" + "c" * 12
    build_mined_task(
        tmp_path / "remine-mined", task_id=minted_id, subject=f"Fix addition ({minted_id})"
    )
    remine_out = tmp_path / "remined"
    remine_out.mkdir(parents=True)
    shutil.copy(
        tmp_path / "remine-mined" / f"{minted_id}.json",
        remine_out / f"{minted_id}.json",
    )

    def fake(donors: Any, **arguments: Any) -> RemineReport:
        return RemineReport(
            minted=(), donors=(DonorOutcome("donor-x", Path("/d"), (), ()),)
        )

    monkeypatch.setattr(night_module, "remine", fake)
    private = tmp_path / "corpus" / "private"

    night = _night(
        tmp_path,
        answers={},
        tasks=(private, remine_out),
        remine_donors=(Path("/tmp/donor"),),
        remine_labels=("donor-x",),
        remine_out=remine_out,
        remine_limit=1,
    )

    recorded = run_ledger.read(night.ledger)
    assert recorded["task_set"]["roots"] == 2, (
        f"WHY THIS IS A FAILURE: task_set.roots is {recorded['task_set']['roots']}, not the "
        "deduplicated union (2). Loading remine_out twice would let the night draw a task twice"
    )
    assert recorded["task_set"]["private"] == 2, (
        f"WHY THIS IS A FAILURE: the private count is {recorded['task_set']['private']}, not 2 "
        "(alpha plus the pre-placed minted task). A double-load would count the same task twice"
    )
    for draw in night.drawn:
        private_ids = [
            record.task_id for record in draw.runs[night_module.PRIVATE].rollouts
        ]
        assert len(private_ids) == len(set(private_ids)), (
            f"WHY THIS IS A FAILURE: a private task id reached a rollout more than once within "
            f"one draw: {sorted(private_ids)}. The union must not double-load remine_out"
        )


def test_a_night_without_remine_flags_records_no_remined_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The no-flag path: no re-mine, no `remined` key — the `record` byte-identity path."""
    def explode(*_: Any, **__: Any) -> RemineReport:  # pragma: no cover - must never run
        raise AssertionError("a night with no re-mine flags called the re-mine")

    monkeypatch.setattr(night_module, "remine", explode)

    night = _night(tmp_path)

    assert "remined" not in run_ledger.read(night.ledger)["task_set"], (
        "WHY THIS IS A FAILURE: an unflagged night wrote a task_set.remined key. The invariant "
        "is that a night without the flags is the pre-change night byte for byte"
    )


def test_a_no_op_remine_does_not_load_an_empty_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M4/M7: a re-mine that mints nothing leaves no manifests, and the night proceeds.

    `mine()` creates its `out` before it considers a candidate, so an unprovisionable or
    nothing-new donor leaves an **empty** root. The night's loader refuses an empty directory, so
    appending it would crash the night on exactly the no-op case that must not fail it.
    """
    def fake(donors: Any, **arguments: Any) -> RemineReport:
        Path(arguments["out"]).mkdir(parents=True, exist_ok=True)
        return RemineReport(
            minted=(),
            donors=(DonorOutcome("donor-x", Path("/d"), (), (), "cold cache"),),
        )

    monkeypatch.setattr(night_module, "remine", fake)

    night = _night(
        tmp_path,
        answers={},
        remine_donors=(Path("/tmp/d"),),
        remine_labels=("donor-x",),
        remine_out=tmp_path / "remined",
        remine_limit=1,
    )

    recorded = run_ledger.read(night.ledger)
    assert recorded["task_set"]["remined"] == [], recorded["task_set"].get("remined")
    assert recorded["task_set"]["roots"] == 1, (
        f"WHY THIS IS A FAILURE: roots is {recorded['task_set']['roots']}. The empty re-mine root "
        "was unioned into the loaded corpus, which the strict loader would refuse"
    )


def test_an_absent_donor_does_not_append_a_nonexistent_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`MintFailed` leaves no `out` at all; the night must not try to load a missing root."""
    def fake(donors: Any, **arguments: Any) -> RemineReport:
        assert not Path(arguments["out"]).exists()
        return RemineReport(
            minted=(),
            donors=(DonorOutcome("donor-x", Path("/missing"), (), (), "not a repository"),),
        )

    monkeypatch.setattr(night_module, "remine", fake)

    night = _night(
        tmp_path,
        answers={},
        remine_donors=(Path("/tmp/missing"),),
        remine_labels=("donor-x",),
        remine_out=tmp_path / "remined",
        remine_limit=1,
    )

    recorded = run_ledger.read(night.ledger)
    assert recorded["task_set"]["remined"] == [] and recorded["task_set"]["roots"] == 1
    assert not (tmp_path / "remined").exists(), "the absent donor's root was created anyway"
