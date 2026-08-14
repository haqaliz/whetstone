"""The operator entry point: three bases, two sources, one night, and no way to move the question.

Every other module in this package has a narrow claim and is tested against it. This one composes
them into a run, and composition is where the honesty controls either hold or quietly do not —
each of them lives in a seam between two modules that are individually correct.

**It is `python -m whetstone.bakeoff.run` and deliberately not a `whetstone` subcommand.**
`src/whetstone/cli.py` is a guarded root (`tests/test_no_inference_on_reward_path.py:107`): it is
the reward's entry point, it calls `verify_strict`, and nothing it imports may reach an inference
library. A `whetstone bakeoff` subcommand would put `mlx_lm` one transitive import from the reward
path while every guard in this repository stayed green, because the ban names inference-shaped
module names and neither `bakeoff` nor `run` is one. The cost of the separate entry point is one
longer command in a runbook; the cost of the subcommand is the project's central claim.

**The generation contract is frozen before the first scored result, and the seal is structural.**
PRD M7b fixes the prompt and the extractor before the run and invalidates any run they move
during. The temptation that guards against is the strongest one in P1: a disappointing number
reads exactly like evidence that the prompt was wrong, and after the fact the two are
indistinguishable unless something refused to let them mix. So the contract is not a flag anybody
sets. It is frozen as **the set of prompt digests the declared template produces over the scored
set**, computed before any engine exists, and every base is handed to `sweep` wrapped in a `Sealed`
that will not pass on a prompt whose digest is not in that set. Editing the template mid-run does
not produce a footnote; it produces an abort, before the base is asked anything.

**The probe (D7) publishes cost and refuses to publish counts.** The verifier half of this run is
unmeasured, so a sample is timed before the full matrix is committed to. What makes that safe is
what the sample is *allowed to emit*: seconds, and the harness's own status. Had it emitted solved
counts, the operator would be choosing the scored set's size while looking at partial results from
it — which is the act M7b forbids one layer up, performed on the denominator instead of the
prompt. Note the word collision, since both senses are the PRD's: `control.probe` is the control
arm, run on every task; `--probe N` is D7's timing sample. This module runs the first inside the
second and never confuses them, because one is a `Probe` and the other is an `int`.

**Nothing here decides what a patch earns.** It loads weights, freezes a question, hands both to
`sweep`, and renders what `report` derives. The verdict is `whetstone.verify`'s, taken by
re-executing the task's own tests in a sandbox, and no line of this file participates in it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import resource
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from whetstone import __version__
from whetstone.bakeoff import patch as extraction
from whetstone.bakeoff.diffcheck import Trigger, diagnosis_vocabulary_sha256
from whetstone.bakeoff.generator import Generator
from whetstone.bakeoff.journal import Journal
from whetstone.bakeoff.mlx_runtime import DEFAULT_MAX_TOKENS, PINNED_MLX_LM, SAMPLER, MlxGenerator
from whetstone.bakeoff.rendering import prompt_hash, render_prompt
from whetstone.bakeoff.report import (
    Entrant,
    GenerationContract,
    Provenance,
    Report,
    build_report,
    funnel_from_ledger,
    write,
)
from whetstone.bakeoff.retry import RETRY_BUDGET, Retry, retry_prompt, retry_template_sha256
from whetstone.bakeoff.scoring import Interpreters, Rollout
from whetstone.bakeoff.selection import Contender
from whetstone.bakeoff.sources import oracle_sources
from whetstone.bakeoff.stratum import (
    EmptyStratum,
    StratumDigestMismatch,
    StratumSchemaError,
    UnknownStratumId,
    include_stratum,
    read_document,
)
from whetstone.bakeoff.sweep import Sweep, rankable, sweep
from whetstone.bakeoff.transcript import RecordingGenerator, Transcript
from whetstone.bakeoff.weights import Weights, load_weights
from whetstone.tasks.manifest import load_tasks
from whetstone.verify.task import Task
from whetstone.verify.verdict import Status

#: The scored run's document, as `report.write` names it. Repeated here as a constant because
#: this module asserts its own absence — a refused run must leave nothing behind — and a literal
#: spelled twice is a literal that can disagree with itself.
REPORT_FILE = "report.md"

#: Where the measured wall-clock and peak memory go (AC5, AC8). A sidecar rather than a section of
#: `report.md`, because `build_report` is a pure function of counts and provenance and threading a
#: stopwatch through it would make the document depend on how fast the machine was that night.
COST_FILE = "cost.json"

#: Where `--probe N` writes what it measured. A different filename from `COST_FILE` on purpose: a
#: probe and a scored run must not be able to overwrite one another, and a reader who finds only
#: this file must be unable to mistake it for a measurement.
PROBE_FILE = "probe.json"

#: The environment variable that turns a mistyped path into a raise instead of a download.
#: `mlx_lm.utils.load` treats anything that is not an existing directory as a HuggingFace repo id
#: and fetches it at call time; with this set, that fetch raises `LocalEntryNotFoundError` instead.
#: Set for the whole scored run rather than around the load, because the verifier's own
#: subprocesses inherit this process's environment and none of them has any business downloading.
HF_HUB_OFFLINE = "HF_HUB_OFFLINE"

#: How a candidate's name becomes a directory name. Repo ids carry a slash, which would silently
#: create an `mlx-community/` level inside the workspace and make two candidates from two orgs
#: with the same model name collide.
_SEPARATOR = "__"

#: Reads the declared parameter count out of a repository name — `…-3B-Instruct-4bit` → `3.0`.
#: Upper-case `B` only, so the `4bit` quantisation suffix is not mistaken for a size, and anchored
#: on nothing else so a name that does not declare one refuses rather than guesses.
_SIZE = re.compile(r"(\d+(?:\.\d+)?)B")

#: How the environment pinning is described in the provenance block. A sentence rather than a
#: dump, because the pins themselves are per task and already committed in the manifests.
_ENVIRONMENT_PINS = (
    "per task, from its own manifest: exact `==` pins and a nominated interpreter, resolved once "
    "per distinct pin set (whetstone.bakeoff.scoring.Interpreters) and shared by the control arm "
    "and the rollout so both are graded under the same environment"
)

#: What is recorded where a seed would go. Not "n/a": the reason there is no seed is a decision
#: (D3, one greedy attempt) and a reader checking reproducibility needs the decision, not a blank.
_SEEDS = (
    "none: one greedy attempt per task per candidate (argmax over the vocabulary, "
    "mlx_lm==" + PINNED_MLX_LM + "). No sampling is performed, so there is no seed to record and "
    "no draw for a re-run to differ on"
)


class ContractChanged(RuntimeError):
    """The generation contract moved while the run was in flight. PRD M7b: the run is invalid.

    Raised rather than recorded, and raised **before** the base is asked the changed question, so
    that no scored result can exist under two contracts. A run that carried on would publish a
    comparison between bases that were shown different questions, under one heading, with nothing
    in the document saying so.
    """


class TranscriptNotPrivate(ValueError):
    """The transcript was pointed inside the published output directory. Refused, not warned about.

    `--out` is what `reports/baseline/` is: a committed directory an outside reader is expected to
    read. A transcript holds completions, and a source-B completion quotes the user's own private
    donor code back verbatim — which is the whole reason the manifests live in gitignored
    `tasks/local/` and only hashes and verdicts are committed. A transcript written under `--out` is
    therefore private code staged for publication by a path default.

    A warning would not do. It is printed at the top of a night's run, read by nobody, and by the
    time anyone looks the file exists.
    """


class UnknownCandidate(ValueError):
    """`--only` named something no fetched candidate matches, or something several match.

    Refused rather than resolved. A name matching nothing would score an empty matrix and render
    as a completed sweep with no entrant — the same silent-success shape `UnknownDevSubset` is
    refused for. A name matching several would pick one by position, which is a coin toss the
    report has no way to disclose.
    """


class UnknownDevSubset(ValueError):
    """A declared dev-subset id matches no task in either corpus, so it excludes nothing.

    The failure is silent by construction: the filter matches nothing, every task is scored, and
    the report still prints the declared subset — a disclosure that is false in the one direction
    nobody checks. Refusing costs one comparison and closes it.
    """


class UndeclaredSize(ValueError):
    """A candidate's repository name declares no parameter count, so M7a's tie-break has no key.

    Refused rather than defaulted. The tie-break decides which base P1 starts from when two solve
    the same number of tasks, and a candidate silently sorted as `0.0B` would win every tie it
    entered on a value nobody chose.
    """


#: How a candidate's weights become something that answers prompts. Injected so that every test
#: of this module runs with no `mlx`, no weights and no network — the same inversion
#: `generator.Generator` makes one layer down, made once more here because the *construction* is
#: what AC1 is about: a path loads offline and a repo id downloads.
Engine = Callable[[Weights, int], Generator]


@dataclass(frozen=True)
class Contract:
    """The frozen question. Computed once, before any engine exists, and never recomputed.

    `prompts` is the set of digests the declared template produces over the **scored** set — the
    dev subset is excluded, because those tasks are never generated for. `sha256` is a digest over
    that set, in sorted order, and it is what goes into the published provenance block: an outside
    reader holding the committed task manifests and this repository can recompute it, which is the
    property that makes M7b's invalidation rule checkable rather than merely stated.
    """

    #: The run-level digest, published beside every count.
    sha256: str

    #: Every prompt digest the frozen template yields, against the task it poses. The keys are the
    #: seal `Sealed` enforces; the values exist so a recorder can file a completion under the task
    #: it answers without inferring one from the prompt. The mapping is exact rather than a guess:
    #: it is built by the same pass that freezes the digests, from the same tasks and the same
    #: renderer, so a prompt that reaches a base either appears here or is refused.
    #:
    #: Two tasks rendering an identical prompt collapse to one entry, and that is sound rather than
    #: tolerated: they are the same question, decoding is greedy, so both rollouts receive the same
    #: completion and one record explains both. What the key then names is one of the two.
    posed: Mapping[str, str]

    @property
    def prompts(self) -> frozenset[str]:
        """The digests alone — the seal, without the attribution that rides alongside it.

        A property rather than a second field, because a stored set and a stored mapping are two
        things that can disagree about what was frozen while each looks correct on its own.
        """
        return frozenset(self.posed)


@dataclass(frozen=True)
class Sealed:
    """A base behind the frozen contract: it cannot be asked a question the contract did not fix.

    A `Generator` by structure, wrapping another, so `sweep` and `score` need to know nothing about
    M7b. The check is on the way in and before delegation, which is what makes the abort arrive
    *before* a scored result exists rather than after one has been recorded under a second
    contract.
    """

    #: What actually generates. Never consulted until the prompt has been checked.
    inner: Generator

    #: What was frozen before the run started.
    contract: Contract

    def generate(self, prompt: str) -> str:
        """Refuse a prompt the frozen template did not produce; otherwise pass it straight on."""
        seen = prompt_hash(prompt)
        if seen not in self.contract.posed:
            raise ContractChanged(
                f"a prompt with digest {seen} was about to be sent to a base, and the generation "
                f"contract frozen before this run ({self.contract.sha256}) produces no such "
                "prompt. The template or the extractor moved while the run was in flight, and PRD "
                "M7b makes that an invalidation rather than a footnote: the run is void and must "
                "be restarted from a single contract. Do not resume it — half its rollouts would "
                "answer a different question from the other half, and no reader could tell which"
            )
        return self.inner.generate(prompt)


@dataclass(frozen=True)
class Recording:
    """One candidate's transcript, over a seam that is handed one generator for a whole source.

    `RecordingGenerator` is keyed per (candidate, task) — a record filed under a guessed key is
    worse than no record, since it attributes one task's failure to another. But `sweep` takes a
    single generator for every task in a source, so the per-task recorder has to be built at the
    only moment the task is knowable from here: the call itself. This resolves it from the frozen
    contract, which already knows which task each sealed prompt poses, and builds the recorder for
    that pair. The lookup is exact rather than inferred — the contract was frozen over these tasks
    with this renderer, and `Sealed` guarantees nothing else reaches the base.

    **A prompt the contract does not carry is passed straight down, unrecorded.** That is not a
    tolerated gap, it is the point of the composition: this wrapper sits *outside* `Sealed`, so it
    is the first thing a drifted prompt reaches, and delegating without recording is what lets
    `Sealed` raise `ContractChanged` while the transcript stays a file of completions. Recording it
    under a placeholder — the tempting reading of "capture everything we sent" — would put a
    completion-less row in the transcript for a rollout that never happened and that M7b voided.
    """

    #: The sealed base. Called once per `generate`, whether or not the prompt is being recorded.
    inner: Generator

    #: The file every record goes to. Shared across sources and tasks; the key keeps them apart.
    transcript: Transcript

    #: The base being recorded — the half of the key that does not change between calls.
    candidate: str

    #: The frozen question, read only to learn which task a prompt poses. Never re-checked here:
    #: enforcing the seal is `Sealed`'s job, and a second enforcement is one more thing to get
    #: wrong.
    contract: Contract

    def generate(self, prompt: str) -> str:
        """Record under the task this prompt was frozen for; pass a prompt it did not freeze."""
        task_id = self.contract.posed.get(prompt_hash(prompt))
        if task_id is None:
            return self.inner.generate(prompt)
        return RecordingGenerator(
            inner=self.inner,
            transcript=self.transcript,
            candidate=self.candidate,
            task_id=task_id,
        ).generate(prompt)


@dataclass(frozen=True)
class Cost:
    """What one candidate's run actually cost, measured rather than estimated.

    Kept apart from every count in `report.Tally` on purpose. These are facts about a machine on
    one night; those are facts about a base. A single structure carrying both would invite a
    figure like "solved per hour", which is a rate over two things nobody pinned together.
    """

    #: The base this is about.
    candidate: str

    #: How many tasks were run. Under `--probe N` this is `N`, which is the whole point of it.
    tasks: int

    #: Seconds spent asking the base for text.
    generation_seconds: float

    #: Seconds inside the two verifiers.
    verification_seconds: float

    #: Seconds inside the control arm. Separate because it is overhead the published counts do not
    #: come from, and an operator deciding scope needs to know how much of the night it takes.
    control_seconds: float

    #: Wall-clock around the whole candidate, which exceeds the three above by the environment
    #: builds and the git clones that neither of them is inside.
    wall_seconds: float

    #: Peak resident bytes of **this** process, which is the one holding the weights. The capacity
    #: question `docs/ROADMAP.md:594-596` asks is whether a candidate fits, and that is this
    #: number rather than anything the sandboxed test subprocesses reach.
    peak_bytes: int

    #: The control arm's verdict over this candidate's run. Carried here so a probe — which
    #: publishes no counts and therefore never calls `rankable` — still reports a broken harness.
    harness: Status

    @property
    def seconds_per_task(self) -> float:
        """The measured per-task cost D7 exists to obtain. `0.0` over an empty run."""
        return self.wall_seconds / self.tasks if self.tasks else 0.0


@dataclass(frozen=True)
class Conducted:
    """Everything a run produced, so a caller can assert on it without re-reading the disk."""

    #: The question every scored rollout was asked, frozen before the first of them.
    contract: Contract

    #: One per candidate, in provenance order.
    costs: tuple[Cost, ...]

    #: Every task id that reached a scored rollout. The audit trail behind the dev-subset claim.
    scored: tuple[str, ...]

    #: The rendered report, or `None` for a probe — which measures time and publishes no counts.
    report: Report | None

    #: `(report.md, report.json)` when one was written, else `None`.
    written: tuple[Path, Path] | None


def mlx_engine(weights: Weights, max_tokens: int) -> Generator:
    """Load a verified candidate from its own directory, offline, pinned to its recorded sha.

    Three properties, and the order matters. `HF_HUB_OFFLINE` is set *first*, so that a defect in
    either of the next two raises instead of downloading. The **path** is passed, never
    `weights.repo_id` — `mlx_lm.utils.load` resolves an existing directory from disk and treats
    anything else as a repo id to fetch, and the two are one paste apart. And `revision` is the
    immutable commit sha `load_weights` verified the bytes against, not the tag anybody typed.
    """
    os.environ[HF_HUB_OFFLINE] = "1"
    return MlxGenerator(weights.local_dir, revision=weights.revision, max_tokens=max_tokens)


def select_candidates(fetched: Sequence[Any], only: Sequence[str]) -> tuple[Any, ...]:
    """The candidates to score: all of them, or exactly the ones `--only` names.

    Returned in **fetched** order rather than argument order, so two runs naming the same set
    produce the same sequence and their journals line up.

    Narrowing is opt-in because a report over one candidate must never be able to read as a
    bake-off; the names are recorded in the command line and the report carries one entrant per
    candidate actually scored.
    """
    if not only:
        return tuple(fetched)

    chosen: list[Any] = []
    for name in only:
        matched = [one for one in fetched if name in one.repo_id]
        if len(matched) != 1:
            available = ", ".join(one.repo_id for one in fetched)
            verb = "matches nothing" if not matched else f"matches {len(matched)} candidates"
            raise UnknownCandidate(
                f"--only {name!r} {verb}. Available: {available}. Refused rather than resolved: "
                "a name matching nothing scores an empty matrix and reads as a finished sweep, "
                "and a name matching several picks one by position"
            )
        if matched[0] not in chosen:
            chosen.append(matched[0])
    return tuple(one for one in fetched if one in chosen)


def freeze(tasks: Sequence[Task], *, pool: Path | None = None, retry: bool = False) -> Contract:
    """Fix the question, over the scored set, before anything is loaded or generated.

    Takes the tasks rather than reading the template's source. A source digest would move when a
    comment moved and stay put when a caller passed a different renderer, which is wrong in both
    directions; a digest over the prompts every base will actually be shown moves exactly when
    what they are shown moves. It is also the version an outside reader can recompute.

    **The oracle sources are derived here as well as in `score`, and they have to be.** The prompt
    a base is shown includes the non-test files its task's fix touches, so a contract frozen
    without them would name questions nobody asks and the seal would abort every honest run. The
    derivation is deterministic — the same commit, read out of the same donor — so the two agree;
    what it is not is free, and paying for a second checkout per task once per run is the cost of
    fixing the question before any engine exists rather than after.

    A task whose oracle cannot be derived contributes **no digest**, because `score` records it as
    skipped-with-reason and never asks a base anything about it. Sealing a prompt that is never
    sent would be sealing a question that does not exist.

    The run-level digest is taken over the **distinct** questions, which is the set the seal is,
    and each is recorded against the task that posed it so a completion can be filed under the task
    it answers rather than under one inferred from its text.

    **`retry` folds the retry vocabulary into the same map.** The retry prompt is a pure function
    of `(first-attempt prompt, trigger)` (spec B1), so every retry prompt a retried run may issue
    is pre-rendered here, per task, per trigger, through the same `setdefault` — one task's prompts
    map to that task, the contract SHA covers the whole retry vocabulary, and `Sealed` accepts a
    retry prompt at runtime exactly when it was frozen before the run (PRD D8). Off by default:
    a retries-disabled run's contract is byte-identical to the contract the baseline report
    published, so a reader recomputing that SHA from the committed manifests gets the published
    value.

    **`pool` must be the one `score` is given, and this is the seam where that bites.** A public
    task's file set is declared by its committed gold patch, so a seal taken without the pool omits
    a prompt the rollout then renders — and the sealed generator, correctly, refuses to send a
    question the contract does not carry. The run dies at the first public rollout, after the
    weights are loaded and the private sweep is under way. Passing it in both places is not
    plumbing: it is what makes the question that gets asked the question that was fixed.
    """
    posed: dict[str, str] = {}
    for task in tasks:
        sources = oracle_sources(task, pool=pool)
        if sources.files is None:
            continue
        first = render_prompt(task, sources.files)
        # `setdefault`, so the first task to pose a question keeps it. See `Contract.posed` for why
        # a collision is sound: two tasks rendering one prompt are one question, and greedy
        # decoding gives both the same answer.
        posed.setdefault(prompt_hash(first), task.task_id)
        if retry:
            for trigger in Trigger:
                posed.setdefault(prompt_hash(retry_prompt(first, trigger)), task.task_id)
    return Contract(
        sha256=hashlib.sha256("\n".join(sorted(posed)).encode("utf-8")).hexdigest(),
        posed=MappingProxyType(posed),
    )


def load_task_roots(roots: Sequence[Path]) -> tuple[Task, ...]:
    """Union several corpus directories into one task set, in the order given.

    The miner writes one directory per donor (`tasks/README.md`), so the real source-B corpus is
    two directories rather than one, and `load_tasks` deliberately refuses their parent — it will
    not descend into a subdirectory, because *"a skipped task is a missing denominator"*
    (`whetstone/tasks/manifest.py:79-83`). That refusal is right and is left alone; what changes is
    that the caller may name more than one root.

    Nothing is deduplicated. Two roots naming the same task would be a corpus that counts a task
    twice, and silently collapsing them would hide it — `load_tasks` already fails closed on a
    malformed root, and a repeated one is the operator's error to see.
    """
    assert roots, "no task roots — a run over nothing is a malformed invocation, not a verdict"
    collected: list[Task] = []
    for root in roots:
        collected.extend(load_tasks(root))
    return tuple(collected)


def conduct(
    *,
    tasks: Sequence[Path],
    public: Path,
    pool: Path,
    funnel: Path,
    weights: Path,
    out: Path,
    workspace: Path,
    timeout: float,
    recorded_on: str,
    dev_subset: Sequence[str] = (),
    stratum: Path | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    only: Sequence[str] = (),
    probe: int | None = None,
    journal: Path | None = None,
    transcript: Path | None = None,
    retries: bool = False,
    engine: Engine = mlx_engine,
) -> Conducted:
    """Run the bake-off: verify the weights, freeze the question, sweep, and publish or refuse.

    The order below is the design. Weights are verified before a question is frozen, the question
    is frozen before an engine is constructed, and every count is derived only after `rankable` has
    been asked whether this run's harness proved it could grade anything. Nothing is written until
    all of that has succeeded — a document on disk is a document somebody quotes, and it outlives
    the exception that should have stopped it.

    `probe` is D7's timing sample and not `control.probe`: it runs the first `probe` tasks of the
    private source, writes what they cost, and publishes **no counts at all**.

    `pool` is required rather than optional, and that is the lesson of the first scored run. Source
    A's tasks carry no donor commit, so their control arm has nothing to re-derive and reads the
    committed gold patch from the pool instead. Without one, every public probe is a SKIPPED,
    source A reaches no INTACT, and `rankable` refuses the entire night — after the generation has
    been paid for. `--public` is already required and neither source may be published alone
    (`PREREGISTRATION.md:142-143`), so there is no sound invocation of this function that does not
    need it.

    `transcript` keeps every prompt and completion, so the cause of a zero can be re-derived offline
    rather than by paying for another night of generation. Undefaulted, and checked against `out`
    before anything else happens — see `TranscriptNotPrivate`.

    `retries` is the format-hardening arm's switch, **off by default until the measured arm opts
    in** (PRD R5): when on, `freeze` folds the retry vocabulary into the contract and the entrant
    loop composes the budgeted retry wrapper. A retry is never composed without a transcript — the
    wrapper writes the per-attempt records itself, and `--transcript` is the operator's choice —
    so `retries` on a transcript-less run is still today's run, with the same composition.

    `stratum` is the easier-stratum probe's pinned input (PRD M3): a committed
    `whetstone-stratum/1` document whose membership the run is restricted to. The document is
    **consumed, never recomputed** — a task set changed by the stratum is a new series — and
    the loader is aspect 1's, by identity. The filter runs at the partition seam, before the
    contract is frozen, so both audit trails cover the subset automatically: `freeze` digests
    the posed prompts of the tasks it is handed, and `Conducted.scored` is derived from the
    sweeps over the filtered sets. The dev-subset overlay is unchanged and applies **on top**
    (PRD M3: dev ∩ stratum is exclusion, never a refusal), and an empty scored private set
    after the overlay is refused **before** `freeze` — `MissingSource` would fire only after
    the night is spent (report.py:488-493). Absent, the run is today's run, byte for byte —
    the no-retries precedent (spec AC 10).
    """
    _refuse_published_transcript(transcript, out)
    os.environ[HF_HUB_OFFLINE] = "1"

    private_root_tasks = load_task_roots(tasks)
    stratum_clause = ""
    if stratum is not None:
        try:
            loaded = read_document(stratum)
        except ValueError as exc:
            if isinstance(
                exc, (StratumSchemaError, StratumDigestMismatch, EmptyStratum, UnknownStratumId)
            ):
                raise
            raise StratumSchemaError(
                f"the stratum document {str(stratum)!r} could not be read as a run input: "
                f"{exc}. A document that half-parses selects a membership the run cannot "
                "attribute, and a pinned input that cannot be read is refused rather than "
                "defaulted"
            ) from exc
        private_root_tasks = include_stratum(loaded.membership, private_root_tasks)
        stratum_clause = (
            f"selected by the committed stratum at {stratum!s} (membership "
            f"{len(loaded.membership)}); "
        )
    private_tasks, public_tasks, declared = _partition(
        private_root_tasks, load_tasks(public), dev_subset
    )
    if stratum is not None and not private_tasks:
        raise EmptyStratum(
            f"the stratum document {str(stratum)!r} left no private task to score: every "
            "member of its membership was removed by the dev-subset overlay. The night would "
            "be spent scoring source A alone and `MissingSource` would refuse the report only "
            "after it — refused here, before the contract is frozen or anything is generated"
        )
    contract = freeze((*private_tasks, *public_tasks), pool=pool, retry=retries)
    fetched = select_candidates(load_weights(weights), only)

    interpreters = Interpreters(workspace=workspace / "environments")
    checkpoint = Journal(path=journal) if journal is not None else None

    if probe is not None:
        return _probe(
            fetched,
            private_tasks[:probe],
            contract=contract,
            workspace=workspace,
            out=out,
            timeout=timeout,
            interpreters=interpreters,
            engine=engine,
            max_tokens=max_tokens,
            pool=pool,
        )

    kept = Transcript(path=transcript) if transcript is not None else None

    entrants: list[Entrant] = []
    costs: list[Cost] = []
    scored: list[str] = []
    for one in fetched:
        started = time.perf_counter()
        # `Recording` outside `Sealed`, never the reverse: the recorder must see every prompt the
        # run tries to ask, including one the frozen contract refuses — that is how it can be shown
        # to record none of them. A recorder placed inside the seal would be observing a filtered
        # stream and the property would hold by construction rather than by design.
        asked: Generator = Sealed(inner=engine(one, max_tokens), contract=contract)
        if kept is not None:
            if retries:
                # The retried composition. The retry wrapper is itself the per-attempt recorder —
                # it holds the transcript, the candidate and the frozen `posed` map, and writes one
                # record per attempt with the attempt/decision fields aspect 1 added — so it wraps
                # the sealed engine directly. `Sealed` stays innermost: every prompt, first and
                # retry, must pass the frozen-set check (PRD D8), and a seal-refused retry prompt
                # raises `ContractChanged` through the wrapper with no record for that attempt and
                # no further attempts.
                asked = Retry(
                    inner=asked,
                    transcript=kept,
                    candidate=one.repo_id,
                    contract=contract.posed,
                    budget=RETRY_BUDGET,
                )
            else:
                asked = Recording(
                    inner=asked, transcript=kept, candidate=one.repo_id, contract=contract
                )
        runs = {
            source: sweep(
                candidate=one.repo_id,
                tasks=source_tasks,
                generator=asked,
                sandbox_root=_workspace(workspace, one, source),
                timeout=timeout,
                interpreters=interpreters,
                journal=checkpoint,
                pool=pool,
            )
            for source, source_tasks in (("private", private_tasks), ("public", public_tasks))
        }
        costs.append(
            _cost(one.repo_id, (runs["private"], runs["public"]), time.perf_counter() - started)
        )
        # `rankable` here rather than only inside `build_report`: it refuses a run whose control
        # arm never proved the harness grades anything, and refusing before the next candidate
        # spends a night is worth the duplicated call.
        scored.extend(
            record.task_id
            for run in runs.values()
            for record in rankable(run)
        )
        entrants.append(
            Entrant(
                contender=Contender(
                    candidate=one.repo_id,
                    revision=one.revision,
                    parameters_billions=_billions(one.repo_id),
                ),
                private=runs["private"],
                public=runs["public"],
            )
        )

    report = build_report(
        entrants=entrants,
        provenance=Provenance(
            task_set=(
                # The corpus directories are counted, never named. They live under
                # `tasks/local/`, they are the user's own private repositories, and this
                # document is published — an absolute path from the author's machine
                # discloses both the name and the home directory while telling an outside
                # reader nothing they can use. Identity, in its pseudonymous form, lives in
                # `tasks/recipes/`, which is the committed half built for exactly that.
                f"source B: {len(private_tasks)} tasks from {len(tasks)} declared corpus "
                f"{'directory' if len(tasks) == 1 else 'directories'} (labelled in "
                f"tasks/recipes/); {stratum_clause}source A: {len(public_tasks)} from "
                f"{public}. Declared and "
                "hash-recorded, and deliberately NOT called held out (PRD D4): "
                "PREREGISTRATION.md § 7.1 leaves that split open and unspent"
            ),
            environment_pins=_ENVIRONMENT_PINS,
            seeds=_SEEDS,
            tool_versions=_tool_versions(),
            recorded_on=recorded_on,
        ),
        contract=GenerationContract(
            prompt_sha256=contract.sha256,
            sampler=SAMPLER,
            max_tokens=max_tokens,
            extractor_version=_extractor_version(),
            dev_subset=declared,
            retry_budget=RETRY_BUDGET if retries else 0,
            retry_template_sha256=retry_template_sha256() if retries else "",
            diagnosis_vocabulary_version=diagnosis_vocabulary_sha256() if retries else "",
            retrieval="oracle",
        ),
        funnel=funnel_from_ledger(funnel),
    )
    written = write(report, out)
    _publish(out / COST_FILE, costs, kind="scored")
    return Conducted(
        contract=contract,
        costs=tuple(costs),
        scored=tuple(scored),
        report=report,
        written=written,
    )


def _positive(value: str) -> int:
    """A generation budget that could actually produce a patch.

    Zero or negative is refused rather than clamped: every candidate would fail for a reason
    about the harness, and the sweep of zeros would read as a finding about the bases.
    """
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError(
            f"--max-tokens must be at least 1, got {number}. A run that cannot emit a token "
            "publishes a matrix of zeros that says nothing about any candidate"
        )
    return number


def build_parser() -> argparse.ArgumentParser:
    """The CLI surface, built separately so tests can exercise it without running anything.

    Split out of ``main`` when ``--tasks`` became repeatable: a flag whose accumulation is the
    difference between scoring a corpus and scoring one donor of it deserves an assertion, and
    an assertion needs a parser it can reach without a weights provenance and a night to spare.
    """
    parser = argparse.ArgumentParser(
        prog="python -m whetstone.bakeoff.run",
        description=(
            "Run the P1 baseline bake-off: every candidate in a weights provenance, over both "
            "task sources, against the STRICT and WEAK verifiers, under a generation contract "
            "frozen before the first scored result."
        ),
    )
    parser.add_argument(
        "--tasks",
        type=Path,
        required=True,
        action="append",
        metavar="DIR",
        help="source B: a private corpus directory, repeatable. The miner writes one directory "
        "per donor, so the real corpus is `tasks/local/donor-b` and `tasks/local/donor-a` rather "
        "than their parent — `load_tasks` refuses a directory holding subdirectories, on the "
        "ground that a skipped task is a missing denominator. Name each donor; the roots are "
        "unioned. Read by path and never copied: it is the user's own code and lives outside "
        "any worktree.",
    )
    parser.add_argument(
        "--public",
        type=Path,
        required=True,
        help="source A: the eligible public instance(s). Published beside source B always "
        "(PREREGISTRATION.md:142-143); neither source may appear alone.",
    )
    parser.add_argument(
        "--pool",
        type=Path,
        required=True,
        help="source A's committed pool (tasks/public/pool.json). A public instance has no donor "
        "commit, so its control arm reads the gold patch from here rather than re-deriving one. "
        "Required, not optional: without it every public probe is a skip, source A proves nothing "
        "about the harness, and the whole run is refused a ranking after the generation is paid "
        "for — which is exactly how the first scored run ended. Never read for source B.",
    )
    parser.add_argument(
        "--funnel",
        type=Path,
        required=True,
        help="source A's four-gate rejection ledger (tasks/public/ineligible.json), so the "
        "funnel is quoted from the evidence rather than from memory.",
    )
    parser.add_argument(
        "--weights",
        type=Path,
        required=True,
        help="the weights root holding provenance.json. Every recorded sha256 is re-checked "
        "before a token is generated.",
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="where report.md, report.json and cost.json go."
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        required=True,
        help="where sandboxes and provisioned environments are built. Never inside --out: that "
        "directory is committed and this one is gigabytes of scratch.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        required=True,
        help="seconds allowed per verification. No default, matching the verifiers: a limit "
        "inherited from elsewhere turns every slow task into an UNVERIFIED nobody can explain.",
    )
    parser.add_argument(
        "--recorded-on",
        required=True,
        help="the date the operator declares for this run. An input, never the clock — a report "
        "that dated itself would differ from itself between two renders of the same records.",
    )
    parser.add_argument(
        "--dev-subset",
        action="append",
        default=[],
        metavar="TASK_ID",
        help="a task id the generation contract was developed against (PRD M7b). Repeatable. "
        "Excluded from every published count and named in the report. An id matching no task is "
        "refused, because it would exclude nothing while the report said it had.",
    )
    parser.add_argument(
        "--stratum",
        type=Path,
        help="the committed stratum document (schema whetstone-stratum/1) naming the source-B "
        "membership this run is restricted to (PRD M3). The document is a pinned input — "
        "consumed, never recomputed — and the loader refuses by name: an unknown schema, an "
        "unknown field, a rule or document digest that no longer matches, a membership id "
        "matching no loaded private task, a duplicated membership, a member the rule refused, "
        "or a degenerate membership (empty, whole corpus, or empty after the dev-subset "
        "overlay). Source A is still scored in full; both sources always publish together. "
        "Off by default: without the flag the run is today's run, byte for byte.",
    )
    parser.add_argument(
        "--max-tokens",
        type=_positive,
        default=DEFAULT_MAX_TOKENS,
        metavar="N",
        help=(
            "the generation budget per rollout. Defaults to the pinned one, so an unflagged "
            "re-run is the same experiment. It is a GenerationContract field, so a run at a "
            "different budget discloses that in its own provenance block rather than looking "
            "like the run before it"
        ),
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="NAME",
        help=(
            "score only the candidates whose repo id contains NAME. Repeatable. A name matching "
            "nothing or matching several is refused, never resolved: the first scores an empty "
            "matrix that reads as a finished sweep, the second picks one by position"
        ),
    )
    parser.add_argument(
        "--probe",
        type=int,
        metavar="N",
        help="D7: run only the first N tasks of source B, publish what they cost, and publish no "
        "counts whatsoever. Use it to decide scope before committing to the full matrix.",
    )
    parser.add_argument(
        "--journal",
        type=Path,
        help="checkpoint file, so an interrupted overnight run resumes instead of restarting. "
        "Optional and undefaulted: a default would resume from a run somebody had forgotten.",
    )
    parser.add_argument(
        "--transcript",
        type=Path,
        help="where every prompt and completion is kept, so the cause of a zero can be re-derived "
        "offline instead of by paying for another night of generation. Optional and undefaulted, "
        "for the reason --journal is and then some: a default would resume from a run somebody had "
        "forgotten, and this one would write the user's own private donor code, verbatim, to a "
        "path nobody chose. It may not be inside --out, which is published, and it is ignored "
        "under --probe, which measures time and gathers no evidence.",
    )
    parser.add_argument(
        "--retries",
        action="store_true",
        help="the format-hardening arm's switch (PRD R5): fold the retry vocabulary into the "
        "frozen contract and compose the budgeted retry wrapper, so a parse-refusal shape can be "
        "re-asked up to the budget. Off by default, so an unflagged re-run is the baseline "
        "contract, byte for byte. A retry is never composed without a transcript — the wrapper "
        "writes the per-attempt records itself — so on a run without --transcript this flag is "
        "still today's run, with the same composition.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse an operator's invocation and run it. The whole CLI surface of the bake-off.

    Every path and every limit is **required**, with no defaults anywhere. A default output
    directory, workspace or timeout would each put a night's work — or a night's failure — somewhere
    the operator did not choose, which is the argument `sweep` already makes for refusing to
    default its journal and `score` makes for refusing to default its timeout.
    """
    parser = build_parser()
    arguments = parser.parse_args(argv)

    # Converted to argparse's own usage error rather than allowed to propagate, because the two
    # read as different problems to the operator: a traceback says the harness is broken and invites
    # the same command again, while a usage error names the flag that was wrong. The check itself
    # lives in `conduct`, so a caller reaching it another way is refused just the same.
    try:
        conducted = conduct(
            tasks=arguments.tasks,
            public=arguments.public,
            pool=arguments.pool,
            funnel=arguments.funnel,
            weights=arguments.weights,
            out=arguments.out,
            workspace=arguments.workspace,
            timeout=arguments.timeout,
            recorded_on=arguments.recorded_on,
            dev_subset=arguments.dev_subset,
            stratum=arguments.stratum,
            max_tokens=arguments.max_tokens,
            only=arguments.only,
            probe=arguments.probe,
            journal=arguments.journal,
            transcript=arguments.transcript,
            retries=arguments.retries,
        )
    except (
        TranscriptNotPrivate,
        UnknownCandidate,
        StratumSchemaError,
        StratumDigestMismatch,
        EmptyStratum,
        UnknownStratumId,
    ) as refusal:
        parser.error(str(refusal))
    for cost in conducted.costs:
        print(
            f"{cost.candidate}: {cost.tasks} tasks, {cost.wall_seconds:.1f}s "
            f"({cost.seconds_per_task:.1f}s/task), peak {cost.peak_bytes / 1024**3:.2f} GiB, "
            f"harness {cost.harness.value}"
        )
    if conducted.written is not None:
        print(f"wrote {conducted.written[0]} and {conducted.written[1]}")
    return 0


