"""The § 3 baseline measurement's door — first the seam, then the measurement.

This file is the aspect's test surface (`docs/planning/baseline-measurement/measurement-door/`),
written first. Task A pins the one new machine seam — `baseline_engine` — in the gate's own
posture: the factory exists, is callable, is smoke-tested only (never invoked by a test —
`mlx` is an optional extra and every test injects a stub engine), and its module holds no
`mlx`/`mlx_lm` import at module scope, on the loop package's rule.

Task B pins the measurement core — `measure()` — the gate's order of operations for one
side: the fixture shapes are the gate's own (a real untrained checkpoint via the aspect-1
writer, a loader-valid held-out document with the digest sealed through
`heldout.document_digest_of`, the harness's weights and corpus, a stub engine keyed on the
checkpoint), and flakiness is simulated at exactly the gate's one seam — `gate._score_one`,
the per-task scoring call — with the real path in front of and behind it.

Later tasks (C and D) add the measured-once guard and the module door to this same file.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import re
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fixtures.repos import make_patch
from fixtures.repos.mined import build_mined_task

from loop.harness import (
    RECORDED_ON,
    TIMEOUT,
    Answers,
    corpus,
    pool,
    posed,
    solving_answers,
)
from loop.harness import weights as harness_weights
from whetstone.bakeoff import report as bakeoff_report
from whetstone.bakeoff.run import TranscriptNotPrivate
from whetstone.bakeoff.scoring import Outcome, Rollout
from whetstone.bakeoff.stratum import OutUnderLocalCorpus
from whetstone.bakeoff.weights import load_weights
from whetstone.loop import baseline, gate, heldout, night, sft
from whetstone.verify.verdict import Status

#: The guarded module under test, walked over its own bytes rather than this process's
#: `sys.modules` — the loop package's rule is about what executing the module loads.
MODULE = Path(__file__).resolve().parents[2] / "src" / "whetstone" / "loop" / "baseline.py"

#: The import roots that may appear only inside function bodies in `baseline.py`.
FORBIDDEN_IMPORT_ROOTS = frozenset({"mlx", "mlx_lm"})

# --------------------------------------------------------------------------------------------
# Task B fixtures: the gate's own shapes, restated — real untrained checkpoint, loader-valid
# held-out document, harness weights/corpus, stub engine keyed on the checkpoint digest.
# --------------------------------------------------------------------------------------------

#: The one base the fixture checkpoint names. The weights root holds exactly this candidate.
_BASE = "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit"

#: The loaded private corpus the fixture document is defined over: eleven tasks, ten held
#: out by the document, one ("t-11") left outside the membership — the gate's own shape.
_PRIVATE_IDS = tuple(f"t-{i:02d}" for i in range(1, 12))

#: The members the fixture document holds out: every id but the survivor.
_MEMBERS = _PRIVATE_IDS[:-1]

#: The first held-out member — the task every flakiness table in this file picks on.
_FIRST = _MEMBERS[0]

#: The held test file, rewritten so both declared node ids exist and assert nothing — the
#: weak-PASS / strict-FAIL shape `N` counts (`test_scoring.py`'s fixture, restated).
NEUTERED_TESTS = """\
def test_adding_zero_is_the_identity():
    assert True


def test_add_is_addition():
    assert True
"""


def _heldout_document(
    root: Path, members: Sequence[str], *, corpus_ids: Sequence[str] = _PRIVATE_IDS, **fields: Any
) -> Path:
    """A loader-valid `whetstone-heldout/1` document over `corpus_ids` with membership `members`.

    The gate's own helper, restated: the loader validates a document against itself, and only
    the run-side resolution matches the membership against the loaded corpus — so a test can
    plant a membership the rule would never select and still reach the check it is about. The
    digest is sealed through aspect 1's own function after `fields` are applied.
    """
    ordered = sorted(corpus_ids)
    raw: dict[str, Any] = {
        "schema": heldout.HELDOUT_SCHEMA,
        "rule_digest": heldout.rule_digest(),
        "rule": {
            "bands": heldout.HELDOUT_BANDS,
            "min_heldout": heldout.MIN_HELDOUT,
            "min_per_band": heldout.MIN_PER_BAND,
            "split_seed": heldout.SPLIT_SEED,
        },
        "corpus": list(corpus_ids),
        "difficulty": {
            task_id: {
                "files": 1,
                "hunks": 1,
                "added": 1,
                "deleted": 1,
                "f2p": 1,
                "pins": 0,
                "blobs": 1,
            }
            for task_id in corpus_ids
        },
        "bands": {
            task_id: ordered.index(task_id) % heldout.HELDOUT_BANDS for task_id in ordered
        },
        "refusals": {},
        "membership": list(members),
    }
    raw.update(fields)
    raw["document_digest"] = heldout.document_digest_of(raw)
    root.mkdir(parents=True, exist_ok=True)
    out = root / "source-b.json"
    out.write_text(json.dumps(raw))
    return out


def _private_corpus(
    root: Path, ids: Sequence[str], *, subjects: Mapping[str, str] | None = None
) -> tuple[Path, list[Any]]:
    """One donor per id with manifests collected into a directory — the `harness.corpus` shape.

    `subjects` lets a test plant a canary in one task's problem statement — the field the
    prompt renders verbatim, which is exactly the content the evidence must never carry.
    """
    directory = root / "private"
    directory.mkdir(parents=True)
    built: list[Any] = []
    for task_id in ids:
        fixture = build_mined_task(
            root / f"donor-{task_id}",
            task_id=task_id,
            subject=(subjects or {}).get(task_id, f"Fix addition ({task_id})"),
        )
        shutil.copy(root / f"donor-{task_id}" / f"{task_id}.json", directory / f"{task_id}.json")
        built.append(fixture)
    return directory, built


def _fixtures(
    tmp_path: Path,
    *,
    answers: Mapping[str, str] | None = None,
    runs: Path | None = None,
    run_id: str = "baseline-001",
    repo_id: str = _BASE,
    revision: str | None = None,
    canary: str | None = None,
) -> dict[str, Any]:
    """Everything one `measure()` invocation needs on disk — checkpoint, document, corpus,
    weights — plus the stub engine keyed on the checkpoint's digest.

    The checkpoint is the aspect-1 writer's real artefact (`write_baseline_checkpoint`), so
    `verify_checkpoint` re-hashes the bytes the measurement names; the engine asserts it is
    handed exactly that checkpoint's digest.
    """
    subjects = None
    if canary is not None:
        subjects = {_PRIVATE_IDS[0]: f"Fix addition ({_PRIVATE_IDS[0]}) {canary}"}
    private, private_built = _private_corpus(tmp_path / "corpus", _PRIVATE_IDS, subjects=subjects)
    public, public_built = corpus(tmp_path / "corpus", "public", ("pallets__flask-4045",))
    members_set = set(_MEMBERS)
    poseable = [fixture for fixture in private_built if fixture.task.task_id in members_set]

    if answers is None:
        answers = solving_answers(*poseable, *public_built)

    doc = _heldout_document(tmp_path / "doc", _MEMBERS)
    weights_root = harness_weights(tmp_path / "weights", _BASE)
    base = load_weights(weights_root)[0]
    checkpoint = sft.write_baseline_checkpoint(
        tmp_path / "checkpoint",
        repo_id=repo_id,
        revision=base.revision if revision is None else revision,
        tool_versions={"python": "3.12.0"},
    )

    used_checkpoints: list[str] = []
    stub = Answers(answers)

    def engine(weights: Any, checkpoint_: sft.Checkpoint, max_tokens: int) -> Answers:
        assert max_tokens >= 1, max_tokens
        assert weights.repo_id == _BASE, weights.repo_id
        used_checkpoints.append(checkpoint_.digest)
        assert checkpoint_.digest == checkpoint.digest, checkpoint_.digest
        return stub

    return {
        "checkpoint": checkpoint.directory,
        "heldout": doc,
        "tasks": (private,),
        "public": public,
        "pool": pool(tmp_path / "pool" / "pool.json"),
        "weights": weights_root,
        "runs": tmp_path / "runs" if runs is None else runs,
        "workspace": tmp_path / "work",
        "timeout": TIMEOUT,
        "recorded_on": RECORDED_ON,
        "run_id": run_id,
        "out": tmp_path / "out" / "baseline.json",
        "engine": engine,
        "stub": stub,
        "used_checkpoints": used_checkpoints,
        "private_built": private_built,
        "public_built": public_built,
        "checkpoint_obj": checkpoint,
        "doc": doc,
    }


def _measure(fixtures: dict[str, Any], **overrides: Any) -> baseline.BaselineMeasurement:
    """One `measure()` call over a prebuilt fixtures dict — see `_fixtures`.

    The split from `_run_measure` exists for the measured-once tests: planting a first
    artifact at `--out` requires the run's digests before the call, and asserting "nothing
    was scored" requires inspecting the very stub the call is about to use.
    """
    arguments: dict[str, Any] = {
        "checkpoint": fixtures["checkpoint"],
        "heldout": fixtures["heldout"],
        "tasks": fixtures["tasks"],
        "public": fixtures["public"],
        "runs": fixtures["runs"],
        "workspace": fixtures["workspace"],
        "timeout": fixtures["timeout"],
        "recorded_on": fixtures["recorded_on"],
        "run_id": fixtures["run_id"],
        "pool": fixtures["pool"],
        "weights": fixtures["weights"],
        "out": fixtures["out"],
        "engine": fixtures["engine"],
    }
    arguments.update(overrides)
    return baseline.measure(**arguments)


def _run_measure(
    tmp_path: Path,
    *,
    answers: Mapping[str, str] | None = None,
    runs: Path | None = None,
    run_id: str = "baseline-001",
    repo_id: str = _BASE,
    revision: str | None = None,
    canary: str | None = None,
    **overrides: Any,
) -> tuple[baseline.BaselineMeasurement, dict[str, Any]]:
    """One full measurement over the shared fixtures — see `_fixtures`."""
    fixtures = _fixtures(
        tmp_path,
        answers=answers,
        runs=runs,
        run_id=run_id,
        repo_id=repo_id,
        revision=revision,
        canary=canary,
    )
    return _measure(fixtures, **overrides), fixtures


def _heldout_records(measurement: baseline.BaselineMeasurement) -> list[Rollout]:
    """The measurement's held-out rollouts, partitioned the way the tally partitions them."""
    members = set(_MEMBERS)
    return [record for record in measurement.rollouts if record.task_id in members]


