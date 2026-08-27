"""The gate's pure decision core: the roadmap rule, with no harness in front of it.

The gate's verdict is `docs/ROADMAP.md:420-427` and nothing else:

    promote iff  solved_new > solved_old
            AND  regressed  == 0
            AND  unverified == 0

Three exits only: `promoted` / `rejected` / `UNVERIFIED`, and `UNVERIFIED` is never collapsed
into `promoted`. This file tests the *pure* half — `decide` over two per-task outcome maps —
because the rule is the one thing in this unit that must not be buried under the harness:
every other guarantee (re-hashed checkpoints, the held-out document, the STRICT verifier) is
machinery around it, and a rule that is only ever exercised through machinery is a rule whose
edge cases nobody has read.

The counts are all over the **shared denominator**: the task set both maps carry. A task
either side failed to reach a verdict on (`UNVERIFIED`, `UNPROVISIONED`, `NO_ORACLE` — the
sibling's own `_UNCOVERED` set, imported by identity) is a task no comparison was actually
made on, and it makes the whole evaluation `UNVERIFIED` (`docs/ROADMAP.md:438-440`): not
promoted and not rejected, because neither would be a statement the evidence supports.

No model, no `mlx`, no network — the inputs are outcome maps and the outputs are counts.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from fixtures.repos.mined import build_mined_task

from loop.harness import (
    RECORDED_ON,
    TIMEOUT,
    Answers,
    corpus,
    pool,
    solving_answers,
)
from loop.harness import (
    weights as harness_weights,
)
from whetstone.bakeoff.scoring import Outcome
from whetstone.bakeoff.weights import Weights, load_weights
from whetstone.loop import gate, heldout, sft
from whetstone.loop.gate import Exit, GateDecision, decide
from whetstone.verify.task import Task

#: Three tasks, enough to separate every count the rule reads.
_IDS = ("a", "b", "c")


def _map(*outcomes: Outcome) -> dict[str, Outcome]:
    """One outcome per declared id, in order."""
    assert len(outcomes) == len(_IDS), outcomes
    return dict(zip(_IDS, outcomes, strict=True))


def test_known_better_is_promoted() -> None:
    """The rule's happy path: more solves, nothing lost, nothing unverified."""
    decision = decide(
        candidate=_map(Outcome.SOLVED, Outcome.SOLVED, Outcome.NOT_SOLVED),
        incumbent=_map(Outcome.SOLVED, Outcome.NOT_SOLVED, Outcome.NOT_SOLVED),
    )
    assert decision.exit is Exit.PROMOTED
    assert decision.denominator == 3
    assert decision.solved_new == 2 and decision.solved_old == 1
    assert decision.regressed == 0 and decision.unverified == 0


def test_known_worse_is_rejected() -> None:
    """Fewer solves is a rejection; the incumbent stays put."""
    decision = decide(
        candidate=_map(Outcome.SOLVED, Outcome.NOT_SOLVED, Outcome.NOT_SOLVED),
        incumbent=_map(Outcome.SOLVED, Outcome.SOLVED, Outcome.NOT_SOLVED),
    )
    assert decision.exit is Exit.REJECTED
    assert decision.solved_new == 1 and decision.solved_old == 2


def test_equal_solved_counts_is_rejected_by_the_greater_than_term() -> None:
    """Equal solves is `rejected`, never a tie-break — the rule says `>`, not `>=`.

    This is the trap the asserted test exists for: a tie reads like a promotion to a reader
    who sees "no regression, no unverified" and stops there. The `>` term is the whole
    never-regress contract — a checkpoint that provably beats the last one, not merely
    matches it.
    """
    decision = decide(
        candidate=_map(Outcome.SOLVED, Outcome.SOLVED, Outcome.NOT_SOLVED),
        incumbent=_map(Outcome.SOLVED, Outcome.SOLVED, Outcome.NOT_SOLVED),
    )
    assert decision.exit is Exit.REJECTED
    assert decision.solved_new == decision.solved_old == 2
    assert decision.regressed == 0 and decision.unverified == 0


def test_candidate_identical_to_incumbent_is_rejected() -> None:
    """The self-comparison is `rejected` by the `>` term — asserted, not an accident.

    A gate that promoted "the same checkpoint against itself" would let any operator
    manufacture a promotion by pointing both flags at one directory. There is no special
    case here; the rule's own `>` makes it a rejection, and the test pins that it does.
    """
    both = _map(Outcome.SOLVED, Outcome.NOT_SOLVED, Outcome.NOT_SOLVED)
    decision = decide(candidate=both, incumbent=dict(both))
    assert decision.exit is Exit.REJECTED
    assert decision.solved_new == decision.solved_old == 1


def test_one_still_unverified_task_makes_the_whole_eval_unverified() -> None:
    """`docs/ROADMAP.md:438-440`: no comparison was actually made, so nothing is decided.

    The counts are reported — the decision carries them — but the exit is the third one:
    not promoted and not rejected, because neither would be a statement the evidence
    supports.
    """
    decision = decide(
        candidate=_map(Outcome.SOLVED, Outcome.UNVERIFIED, Outcome.NOT_SOLVED),
        incumbent=_map(Outcome.NOT_SOLVED, Outcome.SOLVED, Outcome.NOT_SOLVED),
    )
    assert decision.exit is Exit.UNVERIFIED
    assert decision.unverified == 1
    assert decision.solved_new == 1 and decision.solved_old == 0, (
        "WHY THIS IS A FAILURE: a solve on a task the other side could not be scored on "
        "was credited to a side. No comparison was actually made on that task, so neither "
        "side may count it"
    )


