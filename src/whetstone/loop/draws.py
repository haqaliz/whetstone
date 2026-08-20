"""`K` draws per task, one control per task, and a checkpoint that resumes into the same records.

The bake-off's `sweep` runs the control arm and one rollout per task and stores them together,
which is exactly right for one greedy attempt. Rejection sampling needs `K` rollouts per task and
still needs the control — but it needs it **once**. Running `control.probe` per draw would cost
`K` extra sandboxed pytest pairs per task, and would be measuring the same thing `K` times: the
probe answers *"does this harness discriminate on this task, in this run, under this
interpreter"*, and none of those three change between draws of the same night.

So this module composes the same pieces in the shape sampling needs, and composes them **by
identity**: `control.probe`, `control.harness_status`, `scoring.score`, `journal.Step`,
`sweep.Sweep`. It defines no new record type for anything that already has one — a draw's result
*is* a `Sweep`, so `sweep.rankable` gates it unchanged and the report's `tally` could count it
without learning that sampling exists.

**One journal and one transcript per draw index, and that is forced rather than chosen.** Both
files are keyed `(candidate, task_id)` — `journal.Key`, `transcript.Key` — and `K` draws of one
task share that key exactly. A single file would make `replay()` return the last draw and silently
discard the other seven, which is the shape of failure that reports a full record set with holes
in it. Separate files keep both codecs untouched, keep resumption exact, and make the transcript's
own `attempt` field unambiguous: it numbers *retries within a draw*, and the draw index is the
file it lives in.

**Resuming reuses the recorded control, never a fresh one.** A night killed after four draws of a
task resumes with the probe those four were recorded against, because re-running it would make the
resumed run's records depend on when it resumed — the property `journal.py` exists to preserve,
applied one level up.

**Nothing here decides what a patch earns.** It arranges draws; the verdict is
`whetstone.verify`'s, taken by re-executing the task's own tests in a sandbox.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from whetstone.bakeoff.control import Probe, harness_status, probe
from whetstone.bakeoff.generator import Generator
from whetstone.bakeoff.journal import Journal, Step
from whetstone.bakeoff.retry import RETRY_BUDGET, Retry
from whetstone.bakeoff.run import Contract, Recording, Sealed
from whetstone.bakeoff.scoring import Interpreters, score
from whetstone.bakeoff.sweep import Sweep
from whetstone.bakeoff.transcript import Transcript
from whetstone.loop.sampling import Applied, Draw, Seeder, mlx_seeder
from whetstone.verify.task import Task

#: How a draw index becomes a filename component. Zero-padded so a directory listing sorts in
#: draw order rather than lexicographically — `draw-10` before `draw-2` is the kind of thing that
#: makes an operator read the wrong evidence at four in the morning.
_STEM = "draw-{attempt:02d}"


@dataclass(frozen=True)
class Drawn:
    """One draw index across every source: what it produced, under which seeds, from which files.

    `runs` is keyed by source (`"private"` / `"public"`) and holds a `Sweep` per source, so
    `sweep.rankable` gates each one by identity — a draw whose control arm proved nothing yields
    no training data, exactly as a bake-off whose control arm proved nothing yields no report.
    """

    #: Which draw of `K` this is. One-based.
    attempt: int

    #: Source name to the `Sweep` this draw produced over it.
    runs: Mapping[str, Sweep]

    #: Every seed applied during this draw, in application order.
    seeds: tuple[Applied, ...]

    #: The checkpoint this draw's steps were appended to.
    journal: Path

    #: The transcript this draw's completions were appended to.
    transcript: Path


def evidence_paths(root: Path, attempt: int) -> tuple[Path, Path]:
    """The (journal, transcript) pair for one draw index, under the run's evidence directory.

    A function rather than two f-strings at the call site, because the resumption story depends on
    a second invocation naming the same files, and two spellings of a path are two things that can
    disagree while both look right.
    """
    stem = _STEM.format(attempt=attempt)
    return root / f"{stem}.journal.jsonl", root / f"{stem}.transcript.jsonl"


def sample(
    *,
    candidate: str,
    sources: Mapping[str, Sequence[Task]],
    engine: Generator,
    contract: Contract,
    run_seed: int,
    draws: int,
    evidence: Path,
    sandbox_root: Path,
    timeout: float,
    interpreters: Interpreters,
    pool: Path | None = None,
    seeder: Seeder = mlx_seeder,
    retries: bool = False,
) -> tuple[Drawn, ...]:
    """Draw `draws` seeded attempts at every task in every source, with one control arm per task.

    `engine` is the loaded base, unwrapped. The wrapper chain is built here, per draw, and its
    order is the design:

        Draw → (Retry | Recording) → Sealed → engine

    `Sealed` innermost, so every prompt — first attempt and retry alike — passes the frozen-set
    check before it reaches the base (PRD M7b, and the retry vocabulary is frozen with it).
    `Retry`/`Recording` next, so the transcript sees every generation the run actually made.
    `Draw` **outermost**, so the seed is applied once per draw, before anything under it
    generates: a retry is a further draw from the stream that seed started, which is why a retry
    consumes no new seed and the (candidate, task, draw) → seed map stays one-to-one.

    Exceptions from the generator are not caught, for `sweep`'s own reason: an interrupted night
    is an interrupted night. It stops, having checkpointed every (task, draw) it completed, and
    resumes there.
    """
    if draws < 1:
        raise ValueError(
            f"a night must take at least one draw per task, got {draws}. Zero draws asks nothing "
            "and would report an empty dataset as a measured outcome"
        )

    evidence.mkdir(parents=True, exist_ok=True)
    journals: dict[int, Journal] = {}
    transcripts: dict[int, Transcript] = {}
    replayed: dict[int, Mapping[tuple[str, str], Step]] = {}
    for attempt in range(1, draws + 1):
        journal_path, transcript_path = evidence_paths(evidence, attempt)
        journals[attempt] = Journal(path=journal_path)
        transcripts[attempt] = Transcript(path=transcript_path)
        replayed[attempt] = journals[attempt].replay()

    asked: dict[int, Draw] = {
        attempt: _compose(
            engine,
            contract=contract,
            candidate=candidate,
            run_seed=run_seed,
            attempt=attempt,
            transcript=transcripts[attempt],
            seeder=seeder,
            retries=retries,
        )
        for attempt in range(1, draws + 1)
    }

    steps: dict[tuple[int, str], list[Step]] = {
        (attempt, source): [] for attempt in range(1, draws + 1) for source in sources
    }
    for source, tasks in sources.items():
        for task in tasks:
            recorded = {
                attempt: replayed[attempt].get((candidate, task.task_id))
                for attempt in range(1, draws + 1)
            }
            control = _control(
                recorded,
                candidate=candidate,
                task=task,
                sandbox_root=sandbox_root / source / task.task_id / "control",
                timeout=timeout,
                interpreters=interpreters,
                pool=pool,
            )
            for attempt in range(1, draws + 1):
                already = recorded[attempt]
                if already is not None:
                    # Returned verbatim, never re-verified: the resumed run must produce the
                    # record set an uninterrupted one would have (`journal.py`).
                    steps[(attempt, source)].append(already)
                    continue
                step = Step(
                    probe=control,
                    rollout=score(
                        candidate=candidate,
                        task=task,
                        generator=asked[attempt],
                        sandbox_root=(
                            sandbox_root
                            / source
                            / task.task_id
                            / _STEM.format(attempt=attempt)
                        ),
                        timeout=timeout,
                        interpreters=interpreters,
                        pool=pool,
                    ),
                )
                journals[attempt].append(step)
                steps[(attempt, source)].append(step)

    return tuple(
        Drawn(
            attempt=attempt,
            runs={
                source: Sweep(
                    candidate=candidate,
                    status=harness_status(step.probe for step in steps[(attempt, source)]),
                    steps=tuple(steps[(attempt, source)]),
                )
                for source in sources
            },
            seeds=tuple(asked[attempt].applied),
            journal=evidence_paths(evidence, attempt)[0],
            transcript=evidence_paths(evidence, attempt)[1],
        )
        for attempt in range(1, draws + 1)
    )


def _compose(
    engine: Generator,
    *,
    contract: Contract,
    candidate: str,
    run_seed: int,
    attempt: int,
    transcript: Transcript,
    seeder: Seeder,
    retries: bool,
) -> Draw:
    """Build one draw's wrapper chain. See `sample` for why the order is what it is."""
    inner: Generator = Sealed(inner=engine, contract=contract)
    if retries:
        inner = Retry(
            inner=inner,
            transcript=transcript,
            candidate=candidate,
            contract=contract.posed,
            budget=RETRY_BUDGET,
        )
    else:
        inner = Recording(
            inner=inner, transcript=transcript, candidate=candidate, contract=contract
        )
    return Draw(
        inner=inner,
        contract=contract.posed,
        run_seed=run_seed,
        attempt=attempt,
        seeder=seeder,
    )


def _control(
    recorded: Mapping[int, Step | None],
    *,
    candidate: str,
    task: Task,
    sandbox_root: Path,
    timeout: float,
    interpreters: Interpreters,
    pool: Path | None,
) -> Probe:
    """The control arm for one task: the recorded one if this night is resuming, else a fresh one.

    Reusing the recorded probe is not an optimisation. A resumed night must produce the records an
    uninterrupted one would have produced, and a second probe — taken hours later, against a
    checkout git has since garbage-collected, under an interpreter the cache rebuilt — is a
    different observation filed under the same task.
    """
    for step in recorded.values():
        if step is not None:
            return step.probe
    return probe(
        candidate=candidate,
        task=task,
        sandbox_root=sandbox_root,
        timeout=timeout,
        interpreters=interpreters,
        pool=pool,
    )


__all__ = ["Drawn", "evidence_paths", "sample"]