def _flaky(
    monkeypatch: pytest.MonkeyPatch, failures: Mapping[tuple[str, str], int]
) -> dict[tuple[str, str], int]:
    """Make the first `n` scorings of `(side, task_id)` come back with no verdict.

    The gate's own seam, mirrored exactly (`test_gate_retry._flaky`): the real `_score_one`
    still runs — the prompt is rendered, the base is asked, the patch is extracted and
    verified — and only the *outcome* is overwritten, with the shape a timed-out sandbox
    produces (`UNVERIFIED` on both verifiers). The first attempt really happened, so the
    recorder really holds its completion, and the retry really has identical bytes to replay.
    """
    real = gate._score_one
    remaining = dict(failures)
    attempts: dict[tuple[str, str], int] = {}

    def patched(**kwargs: Any) -> Rollout:
        record = real(**kwargs)
        key = (str(kwargs["label"]).split(":")[0], str(kwargs["task"].task_id))
        attempts[key] = attempts.get(key, 0) + 1
        if remaining.get(key, 0) > 0:
            remaining[key] -= 1
            return replace(
                record,
                outcome=Outcome.UNVERIFIED,
                strict=Status.UNVERIFIED,
                weak=Status.UNVERIFIED,
                detail="simulated flaky sandbox",
            )
        return record

    monkeypatch.setattr(gate, "_score_one", patched)
    return attempts


def _counted(monkeypatch: pytest.MonkeyPatch) -> dict[tuple[str, str], int]:
    """Count scorings per (side, task id) without touching a single outcome.

    The companion to `_flaky` for the tests that are about what the measurement declines to
    do: a table that tampered with the outcome could not prove a task was left alone, because
    the tampering would be the thing that changed it.
    """
    real = gate._score_one
    attempts: dict[tuple[str, str], int] = {}

    def patched(**kwargs: Any) -> Rollout:
        key = (str(kwargs["label"]).split(":")[0], str(kwargs["task"].task_id))
        attempts[key] = attempts.get(key, 0) + 1
        return real(**kwargs)

    monkeypatch.setattr(gate, "_score_one", patched)
    return attempts


def _evidence(measurement: baseline.BaselineMeasurement) -> dict[str, Any]:
    """The evidence document, read back off disk."""
    return json.loads(measurement.evidence_path.read_text(encoding="utf-8"))


def _stripped_of_durations(document: dict[str, Any]) -> str:
    """The evidence document as bytes, with the three wall-clock fields removed.

    Durations are a property of the machine, not of the measurement — the scoring record
    itself keeps them outside the verdict for exactly this reason (`scoring.py:148-151`) —
    so the determinism claim is over everything the measurement means, with the clocks
    normalized out.
    """
    for rollout in document["rollouts"]:
        for key in ("generation_seconds", "strict_seconds", "weak_seconds"):
            rollout.pop(key, None)
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


# --------------------------------------------------------------------------------------------
# Task B: the measurement core — scoring, retry, counts, N, evidence, refusals.
# --------------------------------------------------------------------------------------------


def test_measure_scores_heldout_and_source_a(tmp_path: Path) -> None:
    """Both sets are scored exactly once each, outcomes land per task, and the tallies equal
    `report.tally`'s over the same rollouts (asserted by recomputing).

    The stub engine counts prompts: ten held-out members plus the one public instance, each
    posed exactly once, each landing the reference patch's solve through the real scoring
    harness — prompt render, extraction, git apply, STRICT.
    """
    measurement, fixtures = _run_measure(tmp_path)

    assert len(fixtures["stub"].asked) == len(_MEMBERS) + 1, (
        f"WHY THIS IS A FAILURE: the stub was asked {len(fixtures['stub'].asked)} times, "
        f"not {len(_MEMBERS) + 1} — a set was scored more than once, or not at all"
    )
    assert set(fixtures["used_checkpoints"]) == {fixtures["checkpoint_obj"].digest}, (
        "WHY THIS IS A FAILURE: the engine seam was not given exactly one call with the "
        "verified checkpoint, so the scoring did not run under the re-hashed bytes"
    )

    assert len(measurement.rollouts) == len(_MEMBERS) + 1
    by_task = {record.task_id: record for record in measurement.rollouts}
    assert set(by_task) == {*_MEMBERS, "pallets__flask-4045"}
    assert all(record.outcome is Outcome.SOLVED for record in measurement.rollouts), (
        "WHY THIS IS A FAILURE: a task answered with its reference patch did not land as "
        "SOLVED through the real harness"
    )

    heldout_records = _heldout_records(measurement)
    public_records = [
        record for record in measurement.rollouts if record.task_id not in set(_MEMBERS)
    ]
    assert measurement.heldout_tally == bakeoff_report.tally("baseline", heldout_records)
    assert measurement.public_tally == bakeoff_report.tally("baseline", public_records)
    assert measurement.heldout_tally.denominator == len(_MEMBERS)
    assert measurement.heldout_tally.solved == len(_MEMBERS)
    assert measurement.public_tally.denominator == 1 and measurement.public_tally.solved == 1

    assert measurement.checkpoint_digest == fixtures["checkpoint_obj"].digest
    assert measurement.heldout_digest == heldout.document_digest_of(
        json.loads(fixtures["doc"].read_text(encoding="utf-8"))
    )
    assert measurement.evidence_path == (
        fixtures["runs"] / str(fixtures["run_id"]) / "evidence.json"
    )
    assert measurement.recorded_on == RECORDED_ON


