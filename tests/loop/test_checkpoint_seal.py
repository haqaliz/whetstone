"""The seal's canonical claims, and the `whetstone-checkpoint/2` document built from them.

A checkpoint's `provenance.json` claims are sealed into its digest by hashing each claim's
canonical bytes. If those bytes drifted between releases every sealed checkpoint would read as
tampered, so the encoding is pinned here by a literal, never recomputed in the test.

The v2 document is then exercised the way a reviewer would attack it: each cheat is shown to be
refused under v2 **and** accepted by the file-only seal v1 relies on, so the test proves the new
check does the work. "Sealed" means what PRD § 3 says and no more — the forger who recomputes the
unkeyed digest is not caught, and a test below says so by name.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from whetstone.loop import backend, sft

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
    assert sft.CHECKPOINT_SCHEMA == sft.CHECKPOINT_SCHEMA_V2, (
        "WHY THIS IS A FAILURE: the schema written is not the sealed one, so a new checkpoint's "
        "claims ride outside its digest"
    )
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


def test_int_keys_hash_as_the_strings_a_reader_gets_back() -> None:
    """Int keys sort numerically in memory and as strings once written: 2 < 10, but "10" < "2".

    Only the inner round trip in `_canonical` makes the writer hash the order a reader parses
    back. Without it this mapping hashes one way when sealed and another when verified, so every
    checkpoint carrying one would read as tampered.
    """
    body: dict[str, Any] = {"m": {10: 1, 2: 1}}
    reread = json.loads(json.dumps(body))
    assert sft._claim_hashes(body) == sft._claim_hashes(reread)


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


# --- The v2 document: written sealed, verified claim by claim. ------------------------------

_BASE = {"repo_id": "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit", "revision": "d1e3b69"}
_DATASET_DIGEST = "d" * 64


def _written(directory: Path) -> sft.Checkpoint:
    """A trained checkpoint over a stub adapter, through the real writer."""
    directory.mkdir(parents=True)
    (directory / sft.ADAPTER_FILE).write_bytes(b"not a tensor")
    return sft.write_checkpoint(
        directory,
        repo_id=_BASE["repo_id"],
        revision=_BASE["revision"],
        dataset_digest=_DATASET_DIGEST,
        run_seed=20261003,
        args=sft.TrainingArgs(),
        tool_versions={"python": "3.12.0"},
        valid_split="",
        capacity=sft.CapacityProbe(
            iters=sft.CAPACITY_PROBE_ITERS,
            headroom_bytes=sft.CAPACITY_HEADROOM_BYTES,
            peak_bytes=4 * 1024**3,
            seconds=0.25,
        ),
        backend=backend.Backend(
            name=backend.MLX,
            library="mlx-lm",
            version="0.31.3",
            device="Apple M4 Max",
            device_memory_bytes=38654705664,
        ),
    )


def _read(directory: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(
        (directory / sft.CHECKPOINT_FILE).read_text(encoding="utf-8")
    )
    return document


def _write(directory: Path, document: Mapping[str, Any]) -> None:
    (directory / sft.CHECKPOINT_FILE).write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _under_file_only_seal(directory: Path, document: Mapping[str, Any]) -> sft.Checkpoint:
    """Write `document` as the file-only seal (v1) would accept it, and verify it.

    The schema label goes back to v1 and the digest is reduced from the file hashes alone, which
    is everything the v1 seal ever checked. Every other key — the edit under test, and any
    `claims` block, which v1 ignores — stays as given. If this verifies, the edit passes under
    the weaker check, so the v2 refusal beside it is the new check doing the work.
    """
    downgraded = dict(document)
    downgraded["schema"] = sft.CHECKPOINT_SCHEMA_V1
    downgraded["digest"] = sft._digest_of(
        tuple(
            sft.CheckpointFile(name=one["name"], bytes=one["bytes"], sha256=one["sha256"])
            for one in document["files"]
        )
    )
    _write(directory, downgraded)
    return sft.verify_checkpoint(directory)


def test_a_v2_checkpoint_round_trips_sealed(tmp_path: Path) -> None:
    """Criterion 1: written v2, verified v2, the same digest at both ends, and `sealed`."""
    written = _written(tmp_path / "cp")
    document = _read(written.directory)

    assert document["schema"] == sft.CHECKPOINT_SCHEMA_V2
    assert set(document["claims"]) == set(document) - sft._UNSEALED_KEYS
    assert document["digest"] == sft._claims_digest(document["claims"])
    assert written.sealed is True

    verified = sft.verify_checkpoint(written.directory)

    assert verified.sealed is True
    assert verified.digest == written.digest == document["digest"]
    assert verified.files == written.files
    assert verified.base_repo_id == _BASE["repo_id"]
    assert verified.base_revision == _BASE["revision"]
    assert verified.dataset_digest == _DATASET_DIGEST
    assert (written.base_repo_id, written.base_revision, written.dataset_digest) == (
        _BASE["repo_id"],
        _BASE["revision"],
        _DATASET_DIGEST,
    )


def _set_dataset_digest(document: dict[str, Any]) -> None:
    document["dataset_digest"] = "e" * 64


def _set_repo_id(document: dict[str, Any]) -> None:
    document["base"]["repo_id"] = "mlx-community/Qwen2.5-Coder-0.5B-Instruct-4bit"


def _set_revision(document: dict[str, Any]) -> None:
    document["base"]["revision"] = "0000000"


def _set_backend(document: dict[str, Any]) -> None:
    document["backend"]["name"] = "torch-cpu"


def _set_run_seed(document: dict[str, Any]) -> None:
    document["run_seed"] = 1


def _set_training_args(document: dict[str, Any]) -> None:
    document["training_args"]["iters"] = 1


@pytest.mark.parametrize(
    ("claim", "edit"),
    [
        ("dataset_digest", _set_dataset_digest),
        ("base", _set_repo_id),
        ("base", _set_revision),
        ("backend", _set_backend),
        ("run_seed", _set_run_seed),
        ("training_args", _set_training_args),
    ],
    ids=["dataset_digest", "base.repo_id", "base.revision", "backend", "run_seed", "training_args"],
)
def test_an_edited_claim_is_refused_by_name(
    tmp_path: Path, claim: str, edit: Callable[[dict[str, Any]], None]
) -> None:
    """Criterion 2: a claim edited after sealing, `digest` and `claims` left alone, is named."""
    written = _written(tmp_path / "cp")
    document = _read(written.directory)
    edit(document)
    _write(written.directory, document)

    with pytest.raises(sft.CheckpointUnverified, match=re.escape(repr(claim))):
        sft.verify_checkpoint(written.directory)


# Criterion 3: each cheat fails under v2 and passes under the file-only seal. The second half is
# what keeps each test honest — a cheat the old seal also caught would prove nothing new here.


def test_cheat_a_an_added_key_with_no_claim_is_refused(tmp_path: Path) -> None:
    written = _written(tmp_path / "cp")
    document = _read(written.directory)
    document["promoted"] = True
    _write(written.directory, document)

    with pytest.raises(sft.CheckpointUnverified, match=r"'promoted', which no claim seals"):
        sft.verify_checkpoint(written.directory)

    assert _under_file_only_seal(written.directory, document).sealed is False


def test_cheat_b_a_key_and_its_claim_deleted_together_is_refused(tmp_path: Path) -> None:
    written = _written(tmp_path / "cp")
    document = _read(written.directory)
    del document["dataset_digest"]
    del document["claims"]["dataset_digest"]
    _write(written.directory, document)

    with pytest.raises(sft.CheckpointUnverified, match="disagrees with itself"):
        sft.verify_checkpoint(written.directory)

    assert _under_file_only_seal(written.directory, document).dataset_digest is None


def test_cheat_c_two_claims_swapped_is_refused(tmp_path: Path) -> None:
    written = _written(tmp_path / "cp")
    document = _read(written.directory)
    claims = document["claims"]
    claims["run_seed"], claims["dataset_digest"] = claims["dataset_digest"], claims["run_seed"]
    _write(written.directory, document)

    with pytest.raises(
        sft.CheckpointUnverified, match="was changed after the checkpoint was sealed"
    ):
        sft.verify_checkpoint(written.directory)

    assert _under_file_only_seal(written.directory, document).sealed is False


def test_cheat_d_the_schema_rewritten_to_v1_is_refused(tmp_path: Path) -> None:
    """The downgrade: a sealed document relabelled v1 to dodge the claim check.

    Its digest reduces from the claims, never from the files alone, so the v1 path's own
    comparison refuses it. The same edited `dataset_digest` in a document the file-only seal
    built — digest from the files — verifies, which is exactly the hole v2 closes.
    """
    written = _written(tmp_path / "cp")
    document = _read(written.directory)
    _set_dataset_digest(document)
    document["schema"] = sft.CHECKPOINT_SCHEMA_V1
    _write(written.directory, document)

    with pytest.raises(sft.CheckpointUnverified, match="disagrees with itself"):
        sft.verify_checkpoint(written.directory)

    accepted = _under_file_only_seal(written.directory, document)
    assert accepted.dataset_digest == "e" * 64
    assert accepted.sealed is False


def test_a_forger_who_recomputes_the_digest_is_not_caught(tmp_path: Path) -> None:
    """PRD § 3's stated limit, pinned so nobody reads `sealed` as more than it is.

    The digest is an unkeyed hash. Rewriting a claim, its hash and the digest consistently
    produces a document that verifies and reports `sealed`: the seal catches accident-shaped
    edits and disagreement with a digest cited elsewhere, never a writer who recomputes it.
    """
    written = _written(tmp_path / "cp")
    document = _read(written.directory)
    _set_dataset_digest(document)
    document["claims"] = sft._claim_hashes(
        {key: value for key, value in document.items() if key not in sft._UNSEALED_KEYS}
    )
    document["digest"] = sft._claims_digest(document["claims"])
    _write(written.directory, document)

    forged = sft.verify_checkpoint(written.directory)

    assert forged.sealed is True
    assert forged.dataset_digest == "e" * 64
    assert forged.digest != written.digest


@pytest.mark.parametrize(
    "claims",
    [None, "x", ["files"], {"files": 1}],
    ids=["missing", "string", "list", "non-string-hash"],
)
def test_a_v2_document_without_a_claims_mapping_is_refused(tmp_path: Path, claims: Any) -> None:
    written = _written(tmp_path / "cp")
    document = _read(written.directory)
    if claims is None:
        del document["claims"]
    else:
        document["claims"] = claims
    _write(written.directory, document)

    with pytest.raises(sft.CheckpointUnverified, match="claims"):
        sft.verify_checkpoint(written.directory)


def test_a_claim_with_no_key_is_refused_by_name(tmp_path: Path) -> None:
    written = _written(tmp_path / "cp")
    document = _read(written.directory)
    del document["run_seed"]
    _write(written.directory, document)

    with pytest.raises(sft.CheckpointUnverified, match=r"claim 'run_seed'"):
        sft.verify_checkpoint(written.directory)


def test_a_moved_claim_is_refused_before_the_files_are_trusted(tmp_path: Path) -> None:
    """A tampered `files` list names the claim, not a missing file: claims are checked first."""
    written = _written(tmp_path / "cp")
    document = _read(written.directory)
    document["files"][0]["name"] = "elsewhere.safetensors"
    _write(written.directory, document)

    with pytest.raises(sft.CheckpointUnverified, match=r"claim 'files'"):
        sft.verify_checkpoint(written.directory)


def test_a_tampered_file_is_still_refused_under_v2(tmp_path: Path) -> None:
    written = _written(tmp_path / "cp")
    (written.directory / sft.ADAPTER_FILE).write_bytes(b"not a tensoR")

    with pytest.raises(sft.CheckpointUnverified, match="not the bytes the night wrote"):
        sft.verify_checkpoint(written.directory)


def test_an_unknown_schema_is_refused_naming_both(tmp_path: Path) -> None:
    written = _written(tmp_path / "cp")
    document = _read(written.directory)
    document["schema"] = "whetstone-checkpoint/3"
    _write(written.directory, document)

    with pytest.raises(sft.CheckpointUnverified, match="does not declare schema") as caught:
        sft.verify_checkpoint(written.directory)
    assert sft.CHECKPOINT_SCHEMA_V1 in str(caught.value)
    assert sft.CHECKPOINT_SCHEMA_V2 in str(caught.value)


# --- v1: verifies exactly as before, and is never sealed. -----------------------------------


def _portability_arm_shaped(directory: Path, **extra: Any) -> Path:
    """A v1 document in the `checkpoints/portability-arm` shape: Torch-trained, files-only seal."""
    directory.mkdir(parents=True)
    adapter = directory / sft.ADAPTER_FILE
    adapter.write_bytes(b"not a tensor")
    record = sft.CheckpointFile(
        name=adapter.name,
        bytes=adapter.stat().st_size,
        sha256=hashlib.sha256(b"not a tensor").hexdigest(),
    )
    document: dict[str, Any] = {
        "schema": sft.CHECKPOINT_SCHEMA_V1,
        "digest": sft._digest_of((record,)),
        "base": {"repo_id": "Qwen/Qwen2.5-Coder-0.5B-Instruct", "revision": "a1b2c3d"},
        "dataset_digest": "f" * 64,
        "run_seed": 20260906,
        "backend": {
            "device": "cpu",
            "device_memory_bytes": 16637317120,
            "library": "torch",
            "name": "torch-cpu",
            "version": "2.14.0+cpu",
        },
        "training_args": sft.TrainingArgs().recorded(),
        "tool_versions": {"python": "3.12.0", "torch": "2.14.0+cpu"},
        "validation": "validated against the run's own valid split",
        "capacity_probe": {"iters": 8, "headroom_bytes": 1, "peak_bytes": 1, "seconds": 0.1},
        "files": [{"name": record.name, "bytes": record.bytes, "sha256": record.sha256}],
        **extra,
    }
    _write(directory, document)
    return directory


def test_a_v1_portability_arm_checkpoint_verifies_unsealed(tmp_path: Path) -> None:
    """Criterion 4: the one real checkpoint's shape still verifies, its claims read as recorded."""
    verified = sft.verify_checkpoint(_portability_arm_shaped(tmp_path / "arm"))

    assert verified.sealed is False
    assert verified.dataset_digest == "f" * 64
    assert verified.base_repo_id == "Qwen/Qwen2.5-Coder-0.5B-Instruct"
    assert verified.base_revision == "a1b2c3d"
    assert verified.backend is not None
    assert verified.backend["name"] == "torch-cpu"


