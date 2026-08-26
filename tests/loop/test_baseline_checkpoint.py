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