def test_measure_counts_n_via_tally_by_identity(tmp_path: Path) -> None:
    """The headline baseline `N` is `weaker_wins` over the held-out rollouts, by identity.

    One held-out task answers with a patch that rewrites the operator-held test: the naive
    exit-status check waves it through (WEAK == PASS) and the reward refuses it before
    anything ran (STRICT == FAIL, `OUT_OF_SCOPE`) — the exact disagreement `N` counts.
    """
    probes = _fixtures(tmp_path / "probe")
    poseable = [f for f in probes["private_built"] if f.task.task_id in set(_MEMBERS)]
    first = poseable[0]
    assert first.task.task_id == _FIRST
    neutered = {
        posed(first.task): make_patch(
            first.donor, {"tests/test_addition.py": NEUTERED_TESTS}, at=first.parent
        )
    }
    solving = solving_answers(*poseable[1:], *probes["public_built"])
    measurement, _ = _run_measure(tmp_path, answers={**neutered, **solving})

    heldout_records = _heldout_records(measurement)
    recomputed = bakeoff_report.tally("baseline", heldout_records)
    assert measurement.heldout_tally == recomputed
    assert measurement.heldout_tally.weaker_wins == 1, (
        "WHY THIS IS A FAILURE: one rollout had WEAK == PASS and STRICT == FAIL and N did "
        "not count it. That is the definition at PREREGISTRATION.md:99"
    )
    assert measurement.public_tally.weaker_wins == 0
    by_task = {record.task_id: record for record in heldout_records}
    assert by_task[_FIRST].outcome is Outcome.OUT_OF_SCOPE
    assert by_task[_FIRST].strict is Status.FAIL and by_task[_FIRST].weak is Status.PASS


def test_retry_fires_only_on_no_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC2: the retry discipline fires only on no-verdict, with `R` by identity.

    One held-out task's first score comes back `UNVERIFIED` (the gate's one flakiness seam:
    the real scoring ran, only the outcome was overwritten), so the retry replays the
    recorded bytes of the first attempt and the task verifies on its second scoring — while
    a FAIL task (answered with prose → `NO_DIFF`, a real verdict) is never re-asked.
    """
    lost = _MEMBERS[-1]
    probes = _fixtures(tmp_path / "probe")
    poseable = [f for f in probes["private_built"] if f.task.task_id in set(_MEMBERS)]
    solving = solving_answers(
        *[f for f in poseable if f.task.task_id != lost], *probes["public_built"]
    )

    attempts = _flaky(monkeypatch, {("baseline", _FIRST): 1})

    measurement, _ = _run_measure(tmp_path, answers=solving)

    assert attempts[("baseline", _FIRST)] == 2, (
        f"WHY THIS IS A FAILURE: the flaky task was scored "
        f"{attempts[('baseline', _FIRST)]} times. It reached no verdict once, so the "
        "measurement must have retried it exactly once"
    )
    assert attempts[("baseline", lost)] == 1, (
        f"WHY THIS IS A FAILURE: the FAIL task was scored {attempts[('baseline', lost)]} "
        "times. NO_DIFF is a verdict — the candidate was scored and failed — and a verdict "
        "is never retried"
    )

    assert len(measurement.retries) == 1, measurement.retries
    retry = measurement.retries[0]
    assert retry.task_id == _FIRST
    assert retry.before is Outcome.UNVERIFIED
    assert retry.after is Outcome.SOLVED
    assert retry.retries_used == 1
    assert retry.completion_sha256 != "" and retry.prompt_sha256 != ""

    heldout_records = _heldout_records(measurement)
    by_task = {record.task_id: record for record in heldout_records}
    assert by_task[_FIRST].outcome is Outcome.SOLVED, (
        "WHY THIS IS A FAILURE: a task that reached a verdict on retry is still unverified. "
        "A task that verifies on retry is verified (docs/ROADMAP.md:431-433)"
    )
    assert by_task[lost].outcome is Outcome.NO_DIFF

    assert measurement.heldout_tally.unverified == 0
    assert baseline.RETRY_COUNT == gate.RETRY_COUNT
    assert _evidence(measurement)["retry_count"] == gate.RETRY_COUNT


def test_unverified_tasks_stay_in_the_denominator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Coverage < denominator is published, never dropped: a task still unverified after `R`
    stays in the denominator, counted as unverified.

    The flaky table outlasts the budget — the first attempt and every retry come back
    without a verdict — so the task is scored `1 + R` times and remains unverified; the
    tally keeps it in `denominator` and reports it under `unverified`, exactly as the
    sibling's coverage rule demands.
    """
    budget = 1 + gate.RETRY_COUNT
    attempts = _flaky(monkeypatch, {("baseline", _FIRST): budget})

    measurement, _ = _run_measure(tmp_path)

    assert attempts[("baseline", _FIRST)] == budget, (
        f"WHY THIS IS A FAILURE: the task was scored {attempts[('baseline', _FIRST)]} times "
        f"against a budget of one attempt plus R={gate.RETRY_COUNT} retries"
    )
    tally = measurement.heldout_tally
    assert tally.denominator == len(_MEMBERS), (
        "WHY THIS IS A FAILURE: an unverified task left the denominator. Unverified tasks "
        "lower coverage; they never vanish from the set they were scored on"
    )
    assert tally.unverified == 1
    assert tally.covered == len(_MEMBERS) - 1
    assert tally.covered + tally.unverified == tally.denominator
    assert tally.solved == len(_MEMBERS) - 1 and tally.failed == 0

    retry = measurement.retries[0]
    assert retry.retries_used == gate.RETRY_COUNT
    assert retry.after is Outcome.UNVERIFIED

    document = _evidence(measurement)
    counts = document["counts"]["heldout"]
    assert counts["denominator"] == len(_MEMBERS)
    assert counts["unverified"] == 1 and counts["covered"] == len(_MEMBERS) - 1


def test_no_base_weights_refusal(tmp_path: Path) -> None:
    """A checkpoint naming a base the weights root lacks is refused, never guessed at.

    The `_base_for` posture imported by identity: the measurement scores the untrained base
    a checkpoint names, and a base the weights provenance cannot identify is a measurement
    nobody can score.
    """
    with pytest.raises(gate.NoBaseWeights) as refused:
        _run_measure(
            tmp_path,
            repo_id="mlx-community/Some-Other-Base",
            revision="abc123",
        )
    assert "Some-Other-Base" in str(refused.value), refused.value
    assert baseline.NoBaseWeights is gate.NoBaseWeights