def _probe(
    fetched: Sequence[Weights],
    tasks: Sequence[Task],
    *,
    contract: Contract,
    workspace: Path,
    out: Path,
    timeout: float,
    interpreters: Interpreters,
    engine: Engine,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    pool: Path,
) -> Conducted:
    """D7's timing sample: run `tasks`, write what they cost, and derive not one count.

    No journal, deliberately. A probe that checkpointed into the scored run's journal would let
    the scored run replay records produced by a sample, and a probe with a journal of its own is a
    file whose only purpose is to be confused with that one.

    **No transcript either, and for the same reason.** `--transcript` names one file; a probe
    writing into it would leave rows from a self-chosen sample in the evidence an offline replay
    reads as a scored run's, and rows for tasks the scored run never touches would survive it. The
    flag is documented as scored-run-only rather than refused alongside `--probe`, because a probe
    is a timing sample and the operator running one is deciding scope, not gathering evidence.

    `rankable` is not called, and that is the reason `Cost` carries the harness status: a probe
    publishes no counts, so there is nothing for `rankable` to gate — but a broken harness is the
    single most important thing a probe can discover, and it must not be silent.
    """
    costs = []
    for one in fetched:
        started = time.perf_counter()
        run = sweep(
            candidate=one.repo_id,
            tasks=tasks,
            generator=Sealed(inner=engine(one, max_tokens), contract=contract),
            sandbox_root=_workspace(workspace, one, "probe"),
            timeout=timeout,
            interpreters=interpreters,
            journal=None,
            pool=pool,
        )
        costs.append(_cost(one.repo_id, (run,), time.perf_counter() - started))

    _publish(out / PROBE_FILE, costs, kind="probe")
    return Conducted(
        contract=contract, costs=tuple(costs), scored=(), report=None, written=None
    )


