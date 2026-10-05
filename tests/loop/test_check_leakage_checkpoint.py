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
    if leaked:  # the fixture must really leak, or this degrades silently to the clean case
        assert not check_leakage.run_check(run, held).clean
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


# --- what it prints -------------------------------------------------------------------------

D12 = RUN_DIGEST[:12]
SEALED_LINE = (
    f"dataset link: the checkpoint's dataset_digest ({D12}) matches this run's dataset.json; "
    "the checkpoint's claims are sealed (whetstone-checkpoint/2), so an edit to that "
    "dataset_digest that did not also recompute the checkpoint's digest would have been "
    "refused (tamper-evidence, not authentication)"
)
V1_LINE = (
    f"dataset link: the checkpoint's dataset_digest ({D12}) matches this run's dataset.json; "
    "it is recorded, not sealed (whetstone-checkpoint/1) \u2014 provenance.json was outside that "
    "checkpoint's digest, so this is what the document says and not something that was checked"
)
FAR_END_LINE = (
    "the run's dataset.json is not sealed, so this compares a checkpoint claim to a document "
    "that anyone with write access to the run can edit"
)


def _link_lines(lines: tuple[str, ...]) -> list[str]:
    return [ln for ln in lines if ln.startswith("dataset link:") or ln == FAR_END_LINE]


def test_disclosure_without_a_link_is_unchanged(tmp_path: Path) -> None:
    """Fails if the link lines were emitted unconditionally."""
    run, held = _fixture(tmp_path)
    lines = check_leakage.disclosure(check_leakage.run_check(run, held))

    assert _link_lines(lines) == []
    assert not any("dataset link" in ln or "sealed" in ln for ln in lines)


def test_a_sealed_link_says_the_checkpoint_claim_is_sealed(tmp_path: Path) -> None:
    """Fails if disclosure ignores report.link, or words the sealed case as the v1 one."""
    run, held = _fixture(tmp_path)
    cp = _trained(tmp_path / "cp")
    lines = check_leakage.disclosure(check_leakage.run_check(run, held, cp.directory))

    assert SEALED_LINE in lines
    assert FAR_END_LINE in lines
    assert V1_LINE not in lines


def test_a_v1_link_says_recorded_not_sealed_and_not_checked(tmp_path: Path) -> None:
    """Fails if a v1 checkpoint is described as sealed."""
    run, held = _fixture(tmp_path)
    cp = _as_v1(_trained(tmp_path / "cp"))
    lines = check_leakage.disclosure(check_leakage.run_check(run, held, cp.directory))

    assert V1_LINE in lines
    assert FAR_END_LINE in lines
    assert SEALED_LINE not in lines


@pytest.mark.parametrize("sealed", [True, False], ids=["v2", "v1"])
def test_no_link_line_claims_verification(tmp_path: Path, sealed: bool) -> None:
    """Fails if the link is called 'verified': the files are verified, the link is not."""
    run, held = _fixture(tmp_path)
    cp = _trained(tmp_path / "cp")
    if not sealed:
        cp = _as_v1(cp)
    lines = check_leakage.disclosure(check_leakage.run_check(run, held, cp.directory))

    link = _link_lines(lines)
    assert len(link) == 2
    assert all("verified" not in ln.lower() for ln in link)


def test_a_leaked_run_keeps_its_leak_lines_and_the_link_comes_after(tmp_path: Path) -> None:
    """Fails if the link changes the verdict or lands before the leak lines."""
    run, held = _fixture(tmp_path, leaked=True)
    cp = _trained(tmp_path / "cp")
    plain = check_leakage.disclosure(check_leakage.run_check(run, held))
    report = check_leakage.run_check(run, held, cp.directory)
    lines = check_leakage.disclosure(report)

    assert report.clean is False
    assert lines[: len(plain)] == plain
    assert list(lines[len(plain) :]) == [SEALED_LINE, FAR_END_LINE]


def test_the_empty_training_set_branch_also_prints_the_link(tmp_path: Path) -> None:
    """Fails if the early-return branch skips the link lines."""
    held = _heldout_document(tmp_path / "doc", _MEMBERS)
    run = _run(tmp_path / "run", private=())
    cp = _trained(tmp_path / "cp")
    report = check_leakage.run_check(run, held, cp.directory)
    lines = check_leakage.disclosure(report)

    assert report.examples == 0
    assert lines[0].startswith("leakage: clean \u2014 the run has no training examples")
    assert lines[-2:] == (SEALED_LINE, FAR_END_LINE)


def test_with_no_ledger_the_notice_is_still_last_after_the_link(tmp_path: Path) -> None:
    """Fails if the link lines are appended after _with_notice."""
    held = _heldout_document(tmp_path / "doc", _MEMBERS)
    run = _run(tmp_path / "run", private=(_SURVIVOR,), ledger=False)
    cp = _trained(tmp_path / "cp")
    report = check_leakage.run_check(run, held, cp.directory)
    lines = check_leakage.disclosure(report)

    assert report.ledger_absent is True
    assert report.link is not None
    assert lines[-1].startswith("notice:")
    assert lines[-3:-1] == (SEALED_LINE, FAR_END_LINE)