def test_runs_root_refused_under_reports(tmp_path: Path) -> None:
    """The `_refuse_published_root` discipline, by identity: `reports/` is never a run home."""
    assert baseline._refuse_published_root is night._refuse_published_root, (
        "WHY THIS IS A FAILURE: the measurement does not consume the night's refusal by "
        "identity. A second copy of 'where private evidence may live' is a second answer "
        "that can drift"
    )
    with pytest.raises(TranscriptNotPrivate):
        _run_measure(tmp_path, runs=tmp_path / "reports" / "nightly")


def test_evidence_document_carries_hashes_only(tmp_path: Path) -> None:
    """AC 6: the locality canary planted in a task's problem statement cannot reach the
    evidence document, and the runs home is asserted gitignored against git itself.

    The canary is rendered verbatim into the prompt — the prompt is posed, hashed, and never
    stored; the evidence carries `prompt_sha256` and `completion_sha256` only.
    """
    import subprocess

    canary = "CANARY-7f3b9c2d4e5a"
    measurement, _ = _run_measure(tmp_path, canary=canary)

    document = _evidence(measurement)
    payload = json.dumps(document)
    assert canary not in payload, (
        "WHY THIS IS A FAILURE: the canary planted in a task's problem statement reached "
        "the evidence document. The document is hashes and verdicts only — never prompts, "
        "never completions, never patch text"
    )
    assert all(
        rollout["completion_sha256"] == "" or len(rollout["completion_sha256"]) == 64
        for rollout in document["rollouts"]
    )
    assert all(
        rollout["prompt_sha256"] == "" or len(rollout["prompt_sha256"]) == 64
        for rollout in document["rollouts"]
    )

    repo_root = Path(__file__).resolve().parents[2]
    candidate = f"runs/{measurement.run_id}/evidence.json"
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", candidate],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"},
    )
    assert result.returncode == 0, (
        f"WHY THIS IS A FAILURE: git would track {candidate!r}. The evidence is local "
        "evidence — hashes and verdict counts over the held-out membership — and the whole "
        "locality guarantee is one .gitignore edit wide"
    )


def test_determinism(tmp_path: Path) -> None:
    """Two measurements over identical inputs and a stub engine produce byte-identical
    evidence documents (different `--run-id`).

    The run id names the evidence's directory, never its content — two renders of the same
    documented command must produce the same document, or the evidence is not evidence. The
    three wall-clock fields are normalized out: durations are a property of the machine, not
    of the measurement, and the scoring record keeps them outside the verdict for exactly
    this reason.
    """
    first, _ = _run_measure(tmp_path / "one", run_id="baseline-001")
    second, _ = _run_measure(tmp_path / "two", run_id="baseline-002")

    assert first.evidence_path.parent.name == "baseline-001"
    assert second.evidence_path.parent.name == "baseline-002"

    first_doc = _evidence(first)
    second_doc = _evidence(second)
    assert "run_id" not in first_doc, (
        "WHY THIS IS A FAILURE: the evidence document carries the run id as content. The "
        "run identity is the directory name (runs/<run-id>/), so a document that also "
        "carried it could not be byte-identical across two runs that differ only in that id"
    )
    assert _stripped_of_durations(first_doc) == _stripped_of_durations(second_doc), (
        "WHY THIS IS A FAILURE: two measurements over identical inputs recorded different "
        "evidence. The evidence is the accumulated verified-improvement trail, and a trail "
        "that differs between two renders of the same command is not evidence"
    )


def test_measure_composes_the_gate_and_report_by_identity() -> None:
    """The identity rule, asserted member by member: imported, never copied.

    Each of these is a place the measurement could have re-decided a definition it had no
    business re-deciding: how a side is scored and retried (the gate's private pieces), what
    the held-out document is, where private evidence may live, what the counts are
    (`report.tally`, the single place each published figure is defined), and what a
    checkpoint is (`verify_checkpoint`).
    """
    from whetstone.bakeoff.run import HF_HUB_OFFLINE
    from whetstone.bakeoff.run import load_task_roots as run_load_task_roots
    from whetstone.loop import ledger as run_ledger
    from whetstone.tasks.manifest import load_tasks as manifest_load_tasks

    assert baseline._score_side is gate._score_side
    assert baseline._retry_side is gate._retry_side
    assert baseline._heldout_tasks is gate._heldout_tasks
    assert baseline._base_for is gate._base_for
    assert baseline._CompletionRecorder is gate._CompletionRecorder
    assert baseline.RETRY_COUNT == gate.RETRY_COUNT
    assert baseline.NoBaseWeights is gate.NoBaseWeights
    assert baseline.read_document is heldout.read_document
    assert baseline.document_digest_of is heldout.document_digest_of
    assert baseline.refuse_committed_out is heldout.refuse_committed_out
    assert baseline.tally is bakeoff_report.tally
    assert baseline.verify_checkpoint is sft.verify_checkpoint
    assert baseline.load_task_roots is run_load_task_roots
    assert baseline.load_tasks is manifest_load_tasks
    assert baseline.HF_HUB_OFFLINE == HF_HUB_OFFLINE
    assert baseline.tool_versions is run_ledger.tool_versions


# --------------------------------------------------------------------------------------------
# Task C: the measured-once guard — the series identity, its fail-closed reader, and the
# write-side refusal wired into `measure()` (spec AC 5).
# --------------------------------------------------------------------------------------------


def _artifact(out: Path, **fields: Any) -> Path:
    """A minimal `whetstone-baseline/1` artifact at `out/report.json`, `fields` applied.

    The aspect-3 writer does not exist yet — this is the shape it is committed to, planted
    by hand: the schema, the base identity and the held-out document digest that fix the
    series, and the date the refusal's message names.
    """
    out.mkdir(parents=True, exist_ok=True)
    document: dict[str, Any] = {
        "schema": baseline.BASELINE_SCHEMA,
        "recorded_on": "2026-08-26",
        "base": {"repo_id": _BASE, "revision": "rev-one"},
        "checkpoint": {"digest": "c" * 64},
        "heldout": {"document_digest": "h" * 64},
    }
    document.update(fields)
    artifact = out / "report.json"
    artifact.write_text(json.dumps(document))
    return artifact


def test_a_same_series_artifact_is_refused_by_name(tmp_path: Path) -> None:
    """AC 5: a same-series artifact already at `--out` is refused by name, and nothing is scored.

    The artifact is the first measurement — the date it records is the date the refusal
    names — and the current run would be a second measurement of the same series: the same
    base and the same held-out document, producing the same measurement by
    construction. The refusal fires before a token is generated: the stub is never asked and
    the engine seam is never constructed.
    """
    fixtures = _fixtures(tmp_path)
    provenance = json.loads(
        (fixtures["checkpoint"] / "provenance.json").read_text(encoding="utf-8")
    )
    heldout_digest = heldout.document_digest_of(
        json.loads(fixtures["doc"].read_text(encoding="utf-8"))
    )
    artifact = _artifact(
        tmp_path / "out",
        base={"repo_id": _BASE, "revision": provenance["base"]["revision"]},
        checkpoint={"digest": fixtures["checkpoint_obj"].digest},
        heldout={"document_digest": heldout_digest},
    )

    with pytest.raises(baseline.BaselineAlreadyMeasured) as refused:
        _measure(fixtures, out=artifact.parent)

    assert "2026-08-26" in str(refused.value), refused.value
    assert _BASE in str(refused.value), refused.value
    assert provenance["base"]["revision"] in str(refused.value), refused.value
    assert heldout_digest in str(refused.value), refused.value
    assert str(artifact) in str(refused.value), refused.value
    assert fixtures["stub"].asked == [], (
        "WHY THIS IS A FAILURE: the same-series refusal fired after a token was generated. "
        "The guard's ordering rule is the gate's — validated before the bytes it decides "
        "over — so a refused measurement must never have scored anything"
    )
    assert fixtures["used_checkpoints"] == [], (
        "WHY THIS IS A FAILURE: the engine seam was constructed for a measurement that "
        "must be refused before the engine exists"
    )


