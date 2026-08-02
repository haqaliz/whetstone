"""Which base P1 starts from — the rule, fixed in code before any count existed to read it off.

`PREREGISTRATION.md` § 7.3 is left open deliberately, and is closed *by* the bake-off report this
module feeds. That ordering is the whole difficulty: a selection rule written after the counts are
visible is post-hoc selection wearing the costume of rigour, which `PREREGISTRATION.md:171-177`
forbids by name. So the rule lives here, as code, ranked by one quantity fixed in the PRD (M7a),
and the report renders what it returns rather than deciding anything of its own.

**The rule is a ranking and never a bar.** It names no minimum a base must clear, because no such
minimum could be grounded before a baseline exists and `PREREGISTRATION.md:171` forbids one being
added once a number does. `Selection` therefore carries an order and a winner; there is nowhere in
this module for a threshold to live, which is the intended shape rather than an omission.

**The all-zero case is the one this module exists to get right.** A function that must return a
base will find a way to return one — the first candidate, or the smallest — and a rule that did
that would close § 7.3 on no evidence whatever *and* swallow `docs/ROADMAP.md:387-389`'s pivot
signal, the finding that matters most when it fires. The three facts are therefore separable
fields rather than one nullable answer: who was selected, whether § 7.3 is closed, and whether the
pivot signal fired. An all-zero bake-off is a legitimate result, and P1's base decision has to be
able to rest on it.

**Nothing here reads a record.** The rule ranks counts that the report has already derived from
`Rollout`s at the single place `solved` is defined. A second traversal of the records here would
be a second definition of the headline quantity, and `PREREGISTRATION.md` fixes it as one.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

#: What is said when a base was selected. A sentence rather than a flag because it is rendered
#: into the report verbatim, and the report has to say on what ground the base was chosen.
_ON_EVIDENCE = (
    "selected on the highest count of STRICT-PASS tasks over the declared source-B set, with "
    "ties broken toward the smaller base (PRD M7a). This is a ranking rule and names no bar."
)

#: What is said when none was. Names the consequence rather than only the fact, because an
#: all-zero bake-off is an instruction — change the stratum or the base, never the verifier.
_NO_EVIDENCE = (
    "no base is selected: every candidate solved zero, so there is no evidence to choose on. "
    "PREREGISTRATION.md § 7.3 stays open and the pivot signal at docs/ROADMAP.md:387-389 is "
    "reported as fired — the response is an easier task stratum or a larger base, never a "
    "looser verifier."
)


class NoContenders(ValueError):
    """No candidates were supplied, which is a usage error and not an all-zero result.

    Raised rather than falling through to the all-zero branch because the two mean opposite
    things: all-zero is a measurement that fired the pivot signal, and an empty bake-off measured
    nothing at all. Collapsing them would report the signal as fired on a run that never scored a
    task — the vacuous-pass shape `whetstone.tasks` already refuses for an empty task directory.
    """


@dataclass(frozen=True)
class Contender:
    """One base in the bake-off, and the pinned facts the rule and the report need about it."""

    #: The operator's identifier for this base. Carried through unread — nothing parses it — and
    #: used as the final, arbitrary-but-fixed tie-break key so the rule is total.
    candidate: str

    #: The exact revision scored. A pinned input (`PREREGISTRATION.md:131`), which is why any
    #: side-by-side presentation of two contenders crosses a changed pinned input.
    revision: str

    #: Declared parameter count, in billions. The tie-break key, and the only reason this module
    #: knows anything about size: `CLAUDE.md` #4 prefers what stays cheap as bases improve.
    parameters_billions: float


@dataclass(frozen=True)
class Ranked:
    """One candidate's line in the ranking: the count, and the denominator it is over.

    The denominator travels with the count because `PREREGISTRATION.md:157` requires it to and a
    count separated from its denominator is the bare proportion waiting to happen.
    """

    #: Who this line is about.
    contender: Contender

    #: STRICT `PASS` and nothing else (`PREREGISTRATION.md:86-90`). Derived by the report.
    solved: int

    #: The declared source-B set's size. Unread by the rule, rendered by the report.
    denominator: int


@dataclass(frozen=True)
class Selection:
    """The rule's whole answer: the order, the winner if there is one, and what follows.

    `selected is None` is not an error state and must not be rendered as one. It is the result of
    a bake-off in which nothing was solved, which is a finding with its own two consequences —
    both of which are separate fields here so that neither can be inferred from the other by
    downstream code that guessed.
    """

    #: The chosen base, or `None` when no candidate solved anything.
    selected: Contender | None

    #: Every candidate, in the rule's order, kept whether or not a base was selected: an all-zero
    #: ranking is still the record a reader needs.
    ranking: tuple[Ranked, ...]

    #: Whether this bake-off closes `PREREGISTRATION.md` § 7.3. False on an all-zero run — an item
    #: recorded as closed is one nobody revisits.
    closes_open_question_7_3: bool

    #: Whether `docs/ROADMAP.md:387-389`'s pivot signal fired. Reported, never suppressed: an
    #: unreported all-zero run reads as a weak field rather than as an instruction.
    pivot_signal_fired: bool

    #: The sentence the report renders beside the outcome, so the ground is published with it.
    reason: str


def select(entries: Iterable[Ranked]) -> Selection:
    """Rank `entries` and name the base, or name nothing and say why.

    Total over every non-empty input. The sort key is `(-solved, parameters_billions, candidate)`:
    the first two are M7a's rule, and the third is an arbitrary-but-fixed final key so that two
    candidates identical on both of M7a's terms still produce one answer, and the same answer
    whichever order they were listed in. Without it the winner would depend on input order, which
    is a property no measurement should have.
    """
    lines: Sequence[Ranked] = tuple(entries)
    if not lines:
        raise NoContenders(
            "no candidates were supplied to the selection rule, so nothing was measured. This "
            "is not an all-zero bake-off: an all-zero run scored every task and solved none, "
            "and reporting the pivot signal as fired for a run that scored nothing would be a "
            "finding about an experiment that never happened"
        )

    order = tuple(
        sorted(
            lines,
            key=lambda line: (
                -line.solved,
                line.contender.parameters_billions,
                line.contender.candidate,
            ),
        )
    )
    if all(line.solved == 0 for line in order):
        return Selection(
            selected=None,
            ranking=order,
            closes_open_question_7_3=False,
            pivot_signal_fired=True,
            reason=_NO_EVIDENCE,
        )
    return Selection(
        selected=order[0].contender,
        ranking=order,
        closes_open_question_7_3=True,
        pivot_signal_fired=False,
        reason=_ON_EVIDENCE,
    )


__all__ = ["Contender", "NoContenders", "Ranked", "Selection", "select"]
