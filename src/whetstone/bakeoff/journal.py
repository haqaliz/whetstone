"""The checkpoint: an overnight run that is interrupted resumes, and resumes *identically*.

A bake-off is several candidates across 66 tasks, and every one of those pairs costs three
sandboxed pytest runs — two for the control arm, one for the reward — plus a model generation.
That is a night's work. Without a checkpoint, a crash at hour six costs the whole night and the
P1 base decision waits another day per interruption.

**The property that makes resuming safe is not "it finishes faster".** It is that a resumed run
produces *the record set an uninterrupted run would have produced*. Anything weaker and a night
that crashed once is a different experiment from the one `PREREGISTRATION.md` fixed, and the two
cannot be compared or pooled. Three decisions follow from that and none of them are style:

* **The unit is the (candidate, task) pair, complete.** A `Step` carries the control probe *and*
  the rollout, and it is written only once both are in hand. Checkpointing them separately would
  let a crash between the two leave a task whose rollout is on disk and whose control is not —
  which resumes into a run that scored a task it never proved the harness on, silently.
* **Nothing is recomputed that was recorded.** A replayed step is returned verbatim, not
  re-verified against the current tree. Re-running it would be the more "careful" choice and it
  would be wrong: it would make the resumed run's records depend on when it resumed.
* **A line that cannot be read is an error, never a skipped record.** A truncated final line is
  exactly what a killed process leaves behind, and dropping it quietly is the one failure mode
  that breaks the property above without anything appearing to go wrong — the run would re-do or
  omit a task and still report a full set.

**What is NOT here.** No counting, no totals, no ranking, and no report. The journal stores
records and hands them back; every number in the published baseline is derived from them
downstream, from one place, so there is exactly one definition of each.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from whetstone.bakeoff.control import Control, Probe
from whetstone.bakeoff.scoring import Outcome, Rollout
from whetstone.verify.verdict import Status

#: The key a step is filed and looked up under. Both halves are needed: one candidate's work on a
#: task says nothing about another's, and a journal keyed on the task alone would resume a
#: three-candidate bake-off having run one.
Key = tuple[str, str]


class JournalUnreadable(ValueError):
    """A checkpoint line could not be read back. Raised rather than skipped — see the docstring.

    Its own type so a caller can tell a corrupt checkpoint from a missing one: the second is the
    ordinary first night, and the first needs a human.
    """


@dataclass(frozen=True)
class Step:
    """One candidate's complete work on one task: what the harness proved, and what the base did.

    The two travel together because they are only meaningful together. A rollout says a base
    scored zero; the probe beside it says whether that zero was about the base. Separating them
    into two records would make it possible — and eventually routine — to read one without the
    other, which is the exact confusion the control arm exists to prevent.
    """

    #: What the control arm established about the harness on this task, in this run.
    probe: Probe

    #: What the candidate did on this task.
    rollout: Rollout

    @property
    def key(self) -> Key:
        """The (candidate, task) pair this step is filed under."""
        return (self.rollout.candidate, self.rollout.task_id)


@dataclass(frozen=True)
class Journal:
    """An append-only checkpoint file. One JSON object per line, one line per (candidate, task).

    JSON Lines rather than a single JSON document because the file is written *during* a run that
    may be killed at any moment: a document would have to be rewritten whole on every step, and a
    process killed mid-rewrite loses everything already recorded rather than the one line it was
    adding. Append-only for the same reason — nothing already on disk is ever touched again.

    Frozen: a journal names a file and nothing else. There is no in-memory index to go stale,
    which is why `replay` reads the file each time it is asked rather than caching.
    """

    #: The checkpoint file. Created, with its parents, on the first append.
    path: Path

    def append(self, step: Step) -> None:
        """Record `step`, durably enough that a killed process keeps it.

        Flushed on every call. A buffered journal is one whose last few steps exist only in the
        memory of the process that is about to be killed, which is the case it is written for.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_encode(step), sort_keys=True) + "\n")
            handle.flush()

    def replay(self) -> dict[Key, Step]:
        """Every step on disk, keyed by (candidate, task). An absent file is an empty run.

        A missing file is not an error: it is the first night. A file that exists and cannot be
        parsed *is* one — see the module docstring on why a dropped line is worse than a raise.

        A repeated key takes the **last** record, which is the append-only file's own answer: a
        step recorded twice means a task was somehow run twice, and the later run is the one whose
        result the sweep would have carried forward.
        """
        if not self.path.exists():
            return {}

        steps: dict[Key, Step] = {}
        for number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                step = _decode(json.loads(line))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                raise JournalUnreadable(
                    f"line {number} of the checkpoint at {str(self.path)!r} could not be read "
                    f"({type(exc).__name__}: {exc}). It is not skipped: a resumed run that "
                    f"quietly dropped a recorded step would re-run or omit that task and still "
                    f"report a full set, which is a different experiment reported as the same one"
                ) from exc
            steps[step.key] = step
        return steps


