"""The dataset document's seal: `whetstone-training-set/2`, writer side, then the reader.

The dataset's `digest` used to be a digest of the `examples` list alone: `schema`,
`denominator`, `unverified` and `coverage` sat outside it, and no reader recomputed it. Under
v2 every payload key is a claim — `denominator`, `unverified`, `coverage`, `examples` — and
`digest` reduces from the claim hashes, domain-separated by the schema tag exactly as the
checkpoint's is. `Dataset.digest` becomes that seal, so what a checkpoint records as
`dataset_digest` names the whole document.

This file starts with the writer's half: the round trip, determinism, the pinned seal digest,
and the rule that the writer never repairs a digest it was handed. The reader's half follows:
`verify_document` re-hashes a v2 document's claims before anyone reads its fields, refuses every
adversarial shape by name, and returns a v1 document — night-001's real shape, never rewritten —
unsealed, exactly as it always read.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from whetstone.bakeoff.scoring import Outcome
from whetstone.loop import dataset as training
from whetstone.loop import seal
from whetstone.verify.verdict import Status

#: The seal digest of `_built()`, computed once from the finished helper and pasted; never
#: recomputed in this file. The same rule as the checkpoint's canonical-bytes pin: a literal
#: that can only move if the encoding moves.
_FIXED_SEAL_DIGEST = "02a7458db39e3abcf5d98a87ca1359a876e81211a5dfb8c6686fe52da1f442c0"


def _example(task_id: str, source: str, *, attempt: int) -> training.Example:
    """One record in the shape the night writes it — hashes and verdicts only."""
    return training.Example(
        task_id=task_id,
        source=source,
        attempt=attempt,
        seed=attempt,
        prompt_sha256="a" * 64,
        completion_sha256="b" * 64,
        strict=Status.PASS,
        outcome=Outcome.SOLVED,
        control=Status.PASS,
    )


def _text(task_id: str, source: str, *, attempt: int) -> training.TrainingText:
    return training.TrainingText(
        example=_example(task_id, source, attempt=attempt),
        prompt="fix the adder",
        completion="def add(a, b):\n    return a + b\n",
    )


def _built() -> training.Dataset:
    """The fixed two-example dataset every digest assertion below is about."""
    return training.build(
        [_text("alpha", "private", attempt=1), _text("beta", "public", attempt=2)],
        denominator=4,
        unverified=1,
    )


def _body_of(document: dict[str, object]) -> dict[str, object]:
    """The document's claims body: every top-level key that is not one of the seal's own."""
    return {key: value for key, value in document.items() if key not in seal.UNSEALED_KEYS}


def test_schema_constants() -> None:
    assert training.DATASET_SCHEMA_V1 == "whetstone-training-set/1"
    assert training.DATASET_SCHEMA_V2 == "whetstone-training-set/2"
    assert training.DATASET_SCHEMA == training.DATASET_SCHEMA_V2, (
        "WHY THIS IS A FAILURE: the schema written is not the sealed one, so a new dataset's "
        "claims ride outside its digest — the exact hole this unit closes"
    )
    assert {"DATASET_SCHEMA_V1", "DATASET_SCHEMA_V2", "DATASET_SCHEMA"} <= set(training.__all__)


def test_a_fixed_dataset_has_a_pinned_seal_digest() -> None:
    assert _built().digest == _FIXED_SEAL_DIGEST, (
        "WHY THIS IS A FAILURE: the seal digest moved. Every checkpoint that records a dataset "
        "digest, and every committed citation of one, would name bytes that no longer exist"
    )


def test_the_document_carries_the_datasets_own_seal() -> None:
    """The round trip: `Dataset.digest`, `document()["digest"]` and the re-hash are one value."""
    built = _built()
    document = json.loads(training.document(built))
    body = _body_of(document)
    claims = seal.claim_hashes(body, subject="training set", refuse=training.DatasetUnverified)

    assert document["schema"] == training.DATASET_SCHEMA_V2
    assert document["digest"] == built.digest
    assert document["claims"] == claims
    assert seal.claims_digest(claims, schema=training.DATASET_SCHEMA_V2) == built.digest, (
        "WHY THIS IS A FAILURE: the emitted document does not reduce to the digest it carries, "
        "so a reader that re-hashes it — the whole point of the seal — refuses an honest write"
    )


def test_claims_cover_exactly_the_body_keys() -> None:
    """Four claims, no more and no fewer, and the seal's own fields are never claimed."""
    document = json.loads(training.document(_built()))

    assert set(document["claims"]) == {"denominator", "unverified", "coverage", "examples"}
    assert not set(document["claims"]) & seal.UNSEALED_KEYS
    assert set(document) == seal.UNSEALED_KEYS | set(document["claims"])


