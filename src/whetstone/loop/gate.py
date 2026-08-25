"""The never-regress promotion gate: score two checkpoints, decide with the roadmap's rule.

`docs/ROADMAP.md:420-427` fixes the gate's verdict before this module existed:

    promote iff  solved_new > solved_old
            AND  regressed  == 0
            AND  unverified == 0

Three exits only: `promoted` / `rejected` / `UNVERIFIED`. This module is the door
`whetstone gate --candidate X --incumbent Y --heldout <doc>` stands behind, and it is
composition only: every honesty control it relies on was built and tested somewhere else and
is used here by identity.

- **Checkpoints** are re-hashed on both sides through `loop.sft.verify_checkpoint` before
  anything compares — the bytes the decision names are the bytes on disk, or the run refuses
  (`CheckpointUnverified`, naming the checkpoint).
- **The held-out source-B split** is consumed through aspect 1's fail-closed loader
  (`loop.heldout.read_document`); its digest is recomputed from the payload the loader
  accepted. A held-out set of zero is refused by name — the gate never scores a vacuous set.
- **Scoring** composes `bakeoff.scoring.score` (the bake-off's own loop: prompt render →
  generate → extract → apply → STRICT verify), with the greedy sampler `sampling.sampler_for(1)`
  by identity, so a single-draw gate eval and the bake-off are one experiment.
- **The per-task verdict** is folded through `verify.verdict.reduce` (worst-status-wins,
  UNVERIFIED above PASS) — imported by identity, never re-decided.
- **The single definition of solved** is `Outcome.SOLVED` (`report.tally`'s member, the same
  one the loop's trainable partition imports), and **the single definition of "reached no
  verdict"** is `report._UNCOVERED` (UNVERIFIED, UNPROVISIONED, NO_ORACLE) — imported by
  identity, so the gate's counts cannot drift from the coverage figures every published
  document reduces against.

**The one new machine seam is `gate_engine`.** Nothing else in the tree loads a checkpoint
(base + LoRA adapter) at all; the bake-off's engine and the loop's take `Weights` only. It is
exercised in tests only through the seam — every test injects a stub — and its smoke test
asserts the factory exists and is callable without importing `mlx`.

**Locality, in the `runs/` discipline.** The promotion record is written to
`runs/promotions/<id>.json` — gitignored local evidence, never published — and the runs root
is refused inside a `reports/` directory. `recorded_on` is an input, never the clock, like
every other dated field in this repository.

**No retry mechanism lives here** (aspect 4 wraps the per-task scoring seam); but the
decision core's `unverified` term is that seam, and the gate already refuses to convert a
FAIL into anything else — a FAIL is a verdict, and only a task with no verdict is retryable.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from whetstone.bakeoff import report as bakeoff_report
from whetstone.bakeoff.generator import Generator
from whetstone.bakeoff.mlx_runtime import DEFAULT_MAX_TOKENS
from whetstone.bakeoff.rendering import prompt_hash
from whetstone.bakeoff.run import HF_HUB_OFFLINE, TranscriptNotPrivate, load_task_roots
from whetstone.bakeoff.scoring import Interpreters, Outcome, Rollout, score
from whetstone.bakeoff.weights import (
    ProvenanceUnreadable,
    Weights,
    WeightsUnverified,
    load_weights,
)
from whetstone.loop.heldout import (
    EmptyHeldout,
    HeldoutDigestMismatch,
    HeldoutSchemaError,
    UnknownHeldoutId,
    document_digest_of,
    exclude_heldout,
    read_document,
)
from whetstone.loop.ledger import tool_versions
from whetstone.loop.night import _refuse_published_root
from whetstone.loop.sampling import sampler_for
from whetstone.loop.sft import Checkpoint, CheckpointUnverified, verify_checkpoint
from whetstone.tasks.manifest import load_tasks
from whetstone.verify.task import Task
from whetstone.verify.verdict import Status, Verdict
from whetstone.verify.verdict import reduce as verdict_reduce

#: The outcomes that mean no verdict was reached — the sibling's own set, imported by
#: identity (`report._UNCOVERED`), so the gate's "unverified" term cannot drift from the
#: coverage definition every published count reduces against. They lower coverage and stay
#: in the denominator; they never vanish from it.
_UNCOVERED = bakeoff_report._UNCOVERED

#: The promotion record's own schema string, checked on read by nobody yet — the record is
#: written, never read back by this module — and named so a later reader has one answer to
#: "what shape is this file".
PROMOTION_SCHEMA = "whetstone-promotion/1"

#: The directory under `--runs` the promotion records live in.
PROMOTIONS_DIR = "promotions"

#: The declared retry budget `R` (aspect 4's constant). Recorded as 0 until that aspect
#: lands: nothing retries yet, and a number must not appear before the mechanism that
#: grounds it exists. The value is revisable only by a § 7.2 amendment, never a CLI knob.
RETRY_COUNT = 0


class Exit(str, Enum):
    """The three exits the roadmap allows. `str` mixin so an exit serialises as its name.

    Spelled exactly as the roadmap spells them: `promoted` / `rejected` / `UNVERIFIED`.
    `UNVERIFIED` is a third outcome, never a promotion and never a rejection — no comparison
    was actually made.
    """

    PROMOTED = "promoted"
    REJECTED = "rejected"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True)
class GateDecision:
    """The rule's verdict over one comparison, with every count that grounds it.

    All counts are over the **shared denominator**: the task set both sides were scored on.
    A task either side failed to reach a verdict on is excluded from the solved and
    regression counts — no comparison was made on it — and counted in `unverified` instead,
    which is what reduces the whole evaluation to `UNVERIFIED`.
    """

    #: Exactly one of the three exits.
    exit: Exit

    #: The shared denominator the counts are over.
    denominator: int

    #: Tasks the candidate solved (both sides had verdicts).
    solved_new: int

    #: Tasks the incumbent solved (both sides had verdicts).
    solved_old: int

    #: Tasks the incumbent solved and the candidate did not — the never-regress conjunct.
    regressed: int

    #: Tasks either side reached no verdict on (the sibling's `_UNCOVERED` set).
    unverified: int

    #: A sentence stating the decision and the counts it was read from.
    detail: str


def decide(
    candidate: Mapping[str, Outcome],
    incumbent: Mapping[str, Outcome],
) -> GateDecision:
    """The roadmap rule, as a pure function of two per-task outcome maps.

    The maps are over the held-out membership; `decide` itself does not know or care which
    document produced them. It refuses a mismatch between the two task sets — a task scored
    on one side alone is a task one checkpoint was never asked about, and a decision over
    the overlap would read as a full comparison.

    The rule verbatim (`docs/ROADMAP.md:420-427`), with `unverified` read as "no verdict was
    reached on either side", using the sibling's own `_UNCOVERED` definition:

    * any unverified task → the whole evaluation is `UNVERIFIED` (not promoted and not
      rejected, because no comparison was actually made, `docs/ROADMAP.md:438-440`);
    * otherwise `solved_new > solved_old AND regressed == 0` → `promoted`;
    * anything else — including equal solved counts, by the `>` term — → `rejected`.
    """
    if set(candidate) != set(incumbent):
        raise ValueError(
            "the candidate and incumbent were scored over different task sets: "
            f"candidate-only={sorted(set(candidate) - set(incumbent))!r}, "
            f"incumbent-only={sorted(set(incumbent) - set(candidate))!r}. Both sides must be "
            "scored over the same held-out membership, or no comparison was actually made"
        )

    denominator = sorted(candidate)
    solved_new = 0
    solved_old = 0
    regressed = 0
    unverified = 0
    for task_id in denominator:
        candidate_outcome = candidate[task_id]
        incumbent_outcome = incumbent[task_id]
        if candidate_outcome in _UNCOVERED or incumbent_outcome in _UNCOVERED:
            unverified += 1
            continue
        if candidate_outcome is Outcome.SOLVED:
            solved_new += 1
        if incumbent_outcome is Outcome.SOLVED:
            solved_old += 1
        if incumbent_outcome is Outcome.SOLVED and candidate_outcome is not Outcome.SOLVED:
            regressed += 1

    if unverified:
        exit_ = Exit.UNVERIFIED
    elif solved_new > solved_old and regressed == 0:
        exit_ = Exit.PROMOTED
    else:
        exit_ = Exit.REJECTED
    return GateDecision(
        exit=exit_,
        denominator=len(denominator),
        solved_new=solved_new,
        solved_old=solved_old,
        regressed=regressed,
        unverified=unverified,
        detail=_sentence(exit_, solved_new, solved_old, regressed, unverified, len(denominator)),
    )


def _sentence(
    exit_: Exit,
    solved_new: int,
    solved_old: int,
    regressed: int,
    unverified: int,
    denominator: int,
) -> str:
    """One sentence stating the decision and the counts it was read from.

    A reader of the promotion record must be able to check the decision against the counts
    in the same document, without reopening the code that made it.
    """
    if exit_ is Exit.UNVERIFIED:
        return (
            f"{unverified} of {denominator} tasks reached no verdict, so no comparison was "
            "actually made and the whole evaluation reduces to UNVERIFIED — not promoted and "
            "not rejected"
        )
    comparison = (
        f"solved_new ({solved_new}) > solved_old ({solved_old})"
        if solved_new > solved_old
        else f"solved_new ({solved_new}) is not greater than solved_old ({solved_old})"
    )
    regressions = f"with {regressed} regression(s)" if regressed else "with no regressions"
    return f"{comparison}, {regressions}, {unverified} unverified over {denominator} tasks"


# --------------------------------------------------------------------------------------------
# Scoring: run_gate, the record, and the refusals an operator can fix by retyping a command.
# --------------------------------------------------------------------------------------------


class NoBaseWeights(ValueError):
    """The weights root holds no candidate matching the base a checkpoint names.

    A checkpoint's provenance names the base it was trained on; the gate loads that base and
    stacks the checkpoint's LoRA adapter on it. A base the weights provenance cannot identify
    is a checkpoint nobody can score — refused rather than guessed at, because guessing would
    score the adapter against the wrong model and publish the result as a comparison.
    """


#: Every refusal `run_gate` raises that is an **operator's error** rather than a finding: a
#: runs root pointed at a published directory, a checkpoint that cannot be re-hashed, a
#: held-out document that cannot be read or whose membership resolves nowhere, a checkpoint
#: naming a base the weights root does not hold, weights whose provenance does not match the
#: disk, and a task root that is empty or malformed. Collected here so `cli.py` — a guarded
#: root, which may hold exactly its documented function-local imports into this package —
#: can map them to the usage code without importing the modules that raise them.
REFUSALS: tuple[type[Exception], ...] = (
    TranscriptNotPrivate,
    CheckpointUnverified,
    HeldoutSchemaError,
    HeldoutDigestMismatch,
    EmptyHeldout,
    UnknownHeldoutId,
    NoBaseWeights,
    ProvenanceUnreadable,
    WeightsUnverified,
    ValueError,
)

#: How the gate's one new machine seam is shaped: a checkpoint's base weights and the
#: checkpoint itself, to a `Generator`. The night's engine takes `Weights` only; a gate
#: engine must also know which adapter to stack on them.
GateEngine = Callable[[Weights, Checkpoint, int], Generator]


@dataclass(frozen=True)
class SideCounts:
    """One checkpoint's counts over one source, over that source's own denominator.

    `covered` is the sibling rule's coverage — denominator minus unverified — and unverified
    tasks **stay in the denominator**: coverage is reported, never silently excluded
    (`docs/ROADMAP.md:539`).
    """

    #: Tasks scored for this source.
    denominator: int

    #: Tasks that reached `Outcome.SOLVED` — the one definition, by identity.
    solved: int

    #: Tasks that reached no verdict (the sibling's `_UNCOVERED` set, by identity).
    unverified: int

    #: `denominator - unverified` — what was actually graded.
    covered: int

    #: `denominator - unverified - solved` — graded and not solved.
    failed: int

    #: The side's reduced status over this source, folded through `verdict.reduce`
    #: (worst-status-wins, UNVERIFIED above PASS — the honesty contract, by identity).
    status: Status


@dataclass(frozen=True)
class Side:
    """One checkpoint's counts over both sources. Both always present, both denominators open."""

    #: Source B: the held-out membership this eval decides over.
    private: SideCounts

    #: Source A: the public instance(s), scored in full and reported beside source B.
    public: SideCounts


