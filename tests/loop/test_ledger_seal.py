"""The run ledger's seal: `whetstone-run/3`, writer side, then the verifying reader.

The ledger recorded the night and carried no digest of itself: `ledger._payload` wrote fifteen
top-level keys and every consumer read raw through `ledger.read`, which checked the schema
string and nothing else. Under v3 every one of those fifteen keys is a claim — hashed
canonically into `claims`, with `digest` reducing from the sorted `key:hash` lines,
domain-separated by the schema tag exactly as the checkpoint's and the dataset's are. The
reader verifies before any consumer sees the document; a `/2` ledger — what the shipped writer
emitted until this unit — reads unsealed and byte-unchanged; `/1` is refused exactly as it was.

This file starts with the writer's half: the shape, the reduction, and determinism across
processes. The reader's half follows: the dual-read, every adversarial shape refused by name,
the schema strings, and the documented limit (the digest is unkeyed, so a forger who recomputes
it is not caught). The consumers' half — identity imports and refusals through their own doors
— is Phase 2; `morning`'s known-field totality is Phase 3; the one-writer guard is Phase 5.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from loop.test_run_ledger import _ledger
from whetstone.loop import ledger as run_ledger
from whetstone.loop import seal

#: The fifteen body keys the v3 seal covers: today's `_payload` minus `schema`. Written out
#: rather than derived, so a key that silently stops being written is a failure here.
_BODY_KEYS = frozenset(
    {
        "run_id",
        "recorded_on",
        "run_seed",
        "draws",
        "model",
        "backend",
        "generation_contract",
        "task_set",
        "environment_pins",
        "tool_versions",
        "seeds",
        "draws_recorded",
        "dataset",
        "checkpoint",
        "capacity",
    }
)


def _written(tmp_path: Path) -> Path:
    return run_ledger.write(tmp_path / "ledger.json", _ledger())


def _rewrite(path: Path, document: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _v2(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    """A `/2` fixture in the probe's shape: a v3 document with the seal keys stripped.

    No real `/2` ledger exists (the one real probe ledger is `/1`), so this helper is the
    tolerance's fixture: the body of a genuine writer-produced document, relabelled to the
    schema the shipped writer emitted until this unit.
    """
    path = _written(tmp_path)
    document = _parse(path)
    del document["claims"]
    del document["digest"]
    document["schema"] = run_ledger.LEDGER_SCHEMA_V2
    _rewrite(path, document)
    return path, document


# ---------------------------------------------------------------------------
# Writer: the shape, the reduction, determinism
# ---------------------------------------------------------------------------


def test_schema_constants() -> None:
    assert run_ledger.LEDGER_SCHEMA_V1 == "whetstone-run/1"
    assert run_ledger.LEDGER_SCHEMA_V2 == "whetstone-run/2"
    assert run_ledger.LEDGER_SCHEMA_V3 == "whetstone-run/3"
    assert run_ledger.LEDGER_SCHEMA == run_ledger.LEDGER_SCHEMA_V3, (
        "WHY THIS IS A FAILURE: the schema written is not the sealed one, so a new ledger's "
        "claims ride outside its digest — the exact hole this unit closes"
    )
    assert {
        "LEDGER_SCHEMA_V1",
        "LEDGER_SCHEMA_V2",
        "LEDGER_SCHEMA_V3",
        "LEDGER_SCHEMA",
    } <= set(run_ledger.__all__)


def test_the_document_seals_every_body_key_under_the_v3_tag() -> None:
    """AC 1: fifteen claims, no more and no fewer, and the seal's own fields are never claimed."""
    document = json.loads(run_ledger.document(_ledger()))
    body = {key: value for key, value in document.items() if key not in seal.UNSEALED_KEYS}

    assert document["schema"] == run_ledger.LEDGER_SCHEMA_V3
    assert set(body) == _BODY_KEYS, (
        f"WHY THIS IS A FAILURE: the sealed body is {sorted(set(body))}, not the fifteen keys "
        "the ledger writes. A body key outside the write function never round-trips"
    )
    assert not _BODY_KEYS & seal.UNSEALED_KEYS
    assert set(document["claims"]) == _BODY_KEYS
    claims = seal.claim_hashes(body, subject="ledger", refuse=run_ledger.LedgerUnverified)
    assert document["claims"] == claims
    assert document["digest"] == seal.claims_digest(claims, schema=run_ledger.LEDGER_SCHEMA_V3), (
        "WHY THIS IS A FAILURE: the emitted document does not reduce to the digest it carries, "
        "so a reader that re-hashes it — the whole point of the seal — refuses an honest write"
    )