def _refuse_published_transcript(transcript: Path | None, out: Path) -> None:
    """Refuse a transcript inside the published output directory, before anything is loaded or run.

    Resolved rather than compared as written, because `out/../out/x.jsonl` and a symlinked scratch
    directory both name a path inside `out` while comparing unequal to it — and the check has to
    hold against the path that gets written, not the one that got typed. `strict=False` throughout:
    neither directory exists yet on the first run, and a check that required them to would refuse
    every honest invocation.
    """
    if transcript is None:
        return
    if transcript.resolve().is_relative_to(out.resolve()):
        raise TranscriptNotPrivate(
            f"the transcript at {str(transcript)!r} is inside the output directory {str(out)!r}, "
            "which is published — `reports/baseline/` is what a committed one looks like. A "
            "transcript holds completions, and a source-B completion quotes the user's own private "
            "donor code back verbatim, which is why the manifests live in gitignored "
            "`tasks/local/` and only hashes and verdicts are committed. Point --transcript at a "
            "gitignored root "
            "outside --out. This is refused rather than warned about because a warning at the top "
            "of a night's run is read after the file already exists"
        )


def _partition(
    private: Sequence[Task], public: Sequence[Task], dev_subset: Sequence[str]
) -> tuple[tuple[Task, ...], tuple[Task, ...], tuple[str, ...]]:
    """Remove the declared dev subset from both sources, refusing any id that matches nothing."""
    declared = tuple(dict.fromkeys(dev_subset))
    known = {task.task_id for task in (*private, *public)}
    unmatched = [one for one in declared if one not in known]
    if unmatched:
        raise UnknownDevSubset(
            f"the declared dev subset names {unmatched}, which match no task in either corpus. "
            "Left alone this excludes nothing while the report still prints the subset as "
            "excluded — a disclosure that is false in the one direction nobody checks. Fix the "
            f"ids or drop them. Loaded task ids: {sorted(known)}"
        )
    excluded = set(declared)
    return (
        tuple(task for task in private if task.task_id not in excluded),
        tuple(task for task in public if task.task_id not in excluded),
        declared,
    )


