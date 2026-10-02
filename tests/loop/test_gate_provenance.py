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


# --------------------------------------------------------------------------------------------
# Phase 2: the promotion record carries what it read, under schema 2, and nothing older reads.
# --------------------------------------------------------------------------------------------


def _recorded(checkpoint: sft.Checkpoint) -> dict[str, object]:
    """The three values as the checkpoint's own `provenance.json` records them — the oracle.

    Read straight off the file `sft` wrote, never through the gate's helpers, so the
    assertion compares the record against the checkpoint rather than the code against itself.
    """
    document = json.loads(
        (checkpoint.directory / sft.CHECKPOINT_FILE).read_text(encoding="utf-8")
    )
    return {
        "dataset_digest": None if checkpoint.untrained else document["dataset_digest"],
        "base_repo_id": document["base"]["repo_id"],
        "base_revision": document["base"]["revision"],
    }


@pytest.mark.parametrize("untrained_incumbent", [False, True], ids=["trained", "untrained"])
def test_a_gate_runs_record_names_what_trained_each_side(
    tmp_path: Path, untrained_incumbent: bool
) -> None:
    """AC 1 and AC 3: the record's training block equals each checkpoint's recorded values.

    Both checkpoints are built by the real writers (`sft.write_checkpoint`,
    `sft.write_baseline_checkpoint`). The untrained incumbent's `dataset_digest` is an
    explicit JSON null — the key present, the value absent — never an omitted key and never an
    invented digest. AC 5: the decision is the one the shared fixture always reached.
    """
    from loop.test_gate import _run_gate

    outcome, fixtures = _run_gate(tmp_path, untrained_incumbent=untrained_incumbent)
    document = json.loads(outcome.record.read_text(encoding="utf-8"))

    assert document["schema"] == "whetstone-promotion/2"
    assert document["candidate"] == {
        "digest": fixtures["candidate_checkpoint"].digest,
        "training": _recorded(fixtures["candidate_checkpoint"]),
    }
    assert document["incumbent"] == {
        "digest": fixtures["incumbent_checkpoint"].digest,
        "training": _recorded(fixtures["incumbent_checkpoint"]),
    }
    assert document["candidate"]["training"]["dataset_digest"] == "d" * 64
    if untrained_incumbent:
        assert "dataset_digest" in document["incumbent"]["training"]
        assert document["incumbent"]["training"]["dataset_digest"] is None

    read = gate.read_promotion_record(outcome.record)
    assert read.candidate_training == gate.TrainingProvenance(
        **_recorded(fixtures["candidate_checkpoint"])  # type: ignore[arg-type]
    )
    assert read.incumbent_training == gate.TrainingProvenance(
        **_recorded(fixtures["incumbent_checkpoint"])  # type: ignore[arg-type]
    )
    assert outcome.decision.exit is gate.Exit.PROMOTED, outcome.decision.detail


@pytest.mark.parametrize("side", ["candidate", "incumbent"])
@pytest.mark.parametrize("label", ["missing", "empty", "malformed"])
def test_an_unrecoverable_digest_exits_two_and_writes_no_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    side: str,
    label: str,
) -> None:
    """AC 2, ADVERSARIAL, end to end through `whetstone gate`: refusal, exit 2, nothing written.

    A trained checkpoint whose provenance no longer names its training set cannot appear in
    a record that claims to say what trained it. The command exits 2, names the checkpoint
    and the field, writes no record file, and generates no token: the refusal happens before
    scoring, so no engine call is made. A trained incumbent is held to the same rule — a
    null written for it would be an absence the gate invented, not one the checkpoint stated.
    """
    from loop.test_gate import _gate_fixtures
    from loop.test_gate_cli import _argv
    from whetstone import cli

    fixtures = _gate_fixtures(tmp_path)
    mutate = {
        "missing": _drop,
        "empty": lambda d: d.update(dataset_digest=""),
        "malformed": lambda d: d.update(dataset_digest="not-a-digest"),
    }[label]
    _rewrite(fixtures[f"{side}_checkpoint"], mutate)
    monkeypatch.setattr(gate, "gate_engine", fixtures["engine"])

    code = cli.main(_argv(fixtures))

    assert code == cli.USAGE_ERROR, (side, label)
    printed = capsys.readouterr().err
    assert "dataset_digest" in printed, printed
    assert str(fixtures[side]) in printed, printed
    assert not (fixtures["runs"] / gate.PROMOTIONS_DIR / "gate-001.json").exists(), (
        "WHY THIS IS A FAILURE: a refused run wrote a promotion record. A record with a blank "
        "or placeholder training digest is the half-truth this refusal exists to prevent"
    )
    assert fixtures["used_checkpoints"] == [], "the refusal must precede any scoring"


# --------------------------------------------------------------------------------------------
# Readers: a schema-1 record predates provenance and is refused loudly, never upgraded.
# --------------------------------------------------------------------------------------------


