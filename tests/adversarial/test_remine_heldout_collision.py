"""The re-mine's adversarial proof: a colliding mint cannot leak a held-out task.

*A verifier is only worth what it rejects* (``tests/adversarial/test_cheats.py:1-28``). The
reward is protected by the partition seam; this file attacks the **re-mine** seam with a mint
whose identity collides with a held-out member's, and asserts it never reaches a rollout or
the trainable partition.

Two identity notions must agree, and the whole test is about the shape that separates them:

* the run-side exclusion matches held-out membership by **exact task id**
  (``src/whetstone/loop/heldout.py``), and
* ``check-leakage`` matches by **trailing-12-hex identity**
  (``src/whetstone/loop/check_leakage.py:494-507``).

A minted id ``donor-x-<sha12>`` sharing a member's ``<sha12>`` under a **different** label is
therefore the shape the two notions disagree about. The resolved mechanism (``../guards/spec.md``
R4, 2026-10-11) is the re-mine's skip-set: it is the loaded corpus's trailing-12-hex id set, and
``exclude_heldout`` requires every held-out member to resolve in that same corpus — so every
member's ``<sha12>`` is already in ``skip`` before a candidate is considered, and a colliding
commit is never minted.

The test therefore has two halves, named as such in their docstrings:

* the **exclusion** half runs a real re-mine night with an injected miner that would mint the
  colliding task *unless* the held-out identity is in the skip-set it receives, and asserts the
  colliding id is absent from ``_rollout_ids(night)`` and from the trainable partition;
* the **detector** half proves the collision is a real identity match — ``check_leakage`` over a
  dataset carrying the colliding id reports it as a leak — so the exclusion above is not the
  vacuous "it was never there".

Nothing writes outside ``tmp_path``. No model, no ``mlx``, no network.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from fixtures.repos.mined import build_mined_task
from loop.test_gate import _heldout_document
from loop.test_night import _night
from loop.test_night_integration import _rollout_ids

import whetstone.loop.night as night_module
from whetstone.loop import check_leakage, night
from whetstone.loop.remine import RemineReport

#: The trailing-12-hex identity shared by the held-out member and the colliding mint.
_SHA12 = "000000000abc"

#: The held-out member, named by its label. It resolves in the loaded corpus, so its identity
#: is in the re-mine's skip-set before any candidate is considered.
_HELD_MEMBER = f"donor-a-{_SHA12}"

#: The colliding mint: the same identity under a different label, which exact-id exclusion does
#: not catch and identity matching does.
_COLLIDING = f"donor-x-{_SHA12}"

#: Eleven tasks ending in a 12-hex identity — the shape ``check_leakage`` matches on. The
#: membership holds out ten (the colliding member among them), leaving the eleventh to draw.
_OTHERS = tuple(f"donor-a-{n:012x}" for n in range(1, 11))
_IDS = (_HELD_MEMBER, *_OTHERS)
_MEMBERS = _IDS[:10]
_SURVIVOR = _IDS[10]


def _collision_miner(records: list[dict[str, Any]]) -> Callable[..., RemineReport]:
    """An injected miner that mints the colliding task **unless** it is in the skip-set.

    This is the counterfactual made executable: if the night did not pass the held-out
    membership's identity into ``existing``, this miner would write the colliding manifest into
    ``remine_out``, the root would be unioned, and ``donor-x-<sha12>`` — matched by no exact-id
    membership — would reach a rollout. That the test observes the opposite is the proof the
    skip-set mechanism holds.
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
        records.append({"existing": frozenset(existing), "donors": tuple(donors)})
        if _SHA12 in existing:
            return RemineReport(minted=(), donors=())
        destination = Path(out)
        destination.mkdir(parents=True, exist_ok=True)
        root = destination.parent / "collision-miner"
        build_mined_task(root, task_id=_COLLIDING)
        shutil.copy(root / f"{_COLLIDING}.json", destination / f"{_COLLIDING}.json")
        return RemineReport(minted=((_COLLIDING, donors[0][0]),), donors=())

    return fake


def test_a_colliding_remine_does_not_reach_a_rollout_or_training(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The **exclusion** half: the colliding mint never reaches a rollout or the training set.

    The miner writes the colliding task only when its identity is absent from the skip-set, so
    the assertions below are about the night's skip-set rather than about the fixture's shape —
    and the skip-set is asserted to carry the held-out identity, which is the mechanism.
    """
    document = _heldout_document(tmp_path / "doc", _MEMBERS, corpus_ids=_IDS)
    records: list[dict[str, Any]] = []
    monkeypatch.setattr(night_module, "remine", _collision_miner(records))

    result = _night(
        tmp_path,
        private_ids=_IDS,
        heldout=document,
        remine_donors=(tmp_path / "donor",),
        remine_labels=("donor-x",),
        remine_out=tmp_path / "remined",
        remine_limit=1,
        answers={},
    )

    assert records, "the injected miner was never called, so this test proves nothing"
    assert _SHA12 in records[0]["existing"], (
        "WHY THIS IS A FAILURE: the skip-set the miner received does not contain the held-out "
        "member's identity. The held-out membership resolves in the loaded corpus, and the "
        "re-mine's `existing` is that corpus's trailing-12-hex id set, so the identity must be "
        "there before any candidate is considered — that is the mechanism that stops a "
        "colliding commit from being minted"
    )
    assert _COLLIDING not in _rollout_ids(result), (
        f"WHY THIS IS A FAILURE: the colliding task {_COLLIDING!r} reached a rollout: "
        f"{_rollout_ids(result)}. It shares a held-out member's identity under a different "
        "label, which exact-id exclusion alone does not catch"
    )
    assert _COLLIDING not in {example.task_id for example in result.dataset.examples}, (
        f"WHY THIS IS A FAILURE: the colliding task {_COLLIDING!r} reached the trainable "
        "partition. A checkpoint trained on a task a held-out member shares an identity with "
        "is not gated"
    )


def test_the_identity_match_would_catch_the_collision() -> None:
    """The **detector** half: the collision is a real identity match, not a vacuous absence.

    Without this, the exclusion above could pass because the ids never collided at all. Here
    the collision is handed directly to ``check-leakage``, which names the held-out member the
    colliding training id matched on its trailing-12-hex identity.
    """
    report = check_leakage.check_overlap({night.PRIVATE: (_COLLIDING,)}, (_HELD_MEMBER,))

    assert report.clean is False, (
        "the colliding id was not reported as a leak, so the two identities do not actually "
        "agree and the exclusion half proves nothing"
    )
    assert report.overlap == (_HELD_MEMBER,), (
        f"the leak did not name the held-out member: {report.overlap!r}. The collision is a "
        "match on trailing-12-hex identity, so the held-out side is what must be named"
    )
    assert report.leaked_examples == 1, report.leaked_examples
