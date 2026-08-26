"""The untrained checkpoint: `verify_checkpoint` must accept it, and refuse its contradictions.

The baseline an untrained open base produces has no adapter, so its checkpoint holds **no
files** — the one shape `verify_checkpoint` refuses today. This file pins the extension:
`files: []` verifies only when the provenance declares `untrained: true`, the label and the
bytes must agree in both directions (untrained with files is refused, trained with none is
refused), and every pre-existing refusal still holds for the untrained shape.

The trained path is not re-tested here: `tests/loop/test_sft.py` pins it, and the two files
together assert that the extension is keyed on the flag rather than on emptiness.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from whetstone.loop import sft

#: The declared base for the untrained-shape fixtures. A pinned input — the *choice* of base is
#: the operator's, recorded in the runbook, never decided in this aspect.
BASE = {"repo_id": "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit", "revision": "d1e3b69"}

#: The digest of an empty adapter set — `_digest_of(())` — computed here for the fixture, so the
#: honest untrained provenance and a doctored one differ only in what the test intends.
EMPTY_DIGEST = hashlib.sha256(b"").hexdigest()


def _write_provenance(directory: Path, payload: dict[str, object]) -> Path:
    """Write a provenance in `write_checkpoint`'s byte conventions: sorted, indented, newline."""
    document = directory / sft.CHECKPOINT_FILE
    document.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return document


def _untrained(directory: Path, *, untrained: bool = True) -> Path:
    """The untrained shape: schema, base, no files, the empty-set digest — and the flag by default.

    The flag is a parameter so the anti-vacuity refusal and the trained-shape pin can build the
    same provenance with one field omitted, byte-identical in every other respect.
    """
    payload: dict[str, object] = {
        "schema": sft.CHECKPOINT_SCHEMA,
        "base": dict(BASE),
        "files": [],
        "digest": EMPTY_DIGEST,
    }
    if untrained:
        payload["untrained"] = True
    directory.mkdir(parents=True, exist_ok=True)
    return _write_provenance(directory, payload)


def test_an_untrained_checkpoint_verifies(tmp_path: Path) -> None:
    """The untrained base is a checkpoint, hashed like any other — its digest is the empty set's.

    Nothing about the untrained shape is exempted from being identified: the returned
    `Checkpoint` carries the flag and the digest, so a gate that compares baselines names bytes,
    exactly as it names a night's adapter bytes.
    """
    directory = tmp_path / "untrained"
    _untrained(directory)

    checkpoint = sft.verify_checkpoint(directory)

    assert checkpoint.untrained is True
    assert checkpoint.digest == EMPTY_DIGEST
    assert checkpoint.files == ()


def test_a_trained_checkpoint_with_no_files_is_still_refused(tmp_path: Path) -> None:
    """Trained provenance carries no `untrained` key, so its empty `files` stays the old refusal."""
    directory = tmp_path / "trained-empty"
    _untrained(directory, untrained=False)

    with pytest.raises(sft.CheckpointUnverified):
        sft.verify_checkpoint(directory)


def test_untrained_with_files_is_refused(tmp_path: Path) -> None:
    """`untrained: true` beside a recorded adapter: the label and the bytes disagree.

    The stub file is real and its record is self-consistent (matching size and sha256, digest
    reduced from the records through `sft._digest_of` by identity), so the only thing wrong is
    the flag's promise — the refusal must name the contradiction, not a moved byte.
    """
    directory = tmp_path / "contradiction"
    directory.mkdir()
    stub = directory / "adapters.safetensors"
    stub.write_bytes(b"not a tensor")
    record = sft.CheckpointFile(
        name=stub.name,
        bytes=stub.stat().st_size,
        sha256=hashlib.sha256(b"not a tensor").hexdigest(),
    )
    payload: dict[str, object] = {
        "schema": sft.CHECKPOINT_SCHEMA,
        "untrained": True,
        "base": dict(BASE),
        "files": [{"name": record.name, "bytes": record.bytes, "sha256": record.sha256}],
        "digest": sft._digest_of((record,)),
    }
    _write_provenance(directory, payload)

    with pytest.raises(sft.CheckpointUnverified, match="the label and the bytes disagree"):
        sft.verify_checkpoint(directory)


def test_a_doctored_untrained_digest_is_refused(tmp_path: Path) -> None:
    """A hand-edited digest is refused for the untrained shape too: the document disagrees with
    itself.

    The digest check already covers the empty case — `_digest_of(())` is a fixed value, so a
    doctored untrained provenance cannot rescue itself by claiming any other digest. The refusal
    is the pre-existing one, reached now through the untrained branch.
    """
    directory = tmp_path / "doctored"
    _untrained(directory)
    document = directory / sft.CHECKPOINT_FILE
    payload = json.loads(document.read_text(encoding="utf-8"))
    payload["digest"] = "0" * 64
    _write_provenance(directory, payload)

    with pytest.raises(sft.CheckpointUnverified, match="disagrees with itself"):
        sft.verify_checkpoint(directory)