def _as_schema_one(path: Path) -> Path:
    """A record exactly as the schema-1 writer emitted it: no training blocks, schema `/1`."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["schema"] = "whetstone-promotion/1"
    raw["candidate"] = {"digest": raw["candidate"]["digest"]}
    raw["incumbent"] = {"digest": raw["incumbent"]["digest"]}
    path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _assert_refused_as_old(message: str) -> None:
    assert "whetstone-promotion/1" in message, message
    assert "predates" in message, message
    assert "never upgraded" in message, message


@pytest.mark.parametrize("training_left_in", [False, True], ids=["as-written", "spliced"])
def test_the_record_reader_refuses_a_schema_one_record(
    tmp_path: Path, training_left_in: bool
) -> None:
    """A `/1` record is refused by name even when someone splices the new fields into it."""
    from loop.test_promotion_record_n import _write_fixture_record

    path = _write_fixture_record(tmp_path)
    if training_left_in:
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["schema"] = "whetstone-promotion/1"
        path.write_text(json.dumps(raw), encoding="utf-8")
    else:
        _as_schema_one(path)

    with pytest.raises(ValueError) as refused:
        gate.read_promotion_record(path)

    assert str(path) in str(refused.value)
    _assert_refused_as_old(str(refused.value))


def test_the_morning_report_refuses_a_schema_one_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`whetstone report --record <a /1 record>` exits 2, names why, and writes nothing."""
    from loop.test_morning_cli import _tree
    from whetstone import cli

    runs, record = _tree(tmp_path)
    _as_schema_one(record)
    out = tmp_path / "home"

    code = cli.main(
        ["report", "--last-night", "--runs", str(runs), "--record", str(record), "--out", str(out)]
    )

    assert code == cli.USAGE_ERROR
    printed = capsys.readouterr().err
    assert "Traceback" not in printed, printed
    _assert_refused_as_old(printed)
    assert not out.exists()


def test_the_honest_report_refuses_a_schema_one_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The honest-number door exits 2 on a `/1` record and writes no artifact."""
    from loop.test_honest_report_door import _argv as honest_argv
    from loop.test_honest_report_door import _fixtures
    from whetstone.loop import honest_report

    fixtures = _fixtures(tmp_path)
    _as_schema_one(fixtures["record"])

    code = honest_report.main(honest_argv(fixtures))

    assert code == 2
    _assert_refused_as_old(capsys.readouterr().err)
    assert not fixtures["out"].exists()


# --------------------------------------------------------------------------------------------
# The training block is read fail-closed: nothing missing, nothing unknown, nothing defaulted.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("where", "value"),
    [
        ("candidate.sneaky", "x"),
        ("candidate.training.sneaky", "x"),
        ("incumbent.training.sneaky", "x"),
        ("candidate.training", None),
        ("candidate.training", "d" * 64),
        ("candidate.training.dataset_digest", None),
        ("candidate.training.dataset_digest", ""),
        ("candidate.training.dataset_digest", "D" * 64),
        ("incumbent.training.dataset_digest", "not-a-digest"),
        ("incumbent.training.dataset_digest", 0),
        ("candidate.training.base_repo_id", None),
        ("incumbent.training.base_revision", 7),
    ],
    ids=[
        "unknown-in-candidate",
        "unknown-in-candidate-training",
        "unknown-in-incumbent-training",
        "candidate-training-null",
        "candidate-training-not-object",
        "candidate-digest-null",
        "candidate-digest-empty",
        "candidate-digest-uppercase",
        "incumbent-digest-malformed",
        "incumbent-digest-integer",
        "candidate-repo-null",
        "incumbent-revision-integer",
    ],
)
def test_a_doctored_training_block_is_refused_by_name(
    tmp_path: Path, where: str, value: object
) -> None:
    """Every malformed shape is refused, naming the field — a candidate is never untrained."""
    from loop.test_promotion_record_n import _doctored, _write_fixture_record

    path = _doctored(_write_fixture_record(tmp_path), where, value)

    with pytest.raises(ValueError) as refused:
        gate.read_promotion_record(path)

    message = str(refused.value)
    assert str(path) in message, message
    assert where.split(".")[0] in message, message


@pytest.mark.parametrize(
    "where",
    [
        "candidate.training",
        "incumbent.training",
        "candidate.training.dataset_digest",
        "incumbent.training.dataset_digest",
        "incumbent.training.base_repo_id",
    ],
)
def test_a_missing_training_field_is_refused_never_defaulted(tmp_path: Path, where: str) -> None:
    """An omitted key is refused — the incumbent's null must be stated, not implied by absence."""
    from loop.test_promotion_record_n import _write_fixture_record

    path = _write_fixture_record(tmp_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    node = raw
    parts = where.split(".")
    for part in parts[:-1]:
        node = node[part]
    del node[parts[-1]]
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError) as refused:
        gate.read_promotion_record(path)

    assert parts[-1] in str(refused.value), refused.value


def test_the_writer_refuses_a_candidate_with_no_training_digest(tmp_path: Path) -> None:
    """A writer handed an untrained-shaped candidate writes nothing rather than a null."""
    from loop.test_promotion_record_n import _write_fixture_record

    with pytest.raises(gate.DatasetDigestUnrecorded):
        _write_fixture_record(
            tmp_path,
            candidate_training=gate.TrainingProvenance(
                dataset_digest=None, base_repo_id=REPO, base_revision="d1e3b69"
            ),
        )
    assert not (tmp_path / "record.json").exists()
