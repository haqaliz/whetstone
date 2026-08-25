"""The night's held-out seam: `--heldout` excludes the split's membership before the freeze.

`PREREGISTRATION.md` § 7.1 closes the held-out split at `tasks/heldout/source-b.json` (aspect 1),
and aspect 2 is the honest half of the gate: leakage is **prevented, not merely detected**. The
night must accept the committed document as a pinned input, exclude its membership at the
partition seam before the contract is frozen, and record the exclusion so `check-leakage` can
prove it (spec AC 1).

The template throughout is the stratum-filter aspect of the easier-stratum unit
(`tests/bakeoff/test_stratum_filter.py`): the loader is consumed by identity, the exclusion
runs at the partition seam, the dev overlay applies on top (dev ∩ held-out is exclusion, never
a refusal), an empty scored private set is refused before `freeze`, source A is always scored
in full, an unflagged run is today's run byte for byte, and the adversarial proofs are watched
failing first.

The fixture document is **hand-built** rather than composed (the `_stratum` precedent): the
loader validates a document against itself, and only the run-side exclusion resolves its
membership against the loaded corpus — so a test can plant a membership the rule would never
select and still reach the check it is about. The digest is sealed through aspect 1's own
`document_digest_of` after any edits, so a doctored field does not hide behind a stale digest.

No model, no `mlx`, no network. The night is the `_night` fixture from `test_night.py` — the
same harness, never a second one — with a stub engine that answers each drawn task's own
reference patch. Nothing writes outside `tmp_path`.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from loop.test_night import _night
from whetstone import cli
from whetstone.loop import heldout
from whetstone.loop import ledger as run_ledger
from whetstone.loop import night as night_module
from whetstone.loop.night import EmptyTaskSet, disclosure

#: The loaded private corpus the fixture documents are defined over. Eleven tasks: ten held
#: out by the fixture document, one ("t-11") left to draw — the shape every night here runs.
_IDS = tuple(f"t-{i:02d}" for i in range(1, 12))

#: A task id that is never in the loaded corpus — the unknown-member shape.
_GHOST = "t-ghost"

#: A declared dev id: a real loaded task a doctored document smuggles into its membership.
_DEV = "t-dev"

#: The members the fixture document holds out: every id but the survivor.
_MEMBERS = _IDS[:-1]


def _heldout_document(
    root: Path, members: Sequence[str], *, corpus_ids: Sequence[str] = _IDS, **fields: Any
) -> Path:
    """A loader-valid `whetstone-heldout/1` document over `corpus_ids` with membership `members`.

    The loader's checks are satisfied by construction: schema, rule digest, every corpus id
    measured and banded, membership a proper subset meeting the pre-committed floors, and the
    `document_digest` sealed through aspect 1's own function **after** `fields` are applied —
    so a doctored field does not hide behind a stale digest, and a test that plants an edit
    reaches the check it is about.
    """
    ordered = sorted(corpus_ids)
    raw: dict[str, Any] = {
        "schema": heldout.HELDOUT_SCHEMA,
        "rule_digest": heldout.rule_digest(),
        "rule": {
            "bands": heldout.HELDOUT_BANDS,
            "min_heldout": heldout.MIN_HELDOUT,
            "min_per_band": heldout.MIN_PER_BAND,
            "split_seed": heldout.SPLIT_SEED,
        },
        "corpus": list(corpus_ids),
        "difficulty": {
            task_id: {
                "files": 1,
                "hunks": 1,
                "added": 1,
                "deleted": 1,
                "f2p": 1,
                "pins": 0,
                "blobs": 1,
            }
            for task_id in corpus_ids
        },
        "bands": {
            task_id: ordered.index(task_id) % heldout.HELDOUT_BANDS for task_id in ordered
        },
        "refusals": {},
        "membership": list(members),
    }
    raw.update(fields)
    raw["document_digest"] = heldout.document_digest_of(raw)
    root.mkdir(parents=True, exist_ok=True)
    out = root / "source-b.json"
    out.write_text(json.dumps(raw))
    return out


def _rollout_ids(night: night_module.Night) -> set[str]:
    """Every task id that reached a rollout record, across every draw and source."""
    return {
        record.task_id
        for draw in night.drawn
        for run in draw.runs.values()
        for record in run.rollouts
    }


def test_the_heldout_document_excludes_every_held_out_id_from_rollouts_and_training(
    tmp_path: Path,
) -> None:
    """AC 1: the membership never reaches a rollout, a posed prompt, or the training set.

    The three derivations of "what the night drew against" must agree — the contract's sealed
    prompt set, the rollouts the draws actually recorded, and the trainable partition the
    dataset selected from them. An exclusion that merely skipped training would leave held-out
    tasks in the evidence; one that skipped drawing would leave them in neither.
    """
    doc = _heldout_document(tmp_path / "doc", _MEMBERS)
    night = _night(tmp_path, private_ids=_IDS, heldout=doc)

    assert set(night.contract.posed.values()) == {"t-11", "pallets__flask-4045"}, (
        "WHY THIS IS A FAILURE: the frozen contract covers a held-out id. The seal is the "
        "audit trail of what was asked, and it must cover exactly the survivors"
    )
    assert _rollout_ids(night) == {"t-11", "pallets__flask-4045"}, (
        f"WHY THIS IS A FAILURE: a held-out id reached a rollout: {_rollout_ids(night)}"
    )
    example_ids = {example.task_id for example in night.dataset.examples}
    assert example_ids == {"t-11", "pallets__flask-4045"}, (
        f"WHY THIS IS A FAILURE: the trainable partition carries a held-out id: {example_ids}"
    )
    assert len(example_ids) == 2 and len(night.dataset.examples) == 4, (
        "WHY THIS IS A FAILURE: the held-out night selected a different training set size "
        "than the survivor tasks' draws would produce — the exclusion moved a count"
    )


def test_source_a_is_always_scored_in_full(tmp_path: Path) -> None:
    """Spec AC 2: the held-out exclusion touches source B only; source A keeps every draw.

    The public instance is not part of the held-out split's scope, and both sources always
    publish together — a night that quietly dropped source A would produce a dataset a reader
    could not place.
    """
    doc = _heldout_document(tmp_path / "doc", _MEMBERS)
    flagged = _night(tmp_path / "flagged", private_ids=_IDS, heldout=doc)
    plain = _night(tmp_path / "plain")

    flagged_public = sum(
        len(run.rollouts) for draw in flagged.drawn for source, run in draw.runs.items()
        if source == night_module.PUBLIC
    )
    plain_public = sum(
        len(run.rollouts) for draw in plain.drawn for source, run in draw.runs.items()
        if source == night_module.PUBLIC
    )
    assert flagged_public == plain_public == 2, (
        f"WHY THIS IS A FAILURE: source A's rollout count changed under --heldout "
        f"({flagged_public} vs {plain_public}). The public source is not part of the "
        "held-out split's scope"
    )
    assert "pallets__flask-4045" in _rollout_ids(flagged)


def test_the_night_uses_aspect_ones_loader_and_filter_by_identity() -> None:
    """The diffcheck identity rule: imported, never copied — and asserted `is`.

    A second loader — or a second exclusion — is a second answer to "what may be held out",
    with only one of them reviewed. The night's seam is aspect 1's module, no other.
    """
    assert night_module.read_document is heldout.read_document, (
        "WHY THIS IS A FAILURE: the night does not consume aspect 1's loader. A copied loader "
        "is a second definition of the pinned input's checks, and the two would drift with "
        "only one of them reviewed"
    )
    assert night_module.exclude_heldout is heldout.exclude_heldout


def test_the_flag_parses_an_optional_path_and_defaults_to_none() -> None:
    """Absent means today's night; given, it is a path, never a string to guess at."""
    from loop.test_night_cli import INVOCATION

    parsed = cli.build_parser().parse_args(INVOCATION)
    assert parsed.heldout is None, (
        f"WHY THIS IS A FAILURE: --heldout defaulted to {parsed.heldout!r}. A default path "
        "would consume a document nobody chose"
    )
    parsed = cli.build_parser().parse_args([*INVOCATION, "--heldout", "/h/source-b.json"])
    assert parsed.heldout == Path("/h/source-b.json")