def test_unverified_outranks_a_promotion_shaped_comparison() -> None:
    """The `unverified` term beats the `>` term: counts that would promote still reduce to 3."""
    decision = decide(
        candidate=_map(Outcome.SOLVED, Outcome.SOLVED, Outcome.UNVERIFIED),
        incumbent=_map(Outcome.NOT_SOLVED, Outcome.NOT_SOLVED, Outcome.NOT_SOLVED),
    )
    assert decision.exit is Exit.UNVERIFIED
    assert decision.solved_new == 2 and decision.solved_old == 0


@pytest.mark.parametrize(
    "unknown",
    [Outcome.UNVERIFIED, Outcome.UNPROVISIONED, Outcome.NO_ORACLE],
    ids=["unverified", "unprovisioned", "no-oracle"],
)
def test_any_task_without_a_verdict_reduces_the_whole_eval(unknown: Outcome) -> None:
    """The sibling's `_UNCOVERED` set is the "reached no verdict" definition, by identity.

    A task whose environment could not be built, or whose generation contract could not be
    built, is a task no comparison was actually made on — the identical argument to a bare
    `UNVERIFIED`, one step earlier in the pipeline.
    """
    decision = decide(
        candidate=_map(Outcome.SOLVED, unknown, Outcome.SOLVED),
        incumbent=_map(Outcome.SOLVED, Outcome.NOT_SOLVED, Outcome.NOT_SOLVED),
    )
    assert decision.exit is Exit.UNVERIFIED
    assert decision.unverified == 1


def test_a_regressed_task_rejects_even_with_a_solved_gain() -> None:
    """`regressed == 0` is a conjunct, never an afterthought: one loss is a rejection.

    The candidate gained a task AND lost one the incumbent solved — net zero, and the rule
    does not do netting. The incumbent's solve on `c` must come back as `regressed`.
    """
    decision = decide(
        candidate=_map(Outcome.SOLVED, Outcome.SOLVED, Outcome.NOT_SOLVED),
        incumbent=_map(Outcome.NOT_SOLVED, Outcome.SOLVED, Outcome.SOLVED),
    )
    assert decision.exit is Exit.REJECTED
    assert decision.solved_new == 2 and decision.solved_old == 2
    assert decision.regressed == 1


def test_a_regression_rejects_even_when_solved_new_exceeds_solved_old() -> None:
    """The strongest form of the conjunct: more solves AND a regression is still `rejected`."""
    decision = decide(
        candidate=_map(Outcome.SOLVED, Outcome.SOLVED, Outcome.NOT_SOLVED),
        incumbent=_map(Outcome.NOT_SOLVED, Outcome.NOT_SOLVED, Outcome.SOLVED),
    )
    assert decision.exit is Exit.REJECTED
    assert decision.solved_new == 2 and decision.solved_old == 1
    assert decision.regressed == 1


def test_mismatched_task_sets_are_refused() -> None:
    """Both sides must be scored over the same membership; a mismatch is a broken caller.

    Refused rather than silently compared over the intersection: a task scored on one side
    alone is a task one checkpoint was never asked about, and a decision over the overlap
    would read as a full comparison.
    """
    with pytest.raises(ValueError) as refused:
        decide(
            candidate=_map(Outcome.SOLVED, Outcome.SOLVED, Outcome.SOLVED),
            incumbent=dict(zip(("a", "b"), (Outcome.SOLVED, Outcome.SOLVED), strict=True)),
        )
    message = str(refused.value)
    assert "c" in message and "candidate-only" in message, (
        f"WHY THIS IS A FAILURE: the refusal does not name the mismatched id: {message!r}"
    )


def test_the_solved_definition_is_outcome_solved_by_identity() -> None:
    """`Outcome.SOLVED` — the same member the loop's trainable partition imports.

    A second notion of "this task was solved" is exactly how the gate and the training
    selection stop agreeing about what a win is. The module imports the one member; the
    assertion pins that it did.
    """
    assert gate.Outcome is Outcome


def test_the_unverified_definition_is_the_siblings_by_identity() -> None:
    """`report._UNCOVERED` — the same set coverage reduces against, imported, never restated."""
    from whetstone.bakeoff import report as bakeoff_report

    assert gate._UNCOVERED is bakeoff_report._UNCOVERED


def test_the_decision_carries_the_counts_a_record_needs() -> None:
    """The record's per-side counts come from the decision; their presence is asserted here.

    A decision that carried only the exit would be a verdict nobody could re-derive from
    the scored outcomes — the promotion record would have to guess these numbers back.
    """
    decision = decide(
        candidate=_map(Outcome.SOLVED, Outcome.NOT_SOLVED, Outcome.UNVERIFIED),
        incumbent=_map(Outcome.NOT_SOLVED, Outcome.SOLVED, Outcome.SOLVED),
    )
    assert isinstance(decision, GateDecision)
    assert decision.denominator == 3
    assert decision.exit is Exit.UNVERIFIED
    assert decision.detail, "WHY THIS IS A FAILURE: the decision carries no sentence explaining it"

