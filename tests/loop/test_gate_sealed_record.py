"""The gate takes its base and dataset digest from the verified `Checkpoint`, never a second read.

`sft.verify_checkpoint` returns the claims it verified. A gate that re-opened `provenance.json`
afterwards would read bytes the seal had already vouched for, and a file changed between the
check and the use would be believed. These tests pin that the gate has no such read, that a v2
checkpoint edited after sealing is refused before any scoring, and that the v1 refusals keep
their text.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from loop.test_gate import _gate_fixtures
from loop.test_gate_provenance import _rewrite
from whetstone.loop import gate, sft

_NAMES = ("provenance.json", "CHECKPOINT_FILE")


def _code_without_docstrings(source: str) -> ast.AST:
    """The module's syntax tree with every docstring removed (comments never reach the AST)."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:] or [ast.Pass()]
    return tree


def _reads_of_the_file(tree: ast.AST) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if any(name in node.value for name in _NAMES):
                found.append(node.value)
        elif isinstance(node, ast.Name | ast.Attribute):
            name = node.id if isinstance(node, ast.Name) else node.attr
            if name in _NAMES:
                found.append(name)
    return found


def test_the_gate_holds_no_read_of_provenance_json() -> None:
    """Outside docstrings and comments, `gate.py` names neither the file nor its constant.

    String literals in the refusal messages are exempt only by content: any literal that
    mentions the file is reported, so a message must say 'provenance' without the filename.
    """
    source = Path(gate.__file__).read_text(encoding="utf-8")

    reads = _reads_of_the_file(_code_without_docstrings(source))

    assert reads == [] or all("is trained but its provenance.json" in one for one in reads), reads


def _arguments(fixtures: dict[str, Any]) -> dict[str, Any]:
    keys = [
        *("candidate", "incumbent", "heldout", "tasks", "public", "pool", "weights"),
        *("runs", "workspace", "timeout", "recorded_on", "run_id", "engine"),
    ]
    return {key: fixtures[key] for key in keys}


def test_a_v2_digest_edited_after_sealing_is_refused_before_any_scoring(tmp_path: Path) -> None:
    fixtures = _gate_fixtures(tmp_path)
    path = fixtures["candidate"] / sft.CHECKPOINT_FILE
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["schema"] == sft.CHECKPOINT_SCHEMA_V2
    document["dataset_digest"] = "e" * 64
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(sft.CheckpointUnverified):
        gate.run_gate(**_arguments(fixtures))

    assert fixtures["used_checkpoints"] == [], "the engine must never have been invoked"
    assert not (fixtures["runs"] / gate.PROMOTIONS_DIR / "gate-001.json").exists()


def test_a_trained_v1_checkpoint_with_no_digest_keeps_its_refusal(tmp_path: Path) -> None:
    fixtures = _gate_fixtures(tmp_path)
    checkpoint = _rewrite(fixtures["candidate_checkpoint"], lambda d: d.update(dataset_digest=7))

    with pytest.raises(gate.DatasetDigestUnrecorded) as caught:
        gate._checkpoint_dataset_digest(checkpoint)

    message = str(caught.value)
    assert "found 7; expected a 64-digit lowercase sha256" in message, message
    assert "provenance.json records no well-formed `dataset_digest`" in message, message


def test_a_checkpoint_naming_no_base_is_unverified_not_a_key_error(tmp_path: Path) -> None:
    fixtures = _gate_fixtures(tmp_path)
    checkpoint = _rewrite(fixtures["candidate_checkpoint"], lambda d: d.pop("base"))

    with pytest.raises(sft.CheckpointUnverified, match="names no base"):
        gate._checkpoint_base(checkpoint)


def test_the_gate_answers_from_the_object_not_from_the_file_on_disk(tmp_path: Path) -> None:
    """Check-then-use: a file edited after `verify_checkpoint` cannot change what the gate reads."""
    fixtures = _gate_fixtures(tmp_path)
    checkpoint = sft.verify_checkpoint(fixtures["candidate"])
    path = fixtures["candidate"] / sft.CHECKPOINT_FILE
    document = json.loads(path.read_text(encoding="utf-8"))
    document["dataset_digest"] = "e" * 64
    document["base"] = {"repo_id": "someone/else", "revision": "0000000"}
    path.write_text(json.dumps(document), encoding="utf-8")

    assert gate._checkpoint_dataset_digest(checkpoint) == "d" * 64
    assert gate._checkpoint_base(checkpoint) == {
        "repo_id": checkpoint.base_repo_id,
        "revision": checkpoint.base_revision,
    }


