"""The retry: a finite, sealed-friendly prompt builder and the budgeted wrapper that asks it.

The format-hardening wall (`p2-diff-autopsy/finding.md`) is that candidates write diffs git
refuses to parse. The validator (`diffcheck.py`) names the shape; this module converts — it
re-asks the model, bounded and only when the evidence says the attempt was convertible, with
a prompt the run's own seal will accept. That last constraint decides the design:

**The retry prompt is a pure function of `(first-attempt prompt, trigger)` (spec B1).** The
seal (`run.py:240-252`) refuses any prompt whose hash is not in the frozen `posed` map, so
every possible retry prompt must be pre-rendered at freeze time (`run.py:408-450`). A retry
prompt that carried the prior completion — the PRD R2 wording, amended here — would make the
prompt set unbounded and the seal unfreezable, so it is exactly: the first-attempt prompt,
plus the fixed `RETRY_INSTRUCTION`, plus one sentence from the finite diagnosis vocabulary
(`diffcheck.DIAGNOSES`). The 3B rollover lesson (`dig-transcripts.md:363-366`) is discharged
by the validator instead: loop/rollover shapes are non-triggers by the autopsy's own
precedence.

**The wrapper is a `Generator` wrapper, so the one-method seam is not widened.** `Retry`
calls `inner.generate` once per attempt and returns the last completion; it decides after
each attempt whether another draw may help, and stops at `1 + budget` total generations
(B4: budget 2 — at most two retries). The decision is `trigger_of(classify_completion(text))`
by default — the taxonomy imported by identity, never reimplemented — so it is a pure
function of the completion and the wrapper is replayable from a stored transcript (PRD R3).

**Every attempt is recorded, with the attempt/decision fields aspect 1 added.** The wrapper
holds the recording pieces — the `Transcript`, the candidate, and the frozen `posed` map —
and writes one record per attempt *after* its generation returns: `decision == "retry"` when
a later attempt follows, `"graded"` when it is the decided record for its key. The pieces
are optional: without a transcript the wrapper is the same decide-loop, recording nothing.
The `task_id` for a retry prompt comes from the same mechanism `run.Recording` uses — the
`posed` lookup — and retry prompts were posed under the first-attempt prompt's task at
freeze time, so every attempt of a task files under that task. A record is written only
after the generation it records has returned: a prompt refused by the seal raises through
`inner.generate` before any record exists for it, and no further attempts are made (the
record-follows-generation rule, `transcript.py:223-235`).

**Off the reward path, and off the driver path.** Nothing here imports `mlx`, the driver
(`run.py`), or `scoring`; its own no-inference AST walk (`tests/bakeoff/test_retry.py`)
refuses all of them. This module may not be imported by anything under `verify/` or
`tasks/` (the package docstring).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

from whetstone.bakeoff.diffcheck import (
    Trigger,
    classify_completion,
    diagnosis_of,
    trigger_of,
)
from whetstone.bakeoff.generator import Generator

#: How many retries a (candidate, task) may get (spec B4). One contract field's value; the
#: wrapper's default and the driver's composition both read it from here so they cannot
#: disagree about the budget.
RETRY_BUDGET = 2

#: The fixed retry instruction: re-ask for a single fenced diff and state the one rule that
#: converts the parse refusals — the hunk header's declared counts must match the body. A
#: constant by construction: it is part of every retry prompt, and a template edit here is a
#: contract edit that voids any run frozen before it (PRD M7b applied to the retry
#: vocabulary). No format placeholder and no digit, asserted in `test_retry.py` — the
#: finiteness rule of `diffcheck.py:98-127`, restated for the instruction.
RETRY_INSTRUCTION = (
    "The diff you wrote could not be parsed, so it was never applied. Reply again with a "
    "single unified diff and nothing else, inside one fenced block tagged `diff`. Every "
    "hunk header's declared line counts must match the hunk body exactly."
)


def retry_prompt(prompt: str, trigger: Trigger) -> str:
    """The second draw of `prompt`, told which shape to fix — and nothing else.

    Exactly three parts, in a fixed order: the first-attempt prompt, the fixed instruction,
    and the one diagnosis sentence for `trigger`. The prior completion is deliberately
    absent (B1): any completion-derived content would make the prompt set unbounded, and
    the seal can only accept prompts frozen before the run. Pure by construction, so the
    freeze can pre-render every retry prompt a run may issue and the seal's contract hash
    covers them all (PRD D8).
    """
    return prompt + "\n\n" + RETRY_INSTRUCTION + "\n" + diagnosis_of(trigger)


def retry_template_sha256() -> str:
    """A digest of the retry template — the instruction plus the sorted diagnosis sentences.

    The contract field `contract-report` publishes (`retry_template_sha256`): the value a
    reader recomputes from the published vocabulary to check that a run's retries were
    posed under the declared template. The sentences are sorted so the digest does not
    depend on the trigger enum's declaration order, and the construction is spelled in the
    test (`test_retry.py`) so a reader can reproduce it with stdlib alone. A sentence or
    instruction edit moves the digest — a template change voids the run, like any other.
    """
    material = "\n".join(
        (RETRY_INSTRUCTION, *(sorted(diagnosis_of(trigger) for trigger in Trigger)))
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _decide(completion: str) -> Trigger | None:
    """The default decision: the validator's trigger mapping over the autopsy's verdict.

    Imported, never reimplemented — the trigger decision must be the taxonomy itself, or the
    online retry and the offline autopsy could disagree about the same bytes
    (`diffcheck.py:1-31`).
    """
    return trigger_of(classify_completion(completion))


@dataclass(frozen=True)
class Retry:
    """A `Generator` wrapper: re-ask, bounded and trigger-gated, and decide the last draw.

    The one-method seam is not widened: this is a wrapper, like `run.Sealed` and
    `run.Recording`, so `sweep` and `score` learn nothing about retries. `generate(prompt)`
    runs the first attempt, decides after it, and — while the verdict is a trigger and the
    budget (B4: `RETRY_BUDGET` retries, `1 + budget` total generations) remains — re-asks
    with `retry_prompt(first, trigger)`, each retry named for its own verdict's trigger and
    built from the first-attempt prompt (B1). The last completion is returned; earlier ones
    are superseded, and the record-follows-generation rule means a prompt refused by the
    seal raises `ContractChanged` out of `inner.generate` with no record and no further
    attempts.

    The wrapper decides only; it does not catch. An exception from `inner` propagates
    untouched — the `sweep` discipline (`sweep.py:109-112`), because an interrupted run must
    stop rather than produce a full-looking record set with holes in it.

    Deterministic by construction: the decision is a pure function of the completion, the
    inner is greedy, and nothing here reads the clock or the filesystem — two runs over the
    same stub table ask the same questions in the same order (asserted in `test_retry.py`).
    """

    #: What actually generates. Called once per attempt, never between attempts.
    inner: Generator

    #: How many retries a (candidate, task) may get; the loop stops at `1 + budget`
    #: total generations even if every verdict triggers. The contract field's value,
    #: one home (`RETRY_BUDGET`).
    budget: int = RETRY_BUDGET

    #: The retry decision: a completion in, a trigger or `None` out. Defaults to the
    #: validator's mapping over the autopsy's verdict — the taxonomy by identity, never
    #: reimplemented.
    decide: Callable[[str], Trigger | None] = _decide

    def generate(self, prompt: str) -> str:
        """The decided completion: attempt, decide, retry while triggered and within budget.

        The first prompt is kept as the base of every retry prompt (B1) — each retry is a
        second draw of the same question, told which shape to fix, and the whole retry
        vocabulary is pre-rendered from this one prompt at freeze time (PRD D8).
        """
        first = prompt
        completion = self.inner.generate(prompt)
        trigger = self.decide(completion)
        attempts = 1
        while trigger is not None and attempts < 1 + self.budget:
            prompt = retry_prompt(first, trigger)
            completion = self.inner.generate(prompt)
            attempts += 1
            trigger = self.decide(completion)
        return completion


__all__ = [
    "RETRY_BUDGET",
    "RETRY_INSTRUCTION",
    "Retry",
    "retry_prompt",
    "retry_template_sha256",
]