# --------------------------------------------------------------------------------------------
# Phase 2: scoring and the promotion record. run_gate over fixture checkpoints, a fixture
# held-out document and the stub engine — the three exits are asserted through the full
# harness here and at the CLI boundary (tests/loop/test_gate_cli.py).
# --------------------------------------------------------------------------------------------

#: The one base both fixture checkpoints name. The weights root holds exactly this candidate.
_BASE = "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit"

#: The loaded private corpus the fixture documents are defined over: eleven tasks, ten held
#: out by the document, one ("t-11") left outside the membership — the shape that proves the
#: gate scores exactly the membership and nothing else.
_PRIVATE_IDS = tuple(f"t-{i:02d}" for i in range(1, 12))

#: The members the fixture document holds out: every id but the survivor.
_MEMBERS = _PRIVATE_IDS[:-1]

#: A task whose fix commit carries a file over the 80_000-character oracle budget, so no
#: prompt can be rendered for it and every rollout is `NO_ORACLE` — the deterministic
#: "reached no verdict" shape this suite uses for the incomplete-eval tests.
_BULK = {"t-12": 200_000}

#: How many held-out tasks the incumbent solves in the default "known-better" pair.
_INCUMBENT_SOLVES = 6


def _stub_trainer(label: str) -> sft.Trainer:
    """A trainer that writes an adapter-shaped file distinguishable by `label`.

    The two fixture checkpoints must differ by digest — the gate's engine seam keys on it —
    so the adapter bytes carry the label.
    """

    def train(request: sft.TrainingRequest) -> sft.TrainingResult:
        request.adapters.mkdir(parents=True, exist_ok=True)
        (request.adapters / request.args.adapter_file).write_bytes(
            f"not a tensor, deliberately ({label})".encode()
        )
        (request.adapters / sft.ADAPTER_CONFIG).write_text('{"lora_parameters": {}}')
        return sft.TrainingResult(peak_bytes=4 * 1024**3, seconds=0.25)

    return train


def _checkpoint(root: Path, *, repo_id: str, revision: str, label: str) -> sft.Checkpoint:
    """A night-shaped checkpoint over a stub adapter, hashed by `sft.write_checkpoint`.

    The same seam the night itself uses, so a gate test's checkpoints are the real artefact
    `verify_checkpoint` will re-hash — never a hand-written directory beside it.
    """
    request = sft.TrainingRequest(
        model_path=root / "weights",
        revision=revision,
        data=root / "data",
        adapters=root / label,
        args=sft.TrainingArgs(),
    )
    capacity = sft.probe_capacity(request, trainer=_stub_trainer(label))
    sft.train(request, trainer=_stub_trainer(label), capacity=capacity, examples=3)
    return sft.write_checkpoint(
        root / label,
        repo_id=repo_id,
        revision=revision,
        dataset_digest="d" * 64,
        run_seed=20260824,
        args=request.args,
        tool_versions={"python": "3.12.0"},
        valid_split="",
        capacity=capacity,
    )


