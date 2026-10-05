"""`run_check` can link a checkpoint to the night it claims to have been trained on.

The checkpoint's recorded `dataset_digest` is compared with the digest in the run's
`dataset.json`. The checkpoint's claim is sealed only when it is a v2 checkpoint; the run's
document is not sealed at all, so this is tamper-evidence on one side, not authentication.
The order is the design: the checkpoint is verified and both digests are read before the
overlap comparison, so a leaked run plus another night's checkpoint is a refusal, never a
verdict about the wrong night.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from loop.test_check_leakage import _MEMBERS, _SURVIVOR, _heldout_document, _run
from whetstone.loop import backend, check_leakage, sft

RUN_DIGEST = "d" * 64  # what `_run` writes into dataset.json
OTHER_DIGEST = "e" * 64


def _trained(directory: Path, dataset_digest: str = RUN_DIGEST) -> sft.Checkpoint:
    directory.mkdir(parents=True)
    (directory / sft.ADAPTER_FILE).write_bytes(b"not a tensor")
    return sft.write_checkpoint(
        directory,
        repo_id="mlx-community/Qwen2.5-Coder-32B-Instruct-4bit",
        revision="d1e3b69",
        dataset_digest=dataset_digest,
        run_seed=20261003,
        args=sft.TrainingArgs(),
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


def _as_v1(checkpoint: sft.Checkpoint, mutate: Any = None) -> sft.Checkpoint:
    """Re-issue as a hand-made v1 document (files-only seal), optionally edited first."""
    path = checkpoint.directory / sft.CHECKPOINT_FILE
    document = json.loads(path.read_text(encoding="utf-8"))
    document["schema"] = sft.CHECKPOINT_SCHEMA_V1
    document.pop("claims", None)
    document["digest"] = sft._digest_of(checkpoint.files)
    if mutate is not None:
        mutate(document)
    path.write_text(json.dumps(document), encoding="utf-8")
    return sft.verify_checkpoint(checkpoint.directory)


def _fixture(tmp_path: Path, *, leaked: bool = False) -> tuple[Path, Path]:
    held = _heldout_document(tmp_path / "doc", _MEMBERS)
    training = (_MEMBERS[0],) if leaked else (_SURVIVOR,)
    return _run(tmp_path / "run", private=training), held


def test_a_v2_checkpoint_that_matches_reports_a_sealed_link(tmp_path: Path) -> None:
    run, held = _fixture(tmp_path)
    cp = _trained(tmp_path / "cp")

    report = check_leakage.run_check(run, held, cp.directory)

    assert report.link == check_leakage.DatasetLink(digest=RUN_DIGEST, sealed=True)
    assert report.clean


def test_a_v1_checkpoint_that_matches_reports_an_unsealed_link(tmp_path: Path) -> None:
    run, held = _fixture(tmp_path)
    cp = _as_v1(_trained(tmp_path / "cp"))

    report = check_leakage.run_check(run, held, cp.directory)

    assert report.link is not None
    assert report.link.sealed is False
    assert report.link.digest == RUN_DIGEST


def test_without_a_checkpoint_there_is_no_link(tmp_path: Path) -> None:
    run, held = _fixture(tmp_path)

    assert check_leakage.run_check(run, held).link is None


@pytest.mark.parametrize("leaked", [False, True], ids=["clean-run", "leaked-run"])
def test_a_mismatching_checkpoint_is_refused_even_when_the_run_is_leaked(
    tmp_path: Path, leaked: bool
) -> None:
    """The adversarial case: another night's checkpoint must never reach a verdict."""
    run, held = _fixture(tmp_path, leaked=leaked)
    cp = _trained(tmp_path / "cp", OTHER_DIGEST)

    with pytest.raises(check_leakage.CheckpointNotThisRun) as refusal:
        check_leakage.run_check(run, held, cp.directory)

    assert RUN_DIGEST[:12] in str(refusal.value)
    assert OTHER_DIGEST[:12] in str(refusal.value)
    assert "not trained on this run" in str(refusal.value)


def test_a_tampered_v2_checkpoint_is_unverified(tmp_path: Path) -> None:
    run, held = _fixture(tmp_path)
    cp = _trained(tmp_path / "cp", OTHER_DIGEST)
    path = cp.directory / sft.CHECKPOINT_FILE
    document = json.loads(path.read_text(encoding="utf-8"))
    document["dataset_digest"] = RUN_DIGEST  # edited to match; the digest is left alone
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(sft.CheckpointUnverified):
        check_leakage.run_check(run, held, cp.directory)


def test_an_untrained_checkpoint_has_no_dataset(tmp_path: Path) -> None:
    run, held = _fixture(tmp_path)
    directory = tmp_path / "base"
    sft.write_baseline_checkpoint(
        directory, repo_id="m/x", revision="abc", tool_versions={"python": "3.12.0"}
    )

    with pytest.raises(check_leakage.CheckpointHasNoDataset) as refusal:
        check_leakage.run_check(run, held, directory)

    assert "no dataset to compare" in str(refusal.value)


def test_a_directory_without_provenance_is_unverified(tmp_path: Path) -> None:
    run, held = _fixture(tmp_path)
    (tmp_path / "empty").mkdir()

    with pytest.raises(sft.CheckpointUnverified):
        check_leakage.run_check(run, held, tmp_path / "empty")


def test_a_missing_checkpoint_directory_is_unverified(tmp_path: Path) -> None:
    run, held = _fixture(tmp_path)

    with pytest.raises(sft.CheckpointUnverified):
        check_leakage.run_check(run, held, tmp_path / "nowhere")


def test_digests_are_compared_exactly_not_case_folded(tmp_path: Path) -> None:
    run, held = _fixture(tmp_path)
    cp = _as_v1(_trained(tmp_path / "cp"), lambda d: d.update(dataset_digest=RUN_DIGEST.upper()))

    with pytest.raises(check_leakage.CheckpointNotThisRun):
        check_leakage.run_check(run, held, cp.directory)


def test_a_non_string_recorded_digest_is_a_mismatch(tmp_path: Path) -> None:
    run, held = _fixture(tmp_path)
    cp = _as_v1(_trained(tmp_path / "cp"), lambda d: d.update(dataset_digest=12345))

    with pytest.raises(check_leakage.CheckpointNotThisRun) as refusal:
        check_leakage.run_check(run, held, cp.directory)

    assert "12345" in str(refusal.value)


def test_a_run_whose_document_carries_no_digest_is_unreadable(tmp_path: Path) -> None:
    held = _heldout_document(tmp_path / "doc", _MEMBERS)
    run = _run(tmp_path / "run", private=(_SURVIVOR,))
    path = run / "dataset.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document.pop("digest")
    path.write_text(json.dumps(document), encoding="utf-8")
    cp = _trained(tmp_path / "cp")

    with pytest.raises(check_leakage.DatasetUnreadable):
        check_leakage.run_check(run, held, cp.directory)


def test_the_new_refusals_are_operator_fixable() -> None:
    for refusal in (
        check_leakage.CheckpointHasNoDataset,
        check_leakage.CheckpointNotThisRun,
        sft.CheckpointUnverified,
    ):
        assert refusal in check_leakage.REFUSALS
        assert issubclass(refusal, ValueError)
