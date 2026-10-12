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

import hashlib
import shutil
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from fixtures.repos.mined import build_mined_task

import whetstone.loop.night as night_module
from loop.test_gate import _heldout_document
from loop.test_heldout_document import REPO_ROOT, _primary_root
from loop.test_night import _night
from loop.test_night_integration import _rollout_ids
from whetstone.loop import check_leakage
from whetstone.loop.dataset import TRAIN_FILE
from whetstone.loop.night import DATA_DIR, DATASET_FILE, Night
from whetstone.loop.remine import RemineReport

#: The committed held-out document whose bytes this file pins (AC-G2).
HELDOUT_DOCUMENT = REPO_ROOT / "tasks" / "heldout" / "source-b.json"

#: The source-B corpus the leakage test is defined over: eleven tasks ending in a 12-hex
#: identity, exactly the shape ``check_leakage`` matches on. The membership holds out the
#: first ten, leaving ``_SURVIVOR`` to draw.
_IDS = tuple(f"donor-a-{n:012x}" for n in range(1, 12))
_MEMBERS = _IDS[:-1]
_SURVIVOR = _IDS[-1]

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


# --------------------------------------------------------------------------------------------
# The held-out invariant (AC-G2..AC-G5, M5). The re-mine writes under the operator-named root
# and nowhere else; the committed document and the donors' roots are left exactly as they were.
# --------------------------------------------------------------------------------------------


def _one_remine_night(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **overrides: Any) -> Night:
    """A single re-mine night with the miner injected, for the held-out invariant tests."""
    records: list[dict[str, Any]] = []
    monkeypatch.setattr(night_module, "remine", _fake_miner(_MINTED, records))
    arguments: dict[str, Any] = {
        "remine_donors": (tmp_path / "donor",),
        "remine_labels": ("donor-x",),
        "remine_out": tmp_path / "remined",
        "remine_limit": 1,
        "answers": {},
    }
    arguments.update(overrides)
    return _night(tmp_path, **arguments)


def _snapshot(roots: Sequence[Path]) -> dict[str, str]:
    """A sorted recursive digest listing of every path under every root.

    Directories are recorded as a marker rather than skipped, so a whole subtree appearing or
    vanishing is a change this sees.
    """
    found: dict[str, str] = {}
    for root in roots:
        for path in sorted(root.rglob("*")):
            relative = str(path.relative_to(root))
            key = f"{root.name}/{relative}"
            found[key] = (
                hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "<dir>"
            )
    return found