# --------------------------------------------------------------------------------------------
# Phase 2: `whetstone-promotion/3` says, per side, whether the dataset link was sealed — and
# `sealed` is recorded, never decisive.
# --------------------------------------------------------------------------------------------


def _as_v1(fixtures: dict[str, Any], side: str) -> sft.Checkpoint:
    """Downgrade one side's checkpoint to a hand-built v1 document (files-only seal)."""
    return _rewrite(fixtures[f"{side}_checkpoint"], lambda document: None)


def _rekeyed(fixtures: dict[str, Any], **now: sft.Checkpoint) -> None:
    """Keep the stub engine answering per side after a side's digest changed by downgrade.

    A v1 digest reduces from the files alone, so it differs from the v2 digest the stub engine
    was keyed on. The wrapper maps the new digest back to the checkpoint the stub knows, so the
    two sides keep exactly the answers they had — the only thing that changed is the schema.
    """
    original = fixtures["engine"]
    back = {checkpoint.digest: fixtures[f"{side}_checkpoint"] for side, checkpoint in now.items()}

    def engine(weights: Any, checkpoint: sft.Checkpoint, max_tokens: int) -> Any:
        return original(weights, back.get(checkpoint.digest, checkpoint), max_tokens)

    fixtures["engine"] = engine


def _gated(tmp_path: Path, *, v1: tuple[str, ...] = (), **options: Any) -> dict[str, Any]:
    """One `run_gate` over the shared fixtures, with the named sides downgraded to v1."""
    fixtures = _gate_fixtures(tmp_path, **options)
    downgraded = {side: _as_v1(fixtures, side) for side in v1}
    _rekeyed(fixtures, **downgraded)
    for side, checkpoint in downgraded.items():
        assert checkpoint.sealed is False, side
    outcome = gate.run_gate(**_arguments(fixtures))
    document: dict[str, Any] = json.loads(outcome.record.read_text(encoding="utf-8"))
    return document


def test_a_v2_pair_writes_schema_three_sealed_on_both_sides(tmp_path: Path) -> None:
    """Criterion 1: two sealed checkpoints, a `/3` record, `sealed: true` on both sides."""
    document = _gated(tmp_path)

    assert gate.PROMOTION_SCHEMA == "whetstone-promotion/3"
    assert document["schema"] == "whetstone-promotion/3"
    assert document["candidate"]["training"]["sealed"] is True
    assert document["incumbent"]["training"]["sealed"] is True


def test_a_v1_candidate_is_recorded_unsealed_and_the_incumbent_as_it_reports(
    tmp_path: Path,
) -> None:
    """Criterion 2: the candidate's v1 link is `sealed: false`; the v2 incumbent's is its own."""
    document = _gated(tmp_path, v1=("candidate",), untrained_incumbent=True)

    assert document["candidate"]["training"]["sealed"] is False
    assert document["incumbent"]["training"]["sealed"] is True
    assert document["candidate"]["training"]["dataset_digest"] == "d" * 64


@pytest.mark.parametrize("v1", [False, True], ids=["v2-untrained", "v1-untrained"])
def test_an_untrained_incumbent_records_null_and_its_own_seal(tmp_path: Path, v1: bool) -> None:
    """Criterion 3: `dataset_digest: null` stated, and `sealed` exactly as the checkpoint says."""
    document = _gated(tmp_path, v1=("incumbent",) if v1 else (), untrained_incumbent=True)

    training = document["incumbent"]["training"]
    assert "dataset_digest" in training and training["dataset_digest"] is None
    assert training["sealed"] is (not v1)


def _decided(document: dict[str, Any]) -> dict[str, Any]:
    """Everything the decision was made of and from: the block, the counts, the retry facts."""
    keys = ("decision", "sides", "retry_count", "retries_used", "retries")
    return {
        **{key: document[key] for key in keys},
        "unverified_after_retries": document["unverified_after_retries"],
    }


@pytest.mark.parametrize(
    "options",
    [{}, {"candidate_solve": 6}],
    ids=["promoted", "rejected"],
)
def test_sealed_never_enters_the_decision(tmp_path: Path, options: dict[str, Any]) -> None:
    """DIFFERENTIAL: the same counts over a sealed pair and an unsealed pair decide identically.

    `sealed` is recorded information, never a condition of promotion. The two runs share the
    fixtures, the answers and the engine; only the checkpoints' schema differs, so every field
    of the decision — exit, denominator, solved/regressed/unverified, detail — and every count
    and retry fact must match. A gate that promoted only a sealed candidate (or rejected an
    unsealed one, or wrote a different `detail` for it) fails here.
    """
    sealed = _gated(tmp_path / "sealed", **options)
    unsealed = _gated(tmp_path / "unsealed", v1=("candidate", "incumbent"), **options)

    assert sealed["candidate"]["training"]["sealed"] is True
    assert unsealed["candidate"]["training"]["sealed"] is False
    assert unsealed["incumbent"]["training"]["sealed"] is False
    assert _decided(sealed) == _decided(unsealed)
    assert sealed["decision"]["exit"] == ("promoted" if not options else "rejected")


