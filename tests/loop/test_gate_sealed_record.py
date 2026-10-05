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
from whetstone.loop import card, gate, sft

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


#: The one literal in `gate.py` allowed to name the file: the constant part of the refusal of a
#: trained checkpoint whose provenance records no well-formed digest (the AST holds the f-string's
#: constant segments joined, so this is the whole segment after the interpolated directory).
#: It is matched by exact equality; any other literal that names the file is a read.
_GATE_REFUSAL_LITERAL = (
    " is trained but its provenance.json records no well-formed `dataset_digest` (found "
)


@pytest.mark.parametrize("module", [gate, card], ids=["gate", "card"])
def test_the_gate_and_the_card_hold_no_read_of_provenance_json(module: Any) -> None:
    """Outside docstrings and comments, neither module names the file nor its constant.

    `gate.py` is allowed exactly one literal that mentions the file: the refusal message
    `_GATE_REFUSAL_LITERAL`, matched by exact string equality. Every other literal that
    mentions it is reported, and `card.py` has no exemption at all.
    """
    source = Path(module.__file__).read_text(encoding="utf-8")

    reads = _reads_of_the_file(_code_without_docstrings(source))

    if module is gate:
        assert all(one == _GATE_REFUSAL_LITERAL for one in reads), reads
    else:
        assert reads == [], reads


def _arguments(fixtures: dict[str, Any]) -> dict[str, Any]:
    keys = [
        *("candidate", "incumbent", "heldout", "tasks", "public", "pool", "weights"),
        *("runs", "workspace", "timeout", "recorded_on", "run_id", "engine"),
    ]
    return {key: fixtures[key] for key in keys}


def test_a_v2_digest_edited_after_sealing_is_refused_before_any_scoring(tmp_path: Path) -> None:
    # An end-to-end pin, not a discriminator: it also passes on the pre-aspect-2 code, because
    # aspect 1's `verify_checkpoint` already refuses this edit. The source-reading test and the
    # check-then-use test below are what separate the object read from the file read.
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
    assert gate._checkpoint_base(checkpoint)["repo_id"] != "someone/else"


def _mapping_of(checkpoint: sft.Checkpoint) -> dict[str, Any]:
    """The mapping `build_model_card` takes, spelled out from the claims a v2 seal carries."""
    return {
        "base": {"repo_id": checkpoint.base_repo_id, "revision": checkpoint.base_revision},
        "backend": checkpoint.backend,
    }


def test_the_card_for_a_v2_checkpoint_is_the_card_over_the_equivalent_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The writer's page is byte-identical to the pure renderer's over the verified claims."""
    from loop.test_model_card import _night
    from whetstone.loop import morning

    fixtures = _gate_fixtures(tmp_path)
    verified = sft.verify_checkpoint(fixtures["candidate"])
    night = _night()
    monkeypatch.setattr(morning, "load_named_run", lambda run: night)

    out = card.render_card(
        run=tmp_path / "night",
        checkpoint=fixtures["candidate"],
        out=tmp_path / "card" / "README.md",
    )

    expected = card.build_model_card(night=night, checkpoint=_mapping_of(verified))
    assert out.read_text(encoding="utf-8") == expected


def test_the_card_renders_from_the_object_not_from_the_file_on_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Check-then-use: a provenance edited or removed after verification cannot change the page."""
    from loop.test_model_card import _night
    from whetstone.loop import morning

    fixtures = _gate_fixtures(tmp_path)
    directory = fixtures["candidate"]
    verified = sft.verify_checkpoint(directory)
    night = _night()
    real = sft.verify_checkpoint

    def verify_then_tamper(path: Path) -> sft.Checkpoint:
        checked = real(path)
        document = json.loads((path / sft.CHECKPOINT_FILE).read_text(encoding="utf-8"))
        document["base"] = {"repo_id": "someone/else", "revision": "0000000"}
        (path / sft.CHECKPOINT_FILE).write_text(json.dumps(document), encoding="utf-8")
        return checked

    monkeypatch.setattr(morning, "load_named_run", lambda run: night)
    monkeypatch.setattr(sft, "verify_checkpoint", verify_then_tamper)

    out = card.render_card(
        run=tmp_path / "night", checkpoint=directory, out=tmp_path / "c" / "R.md"
    )

    page = out.read_text(encoding="utf-8")
    assert "someone/else" not in page
    assert f"`{verified.base_repo_id}`" in page
    assert page == card.build_model_card(night=night, checkpoint=_mapping_of(verified))


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


