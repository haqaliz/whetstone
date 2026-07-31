"""The rule that picks a base — written before any number exists for it to be tempted by.

`PREREGISTRATION.md` § 7.3 is closed *by* the bake-off report, which means the rule that closes
it has to exist before the report does. A rule chosen after the counts are visible is post-hoc
selection wearing the costume of rigour, and `PREREGISTRATION.md:171-177` forbids exactly that.
So the rule is code, and this file is the code's contract: highest STRICT-PASS count on the
declared source-B set, ties broken toward the **smaller** base, and — the case that must not be
an afterthought — **all candidates at zero selects nothing**.

**The degenerate case is the one worth reading.** An all-zero bake-off is a legitimate result and
P1's base decision has to be able to rest on it. The failure it invites is a rule that quietly
returns *someone* — the first candidate, or the smallest — because a function that must return a
base will find a way to. That would close § 7.3 on no evidence at all and would swallow
`docs/ROADMAP.md:387-389`'s pivot signal, which is the finding that matters most when it fires.
So `Selection` carries three separable facts — who was selected, whether § 7.3 is closed, and
whether the pivot signal fired — and this file asserts all three in every case.

**No model, no records, no I/O.** The rule ranks counts. Everything here is synthetic.
"""

from __future__ import annotations

import pytest

from whetstone.bakeoff.selection import Contender, NoContenders, Ranked, select

#: The declared source-B set's size, used as every denominator here. The real corpus is 66 tasks
#: (`tasks/README.md`); the rule never reads the denominator, so the value only has to be honest
#: about the shape of the input.
DENOMINATOR = 66


def _ranked(candidate: str, *, solved: int, billions: float) -> Ranked:
    """One candidate's line in the ranking: who, how big, and how many it solved."""
    return Ranked(
        contender=Contender(
            candidate=candidate, revision=f"rev-of-{candidate}", parameters_billions=billions
        ),
        solved=solved,
        denominator=DENOMINATOR,
    )


def test_the_highest_strict_pass_count_is_selected() -> None:
    """A clear winner is selected on count alone, and § 7.3 is recorded as closed.

    Size is deliberately *anti-correlated* with the count here — the winner is the largest
    candidate — so a rule that had quietly preferred the smaller base would be caught rather
    than agreeing with the answer by luck.
    """
    chosen = select(
        [
            _ranked("small", solved=2, billions=3.0),
            _ranked("large", solved=9, billions=14.0),
            _ranked("middle", solved=5, billions=7.0),
        ]
    )

    assert chosen.selected is not None and chosen.selected.candidate == "large", (
        "WHY THIS IS A FAILURE: the rule fixed in the PRD (M7a) is the highest count of "
        "STRICT-PASS tasks on the declared source-B set, and it did not select the candidate "
        f"with that count. Got {chosen.selected!r}"
    )
    assert [line.contender.candidate for line in chosen.ranking] == ["large", "middle", "small"], (
        "WHY THIS IS A FAILURE: the ranking is the report's ordering and must be descending by "
        f"count. Got {[line.contender.candidate for line in chosen.ranking]}"
    )
    assert chosen.closes_open_question_7_3 and not chosen.pivot_signal_fired, (
        "WHY THIS IS A FAILURE: a bake-off that selected a base on evidence closes "
        "PREREGISTRATION.md § 7.3 and does not fire the pivot signal. Reporting the signal as "
        "fired here would make docs/ROADMAP.md:387-389 mean nothing when it fires for real"
    )


def test_a_tie_is_broken_toward_the_smaller_base() -> None:
    """Equal counts select the smaller candidate — the ground stated in M7a, not a later reading.

    The larger candidate is listed **first** in the input, so a rule that had merely kept
    insertion order would return it and this test would catch that rather than the tie-break.
    """
    chosen = select(
        [
            _ranked("large", solved=4, billions=14.0),
            _ranked("small", solved=4, billions=3.0),
        ]
    )

    assert chosen.selected is not None and chosen.selected.candidate == "small", (
        "WHY THIS IS A FAILURE: two candidates solved the same count and the rule did not break "
        "the tie toward the smaller base. M7a fixes that direction in advance, on the stated "
        "ground that a smaller base is cheaper to train — deciding it afterwards would be "
        f"choosing while looking at the result. Got {chosen.selected!r}"
    )
    assert chosen.closes_open_question_7_3, (
        "WHY THIS IS A FAILURE: a tie is still evidence — some base solved something — so § 7.3 "
        "is closed by it"
    )