def test_the_existing_refusals_hold_for_untrained(tmp_path: Path) -> None:
    """Missing provenance, wrong schema and unreadable JSON refuse the untrained shape unchanged."""
    missing = tmp_path / "missing"
    missing.mkdir()
    with pytest.raises(sft.CheckpointUnverified, match=r"no provenance\.json"):
        sft.verify_checkpoint(missing)

    wrong_schema = tmp_path / "wrong-schema"
    wrong_schema.mkdir()
    _write_provenance(
        wrong_schema,
        {
            "schema": "whetstone-checkpoint/2",
            "untrained": True,
            "base": dict(BASE),
            "files": [],
            "digest": EMPTY_DIGEST,
        },
    )
    with pytest.raises(sft.CheckpointUnverified, match="does not declare schema"):
        sft.verify_checkpoint(wrong_schema)

    unreadable = tmp_path / "unreadable"
    unreadable.mkdir()
    (unreadable / sft.CHECKPOINT_FILE).write_text("{not json", encoding="utf-8")
    with pytest.raises(sft.CheckpointUnverified, match="could not be read"):
        sft.verify_checkpoint(unreadable)


def test_an_untrained_checkpoint_without_the_flag_is_refused(tmp_path: Path) -> None:
    """Anti-vacuity: the extension is keyed on the flag, not on the emptiness.

    If the implementation accepted empty `files` unconditionally, this fixture — identical to
    the honest untrained provenance except for the missing flag — would verify. It must refuse
    with the trained-path refusal, which is what pins the flag as the key.
    """
    directory = tmp_path / "no-flag"
    _untrained(directory, untrained=False)

    with pytest.raises(sft.CheckpointUnverified, match="records no files"):
        sft.verify_checkpoint(directory)


#: The pre-extension key set of a trained provenance — the byte-identity pin for the trained path.
#: Any key added to `write_checkpoint`'s document fails this test, and `untrained` is exactly the
#: key this aspect must not add there.
TRAINED_KEYS = {
    "schema",
    "digest",
    "base",
    "dataset_digest",
    "run_seed",
    "training_args",
    "tool_versions",
    "validation",
    "capacity_probe",
    "files",
}


def _trained(tmp_path: Path) -> Path:
    """A trained checkpoint via `write_checkpoint` — the `test_sft._written` shape, minimally.

    The helpers in `tests/loop/test_sft.py` are module-private, so this file does not import
    them; the part that matters for provenance identity is `write_checkpoint`'s own document,
    and that is exercised here through the real writer.
    """
    directory = tmp_path / "trained"
    directory.mkdir()
    (directory / sft.ADAPTER_FILE).write_bytes(b"not a tensor")
    sft.write_checkpoint(
        directory,
        repo_id=BASE["repo_id"],
        revision=BASE["revision"],
        dataset_digest="d" * 64,
        run_seed=20260826,
        args=sft.TrainingArgs(),
        tool_versions={"python": "3.12.0"},
        valid_split="",
        capacity=sft.CapacityProbe(
            iters=sft.CAPACITY_PROBE_ITERS,
            headroom_bytes=sft.CAPACITY_HEADROOM_BYTES,
            peak_bytes=4 * 1024**3,
            seconds=0.25,
        ),
    )
    return directory


def test_write_baseline_checkpoint_round_trips(tmp_path: Path) -> None:
    """The writer's output is the untrained shape the verifier accepts — one shape, both ends.

    The provenance declares the flag, no files, the base verbatim, the tool versions sorted,
    and the empty set's digest; the returned `Checkpoint` and the re-verification agree with
    the document on every field.
    """
    directory = tmp_path / "baseline"
    tool_versions = {"uv": "0.6.0", "python": "3.12.0"}

    checkpoint = sft.write_baseline_checkpoint(
        directory,
        repo_id=BASE["repo_id"],
        revision=BASE["revision"],
        tool_versions=tool_versions,
    )

    assert checkpoint.untrained is True
    assert checkpoint.digest == EMPTY_DIGEST
    assert checkpoint.files == ()
    assert checkpoint.directory == directory

    provenance = json.loads(
        (directory / sft.CHECKPOINT_FILE).read_text(encoding="utf-8")
    )
    assert provenance["untrained"] is True
    assert provenance["files"] == []
    assert provenance["base"] == BASE
    assert provenance["tool_versions"] == {"python": "3.12.0", "uv": "0.6.0"}
    assert provenance["digest"] == EMPTY_DIGEST

    reverified = sft.verify_checkpoint(directory)
    assert reverified.untrained is True
    assert reverified.digest == EMPTY_DIGEST


def test_write_baseline_checkpoint_refuses_a_non_empty_directory(tmp_path: Path) -> None:
    """An adapter beside an untrained provenance is the contradiction the flag exists to exclude.

    The opposite sign of `write_checkpoint`'s empty-directory refusal: a baseline declaring
    `untrained: true` into a directory that holds bytes would label a night's adapter a base
    that never trained. The refusal names the directory.
    """
    directory = tmp_path / "baseline"
    directory.mkdir()
    (directory / sft.ADAPTER_FILE).write_bytes(b"not a tensor")

    with pytest.raises(
        sft.CheckpointUnverified, match=re.escape(str(directory))
    ):
        sft.write_baseline_checkpoint(
            directory,
            repo_id=BASE["repo_id"],
            revision=BASE["revision"],
            tool_versions={},
        )


def test_trained_provenance_carries_no_untrained_key(tmp_path: Path) -> None:
    """The trained writer is byte-identical to today: no `untrained` key, and no other drift.

    The key set is asserted exactly rather than by absence alone, so a later edit that adds
    *any* key to `write_checkpoint`'s document fails this pin — the trained path's identity is
    the whole pre-extension set, not just the absence of the one new flag.
    """
    directory = _trained(tmp_path)
    provenance = json.loads(
        (directory / sft.CHECKPOINT_FILE).read_text(encoding="utf-8")
    )

    assert "untrained" not in provenance
    assert set(provenance) == TRAINED_KEYS