def _encode(step: Step) -> dict[str, Any]:
    """`step` as plain JSON types. Written out field by field, deliberately.

    `dataclasses.asdict` would be shorter and would silently carry any field added later into the
    file without a decoder for it — so a schema change would round-trip lossily rather than
    failing. Naming every field means a new one breaks this function first.
    """
    probe, rollout = step.probe, step.rollout
    return {
        "probe": {
            "candidate": probe.candidate,
            "task_id": probe.task_id,
            "control": probe.control.value,
            "without_patch": None if probe.without_patch is None else probe.without_patch.value,
            "with_reference": None if probe.with_reference is None else probe.with_reference.value,
            "detail": probe.detail,
            "seconds": probe.seconds,
        },
        "rollout": {
            "candidate": rollout.candidate,
            "task_id": rollout.task_id,
            "outcome": rollout.outcome.value,
            "strict": None if rollout.strict is None else rollout.strict.value,
            "weak": None if rollout.weak is None else rollout.weak.value,
            "verdict_kinds": list(rollout.verdict_kinds),
            "executed": rollout.executed,
            "prompt_sha256": rollout.prompt_sha256,
            "detail": rollout.detail,
            "generation_seconds": rollout.generation_seconds,
            "strict_seconds": rollout.strict_seconds,
            "weak_seconds": rollout.weak_seconds,
        },
    }


def _decode(raw: Any) -> Step:
    """The inverse of `_encode`, strict about everything. A missing key raises; nothing defaults.

    No `.get(..., default)` anywhere: a default would turn a field this writer never wrote into a
    plausible value, and the most plausible values here — `PASS`, `0` — are the ones that would
    invent a result. A `KeyError` is caught by `replay` and reported as a corrupt line.
    """
    probe, rollout = raw["probe"], raw["rollout"]
    return Step(
        probe=Probe(
            candidate=probe["candidate"],
            task_id=probe["task_id"],
            control=Control(probe["control"]),
            without_patch=_status(probe["without_patch"]),
            with_reference=_status(probe["with_reference"]),
            detail=probe["detail"],
            seconds=float(probe["seconds"]),
        ),
        rollout=Rollout(
            candidate=rollout["candidate"],
            task_id=rollout["task_id"],
            outcome=Outcome(rollout["outcome"]),
            strict=_status(rollout["strict"]),
            weak=_status(rollout["weak"]),
            verdict_kinds=tuple(rollout["verdict_kinds"]),
            executed=rollout["executed"],
            prompt_sha256=rollout["prompt_sha256"],
            detail=rollout["detail"],
            generation_seconds=float(rollout["generation_seconds"]),
            strict_seconds=float(rollout["strict_seconds"]),
            weak_seconds=float(rollout["weak_seconds"]),
        ),
    )


def _status(value: Any) -> Status | None:
    """`None` stays `None`; anything else must be a status this project knows.

    `None` is load-bearing and is not a missing value: on a rollout it means no verifier ran,
    which is a different fact from `UNVERIFIED` — the harness never tried, rather than tried and
    could not tell. Collapsing the two would inflate the UNVERIFIED count the pivot signal reads.
    """
    return None if value is None else Status(value)


__all__ = ["Journal", "JournalUnreadable", "Key", "Step"]