@dataclass(frozen=True)
class Retryable:
    """A task no verdict was reached on, with the evidence the first attempt ran.

    The seam aspect 4's deterministic retry wraps: each of these is re-posed `R` times with
    identical seed and inputs, and a task that verifies on retry is verified. `outcome`
    names which kind of no-verdict it is; `prompt_sha256` and `completion_sha256` are empty
    for a task no prompt was ever rendered for (`UNPROVISIONED`, `NO_ORACLE`) — there is
    nothing to re-pose, and only a task that has a prompt (a bare `UNVERIFIED` from the
    verifier) can be retried into a verdict.
    """

    #: Which side this was scored on ("candidate" or "incumbent").
    side: str

    #: The task's own id.
    task_id: str

    #: Which no-verdict outcome it was.
    outcome: Outcome

    #: SHA-256 of the exact prompt the first attempt was shown, or empty if none was rendered.
    prompt_sha256: str

    #: SHA-256 of the first attempt's completion, or empty if none was generated.
    completion_sha256: str


@dataclass(frozen=True)
class GateOutcome:
    """What one gate run decided, and the evidence it decided on — never a bare exit."""

    #: The roadmap rule's verdict over the held-out membership.
    decision: GateDecision

    #: The candidate's re-hashed digest.
    candidate_digest: str

    #: The incumbent's re-hashed digest.
    incumbent_digest: str

    #: The held-out document's digest, recomputed from the payload the loader accepted.
    heldout_digest: str

    #: The candidate's counts over both sources.
    candidate: Side

    #: The incumbent's counts over both sources.
    incumbent: Side

    #: The written promotion record.
    record: Path

    #: Every (side, task) that reached no verdict — the set aspect 4's retry discipline wraps.
    retryable: tuple[Retryable, ...]


