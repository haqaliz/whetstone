"""The night's stratum seam: `--stratum` narrows the draw to a band, without touching the split.

`docs/ROADMAP.md` § 4, P2 pre-commits the response to a zero-yield corpus — *"stratify by
difficulty or raise k — do not weaken the check to manufacture wins"* — and
`PREREGISTRATION.md` § 10.15 takes the first of those. The stratum document has existed at
`tasks/stratum/easier.json` since 2026-08-14 (§ 10.5) and **nothing in the loop could consume
it**, which is why the arm climbed base sizes instead: the pre-committed response had no code
behind it. This aspect is that code.

The template is the held-out seam next door (`test_night_integration.py`), which was itself
built from the bake-off's stratum filter — so this closes the circle rather than opening a
second spelling. `bakeoff.stratum.read_document` and `bakeoff.stratum.include_stratum` are
consumed **by identity**: a second implementation of "which tasks are in the band" would be a
second answer to the question the committed document already answers.

Three properties carry the design, and none are style:

* **The split wins over the band.** A band member that is also held out is excluded, never
  drawn. Held-out protection is the gate's foundation and a narrowing flag must not be able to
  reach past it — so the stratum applies *after* the exclusion, and the test proves the order
  by planting a task in both.
* **The corpus is still loaded in full.** A stratum narrows what is *drawn*; it never narrows
  what is *loaded*. That is what keeps the held-out document resolvable — the failure that
  `UnknownStratumId`'s sibling guard already refuses, and the one this seam exists to avoid
  forcing an operator into.
* **An unflagged night is today's night, byte for byte.** The contract SHA, the seeds and the
  drawn set of a run without `--stratum` must be identical to one built before the flag
  existed, or every figure already recorded becomes non-comparable to every figure after it.

The fixture document is hand-built for the `_heldout_document` reason: the loader validates a
document against itself, and only the run-side inclusion resolves membership against the loaded
corpus, so a test can plant a membership the rule would never select and still reach the check
it is about. Digests are sealed through the module's own functions after any edit.

No model, no `mlx`, no network. Nothing writes outside `tmp_path`.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from loop.test_night import _night
from whetstone.bakeoff import stratum
from whetstone.loop import ledger as run_ledger
from whetstone.loop import night as night_module
from whetstone.loop.night import EmptyTaskSet

#: The loaded private corpus these documents are defined over. Sixteen, because the
#: held-out floor is 10 (`heldout.MIN_HELDOUT`) and a test that holds out a band member
#: still has to leave the rest of the band drawable.
_IDS = tuple(f"t-{i:02d}" for i in range(1, 17))

#: The band: three of the eleven. Small enough that "narrowed" is unmistakable in an assertion.
_BAND = ("t-02", "t-05", "t-09")

#: A task id that is never in the loaded corpus — the unknown-member shape.
_GHOST = "t-ghost"

#: A held-out membership meeting the pre-committed floors (10 members, >=2 per band) that
#: holds out exactly ONE band member, leaving the other two drawable.
_HELD_ONE_BAND_MEMBER = (
    "t-05",
    "t-01",
    "t-03",
    "t-04",
    "t-06",
    "t-07",
    "t-08",
    "t-10",
    "t-11",
    "t-12",
)

#: A held-out membership meeting the same floors that holds out the WHOLE band, so the
#: stratum narrows to nothing.
_HELD_WHOLE_BAND = (
    "t-02",
    "t-05",
    "t-09",
    "t-01",
    "t-03",
    "t-04",
    "t-06",
    "t-07",
    "t-08",
    "t-10",
)


def _stratum_document(
    root: Path, members: Sequence[str], *, corpus_ids: Sequence[str] = _IDS, **fields: Any
) -> Path:
    """A loader-valid `whetstone-stratum/1` document over `corpus_ids` with membership `members`.

    Satisfied by construction: schema, rule digest, every corpus id measured, and the
    `document_digest` sealed through the module's own `document_digest_of` **after** `fields`
    are applied — so a doctored field cannot hide behind a stale digest.
    """
    raw: dict[str, Any] = {
        "schema": stratum.STRATUM_SCHEMA,
        "rule_digest": stratum.rule_digest(),
        "band": {"max_changed_lines": 30, "max_hunks": 2, "max_non_test_files": 1},
        "corpus": list(corpus_ids),
        "difficulty": {
            task_id: {
                "added": 1,
                "blobs": 1,
                "deleted": 1,
                "f2p": 1,
                "files": 1,
                "hunks": 1,
                "pins": 0,
            }
            for task_id in corpus_ids
        },
        "donor_heads": {"private": "0" * 40},
        "refusals": {},
        "membership": list(members),
    }
    raw.update(fields)
    raw["document_digest"] = stratum.document_digest_of(raw)
    root.mkdir(parents=True, exist_ok=True)
    out = root / "easier.json"
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


def test_the_stratum_narrows_the_drawn_private_set_to_its_membership(tmp_path: Path) -> None:
    """The band is what gets drawn, and source A is still scored in full.

    The three derivations of "what the night drew against" must agree — the frozen contract's
    posed set, the rollouts recorded, and the trainable partition — exactly as the held-out
    seam requires. A narrowing that reached only the training step would leave out-of-band
    tasks in the evidence while the ledger claimed a stratum.
    """
    doc = _stratum_document(tmp_path / "doc", _BAND)
    night = _night(tmp_path, private_ids=_IDS, stratum=doc)

    expected = set(_BAND) | {"pallets__flask-4045"}
    assert set(night.contract.posed.values()) == expected, (
        "WHY THIS IS A FAILURE: the frozen contract covers a task outside the band. The seal "
        "is the audit trail of what was asked, and it must cover exactly the band plus source A"
    )
    assert _rollout_ids(night) == expected, (
        f"WHY THIS IS A FAILURE: an out-of-band id reached a rollout: {_rollout_ids(night)}"
    )
    example_ids = {example.task_id for example in night.dataset.examples}
    assert example_ids == expected, (
        f"WHY THIS IS A FAILURE: the trainable partition carries an out-of-band id: {example_ids}"
    )


def test_a_held_out_band_member_is_excluded_rather_than_drawn(tmp_path: Path) -> None:
    """The split wins over the band, and the order of the two narrowings is what proves it.

    A band member inside the held-out membership must not be drawn. If the stratum were applied
    before the exclusion — or instead of it — a narrowing flag would become a way to reach past
    the protection the whole promotion gate rests on.
    """
    from loop.test_night_integration import _heldout_document

    held = _heldout_document(tmp_path / "held", _HELD_ONE_BAND_MEMBER, corpus_ids=_IDS)
    doc = _stratum_document(tmp_path / "doc", _BAND)
    night = _night(tmp_path, private_ids=_IDS, stratum=doc, heldout=held)

    drawn = _rollout_ids(night)
    assert "t-05" not in drawn, (
        "WHY THIS IS A FAILURE: a held-out task was drawn because it was in the band. The "
        "stratum must narrow what survives the exclusion, never restore what the split removed"
    )
    assert drawn == {"t-02", "t-09", "pallets__flask-4045"}, (
        f"WHY THIS IS A FAILURE: the night drew {drawn}, not the band minus the held-out member"
    )


def test_a_membership_id_matching_no_loaded_task_is_refused_by_name(tmp_path: Path) -> None:
    """`UnknownStratumId`, by identity from the module that raises it.

    An id resolving nowhere would select nothing while the ledger recorded a stratum — the same
    failure shape the held-out loader refuses, and the reason this seam narrows the *drawn* set
    rather than asking an operator to narrow the *loaded* corpus.
    """
    doc = _stratum_document(tmp_path / "doc", (*_BAND, _GHOST), corpus_ids=(*_IDS, _GHOST))

    with pytest.raises(stratum.UnknownStratumId) as caught:
        _night(tmp_path, private_ids=_IDS, stratum=doc)

    assert _GHOST in str(caught.value), (
        "WHY THIS IS A FAILURE: the refusal did not name the unresolvable id, so an operator "
        "cannot tell which membership entry to fix"
    )


def test_a_stratum_that_empties_the_private_set_is_refused_before_the_freeze(
    tmp_path: Path,
) -> None:
    """`EmptyTaskSet`: a night that would draw no source-B task refuses, it does not proceed.

    The two-source rule (§ 4) is not satisfied by source A alone, and a run that generated
    against one source while its ledger named two would be the exact dishonesty the refusal
    exists to prevent.
    """
    from loop.test_night_integration import _heldout_document

    held = _heldout_document(tmp_path / "held", _HELD_WHOLE_BAND, corpus_ids=_IDS)
    doc = _stratum_document(tmp_path / "doc", _BAND)

    with pytest.raises(EmptyTaskSet):
        _night(tmp_path, private_ids=_IDS, stratum=doc, heldout=held)


def test_the_ledger_records_the_stratum_by_digest_and_count_never_by_membership(
    tmp_path: Path,
) -> None:
    """Hashes and counts, never ids — the ledger's standing discipline, same as the split's.

    The claim is about the *stratum record*, not the whole ledger: a night's seed map has
    always recorded the task ids it drew against, and must, because a seed nobody can attribute
    to a task reproduces nothing. What the record must not do is restate the membership — a
    reader holding the digest opens the committed document for that.
    """
    doc = _stratum_document(tmp_path / "doc", _BAND)
    night = _night(tmp_path, private_ids=_IDS, stratum=doc)

    written = run_ledger.read(night.ledger)
    record = written["task_set"]["stratum"]
    assert record is not None, (
        "WHY THIS IS A FAILURE: the night narrowed by a stratum and recorded nothing. An "
        "unrecorded narrowing is a figure whose denominator no reader can reconstruct"
    )
    document = json.loads(doc.read_text())
    assert record["membership_count"] == len(_BAND)
    assert record["document_digest"] == document["document_digest"]
    assert record["rule_digest"] == document["rule_digest"], (
        "WHY THIS IS A FAILURE: the band rule's digest is missing, so a reader cannot tell "
        "the band was defined by the patch rather than chosen after an outcome"
    )
    assert set(record) == {"document_digest", "rule_digest", "membership_count"}, (
        f"WHY THIS IS A FAILURE: the stratum record carries {sorted(record)}. Counts and "
        "digests only — the membership lives in the committed document, and a record that "
        "listed it would publish the user's own task ids for no gain"
    )


def test_a_night_without_a_stratum_is_unchanged(tmp_path: Path) -> None:
    """The regression that matters: an unflagged night is byte for byte today's night.

    Every figure already recorded was produced without this flag. If adding it moved the
    contract SHA, the seeds or the drawn set of an unflagged run, every prior figure would
    become non-comparable to every later one for no reason anybody chose.
    """
    plain = _night(tmp_path / "plain", private_ids=_IDS)
    again = _night(tmp_path / "again", private_ids=_IDS, stratum=None)

    assert plain.contract.sha256 == again.contract.sha256, (
        "WHY THIS IS A FAILURE: passing stratum=None moved the frozen contract's hash, so the "
        "flag is not inert when unused"
    )
    assert run_ledger.read(plain.ledger)["task_set"]["stratum"] is None, (
        "WHY THIS IS A FAILURE: an unflagged night recorded a stratum it never applied"
    )
