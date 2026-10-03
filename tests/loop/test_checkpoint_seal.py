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