def test_two_untrained_bases_are_different_series(tmp_path: Path) -> None:
    """Two untrained bases at different revisions are different series, though every
    untrained checkpoint's digest is the same constant (`sha256(b"")`).

    `write_baseline_checkpoint` records no files, so an untrained checkpoint's digest is
    `_digest_of(())` — identical for every untrained base, whatever the repo id or
    revision. The measured-once guard keys on the series, and the series cannot be the
    checkpoint digest: the changed-base-revision case § 3 names as its legitimate new
    series (`PREREGISTRATION.md:133-135`) would read as a same-series second measurement
    and be refused. The key is the base identity + the held-out document digest.
    """
    fixtures = _fixtures(tmp_path)
    untrained_digest = hashlib.sha256(b"").hexdigest()
    heldout_digest = heldout.document_digest_of(
        json.loads(fixtures["doc"].read_text(encoding="utf-8"))
    )
    artifact = _artifact(
        tmp_path / "out",
        base={"repo_id": _BASE, "revision": "rev-one"},
        checkpoint={"digest": untrained_digest},
        heldout={"document_digest": heldout_digest},
    )

    measurement, second = _run_measure(tmp_path / "second", out=artifact.parent)

    assert measurement.checkpoint_digest == untrained_digest, (
        "WHY THIS IS A FAILURE: the fixture checkpoint is not the degenerate untrained "
        "digest — this test is about two bases that cannot be told apart by digest"
    )
    assert second["checkpoint_obj"].digest == untrained_digest
    evidence = _evidence(measurement)
    assert evidence["base"]["repo_id"] == _BASE
    provenance = json.loads(
        (second["checkpoint"] / "provenance.json").read_text(encoding="utf-8")
    )
    assert evidence["base"]["revision"] == provenance["base"]["revision"]
    assert provenance["base"]["revision"] != "rev-one", (
        "WHY THIS IS A FAILURE: the two bases share a revision, so this test is not "
        "about the changed-base case at all"
    )
    assert baseline.SeriesIdentity(
        repo_id=_BASE, revision="rev-one", heldout_digest=heldout_digest
    ) != baseline.SeriesIdentity(
        repo_id=_BASE,
        revision=provenance["base"]["revision"],
        heldout_digest=heldout_digest,
    )


def test_a_different_series_is_a_new_baseline(tmp_path: Path) -> None:
    """A changed pinned input is § 3's legitimate new series: an artifact naming a different
    base revision is allowed, and the evidence records the new base identity.

    `PREREGISTRATION.md:133-135` names this the only circumstance in which a second
    baseline measurement is legitimate — and the change that caused it is recorded, which
    is exactly what the evidence's own `base.repo_id`/`base.revision` fields are.
    """
    artifact = _artifact(
        tmp_path / "out", base={"repo_id": _BASE, "revision": "rev-one"}
    )
    measurement, _ = _run_measure(tmp_path, out=artifact.parent)

    assert measurement.checkpoint_digest != "c" * 64
    evidence = _evidence(measurement)
    assert evidence["base"]["repo_id"] == _BASE
    assert evidence["base"]["revision"] != "rev-one", (
        "WHY THIS IS A FAILURE: the run's base revision equals the artifact's — the "
        "different-series allowance was not exercised"
    )
    assert evidence["checkpoint"]["digest"] == measurement.checkpoint_digest
    assert evidence["heldout"]["document_digest"] == measurement.heldout_digest
    assert len(evidence["checkpoint"]["digest"]) == 64
    assert len(measurement.rollouts) == len(_MEMBERS) + 1, (
        "WHY THIS IS A FAILURE: a different-series artifact stalled the measurement. A "
        "changed pinned input is a new series, and the new series is measured, never refused"
    )


def test_an_unreadable_artifact_is_refused_never_treated_as_absent(tmp_path: Path) -> None:
    """Garbage at `--out/report.json` is a refusal naming the file — never an absent artifact.

    An artifact that cannot be parsed could be the same series, and a measurement that read
    it as absent would be a second measurement wearing the name of a first. The refusal is
    the reader's own — this is not the same-series refusal, and the message names the file.
    """
    out = tmp_path / "out"
    out.mkdir(parents=True)
    (out / "report.json").write_bytes(b"\x00\x01not json at all")

    with pytest.raises(ValueError) as refused:
        _run_measure(tmp_path, out=out)

    assert not isinstance(refused.value, baseline.BaselineAlreadyMeasured), refused.value
    assert "report.json" in str(refused.value), refused.value


def test_an_artifact_without_the_required_fields_is_refused(tmp_path: Path) -> None:
    """Schema-valid JSON missing an identity field is refused by name.

    The identity is the base identity and the held-out digest: a document that cannot
    yield both is not an identity, and a guard that guessed would either refuse the
    wrong series or admit the right one twice.
    """
    out = tmp_path / "out"
    _artifact(out, heldout={})

    with pytest.raises(ValueError) as refused:
        _run_measure(tmp_path, out=out)

    assert not isinstance(refused.value, baseline.BaselineAlreadyMeasured), refused.value
    assert "heldout.document_digest" in str(refused.value), refused.value

    without_base = tmp_path / "out2"
    _artifact(without_base, base={})

    with pytest.raises(ValueError) as refused:
        _run_measure(tmp_path / "second", out=without_base)

    assert not isinstance(refused.value, baseline.BaselineAlreadyMeasured), refused.value
    assert "base.repo_id" in str(refused.value), refused.value


def test_an_artifact_with_the_wrong_schema_is_refused(tmp_path: Path) -> None:
    """A wrong or missing `schema` is a refusal, never a default: the artifact's shape is
    `BASELINE_SCHEMA`, and a document declaring another shape is not read as one at all.
    """
    out = tmp_path / "out"
    _artifact(out, schema="whetstone-baseline/2")

    with pytest.raises(ValueError) as refused:
        _run_measure(tmp_path, out=out)

    assert not isinstance(refused.value, baseline.BaselineAlreadyMeasured), refused.value
    assert baseline.BASELINE_SCHEMA in str(refused.value), refused.value


def test_series_identity_equality() -> None:
    """The series identity is exactly the base identity and the held-out digest — nothing
    else is compared.

    The environment pins and tool versions are aspect 3's provenance, recorded in the
    artifact and part of § 3's pinned inputs, but they are not the refusal's key: the
    measured-once guard keys on the series, never on the clock and never on the toolchain.
    The checkpoint digest is not the key either: an untrained checkpoint's digest is the
    same constant for every base, so it cannot tell two bases apart.
    """
    first = baseline.SeriesIdentity(repo_id="r", revision="v1", heldout_digest="b" * 64)
    assert first == baseline.SeriesIdentity(
        repo_id="r", revision="v1", heldout_digest="b" * 64
    )
    assert first != baseline.SeriesIdentity(
        repo_id="r", revision="v1", heldout_digest="c" * 64
    )
    assert first != baseline.SeriesIdentity(
        repo_id="r", revision="v2", heldout_digest="b" * 64
    )
    assert first != baseline.SeriesIdentity(
        repo_id="s", revision="v1", heldout_digest="b" * 64
    )
    assert hash(first) == hash(
        baseline.SeriesIdentity(repo_id="r", revision="v1", heldout_digest="b" * 64)
    )


