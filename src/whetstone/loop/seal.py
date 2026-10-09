"""The seal primitives every run document shares: canonical bytes, claims, and their digest.

A sealed document carries three keys that are not claims — its schema label, its `digest` and
the `claims` map — and every other top-level key is a claim: hashed canonically into `claims`,
with `digest` reducing from the sorted `key:hash` lines. Editing any claim without recomputing
the whole document is then refused by name on read; the digest is an unkeyed hash, so a writer
who recomputes it is not caught, and no surface may call this authentication.

The logic was private to `sft.py`, where the `whetstone-checkpoint/2` seal was built. It is one
implementation here because the dataset document (`whetstone-training-set/2`) and, later, the
ledger need exactly the same bytes and the same refusals: a second implementation is how two
documents come to disagree about what sealing means, with every test of each still green.

**Everything is parameterised by the document family**, never hardcoded: `subject` is the noun
the refusal messages name, `schema` is the tag `digest` is domain-separated by, and `refuse` is
the caller's named exception — so `subject="checkpoint"` reproduces the checkpoint's messages
byte-for-byte while a dataset passes its own. Stdlib only (`hashlib`, `json`, `re`): this is a
leaf module, and nothing here may ever reach the reward path.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

#: The document keys that are not claims: the schema label, the digest, and the claim hashes.
UNSEALED_KEYS: frozenset[str] = frozenset({"schema", "digest", "claims"})

#: A claim hash: exactly the lowercase hex `hexdigest()` writes. Fixed length and newline-free,
#: so with newlines also banned from keys, every `key:hash` line `claims_digest` joins splits
#: back into exactly one key and one hash — the line format is injective.
CLAIM_HASH: re.Pattern[str] = re.compile(r"[0-9a-f]{64}")


def canonical(value: Any) -> bytes:
    """The bytes a claim is hashed over: what a reader will parse back, in one fixed encoding.

    The inner round trip means the hashed value is the one `json.loads` returns from the written
    document, never the in-memory object (a tuple hashes as the list it will be read back as).
    """
    return json.dumps(
        json.loads(json.dumps(value)), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def claim_hashes(
    body: Mapping[str, Any], *, subject: str, refuse: type[Exception]
) -> dict[str, str]:
    """One sha256 per claim in `body`, over that claim's canonical bytes.

    `body` holds claims only. A key from `UNSEALED_KEYS` here is a writer bug rather than an
    operator error, so it raises: sealing the seal's own fields would make the digest circular.
    A newline in a key would let one claim line read as two in `claims_digest`, so the writer
    refuses to seal one rather than produce a document whose lines are ambiguous.

    `subject` is the noun the refusals name; `refuse` is the document family's exception type,
    so every failure here is that named refusal and never a stray `KeyError` or `TypeError`.
    """
    stray = sorted(UNSEALED_KEYS & body.keys())
    if stray:
        raise refuse(f"a {subject} body must not carry {stray}; they are not claims")
    broken = sorted(key for key in body if "\n" in key)
    if broken:
        raise refuse(
            f"a {subject} body must not carry the key {broken[0]!r}: a newline in a claim key "
            "makes the digest's claim lines ambiguous"
        )
    return {key: hashlib.sha256(canonical(value)).hexdigest() for key, value in body.items()}


def claims_digest(claims: Mapping[str, str], *, schema: str) -> str:
    """The sha256 of the schema tag, a NUL, then the claim hashes as sorted `key:hash` lines.

    The tag is the domain separation. Without it the material is the same shape a v1 checkpoint
    reduces from — `name:sha256` lines over its file list — so a v1 document listing one file per
    claim key, each holding that claim's canonical bytes, could reduce to an honest sealed digest
    while whatever the claims describe sat outside the list. A v1 digest's input begins with a
    file name, and a NUL can never appear in a path (a name carrying one is never `is_file()`),
    so no v1 file list that verifies can produce the NUL the sealed input carries right after its
    tag: the two digests cannot coincide. Passing each document family's own schema tag here
    extends the separation across families as well.
    """
    text = "\n".join(f"{key}:{claims[key]}" for key in sorted(claims))
    return hashlib.sha256((schema + "\0" + text).encode("utf-8")).hexdigest()


def sealed_document(
    body: Mapping[str, Any], *, schema: str, subject: str, refuse: type[Exception]
) -> dict[str, Any]:
    """The whole sealed document: schema, claim hashes, digest, and `body` beside them.

    One function, so a writer cannot emit a document whose `claims` and `digest` disagree with
    the body they are supposed to seal — the `body` is hashed here, once, and the document is
    built from that result.
    """
    claims = claim_hashes(body, subject=subject, refuse=refuse)
    return {
        "schema": schema,
        "digest": claims_digest(claims, schema=schema),
        "claims": claims,
        **body,
    }


def verify_claims(
    document: Path,
    raw: Mapping[str, Any],
    *,
    schema: str,
    subject: str,
    refuse: type[Exception],
) -> None:
    """Refuse a sealed document whose claims do not re-hash, naming the first key that moved.

    Every key except `UNSEALED_KEYS` is a claim and must have exactly one hash; a key with no
    hash, a hash with no key, and a hash the key no longer produces are each refused by name.
    Then the digest must reduce from the claims — which is what catches a key deleted together
    with its hash, since the remaining claims are consistent with each other and not with it.

    `document` is the path only for the messages; `raw` is the one parse just loaded, so nothing
    is read twice. `subject` and `refuse` are the calling family's own, so a checkpoint passes
    `"checkpoint"` and `CheckpointUnverified` and gets exactly its historical messages.
    """
    claims = raw.get("claims")
    if not isinstance(claims, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in claims.items()
    ):
        raise refuse(
            f"{str(document)!r} declares schema {schema!r} and carries no claims mapping of key "
            f"to sha256, so none of what it says about this {subject} is sealed"
        )
    # Checked explicitly, before anything is compared: the digest's `key:hash` lines are only
    # injective while no key holds a newline and every hash is fixed-length hex. Without this a
    # claim keyed "backend:<hash>\nbase" carrying `base`'s hash reproduces the honest digest
    # with both keys deleted.
    for key in sorted(claims):
        if "\n" in key:
            raise refuse(
                f"{str(document)!r} records claim {key!r}, whose key holds a newline — one claim "
                "line forged to read as two, which no writer produces"
            )
        if not CLAIM_HASH.fullmatch(claims[key]):
            raise refuse(
                f"{str(document)!r}: claim {key!r} records {claims[key]!r}, which is not a "
                "sha256 (64 lowercase hex characters)"
            )
    body = {key: value for key, value in raw.items() if key not in UNSEALED_KEYS}
    unclaimed = sorted(body.keys() - claims.keys())
    if unclaimed:
        raise refuse(
            f"{str(document)!r} carries {unclaimed[0]!r}, which no claim seals. A key added "
            f"after the {subject} was sealed reads exactly like one the night wrote"
        )
    orphaned = sorted(claims.keys() - body.keys())
    if orphaned:
        raise refuse(
            f"{str(document)!r} records claim {orphaned[0]!r} and carries no {orphaned[0]!r}. "
            f"A sealed key was removed after the {subject} was sealed"
        )
    rehashed = claim_hashes(body, subject=subject, refuse=refuse)
    for key in sorted(body):
        if rehashed[key] != claims[key]:
            raise refuse(
                f"{str(document)!r}: claim {key!r} records sha256 {claims[key]} and the "
                f"document's {key!r} hashes to {rehashed[key]} — the document's {key!r} was "
                f"changed after the {subject} was sealed"
            )
    digest = claims_digest(claims, schema=schema)
    if digest != raw.get("digest"):
        raise refuse(
            f"{str(document)!r} records digest {raw.get('digest')!r} and its claims reduce to "
            f"{digest!r}. The document disagrees with itself, which a hand edit produces and a "
            "night does not"
        )


__all__ = [
    "CLAIM_HASH",
    "UNSEALED_KEYS",
    "canonical",
    "claim_hashes",
    "claims_digest",
    "sealed_document",
    "verify_claims",
]