def _heldout_document(
    root: Path, members: Sequence[str], *, corpus_ids: Sequence[str] = _PRIVATE_IDS, **fields: Any
) -> Path:
    """A loader-valid `whetstone-heldout/1` document over `corpus_ids` with membership `members`.

    The `test_night_integration` shape, restated here: the loader validates a document against
    itself, and only the run-side resolution matches the membership against the loaded corpus —
    so a test can plant a membership the rule would never select and still reach the check it
    is about. The digest is sealed through aspect 1's own function after `fields` are applied.
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
    root: Path, ids: Sequence[str], *, bulk: Mapping[str, int] | None = None
) -> tuple[Path, list[Any]]:
    """One donor per id with manifests collected into a directory — the `harness.corpus` shape.

    Restated here (rather than parameterised through the harness) because the gate's
    incomplete-eval tests need one task carrying an over-budget source file, and that is a
    `build_mined_task` option the harness's `corpus` does not expose.
    """
    directory = root / "private"
    directory.mkdir(parents=True)
    built: list[Any] = []
    for task_id in ids:
        fixture = build_mined_task(
            root / f"donor-{task_id}",
            task_id=task_id,
            subject=f"Fix addition ({task_id})",
            bulk_chars=(bulk or {}).get(task_id, 0),
        )
        shutil.copy(root / f"donor-{task_id}" / f"{task_id}.json", directory / f"{task_id}.json")
        built.append(fixture)
    return directory, built


def _gate_fixtures(
    tmp_path: Path,
    *,
    candidate_answers: Mapping[str, str] | None = None,
    incumbent_answers: Mapping[str, str] | None = None,
    candidate_solve: int | None = None,
    incumbent_solve: int = _INCUMBENT_SOLVES,
    private_ids: Sequence[str] = _PRIVATE_IDS,
    members: Sequence[str] = _MEMBERS,
    bulk: Mapping[str, int] | None = None,
    runs: Path | None = None,
) -> dict[str, Any]:
    """Everything a gate invocation needs on disk — checkpoints, document, corpus, weights —
    plus the stub engine keyed on the checkpoints' digests.

    The shared shape behind both `_run_gate` (direct calls) and the CLI tests (invocations
    of `whetstone gate` with `gate.gate_engine` monkeypatched to `fixtures["engine"]`), so
    the three exits are asserted through the full harness at both boundaries.
    """
    private, private_built = _private_corpus(tmp_path / "corpus", private_ids, bulk=bulk)
    public, public_built = corpus(tmp_path / "corpus", "public", ("pallets__flask-4045",))
    members_set = set(members)
    held_members = [fixture for fixture in private_built if fixture.task.task_id in members_set]
    poseable = [fixture for fixture in held_members if _poseable(fixture.task)]

    if candidate_answers is None:
        take = len(members) if candidate_solve is None else candidate_solve
        candidate_answers = solving_answers(*poseable[:take], *public_built)
    if incumbent_answers is None:
        incumbent_answers = solving_answers(*poseable[:incumbent_solve], *public_built)

    doc = _heldout_document(tmp_path / "doc", members, corpus_ids=private_ids)
    weights_root = harness_weights(tmp_path / "weights", _BASE)
    base = load_weights(weights_root)[0]
    candidate_checkpoint = _checkpoint(
        tmp_path / "candidate", repo_id=_BASE, revision=base.revision, label="candidate"
    )
    incumbent_checkpoint = _checkpoint(
        tmp_path / "incumbent", repo_id=_BASE, revision=base.revision, label="incumbent"
    )

    used_checkpoints: list[str] = []

    def engine(weights: Weights, checkpoint: sft.Checkpoint, max_tokens: int) -> Answers:
        assert max_tokens >= 1, max_tokens
        assert weights.repo_id == _BASE, weights.repo_id
        used_checkpoints.append(checkpoint.digest)
        if checkpoint.digest == candidate_checkpoint.digest:
            return Answers(candidate_answers)
        assert checkpoint.digest == incumbent_checkpoint.digest, checkpoint.digest
        return Answers(incumbent_answers)

    return {
        "candidate": candidate_checkpoint.directory,
        "incumbent": incumbent_checkpoint.directory,
        "heldout": doc,
        "tasks": (private,),
        "public": public,
        "pool": pool(tmp_path / "pool" / "pool.json"),
        "weights": weights_root,
        "runs": tmp_path / "runs" if runs is None else runs,
        "workspace": tmp_path / "work",
        "timeout": TIMEOUT,
        "recorded_on": RECORDED_ON,
        "run_id": "gate-001",
        "engine": engine,
        "candidate_checkpoint": candidate_checkpoint,
        "incumbent_checkpoint": incumbent_checkpoint,
        "doc": doc,
        "private_built": private_built,
        "public_built": public_built,
        "used_checkpoints": used_checkpoints,
        "answers_generators": [candidate_answers, incumbent_answers],
    }


def _run_gate(
    tmp_path: Path,
    *,
    candidate_answers: Mapping[str, str] | None = None,
    incumbent_answers: Mapping[str, str] | None = None,
    candidate_solve: int | None = None,
    incumbent_solve: int = _INCUMBENT_SOLVES,
    private_ids: Sequence[str] = _PRIVATE_IDS,
    members: Sequence[str] = _MEMBERS,
    bulk: Mapping[str, int] | None = None,
    runs: Path | None = None,
    **overrides: Any,
) -> tuple[gate.GateOutcome, dict[str, Any]]:
    """One full gate run over the shared fixtures — see `_gate_fixtures`.

    The candidate answers the reference patch for every held-out member unless narrowed by
    `candidate_solve`; the incumbent answers `incumbent_solve` of them. Either table can be
    replaced wholesale via `candidate_answers` / `incumbent_answers`. The returned fixtures
    dict carries the checkpoints, the document, and every posed prompt, so a test can assert
    on the evidence rather than on the code's own claims.
    """
    fixtures = _gate_fixtures(
        tmp_path,
        candidate_answers=candidate_answers,
        incumbent_answers=incumbent_answers,
        candidate_solve=candidate_solve,
        incumbent_solve=incumbent_solve,
        private_ids=private_ids,
        members=members,
        bulk=bulk,
        runs=runs,
    )
    arguments: dict[str, Any] = {
        "candidate": fixtures["candidate"],
        "incumbent": fixtures["incumbent"],
        "heldout": fixtures["heldout"],
        "tasks": fixtures["tasks"],
        "public": fixtures["public"],
        "pool": fixtures["pool"],
        "weights": fixtures["weights"],
        "runs": fixtures["runs"],
        "workspace": fixtures["workspace"],
        "timeout": fixtures["timeout"],
        "recorded_on": fixtures["recorded_on"],
        "run_id": fixtures["run_id"],
        "engine": fixtures["engine"],
    }
    arguments.update(overrides)
    outcome = gate.run_gate(**arguments)
    return outcome, fixtures


def _prompted(fixture: Any) -> str:
    """The prompt the stub poses for `fixture`, via the harness's own renderer."""
    from loop.harness import posed

    return posed(fixture.task)


def _poseable(task: Task) -> bool:
    """Whether a prompt can be rendered for `task` at all — the oracle's own answer.

    `solving_answers` poses every fixture it is given, and `posed` asserts the oracle
    resolved; an over-budget task (`NO_ORACLE`) must be excluded from the answer tables,
    not posed and crashed on.
    """
    from whetstone.bakeoff.sources import oracle_sources

    return oracle_sources(task).files is not None