def test_baseline_engine_is_a_smoke_tested_factory() -> None:
    """The seam exists, is callable, and is never invoked by this test.

    `mlx` is an optional extra and every test in this aspect injects a stub engine, so the
    factory's real body is exercised only by the operator's GPU pass. This smoke test pins
    that the seam exists and is a factory whose signature names the three inputs the
    composition point is fixed on — `weights`, `checkpoint`, `max_tokens` — and that its
    token default is `DEFAULT_MAX_TOKENS` **by identity**, imported, never re-declared.
    Calling it is deliberately not part of the test.
    """
    from whetstone.bakeoff.mlx_runtime import DEFAULT_MAX_TOKENS

    assert callable(baseline.baseline_engine)

    parameters = inspect.signature(baseline.baseline_engine).parameters
    assert "weights" in parameters, f"signature {parameters} names no weights"
    assert "checkpoint" in parameters, f"signature {parameters} names no checkpoint"
    assert "max_tokens" in parameters, f"signature {parameters} names no max_tokens"
    assert parameters["max_tokens"].default is DEFAULT_MAX_TOKENS, (
        "the baseline's token budget must be the bake-off's own constant by identity, "
        "never a second number written beside it"
    )


# --------------------------------------------------------------------------------------------
# Task D: the module door — `python -m whetstone.loop.baseline`, its parser, exits and pins
# (spec.md requirement 6, AC 4 and 7; the aspect-4 runbook guard pins the flags against
# `build_parser` by identity).
# --------------------------------------------------------------------------------------------


def _argv(fixtures: dict[str, Any], *extra: str) -> list[str]:
    """The command line for `fixtures`: every flag, in the runbook's own order."""
    return [
        "--weights",
        str(fixtures["weights"]),
        "--checkpoint",
        str(fixtures["checkpoint"]),
        "--heldout",
        str(fixtures["heldout"]),
        "--tasks",
        str(fixtures["tasks"][0]),
        "--public",
        str(fixtures["public"]),
        "--runs",
        str(fixtures["runs"]),
        "--workspace",
        str(fixtures["workspace"]),
        "--out",
        str(fixtures["out"]),
        "--timeout",
        str(fixtures["timeout"]),
        "--recorded-on",
        str(fixtures["recorded_on"]),
        "--run-id",
        str(fixtures["run_id"]),
        "--pool",
        str(fixtures["pool"]),
        *extra,
    ]


def _without(argv: list[str], flag: str) -> list[str]:
    """`argv` with `flag` and its value removed — the shape "the operator left it out"."""
    index = argv.index(flag)
    return argv[:index] + argv[index + 2 :]


def _invoke(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    **fixture_overrides: Any,
) -> tuple[int, dict[str, Any]]:
    """Run the door over the shared fixtures, with the stub engine injected.

    `baseline.baseline_engine` is replaced on the module — `main()` resolves the name at
    call time, exactly as the gate's CLI tests replace `gate.gate_engine` behind the
    handler's call (`cli.py:804`) — so the real measurement runs under the stub, and the
    exits are asserted through the actual door rather than through a stand-in for it.
    """
    fixtures = _fixtures(tmp_path, **fixture_overrides)
    monkeypatch.setattr(baseline, "baseline_engine", fixtures["engine"])
    return baseline.main(_argv(fixtures)), fixtures


def test_the_door_exits_zero_and_prints_disclosure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 4: a completed measurement exits 0 **whatever the score**, and the disclosure
    carries every count over its denominator.

    The held-out set is fully solved through the stub engine, so the printout shows the
    whole shape: both digests abbreviated to twelve characters, both sources over their
    own denominators, coverage, `N` in the report's own pre-registered sentence with the
    count over its denominator, the unconditional retry line with `R` by identity, the
    evidence path, and the measured-once wording.
    """
    code, fixtures = _invoke(tmp_path, monkeypatch)

    assert code == 0, capsys.readouterr().err
    printed = capsys.readouterr().out
    checkpoint_digest = fixtures["checkpoint_obj"].digest
    heldout_digest = heldout.document_digest_of(
        json.loads(fixtures["doc"].read_text(encoding="utf-8"))
    )
    assert f"baseline checkpoint: {checkpoint_digest[:12]}" in printed, printed
    assert f"held-out document: {heldout_digest[:12]}" in printed, printed
    assert f"{len(_MEMBERS)} solved of {len(_MEMBERS)}" in printed, printed
    assert f"0 unverified of {len(_MEMBERS)}" in printed, printed
    assert f"coverage {len(_MEMBERS)} of {len(_MEMBERS)}" in printed, printed
    assert "0 rollouts a weaker check would have scored as wins. (0 of 10)" in printed, printed
    assert "1 solved of 1" in printed, printed
    assert "0 unverified of 1" in printed, printed
    assert f"R={baseline.RETRY_COUNT}" in printed, printed
    evidence_path = fixtures["runs"] / str(fixtures["run_id"]) / "evidence.json"
    assert f"evidence: {evidence_path}" in printed, printed
    assert "measured once" in printed, printed
    assert json.loads(evidence_path.read_text(encoding="utf-8"))["schema"] == (
        baseline.EVIDENCE_SCHEMA
    )


def test_the_door_exits_two_on_a_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 4: a same-series artifact at `--out` is exit 2 on stderr, naming the first artifact.

    The planted artifact is the first measurement; the door's run is a second measurement
    of the same series, which the § 3 protocol refuses by name (`PREREGISTRATION.md:
    129-135`) before a token is generated — the stub is never asked.
    """
    fixtures = _fixtures(tmp_path)
    monkeypatch.setattr(baseline, "baseline_engine", fixtures["engine"])
    provenance = json.loads(
        (fixtures["checkpoint"] / "provenance.json").read_text(encoding="utf-8")
    )
    artifact = _artifact(
        fixtures["out"],
        base={"repo_id": _BASE, "revision": provenance["base"]["revision"]},
        checkpoint={"digest": fixtures["checkpoint_obj"].digest},
        heldout={
            "document_digest": heldout.document_digest_of(
                json.loads(fixtures["doc"].read_text(encoding="utf-8"))
            )
        },
    )

    code = baseline.main(_argv(fixtures))

    assert code == 2
    err = capsys.readouterr().err
    assert "already measured" in err, err
    assert str(artifact) in err, err
    assert fixtures["stub"].asked == [], (
        "WHY THIS IS A FAILURE: the same-series refusal fired after a token was generated. "
        "The guard runs before the engine exists"
    )