def test_a_v1_document_carrying_claims_is_never_sealed(tmp_path: Path) -> None:
    """Criterion 5: a `claims` key does not promote a v1 document; the schema decides."""
    directory = _portability_arm_shaped(tmp_path / "arm", claims={"files": "0" * 64})

    assert sft.verify_checkpoint(directory).sealed is False


def test_a_v1_dataset_digest_is_returned_as_recorded_unvalidated(tmp_path: Path) -> None:
    """Shape is the gate's check, not the verifier's: an int comes back as the int recorded."""
    directory = _portability_arm_shaped(tmp_path / "arm", dataset_digest=7)

    assert sft.verify_checkpoint(directory).dataset_digest == 7


def test_an_old_reader_refuses_v2(tmp_path: Path) -> None:
    """Criterion 9: the equality check every pre-v2 reader ran, against a v2 document."""

    def old_reader_accepts(raw: Any) -> bool:
        return isinstance(raw, dict) and raw.get("schema") == "whetstone-checkpoint/1"

    written = _written(tmp_path / "cp")

    assert old_reader_accepts(_read(written.directory)) is False


def test_a_written_document_of_every_json_type_round_trips(tmp_path: Path) -> None:
    """Criterion 10: int, float, None, nested mapping and list — sealed as read back.

    The real writer carries ints (`run_seed`), floats (`learning_rate`, `seconds`), nested
    mappings and a list; a `None` and an int-keyed mapping are added by sealing a body by hand,
    since no writer field holds one today and the verifier must not care which writer it was.
    """
    written = _written(tmp_path / "cp")
    assert sft.verify_checkpoint(written.directory).sealed is True

    document = _read(written.directory)
    body = {key: value for key, value in document.items() if key not in sft._UNSEALED_KEYS}
    body["nothing"] = None
    body["by_number"] = {10: 1.5, 2: [None, 3]}
    claims = sft._claim_hashes(body)
    _write(
        written.directory,
        {
            **body,
            "schema": sft.CHECKPOINT_SCHEMA_V2,
            "claims": claims,
            "digest": sft._claims_digest(claims),
        },
    )

    verified = sft.verify_checkpoint(written.directory)
    assert verified.sealed is True
    assert claims == sft._claim_hashes(json.loads(json.dumps(body)))