def test_a_tie_on_count_and_size_is_still_total_and_deterministic() -> None:
    """Two candidates identical on both keys must still produce one answer, and the same one.

    The rule has to be **total**: a bake-off that hit this case and raised, or returned whichever
    candidate a set iterated first, would leave § 7.3 open for a reason that has nothing to do
    with the evidence. The final key is the candidate identifier, ascending, which is arbitrary
    but fixed and disclosed — and the same both ways round, which is what this asserts.
    """
    alpha = _ranked("alpha", solved=4, billions=7.0)
    bravo = _ranked("bravo", solved=4, billions=7.0)
    forwards = select([bravo, alpha])
    backwards = select([alpha, bravo])

    assert forwards.selected is not None and forwards.selected.candidate == "alpha", (
        "WHY THIS IS A FAILURE: candidates tied on count and on size, and the rule did not fall "
        f"through to its final, declared key. Got {forwards.selected!r}"
    )
    assert forwards == backwards, (
        "WHY THIS IS A FAILURE: the same two candidates in the other order produced a different "
        "selection, so which base P1 starts from would depend on the order they were listed in. "
        f"Got {forwards!r} and {backwards!r}"
    )


def test_all_zero_selects_nothing_leaves_7_3_open_and_fires_the_pivot_signal() -> None:
    """The degenerate case: no base is selected, and the finding is reported rather than hidden.

    This is the case the rule exists to get right. Every candidate solved zero, so there is no
    evidence to close § 7.3 with, and `docs/ROADMAP.md:387-389` says what that means: expert
    iteration has nothing to bootstrap from, and the response is an easier task stratum or a
    larger base — never a looser verifier. A rule that returned the smallest candidate here
    would report a decision that no measurement supports.
    """
    chosen = select(
        [
            _ranked("small", solved=0, billions=3.0),
            _ranked("large", solved=0, billions=14.0),
        ]
    )

    assert chosen.selected is None, (
        "WHY THIS IS A FAILURE: every candidate solved zero and the rule still named a base. "
        "That closes PREREGISTRATION.md § 7.3 on no evidence whatever, which is precisely the "
        f"post-hoc selection the pre-registration exists to prevent. Got {chosen.selected!r}"
    )
    assert not chosen.closes_open_question_7_3, (
        "WHY THIS IS A FAILURE: § 7.3 was recorded as closed by a bake-off that selected nothing. "
        "An item recorded closed is one nobody revisits"
    )
    assert chosen.pivot_signal_fired, (
        "WHY THIS IS A FAILURE: no candidate solved anything and the pivot signal "
        "(docs/ROADMAP.md:387-389) was not reported as fired. That signal is the whole point of "
        "running a bake-off that might come back empty — unreported, an all-zero result reads as "
        "a weak field rather than as the instruction to change the task stratum or the base"
    )
    assert [line.contender.candidate for line in chosen.ranking] == ["small", "large"], (
        "WHY THIS IS A FAILURE: selecting nothing must not discard the ranking. The per-candidate "
        f"records are still the finding a reader needs. Got {chosen.ranking!r}"
    )


def test_a_bake_off_with_no_candidates_is_refused_rather_than_answered() -> None:
    """No candidates is a usage error, not an all-zero result — the two mean opposite things.

    An empty input reaching the all-zero branch would report the pivot signal as fired on a run
    that never scored anything, which is the vacuous-pass shape `whetstone.tasks` already refuses
    for an empty task directory.
    """
    with pytest.raises(NoContenders) as refusal:
        select([])

    assert "no candidates" in str(refusal.value).lower(), (
        "WHY THIS IS A FAILURE: the refusal must say what was wrong, or an operator reads it as "
        f"the pivot signal. Got {str(refusal.value)!r}"
    )
