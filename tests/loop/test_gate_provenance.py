"""The gate reads which dataset trained a candidate, and refuses a checkpoint that cannot say.

A promotion record that does not name its training data cannot be audited against the held-out
split for leakage. The digest is read from the checkpoint's own `provenance.json`, the document
`sft.write_checkpoint` writes, and never defaulted: a trained checkpoint with no recorded digest
is a refusal (exit 2), not an empty string. An untrained checkpoint trained on nothing, and says
so with an explicit `None` rather than an invented digest.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whetstone.loop import backend, gate, sft

DIGEST = "d" * 64
REPO = "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit"


def _trained(directory: Path) -> sft.Checkpoint:
    directory.mkdir(parents=True)
    args = sft.TrainingArgs()
    (directory / args.adapter_file).write_bytes(b"not a tensor")
    return sft.write_checkpoint(
        directory,
        repo_id=REPO,
        revision="d1e3b69",
        dataset_digest=DIGEST,
        run_seed=20260820,
        args=args,
        tool_versions={"python": "3.12.0"},
        valid_split="",
        capacity=sft.CapacityProbe(
            iters=sft.CAPACITY_PROBE_ITERS,
            headroom_bytes=sft.CAPACITY_HEADROOM_BYTES,
            peak_bytes=1,
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


def _rewrite(checkpoint: sft.Checkpoint, mutate: object) -> None:
    path = checkpoint.directory / sft.CHECKPOINT_FILE
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)  # type: ignore[operator]
    path.write_text(json.dumps(document), encoding="utf-8")


def test_a_trained_checkpoint_yields_the_digest_it_recorded(tmp_path: Path) -> None:
    checkpoint = _trained(tmp_path / "cp")

    assert gate._checkpoint_dataset_digest(checkpoint) == DIGEST


def test_an_untrained_checkpoint_yields_an_explicit_absence(tmp_path: Path) -> None:
    directory = tmp_path / "base"
    directory.mkdir()
    checkpoint = sft.write_baseline_checkpoint(
        directory, repo_id=REPO, revision="d1e3b69", tool_versions={"python": "3.12.0"}
    )

    assert gate._checkpoint_dataset_digest(checkpoint) is None


def _drop(document: dict[str, object]) -> None:
    del document["dataset_digest"]


@pytest.mark.parametrize(
    ("label", "mutate"),
    [
        ("missing", _drop),
        ("empty", lambda d: d.update(dataset_digest="")),
        ("null", lambda d: d.update(dataset_digest=None)),
        ("integer", lambda d: d.update(dataset_digest=12345)),
        ("list", lambda d: d.update(dataset_digest=[DIGEST])),
        ("short", lambda d: d.update(dataset_digest="d" * 63)),
        ("long", lambda d: d.update(dataset_digest="d" * 65)),
        ("not hex", lambda d: d.update(dataset_digest="z" * 64)),
        ("uppercase", lambda d: d.update(dataset_digest="D" * 64)),
        ("whitespace", lambda d: d.update(dataset_digest=" " + "d" * 63)),
    ],
)
def test_a_trained_checkpoint_without_a_well_formed_digest_is_a_refusal(
    tmp_path: Path, label: str, mutate: object
) -> None:
    checkpoint = _trained(tmp_path / "cp")
    _rewrite(checkpoint, mutate)

    with pytest.raises(gate.DatasetDigestUnrecorded) as caught:
        gate._checkpoint_dataset_digest(checkpoint)

    assert isinstance(caught.value, gate.REFUSALS), label
    message = str(caught.value)
    assert str(checkpoint.directory) in message, message
    assert "dataset_digest" in message, message
