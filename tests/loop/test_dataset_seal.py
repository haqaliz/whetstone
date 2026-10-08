"""The dataset document's seal: `whetstone-training-set/2`, writer side, then the reader.

The dataset's `digest` used to be a digest of the `examples` list alone: `schema`,
`denominator`, `unverified` and `coverage` sat outside it, and no reader recomputed it. Under
v2 every payload key is a claim — `denominator`, `unverified`, `coverage`, `examples` — and
`digest` reduces from the claim hashes, domain-separated by the schema tag exactly as the
checkpoint's is. `Dataset.digest` becomes that seal, so what a checkpoint records as
`dataset_digest` names the whole document.

This file starts with the writer's half: the round trip, determinism, the pinned seal digest,
and the rule that the writer never repairs a digest it was handed. The verifying reader — every
adversarial shape refused by name — lands in this file in the reader's phase.
"""

from __future__ import annotations

import json

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
