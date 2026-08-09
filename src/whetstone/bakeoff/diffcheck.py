"""The online validator: name the failure shape, decide the retry, and never touch the diff.

The autopsy (`autopsy.py`) classifies a stored completion into exactly one fine cause, and its
walk was corrected until it agreed with git on every stored record (`finding.md:69-71`). This
module consults that taxonomy **at grading time** — before the verifier — so a retry can be
triggered on the convertible shapes and never on the others. The taxonomy is imported, never
copied: `classify_completion` and the cause and death enums come from `autopsy.py` by identity
(asserted in `tests/bakeoff/test_diffcheck.py`), so an online verdict and the offline autopsy
cannot disagree about the same bytes.

**The trigger decision is the taxonomy, not a second git pass.** The fuzzy margin between
`hunk-dies-early` and `hunk-count-mismatch` was settled *as* the taxonomy
(`finding.md:69-71`); running a fresh `git apply` at trigger time would introduce a second
opinion on exactly that margin. Git is consulted in the measured-arm pre-analysis only
(`prd.md` R5), never in the online trigger decision.

**This module classifies; it never authors.** A diff that edits a held test passes through
unmodified and reaches STRICT, which refuses it as `patch-scope` — stripping, re-anchoring or
re-counting the held hunk here would convert a caught cheat into an uncaught one, and the
never-repair rule is the extractor's own (`patch.py:20-35`). The validator has no authoring
power and no task context: it is handed the autopsy's verdict alone, so it cannot even see
`test_blobs` to be tempted with.

**Truncation is inferred, never claimed measured.** `end-of-output` is a shape
(`finding.md:81-84`), not a measured token cap, and it is never a trigger: a retry would burn
budget on missing content.

Stdlib only, plus the autopsy's own objects imported by identity. No model, no network, no
`mlx`, no `run.py` (its own AST walk in `tests/bakeoff/test_diffcheck.py` refuses all of
them).
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Literal

from whetstone.bakeoff.autopsy import (
    AutopsyResult,
    DeathKind,
    FineCause,
    classify_completion,
)

#: What became of an attempt: "retry" when a later record follows it, "graded" when it is the
#: decided record for its key. The transcript's own vocabulary (`transcript.py`), spelled here
#: as the literal the retry wrapper will decide with — two values, closed by type.
Decision = Literal["retry", "graded"]


class Trigger(str, Enum):
    """The retry triggers: the parse-refusal shapes a fresh draw can fix (`prd.md` D3).

    Trigger causes only — every member of this enum is a shape the retry policy may retry.
    The non-triggers (`well-formed`, `im-start-loop`, `no-diff`, `unrecognised-shape`, the
    `end-of-output` death) are deliberately absent: a trigger list that could not retry
    `well-formed` would not be the policy, and a list that could would be an unfixable
    contradiction, so only the retry-eligible shapes are named here.
    """

    HUNK_DIES_EARLY = "hunk-dies-early"
    HUNK_COUNT_MISMATCH = "hunk-count-mismatch"
    HEADER_WITHOUT_HUNK = "header-without-hunk"


#: The deaths inside a hunk body that a retry can fix: the walk stopped on a bare line (a
#: pasted source line) or on the closing fence — both shapes a fresh draw carrying the whole
#: prior completion can complete. `END_OF_OUTPUT` is deliberately absent: budget truncation is
#: inferred from shape, never measured (`finding.md:81-84`), and a retry would spend another
#: draw on content the budget never reached.
_RETRYABLE_DEATHS = frozenset({DeathKind.BARE_LINE.value, DeathKind.FENCE_CUT.value})


def trigger_of(
    result: AutopsyResult, *, header_without_hunk_is_trigger: bool = False
) -> Trigger | None:
    """The retry decision for one classified completion: a trigger, or `None` (no retry).

    Triggers are the parse-refusal shapes a fresh draw can fix (`prd.md` D3):
    `hunk-count-mismatch`, and a first-hunk death on a bare line or the closing fence.
    Everything else is a non-trigger: `well-formed` (it must reach git and be graded),
    `im-start-loop` (nothing content-side converts it), `end-of-output` (truncation-inferred,
    never retried), `no-diff`, `unrecognised-shape`, and `header-without-hunk` — unless the
    measured-arm pre-analysis (`prd.md` R5) has evidence that flips it, which is exactly what
    `header_without_hunk_is_trigger` is for. Nothing else changes the decision: the mapping
    is a pure function of the verdict, so it is replayable from a stored transcript (PRD R3).
    """
    if result.cause is FineCause.HUNK_COUNT_MISMATCH:
        return Trigger.HUNK_COUNT_MISMATCH
    if result.cause is FineCause.HUNK_DIES_EARLY and result.detail in _RETRYABLE_DEATHS:
        return Trigger.HUNK_DIES_EARLY
    if result.cause is FineCause.HEADER_WITHOUT_HUNK and header_without_hunk_is_trigger:
        return Trigger.HEADER_WITHOUT_HUNK
    return None


#: The finite, fixed diagnosis vocabulary (PRD D8): one constant sentence per trigger. The
#: retry prompt is the first-attempt prompt plus a fixed retry instruction plus exactly one
#: sentence from this set, and every possible retry prompt is pre-rendered at freeze time
#: (`run.py:240-252`) — so the sentences are constants by construction. No format argument
#: and no digit may appear in any sentence: a number would have to be derived from the
#: completion, which would make the prompt set unbounded and the seal unfreezable. The
#: finiteness rule is asserted in `tests/bakeoff/test_diffcheck.py`.
DIAGNOSES: Mapping[Trigger, str] = {
    Trigger.HUNK_DIES_EARLY: (
        "The patch stops mid-hunk with counts remaining; rewrite it as one complete patch."
    ),
    Trigger.HUNK_COUNT_MISMATCH: (
        "The patch's hunks do not match their declared counts; rewrite it as one complete patch."
    ),
    Trigger.HEADER_WITHOUT_HUNK: (
        "The patch names a file but writes no hunk; rewrite it as one complete patch."
    ),
}


def diagnosis_of(trigger: Trigger) -> str:
    """The one fixed sentence the retry prompt appends for `trigger`.

    Total over `Trigger`: every trigger has a sentence, because every retry prompt must be
    pre-rendered at freeze time — a trigger without a sentence is a retry that cannot be
    posed. The sentences are the vocabulary: finite, fixed, no completion-derived content
    (`prd.md` D8). A sentence change is a template change — it moves a contract field and
    voids the run, like any other template edit.
    """
    return DIAGNOSES[trigger]


__all__ = [
    "DIAGNOSES",
    "Decision",
    "Trigger",
    "classify_completion",
    "diagnosis_of",
    "trigger_of",
]