def _cost(candidate: str, runs: Sequence[Sweep], wall_seconds: float) -> Cost:
    """Total one candidate's measured seconds across every source it was run on."""
    steps = [step for run in runs for step in run.steps]
    records: list[Rollout] = [step.rollout for step in steps]
    return Cost(
        candidate=candidate,
        tasks=len(steps),
        generation_seconds=sum(record.generation_seconds for record in records),
        verification_seconds=sum(
            record.strict_seconds + record.weak_seconds for record in records
        ),
        control_seconds=sum(step.probe.seconds for step in steps),
        wall_seconds=wall_seconds,
        peak_bytes=_peak_bytes(),
        harness=Status.UNVERIFIED
        if any(run.status is not Status.PASS for run in runs)
        else Status.PASS,
    )


def _publish(path: Path, costs: Sequence[Cost], *, kind: str) -> Path:
    """Write the measured cost, and nothing derived from a verdict.

    The payload is per-candidate seconds, memory and the harness's status. There is deliberately
    no count of anything a base did: a probe's payload is read before the scored set's size is
    fixed, and a partial score in it would make that decision one taken while looking at results.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "kind": kind,
                "candidates": [
                    {
                        "candidate": cost.candidate,
                        "tasks": cost.tasks,
                        "generation_seconds": round(cost.generation_seconds, 3),
                        "verification_seconds": round(cost.verification_seconds, 3),
                        "control_seconds": round(cost.control_seconds, 3),
                        "wall_seconds": round(cost.wall_seconds, 3),
                        "seconds_per_task": round(cost.seconds_per_task, 3),
                        "peak_bytes": cost.peak_bytes,
                        "harness": cost.harness.value,
                    }
                    for cost in costs
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _workspace(root: Path, weights: Weights, source: str) -> Path:
    """A sandbox root per candidate per source, with the repo id's slash flattened out."""
    return root / "sandbox" / weights.repo_id.replace("/", _SEPARATOR) / source