def test_run_gate_scores_the_held_out_membership_and_promotes_the_known_better(
    tmp_path: Path,
) -> None:
    """A known-better pair reaches `promoted` through the full harness, with the record.

    The candidate answers the reference patch for every held-out task; the incumbent for six.
    Through the real scoring harness — prompt render, extraction, git apply, STRICT — the
    candidate's solves beat the incumbent's with no regression and no unverified, so the
    decision is `promoted` and the promotion record names the bytes it compared.
    """
    outcome, fixtures = _run_gate(tmp_path)

    assert outcome.decision.exit is Exit.PROMOTED, outcome.decision.detail
    assert outcome.decision.denominator == len(_MEMBERS)
    assert outcome.decision.solved_new == len(_MEMBERS)
    assert outcome.decision.solved_old == _INCUMBENT_SOLVES
    assert outcome.decision.regressed == 0 and outcome.decision.unverified == 0

    assert outcome.candidate_digest == fixtures["candidate_checkpoint"].digest
    assert outcome.incumbent_digest == fixtures["incumbent_checkpoint"].digest
    assert set(fixtures["used_checkpoints"]) == {
        fixtures["candidate_checkpoint"].digest,
        fixtures["incumbent_checkpoint"].digest,
    }, (
        "WHY THIS IS A FAILURE: the engine seam was not given exactly one call per side with "
        "the verified checkpoint, so the scoring did not run under the re-hashed bytes"
    )

    document = json.loads(outcome.record.read_text(encoding="utf-8"))
    assert document["schema"] == gate.PROMOTION_SCHEMA
    assert document["run_id"] == "gate-001"
    assert document["recorded_on"] == RECORDED_ON
    assert document["candidate"]["digest"] == fixtures["candidate_checkpoint"].digest
    assert document["incumbent"]["digest"] == fixtures["incumbent_checkpoint"].digest
    assert document["heldout"]["document_digest"] == heldout.document_digest_of(
        json.loads(fixtures["doc"].read_text(encoding="utf-8"))
    )
    assert document["decision"]["exit"] == "promoted"
    assert document["decision"]["denominator"] == len(_MEMBERS)
    assert document["retries_used"] == 0 and document["retry_count"] == gate.RETRY_COUNT, (
        "WHY THIS IS A FAILURE: nothing wobbled in this fixture, so no retry was spent — but "
        "the declared budget R must still be recorded. A record that reported a budget of "
        "zero would say the eval was ungoverned, which is a different run"
    )
    assert document["retries"] == [] and document["unverified_after_retries"] == []
    assert set(document["tool_versions"]) >= {"python", "whetstonehq", "mlx-lm", "platform"}


def test_the_record_reports_both_sources_with_both_denominators_disclosed(
    tmp_path: Path,
) -> None:
    """`PREREGISTRATION.md:142-147`: source A scored in full and reported beside source B.

    Both denominators are disclosed — the held-out membership's, and the public instance's —
    and coverage (denominator minus unverified) is carried per side. The public instance is
    not part of the decision; it is reported beside it.
    """
    outcome, _fixtures = _run_gate(tmp_path)
    document = json.loads(outcome.record.read_text(encoding="utf-8"))

    candidate_private = document["sides"]["candidate"]["private"]
    assert candidate_private == {
        "denominator": len(_MEMBERS),
        "solved": len(_MEMBERS),
        "unverified": 0,
        "covered": len(_MEMBERS),
        "failed": 0,
        "weaker_wins": 0,
        "status": "PASS",
    }, candidate_private

    incumbent_private = document["sides"]["incumbent"]["private"]
    assert incumbent_private["denominator"] == len(_MEMBERS)
    assert incumbent_private["solved"] == _INCUMBENT_SOLVES
    assert incumbent_private["unverified"] == 0
    assert incumbent_private["covered"] == len(_MEMBERS) - 0
    assert incumbent_private["failed"] == len(_MEMBERS) - _INCUMBENT_SOLVES
    assert incumbent_private["status"] == "FAIL"

    for side in ("candidate", "incumbent"):
        public = document["sides"][side]["public"]
        assert public["denominator"] == 1, public
        assert public["solved"] == 1, public
        assert public["unverified"] == 0 and public["covered"] == 1 and public["failed"] == 0


def test_the_gate_scores_exactly_the_membership_and_nothing_else(tmp_path: Path) -> None:
    """The survivor outside the membership is never posed, never scored, never counted.

    `t-11` is in the loaded corpus but outside the document's membership. The gate's scored
    set must be exactly the membership — a task outside it is not held out, and holding it in
    would move every count and every prompt in the record.
    """
    outcome, fixtures = _run_gate(tmp_path)

    survivor = fixtures["private_built"][-1]
    survivor_prompt = _prompted(survivor)
    for answers in fixtures["answers_generators"]:
        assert survivor_prompt not in answers, (
            "WHY THIS IS A FAILURE: the non-member task was posed. The gate scores exactly "
            "the held-out membership; a task outside it is not part of the comparison"
        )
    assert outcome.decision.denominator == len(_MEMBERS)


def test_a_known_worse_pair_is_rejected_through_the_harness(tmp_path: Path) -> None:
    """The mirror image: fewer solves through the same harness is `rejected`, not a finding."""
    outcome, _fixtures = _run_gate(
        tmp_path, candidate_solve=3, incumbent_solve=len(_MEMBERS)
    )

    assert outcome.decision.exit is Exit.REJECTED
    assert outcome.decision.solved_new == 3
    assert outcome.decision.solved_old == len(_MEMBERS)
    assert outcome.decision.regressed == len(_MEMBERS) - 3, (
        "WHY THIS IS A FAILURE: the candidate lost tasks the incumbent solved, and those "
        "losses must be counted as regressions — the never-regress conjunct"
    )
    assert outcome.decision.unverified == 0