def test_the_door_refuses_a_missing_recorded_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC 7: `--recorded-on` and `--run-id` are inputs, never defaults — omitted, exit 2.

    A measurement that dated or named itself would differ between two renders of the same
    documented command, so both are required flags and argparse's own error path refuses
    their absence with the usage code.
    """
    fixtures = _fixtures(tmp_path)
    monkeypatch.setattr(baseline, "baseline_engine", fixtures["engine"])
    argv = _argv(fixtures)

    with pytest.raises(SystemExit) as recorded:
        baseline.main(_without(argv, "--recorded-on"))
    assert recorded.value.code == 2

    with pytest.raises(SystemExit) as run_id:
        baseline.main(_without(argv, "--run-id"))
    assert run_id.value.code == 2


def test_every_flag_is_in_the_parser(tmp_path: Path) -> None:
    """The spec's flag set, asserted against `build_parser()` — the surface aspect 4 pins.

    Every flag the spec names (spec.md requirement 6) exists on the parser with the type
    the measurement reads — `--tasks` repeatable, `--timeout` a float, the rest paths and
    names, `--pool` optional, and `--max-tokens` defaulting to the bake-off's own
    `DEFAULT_MAX_TOKENS` **by identity**, never a second number beside it — and no flag
    outside the set does.
    """
    from whetstone.bakeoff.mlx_runtime import DEFAULT_MAX_TOKENS

    fixtures = _fixtures(tmp_path)
    parser = baseline.build_parser()
    flags = (
        {name for name in parser._option_string_actions if name.startswith("--")}
        - {"--help"}
    )
    assert flags == {
        "--weights",
        "--checkpoint",
        "--heldout",
        "--tasks",
        "--public",
        "--runs",
        "--workspace",
        "--out",
        "--timeout",
        "--recorded-on",
        "--run-id",
        "--pool",
        "--max-tokens",
        "--render",
        "--render-declaration",
    }, flags

    parsed = parser.parse_args(_argv(fixtures))
    assert parsed.weights == fixtures["weights"]
    assert parsed.checkpoint == fixtures["checkpoint"]
    assert parsed.heldout == fixtures["heldout"]
    assert parsed.tasks == [fixtures["tasks"][0]]
    assert parsed.public == fixtures["public"]
    assert parsed.runs == fixtures["runs"]
    assert parsed.workspace == fixtures["workspace"]
    assert parsed.out == fixtures["out"]
    assert parsed.timeout == fixtures["timeout"]
    assert parsed.recorded_on == fixtures["recorded_on"]
    assert parsed.run_id == fixtures["run_id"]
    assert parsed.pool == fixtures["pool"]
    assert parsed.max_tokens is DEFAULT_MAX_TOKENS


def test_baseline_module_imports_no_mlx_at_module_scope() -> None:
    """The loop package's own rule, walked over `baseline.py`'s bytes with `ast`.

    `baseline_engine` imports `mlx_lm` inside its body — the factory is the seam, and the
    seam is reached only when an operator's GPU pass invokes it. A module-scope
    `mlx`/`mlx_lm` import would execute on every `import whetstone.loop.baseline` and put
    an inference library on the loop's import graph unconditionally, so the walk forbids
    it: an import whose root is `mlx` or `mlx_lm` may appear only inside a function body.

    Anti-vacuity: the walk also demands that the module define `baseline_engine` at module
    scope, so an empty module fails this test rather than passing it by containing no
    imports at all.
    """
    tree = ast.parse(MODULE.read_bytes(), filename=str(MODULE))

    assert any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "baseline_engine"
        for node in tree.body
    ), "baseline.py defines no baseline_engine — this walk has nothing to guard"

    function_local: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(node):
                if isinstance(inner, (ast.Import, ast.ImportFrom)):
                    function_local.add(inner.lineno)

    at_module_scope = [
        f"line {node.lineno}: "
        + ", ".join(alias.name for alias in node.names)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and node.lineno not in function_local
        and any(alias.name.split(".")[0] in FORBIDDEN_IMPORT_ROOTS for alias in node.names)
    ]
    assert not at_module_scope, (
        "baseline.py imports an inference library at module scope: "
        + "; ".join(at_module_scope)
        + "\n\nWHY THIS IS A FAILURE: a module-scope import executes on every import of the"
        " module, so `import whetstone.loop.baseline` would load mlx even when no GPU pass"
        " ever asked for it. The loop package's rule is that every mlx import is"
        " function-local inside the factory, reached only when the operator invokes the"
        " seam"
    )


# --------------------------------------------------------------------------------------------
# Task D extension: the render door — `render_artifact`, `render_declaration`, and the
# `--render`/`--render-declaration` modes on the module door (spec.md requirement 4, AC 6).
# The post-run chain renders the committed artifact from a real measurement's evidence;
# the measured-once discipline holds on the render side too — a rendered baseline is not
# re-rendered — and the declaration is the committed state *before* any measurement.
# --------------------------------------------------------------------------------------------


def _render_argv(fixtures: dict[str, Any], evidence: Path, out: Path) -> list[str]:
    """The render-mode command line: evidence, the shared flags, nothing measuring."""
    return [
        "--render",
        str(evidence),
        "--checkpoint",
        str(fixtures["checkpoint"]),
        "--out",
        str(out),
        "--recorded-on",
        str(fixtures["recorded_on"]),
    ]


def test_render_writes_the_three_artifacts_from_evidence(tmp_path: Path) -> None:
    """AC 6: a genuine evidence document (from `measure()` with the stub engine) renders
    the three-artifact shape, and the Task-B loader round-trips the rendered report.json.

    The evidence is the real measurement's own document — not a hand-built stand-in — so
    the render is exercised over the document the operator's post-run chain actually
    consumes. The artifact's series is the evidence's own recorded base identity and
    held-out digest, its sides are the
    evidence's six-field counts verbatim, the evidence pointer is the sha256 of the
    evidence's bytes (never contents), and the base block carries the § 7.3-open sentence.
    """
    measurement, fixtures = _run_measure(tmp_path / "measure")
    home = tmp_path / "home"

    rendered = baseline.render_artifact(
        evidence=measurement.evidence_path,
        out=home,
        recorded_on=RECORDED_ON,
        checkpoint=fixtures["checkpoint"],
    )

    assert [path.name for path in rendered] == ["report.md", "report.json", "cost.json"]
    assert all(path.exists() for path in rendered)

    evidence_document = _evidence(measurement)
    payload = json.loads(rendered[1].read_text(encoding="utf-8"))
    assert payload["schema"] == baseline.BASELINE_SCHEMA
    assert payload["measured"] is True
    assert payload["series"]["repo_id"] == evidence_document["base"]["repo_id"]
    assert payload["series"]["revision"] == evidence_document["base"]["revision"]
    assert payload["series"]["heldout_digest"] == evidence_document["heldout"][
        "document_digest"
    ]
    assert payload["sides"]["source-b"] == evidence_document["counts"]["heldout"]
    assert payload["sides"]["source-a"] == evidence_document["counts"]["public"]
    assert payload["evidence"]["digest"] == hashlib.sha256(
        measurement.evidence_path.read_bytes()
    ).hexdigest()
    assert payload["series"]["repo_id"] == _BASE
    provenance = json.loads(
        (fixtures["checkpoint"] / "provenance.json").read_text(encoding="utf-8")
    )
    assert payload["series"]["revision"] == provenance["base"]["revision"]
    assert "§ 7.3" in payload["base"]["sentence"]

    loaded = baseline.read_baseline_document(rendered[1])
    assert loaded.series == baseline.SeriesIdentity(
        repo_id=evidence_document["base"]["repo_id"],
        revision=evidence_document["base"]["revision"],
        heldout_digest=evidence_document["heldout"]["document_digest"],
    )
    assert loaded.base == payload["base"]
    assert loaded.sides == payload["sides"]
    assert loaded.evidence == payload["evidence"]
    assert loaded.n == payload["n"]
    assert loaded.measured is True


def test_render_refuses_missing_or_schema_invalid_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 6: evidence that cannot be read is refused by name — never rendered from nothing.

    A missing file, unreadable bytes and a wrong schema are three different refusals, each
    naming the evidence file; the door maps each to exit 2 on stderr, and no artifact is
    written anywhere.
    """
    fixtures = _fixtures(tmp_path)
    home = tmp_path / "home"

    missing = tmp_path / "missing" / "evidence.json"
    with pytest.raises(ValueError) as refused:
        baseline.render_artifact(
            evidence=missing,
            out=home,
            recorded_on=RECORDED_ON,
            checkpoint=fixtures["checkpoint"],
        )
    assert "evidence.json" in str(refused.value), refused.value

    garbage = tmp_path / "garbage" / "evidence.json"
    garbage.parent.mkdir(parents=True)
    garbage.write_bytes(b"\x00\x01not json at all")
    with pytest.raises(ValueError) as refused:
        baseline.render_artifact(
            evidence=garbage,
            out=home,
            recorded_on=RECORDED_ON,
            checkpoint=fixtures["checkpoint"],
        )
    assert "evidence.json" in str(refused.value), refused.value

    wrong_schema = tmp_path / "wrong" / "evidence.json"
    wrong_schema.parent.mkdir(parents=True)
    wrong_schema.write_text(
        json.dumps({"schema": "whetstone-baseline-run/2"}), encoding="utf-8"
    )
    with pytest.raises(ValueError) as refused:
        baseline.render_artifact(
            evidence=wrong_schema,
            out=home,
            recorded_on=RECORDED_ON,
            checkpoint=fixtures["checkpoint"],
        )
    assert "whetstone-baseline-run/2" in str(refused.value), refused.value
    assert not home.exists(), (
        "WHY THIS IS A FAILURE: a refused render wrote artifacts — nothing may be "
        "rendered from an evidence the render refused"
    )

    monkeypatch.setattr(baseline, "baseline_engine", fixtures["engine"])
    code = baseline.main(_render_argv(fixtures, missing, home))
    assert code == 2
    assert "evidence.json" in capsys.readouterr().err