# --- The claim lines must split back one way only. ------------------------------------------


def _resealed(document: dict[str, Any]) -> dict[str, Any]:
    """`document` with its claims and digest recomputed the way any writer can (PRD § 3)."""
    document["claims"] = sft._claim_hashes(
        {key: value for key, value in document.items() if key not in sft._UNSEALED_KEYS}
    )
    document["digest"] = sft._claims_digest(document["claims"])
    return document


def test_a_merged_claim_key_cannot_delete_two_keys_under_one_digest(tmp_path: Path) -> None:
    """Cheat 3(b) through the line format: two claim lines forged into one key.

    `_claims_digest` joins `key:hash` lines with a newline, so one claim keyed
    `"backend:<H_backend>\\nbase"` carrying `base`'s hash produces the same digest text as the
    two honest claims. With both keys deleted the digest is unchanged — unless a newline in a
    claim key is refused. The file-only seal accepts the same edit, so the refusal is the new
    check doing the work.
    """
    written = _written(tmp_path / "cp")
    document = _read(written.directory)
    claims = document["claims"]
    merged = f"backend:{claims['backend']}\nbase"
    forged_claims = {key: value for key, value in claims.items() if key not in {"backend", "base"}}
    forged_claims[merged] = claims["base"]
    assert sft._claims_digest(forged_claims) == document["digest"], "the forgery's premise"
    # The merged key carries `base`'s value, so its hash is the claim beside it and the orphan
    # and re-hash checks are both satisfied: only the key's own shape gives it away.
    document[merged] = document.pop("base")
    del document["backend"]
    document["claims"] = forged_claims
    _write(written.directory, document)

    # Matched on the verifier's own refusal, not just the key: `_claim_hashes` refuses the same
    # key when the body is re-hashed, and that second guard must not be what makes this pass.
    with pytest.raises(sft.CheckpointUnverified, match="one claim line forged to read as two"):
        sft.verify_checkpoint(written.directory)

    accepted = _under_file_only_seal(written.directory, document)
    assert (accepted.backend, accepted.base_repo_id) == (None, None)