def test_one_task_without_a_verdict_makes_the_whole_eval_unverified(tmp_path: Path) -> None:
    """`docs/ROADMAP.md:438-440` through the harness: `NO_ORACLE` reduces the whole eval.

    A twelfth task in the corpus carries an over-budget source file, so no prompt can be
    rendered for it and both sides record `NO_ORACLE` — the sibling's "reached no verdict"
    set, by identity. The decision is `UNVERIFIED` even though the candidate solved every
    task it could be scored on.
    """
    private_ids = (*_PRIVATE_IDS, "t-12")
    members = (*_MEMBERS[:9], "t-12")
    outcome, _fixtures = _run_gate(tmp_path, private_ids=private_ids, members=members, bulk=_BULK)

    assert outcome.decision.exit is Exit.UNVERIFIED, outcome.decision.detail
    assert outcome.decision.unverified == 1
    assert outcome.decision.denominator == len(members)
    assert outcome.decision.solved_new == len(members) - 1

    document = json.loads(outcome.record.read_text(encoding="utf-8"))
    assert document["decision"]["exit"] == "UNVERIFIED"
    assert document["sides"]["candidate"]["private"]["unverified"] == 1


def test_a_doctored_checkpoint_is_refused_naming_the_checkpoint(tmp_path: Path) -> None:
    """AC 2: a provenance digest mismatch refuses by name and never reaches the decision."""
    outcome, fixtures = _run_gate(tmp_path)
    assert outcome.decision.exit is Exit.PROMOTED

    tampered = fixtures["candidate_checkpoint"].directory / sft.ADAPTER_FILE
    tampered.write_bytes(b"tampered bytes")

    with pytest.raises(sft.CheckpointUnverified) as refused:
        gate.run_gate(
            candidate=fixtures["candidate_checkpoint"].directory,
            incumbent=fixtures["incumbent_checkpoint"].directory,
            heldout=fixtures["doc"],
            tasks=(tmp_path / "corpus" / "private",),
            public=tmp_path / "corpus" / "public",
            pool=tmp_path / "pool" / "pool.json",
            weights=tmp_path / "weights",
            runs=tmp_path / "runs",
            workspace=tmp_path / "work",
            timeout=TIMEOUT,
            recorded_on=RECORDED_ON,
            run_id="gate-001",
            engine=lambda _w, _c, _m: Answers({}),
        )
    assert str(tampered) in str(refused.value), (
        "WHY THIS IS A FAILURE: the refusal does not name the moved file: " + str(refused.value)
    )


def test_a_checkpoint_with_no_provenance_is_refused(tmp_path: Path) -> None:
    """Spec requirement 8: a directory that is not a night-written checkpoint is refused."""
    outcome, fixtures = _run_gate(tmp_path)
    assert outcome.decision.exit is Exit.PROMOTED

    bare = tmp_path / "bare"
    bare.mkdir()
    (bare / sft.ADAPTER_FILE).write_bytes(b"not a tensor")

    with pytest.raises(sft.CheckpointUnverified) as refused:
        gate.run_gate(
            candidate=bare,
            incumbent=fixtures["incumbent_checkpoint"].directory,
            heldout=fixtures["doc"],
            tasks=(tmp_path / "corpus" / "private",),
            public=tmp_path / "corpus" / "public",
            pool=tmp_path / "pool" / "pool.json",
            weights=tmp_path / "weights",
            runs=tmp_path / "runs",
            workspace=tmp_path / "work",
            timeout=TIMEOUT,
            recorded_on=RECORDED_ON,
            run_id="gate-001",
            engine=lambda _w, _c, _m: Answers({}),
        )
    assert str(bare) in str(refused.value), refused.value


def test_a_doctored_held_out_document_is_refused_by_name(tmp_path: Path) -> None:
    """AC 2: a hand-edited membership in an otherwise valid document is refused, not trusted.

    The doctored shape swaps the survivor (`t-11`) into the membership — ten members still,
    every loader check on shape and floors satisfied — and leaves the digest stale. Only the
    digest check can refuse it, which is the point.
    """
    outcome, fixtures = _run_gate(tmp_path)
    assert outcome.decision.exit is Exit.PROMOTED

    raw = json.loads(fixtures["doc"].read_text(encoding="utf-8"))
    raw["membership"] = [*_MEMBERS[:-1], _PRIVATE_IDS[-1]]
    fixtures["doc"].write_text(json.dumps(raw))

    with pytest.raises(heldout.HeldoutDigestMismatch) as refused:
        gate.run_gate(
            candidate=fixtures["candidate_checkpoint"].directory,
            incumbent=fixtures["incumbent_checkpoint"].directory,
            heldout=fixtures["doc"],
            tasks=(tmp_path / "corpus" / "private",),
            public=tmp_path / "corpus" / "public",
            pool=tmp_path / "pool" / "pool.json",
            weights=tmp_path / "weights",
            runs=tmp_path / "runs",
            workspace=tmp_path / "work",
            timeout=TIMEOUT,
            recorded_on=RECORDED_ON,
            run_id="gate-001",
            engine=lambda _w, _c, _m: Answers({}),
        )
    assert "document" in str(refused.value).lower(), refused.value


