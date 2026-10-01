"""The measurement driver: one greedy attempt per pinned task, and no verdict at all.

The unit asks whether the pinned base can *address* a numbered listing — the generation
half of the edit-contract finding (`docs/planning/edit-contract-finding/prd.md` § 4.1).
The driver spends that small bake-off: for each of the 16 pre-committed tasks it renders
the format's prompt — the numbered listing by default (`--renderer line-range`,
byte-identical to the v0.17.0 run), or the whole-function format under `--renderer
whole-function` — asks the base once (`K = 1`, greedy — `sampler_for(1)` is
the bake-off's own `greedy_sampler` by identity — retries 0), and records the completion
beside a rollout row that says `UNVERIFIED` with the reason spelled out:
**"measurement run — no grading performed by design"**. The verifier is never entered
for any rollout: there is no diff to grade, and a verdict about a verifier that graded
nothing is no verdict — the run's evidence is what the offline instrument classifies,
not what a reward graded.

**The population is pinned by identity, and a run that differs is refused.** The
population is the committed stratum document's membership minus the committed held-out
document's membership — read through the same fail-closed loaders the night and the
gate use, so an unknown schema, a drifted rule digest, a hand-edited payload or a broken
`document_digest` is a named refusal — and the result must equal the spec's pinned
16-task list (`_PINNED_POPULATION`, the spec's "Population" rule, cross-pinned in
`test_measure_driver.py`). A held-out member is never a rollout target; a task set that
differs from the pinned list is a different experiment and is refused before anything
is generated.

**The control arm is required, and it is the real one.** Per task, the same probe the
night builds — `control.probe` by identity: the inert patch must FAIL and the task's own
re-derived reference must PASS, both through the shipped `verify_strict`, under the same
provisioned interpreters the run uses. If the fold over every draw is not `PASS`, the
run refuses with the named reason and **writes no evidence**: a journal, transcript or
manifest on disk is a document somebody quotes, and it must not exist for a run whose
harness was never shown to grade anything.

**Evidence is written only when the whole run has succeeded.** The journal and
transcript codecs are append-only, but this driver appends at the end, deliberately:
the `RecordingGenerator` wrapper would write a completion the moment it was generated,
and a run that later refuses on the control fold would leave exactly the evidence the
refusal says must not exist. So completions and steps accumulate in memory, the fold is
the gate, and only then are the three files written — journal and transcript first, the
manifest last. Exit 0 means all three are on disk.

**It is `python -m whetstone.bakeoff.measure` and deliberately not a `whetstone`
subcommand**, for the same reason `run.py:7-13` gives: a subcommand would put `mlx_lm`
one transitive import from the reward path while every guard stayed green.

**Nothing here decides what a patch earns — because nothing here grades at all.** The
rows it writes are `UNVERIFIED` by design and must never be read as verdicts; the
manifest is the source of truth for population, candidate and the per-task prompt
digests, and the finding restates the spec's disclosure (`spec.md`, "Open questions").
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from whetstone.bakeoff.control import Control, harness_status, probe
from whetstone.bakeoff.journal import Journal, Step
from whetstone.bakeoff.line_range import render_line_range_prompt
from whetstone.bakeoff.mlx_runtime import DEFAULT_MAX_TOKENS
from whetstone.bakeoff.rendering import prompt_hash
from whetstone.bakeoff.run import (
    Engine,
    _tool_versions,
    load_task_roots,
    mlx_engine,
    select_candidates,
)
from whetstone.bakeoff.scoring import Interpreters, Outcome, Renderer, Rollout
from whetstone.bakeoff.sources import oracle_sources
from whetstone.bakeoff.stratum import (
    EmptyStratum,
    StratumDigestMismatch,
    StratumSchemaError,
    UnknownStratumId,
)
from whetstone.bakeoff.stratum import (
    read_document as read_stratum_document,
)
from whetstone.bakeoff.transcript import Transcribed, Transcript
from whetstone.bakeoff.weights import ProvenanceUnreadable, WeightsUnverified, load_weights
from whetstone.bakeoff.whole_function import render_whole_function_prompt
from whetstone.loop.heldout import (
    EmptyHeldout,
    HeldoutDigestMismatch,
    HeldoutSchemaError,
    UnknownHeldoutId,
)
from whetstone.loop.heldout import (
    read_document as read_heldout_document,
)
from whetstone.verify.task import Task
from whetstone.verify.verdict import Status

#: The manifest's schema. Bumped on any change to a field's meaning.
MANIFEST_SCHEMA = "whetstone-measure/1"

#: The population the run must consume, pinned by the spec before any rollout ran
#: (`docs/planning/edit-contract-finding/measurement-run/spec.md`, "Population"): the
#: easier-stratum document's membership minus the held-out document's membership, by
#: identity — 19 easier-band members less the three held-out members that overlap
#: (`donor-a-6884ed72a9e9`, `donor-a-c6e4d4c4de87`, `donor-a-c7cee63e3cab`). A run whose
#: task set differs from this list is refused. Sorted, which is also the order the run
#: poses them in.
_PINNED_POPULATION = (
    "donor-a-128bcb99b701",
    "donor-a-16213e62eae1",
    "donor-a-2ef3383b0ce7",
    "donor-a-2f4e497580ff",
    "donor-a-34daf85182d5",
    "donor-a-5e25b106874c",
    "donor-a-6005d7ec06f5",
    "donor-a-7975de5439dc",
    "donor-a-b7c53b77453a",
    "donor-a-d601ff2d0ec0",
    "donor-a-ec3af08b913d",
    "donor-a-f100a90e47f2",
    "donor-b-0f8651175ef8",
    "donor-b-45740535725b",
    "donor-b-c57246c7841a",
    "donor-b-dbf19c8009dd",
)

#: The sentence every rollout row carries, so the journal can never silently stop saying
#: the run never grades. The finding restates it; consumers must not read the field as a
#: verdict (spec.md, "Open questions").
MEASUREMENT_DETAIL = "measurement run — no grading performed by design"

#: The run's declared seed. The measurement decodes greedily (`K = 1`, retries 0), so no
#: draw consumes it; it is recorded because the run id descends from it and because a
#: seedless run id would make two runs of different experiments indistinguishable. A
#: declared constant, never a flag — the `SPLIT_SEED` discipline: a per-run decoding knob
#: is a knob that gets turned until the number improves.
RUN_SEED = 1

#: The two named prompt formats the run can pose, by their `--renderer` values. The
#: default is `line-range` — the v0.17.0 behaviour, byte-identical — and `whole-function`
#: is this unit's format, pinned by the runbook for its run. A name that is neither is a
#: refusal, never a fallback: a run that quietly posed a different format than its
#: command named would write evidence no reader could trust. The manifest schema is
#: unchanged — the per-task `prompt_sha256` is the only discriminator between formats.
RENDERERS: dict[str, Renderer] = {
    "line-range": render_line_range_prompt,
    "whole-function": render_whole_function_prompt,
}

#: The evidence home the run defaults to: gitignored, so a private run's completions —
#: which quote the user's own donor code back verbatim — never enter the tree.
_RUN_DIR = Path("runs") / "edit-contract-finding"
_JOURNAL_FILE = "journal.jsonl"
_TRANSCRIPT_FILE = "transcript.jsonl"
_MANIFEST_FILE = "manifest.json"


class RelativeWorkspace(ValueError):
    """`--workspace` was not an absolute path — the runbook's known pitfall, refused here.

    A relative workspace resolves against wherever the operator happened to start the
    process, so the same command from two shells builds its sandboxes in two places.
    """


class EmptyPopulation(ValueError):
    """The stratum minus the held-out membership left nothing to roll out."""


class PopulationMismatch(ValueError):
    """The documents' memberships do not subtract to the spec's pinned 16-task list.

    A changed document — or a changed spec — is a halt, never a rerun: a run whose task
    set differs from the pinned list is a different experiment.
    """


class UnknownPopulationMember(ValueError):
    """A pinned id matches no loaded task, so the run could not ask it anything."""


class NotOneCandidate(ValueError):
    """The weights provenance does not name exactly one candidate to measure.

    The measurement is one base — the pinned 32B — and a provenance naming several (or
    none) is refused rather than picked, because selecting by position is a coin toss the
    manifest has no way to disclose.
    """


class ControlNotIntact(ValueError):
    """The control fold over every draw is not `PASS`, so no evidence may exist.

    A verdict about a verifier that graded nothing is no verdict: the run refuses with
    the failing draws named, and nothing is written.
    """


class UnknownRenderer(ValueError):
    """`--renderer` named a format this driver does not pose.

    Exactly two formats exist — `line-range`, the default, and `whole-function` — and a
    name that is neither is refused rather than defaulted: a run that quietly fell back
    would pose one format while its command named another, and its evidence would read
    as the format it never posed.
    """


#: What the CLI turns into a refusal exit (2) rather than a traceback. The named refusals
#: first; `ValueError` closes the tuple — the document loaders' own errors (a missing
#: file, an unreadable JSON) are `ValueError`s, and a door that crashes on an unforeseen
#: `ValueError` with a traceback is worse than a named exit-2 (the `check_probe` shape).
REFUSALS: tuple[type[Exception], ...] = (
    RelativeWorkspace,
    EmptyPopulation,
    PopulationMismatch,
    UnknownPopulationMember,
    NotOneCandidate,
    ControlNotIntact,
    UnknownRenderer,
    ProvenanceUnreadable,
    WeightsUnverified,
    StratumSchemaError,
    StratumDigestMismatch,
    EmptyStratum,
    UnknownStratumId,
    HeldoutSchemaError,
    HeldoutDigestMismatch,
    EmptyHeldout,
    UnknownHeldoutId,
    ValueError,
)


@dataclass(frozen=True)
class Measured:
    """Everything a measurement run produced, so a caller can assert without re-reading disk."""

    #: The run's id: a digest over the declared inputs, never the clock.
    run_id: str

    #: The candidate's repo id, from the weights provenance.
    candidate: str

    #: The immutable revision the provenance recorded for the candidate.
    revision: str

    #: The pinned population, in the order it was posed.
    tasks: tuple[str, ...]

    #: Where the steps were appended, once the control fold passed.
    journal: Path

    #: Where the completions were appended, once the control fold passed.
    transcript: Path

    #: The run manifest, written last — its existence is the exit-0 condition.
    manifest: Path


def run_measurement(
    *,
    tasks: Sequence[Path],
    stratum: Path,
    heldout: Path,
    weights: Path,
    workspace: Path | str,
    recorded_on: str,
    timeout: float,
    journal: Path | None = None,
    transcript: Path | None = None,
    manifest: Path | None = None,
    only: Sequence[str] = (),
    run_seed: int = RUN_SEED,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    engine: Engine = mlx_engine,
    renderer: Renderer = render_line_range_prompt,
) -> Measured:
    """Run the measurement over the pinned population, or refuse — writing nothing on refusal.

    The order below is the design. The workspace is checked first, because a relative one
    is the runbook's known pitfall and it costs nothing to refuse; the documents are read
    through their own fail-closed loaders before anything is generated, so a drifted or
    hand-edited pinned input halts before a token is spent; the population is pinned by
    identity before a task is posed. Then, per task: the control probe runs first (the
    `sweep` shape — a harness that cannot grade is visible from the first task), the
    format's prompt is rendered from the same oracle derivation `score` uses, and
    one greedy completion is asked for and held, ungraded.

    Everything is held until the fold is known: a run whose control fold is not `PASS`
    writes nothing. Only then are the journal, the transcript and the manifest written,
    in that order — the manifest last, so its existence is the exit-0 condition.

    `engine` is the generator seam, `run.mlx_engine` by default (offline, greedy, pinned
    revision); tests substitute a stub. `pool` is deliberately never threaded: every
    member of the pinned population is a source-B task carrying a donor commit, and the
    measurement must never fall back to a public dataset's scope.

    `renderer` is the seam this driver's prompt is threaded through — the `score` seam
    shape. The default is `render_line_range_prompt` itself (`RENDERERS["line-range"]`),
    so every existing caller's behaviour is byte-identical (the line-range assertions in
    `test_measure_driver.py` are the anti-regression control); `--renderer whole-function`
    selects this unit's format. A renderer is a pure function of `(task, sources)` that
    refuses a held test path in its sources the way `render_prompt` does — the seam
    supplies bytes, never permission to show the answer key. The manifest schema does not
    change with the renderer: the per-task `prompt_sha256` is the format discriminator.
    """
    workspace = _refuse_relative_workspace(workspace)

    journal_path = Path(journal or _RUN_DIR / _JOURNAL_FILE)
    transcript_path = Path(transcript or _RUN_DIR / _TRANSCRIPT_FILE)
    manifest_path = Path(manifest or _RUN_DIR / _MANIFEST_FILE)

    loaded = load_task_roots(tasks)
    fetched = load_weights(weights)
    chosen = select_candidates(fetched, only)
    if len(chosen) != 1:
        available = ", ".join(one.repo_id for one in chosen)
        raise NotOneCandidate(
            f"the measurement is one candidate — the pinned base — and the weights "
            f"provenance at {str(weights)!r} names {len(chosen)} after selection "
            f"({available or 'none'}). Refused rather than picked: selecting by position "
            "is a coin toss the manifest has no way to disclose"
        )
    candidate = chosen[0]

    stratum_document = read_stratum_document(Path(stratum))
    heldout_document = read_heldout_document(Path(heldout))

    population = tuple(sorted(set(stratum_document.membership) - set(heldout_document.membership)))
    if not population:
        raise EmptyPopulation(
            f"the stratum membership ({len(stratum_document.membership)} members) minus the "
            f"held-out membership ({len(heldout_document.membership)} members) leaves nothing "
            "to roll out. A held-out member is never a rollout target, and a run of no tasks "
            "is a usage error, never a result"
        )
    if population != _PINNED_POPULATION:
        raise PopulationMismatch(
            f"the committed documents subtract to {len(population)} tasks, not the spec's "
            f"pinned {len(_PINNED_POPULATION)}. A run whose task set differs from the "
            "pinned list is a different experiment (spec.md, \"Population\"), and a changed "
            "pre-committed input is a halt, never a rerun. Got: "
            + ", ".join(population[:5])
            + ("…" if len(population) > 5 else "")
        )

    by_id = {task.task_id: task for task in loaded}
    missing = [task_id for task_id in population if task_id not in by_id]
    if missing:
        raise UnknownPopulationMember(
            f"the pinned population names {missing}, which match no loaded task from the "
            f"declared corpus directories. A task the run cannot load is a denominator the "
            f"run cannot ask. Loaded task ids: {sorted(by_id)}"
        )

    interpreters = Interpreters(workspace=workspace / "environments")
    generator = engine(candidate, max_tokens)

    steps: list[Step] = []
    records: list[Transcribed] = []
    for task_id in population:
        task = by_id[task_id]
        controlled = probe(
            candidate=candidate.repo_id,
            task=task,
            sandbox_root=workspace / "sandbox" / task_id / "control",
            timeout=timeout,
            interpreters=interpreters,
            pool=None,
        )

        sources = oracle_sources(task, pool=None)
        if sources.files is None:
            # The oracle could not be built — no prompt, no generation, and no verifier.
            # Recorded like `score` records it, with the reason; the control fold gates
            # whether the run as a whole may exist.
            steps.append(
                Step(
                    probe=controlled,
                    rollout=_no_oracle(candidate.repo_id, task, sources.reason),
                )
            )
            continue

        prompt = renderer(task, sources.files)
        started = time.perf_counter()
        completion = generator.generate(prompt)
        generation_seconds = time.perf_counter() - started

        steps.append(
            Step(
                probe=controlled,
                rollout=Rollout(
                    candidate=candidate.repo_id,
                    task_id=task_id,
                    outcome=Outcome.UNVERIFIED,
                    strict=None,
                    weak=None,
                    verdict_kinds=(),
                    executed=None,
                    prompt_sha256=prompt_hash(prompt),
                    detail=MEASUREMENT_DETAIL,
                    generation_seconds=generation_seconds,
                    strict_seconds=0.0,
                    weak_seconds=0.0,
                ),
            )
        )
        records.append(
            Transcribed(
                candidate=candidate.repo_id,
                task_id=task_id,
                prompt_sha256=prompt_hash(prompt),
                prompt=prompt,
                completion=completion,
                attempt=1,
                decision="graded",
            )
        )

    fold = harness_status(step.probe for step in steps)
    if fold is not Status.PASS:
        failing = [
            f"{step.probe.task_id}: {step.probe.control.value}"
            + (f" — {step.probe.detail}" if step.probe.detail else "")
            for step in steps
            if step.probe.control is not Control.INTACT
        ]
        raise ControlNotIntact(
            f"the control fold over {len(steps)} draws is {fold.value}, not PASS, so "
            "nothing this run generated is evidence about any base and no evidence is "
            "written. Failing draws: " + "; ".join(failing)
        )

    journal_codec = Journal(path=journal_path)
    transcript_codec = Transcript(path=transcript_path)
    for step in steps:
        journal_codec.append(step)
    for record in records:
        transcript_codec.append(record)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(_manifest(candidate.repo_id, candidate.revision, run_seed, recorded_on,
                             population, Path(stratum), Path(heldout), steps),
                    indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    return Measured(
        run_id=_run_id(recorded_on, candidate.repo_id, run_seed),
        candidate=candidate.repo_id,
        revision=candidate.revision,
        tasks=population,
        journal=journal_path,
        transcript=transcript_path,
        manifest=manifest_path,
    )


def _manifest(
    candidate: str,
    revision: str,
    run_seed: int,
    recorded_on: str,
    population: tuple[str, ...],
    stratum_path: Path,
    heldout_path: Path,
    steps: Sequence[Step],
) -> dict[str, Any]:
    """The run manifest — every field the instrument reads, and nothing measured.

    `prompt_sha256` is keyed by task id so a reader holding the committed tasks and this
    repository can recompute what each rollout was asked; `control` carries the per-draw
    control status; the document digests are the committed documents' own, read back from
    the bytes the loaders just vouched for.
    """
    return {
        "schema": MANIFEST_SCHEMA,
        "run_id": _run_id(recorded_on, candidate, run_seed),
        "recorded_on": recorded_on,
        "candidate": {"repo_id": candidate, "revision": revision},
        "run_seed": run_seed,
        "tasks": list(population),
        "stratum_document_digest": _recorded_digest(stratum_path),
        "heldout_document_digest": _recorded_digest(heldout_path),
        "prompt_sha256": {step.rollout.task_id: step.rollout.prompt_sha256 for step in steps},
        "control": {step.probe.task_id: step.probe.control.value for step in steps},
        "tool_versions": _tool_versions(),
    }


def _no_oracle(candidate: str, task: Task, reason: str) -> Rollout:
    """The record for a task whose oracle could not be built — the `score` shape.

    No prompt was rendered and nothing was generated, so `prompt_sha256` stays empty: a
    digest of a question nobody was asked is worse than a blank (`scoring._partial`).
    """
    return Rollout(
        candidate=candidate,
        task_id=task.task_id,
        outcome=Outcome.NO_ORACLE,
        strict=Status.UNVERIFIED,
        weak=Status.UNVERIFIED,
        verdict_kinds=(),
        executed=None,
        prompt_sha256="",
        detail=reason,
        generation_seconds=0.0,
        strict_seconds=0.0,
        weak_seconds=0.0,
    )


def _resolve_renderer(name: str) -> Renderer:
    """The renderer `--renderer` names — `line-range` by default, or the named refusal.

    A name that is neither of the two formats is refused rather than defaulted: a run
    that quietly posed a different format than its command named would write evidence
    no reader could trust.
    """
    try:
        return RENDERERS[name]
    except KeyError:
        raise UnknownRenderer(
            f"--renderer {name!r} is not a format this driver poses. The choice is "
            f"'line-range' (the default) or 'whole-function'; refused rather than "
            "defaulted, so a run's prompts always match the format its command named"
        ) from None


def _refuse_relative_workspace(workspace: Path | str) -> Path:
    """The absolute-path rule, enforced before anything else is read or written."""
    root = Path(workspace)
    if not root.is_absolute():
        raise RelativeWorkspace(
            f"--workspace must be an absolute path, got {str(workspace)!r}. A relative "
            "workspace resolves against wherever the process happened to be started, so "
            "the same command from two shells builds its sandboxes in two places — the "
            "runbook's known pitfall, refused here rather than recorded"
        )
    return root


def _run_id(recorded_on: str, candidate: str, run_seed: int) -> str:
    """The run's id: a digest over its declared identity, never the clock.

    sha256 rather than `hash` (the `attempt_seed` discipline: the builtin is salted per
    process), truncated because twelve hex characters identify a run without pretending
    to be a content hash of anything.
    """
    material = f"{recorded_on}\n{candidate}\n{run_seed}".encode()
    return f"measure-{hashlib.sha256(material).hexdigest()[:12]}"


def _recorded_digest(path: Path) -> str:
    """The document's own `document_digest` field, from the file the loader just vouched for.

    The loaders validate the digest and deliberately do not carry it
    (`heldout.py:243-247`); the manifest records the committed value so a reader can
    cross-check it against the document itself. Read back from the same bytes the loader
    validated — the field and the payload cannot disagree without the loader having
    refused.
    """
    raw: Any = json.loads(path.read_text(encoding="utf-8"))
    return str(raw["document_digest"])


def build_parser() -> argparse.ArgumentParser:
    """The CLI surface, built separately so tests can exercise it without running anything."""
    parser = argparse.ArgumentParser(
        prog="python -m whetstone.bakeoff.measure",
        description=(
            "Run the measurement over the spec's pinned 16-task population: one greedy "
            "completion per task, no verifier entry, the control arm intact on every "
            "draw required, and manifest + journal + transcript written only when the "
            "whole run has succeeded. The prompt format is a choice — the numbered "
            "listing by default, or the whole-function format."
        ),
    )
    parser.add_argument(
        "--tasks",
        type=Path,
        required=True,
        action="append",
        metavar="DIR",
        help="a private corpus directory, repeatable — the same union `run.py` reads. The "
        "pinned population is resolved against the loaded tasks by identity.",
    )
    parser.add_argument(
        "--stratum",
        type=Path,
        required=True,
        help="the committed stratum document (tasks/stratum/easier.json), read through its "
        "own fail-closed loader: unknown schema, drifted rule, broken document digest or "
        "hand-edited payload is a refusal.",
    )
    parser.add_argument(
        "--heldout",
        type=Path,
        required=True,
        help="the committed held-out document (tasks/heldout/source-b.json), read through "
        "its own fail-closed loader. Its members are never rollout targets.",
    )
    parser.add_argument(
        "--weights",
        type=Path,
        required=True,
        help="the weights root holding provenance.json; every recorded sha256 is re-checked "
        "before a token is generated. The provenance must name exactly one candidate.",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="NAME",
        help="measure only the candidate whose repo id contains NAME. A name matching "
        "nothing or matching several is refused, never resolved.",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        required=True,
        help="where sandboxes and provisioned environments are built. Must be an absolute "
        "path — a relative one is refused.",
    )
    parser.add_argument(
        "--journal",
        type=Path,
        help="where the journal goes. Defaults to runs/edit-contract-finding/journal.jsonl, "
        "which is gitignored.",
    )
    parser.add_argument(
        "--transcript",
        type=Path,
        help="where every prompt and completion is kept. Defaults to "
        "runs/edit-contract-finding/transcript.jsonl, which is gitignored — a completion "
        "quotes the user's own donor code back verbatim.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="where the run manifest goes. Defaults to "
        "runs/edit-contract-finding/manifest.json.",
    )
    parser.add_argument(
        "--recorded-on",
        required=True,
        help="the date the operator declares for this run. An input, never the clock.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        required=True,
        help="seconds allowed per control-arm verification. No default, matching the "
        "verifiers.",
    )
    parser.add_argument(
        "--renderer",
        default="line-range",
        help="the prompt format the run poses: 'line-range' (the default — the numbered "
        "listing, v0.17.0's behaviour) or 'whole-function' (this unit's EDIT/FUNCTION "
        "format). A name that is neither is refused, never defaulted.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse an operator's invocation and run it. Exit 0 only when all three files are written.

    A refusal prints its named reason to stderr and exits 2 — the `check-probe`/
    `locatability` shape — and writes nothing.
    """
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        measured = run_measurement(
            tasks=arguments.tasks,
            stratum=arguments.stratum,
            heldout=arguments.heldout,
            weights=arguments.weights,
            workspace=arguments.workspace,
            recorded_on=arguments.recorded_on,
            timeout=arguments.timeout,
            journal=arguments.journal,
            transcript=arguments.transcript,
            manifest=arguments.manifest,
            only=arguments.only,
            renderer=_resolve_renderer(arguments.renderer),
        )
    except REFUSALS as refusal:
        print(f"whetstone measure: {refusal}", file=sys.stderr)
        return 2
    print(
        f"measure: {measured.run_id} over {len(measured.tasks)} tasks, "
        f"candidate {measured.candidate}"
    )
    print(f"wrote {measured.journal}, {measured.transcript}, {measured.manifest}")
    return 0


__all__ = [
    "MANIFEST_SCHEMA",
    "MEASUREMENT_DETAIL",
    "REFUSALS",
    "RENDERERS",
    "RUN_SEED",
    "ControlNotIntact",
    "EmptyPopulation",
    "Measured",
    "NotOneCandidate",
    "PopulationMismatch",
    "RelativeWorkspace",
    "UnknownPopulationMember",
    "UnknownRenderer",
    "build_parser",
    "main",
    "run_measurement",
]


if __name__ == "__main__":
    raise SystemExit(main())