def test_the_digest_is_domain_separated_by_the_schema_tag() -> None:
    document = json.loads(run_ledger.document(_ledger()))

    assert document["digest"] != seal.claims_digest(
        document["claims"], schema=run_ledger.LEDGER_SCHEMA_V2
    )
    assert document["digest"] != seal.claims_digest(
        document["claims"], schema="whetstone-training-set/2"
    ), (
        "WHY THIS IS A FAILURE: the same claims digest identically under another document "
        "family's schema tag, so two generations and two families can collide"
    )


def test_the_written_bytes_are_the_documents_bytes(tmp_path: Path) -> None:
    path = _written(tmp_path)
    assert path.read_text(encoding="utf-8") == run_ledger.document(_ledger())


def test_the_document_is_identical_across_processes_and_hash_seeds() -> None:
    """AC 1: a fresh interpreter under either `PYTHONHASHSEED` renders the same bytes.

    Mapping and set iteration order are the two things that vary across processes and not
    within one; a claim map built in iteration order would make the bytes depend on the run
    that produced them, and a reader regenerating them could not tell a re-render from a
    re-measurement.
    """
    in_process = hashlib.sha256(run_ledger.document(_ledger()).encode("utf-8")).hexdigest()
    tests_root = Path(__file__).resolve().parents[1]
    program = (
        f"import sys, hashlib; sys.path.insert(0, {str(tests_root)!r});"
        "from loop.test_run_ledger import _ledger;"
        "from whetstone.loop import ledger;"
        "print(hashlib.sha256(ledger.document(_ledger()).encode('utf-8')).hexdigest())"
    )
    seen = {}
    for seed in ("0", "1"):
        run = subprocess.run(
            [sys.executable, "-c", program],
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": seed},
        )
        assert run.returncode == 0, run.stderr
        seen[seed] = run.stdout.strip()
    assert seen["0"] == seen["1"] == in_process, (
        "WHY THIS IS A FAILURE: the ledger's bytes depend on the process that produced them "
        f"(hash seeds {seen}); some mapping or set is serialised in iteration order"
    )


# ---------------------------------------------------------------------------
# Reader: the dual-read and the downgrade guard
# ---------------------------------------------------------------------------


def test_a_v3_ledger_verifies_sealed(tmp_path: Path) -> None:
    path = _written(tmp_path)
    parsed = _parse(path)
    verified = run_ledger.verify_document(path)

    assert isinstance(verified, run_ledger.VerifiedLedger)
    assert verified.sealed is True
    assert verified.document == parsed
    assert run_ledger.read(path) == parsed, (
        "WHY THIS IS A FAILURE: the public reader does not go through the verifying one, so a "
        "consumer would read a tampered document that verify_document would refuse"
    )


def test_a_v2_ledger_reads_unsealed_and_byte_unchanged(tmp_path: Path) -> None:
    """AC 3: the shipped generation still reads, exactly as it did, and is never rewritten."""
    path, document = _v2(tmp_path)
    before = path.read_bytes()

    verified = run_ledger.verify_document(path)

    assert verified.sealed is False
    assert verified.document == document
    assert run_ledger.read(path) == document
    assert path.read_bytes() == before, (
        "WHY THIS IS A FAILURE: reading an older ledger rewrote it. A gitignored operator "
        "artifact is never upgraded in place"
    )


def test_a_v2_document_carrying_claims_is_refused_the_downgrade_guard(tmp_path: Path) -> None:
    """A re-labelled v3 document is the one downgrade with no self-digest fallback.

    No `/2` writer ever emitted `claims`, so their presence under the old schema is a
    deliberate refusal: without it a v3 document relabelled `/2` would read as unsealed with
    no refusal anywhere, and its edits would ride along.
    """
    path = _written(tmp_path)
    document = _parse(path)
    document["schema"] = run_ledger.LEDGER_SCHEMA_V2
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnverified, match=r"claims.*whetstone-run/2"):
        run_ledger.verify_document(path)