def test_a_held_out_set_of_zero_is_refused_never_vacuous(tmp_path: Path) -> None:
    """Spec requirement 8: an empty membership is a usage error, never a vacuous pass."""
    doc = _heldout_document(tmp_path / "doc", (), corpus_ids=_PRIVATE_IDS)

    with pytest.raises(heldout.EmptyHeldout) as refused:
        gate.run_gate(
            candidate=tmp_path / "candidate",
            incumbent=tmp_path / "incumbent",
            heldout=doc,
            tasks=(tmp_path / "corpus" / "private",),
            public=tmp_path / "corpus" / "public",
            pool=tmp_path / "pool" / "pool.json",
            weights=tmp_path / "weights",
            runs=tmp_path / "runs",
            workspace=tmp_path / "work",
            timeout=TIMEOUT,
            recorded_on=RECORDED_ON,
            run_id="gate-001",
            engine=lambda _w, _c, _m: Answers({}),
        )
    assert "empty membership" in str(refused.value), refused.value


def test_a_membership_id_matching_no_loaded_task_is_refused_with_the_ids(tmp_path: Path) -> None:
    """The `UnknownHeldoutId` posture: an id that resolves nowhere excludes nothing.

    The document is loader-valid — its own corpus carries the ghost — but the loaded private
    corpus does not, and the run-side resolution refuses by name, naming the unmatched id
    **and** the loaded ids (`heldout.exclude_heldout`, the `UnknownDevSubset` posture). Left
    alone the membership would match nothing while the record said the document was applied.
    """
    private, _built = _private_corpus(tmp_path / "corpus", _PRIVATE_IDS)
    public, _public_built = corpus(tmp_path / "corpus", "public", ("pallets__flask-4045",))
    members = (*_MEMBERS[:9], "t-ghost")
    doc = _heldout_document(tmp_path / "doc", members, corpus_ids=(*_PRIVATE_IDS, "t-ghost"))

    with pytest.raises(heldout.UnknownHeldoutId) as refused:
        gate.run_gate(
            candidate=tmp_path / "candidate",
            incumbent=tmp_path / "incumbent",
            heldout=doc,
            tasks=(private,),
            public=public,
            pool=tmp_path / "pool" / "pool.json",
            weights=tmp_path / "weights",
            runs=tmp_path / "runs",
            workspace=tmp_path / "work",
            timeout=TIMEOUT,
            recorded_on=RECORDED_ON,
            run_id="gate-001",
            engine=lambda _w, _c, _m: Answers({}),
        )
    message = str(refused.value)
    assert "t-ghost" in message and all(task_id in message for task_id in _PRIVATE_IDS), message


def test_a_checkpoint_naming_a_base_the_weights_root_does_not_hold_is_refused(
    tmp_path: Path,
) -> None:
    """Every comparison names its evidence: an unresolvable base is refused, never guessed at."""
    outcome, fixtures = _run_gate(tmp_path)
    assert outcome.decision.exit is Exit.PROMOTED

    foreign = _checkpoint(
        tmp_path / "foreign",
        repo_id="mlx-community/Some-Other-Base",
        revision="abc123",
        label="foreign",
    )

    with pytest.raises(gate.NoBaseWeights) as refused:
        gate.run_gate(
            candidate=foreign.directory,
            incumbent=fixtures["incumbent_checkpoint"].directory,
            heldout=fixtures["doc"],
            tasks=(tmp_path / "corpus" / "private",),
            public=tmp_path / "corpus" / "public",
            pool=tmp_path / "pool" / "pool.json",
            weights=tmp_path / "weights",
            runs=tmp_path / "runs",
            workspace=tmp_path / "work",
            timeout=TIMEOUT,
            recorded_on=RECORDED_ON,
            run_id="gate-001",
            engine=lambda _w, _c, _m: Answers({}),
        )
    assert "Some-Other-Base" in str(refused.value), refused.value


def test_the_runs_root_is_refused_inside_a_published_directory(tmp_path: Path) -> None:
    """The `_refuse_published_root` discipline, by identity: `reports/` is never a run home."""
    from whetstone.bakeoff.run import TranscriptNotPrivate
    from whetstone.loop.night import _refuse_published_root

    assert gate._refuse_published_root is _refuse_published_root, (
        "WHY THIS IS A FAILURE: the gate does not consume the night's refusal by identity. A "
        "second copy of 'where private evidence may live' is a second answer that can drift"
    )
    with pytest.raises(TranscriptNotPrivate):
        gate._refuse_published_root(tmp_path / "reports" / "nightly", "--runs")


def test_the_gate_composes_the_bakeoff_and_verifier_by_identity() -> None:
    """The identity rule, asserted member by member: imported, never copied.

    Each of these is a place the gate could have re-decided a definition it had no business
    re-deciding: what a checkpoint is (`verify_checkpoint`), what the held-out document is
    (`read_document`), how a rollout is scored (`score`), how per-task verdicts fold
    (`verdict.reduce`), which sampler a single draw decodes with (`sampler_for(1)`), and
    which tool versions a record is interpretable against.
    """
    from whetstone.bakeoff import scoring as bakeoff_scoring
    from whetstone.bakeoff.scoring import score as bakeoff_score
    from whetstone.loop import ledger as run_ledger
    from whetstone.loop import sampling
    from whetstone.verify import verdict

    assert gate.verify_checkpoint is sft.verify_checkpoint
    assert gate.read_document is heldout.read_document
    assert gate.exclude_heldout is heldout.exclude_heldout
    assert gate.score is bakeoff_score
    assert gate.Outcome is bakeoff_scoring.Outcome
    assert gate.verdict_reduce is verdict.reduce
    assert gate.sampler_for is sampling.sampler_for
    assert gate.tool_versions is run_ledger.tool_versions