def gate_engine(
    weights: Weights, checkpoint: Checkpoint, max_tokens: int = DEFAULT_MAX_TOKENS
) -> Generator:
    """Load `checkpoint`'s LoRA adapter onto `weights`' base and return a greedy `Generator`.

    The one new machine seam in this unit: nothing else in the tree loads a checkpoint at
    all — the bake-off's `MlxGenerator` and the loop's `SampledMlxGenerator` take `Weights`
    only. The base is loaded from `weights.local_dir` (never a repo id) at the revision the
    checkpoint's own provenance names, the adapter is stacked from the checkpoint directory
    (`adapters.safetensors` + `adapter_config.json`, both re-hashed by `verify_checkpoint`
    before this is ever called), and decoding is greedy — `sampler_for(1)` is
    `greedy_sampler` **by identity**, so a single-draw gate eval and the bake-off are one
    experiment.

    Every `mlx` import is function-local, on the loop package's own rule. The factory is
    never invoked by the test suite (`mlx` is an optional extra CI does not install), so its
    correctness is pinned by the smoke test and by the operator's runbook, not by CI.
    """
    from mlx_lm.generate import generate
    from mlx_lm.utils import load as load_model

    model, tokenizer = load_model(
        str(weights.local_dir),
        revision=weights.revision,
        adapter_path=str(checkpoint.directory),
    )
    return _CheckpointGenerator(
        model,
        tokenizer,
        generate=generate,
        max_tokens=max_tokens,
        sampler=sampler_for(1),
    )


