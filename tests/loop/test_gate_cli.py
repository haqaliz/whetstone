"""The door: `whetstone gate`, its flag surface, and the three exits at the process boundary.

`docs/ROADMAP.md:445-451` names this command as the promotion gate's exit criterion — *"`uv
run whetstone gate --candidate X --incumbent Y` returns one of the three exits"* — and the
three exits are asserted **through the CLI**, not just against the pure core: fixture
checkpoints, the fixture held-out document, the real scoring harness, and the stub engine
substituted for `gate_engine` behind the handler's function-local import (the same seam
`test_night_cli.py` uses for the night).

The exit codes are the existing four-code contract (`cli.py:64-84`), no fifth: `promoted` →
0, `rejected` → 1, `UNVERIFIED` → 3 (never 0 — a caller checking `rc == 0` must never read
an incomplete eval as a win), and refusals — a doctored checkpoint, a doctored held-out
document, a held-out set of zero — → 2, naming what was wrong.

The output carries the verdict counts over their denominators, coverage, the unverified
count over its denominator, and source A beside source B (`PREREGISTRATION.md:142-147,157`).

No model, no `mlx`, no network — the gate runs under the stub engine, exactly as every
other test in this package does.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from loop.test_gate import _BULK, _INCUMBENT_SOLVES, _MEMBERS, _PRIVATE_IDS, _gate_fixtures
from whetstone import cli
from whetstone.loop import gate, sft


def _argv(
    fixtures: dict[str, Any],
    *extra: str,
) -> list[str]:
    """The command line for `fixtures`: every flag, in the runbook's own order."""
    return [
        "gate",
        "--candidate",
        str(fixtures["candidate"]),
        "--incumbent",
        str(fixtures["incumbent"]),
        "--heldout",
        str(fixtures["heldout"]),
        "--tasks",
        str(fixtures["tasks"][0]),
        "--public",
        str(fixtures["public"]),
        "--pool",
        str(fixtures["pool"]),
        "--weights",
        str(fixtures["weights"]),
        "--runs",
        str(fixtures["runs"]),
        "--workspace",
        str(fixtures["workspace"]),
        "--timeout",
        str(fixtures["timeout"]),
        "--recorded-on",
        str(fixtures["recorded_on"]),
        "--run-id",
        str(fixtures["run_id"]),
        *extra,
    ]


def _invoke(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
    *,
    members: tuple[str, ...] = _MEMBERS,
    candidate_solve: int | None = None,
    incumbent_solve: int = 6,
    **fixture_overrides: Any,
) -> tuple[int, dict[str, Any]]:
    """Run `whetstone gate` over the shared fixture pair, with the stub engine injected.

    `gate.gate_engine` is replaced on the module — the handler's function-local import reads
    it at call time, so the real harness runs under the stub, and the three exits are
    asserted through the actual command rather than through a stand-in for it.
    """
    fixtures = _gate_fixtures(
        tmp_path,
        members=members,
        candidate_solve=candidate_solve,
        incumbent_solve=incumbent_solve,
        **fixture_overrides,
    )
    monkeypatch.setattr(gate, "gate_engine", fixtures["engine"])
    return cli.main(_argv(fixtures)), fixtures


def test_the_help_for_the_gate_door_exits_zero() -> None:
    """A `--help` advertising work the code cannot do is the failure `cli.py` exists to avoid."""
    assert cli.main(["gate", "--help"]) == cli.PASS_EXIT


def test_the_gate_parses_every_declared_flag(tmp_path: Any) -> None:
    """The flags the runbook spells exist on the parser, with the types the gate reads.

    `--tasks` is repeatable; `--timeout` is a float; the rest are paths and names, never
    strings a handler has to guess at.
    """
    fixtures = _gate_fixtures(tmp_path)
    parsed = cli.build_parser().parse_args(_argv(fixtures))

    assert parsed.candidate == fixtures["candidate"]
    assert parsed.incumbent == fixtures["incumbent"]
    assert parsed.heldout == fixtures["heldout"]
    assert parsed.tasks == [fixtures["tasks"][0]]
    assert parsed.public == fixtures["public"]
    assert parsed.pool == fixtures["pool"]
    assert parsed.weights == fixtures["weights"]
    assert parsed.runs == fixtures["runs"]
    assert parsed.workspace == fixtures["workspace"]
    assert parsed.timeout == fixtures["timeout"]
    assert parsed.recorded_on == fixtures["recorded_on"]
    assert parsed.run_id == fixtures["run_id"]