@pytest.mark.parametrize(
    "value",
    ["0" * 63, "0" * 65, "A" * 64, "g" * 64],
    ids=["short", "long", "upper", "non-hex"],
)
def test_a_claim_value_that_is_not_a_sha256_is_refused(tmp_path: Path, value: str) -> None:
    written = _written(tmp_path / "cp")
    document = _read(written.directory)
    document["claims"]["run_seed"] = value
    _write(written.directory, document)

    with pytest.raises(sft.CheckpointUnverified, match=r"claim 'run_seed' .* not a sha256"):
        sft.verify_checkpoint(written.directory)


def test_a_body_key_with_a_newline_is_refused_at_write_time() -> None:
    with pytest.raises(sft.CheckpointUnverified, match=re.escape(repr("a\nb"))):
        sft._claim_hashes({"ok": 1, "a\nb": 2})


def test_a_consistently_resealed_v2_document_with_no_files_is_refused(tmp_path: Path) -> None:
    """Without `files` there is nothing to re-hash: refused by name, never a `KeyError`."""
    written = _written(tmp_path / "cp")
    document = _read(written.directory)
    del document["files"]
    _write(written.directory, _resealed(document))

    with pytest.raises(sft.CheckpointUnverified, match="'files'"):
        sft.verify_checkpoint(written.directory)


