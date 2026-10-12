"""The run ledger's re-mine delta: `task_set.remined`, its conditional bytes, and its consumers.

`night-corpus-remine` aspect 2 (`docs/planning/night-corpus-remine/record/`). The ledger already
recorded *which tasks the night drew against*; it recorded nothing about the corpus having
**grown** that night, or from which donor. The re-mine delta lands under the existing `task_set`
claim as `remined` — a list of `(task_id, donor)` pairs, ids and labels only, never contents.

Two properties carry the design:

* **no-flag byte-identity.** `remined` is emitted only when the field is not `None`, so a night
  without the re-mine flags writes the pre-change bytes exactly. An always-present
  `"remined": null` would move every ledger's `task_set` claim and break that; the deliberate
  deviation from `heldout`/`stratum`'s always-present `null` style is the safety property.
* **the seal covers it.** `remined` is nested inside `task_set`, which is one claim, so editing it
  without recomputing the document is a `LedgerUnverified` naming `task_set` — while a forger who
  recomputes `claims`/`digest` is not caught, the documented unkeyed-hash boundary.

No model, no runtime, no network. The fixtures are the shipped `_ledger()` (imported, never
edited — it is a shared fixture and the golden's subject) plus `dataclasses.replace`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from loop.test_run_ledger import _ledger
from whetstone.loop import ledger as run_ledger
from whetstone.loop import seal

#: The pre-change golden: `ledger.document(_ledger())` on the tree before `TaskSet.remined`
#: existed, captured 2026-10-11. It must **not** move: a no-flag night is the pre-change night
#: byte for byte.
GOLDEN_SHA256 = "4fe1022f659fe0b98123dbbf011ace415fd1b9210a6ebee83f6f49ef9aae392d"

#: A re-mine delta in minting order (unsorted): the writer, not the caller, must sort it.
_MINTED = (
    ("task-zeta", "donor-c"),
    ("task-alpha", "donor-b"),
    ("task-alpha", "donor-a"),
)

#: The same delta as the writer must serialize it: sorted by `(task_id, donor)`.
_SORTED = [
    {"task_id": "task-alpha", "donor": "donor-a"},
    {"task_id": "task-alpha", "donor": "donor-b"},
    {"task_id": "task-zeta", "donor": "donor-c"},
]


def _remined(pairs: tuple[tuple[str, str], ...] | None) -> run_ledger.Ledger:
    """The shipped fixture with its `task_set.remined` replaced. `_ledger()` is never edited."""
    base = _ledger()
    return replace(base, task_set=replace(base.task_set, remined=pairs))


def _rewrite(path: Path, document: dict[str, object]) -> None:
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_the_remine_delta_round_trips_sorted_and_ids_only(tmp_path: Path) -> None:
    """AC 1: `(task_id, donor)` pairs round-trip as sorted `{task_id, donor}` dicts.

    The pairs are fed in minting order and read back sorted, so the sort is the writer's and not
    the caller's; each entry carries exactly the two keys, never a third.
    """
    path = run_ledger.write(tmp_path / "ledger.json", _remined(_MINTED))
    recorded = run_ledger.read(path)

    assert recorded["task_set"]["remined"] == _SORTED, (
        f"WHY THIS IS A FAILURE: the re-mine delta did not round-trip sorted: "
        f"{recorded['task_set']['remined']!r}. A caller that minted in another order would "
        "produce different bytes for the same delta"
    )
    for entry in recorded["task_set"]["remined"]:
        assert set(entry) == {"task_id", "donor"}, (
            f"WHY THIS IS A FAILURE: a re-mine entry carries {sorted(entry)}. The ledger's "
            "discipline is ids and labels only, never a third field that could hold content"
        )


def test_the_writer_sorts_at_the_document_boundary() -> None:
    """AC 5: the pure writer emits the sorted list, so the sort is not the read path's doing."""
    document = json.loads(run_ledger.document(_remined(tuple(reversed(_MINTED)))))

    assert document["task_set"]["remined"] == _SORTED, (
        f"WHY THIS IS A FAILURE: `document()` emitted "
        f"{document['task_set']['remined']!r}, not the sorted delta. The serialization boundary "
        "is where the order is fixed, so the same delta is the same bytes whatever order it "
        "was minted in"
    )