def test_the_committed_heldout_document_is_byte_identical_across_a_remine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-G2: the re-mine writes only under its own root, never under ``tasks/``.

    The committed document is the pre-committed pinned input; its ``membership`` and
    ``document_digest`` are the fields that would move if a re-mine edited it, and those are
    what the failure message names.
    """
    before = HELDOUT_DOCUMENT.read_bytes()

    _one_remine_night(tmp_path, monkeypatch)

    after = HELDOUT_DOCUMENT.read_bytes()
    assert before == after, (
        "WHY THIS IS A FAILURE: a re-mine changed tasks/heldout/source-b.json. Its `membership` "
        "and `document_digest` are the pre-committed pinned input; a run that can edit them can "
        "move its own held-out split. The re-mine writes only under the operator-named "
        "training-only root, never under tasks/ (`../prd.md:82-84,140-142`)"
    )


def test_the_remine_root_is_distinct_from_the_donor_roots(tmp_path: Path) -> None:
    """AC-G3: the re-mine root is not the donors' root, and not nested under it.

    A *test* failure, not a runtime refusal: the invariant is that a re-mine could not write
    the donors' roots even by accident, and a root that shared their prefix but was not them
    (a nested ``donor-a/remined``) would still be a write into the corpus.
    """
    remine_out = (tmp_path / "remined").resolve()
    for name in ("donor-a", "donor-b"):
        donor_root = (REPO_ROOT / "tasks" / "local" / name).resolve()
        assert remine_out != donor_root, (
            f"the re-mine root resolves to the committed donor root {donor_root}"
        )
        assert not remine_out.is_relative_to(donor_root), (
            f"the re-mine root {remine_out} is nested under the donor root {donor_root}; a "
            "re-mine must write only its own operator-named training-only root"
        )


def test_the_donor_roots_are_never_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-G3: a re-mine leaves the primary checkout's donor roots byte-for-byte unchanged.

    The recomputation test reads those roots, so a re-mine that wrote into them would change
    what the committed held-out document recomputes to. On CI's plain checkout they do not
    exist and the test skips with a named reason, exactly as ``test_heldout_document.py`` does;
    on the machine that generated the document it runs.
    """
    primary = _primary_root()
    roots = [primary / "tasks" / "local" / name for name in ("donor-a", "donor-b")]
    missing = [str(root) for root in roots if not root.is_dir()]
    if missing:
        pytest.skip(
            "the machine-level source-B corpus is absent here: "
            + ", ".join(missing)
            + " do not exist. CI's plain checkout has no gitignored manifests, so this walk "
            "runs only on the operator's machine"
        )

    before = _snapshot(roots)

    _one_remine_night(tmp_path, monkeypatch)

    assert _snapshot(roots) == before, (
        "WHY THIS IS A FAILURE: a re-mine wrote into the donors' roots. The donors are the "
        "user's own checkouts and the recomputation's input; a run that writes them can change "
        "the committed held-out document's own derivation"
    )


def test_check_leakage_on_a_remine_night_dataset_is_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-G4: ``check-leakage`` behaves as before on a re-mine night's dataset.

    The fixture document holds out ten of the eleven loaded tasks, leaving ``_SURVIVOR`` to
    draw and solve, so the dataset carries source-B examples (the anti-vacuity: a dataset with
    no source-B example raises ``NothingCompared``, and the check would then prove nothing).
    The re-mined id shares no member's trailing-12-hex identity, so the report is clean.
    """
    document = _heldout_document(tmp_path / "doc", _MEMBERS, corpus_ids=_IDS)
    night = _one_remine_night(
        tmp_path, monkeypatch, private_ids=_IDS, heldout=document, answers=None
    )  # `answers=None` restores the solving default, so the survivor reaches the training set

    report = check_leakage.run_check(night.directory, document)

    assert report.clean is True and report.overlap == (), (
        f"WHY THIS IS A FAILURE: a re-mine night's dataset reports a leak: {report.overlap!r}. "
        "The re-mined id must match no held-out member by trailing-12-hex identity"
    )
    assert report.private.examples >= 1, (
        "the check compared no source-B example, so `clean` is vacuous — the survivor's solved "
        "draws are what make the comparison meaningful"
    )


def test_the_heldout_recomputation_test_is_unedited() -> None:
    """AC-G5: ``tests/loop/test_heldout_document.py`` is a tripwire, not a subject.

    That file re-derives the committed document from the primary checkout's donor roots. It is
    the invariant this aspect exists to hold still, so it may not be edited in the same change
    — an edit would make the guard prove something about the edited file rather than about the
    re-mine. The bytes are pinned to the value captured before this aspect touched anything.
    """
    tripped = Path(__file__).resolve().parent / "test_heldout_document.py"
    digest = hashlib.sha256(tripped.read_bytes()).hexdigest()

    assert digest == "207a46aa384dc0edd723c3256aa9392f1bf539be48e341f22a0e8945c4205945", (
        "WHY THIS IS A FAILURE: tests/loop/test_heldout_document.py has been edited. It is a "
        "tripwire, not a subject: its recomputation is the held-out invariant this aspect "
        "holds still, and a guard that edits its own subject proves nothing. Revert the edit, "
        "or if the file legitimately moved, re-capture its hash deliberately in this diff"
    )