def test_a_v2_document_carrying_a_digest_is_refused_the_downgrade_guard(tmp_path: Path) -> None:
    path = _written(tmp_path)
    document = _parse(path)
    del document["claims"]
    document["schema"] = run_ledger.LEDGER_SCHEMA_V2
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnverified, match="digest"):
        run_ledger.verify_document(path)


# ---------------------------------------------------------------------------
# Reader: the adversarial set, each shape refused by name
# ---------------------------------------------------------------------------


def test_every_body_claim_moved_is_refused_naming_the_key(tmp_path: Path) -> None:
    """AC 5(a): parameterised over the document's own body keys, so an added key is covered.

    The value is replaced by `[value]` — a type change no writer produces — while `claims` and
    `digest` are left alone, which is what a quiet edit in a text editor looks like.
    """
    path = _written(tmp_path)
    pristine = _parse(path)
    body_keys = sorted(set(pristine) - seal.UNSEALED_KEYS)
    assert body_keys, "the fixture seals nothing, so this test would prove nothing"

    missed = []
    for key in body_keys:
        doctored = copy.deepcopy(pristine)
        doctored[key] = [doctored[key]]
        _rewrite(path, doctored)
        try:
            run_ledger.verify_document(path)
        except run_ledger.LedgerUnverified as refusal:
            assert key in str(refusal), (
                f"the refusal for a moved {key!r} does not name it: {refusal}"
            )
        else:
            missed.append(key)
    assert missed == [], f"moved body keys accepted without a refusal: {missed}"


def test_an_unclaimed_key_is_refused_by_name(tmp_path: Path) -> None:
    path = _written(tmp_path)
    document = _parse(path)
    document["promoted"] = True
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnverified, match=r"'promoted', which no claim seals"):
        run_ledger.verify_document(path)


def test_an_orphaned_claim_is_refused_by_name(tmp_path: Path) -> None:
    path = _written(tmp_path)
    document = _parse(path)
    del document["run_seed"]
    _rewrite(path, document)

    with pytest.raises(
        run_ledger.LedgerUnverified, match=r"records claim 'run_seed' and carries no 'run_seed'"
    ):
        run_ledger.verify_document(path)


def test_a_claim_deleted_while_its_body_key_remains_is_refused(tmp_path: Path) -> None:
    """The body key is then unclaimed, so it is refused exactly as a key added later would be."""
    path = _written(tmp_path)
    document = _parse(path)
    del document["claims"]["run_seed"]
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnverified, match=r"'run_seed', which no claim seals"):
        run_ledger.verify_document(path)


def test_a_claim_and_its_body_key_deleted_together_are_refused(tmp_path: Path) -> None:
    """The digest is what catches this one: the remaining claims agree with each other."""
    path = _written(tmp_path)
    document = _parse(path)
    del document["run_seed"]
    del document["claims"]["run_seed"]
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnverified, match="disagrees with itself"):
        run_ledger.verify_document(path)


def test_two_swapped_claim_values_name_the_first_moved_key(tmp_path: Path) -> None:
    path = _written(tmp_path)
    document = _parse(path)
    claims = document["claims"]
    claims["draws"], claims["run_seed"] = claims["run_seed"], claims["draws"]
    _rewrite(path, document)

    with pytest.raises(
        run_ledger.LedgerUnverified,
        match=r"claim 'draws'.*was changed after the ledger was sealed",
    ):
        run_ledger.verify_document(path)


@pytest.mark.parametrize("value", ["g" * 64, "0" * 63, "A" * 64], ids=["non-hex", "short", "upper"])
def test_a_claim_hash_that_is_not_a_sha256_is_refused(tmp_path: Path, value: str) -> None:
    path = _written(tmp_path)
    document = _parse(path)
    document["claims"]["run_seed"] = value
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnverified, match=r"claim 'run_seed' .* not a sha256"):
        run_ledger.verify_document(path)


def test_a_newline_bearing_claim_key_is_refused(tmp_path: Path) -> None:
    path = _written(tmp_path)
    document = _parse(path)
    document["claims"]["a\nb"] = "0" * 64
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnverified, match="holds a newline"):
        run_ledger.verify_document(path)