def _billions(repo_id: str) -> float:
    """The declared parameter count in a repository name, or a refusal naming what was read.

    Read from the operator's own identifier rather than guessed, and refused when the name
    declares nothing: it is M7a's tie-break key, and a candidate silently sorted as `0.0B` would
    win every tie it entered on a value nobody chose. Exactly one match is required, so a name
    carrying two numbers before a `B` is a refusal rather than a coin toss.
    """
    found = _SIZE.findall(repo_id.split("/")[-1])
    if len(found) != 1:
        raise UndeclaredSize(
            f"{repo_id!r} declares {len(found)} parameter counts ({found}), and M7a's tie-break "
            "needs exactly one. Rename the fetched directory, or record the size explicitly — do "
            "not let a candidate be ranked on a number this function guessed"
        )
    return float(found[0])


def _extractor_version() -> str:
    """A digest of the extractor's own source, so the recorded version cannot drift from it.

    A hand-maintained `"1"` is a string somebody forgets to bump on the one commit where it
    mattered. This is recorded in the provenance block and never compared mid-run, so a docstring
    edit moving it costs a reader nothing and buys the guarantee that a real edit moves it too.
    """
    source = Path(extraction.__file__).read_bytes()
    return f"extract_patch@{hashlib.sha256(source).hexdigest()[:12]}"


def _tool_versions() -> dict[str, str]:
    """The versions a figure is only interpretable against (`PREREGISTRATION.md:131-132`)."""
    return {
        "python": platform.python_version(),
        "whetstonehq": __version__,
        "mlx-lm": PINNED_MLX_LM,
        "platform": f"{platform.system()} {platform.release()} {platform.machine()}",
    }


def _peak_bytes() -> int:
    """Peak resident bytes of this process, in bytes on every platform this runs on.

    `ru_maxrss` is bytes on Darwin and kibibytes on Linux, which is the kind of difference that
    produces a capacity finding off by a factor of 1024. The bake-off is macOS-only
    (`sandbox.py:66`), so the conversion is belt-and-braces for anyone reading this on Linux.
    """
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


__all__ = [
    "COST_FILE",
    "HF_HUB_OFFLINE",
    "PROBE_FILE",
    "REPORT_FILE",
    "Conducted",
    "Contract",
    "ContractChanged",
    "Cost",
    "Engine",
    "Recording",
    "Sealed",
    "TranscriptNotPrivate",
    "UndeclaredSize",
    "UnknownDevSubset",
    "conduct",
    "freeze",
    "main",
    "mlx_engine",
]


if __name__ == "__main__":
    raise SystemExit(main())