class _CheckpointGenerator:
    """A base with a checkpoint's LoRA adapter stacked on it, decoding greedily.

    The `Generator` the gate's real engine returns, in the shape `SampledMlxGenerator`
    established: everything that decides what is generated is fixed at construction, the
    sampler is the one `sampler_for(1)` returns (greedy, by identity), and a non-string
    answer raises rather than being coerced into a repr that holds no diff.
    """

    def __init__(
        self,
        model: Any,
        tokenizer: Any,
        *,
        generate: Callable[..., Any],
        max_tokens: int,
        sampler: Any,
    ) -> None:
        self._model = model
        self._tokenizer = tokenizer
        self._generate = generate
        self._max_tokens = max_tokens
        self._sampler = sampler

    def generate(self, prompt: str) -> str:
        answer = self._generate(
            self._model,
            self._tokenizer,
            prompt,
            max_tokens=self._max_tokens,
            sampler=self._sampler,
        )
        if not isinstance(answer, str):
            raise TypeError(
                f"mlx_lm.generate.generate returned {type(answer).__name__}, not str. "
                "Coercing it here would hand the extractor a repr, which holds no diff"
            )
        return answer


def run_gate(
    *,
    candidate: Path,
    incumbent: Path,
    heldout: Path,
    tasks: Sequence[Path],
    public: Path,
    pool: Path,
    weights: Path,
    runs: Path,
    workspace: Path,
    timeout: float,
    recorded_on: str,
    run_id: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    engine: GateEngine = gate_engine,
) -> GateOutcome:
    """Score two checkpoints on the held-out membership and return the roadmap's verdict.

    The order below is the design, and it is the same order every arm in this repository
    uses: private roots are refused first, before anything is loaded; the pinned input (the
    held-out document) is validated before the bytes it decides over; both checkpoints are
    re-hashed before anything compares; the base weights are verified and resolved from each
    checkpoint's own provenance; and only then is a token generated.

    `engine` is the machine seam — `gate_engine` for a real run, a stub in every test. It
    receives the **verified** checkpoint, so scoring always runs under the re-hashed bytes.

    `recorded_on` is an input, never the clock, and `run_id` names the promotion record's
    file — both for the arms' rule: a record that dated or named itself would differ between
    two renders of the same documented command.
    """
    _refuse_published_root(runs, "--runs")
    os.environ[HF_HUB_OFFLINE] = "1"

    heldout_document = read_document(heldout)
    heldout_digest = document_digest_of(json.loads(Path(heldout).read_text(encoding="utf-8")))

    private_tasks = load_task_roots(tasks)
    public_tasks = load_tasks(public)
    heldout_tasks = _heldout_tasks(heldout_document.membership, private_tasks)

    candidate_checkpoint = verify_checkpoint(candidate)
    incumbent_checkpoint = verify_checkpoint(incumbent)

    fetched = load_weights(weights)
    candidate_base = _base_for(candidate_checkpoint, fetched, "candidate")
    incumbent_base = _base_for(incumbent_checkpoint, fetched, "incumbent")

    candidate_recorder = _CompletionRecorder(
        engine(candidate_base, candidate_checkpoint, max_tokens)
    )
    incumbent_recorder = _CompletionRecorder(
        engine(incumbent_base, incumbent_checkpoint, max_tokens)
    )

    interpreters = Interpreters(workspace=workspace / "environments")
    sandbox_root = workspace / "sandbox"

    candidate_rollouts = _score_side(
        label=f"candidate:{candidate_checkpoint.digest[:12]}",
        tasks=(*heldout_tasks, *public_tasks),
        generator=candidate_recorder,
        sandbox_root=sandbox_root,
        timeout=timeout,
        interpreters=interpreters,
        pool=pool,
    )
    incumbent_rollouts = _score_side(
        label=f"incumbent:{incumbent_checkpoint.digest[:12]}",
        tasks=(*heldout_tasks, *public_tasks),
        generator=incumbent_recorder,
        sandbox_root=sandbox_root,
        timeout=timeout,
        interpreters=interpreters,
        pool=pool,
    )

    decision = decide(
        _outcome_map(candidate_rollouts, heldout_tasks),
        _outcome_map(incumbent_rollouts, heldout_tasks),
    )
    candidate_side = Side(
        private=_counts(candidate_rollouts, heldout_tasks),
        public=_counts(candidate_rollouts, public_tasks),
    )
    incumbent_side = Side(
        private=_counts(incumbent_rollouts, heldout_tasks),
        public=_counts(incumbent_rollouts, public_tasks),
    )
    retryable = (
        *_retryable("candidate", candidate_recorder, candidate_rollouts, heldout_tasks),
        *_retryable("incumbent", incumbent_recorder, incumbent_rollouts, heldout_tasks),
    )

    record = write_promotion_record(
        path=runs / PROMOTIONS_DIR / f"{run_id}.json",
        run_id=run_id,
        recorded_on=recorded_on,
        candidate_digest=candidate_checkpoint.digest,
        incumbent_digest=incumbent_checkpoint.digest,
        heldout_digest=heldout_digest,
        candidate=candidate_side,
        incumbent=incumbent_side,
        decision=decision,
        retries_used=0,
        retry_count=RETRY_COUNT,
        tool_versions=tool_versions(),
    )
    return GateOutcome(
        decision=decision,
        candidate_digest=candidate_checkpoint.digest,
        incumbent_digest=incumbent_checkpoint.digest,
        heldout_digest=heldout_digest,
        candidate=candidate_side,
        incumbent=incumbent_side,
        record=record,
        retryable=retryable,
    )