def test_none_means_no_remine_block_and_emits_no_key() -> None:
    """AC 3, the no-block half: `None` omits the key entirely — the byte-identity path."""
    document = json.loads(run_ledger.document(_remined(None)))

    assert "remined" not in document["task_set"], (
        f"WHY THIS IS A FAILURE: a ledger with no re-mine block carries a 'remined' key "
        f"({document['task_set'].get('remined')!r}). An always-present key would move every "
        "ledger's bytes, so an unflagged night would not be the pre-change night byte for byte"
    )


def test_an_empty_tuple_means_a_remine_that_minted_nothing() -> None:
    """AC 3, the empty half: `()` is a *recorded* empty delta, distinct from `None`.

    M4's distinction cannot ride on a single boolean: `None` is "no re-mine block ran" and `()`
    is "a re-mine ran and minted nothing", and a reader must be able to tell them apart.
    """
    document = json.loads(run_ledger.document(_remined(())))

    assert document["task_set"].get("remined") == [], (
        f"WHY THIS IS A FAILURE: an empty re-mine delta serialized as "
        f"{document['task_set'].get('remined')!r}, not `[]`. An empty delta that read as an "
        "absent block would conflate 'minted nothing' with 'no re-mine ran'"
    )


def test_the_no_remine_document_is_the_prechange_golden() -> None:
    """AC 2, green-on-arrival and here to stay: the golden bytes must not move.

    The shipped `_ledger()` defaults `remined` to `None`, so the document is the pre-change
    document. This test already passes on the pre-change tree; its job is to fail if the
    conditional ever becomes an always-present key.
    """
    document = run_ledger.document(_ledger())

    assert "remined" not in json.loads(document)["task_set"], (
        "WHY THIS IS A FAILURE: the unmodified fixture carries a 'remined' key, so the "
        "byte-identity claim is broken at the source"
    )
    assert hashlib.sha256(document.encode()).hexdigest() == GOLDEN_SHA256, (
        "WHY THIS IS A FAILURE: the no-flag ledger's bytes moved. A night without the re-mine "
        "flags must write the pre-change document exactly"
    )


def test_the_schema_constant_did_not_move() -> None:
    """AC 9: the field is nested under an existing claim, so no `/4` bump is needed or allowed."""
    assert run_ledger.LEDGER_SCHEMA == run_ledger.LEDGER_SCHEMA_V3


def test_a_mutated_remine_delta_is_refused_by_name(tmp_path: Path) -> None:
    """AC 6: the `task_set` claim covers the nested delta, so an edit is a refusal by name."""
    path = run_ledger.write(tmp_path / "ledger.json", _remined(_MINTED))
    document = json.loads(path.read_text(encoding="utf-8"))
    document["task_set"]["remined"] = []
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnverified, match="task_set"):
        run_ledger.read(path)


def test_a_forger_who_recomputes_the_remine_claims_is_not_caught(tmp_path: Path) -> None:
    """AC 6, the documented limit: the digest is an unkeyed hash, never authentication.

    Recomputing `claims` and `digest` consistently after editing the nested delta produces a
    document this reader accepts and reports `sealed`. That is the boundary the vocabulary states
    (`ledger.py:79-88`), not a defect: the seal catches accident-shaped edits, and anyone who can
    edit the file can recompute both.
    """
    path = run_ledger.write(tmp_path / "ledger.json", _remined(_MINTED))
    document = json.loads(path.read_text(encoding="utf-8"))
    document["task_set"]["remined"] = [{"task_id": "task-forged", "donor": "donor-forged"}]
    body = {key: value for key, value in document.items() if key not in seal.UNSEALED_KEYS}
    document["claims"] = seal.claim_hashes(
        body, subject="ledger", refuse=run_ledger.LedgerUnverified
    )
    document["digest"] = seal.claims_digest(document["claims"], schema=run_ledger.LEDGER_SCHEMA_V3)
    _rewrite(path, document)

    forged = run_ledger.verify_document(path)

    assert forged.sealed is True
    assert forged.document["task_set"]["remined"] == [
        {"task_id": "task-forged", "donor": "donor-forged"}
    ]