def test_an_unknown_flag_is_a_usage_error(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """argparse's own code, unchanged: "you invoked me wrongly" is not a finding about a gate."""
    fixtures = _gate_fixtures(tmp_path)
    monkeypatch.setattr(gate, "gate_engine", fixtures["engine"])
    assert cli.main([*_argv(fixtures), "--sample-more"]) == cli.USAGE_ERROR


def test_a_known_better_pair_exits_zero_and_is_promoted(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """THE roadmap's exit criterion, asserted through the CLI: known-better → exit 0.

    The candidate answers the reference patch for every held-out task, the incumbent for six,
    and the real command decides `promoted`. The output carries the verdict counts over their
    denominators, coverage, the unverified count over its denominator, and source A beside
    source B — and the record path, so the operator knows where the evidence went.
    """
    code, fixtures = _invoke(tmp_path, monkeypatch)

    assert code == cli.PASS_EXIT, capsys.readouterr().err
    printed = capsys.readouterr().out
    assert "decision: promoted" in printed, printed
    assert f"{len(_MEMBERS)} solved of {len(_MEMBERS)}" in printed, printed
    assert f"{_INCUMBENT_SOLVES} solved of {len(_MEMBERS)}" in printed, printed
    assert "0 unverified of 10" in printed, printed
    assert "coverage 10 of 10" in printed, printed
    assert "source B (held-out)" in printed and "source A (public)" in printed, printed
    assert "1 solved of 1" in printed, printed
    assert str(fixtures["run_id"]) in printed, printed

    record = json.loads(fixtures["runs"].joinpath("promotions", "gate-001.json").read_text())
    assert record["decision"]["exit"] == "promoted"


def test_a_known_worse_pair_exits_one(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fewer solves through the same command is `rejected` → exit 1: the incumbent stays put."""
    code, _fixtures = _invoke(tmp_path, monkeypatch, candidate_solve=3)

    assert code == cli.FAIL_EXIT


def test_an_untrained_candidate_exits_two_naming_the_side(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC2 at the process boundary: an untrained candidate is a usage error, exit 2.

    The candidate side of the gate is a night's trained adapter, always. A checkpoint whose
    provenance declares `untrained: true` has no adapter — its digest is the constant
    `sha256("")`, which cannot discriminate bases — so passing one as `--candidate` is
    refused by name before anything is scored, naming the side and the checkpoint path.
    """
    code, fixtures = _invoke(tmp_path, monkeypatch, untrained_candidate=True)

    assert code == cli.USAGE_ERROR, capsys.readouterr().err
    printed = capsys.readouterr().err
    assert "candidate" in printed, printed
    assert str(fixtures["candidate"]) in printed, printed


def test_a_deliberately_incomplete_eval_exits_three_and_is_not_promoted(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`docs/ROADMAP.md:438-440` at the process boundary: exit 3, never 0.

    A twelfth task in the corpus carries an over-budget source file, so no prompt can be
    rendered for it and both sides record `NO_ORACLE` — the sibling's "reached no verdict"
    set, by identity. The command must exit 3 (UNVERIFIED), NOT promote, and print the
    unverified count over its denominator.
    """
    private_ids = (*_PRIVATE_IDS, "t-12")
    members = (*_MEMBERS[:9], "t-12")
    code, fixtures = _invoke(
        tmp_path, monkeypatch, private_ids=private_ids, members=members, bulk=_BULK
    )

    assert code == cli.UNVERIFIED_EXIT, capsys.readouterr().err
    printed = capsys.readouterr().out
    assert "decision: UNVERIFIED" in printed, printed
    assert "1 unverified of 10" in printed, printed
    assert "not promoted" in printed or "no comparison was actually made" in printed, printed

    record = json.loads(fixtures["runs"].joinpath("promotions", "gate-001.json").read_text())
    assert record["decision"]["exit"] == "UNVERIFIED", (
        "WHY THIS IS A FAILURE: the incomplete eval's record claims a promotion or a "
        "rejection. No comparison was actually made, so the record must say UNVERIFIED"
    )


def test_a_doctored_checkpoint_exits_two_naming_the_checkpoint(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 2 through the CLI: a provenance digest mismatch refuses by name, never a decision.

    The candidate's adapter is tampered with after the fixtures are built. The command must
    exit 2 — a usage error, not a finding — and name the moved file on stderr. The decision
    is never reached: no record is written.
    """
    code, fixtures = _invoke(tmp_path, monkeypatch)
    assert code == cli.PASS_EXIT

    tampered = fixtures["candidate"].joinpath(sft.ADAPTER_FILE)
    tampered.write_bytes(b"tampered bytes")
    assert fixtures["runs"].joinpath("promotions", "gate-001.json").exists()

    code = cli.main(_argv(fixtures))
    assert code == cli.USAGE_ERROR, (
        "WHY THIS IS A FAILURE: a doctored checkpoint did not refuse with exit 2. The gate "
        "must never reach a decision over bytes it cannot demonstrate it read"
    )
    assert str(tampered) in capsys.readouterr().err, capsys.readouterr().err

    record = fixtures["runs"].joinpath("promotions", "gate-001.json")
    assert json.loads(record.read_text())["decision"]["exit"] == "promoted", (
        "WHY THIS IS A FAILURE: the doctored run overwrote the earlier record. A refusal "
        "never reaches the decision and never writes a record"
    )


def test_a_doctored_held_out_document_exits_two(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 2 through the CLI: a hand-edited document is refused, never scored against."""
    code, fixtures = _invoke(tmp_path, monkeypatch)
    assert code == cli.PASS_EXIT

    raw = json.loads(fixtures["heldout"].read_text(encoding="utf-8"))
    raw["membership"] = [*_MEMBERS[:-1], _PRIVATE_IDS[-1]]
    fixtures["heldout"].write_text(json.dumps(raw))

    assert cli.main(_argv(fixtures)) == cli.USAGE_ERROR
    assert "document" in capsys.readouterr().err.lower(), capsys.readouterr().err


def _record_backend(checkpoint: Any, name: str, *, reseal: bool = True) -> str:
    """Name the runtime that trained a fixture checkpoint, and return the digest it now carries.

    Under `whetstone-checkpoint/2` `backend` is a sealed claim, so recording it re-seals the
    document: the claim hashes and the digest are recomputed with `sft._claim_hashes` and
    `sft._claims_digest`. That simulates the legitimate re-seal a trainer's own writer performs
    when it records the backend — it is NOT a bypass of the seal, and
    `test_an_unresealed_backend_edit_exits_two_naming_the_claim` pins that the same edit
    without it is refused. `reseal=False` is that edit.
    """
    document = Path(checkpoint) / "provenance.json"
    raw = json.loads(document.read_text(encoding="utf-8"))
    raw["backend"] = {
        "device": "cpu",
        "device_memory_bytes": 16637317120,
        "library": "torch",
        "name": name,
        "version": "2.14.0+cpu",
    }
    if reseal:
        raw["claims"] = sft._claim_hashes(
            {key: value for key, value in raw.items() if key not in sft._UNSEALED_KEYS}
        )
        raw["digest"] = sft._claims_digest(raw["claims"])
    document.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(raw["digest"])


def _torch_backed(fixtures: dict[str, Any]) -> Any:
    """Record Torch on both fixture checkpoints, and the stub engine keyed on the new digests.

    The stub chooses its answers by checkpoint digest, and the re-seal in `_record_backend`
    moved both digests, so each new digest is mapped back to the checkpoint the stub was built
    over. The mapping is total: a digest the gate did not get from a re-sealed fixture raises.
    """
    resealed = {
        _record_backend(fixtures["candidate"], "torch-cpu"): fixtures["candidate_checkpoint"],
        _record_backend(fixtures["incumbent"], "torch-cpu"): fixtures["incumbent_checkpoint"],
    }

    def engine(weights: Any, checkpoint: sft.Checkpoint, max_tokens: int) -> Any:
        return fixtures["engine"](weights, resealed[checkpoint.digest], max_tokens)

    return engine


def test_an_unresealed_backend_edit_exits_two_naming_the_claim(
    tmp_path: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """The edit `_record_backend` re-seals, left unsealed, is a doctored checkpoint: exit 2.

    The counterpart that keeps the helper's re-seal honest. Under the files-only seal this very
    edit verified, which is how a checkpoint's recorded runtime could be rewritten without a
    trace; now the gate refuses it and names the moved claim.
    """
    fixtures = _gate_fixtures(tmp_path, incumbent_solve=6)
    _record_backend(fixtures["candidate"], "torch-cpu", reseal=False)

    assert cli.main(_argv(fixtures)) == cli.USAGE_ERROR, (
        "WHY THIS IS A FAILURE: a backend rewritten after the checkpoint was sealed did not "
        "refuse with exit 2, so the runtime a gate dispatches on can be edited by hand"
    )
    assert "'backend'" in capsys.readouterr().err


def test_the_door_dispatches_the_engine_on_the_checkpoints_own_recorded_backend(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The door must reach `gate_engine_for`, never hand `run_gate` an engine chosen here.

    `test_torch_engine.py` proves the dispatch itself; this proves the command uses it, which
    is a different claim and the one that was false. A door that passes `engine=gate_engine`
    makes `run_gate`'s `if engine is None` branch unreachable, so a Torch-trained candidate is
    loaded through MLX's loader — and that does not raise, it emits weights, so the gate would
    publish a promotion decision about a model nobody trained (#55).

    The stub is injected on `torch_runtime` rather than on `gate`, deliberately: injecting it
    through `gate.gate_engine`, as every other test here does, is exactly what hid the defect.
    """
    from whetstone.loop import torch_runtime

    fixtures = _gate_fixtures(tmp_path, incumbent_solve=6)
    engine = _torch_backed(fixtures)

    def _mlx_engine_refused(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError(
            "the MLX engine was reached for a checkpoint whose provenance records Torch"
        )

    monkeypatch.setattr(gate, "gate_engine", _mlx_engine_refused)
    monkeypatch.setattr(torch_runtime, "torch_gate_engine", engine)

    assert cli.main(_argv(fixtures)) == cli.PASS_EXIT, (
        "WHY THIS IS A FAILURE: the door did not dispatch on the candidate's own backend. "
        "`gate_engine_for` is unreachable from the command, so the runtime that scores a "
        "candidate is whichever one the CLI names rather than the one that trained it"
    )


def test_the_promotion_record_names_the_runtime_that_actually_ran(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The record must not name a library the comparison never loaded (#61).

    `ledger.tool_versions()` records `mlx-lm` unconditionally unless it is given a backend —
    the #33 inaccuracy — and the gate called it bare, so a Torch comparison on a host without
    MLX wrote `"mlx-lm": "0.31.3"` into `runs/promotions/<id>.json`. That document is evidence:
    it is what says which runtime a gated comparison was measured under.

    The gate already knows. It selects its engine from the candidate's own recorded backend
    (`gate_engine_for`, #56), so the same record is what the versions block should follow —
    and then the two cannot disagree.
    """
    from whetstone.loop import torch_runtime

    fixtures = _gate_fixtures(tmp_path, incumbent_solve=6)
    monkeypatch.setattr(torch_runtime, "torch_gate_engine", _torch_backed(fixtures))

    assert cli.main(_argv(fixtures)) == cli.PASS_EXIT

    record = json.loads(
        fixtures["runs"].joinpath("promotions", "gate-001.json").read_text(encoding="utf-8")
    )
    versions = record["tool_versions"]

    assert "mlx-lm" not in versions, (
        "WHY THIS IS A FAILURE: the promotion record names `mlx-lm` for a comparison whose "
        f"candidate records Torch. The record says what the comparison ran under: {versions}"
    )
    assert versions.get("torch") == "2.14.0+cpu", (
        f"the record does not name the runtime the candidate was trained under: {versions}"
    )