def test_coverage_is_claimed_not_only_derived() -> None:
    """`coverage` is in the document, so it is sealed like every other payload key.

    Two datasets with identical examples but a different `unverified` count are different
    documents; if `coverage` rode outside the claims, the second's edit would move nothing.
    """
    texts = [_text("alpha", "private", attempt=1)]
    one = training.build(texts, denominator=4, unverified=1)
    two = training.build(texts, denominator=4, unverified=2)

    assert json.loads(training.document(one))["coverage"] == 3
    assert one.digest != two.digest, (
        "WHY THIS IS A FAILURE: the unverified count is outside the seal, so a hand edit to "
        "`unverified`/`coverage` — the honesty figures this project exists to report — would "
        "leave the digest unchanged"
    )


def test_the_document_is_deterministic_and_order_independent() -> None:
    forwards = training.build(
        [_text("alpha", "private", attempt=1), _text("beta", "public", attempt=2)],
        denominator=4,
        unverified=1,
    )
    backwards = training.build(
        [_text("beta", "public", attempt=2), _text("alpha", "private", attempt=1)],
        denominator=4,
        unverified=1,
    )

    assert training.document(forwards) == training.document(backwards)
    assert forwards.digest == backwards.digest


def test_the_writer_never_repairs_a_digest_it_was_handed() -> None:
    """A hand-built `Dataset` writes the digest it carries, even a wrong one.

    `build` is the only constructor in `src/`; a second one carrying a digest that does not
    reduce from its body must produce a document that **fails verification on read**, not one
    silently repaired here — a writer that recomputed could mask a defective `build`.
    """
    built = _built()
    forged = training.Dataset(
        examples=built.examples,
        digest="0" * 64,
        denominator=built.denominator,
        unverified=built.unverified,
    )
    document = json.loads(training.document(forged))
    claims = seal.claim_hashes(
        _body_of(document), subject="training set", refuse=training.DatasetUnverified
    )

    assert document["digest"] == "0" * 64
    assert seal.claims_digest(claims, schema=training.DATASET_SCHEMA_V2) != document["digest"]


# --- The verifying reader: v2 is checked claim by claim, v1 reads exactly as it always did -----