def test_gate_engine_is_the_callable_factory_smoke_test() -> None:
    """The one new machine seam exists and is callable; it is never invoked without `mlx`.

    `mlx` is an optional extra and every test here injects a stub engine, so the factory's
    real body is exercised only by the operator's runbook. This smoke test pins that the seam
    exists and is a factory — and that merely importing the gate module loads no inference
    library.

    **Measured in a fresh interpreter, not against this process's `sys.modules`.** The
    original spelling asserted `"mlx_lm" not in sys.modules` here, which is a statement about
    everything the whole test session had imported by this point rather than about the gate.
    It passed only because the extra is absent under a plain `uv sync`; with the extra
    installed — which is exactly what the runbooks tell an operator to do — an earlier
    bake-off test imports `mlx_lm` and this assertion fails while the property it names is
    still perfectly true. A subprocess importing the gate and nothing else measures the claim
    in both configurations.
    """
    import subprocess
    import sys

    assert callable(gate.gate_engine)

    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import importlib, sys; importlib.import_module('whetstone.loop.gate'); "
            "print('mlx_lm' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert probe.stdout.strip() == "False", (
        f"WHY THIS IS A FAILURE: importing the gate loaded mlx_lm (probe said "
        f"{probe.stdout.strip()!r}). The exempt package's rule is that every mlx import is "
        "function-local inside the factory"
    )


def test_the_promotion_record_home_is_gitignored() -> None:
    """AC 4: `runs/promotions/<id>.json` must be ignored by git, asserted against git itself."""
    import subprocess

    repo_root = Path(__file__).resolve().parents[2]
    candidate = "runs/promotions/gate-001.json"
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", candidate],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"},
    )
    assert result.returncode == 0, (
        f"WHY THIS IS A FAILURE: git would track {candidate!r}. The promotion record is local "
        "evidence — digests and verdict counts over the held-out membership — and the whole "
        "locality guarantee is one .gitignore edit wide"
    )


# --------------------------------------------------------------------------------------------
# Phase 3: the retry seam. A FAIL is a verdict; only a task with no verdict is retryable.
# --------------------------------------------------------------------------------------------


def test_a_fail_task_stays_fail_through_the_gate(tmp_path: Path) -> None:
    """The seam is not credulous: a candidate's FAIL is never converted into retryable.

    The candidate loses one held-out task the incumbent solved — answering prose, so the
    rollout is `NO_DIFF`, a real verdict. The gate rejects (a regression) rather than
    reducing to UNVERIFIED, and the lost task is not marked retryable: a FAIL is a verdict,
    and only no-verdict is retryable (aspect 4 wraps exactly that set).
    """
    outcome, _fixtures = _run_gate(
        tmp_path, candidate_solve=len(_MEMBERS) - 1, incumbent_solve=len(_MEMBERS)
    )

    assert outcome.decision.exit is Exit.REJECTED, outcome.decision.detail
    assert outcome.decision.regressed == 1
    assert outcome.decision.unverified == 0, (
        "WHY THIS IS A FAILURE: a FAIL task was counted as unverified. NO_DIFF is a verdict — "
        "the candidate was scored and failed — and the whole eval must NOT reduce to UNVERIFIED"
    )
    assert outcome.decision.solved_new == len(_MEMBERS) - 1
    assert outcome.decision.solved_old == len(_MEMBERS)


def test_the_retryable_set_is_exactly_the_no_verdict_tasks_with_their_first_attempt_hashes(
    tmp_path: Path,
) -> None:
    """The seam aspect 4 wraps: no-verdict tasks, named, with the evidence the attempt ran.

    With one `NO_ORACLE` task, exactly that task is retryable — and no FAIL (NO_DIFF) task
    is. The candidate deliberately fails four held-out tasks (prose answers → NO_DIFF) while
    a fifth is NO_ORACLE: the retryable set must contain only the NO_ORACLE task.
    """
    private_ids = (*_PRIVATE_IDS, "t-12")
    members = (*_MEMBERS[:9], "t-12")
    outcome, _fixtures = _run_gate(
        tmp_path,
        private_ids=private_ids,
        members=members,
        bulk=_BULK,
        candidate_solve=5,
        incumbent_solve=9,
    )

    retryable = {one.task_id: one for one in outcome.retryable}
    assert set(retryable) == {"t-12"}, (
        f"WHY THIS IS A FAILURE: the retryable set is {sorted(retryable)!r}. The four "
        "NO_DIFF tasks carry real verdicts — a FAIL is a verdict, never retryable — and the "
        "NO_ORACLE task is the only no-verdict one"
    )
    marker = retryable["t-12"]
    assert marker.outcome is Outcome.NO_ORACLE
    assert marker.prompt_sha256 == "" and marker.completion_sha256 == "", (
        "WHY THIS IS A FAILURE: a NO_ORACLE task carries a prompt or completion hash. No "
        "prompt was ever rendered for it, so there is no first attempt to record"
    )
    assert all(one.outcome is not Outcome.NO_DIFF for one in outcome.retryable), (
        "WHY THIS IS A FAILURE: a FAIL task was marked retryable. A FAIL is a verdict — only "
        "no-verdict is retryable, and aspect 4 wraps exactly that set"
    )