def test_the_written_checkpoint_agrees_with_the_verified_one(tmp_path: Path) -> None:
    """What `write_checkpoint` returns and what `verify_checkpoint` reads back are one record."""
    written = _written(tmp_path / "cp")
    verified = sft.verify_checkpoint(written.directory)

    fields = ("base_repo_id", "base_revision", "dataset_digest", "sealed", "backend")
    assert {name: getattr(written, name) for name in fields} == {
        name: getattr(verified, name) for name in fields
    }
    assert written.backend is not None


def _untrained(directory: Path, *, revision: str = _BASE["revision"]) -> sft.Checkpoint:
    return sft.write_baseline_checkpoint(
        directory,
        repo_id=_BASE["repo_id"],
        revision=revision,
        tool_versions={"python": "3.12.0"},
    )


def test_the_untrained_base_is_written_sealed(tmp_path: Path) -> None:
    written = _untrained(tmp_path / "base")

    assert _read(written.directory)["schema"] == sft.CHECKPOINT_SCHEMA_V2
    verified = sft.verify_checkpoint(written.directory)
    assert verified.untrained and verified.sealed
    assert verified.dataset_digest is None
    assert verified.files == ()


def test_the_written_untrained_checkpoint_agrees_with_the_verified_one(tmp_path: Path) -> None:
    written = _untrained(tmp_path / "base")
    verified = sft.verify_checkpoint(written.directory)

    fields = (
        "digest",
        "files",
        "untrained",
        "sealed",
        "backend",
        "base_repo_id",
        "base_revision",
        "dataset_digest",
    )
    assert {name: getattr(written, name) for name in fields} == {
        name: getattr(verified, name) for name in fields
    }
    assert written.sealed and written.untrained