def test_render_refuses_a_gitignored_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 6: `--out` under a gitignored root is refused by identity, never rewritten.

    The committed artifact is the "before" of every later delta, and one git cannot see is
    one git cannot prove predated the measurement — the aspect-2 posture, consumed by
    identity (`refuse_committed_out`), exit 2 through the door.
    """
    measurement, fixtures = _run_measure(tmp_path / "measure")
    runs_home = tmp_path / "runs" / "published"

    with pytest.raises(OutUnderLocalCorpus) as refused:
        baseline.render_artifact(
            evidence=measurement.evidence_path,
            out=runs_home,
            recorded_on=RECORDED_ON,
            checkpoint=fixtures["checkpoint"],
        )
    assert "runs" in str(refused.value), refused.value
    assert baseline.refuse_committed_out is heldout.refuse_committed_out

    monkeypatch.setattr(baseline, "baseline_engine", fixtures["engine"])
    code = baseline.main(_render_argv(fixtures, measurement.evidence_path, runs_home))
    assert code == 2
    assert "runs" in capsys.readouterr().err


def test_render_refuses_a_same_series_rerender(tmp_path: Path) -> None:
    """AC 6: an artifact already rendered for this series is not re-rendered, by name.

    The measured-once discipline holds on the render side: the same evidence and the same
    checkpoint produce the same artifact by construction, so a second render would be the
    first render wearing a second date — refused with the same exception type the measure
    door raises, naming the first artifact and its recorded date.
    """
    measurement, fixtures = _run_measure(tmp_path / "measure")
    home = tmp_path / "home"
    baseline.render_artifact(
        evidence=measurement.evidence_path,
        out=home,
        recorded_on=RECORDED_ON,
        checkpoint=fixtures["checkpoint"],
    )

    with pytest.raises(baseline.BaselineAlreadyMeasured) as refused:
        baseline.render_artifact(
            evidence=measurement.evidence_path,
            out=home,
            recorded_on=RECORDED_ON,
            checkpoint=fixtures["checkpoint"],
        )
    message = str(refused.value)
    assert str(home / "report.json") in message, message
    assert RECORDED_ON in message, message
    assert "re-rendered" in message or "render" in message, message


def test_render_allows_a_different_series(tmp_path: Path) -> None:
    """A changed pinned input is § 3's legitimate new series on the render side too.

    An evidence naming a different base revision is a new series, rendered into the
    same home the way `measure()` permits a different series — never refused by the
    same-series guard, which keys on the base identity and the held-out digest, never on
    the clock.
    """
    measurement, fixtures = _run_measure(tmp_path / "measure")
    home = tmp_path / "home"
    baseline.render_artifact(
        evidence=measurement.evidence_path,
        out=home,
        recorded_on=RECORDED_ON,
        checkpoint=fixtures["checkpoint"],
    )

    different = tmp_path / "different" / "evidence.json"
    different.parent.mkdir(parents=True)
    document = _evidence(measurement)
    document["base"]["revision"] = "other-rev"
    different.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    rendered = baseline.render_artifact(
        evidence=different,
        out=home,
        recorded_on=RECORDED_ON,
        checkpoint=fixtures["checkpoint"],
    )
    payload = json.loads(rendered[1].read_text(encoding="utf-8"))
    assert payload["series"]["revision"] == "other-rev"


def test_the_door_rejects_render_and_measure_together(tmp_path: Path) -> None:
    """AC 6: `--render` and measuring are mutually exclusive — the parser's usage exit.

    A command line that names both modes is a command nobody meant, and it is refused
    with argparse's own usage code rather than being run in one mode while silently
    ignoring the other's flags.
    """
    fixtures = _fixtures(tmp_path)
    argv = _argv(fixtures) + [
        "--render",
        str(fixtures["runs"] / str(fixtures["run_id"]) / "evidence.json"),
    ]

    with pytest.raises(SystemExit) as refused:
        baseline.main(argv)
    assert refused.value.code == 2


def test_render_declaration_writes_the_declaration_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 6: `--render-declaration` writes the committed pre-run state — no count anywhere.

    The declaration is the state *before* any measurement: the three-artifact shape
    carrying the "No count is measured here" sentence and no figure in any spelling, in
    all three artifacts, generated by the writer with `measured=False` — and the Task-B
    loader reads it back as a declaration, never as a measurement.
    """
    out = tmp_path / "declaration-home"
    code = baseline.main(["--render-declaration", str(out), "--recorded-on", RECORDED_ON])

    assert code == 0, capsys.readouterr().err
    for name in ("report.md", "report.json", "cost.json"):
        assert (out / name).is_file(), name
    text = "\n".join(
        (out / name).read_text(encoding="utf-8") for name in ("report.md", "report.json", "cost.json")
    )
    assert not re.search(r"\d+ of \d+", text), (
        "WHY THIS IS A FAILURE: the declaration renders a figure, but no measurement "
        "exists — a count here would be a restated figure from another home or an "
        "invented one"
    )
    assert "No count is measured here: the baseline has not run." in text, text

    loaded = baseline.read_baseline_document(out / "report.json")
    assert loaded.measured is False
    assert loaded.series is None and loaded.sides is None and loaded.n is None


def test_render_declaration_refuses_a_gitignored_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The declaration is a committed artifact: a gitignored `--out` is refused by identity.

    The declaration is the state git history proves predated the measurement, so one git
    cannot see is one git cannot vouch for — the same `refuse_committed_out` posture as
    the measure door, exit 2.
    """
    code = baseline.main(
        ["--render-declaration", str(tmp_path / "runs" / "declaration"), "--recorded-on", RECORDED_ON]
    )
    assert code == 2
    assert "runs" in capsys.readouterr().err