def _written_v2(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    """A v2 document through the real writer, its path and its parse."""
    path = training.write_document(tmp_path / "run" / "dataset.json", _built())
    return path, json.loads(path.read_text(encoding="utf-8"))


def _rewrite(path: Path, document: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_a_v2_document_verifies_sealed(tmp_path: Path) -> None:
    path, document = _written_v2(tmp_path)
    verified = training.verify_document(path)

    assert isinstance(verified, training.VerifiedDataset)
    assert verified.sealed is True
    assert verified.document == document
    assert training.read_document(path) == document, (
        "WHY THIS IS A FAILURE: the public reader does not go through the verifying one, so "
        "check_leakage would read a tampered document that verify_document would refuse"
    )


_MOVES: dict[str, Any] = {
    "denominator": lambda one: one.update(denominator=5),
    "unverified": lambda one: one.update(unverified=0),
    "coverage": lambda one: one.update(coverage=4),
    "examples": lambda one: one.update(examples=[]),
}


@pytest.mark.parametrize("key", sorted(_MOVES))
def test_a_moved_claim_is_refused_by_name(tmp_path: Path, key: str) -> None:
    path, document = _written_v2(tmp_path)
    _MOVES[key](document)
    _rewrite(path, document)

    with pytest.raises(training.DatasetUnverified, match=rf"claim '{key}'"):
        training.verify_document(path)


def test_an_unclaimed_key_is_refused_by_name(tmp_path: Path) -> None:
    path, document = _written_v2(tmp_path)
    document["promoted"] = True
    _rewrite(path, document)

    with pytest.raises(training.DatasetUnverified, match=r"'promoted', which no claim seals"):
        training.verify_document(path)


def test_a_deleted_claim_is_refused_by_name(tmp_path: Path) -> None:
    path, document = _written_v2(tmp_path)
    del document["claims"]["unverified"]
    _rewrite(path, document)

    with pytest.raises(training.DatasetUnverified, match=r"'unverified', which no claim seals"):
        training.verify_document(path)


def test_an_orphaned_claim_is_refused_by_name(tmp_path: Path) -> None:
    path, document = _written_v2(tmp_path)
    del document["unverified"]
    _rewrite(path, document)

    with pytest.raises(
        training.DatasetUnverified, match=r"records claim 'unverified' and carries no 'unverified'"
    ):
        training.verify_document(path)


def test_a_key_and_its_claim_deleted_together_are_refused(tmp_path: Path) -> None:
    """The digest is what catches this one: the remaining claims agree with each other."""
    path, document = _written_v2(tmp_path)
    del document["denominator"]
    del document["claims"]["denominator"]
    _rewrite(path, document)

    with pytest.raises(training.DatasetUnverified, match="disagrees with itself"):
        training.verify_document(path)


def test_two_swapped_claim_values_are_refused(tmp_path: Path) -> None:
    path, document = _written_v2(tmp_path)
    claims = document["claims"]
    claims["denominator"], claims["unverified"] = claims["unverified"], claims["denominator"]
    _rewrite(path, document)

    with pytest.raises(
        training.DatasetUnverified, match="was changed after the training set was sealed"
    ):
        training.verify_document(path)


@pytest.mark.parametrize("value", ["g" * 64, "0" * 63, "A" * 64], ids=["non-hex", "short", "upper"])
def test_a_claim_hash_that_is_not_a_sha256_is_refused(tmp_path: Path, value: str) -> None:
    path, document = _written_v2(tmp_path)
    document["claims"]["coverage"] = value
    _rewrite(path, document)

    with pytest.raises(training.DatasetUnverified, match=r"claim 'coverage' .* not a sha256"):
        training.verify_document(path)


def test_a_newline_bearing_claim_key_is_refused(tmp_path: Path) -> None:
    path, document = _written_v2(tmp_path)
    document["claims"]["a\nb"] = "0" * 64
    _rewrite(path, document)

    with pytest.raises(training.DatasetUnverified, match="holds a newline"):
        training.verify_document(path)


@pytest.mark.parametrize(
    "claims",
    [None, "x", ["denominator"], {"denominator": 1}],
    ids=["missing", "string", "list", "int-hash"],
)
def test_a_v2_document_without_a_claims_mapping_is_refused(tmp_path: Path, claims: Any) -> None:
    path, document = _written_v2(tmp_path)
    if claims is None:
        del document["claims"]
    else:
        document["claims"] = claims
    _rewrite(path, document)

    with pytest.raises(training.DatasetUnverified, match="claims mapping"):
        training.verify_document(path)


def test_an_unknown_schema_is_refused_naming_both(tmp_path: Path) -> None:
    path, document = _written_v2(tmp_path)
    document["schema"] = "whetstone-training-set/3"
    _rewrite(path, document)

    with pytest.raises(ValueError, match="does not declare schema") as caught:
        training.verify_document(path)

    assert training.DATASET_SCHEMA_V1 in str(caught.value)
    assert training.DATASET_SCHEMA_V2 in str(caught.value)


def test_a_hand_built_dataset_with_a_wrong_digest_is_refused_on_read(tmp_path: Path) -> None:
    """The Phase-2 writer rule, exercised through the reader: no repair, so a refusal."""
    built = _built()
    forged = training.Dataset(
        examples=built.examples,
        digest="0" * 64,
        denominator=built.denominator,
        unverified=built.unverified,
    )
    path = training.write_document(tmp_path / "dataset.json", forged)

    with pytest.raises(training.DatasetUnverified, match="disagrees with itself"):
        training.verify_document(path)


# --- The limit, pinned rather than implied -----------------------------------------------------


def test_a_forger_who_recomputes_the_claims_is_not_caught(tmp_path: Path) -> None:
    """PRD § 3's stated limit: an unkeyed digest does not catch a writer who recomputes it.

    Rewriting a claim, its hash and the digest consistently produces a document that verifies
    and reports `sealed`. The seal catches accident-shaped edits and disagreement with a digest
    cited elsewhere; it is never authentication.
    """
    path, document = _written_v2(tmp_path)
    document["denominator"] = 5
    document["claims"] = seal.claim_hashes(
        _body_of(document), subject="training set", refuse=training.DatasetUnverified
    )
    document["digest"] = seal.claims_digest(document["claims"], schema=training.DATASET_SCHEMA_V2)
    _rewrite(path, document)

    forged = training.verify_document(path)

    assert forged.sealed is True
    assert forged.document["denominator"] == 5


def test_a_v2_document_relabelled_v1_reads_unsealed_the_downgrade_limit(tmp_path: Path) -> None:
    """A schema downgrade is not caught: the v1 path performs no digest check at all.

    This is the other half of the forger limit, pinned so nobody reads `sealed=False` as "this
    is a genuine v1". A reader that accepts v1 documents — which it must, night-001's is one —
    cannot tell a downgraded v2 from an original, and a downgraded document's edits ride along.
    """
    path, document = _written_v2(tmp_path)
    document["schema"] = training.DATASET_SCHEMA_V1
    document["digest"] = hashlib.sha256(
        json.dumps(document["examples"], indent=2, sort_keys=True).encode("utf-8")
    ).hexdigest()
    _rewrite(path, document)

    verified = training.verify_document(path)

    assert verified.sealed is False
    assert verified.document == document


def _v1_document(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    """A document in night-001's shape: `/1`, an examples-only digest, no claims."""
    path, v2 = _written_v2(tmp_path)
    body = _body_of(v2)
    v1 = {
        "schema": training.DATASET_SCHEMA_V1,
        "digest": hashlib.sha256(
            json.dumps(body["examples"], indent=2, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        **body,
    }
    _rewrite(path, v1)
    return path, v1


def test_a_v1_document_reads_unsealed_and_byte_unchanged(tmp_path: Path) -> None:
    """Criterion 5: v1 reads exactly as today, is never reported sealed, and never rewritten."""
    path, document = _v1_document(tmp_path)
    before = path.read_bytes()

    verified = training.verify_document(path)

    assert verified.sealed is False
    assert verified.document == document
    assert training.read_document(path) == document
    assert path.read_bytes() == before, (
        "WHY THIS IS A FAILURE: reading a v1 document rewrote it. The real night-001 dataset "
        "is an operator artifact that must never move"
    )