def disclosure(outcome: GateOutcome) -> tuple[str, ...]:
    """The lines `whetstone gate` prints: the exit, both sides over both sources, the record.

    Every count carries its denominator (`PREREGISTRATION.md:157`), coverage is stated per
    side (`docs/ROADMAP.md:539`), and source A is reported beside source B, never alone
    (`PREREGISTRATION.md:142-147`). The digests are abbreviated to twelve characters —
    enough to match the record and the checkpoints on disk, and the record itself carries
    the full values.
    """
    return (
        f"decision: {outcome.decision.exit.value} — {outcome.decision.detail}",
        _side_line("candidate", outcome.candidate_digest, outcome.candidate),
        _side_line("incumbent", outcome.incumbent_digest, outcome.incumbent),
        f"held-out document: {outcome.heldout_digest[:12]}",
        f"record: {outcome.record}",
    )


def write_promotion_record(
    *,
    path: Path,
    run_id: str,
    recorded_on: str,
    candidate_digest: str,
    incumbent_digest: str,
    heldout_digest: str,
    candidate: Side,
    incumbent: Side,
    decision: GateDecision,
    retries_used: int,
    retry_count: int,
    tool_versions: Mapping[str, str],
) -> Path:
    """Write the promotion record — schema `whetstone-promotion/1` — deterministically.

    The record is local evidence, never published: the digests (re-hashed), the held-out
    document's digest, both sides' counts over both denominators, the decision with every
    count it was read from, the retry fields (0 until aspect 4 lands), the tool versions,
    and `recorded_on` — an input, never the clock.
    """
    document = {
        "schema": PROMOTION_SCHEMA,
        "run_id": run_id,
        "recorded_on": recorded_on,
        "candidate": {"digest": candidate_digest},
        "incumbent": {"digest": incumbent_digest},
        "heldout": {"document_digest": heldout_digest},
        "sides": {
            "candidate": _side_payload(candidate),
            "incumbent": _side_payload(incumbent),
        },
        "decision": {
            "exit": decision.exit.value,
            "denominator": decision.denominator,
            "solved_new": decision.solved_new,
            "solved_old": decision.solved_old,
            "regressed": decision.regressed,
            "unverified": decision.unverified,
            "detail": decision.detail,
        },
        "retries_used": retries_used,
        "retry_count": retry_count,
        "tool_versions": dict(sorted(tool_versions.items())),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


class _CompletionRecorder:
    """Wraps a side's generator and keeps the first-attempt completion hash per prompt.

    The retry discipline (aspect 4) re-poses with identical seed and inputs; the recorded
    hash is the evidence that the first attempt ran and what it produced. Keyed by the
    rendered prompt's own hash — the same value `scoring.score` records on the rollout — so
    a rollout and its completion can be matched without a second definition of "which
    question this was".
    """

    def __init__(self, inner: Generator) -> None:
        self._inner = inner
        self._completions: dict[str, str] = {}

    def generate(self, prompt: str) -> str:
        completion = self._inner.generate(prompt)
        self._completions[prompt_hash(prompt)] = hashlib.sha256(
            completion.encode("utf-8")
        ).hexdigest()
        return completion

    def completion_sha256(self, prompt_sha256: str) -> str:
        """The recorded first-attempt hash for a rendered prompt, or empty if none was rendered."""
        return self._completions.get(prompt_sha256, "")


def _retryable(
    side: str,
    recorder: _CompletionRecorder,
    rollouts: Sequence[Rollout],
    tasks: Sequence[Task],
) -> tuple[Retryable, ...]:
    """Every (side, task) that reached no verdict, with the first attempt's evidence.

    A FAIL is a verdict and is never here — only outcomes in the sibling's `_UNCOVERED` set
    are retryable, and aspect 4 wraps exactly this tuple. A task no prompt was rendered for
    (`UNPROVISIONED`, `NO_ORACLE`) carries empty hashes: there is nothing to re-pose.
    """
    by_task = {record.task_id: record for record in rollouts}
    markers: list[Retryable] = []
    for task in tasks:
        record = by_task[task.task_id]
        if record.outcome not in _UNCOVERED:
            continue
        markers.append(
            Retryable(
                side=side,
                task_id=task.task_id,
                outcome=record.outcome,
                prompt_sha256=record.prompt_sha256,
                completion_sha256=recorder.completion_sha256(record.prompt_sha256),
            )
        )
    return tuple(markers)


def _heldout_tasks(membership: Sequence[str], tasks: Sequence[Task]) -> tuple[Task, ...]:
    """The scored source-B set: the loaded tasks whose ids the membership names.

    The unknown-id refusal is the loader's run-side half, applied **by identity**
    (`heldout.exclude_heldout`): a membership id that matches no loaded private task is
    refused, naming the id and the loaded ids — the `UnknownDevSubset` posture. The empty
    case cannot arise after that: the loader already refused an empty membership, and the
    exclusion proves every member resolves.
    """
    exclude_heldout(membership, tasks)
    members = set(membership)
    return tuple(task for task in tasks if task.task_id in members)


def _base_for(checkpoint: Checkpoint, fetched: Sequence[Weights], label: str) -> Weights:
    """The base a checkpoint names, resolved against the verified weights provenance."""
    base = _checkpoint_base(checkpoint)
    for weights in fetched:
        if weights.repo_id == base["repo_id"] and weights.revision == base["revision"]:
            return weights
    raise NoBaseWeights(
        f"checkpoint {label} ({str(checkpoint.directory)!r}) names base {base['repo_id']!r} "
        f"at revision {base['revision']!r}, and the weights root holds no such candidate. "
        "The gate loads the base under a checkpoint's LoRA adapter, and a base the "
        "provenance cannot identify is a checkpoint nobody can score"
    )


def _checkpoint_base(checkpoint: Checkpoint) -> Mapping[str, str]:
    """The base a checkpoint's provenance names — read after `verify_checkpoint` accepted it."""
    document: Any = json.loads(
        (checkpoint.directory / "provenance.json").read_text(encoding="utf-8")
    )
    base = document["base"]
    return {"repo_id": str(base["repo_id"]), "revision": str(base["revision"])}


def _score_side(
    *,
    label: str,
    tasks: Sequence[Task],
    generator: Generator,
    sandbox_root: Path,
    timeout: float,
    interpreters: Interpreters,
    pool: Path | None,
) -> tuple[Rollout, ...]:
    """Score every task with one generator — the bake-off's own `score`, by identity."""
    return tuple(
        score(
            candidate=label,
            task=task,
            generator=generator,
            sandbox_root=sandbox_root,
            timeout=timeout,
            interpreters=interpreters,
            pool=pool,
        )
        for task in tasks
    )


def _outcome_map(rollouts: Sequence[Rollout], tasks: Sequence[Task]) -> dict[str, Outcome]:
    """One outcome per task, for the pure decision core."""
    by_task = {record.task_id: record.outcome for record in rollouts}
    return {task.task_id: by_task[task.task_id] for task in tasks}


def _counts(rollouts: Sequence[Rollout], tasks: Sequence[Task]) -> SideCounts:
    """One side's counts over one source, using the one definitions of solved and unverified."""
    by_task = {record.task_id: record for record in rollouts}
    records = [by_task[task.task_id] for task in tasks]
    denominator = len(records)
    solved = sum(1 for record in records if record.outcome is Outcome.SOLVED)
    unverified = sum(1 for record in records if record.outcome in _UNCOVERED)
    return SideCounts(
        denominator=denominator,
        solved=solved,
        unverified=unverified,
        covered=denominator - unverified,
        failed=denominator - unverified - solved,
        status=_status_of(records),
    )


def _status_of(records: Sequence[Rollout]) -> Status:
    """One side's reduced status over its records, folded through `verdict.reduce` by identity.

    Each task contributes one `Verdict` whose status is derived from its outcome: `PASS` for
    a solve, `FAIL` for any graded zero, `UNVERIFIED` for the no-verdict set. Reducing with
    the one reduce keeps the honesty contract — UNVERIFIED above PASS — at the status level
    the record reports.
    """
    verdicts = [
        Verdict(
            kind="task",
            status=_verdict_status(record.outcome),
            observed=record.task_id,
            expected=None,
            message=f"{record.task_id} reduced to {_verdict_status(record.outcome).value}",
        )
        for record in records
    ]
    return verdict_reduce(verdicts)


def _verdict_status(outcome: Outcome) -> Status:
    """The status a single outcome folds into a side's reduction."""
    if outcome in _UNCOVERED:
        return Status.UNVERIFIED
    if outcome is Outcome.SOLVED:
        return Status.PASS
    return Status.FAIL


def _side_payload(side: Side) -> Mapping[str, Any]:
    """One side as plain JSON types."""
    return {
        "private": _counts_payload(side.private),
        "public": _counts_payload(side.public),
    }


def _counts_payload(counts: SideCounts) -> Mapping[str, Any]:
    """One source's counts as plain JSON types."""
    return {
        "denominator": counts.denominator,
        "solved": counts.solved,
        "unverified": counts.unverified,
        "covered": counts.covered,
        "failed": counts.failed,
        "status": counts.status.value,
    }


def _side_line(label: str, digest: str, side: Side) -> str:
    """One side's disclosure line: both sources, every count over its denominator."""
    private = side.private
    public = side.public
    return (
        f"{label} {digest[:12]}: source B (held-out) {private.solved} solved of "
        f"{private.denominator}, {private.unverified} unverified of {private.denominator}, "
        f"coverage {private.covered} of {private.denominator}; source A (public) "
        f"{public.solved} solved of {public.denominator}, {public.unverified} unverified of "
        f"{public.denominator}, coverage {public.covered} of {public.denominator}"
    )


__all__ = [
    "Exit",
    "GateDecision",
    "Retryable",
    "decide",
]