# --- readers: `/2` and `/1` predate the statement, and are refused, never upgraded. ----------


def _as_schema(path: Path, schema: str) -> Path:
    """A record exactly as the `/2` (no `sealed`) or `/1` (no `training`) writer emitted it."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["schema"] = schema
    for side in ("candidate", "incumbent"):
        if schema == "whetstone-promotion/1":
            raw[side] = {"digest": raw[side]["digest"]}
        else:
            del raw[side]["training"]["sealed"]
    path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


_OLD = pytest.mark.parametrize("old", ["whetstone-promotion/2", "whetstone-promotion/1"])


def _assert_refused_naming(message: str, old: str) -> None:
    assert old in message, message
    assert "never upgraded" in message, message
    assert "Traceback" not in message, message


@_OLD
def test_the_reader_refuses_an_older_record_by_its_schema(tmp_path: Path, old: str) -> None:
    from loop.test_promotion_record_n import _write_fixture_record

    path = _as_schema(_write_fixture_record(tmp_path), old)
    before = path.read_bytes()

    with pytest.raises(ValueError) as refused:
        gate.read_promotion_record(path)

    message = str(refused.value)
    assert str(path) in message, message
    _assert_refused_naming(message, old)
    if old == "whetstone-promotion/2":
        assert "sealed" in message, message
    assert path.read_bytes() == before, "a refused record is never rewritten"


@_OLD
def test_the_morning_report_refuses_an_older_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], old: str
) -> None:
    """`whetstone report` exits 2 on an old record, through `PromotionRecordRefused`."""
    from loop.test_morning_cli import _tree
    from whetstone import cli
    from whetstone.loop import morning

    runs, record = _tree(tmp_path)
    _as_schema(record, old)
    out = tmp_path / "home"

    with pytest.raises(morning.PromotionRecordRefused) as refused:
        morning._evidence(record)
    _assert_refused_naming(str(refused.value), old)

    code = cli.main(
        ["report", "--last-night", "--runs", str(runs), "--record", str(record), "--out", str(out)]
    )

    assert code == cli.USAGE_ERROR
    _assert_refused_naming(capsys.readouterr().err, old)
    assert not out.exists()


@_OLD
def test_the_honest_report_refuses_an_older_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], old: str
) -> None:
    """The honest-number door exits 2 on an old record and writes no artifact."""
    from loop.test_honest_report_door import _argv as honest_argv
    from loop.test_honest_report_door import _fixtures
    from whetstone.loop import honest_report

    fixtures = _fixtures(tmp_path)
    _as_schema(fixtures["record"], old)

    code = honest_report.main(honest_argv(fixtures))

    assert code == 2
    _assert_refused_naming(capsys.readouterr().err, old)
    assert not fixtures["out"].exists()


@pytest.mark.parametrize("side", ["candidate", "incumbent"])
@pytest.mark.parametrize(
    "value",
    ["missing", "true", 1, 0, None],
    ids=["missing", "string", "one", "zero", "null"],
)
def test_a_sealed_that_is_not_a_bool_is_refused_never_defaulted(
    tmp_path: Path, side: str, value: Any
) -> None:
    """Criterion 5: absence is not a statement, and `1`/`"true"`/`null` are not `true`."""
    from loop.test_promotion_record_n import _doctored, _write_fixture_record

    path = _write_fixture_record(tmp_path)
    if value == "missing":
        raw = json.loads(path.read_text(encoding="utf-8"))
        del raw[side]["training"]["sealed"]
        path.write_text(json.dumps(raw), encoding="utf-8")
    else:
        _doctored(path, f"{side}.training.sealed", value)

    with pytest.raises(ValueError) as refused:
        gate.read_promotion_record(path)

    message = str(refused.value)
    assert str(path) in message, message
    assert f"{side}.training.sealed" in message, message


def test_the_verifier_identity_pins_hold() -> None:
    """Criterion 9: the gate and the honest report call the one verifier, by identity."""
    from whetstone.loop import honest_report

    assert gate.verify_checkpoint is sft.verify_checkpoint
    assert honest_report.verify_checkpoint is sft.verify_checkpoint