def test_the_door_forwards_the_heldout_flag_to_the_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--heldout` at the door reaches `run_night(heldout=...)`, not a dead flag."""
    from loop.test_night_cli import INVOCATION, _Checkpoint, _Dataset, _Night

    calls: list[dict[str, Any]] = []

    def fake(**arguments: Any) -> night_module.Night:
        calls.append(arguments)
        return _Night(dataset=_Dataset(), checkpoint=_Checkpoint())  # type: ignore[return-value]

    monkeypatch.setattr(night_module, "run_night", fake)
    assert cli.main([*INVOCATION, "--heldout", "/h/source-b.json"]) == cli.PASS_EXIT

    assert calls[0]["heldout"] == Path("/h/source-b.json"), (
        f"WHY THIS IS A FAILURE: the door passed heldout={calls[0].get('heldout')!r}. A flag "
        "that dies at the door is a flag the runbook advertises and the loop never sees"
    )


def test_the_ledger_records_the_document_digest_and_its_membership_count(
    tmp_path: Path,
) -> None:
    """Spec AC 1: the exclusion is recorded — counts and digests only, never membership.

    The ledger's `task_set.heldout` record is what `check-leakage` reads to prove the night
    excluded the committed document's membership. The digest is the one the document's own
    payload seals, so a reader can match the ledger against the committed file.
    """
    doc = _heldout_document(tmp_path / "doc", _MEMBERS)
    night = _night(tmp_path, private_ids=_IDS, heldout=doc)

    recorded = run_ledger.read(night.ledger)
    assert recorded["task_set"]["heldout"] == {
        "document_digest": heldout.document_digest_of(
            json.loads(doc.read_text(encoding="utf-8"))
        ),
        "membership_count": len(_MEMBERS),
    }, (
        f"WHY THIS IS A FAILURE: the ledger's task_set carries "
        f"{recorded['task_set']['heldout']!r}. The exclusion is unprovable without a record "
        "that names the document and the size of the membership it excluded"
    )


def test_the_disclosure_names_the_document_and_its_membership_count(
    tmp_path: Path,
) -> None:
    """The operator's terminal names the held-out document and the count — the sentence.

    The ledger is under a gitignored root; the disclosure is what the operator sees at the
    end of a night, and it must say the exclusion happened and against which document.
    """
    doc = _heldout_document(tmp_path / "doc", _MEMBERS)
    night = _night(tmp_path, private_ids=_IDS, heldout=doc)

    sentence = next(
        (line for line in disclosure(night) if "held out" in line), None
    )
    assert sentence is not None, (
        f"WHY THIS IS A FAILURE: the disclosure does not name the held-out exclusion: "
        f"{disclosure(night)!r}"
    )
    assert f"held out {len(_MEMBERS)} source-B tasks" in sentence, (
        f"WHY THIS IS A FAILURE: the sentence does not carry the membership count: "
        f"{sentence!r}"
    )
    assert heldout.document_digest_of(json.loads(doc.read_text(encoding="utf-8"))) in sentence, (
        f"WHY THIS IS A FAILURE: the sentence does not name the document (by its digest): "
        f"{sentence!r}"
    )


def test_an_older_ledger_without_the_heldout_record_still_reads(tmp_path: Path) -> None:
    """The record's absence from older ledgers is tolerated, never assumed.

    No real night has run, so every ledger in existence was written by the current code —
    but a ledger written before this aspect landed, or by a tool that omits the record,
    must still read: `read` answers the schema question and nothing else.
    """
    from loop.test_run_ledger import _ledger

    document = json.loads(run_ledger.document(_ledger()))
    assert "heldout" in document["task_set"], (
        "the fixture ledger carries no heldout record, so removing it below would be a "
        "no-op and this test would prove nothing"
    )
    del document["task_set"]["heldout"]
    path = tmp_path / "old-ledger.json"
    path.write_text(json.dumps(document))

    recorded = run_ledger.read(path)
    assert recorded["schema"] == run_ledger.LEDGER_SCHEMA
    assert "heldout" not in recorded["task_set"]


def test_an_empty_scored_private_set_after_the_overlays_is_refused_before_freeze(
    tmp_path: Path,
) -> None:
    """AC 4: the overlays left nothing to draw against, and the night refuses before `freeze`.

    The document holds out every loaded private task (its own corpus carries one more), so
    the dev overlay and the held-out exclusion together leave an empty scored private set.
    Refused by name before the contract is frozen or anything is generated — left alone the
    night would spend hours drawing against source A alone.
    """
    doc = _heldout_document(
        tmp_path / "doc", _IDS, corpus_ids=(*_IDS, "t-extra")
    )
    runs = tmp_path / "runs"

    with pytest.raises(EmptyTaskSet) as refused:
        _night(tmp_path, private_ids=_IDS, heldout=doc, runs=runs)

    message = str(refused.value)
    assert "held-out exclusion" in message, (
        f"WHY THIS IS A FAILURE: the refusal does not name the held-out exclusion: {message!r}"
    )
    assert not (runs / "night-001").exists(), (
        "WHY THIS IS A FAILURE: the refusal happened after the run directory was created, so "
        "it cannot have fired before anything was generated"
    )