@pytest.mark.parametrize(
    "claims",
    [None, "x", ["run_seed"], {"run_seed": 1}],
    ids=["missing", "string", "list", "int-hash"],
)
def test_a_v3_document_without_a_claims_mapping_is_refused(tmp_path: Path, claims: Any) -> None:
    path = _written(tmp_path)
    document = _parse(path)
    if claims is None:
        del document["claims"]
    else:
        document["claims"] = claims
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnverified, match="claims mapping"):
        run_ledger.verify_document(path)


def test_malformed_or_absent_json_is_unreadable_not_unverified(tmp_path: Path) -> None:
    """A parse failure is the base refusal; tamper is the named one. The two never blur."""
    broken = tmp_path / "broken.json"
    broken.write_text("not json at all", encoding="utf-8")
    with pytest.raises(run_ledger.LedgerUnreadable) as unreadable:
        run_ledger.verify_document(broken)
    assert not isinstance(unreadable.value, run_ledger.LedgerUnverified)

    listing = tmp_path / "listing.json"
    listing.write_text(json.dumps([1, 2]), encoding="utf-8")
    with pytest.raises(run_ledger.LedgerUnreadable):
        run_ledger.verify_document(listing)

    with pytest.raises(run_ledger.LedgerUnreadable):
        run_ledger.verify_document(tmp_path / "absent.json")


def test_the_named_refusal_is_a_ledger_unreadable_and_says_ledger(tmp_path: Path) -> None:
    """Every consumer's refusal tuple already holds the base class, so no tuple needs an edit."""
    assert issubclass(run_ledger.LedgerUnverified, run_ledger.LedgerUnreadable)

    path = _written(tmp_path)
    document = _parse(path)
    document["run_seed"] = [document["run_seed"]]
    _rewrite(path, document)
    with pytest.raises(run_ledger.LedgerUnverified) as refusal:
        run_ledger.verify_document(path)
    assert "ledger" in str(refusal.value), refusal.value
    assert "checkpoint" not in str(refusal.value), refusal.value


# ---------------------------------------------------------------------------
# Reader: the schema strings
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("schema", ["whetstone-run/1", "whetstone-run/99", "something-else/1"])
def test_a_ledger_of_any_other_schema_is_refused_naming_both(tmp_path: Path, schema: str) -> None:
    """AC 6: `/1` and anything unknown are refused, and the message names both accepted schemas.

    `test_backend.py:201-218` passes unedited on this: `LEDGER_SCHEMA` is `/3`, so it is not
    `/1`, and a `/1` stub still raises.
    """
    path = _written(tmp_path)
    document = _parse(path)
    document["schema"] = schema
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnreadable) as refusal:
        run_ledger.verify_document(path)
    assert run_ledger.LEDGER_SCHEMA_V2 in str(refusal.value)
    assert run_ledger.LEDGER_SCHEMA_V3 in str(refusal.value)


def test_a_v2_payload_relabelled_v3_without_claims_is_refused(tmp_path: Path) -> None:
    path, document = _v2(tmp_path)
    document["schema"] = run_ledger.LEDGER_SCHEMA_V3
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnverified, match="claims mapping"):
        run_ledger.verify_document(path)


# ---------------------------------------------------------------------------
# The limit, pinned rather than implied
# ---------------------------------------------------------------------------


def test_a_forger_who_recomputes_the_claims_is_not_caught(tmp_path: Path) -> None:
    """AC 7, the documented limit: the digest is an unkeyed hash, never authentication.

    Editing a value and recomputing `claims` and `digest` consistently (`PRD` § 3) produces a
    document this reader accepts and reports `sealed`. That is the boundary the vocabulary
    states, not a defect: the seal catches accident-shaped edits and disagreement with a digest
    cited elsewhere; anyone who can edit the file can recompute both.
    """
    path = _written(tmp_path)
    document = _parse(path)
    document["run_seed"] = 7
    body = {key: value for key, value in document.items() if key not in seal.UNSEALED_KEYS}
    document["claims"] = seal.claim_hashes(
        body, subject="ledger", refuse=run_ledger.LedgerUnverified
    )
    document["digest"] = seal.claims_digest(document["claims"], schema=run_ledger.LEDGER_SCHEMA_V3)
    _rewrite(path, document)

    forged = run_ledger.verify_document(path)

    assert forged.sealed is True
    assert forged.document["run_seed"] == 7