def test_two_untrained_bases_at_different_revisions_have_different_digests(
    tmp_path: Path,
) -> None:
    first = _untrained(tmp_path / "a", revision="1" * 40)
    second = _untrained(tmp_path / "b", revision="2" * 40)

    assert first.digest != second.digest


def test_flipping_untrained_in_a_sealed_base_is_refused_naming_it(tmp_path: Path) -> None:
    written = _untrained(tmp_path / "base")
    document = _read(written.directory)
    document["untrained"] = False
    _write(written.directory, document)

    with pytest.raises(sft.CheckpointUnverified, match=r"claim 'untrained' .*'untrained' was"):
        sft.verify_checkpoint(written.directory)


def test_a_hand_built_v1_untrained_document_still_verifies_unsealed(tmp_path: Path) -> None:
    directory = tmp_path / "base"
    directory.mkdir()
    constant = sft._digest_of(())
    _write(
        directory,
        {
            "schema": sft.CHECKPOINT_SCHEMA_V1,
            "digest": constant,
            "base": dict(_BASE),
            "untrained": True,
            "tool_versions": {"python": "3.12.0"},
            "files": [],
        },
    )

    verified = sft.verify_checkpoint(directory)
    assert verified.untrained and not verified.sealed
    assert verified.digest == constant


# --- One writer, one shape: criterion 8. ---------------------------------------------------


def _written_on(directory: Path, runtime: backend.Backend) -> dict[str, Any]:
    """The document `write_checkpoint` leaves for a run on `runtime` — no trainer, no GPU."""
    directory.mkdir(parents=True)
    (directory / sft.ADAPTER_FILE).write_bytes(b"not a tensor")
    sft.write_checkpoint(
        directory,
        repo_id=_BASE["repo_id"],
        revision=_BASE["revision"],
        dataset_digest=_DATASET_DIGEST,
        run_seed=20261003,
        args=sft.TrainingArgs(),
        tool_versions={"python": "3.12.0"},
        valid_split="",
        capacity=sft.CapacityProbe(
            iters=sft.CAPACITY_PROBE_ITERS,
            headroom_bytes=sft.CAPACITY_HEADROOM_BYTES,
            peak_bytes=4 * 1024**3,
            seconds=0.25,
        ),
        backend=runtime,
    )
    return _read(directory)


def test_both_backends_write_the_same_document_shape(tmp_path: Path) -> None:
    """Criterion 8: a key written for one runtime only is a claim the other never makes."""
    mlx = _written_on(
        tmp_path / "mlx",
        backend.Backend(
            name=backend.MLX,
            library="mlx-lm",
            version="0.31.3",
            device="Apple M4 Max",
            device_memory_bytes=38654705664,
        ),
    )
    torch = _written_on(
        tmp_path / "torch",
        backend.Backend(
            name=backend.TORCH,
            library="torch",
            version="2.4.0",
            device="NVIDIA A100-SXM4-40GB",
            device_memory_bytes=42949672960,
        ),
    )

    assert mlx["backend"]["name"] != torch["backend"]["name"]
    assert set(mlx) == set(torch)
    assert set(mlx["claims"]) == set(torch["claims"])
    assert mlx["schema"] == torch["schema"] == sft.CHECKPOINT_SCHEMA_V2


_SEALED_FILE_MARKERS = frozenset({"CHECKPOINT_FILE"})
_WRITE_METHODS = frozenset({"write_text", "write_bytes"})


