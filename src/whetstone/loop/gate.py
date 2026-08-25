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

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from whetstone.bakeoff import report as bakeoff_report
from whetstone.bakeoff.scoring import Outcome

#: The outcomes that mean no verdict was reached — the sibling's own set, imported by
#: identity (`report._UNCOVERED`), so the gate's "unverified" term cannot drift from the
#: coverage definition every published count reduces against. They lower coverage and stay
#: in the denominator; they never vanish from it.
_UNCOVERED = bakeoff_report._UNCOVERED


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


__all__ = [
    "Exit",
    "GateDecision",
    "decide",
]