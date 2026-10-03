"""The seal's canonical claims: the bytes a claim hash is taken over, pinned.

A checkpoint's `provenance.json` claims are sealed into its digest by hashing each claim's
canonical bytes. If those bytes drifted between releases every sealed checkpoint would read as
tampered, so the encoding is pinned here by a literal, never recomputed in the test.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from whetstone.loop import sft

_FIXED: dict[str, Any] = {
    "base": "m/x",
    "iters": 3,
    "rate": 0.5,
    "none": None,
    "nested": {"b": [1, 2.5, None], "a": "é"},
}

# Computed once from the finished helper and pasted; never recomputed in this file.
_FIXED_CANONICAL_HEX = (
    "7b2262617365223a226d2f78222c226974657273223a332c226e6573746564223a7b2261223a225c75303065"
    "39222c2262223a5b312c322e352c6e756c6c5d7d2c226e6f6e65223a6e756c6c2c2272617465223a302e357d"
)
_FIXED_CLAIM_HASHES = {
    "base": "231b2ba29f7bf7bfa23384ccd059078c50081a6775035f17abe726a5b469c215",
    "iters": "4e07408562bedb8b60ce05c1decfe3ad16b72230967de01f640b7e4729b49fce",
    "rate": "d2cbad71ff333de67d07ec676e352ab7f38248eb69c942950157220607c55e84",
    "none": "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b",
    "nested": "84afbf1d4853005f9dd0c81cb1819b53ce86978340764c062160f6e8356665de",
}
_FIXED_CLAIMS_DIGEST = "565de2bb2f4566ed90594ecb87f4aff5614f6eb8a4f0a485bba9445db129ded8"


def test_schema_constants() -> None:
    assert sft.CHECKPOINT_SCHEMA_V1 == "whetstone-checkpoint/1"
    assert sft.CHECKPOINT_SCHEMA_V2 == "whetstone-checkpoint/2"
    assert {"CHECKPOINT_SCHEMA_V1", "CHECKPOINT_SCHEMA_V2", "CHECKPOINT_SCHEMA"} <= set(sft.__all__)
    assert frozenset({"schema", "digest", "claims"}) == sft._UNSEALED_KEYS


def test_canonical_bytes_are_pinned() -> None:
    assert sft._canonical(_FIXED).hex() == _FIXED_CANONICAL_HEX


def test_claim_hashes_are_pinned() -> None:
    assert sft._claim_hashes(_FIXED) == _FIXED_CLAIM_HASHES


def test_claims_digest_is_pinned() -> None:
    assert sft._claims_digest(_FIXED_CLAIM_HASHES) == _FIXED_CLAIMS_DIGEST


def test_hash_equals_hash_of_round_tripped_value() -> None:
    body: dict[str, Any] = {
        "i": 1,
        "f": 1.5,
        "n": None,
        "m": {"k": [1, "x"]},
        "t": (1, 2, (3, 4)),
        "l": [None, 2.0],
    }
    reread = json.loads(json.dumps(body))
    assert sft._claim_hashes(body) == sft._claim_hashes(reread)
    assert sft._canonical(body["t"]) == sft._canonical([1, 2, [3, 4]])


def test_key_order_does_not_change_the_hash() -> None:
    a = {"x": {"p": 1, "q": 2}, "y": 3}
    b = {"y": 3, "x": {"q": 2, "p": 1}}
    assert sft._claim_hashes(a) == sft._claim_hashes(b)
    assert sft._claims_digest(sft._claim_hashes(a)) == sft._claims_digest(sft._claim_hashes(b))


def test_claim_hash_is_sha256_of_canonical_bytes() -> None:
    assert sft._claim_hashes({"k": [1]})["k"] == hashlib.sha256(b"[1]").hexdigest()


@pytest.mark.parametrize("key", ["digest", "schema", "claims"])
def test_claim_hashes_refuses_unsealed_keys(key: str) -> None:
    with pytest.raises(sft.CheckpointUnverified):
        sft._claim_hashes({"ok": 1, key: "x"})