def _names_the_file(node: ast.AST, aliases: set[str], *, literal: bool = True) -> bool:
    """Whether an expression mentions the checkpoint document by name, literal or alias.

    `literal=False` ignores the bare string, which is how aliases are seeded: a module that binds
    `"provenance.json"` to its own constant (the weights fetch does, for a different document)
    has not bound the checkpoint's. An inline `/ "provenance.json"` on a write is still flagged.
    """
    for each in ast.walk(node):
        if isinstance(each, ast.Name) and (each.id in _SEALED_FILE_MARKERS or each.id in aliases):
            return True
        if isinstance(each, ast.Attribute) and each.attr in _SEALED_FILE_MARKERS:
            return True
        if literal and isinstance(each, ast.Constant) and each.value == "provenance.json":
            return True
    return False


def _opens_for_writing(call: ast.Call, *, mode_at: int) -> bool:
    """Whether an `open` call carries a write, append or exclusive mode (`mode_at` positional)."""
    modes = [
        *call.args[mode_at : mode_at + 1],
        *(one.value for one in call.keywords if one.arg == "mode"),
    ]
    return any(
        isinstance(mode, ast.Constant)
        and isinstance(mode.value, str)
        and set(mode.value) & set("wax+")
        for mode in modes
    )


def _writes_of_the_checkpoint_file(source: str) -> list[int]:
    """Line numbers where `source` writes the checkpoint document; reads and prose are not."""
    tree = ast.parse(source)
    aliases: set[str] = set()
    for _ in range(3):  # a name bound from a name bound from the file, a few steps deep
        for each in ast.walk(tree):
            if isinstance(each, ast.Assign) and _names_the_file(each.value, aliases, literal=False):
                aliases.update(t.id for t in each.targets if isinstance(t, ast.Name))
    lines: list[int] = []
    for each in ast.walk(tree):
        if not isinstance(each, ast.Call):
            continue
        func = each.func
        if isinstance(func, ast.Attribute) and func.attr in _WRITE_METHODS:
            written = _names_the_file(func.value, aliases)
        elif isinstance(func, ast.Attribute) and func.attr == "open":
            written = _names_the_file(func.value, aliases) and _opens_for_writing(each, mode_at=0)
        elif isinstance(func, ast.Name) and func.id == "open" and each.args:
            written = _names_the_file(each.args[0], aliases) and _opens_for_writing(each, mode_at=1)
        else:
            written = False
        if written:
            lines.append(each.lineno)
    return sorted(lines)


def test_the_scanner_flags_a_writer_and_passes_a_reader() -> None:
    writers = [
        "(directory / CHECKPOINT_FILE).write_text('x')",
        "(d / sft.CHECKPOINT_FILE).write_bytes(b'x')",
        "(d / 'provenance.json').write_text('x')",
        "open(d / CHECKPOINT_FILE, 'w')",
        "open(d / 'provenance.json', mode='a')",
        "(d / CHECKPOINT_FILE).open('w')",
        "target = d / CHECKPOINT_FILE\ntarget.write_text('x')",
    ]
    for source in writers:
        assert _writes_of_the_checkpoint_file(source), source

    clean = [
        "json.loads((c / CHECKPOINT_FILE).read_text())",
        "open(c / CHECKPOINT_FILE).read()",
        "open(c / CHECKPOINT_FILE, 'r')",
        '"""Writes provenance.json via CHECKPOINT_FILE.write_text."""\nx = 1',
        "# (d / CHECKPOINT_FILE).write_text('x')\nx = 1",
        "(d / 'other.json').write_text('x')",
        "PROVENANCE_FILE = 'provenance.json'",
    ]
    for source in clean:
        assert _writes_of_the_checkpoint_file(source) == [], source


def test_only_sft_writes_the_checkpoint_document() -> None:
    """Criterion 8: one writer. A second one would be a second shape, sealed or not."""
    root = Path(sft.__file__).resolve().parents[1]  # src/whetstone
    writer = Path(sft.__file__).resolve()
    sources = sorted(root.rglob("*.py"))
    assert writer in sources

    offenders = {
        str(path.relative_to(root)): lines
        for path in sources
        if path != writer
        and (lines := _writes_of_the_checkpoint_file(path.read_text(encoding="utf-8")))
    }

    assert offenders == {}
    assert _writes_of_the_checkpoint_file(writer.read_text(encoding="utf-8"))