#: The retry case's flaky table: the candidate's first held-out task outlasts the budget (so
#: `unverified_after_retries` is non-empty and the eval reduces to `UNVERIFIED`), while the
#: incumbent's verifies on its one retry — both sides spend retries, on both pairs.
_FLAKY = "flaky"


@pytest.mark.parametrize(
    "options",
    [{}, {"candidate_solve": 6}, {_FLAKY: True}],
    ids=["promoted", "rejected", "retried"],
)
def test_sealed_never_enters_the_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, options: dict[str, Any]
) -> None:
    """DIFFERENTIAL: the same counts over a sealed pair and an unsealed pair decide identically.

    `sealed` is recorded information, never a condition of promotion. The two runs share the
    fixtures, the answers and the engine; only the checkpoints' schema differs, so every field
    of the decision — exit, denominator, solved/regressed/unverified, detail — and every count
    and retry fact must match. A gate that promoted only a sealed candidate (or rejected an
    unsealed one, or wrote a different `detail` for it) fails here; so, in the `retried` case,
    does one that skipped or shortened the retry budget for an unsealed side (e.g.
    `retry_count = 0 if not training.sealed else RETRY_COUNT`), because `retries`,
    `retries_used` and `unverified_after_retries` would then differ between the two runs.
    """
    from loop.test_gate import _MEMBERS
    from loop.test_gate_retry import _flaky

    flaky = options.pop(_FLAKY, False)
    real = gate._score_one

    def run(where: Path, v1: tuple[str, ...] = ()) -> dict[str, Any]:
        if flaky:
            # A fresh table per run: `_flaky` counts down, so each pair gets the same wobble.
            monkeypatch.setattr(gate, "_score_one", real)
            _flaky(
                monkeypatch,
                {("candidate", _MEMBERS[0]): 1 + gate.RETRY_COUNT, ("incumbent", _MEMBERS[0]): 1},
            )
        return _gated(where, v1=v1, **options)

    sealed = run(tmp_path / "sealed")
    unsealed = run(tmp_path / "unsealed", v1=("candidate", "incumbent"))

    assert sealed["candidate"]["training"]["sealed"] is True
    assert unsealed["candidate"]["training"]["sealed"] is False
    assert unsealed["incumbent"]["training"]["sealed"] is False
    assert _decided(sealed) == _decided(unsealed)
    expected = "UNVERIFIED" if flaky else ("promoted" if not options else "rejected")
    assert sealed["decision"]["exit"] == expected
    if flaky:
        assert sealed["retries_used"] == gate.RETRY_COUNT + 1, sealed["retries"]
        assert {one["side"] for one in sealed["retries"]} == {"candidate", "incumbent"}
        assert sealed["unverified_after_retries"] != []


def test_a_v1_candidates_unsealed_record_reads_back_as_written(tmp_path: Path) -> None:
    """`sealed: false` is a statement the reader accepts and returns — never refused, never flipped.

    End to end: a gate run over a hand-built v1 candidate and an untrained v2 incumbent writes
    the record; `read_promotion_record` must hand back `False` for the candidate and the
    incumbent's own `True`. A reader that refused (or coerced) a false `sealed` fails here.
    """
    document = _gated(tmp_path, v1=("candidate",), untrained_incumbent=True)
    path = tmp_path / "runs" / gate.PROMOTIONS_DIR / "gate-001.json"

    read = gate.read_promotion_record(path)

    assert read.candidate_training.sealed is False
    assert read.incumbent_training.sealed is True
    assert read.incumbent_training.sealed is document["incumbent"]["training"]["sealed"]
    assert read.incumbent_training.dataset_digest is None


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
