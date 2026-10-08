"""The shared seal primitives, and the checkpoint document's bytes pinned across the extraction.

The extraction of `sft.py`'s canonical-bytes, claim-hash and claims-digest logic into
`loop/seal.py` must not move a byte of any checkpoint document: every sealed checkpoint that
exists would read as tampered if the encoding drifted. So the first test here was written and
run **before** the extraction, against the pre-extraction writer, and its literal is the
sha256 of that fixture's `provenance.json` — computed once and pasted, never recomputed in the
test. It can only go red if the extraction moves a byte, which is the whole point.

The module-API tests then pin `seal` itself: the canonical encoding, the per-claim hashes,
the domain-separated claims digest, and the verifier's refusals — with `subject="checkpoint"`
reproducing the checkpoint's own error messages byte-for-byte.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

#: The standard checkpoint fixture, in the shape `tests/loop/test_checkpoint_seal.py` writes —
#: one stub adapter through the real writer, every field fixed. Imported rather than copied so
#: the byte pin below is provably the same fixture the checkpoint suite exercises.
from loop.test_checkpoint_seal import (
    _FIXED,
    _FIXED_CANONICAL_HEX,
    _FIXED_CLAIM_HASHES,
    _FIXED_CLAIMS_DIGEST,
    _read,
    _write,
    _written,
)
from whetstone.loop import seal, sft

#: sha256 of the fixture's `provenance.json` **bytes**, as the pre-extraction writer produced
#: them. Computed once from the finished fixture and pasted; never recomputed here.
_WRITTEN_PROVENANCE_SHA256 = "4284f07cfabb7f88d425a43e3155d3a7ad3563666bec3dcfb0e6ef6ef921e300"


def test_the_written_checkpoint_document_is_byte_identical(tmp_path: Path) -> None:
    """The characterization pin: the extraction may not move one byte of provenance.json.

    Run green against the pre-extraction writer before any production line changed. Its only
    failure mode is a byte moving, which is the one thing the whole extraction must not do.
    """
    written = _written(tmp_path / "cp")
    raw = (written.directory / sft.CHECKPOINT_FILE).read_bytes()

    assert hashlib.sha256(raw).hexdigest() == _WRITTEN_PROVENANCE_SHA256, (
        "WHY THIS IS A FAILURE: the checkpoint document's bytes moved across the seal "
        "extraction. Every sealed checkpoint on disk would read as tampered, and the pinned "
        "canonical-bytes tests would not catch a message-free byte drift by themselves"
    )


# --- The module API --------------------------------------------------------------------------


class DatasetUnverified(ValueError):
    """A stand-in for the second document family's refusal, to prove `refuse` is a parameter."""


def test_canonical_bytes_are_pinned() -> None:
    assert seal.canonical(_FIXED).hex() == _FIXED_CANONICAL_HEX, (
        "WHY THIS IS A FAILURE: the canonical bytes moved, so every claim hash over them "
        "moved, so every sealed document on disk reads as tampered"
    )


def test_a_tuple_canonicalises_as_the_list_a_reader_gets_back() -> None:
    """The inner round trip: a tuple is hashed as the list `json.loads` returns."""
    assert seal.canonical((1, 2, (3, 4))) == seal.canonical([1, 2, [3, 4]])
    assert seal.claim_hashes(
        {"t": (1, 2, (3, 4))}, subject="checkpoint", refuse=sft.CheckpointUnverified
    ) == seal.claim_hashes(
        {"t": [1, 2, [3, 4]]}, subject="checkpoint", refuse=sft.CheckpointUnverified
    )


def test_claims_digest_is_pinned() -> None:
    assert (
        seal.claims_digest(_FIXED_CLAIM_HASHES, schema=sft.CHECKPOINT_SCHEMA_V2)
        == _FIXED_CLAIMS_DIGEST
    )


def test_two_schema_tags_give_two_digests_for_one_claims_map() -> None:
    """The domain separation: the tag is part of the digest's material, not decoration."""
    assert seal.claims_digest(
        _FIXED_CLAIM_HASHES, schema=sft.CHECKPOINT_SCHEMA_V1
    ) != seal.claims_digest(_FIXED_CLAIM_HASHES, schema=sft.CHECKPOINT_SCHEMA_V2)


@pytest.mark.parametrize("key", ["schema", "digest", "claims"])
def test_claim_hashes_refuses_unsealed_keys_naming_the_subject(key: str) -> None:
    with pytest.raises(sft.CheckpointUnverified, match="a checkpoint body must not carry"):
        seal.claim_hashes(
            {"ok": 1, key: "x"}, subject="checkpoint", refuse=sft.CheckpointUnverified
        )
    with pytest.raises(DatasetUnverified, match="a training set body must not carry"):
        seal.claim_hashes({"ok": 1, key: "x"}, subject="training set", refuse=DatasetUnverified)


