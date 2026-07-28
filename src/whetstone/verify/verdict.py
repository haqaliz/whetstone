"""The Verdict, its five statuses, and the reduction that combines them.

Every verdict Whetstone emits is a `Verdict` — a fact grounded in something concrete (a
pytest exit status, the set of node ids actually executed, a rejected patch), never an
opinion and never a model's judgement. A single task is many sub-checks, so we need one rule
to fold them into a single status, and `reduce` is it: worst-status-wins.

The ordering is the delicate part, and it is not what you would reach for first.
**UNVERIFIED ranks ABOVE PASS and WARN** (below only FAIL). This is the honesty contract —
"UNVERIFIED is never rendered as PASS" — expressed as the shape of the reduction rather than
a rule bolted on top: a task with one sub-check we could not verify and one that passed
reduces to UNVERIFIED, because "we could not check this" is a stronger statement about the
task than "this part looked fine". Rank UNVERIFIED below PASS and a task we failed to verify
is reported clean; downstream that is a reward paid for work nobody checked, and a promotion
gate counting it as a win. `tests/test_verdict.py` guards the ordering against exactly that.

The reduction reads `status` and nothing else. No check-specific code lives here, and none
should: a future sub-check folds in unchanged by emitting a `Verdict`.

Pure data and logic: no model, no network, no execution. Those live in the checks that build
Verdicts, not in the Verdict itself.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any


class Status(str, Enum):
    """The honest verdict statuses. `str` mixin so a Status serializes as its name.

    The first four are the scored statuses — the ones a task can reduce to, ordered by
    `_RANK` below. `NOT_COVERED` is different in kind and is deliberately listed apart.
    """

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    UNVERIFIED = "UNVERIFIED"

    #: **Sub-verdict only.** A dimension the verifier structurally does not observe — not an
    #: abstention but a coverage boundary. UNVERIFIED says "we tried to check this and could
    #: not"; NOT_COVERED says "this was never inside what Whetstone claims to check", and
    #: folding the second into worst-status-wins would let one permanently unobservable
    #: dimension sink every task the verifier evaluated perfectly. `reduce` therefore filters
    #: it out before ranking, and a task's reduced status can never be NOT_COVERED —
    #: downstream readers depend on that (see `reduce`). It is never rendered as PASS: a
    #: surface that shows a status must also show what was outside coverage.
    NOT_COVERED = "NOT_COVERED"


# Worst-status-wins severity. FAIL > UNVERIFIED > WARN > PASS. UNVERIFIED outranking PASS
# and WARN is the load-bearing choice — see the module docstring. Change this and you
# change the honesty contract.
#
# NOT_COVERED carries a rank only so a future caller that ranks a status without filtering
# first raises nothing mysterious — it is never reached through `reduce`, which drops it
# beforehand. The value is a floor, NOT a "loses to everything" ordering that would make
# `reduce([NOT_COVERED])` return it; that shape is precisely the false PASS this status
# must not create, and it is why the filter, not the rank, is the mechanism.
_RANK: dict[Status, int] = {
    Status.NOT_COVERED: -1,
    Status.PASS: 0,
    Status.WARN: 1,
    Status.UNVERIFIED: 2,
    Status.FAIL: 3,
}


@dataclass(frozen=True)
class Verdict:
    """One grounded sub-check result.

    `kind` names the check that produced it ("pytest", "executed-set", "patch-scope", …).
    There is no `axis`: Whetstone has one verdict axis, and an always-constant field is a
    lie about the structure. `observed` and `expected` carry the concrete grounding — the
    node ids that ran versus the ones the task declared, the paths a patch touched versus
    the operator-held set, whatever the check compared. They are typed permissively because
    different checks ground differently; a reader inspects them knowing which `kind`
    produced the verdict. `message` is the human-readable one-line summary.
    """

    kind: str
    status: Status
    observed: Any | None
    expected: Any | None
    message: str


def reduce(verdicts: Sequence[Verdict]) -> Status:
    """Fold sub-check verdicts into one status by worst-status-wins.

    NOT_COVERED sub-verdicts are dropped BEFORE ranking. They state a coverage boundary, not
    a finding, so they must not lower (or raise) a task — and this filter, rather than a
    losing rank, is what guarantees the reduced status is never NOT_COVERED. That guarantee
    is load-bearing for every consumer downstream: anything that folds a not-FAIL status
    into "decided", anything fail-closed on an unknown status, and any denominator that sums
    every outcome would each read a leaked NOT_COVERED as a verified clean task.

    An empty set — including one that is empty only AFTER the filter — reduces to
    UNVERIFIED, not PASS and not NOT_COVERED: a task with no applicable checks verified
    nothing, and nothing-verified is never a pass.
    """
    scored = [v.status for v in verdicts if v.status is not Status.NOT_COVERED]
    if not scored:
        return Status.UNVERIFIED
    return max(scored, key=lambda s: _RANK[s])
