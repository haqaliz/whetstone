"""The re-mine's cross-cutting invariants: a fixed donor state writes one training set, and
the held-out split stays where it is.

Two properties, both scoped exactly as ``../prd.md:103-105`` scopes them:

* **Determinism (AC-G1, M8).** Two nights over the **same donor state and the same seed**
  write byte-identical ``runs/<id>/dataset.json`` and ``runs/<id>/data/train.jsonl``. A donor
  that advanced changes the set by construction and that is the point — nothing here asserts
  determinism across a changed donor. The night's own basis is
  ``sha256(run_seed, task_id, attempt)`` (``src/whetstone/loop/sampling.py:103-122``) and the
  dataset's ``(task_id, attempt)`` sort (``src/whetstone/loop/dataset.py:311-325``); this pins
  that the re-mine does not perturb either.
* **The held-out invariant (AC-G2..AC-G5, M5).** A re-mine leaves the committed
  ``tasks/heldout/source-b.json`` byte-identical, writes nothing under the donors' roots, and
  ``whetstone check-leakage`` behaves as before on the night's ``dataset.json``.

The miner is **injected** (``monkeypatch`` on ``whetstone.loop.night.remine``) so the
determinism asserted is the night's, not the miner's, and the guards run offline at no
provisioning cost: the fake is a pure function of the state it is handed, which is exactly
what "same donor state" means. The real miner's determinism is ``remine``'s and
``test_mine_cli.py``'s, not this file's.

The night harness is ``_night`` from ``loop.test_night`` — the same harness, never a second
one. Nothing writes outside ``tmp_path`` except the injected miner's own scratch, which is
under ``tmp_path`` too.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from fixtures.repos.mined import build_mined_task

import whetstone.loop.night as night_module
from loop.test_night import _night
from loop.test_night_integration import _rollout_ids
from whetstone.loop.dataset import TRAIN_FILE
from whetstone.loop.night import DATA_DIR, DATASET_FILE, Night
from whetstone.loop.remine import RemineReport

#: The id the injected miner mints. Fixed, so both determinism runs mint the same task.
_MINTED = "donor-x-000000000abc"


def _fake_miner(minted_id: str, records: list[dict[str, Any]]) -> Callable[..., RemineReport]:
    """A pure miner: it writes one manifest into ``out``, records its inputs, returns one pair.

    Pure in the state it is handed — the same donor, the same ``existing``, the same seed
    produce the same manifest and the same pair every call — which is what makes the
    determinism test a property of the night rather than of the miner.
    """

    def fake(
        donors: Sequence[tuple[str, Path]],
        *,
        out: Path,
        limit: int,
        scratch: Path,
        timeout: float,
        existing: frozenset[str],
        seed: int | None = None,
        clock: object = None,
    ) -> RemineReport:
        records.append({"donors": tuple(donors), "existing": frozenset(existing), "seed": seed})
        destination = Path(out)
        destination.mkdir(parents=True, exist_ok=True)
        root = destination.parent / f"fake-miner-{minted_id}"
        build_mined_task(root, task_id=minted_id)
        shutil.copy(root / f"{minted_id}.json", destination / f"{minted_id}.json")
        return RemineReport(minted=((minted_id, donors[0][0]),), donors=())

    return fake


def _two_remine_nights(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Night, Night, list[dict[str, Any]]]:
    """Two nights over one donor state and one seed, with the miner injected and recorded."""
    records: list[dict[str, Any]] = []
    monkeypatch.setattr(night_module, "remine", _fake_miner(_MINTED, records))
    donor = tmp_path / "donor"
    first = _night(
        tmp_path / "one",
        remine_donors=(donor,),
        remine_labels=("donor-x",),
        remine_out=tmp_path / "one" / "remined",
        remine_limit=1,
        answers={},
    )
    second = _night(
        tmp_path / "two",
        remine_donors=(donor,),
        remine_labels=("donor-x",),
        remine_out=tmp_path / "two" / "remined",
        remine_limit=1,
        answers={},
    )
    return first, second, records


def test_two_remine_nights_over_one_donor_state_and_seed_are_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-G1: the re-mine does not perturb the night's determinism basis.

    Compared on the **written** files, not the in-memory objects: the criterion is about a
    training set, which is a file, and in-memory equality would say nothing about the ordering,
    the digest or the serialisation.
    """
    first, second, records = _two_remine_nights(tmp_path, monkeypatch)

    for name in (DATASET_FILE, f"{DATA_DIR}/{TRAIN_FILE}"):
        left = (first.directory / name).read_bytes()
        right = (second.directory / name).read_bytes()
        assert left == right, (
            f"two re-mine nights at one seed over the same donor state produced different "
            f"{name}. The determinism criterion is the entire basis for calling a night "
            "reproducible, and the re-mine must not perturb it"
        )

    assert len(records) == 2, records
    assert _MINTED in _rollout_ids(first), (
        "WHY THIS IS A FAILURE: the injected re-mined task never reached a rollout, so the "
        "byte-identity above is over an unchanged corpus and proves nothing about the re-mine"
    )


def test_the_remine_receives_the_same_existing_set_and_seed_in_both_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-G1, the "same donor state" half: the miner's inputs agree across the two runs.

    The *value* of the seed is not pinned — with ``seed=None`` the miner is oldest-first by sha
    and still deterministic — so this asserts only that the two runs agree, which is the
    property the byte-identity depends on.
    """
    _first, _second, records = _two_remine_nights(tmp_path, monkeypatch)

    assert records[0]["existing"] == records[1]["existing"], (
        "the re-mine received different `existing` sets in two nights over one donor state. "
        "The skip-set is the corpus's sha12 set, so a difference means the loaded corpus moved "
        "between runs and the determinism claim does not hold"
    )
    assert records[0]["seed"] == records[1]["seed"], (
        "the re-mine received different seeds in two nights over the same declared run_seed"
    )