def test_claim_hashes_refuses_a_newline_key_naming_the_subject() -> None:
    with pytest.raises(sft.CheckpointUnverified, match="a checkpoint body must not carry the key"):
        seal.claim_hashes({"a\nb": 2}, subject="checkpoint", refuse=sft.CheckpointUnverified)
    with pytest.raises(DatasetUnverified, match="a training set body must not carry the key"):
        seal.claim_hashes({"a\nb": 2}, subject="training set", refuse=DatasetUnverified)


def test_sealed_document_is_the_three_seal_fields_plus_the_body() -> None:
    body: dict[str, Any] = {"denominator": 2, "unverified": 1, "coverage": 1, "examples": []}
    document = seal.sealed_document(
        body, schema="whetstone-training-set/2", subject="training set", refuse=DatasetUnverified
    )
    claims = seal.claim_hashes(body, subject="training set", refuse=DatasetUnverified)

    assert document["schema"] == "whetstone-training-set/2"
    assert document["claims"] == claims
    assert document["digest"] == seal.claims_digest(claims, schema="whetstone-training-set/2")
    assert {key: document[key] for key in body} == body
    assert set(document) == seal.UNSEALED_KEYS | set(body)
    assert body == {
        "denominator": 2,
        "unverified": 1,
        "coverage": 1,
        "examples": [],
    }, "sealing must not mutate the body it was handed"


# --- verify_claims: every refusal, and the checkpoint's own words byte-for-byte --------------


def _verify(path: Path, raw: Mapping[str, Any]) -> None:
    seal.verify_claims(
        path,
        raw,
        schema=sft.CHECKPOINT_SCHEMA_V2,
        subject="checkpoint",
        refuse=sft.CheckpointUnverified,
    )


def _written_raw(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    written = _written(tmp_path / "cp")
    path = written.directory / sft.CHECKPOINT_FILE
    return path, _read(written.directory)


def test_verify_claims_names_a_moved_key_byte_for_byte(tmp_path: Path) -> None:
    """A claim edited after sealing: `seal.verify_claims` equals the checkpoint's own message."""
    path, document = _written_raw(tmp_path)
    document["dataset_digest"] = "e" * 64
    _write(path.parent, document)
    raw = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in raw.items() if key not in seal.UNSEALED_KEYS}
    live = seal.claim_hashes(body, subject="checkpoint", refuse=sft.CheckpointUnverified)
    expected = (
        f"{str(path)!r}: claim 'dataset_digest' records sha256 {raw['claims']['dataset_digest']} "
        f"and the document's 'dataset_digest' hashes to {live['dataset_digest']} — the "
        "document's 'dataset_digest' was changed after the checkpoint was sealed"
    )

    with pytest.raises(sft.CheckpointUnverified) as current:
        sft._verify_claims(path, raw)
    with pytest.raises(sft.CheckpointUnverified) as extracted:
        _verify(path, raw)

    assert str(current.value) == expected
    assert str(extracted.value) == expected


def test_verify_claims_names_a_digest_that_does_not_reduce_byte_for_byte(tmp_path: Path) -> None:
    path, document = _written_raw(tmp_path)
    document["digest"] = "0" * 64
    _write(path.parent, document)
    raw = json.loads(path.read_text(encoding="utf-8"))
    reduced = seal.claims_digest(raw["claims"], schema=sft.CHECKPOINT_SCHEMA_V2)
    expected = (
        f"{str(path)!r} records digest {'0' * 64!r} and its claims reduce to {reduced!r}. The "
        "document disagrees with itself, which a hand edit produces and a night does not"
    )

    with pytest.raises(sft.CheckpointUnverified) as current:
        sft._verify_claims(path, raw)
    with pytest.raises(sft.CheckpointUnverified) as extracted:
        _verify(path, raw)

    assert str(current.value) == expected
    assert str(extracted.value) == expected


def test_verify_claims_names_the_unclaimed_key(tmp_path: Path) -> None:
    path, document = _written_raw(tmp_path)
    document["promoted"] = True
    _write(path.parent, document)
    raw = json.loads(path.read_text(encoding="utf-8"))

    with pytest.raises(sft.CheckpointUnverified, match=r"'promoted', which no claim seals"):
        _verify(path, raw)


def test_verify_claims_names_the_orphaned_claim(tmp_path: Path) -> None:
    path, document = _written_raw(tmp_path)
    del document["run_seed"]
    _write(path.parent, document)
    raw = json.loads(path.read_text(encoding="utf-8"))

    with pytest.raises(
        sft.CheckpointUnverified, match=r"records claim 'run_seed' and carries no 'run_seed'"
    ):
        _verify(path, raw)


def test_verify_claims_refuses_a_missing_claims_mapping_with_the_passed_subject(
    tmp_path: Path,
) -> None:
    """The refusal type and the subject noun are parameters, not checkpoint hardcoding."""
    path, document = _written_raw(tmp_path)
    del document["claims"]
    _write(path.parent, document)
    raw = json.loads(path.read_text(encoding="utf-8"))

    with pytest.raises(DatasetUnverified, match="about this training set is sealed"):
        seal.verify_claims(
            path,
            raw,
            schema="whetstone-training-set/2",
            subject="training set",
            refuse=DatasetUnverified,
        )
