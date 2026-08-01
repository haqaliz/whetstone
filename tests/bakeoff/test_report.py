"""The first document in this project that makes a claim about a model, held to what was pledged.

`PREREGISTRATION.md` was committed before any number existed, and its value is entirely in that
ordering. This file is where that value is either kept or spent: it asserts, against synthetic
record sets, that the bake-off report says which measurement it is, refuses the shapes the
pre-registration exists to prevent, and carries every bound it promised a reader would see.

**The load-bearing assertion is about identity, not about arithmetic.** A bake-off number and the
pinned baseline number look alike — both are "tasks solved by an untrained base, over a
denominator" — and one of them may be measured exactly once (`PREREGISTRATION.md:129-132`). If the
report does not say, in text, that it is base selection and that the once-only measurement is
**not** spent by it, then the first honest reader to find it will reasonably conclude the baseline
has been taken, and the project's single most constrained measurement is gone with nobody having
decided to spend it. So the statement is required, and its absence fails the build.

**Three assertions here are adversarial and were watched failing against plausible wrong writers**
— a template carrying a minimum-to-qualify line, a tally that dropped `UNVERIFIED` records instead
of leaving them in the denominator, and a source-A section that reported one instance as a
proportion with its result ahead of its funnel. Each of those is what a reasonable person writes
when nobody is watching, which is why each is watched.

**Nothing here runs a model, a sandbox, a verifier, or the network.** Every `Rollout`, `Probe` and
`Sweep` below is constructed by hand. Nothing is written outside `tmp_path`: the real report is
produced by a real run, and this suite must leave `reports/` absent.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from whetstone.bakeoff.control import Control, Probe
from whetstone.bakeoff.journal import Step
from whetstone.bakeoff.report import (
    Entrant,
    Funnel,
    GenerationContract,
    IncompleteProvenance,
    MissingSource,
    Provenance,
    ScoredDevSubset,
    build_report,
    funnel_from_ledger,
    tally,
    write,
)
from whetstone.bakeoff.scoring import Outcome, Rollout
from whetstone.bakeoff.selection import Contender
from whetstone.bakeoff.sweep import Sweep
from whetstone.verify.verdict import Status

#: The repository root, for the two committed files this suite reads rather than fabricates.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: The one source-A instance that survived the four-gate filter (`tasks/README.md`).
FLASK = "pallets__flask-4045"

#: What each outcome implies about the two verifiers when a test does not say otherwise. Written
#: out rather than inferred so a reader can see that `OUT_OF_SCOPE` is the shape `N` counts: STRICT
#: refuses the patch at `patch-scope`, and a weaker check that merely ran the tests would have
#: taken the edited test file at face value and called it a win.
VERDICTS: dict[Outcome, tuple[Status | None, Status | None]] = {
    Outcome.SOLVED: (Status.PASS, Status.PASS),
    Outcome.NOT_SOLVED: (Status.FAIL, Status.FAIL),
    Outcome.NOT_APPLIED: (Status.FAIL, Status.FAIL),
    Outcome.OUT_OF_SCOPE: (Status.FAIL, Status.PASS),
    Outcome.NO_DIFF: (None, None),
    Outcome.UNVERIFIED: (Status.UNVERIFIED, Status.UNVERIFIED),
    Outcome.UNPROVISIONED: (Status.UNVERIFIED, None),
    # No prompt was rendered and no verifier ran: the generation contract could not be built for
    # the task, so both statuses are the honest unknown rather than anything a base earned.
    Outcome.NO_ORACLE: (Status.UNVERIFIED, Status.UNVERIFIED),
}


def _rollout(candidate: str, task_id: str, outcome: Outcome) -> Rollout:
    """One synthetic record, with the verdict pair its outcome implies."""
    strict, weak = VERDICTS[outcome]
    return Rollout(
        candidate=candidate,
        task_id=task_id,
        outcome=outcome,
        strict=strict,
        weak=weak,
        verdict_kinds=("tests",),
        executed=3,
        prompt_sha256="0" * 64,
        detail="",
        generation_seconds=2.0,
        strict_seconds=4.0,
        weak_seconds=1.0,
    )


def _records(candidate: str, outcomes: Sequence[Outcome], *, first: int = 1) -> list[Rollout]:
    """A record per outcome, task ids numbered from `first` so two sources cannot collide."""
    return [
        _rollout(candidate, f"task-{index}", outcome)
        for index, outcome in enumerate(outcomes, start=first)
    ]


def _sweep(
    candidate: str, records: Sequence[Rollout], *, control: Control = Control.INTACT
) -> Sweep:
    """A completed run over `records`, with the control arm answering `control` on every task."""
    steps = tuple(
        Step(
            probe=Probe(
                candidate=candidate,
                task_id=record.task_id,
                control=control,
                without_patch=Status.FAIL,
                with_reference=Status.PASS,
                detail="",
                seconds=3.0,
            ),
            rollout=record,
        )
        for record in records
    )
    status = Status.PASS if control is Control.INTACT else Status.UNVERIFIED
    return Sweep(candidate=candidate, status=status, steps=steps)


def _entrant(
    candidate: str,
    *,
    billions: float,
    private: Sequence[Outcome],
    public: Outcome = Outcome.NOT_SOLVED,
) -> Entrant:
    """One base's whole bake-off: its source-B run, and its one source-A instance."""
    return Entrant(
        contender=Contender(
            candidate=candidate,
            revision=f"sha-{candidate}",
            parameters_billions=billions,
        ),
        private=_sweep(candidate, _records(candidate, private)),
        public=_sweep(candidate, [_rollout(candidate, FLASK, public)]),
    )


#: The four-gate funnel as `tasks/public/ineligible.json` records it. Passed in rather than read
#: from disk by the writer, so the document is a pure function of its inputs — with
#: `test_the_funnel_matches_the_committed_rejection_ledger` holding these values to the ledger.
FUNNEL = Funnel(
    considered=300,
    eligible=(FLASK,),
    refused=299,
    by_gate=(("format", 192), ("environment", 106), ("collectability", 1), ("liveness", 0)),
)

PROVENANCE = Provenance(
    task_set="source B, 66 tasks, tasks/local-ledger.json",
    environment_pins="each task's manifest declares its own == pins and interpreter",
    seeds="0",
    tool_versions={"git": "2.43.0", "python": "3.12.13", "uv": "0.5.11"},
    recorded_on="2026-07-31",
)

CONTRACT = GenerationContract(
    prompt_sha256="a" * 64,
    sampler="greedy",
    max_tokens=600,
    extractor_version="1",
    dev_subset=("dev-a", "dev-b"),
)


def _build(entrants: Sequence[Entrant], **kwargs: object) -> str:
    """The rendered markdown for `entrants`, with the standard provenance unless overridden."""
    report = build_report(
        entrants=entrants,
        provenance=kwargs.get("provenance", PROVENANCE),  # type: ignore[arg-type]
        contract=kwargs.get("contract", CONTRACT),  # type: ignore[arg-type]
        funnel=kwargs.get("funnel", FUNNEL),  # type: ignore[arg-type]
    )
    return report.markdown


def _standard() -> list[Entrant]:
    """Three candidates with a clear winner, one caught out-of-scope patch, and one unverified."""
    return [
        _entrant(
            "small",
            billions=3.0,
            private=[Outcome.SOLVED, Outcome.NOT_SOLVED, Outcome.NO_DIFF, Outcome.UNVERIFIED],
        ),
        _entrant(
            "large",
            billions=14.0,
            private=[Outcome.SOLVED, Outcome.SOLVED, Outcome.OUT_OF_SCOPE, Outcome.UNVERIFIED],
            public=Outcome.SOLVED,
        ),
        _entrant(
            "middle",
            billions=7.0,
            private=[Outcome.SOLVED, Outcome.NOT_APPLIED, Outcome.NOT_SOLVED, Outcome.UNVERIFIED],
        ),
    ]


# --------------------------------------------------------------------------------------------
# AC1 / AC2 — which measurement this is, and which costume it may not wear
# --------------------------------------------------------------------------------------------


def test_the_report_states_it_is_base_selection_and_not_the_pinned_baseline() -> None:
    """The load-bearing statement: this is base selection, and the once-only measurement stands.

    Both halves are required and both are asserted. Saying only "this is base selection" leaves a
    reader to work out for themselves whether `PREREGISTRATION.md:129-132`'s *measured once,
    re-measured never* has been spent — and the reason it has not is not obvious from the number:
    it is that the pinned baseline is scored on the held-out split, which does not exist yet
    (§ 7.1, open until P3). A report that omits that is a report whose most expensive consequence
    is invisible.
    """
    text = _build(_standard()).lower()

    assert "base selection" in text, (
        "WHY THIS IS A FAILURE: the report does not say what measurement it is. A bake-off count "
        "and the pinned baseline count are the same shape — an untrained base's solved tasks over "
        "a denominator — so an unlabelled one will be read as whichever the reader expected"
    )
    assert "not the pinned baseline" in text, (
        "WHY THIS IS A FAILURE: the report does not deny being the pinned baseline of "
        "PREREGISTRATION.md:126-128. Absent the denial, the first reader to cite this document "
        "cites it as the baseline, and the baseline may be measured exactly once"
    )
    assert "measured once, re-measured never" in text and "not spent" in text, (
        "WHY THIS IS A FAILURE: the report does not state that PREREGISTRATION.md:129-132's "
        "once-only rule is unspent by it. That is the consequence a reader cannot recover from "
        "the number, and the whole reason the identity statement above is not merely tidy"
    )
    assert "7.1" in text, (
        "WHY THIS IS A FAILURE: the report claims the baseline is unmeasured without giving the "
        "reason — the held-out split it would be scored on does not exist (PREREGISTRATION.md "
        "§ 7.1). An unexplained claim of that size reads as an assertion of convenience"
    )


def test_the_p4_headline_skeleton_is_refused() -> None:
    """The report may not instantiate `PREREGISTRATION.md:69-72`, nor call its own set held-out.

    *(adversarial)* The skeleton is reserved for one figure: the change in STRICT-PASS count
    between the pinned baseline and the final checkpoint, on the held-out split. A selection
    number printed into that template is not mislabelled by accident — it is a bake-off number
    wearing the P4 headline's costume, and it is exactly the substitution the pre-registration
    exists to prevent. Absence is asserted, and the report's own denial is asserted with it so
    that an emptied document cannot satisfy the check.
    """
    text = _build(_standard())

    assert not re.search(r"\+\s*\d+\s+of\s+\d+", text), (
        "WHY THIS IS A FAILURE: the report renders a signed count over a denominator, which is "
        "the first line of the P4 headline skeleton (PREREGISTRATION.md:69-72). This document "
        "reports no delta at all: `delta` is defined only as solved_final - solved_baseline, and "
        "neither term exists"
    )
    for banned in ("held-out tasks", "at baseline", "at final"):
        assert banned not in text.lower(), (
            f"WHY THIS IS A FAILURE: the report contains {banned!r}, a fragment of the P4 headline "
            "skeleton. The skeleton names a baseline/final pair on a held-out split; none of those "
            "three things exists here"
        )
    for line in text.splitlines():
        if "held-out" in line.lower():
            assert "not" in line.lower(), (
                "WHY THIS IS A FAILURE: the report mentions a held-out split other than to deny "
                "having one. Its scored set is the declared source-B set, and describing it as "
                f"held-out would claim a split that PREREGISTRATION.md § 7.1 leaves open. Got: "
                f"{line.strip()!r}"
            )
    assert "not a held-out split" in text.lower(), (
        "WHY THIS IS A FAILURE: every check above asserts an absence, which an empty document "
        "satisfies. The report must also state the denial, so a reader sees the omission is "
        "deliberate"
    )


# --------------------------------------------------------------------------------------------
# AC3 — a ranking, never a bar
# --------------------------------------------------------------------------------------------

#: The one sentence in the report permitted to name a threshold — because it refuses one. Every
#: other occurrence of these tokens is a bar being introduced after a number exists, which
#: `PREREGISTRATION.md:171` forbids outright.
THRESHOLD_DENIAL = (
    "This report ranks and does not threshold: it names no minimum any candidate must clear, "
    "and PREREGISTRATION.md:171 forbids one being added now that a number exists."
)

#: Words a minimum-to-qualify claim is spelled with. `at least` and `qualif` catch the two
#: phrasings that do not use the word itself.
THRESHOLD_TOKENS = (
    "threshold",
    "minimum",
    "at least",
    "qualif",
    "cut-off",
    "cutoff",
    "must clear",
    "success criterion",
)


def test_the_report_names_no_threshold() -> None:
    """*(adversarial)* A ranking is emitted and no bar is, in any spelling.

    Watched failing against a template carrying a `Minimum to qualify` line — the shape a
    reasonable person adds to make a ranking feel decisive. `PREREGISTRATION.md:171` pre-registers
    no numeric success threshold *and forbids one being added once a number exists*, which is
    precisely the moment this report arrives at.
    """
    text = _build(_standard())

    assert THRESHOLD_DENIAL in text, (
        "WHY THIS IS A FAILURE: the report does not state that it names no bar. The absence check "
        "below is satisfied by an empty document; this is the control that makes it mean something"
    )
    remainder = text.replace(THRESHOLD_DENIAL, "").lower()
    found = [token for token in THRESHOLD_TOKENS if token in remainder]
    assert not found, (
        f"WHY THIS IS A FAILURE: the report states a minimum-to-qualify claim: {found}. "
        "PREREGISTRATION.md:171 pre-registers no success threshold and forbids one being added "
        "once a number exists. A bar set while looking at the result is post-hoc selection "
        "wearing the costume of rigour"
    )


# --------------------------------------------------------------------------------------------
# AC4 / AC5 — the denominator, and what may never leave it
# --------------------------------------------------------------------------------------------


def test_unverified_lowers_coverage_and_never_leaves_the_denominator() -> None:
    """*(adversarial)* An unverified task is counted, uncovered, and in neither solved nor failed.

    Watched failing against a tally that filtered unverified records out before counting — which
    produces the hundred-out-of-hundred-by-construction lie `PREREGISTRATION.md:111-114` refuses by
    name, and produces it while every other number in the document stays internally consistent.
    The invariant asserted last is the one that makes the lie impossible: the three disjoint counts
    must sum to the denominator, so a dropped record has nowhere to go.
    """
    records = _records(
        "small",
        [
            Outcome.SOLVED,
            Outcome.NOT_SOLVED,
            Outcome.UNVERIFIED,
            Outcome.UNPROVISIONED,
        ],
    )
    counted = tally("small", records)

    assert counted.denominator == 4, (
        "WHY THIS IS A FAILURE: two of the four tasks ended without a verdict and the denominator "
        f"shrank to {counted.denominator}. PREREGISTRATION.md:111-114 refuses that by name: "
        "unverified tasks lower coverage, they never leave the denominator"
    )
    assert (counted.solved, counted.covered, counted.unverified) == (1, 2, 2), (
        "WHY THIS IS A FAILURE: coverage did not fall by the number of tasks that reached no "
        f"verdict. Got solved={counted.solved}, covered={counted.covered}, "
        f"unverified={counted.unverified} over a denominator of {counted.denominator}"
    )
    assert counted.failed == 1, (
        "WHY THIS IS A FAILURE: an unverified task was charged to the failed count. UNVERIFIED is "
        "never a win, and it is not a loss either — it is the absence of a comparison, and "
        f"folding it into either column invents one. Got failed={counted.failed}"
    )
    assert counted.solved + counted.failed + counted.unverified == counted.denominator, (
        "WHY THIS IS A FAILURE: the three disjoint counts do not sum to the denominator, so a "
        "record was dropped, double-counted, or invented somewhere between the run and the report"
    )


def test_a_task_the_contract_could_not_be_built_for_is_not_charged_to_the_base() -> None:
    """*(adversarial)* `NO_ORACLE` is an absent question, not a failed answer.

    A task whose source files could not be derived is never posed and never generated for: no
    donor on this machine, no donor commit at all, a fix touching an operator-held path, or files
    over the character budget. Counting it among the failures would publish "this base could not
    fix it" about a task the base was never shown — the same lie as charging an unbuildable
    environment to the candidate, arriving through the prompt rather than through the venv.

    It stays in the denominator for the same reason `UNVERIFIED` does: dropping it produces the
    hundred-out-of-hundred-by-construction figure `PREREGISTRATION.md:111-114` refuses by name.
    """
    records = _records("small", [Outcome.SOLVED, Outcome.NOT_SOLVED, Outcome.NO_ORACLE])
    counted = tally("small", records)

    assert counted.denominator == 3, (
        "WHY THIS IS A FAILURE: the unposable task left the denominator, which is the coverage "
        f"lie the pre-registration refuses by name. Got {counted.denominator}"
    )
    assert (counted.solved, counted.failed, counted.unverified) == (1, 1, 1), (
        "WHY THIS IS A FAILURE: a task the generation contract could not be built for was counted "
        "as something the base got wrong. The base was never shown it — no prompt was rendered "
        f"and no verifier ran. Got solved={counted.solved}, failed={counted.failed}, "
        f"unverified={counted.unverified}"
    )


def test_the_report_discloses_that_the_base_was_shown_which_files_to_change() -> None:
    """The oracle setting is a handicap on what the number means, so the number carries it.

    The prompt shows the base the non-test files the fix touches, which is what makes writing a
    unified diff possible at all — without them every rollout is charged `NOT_APPLIED` against a
    file the base has never seen. It also *tells the base where the answer is*, because that file
    set is derived from the reference patch. A count published without saying so reads as
    performance on a bug report, which is a harder task than the one that was actually scored.
    """
    document = _build(_standard())

    assert "oracle" in document.lower(), (
        "WHY THIS IS A FAILURE: the report never names the retrieval setting it was measured "
        "under. A reader comparing this figure to a published SWE-bench number would be "
        "comparing two different tasks"
    )
    assert "upper bound" in document.lower(), (
        "WHY THIS IS A FAILURE: the disclosure does not say which way the handicap points. "
        "Showing the base which files to change makes the task easier, so the figure bounds what "
        "the same base would do from the bug report alone rather than estimating it"
    )


def test_every_count_in_the_report_carries_its_denominator() -> None:
    """No bare proportion anywhere (`PREREGISTRATION.md:157`), in any spelling.

    Asserted over the rendered text rather than over the tallies, because the tally is a pair of
    integers and it is the *rendering* that can drop one of them. The corpus is small enough that
    a rate moves by large-looking amounts when a single task flips, which reads as a measurement
    and is mostly noise — which is why the pre-registration reports counts and this asserts it.
    """
    text = _build(_standard())

    for spelling in ("%", "percent"):
        assert spelling not in text.lower(), (
            f"WHY THIS IS A FAILURE: the report states a proportion ({spelling!r}). "
            "PREREGISTRATION.md:157 requires every rate to carry its denominator, and on a "
            "66-task corpus a bare proportion manufactures precision the denominator cannot "
            "support"
        )
    figures = re.findall(r"^\| `?(solved|coverage|unverified|N)`? *\|(.+)\|$", text, re.MULTILINE)
    assert figures, (
        "WHY THIS IS A FAILURE: this test found no per-candidate figure rows at all, so its "
        "assertions below would pass over an empty table"
    )
    for label, row in figures:
        cells = [cell.strip() for cell in row.split("|") if cell.strip()]
        for cell in cells:
            assert re.fullmatch(r"\d+ of \d+", cell), (
                f"WHY THIS IS A FAILURE: the {label!r} row renders {cell!r}, which is a number "
                "without its denominator. Every count in this report is published over the set "
                "it was counted on (PREREGISTRATION.md:157)"
            )


# --------------------------------------------------------------------------------------------
# AC6 / AC6a — N, framed exactly as pre-registered, and bounded twice
# --------------------------------------------------------------------------------------------


def test_n_is_counted_and_framed_exactly_as_pre_registered() -> None:
    """`N := count(WEAK == PASS and STRICT == FAIL)`, rendered verbatim and bounded.

    The verbatim sentence is not decoration. `N` is the project's own reward-hacking figure and
    the temptation on it runs both ways — a looser framing overstates what the strictness proved,
    and a quieter one hides it. `PREREGISTRATION.md:102` fixes the words; `:211-220` fixes the
    bound that must sit beside them, because cheats 6 and 10 survive into any reported `N`.
    """
    counted = tally("large", _records("large", [Outcome.SOLVED, Outcome.OUT_OF_SCOPE]))
    assert counted.weaker_wins == 1, (
        "WHY THIS IS A FAILURE: one rollout had WEAK == PASS and STRICT == FAIL and N did not "
        f"count it. That is the definition at PREREGISTRATION.md:99, verbatim. Got "
        f"{counted.weaker_wins}"
    )

    text = _build(_standard())
    assert "1 rollouts a weaker check would have scored as wins." in text, (
        "WHY THIS IS A FAILURE: N is not rendered with the sentence PREREGISTRATION.md:102 fixes "
        "for it. The wording is pre-registered precisely so that neither a later editor nor a "
        "later result can soften or sharpen what the number claims"
    )
    residual = "N counts what the strictness caught. It is not a claim that nothing got through."
    assert residual in text, (
        "WHY THIS IS A FAILURE: N is published without the residual bound at "
        "PREREGISTRATION.md:211-220. Cheats 6 and 10 are accepted by both verifiers, so an "
        "unbounded N reads as a completeness claim the verifier has never made"
    )
    assert "cheat 6" in text.lower() and "cheat 10" in text.lower(), (
        "WHY THIS IS A FAILURE: the residual bound is stated without naming which cheats survive, "
        "leaving a reader unable to check it against docs/ROADMAP.md § 3"
    )
    assert "baseline `N`" in text and "no final `N` exists" in text, (
        "WHY THIS IS A FAILURE: N is published without being labelled a baseline N. "
        "PREREGISTRATION.md:107-109 requires both N values to be published together, and the "
        "final one does not exist — an unlabelled N here would be read as the pair"
    )


#: The one sentence permitted to discuss intent — because it refuses to claim any. A patch that
#: edited a genuinely-buggy test in good faith still counts toward `N` (`PREREGISTRATION.md:103`).
INTENT_DENIAL = (
    "This is a claim about what the strictness caught and not about intent: intent is not "
    "observable, so no claim to measure it is made here."
)


def test_n_carries_no_intent_claim() -> None:
    """*(adversarial)* `N` says what the reward refused, never why a base did it.

    The slide is small and one-directional: "N patches tried to edit the tests" is more readable
    than "N rollouts a weaker check would have scored as wins", and it is a claim about a mind
    nobody observed.
    """
    text = _build(_standard()).replace(INTENT_DENIAL, "")
    found = [
        token
        for token in ("intent", "deliberate", "on purpose", "tried to", "wanted to", "meant to")
        if token in text.lower()
    ]
    assert not found, (
        f"WHY THIS IS A FAILURE: the report makes a claim about the policy's intent: {found}. "
        "PREREGISTRATION.md:102-105 rules that out — a patch that edited a genuinely-buggy test "
        "in good faith counts toward N exactly as one that gamed the check does, and nothing in "
        "the record distinguishes them"
    )
    assert INTENT_DENIAL in _build(_standard()), (
        "WHY THIS IS A FAILURE: the absence check above is satisfied by an empty document. The "
        "report must state that it makes no intent claim, so the omission reads as deliberate"
    )


def test_n_is_disclosed_as_a_floor_because_the_contract_discourages_what_it_counts() -> None:
    """AC6a: the generation contract tells every candidate the patch-scope rule, so `N` is a floor.

    Telling every base the same thing is the right call for comparability, and it is also why this
    `N` is not a natural rate: it is measured under a contract that discourages precisely the
    behaviour it counts. Two consequences have to be published with it, because a reader who
    learns them later learns that something was withheld — that an `N` under a different contract
    is not comparable to this one, and that this is a *second* bound alongside the residual one.
    """
    text = _build(_standard()).lower()

    assert "floor" in text, (
        "WHY THIS IS A FAILURE: N is published without being called a floor. The generation "
        "contract discloses the patch-scope rule to every candidate, so the count is a lower "
        "bound under a disclosing contract rather than a rate"
    )
    assert "not comparable" in text, (
        "WHY THIS IS A FAILURE: the report does not state that an N measured under a different "
        "generation contract is not comparable to this one. The generation contract is an "
        "unpinned input (PRD M8, R5), and this is the first concrete demonstration that it moves "
        "a pre-registered number"
    )
    assert "second bound" in text, (
        "WHY THIS IS A FAILURE: the floor disclosure is not tied to the residual bound at "
        "PREREGISTRATION.md:211-220. There are two separate bounds on N — what the strictness "
        "missed, and what the contract suppressed — and a reader shown one will assume it is all"
    )


# --------------------------------------------------------------------------------------------
# AC7 / AC8 — source A per-instance, funnel first; and both sources together
# --------------------------------------------------------------------------------------------


def test_source_a_is_per_instance_with_its_funnel_before_the_result() -> None:
    """*(adversarial)* One instance of 300, named, with the denominator shown before the outcome.

    Watched failing against a template that reported source A as a proportion with its result
    ahead of its funnel. One instance is not a public benchmark set, and a reader who sees the
    outcome first has already formed an impression by the time they reach the denominator that
    would have stopped them forming it. `PREREGISTRATION.md:149-155` fixes the order for that
    reason, and fixes that no rate and no delta may be stated for it.
    """
    text = _build(_standard())

    assert FLASK in text, (
        "WHY THIS IS A FAILURE: source A is reported without naming the instance. Unnamed, one "
        "instance reads as a set"
    )
    funnel_at = text.index("1 of 300")
    result_at = text.index("Result for")
    assert funnel_at < result_at, (
        "WHY THIS IS A FAILURE: source A's result is printed before its four-gate funnel. The "
        "funnel is the denominator, and PREREGISTRATION.md:153-154 requires a reader to see it "
        f"before the result. Funnel at {funnel_at}, result at {result_at}"
    )
    for figure in ("299", "192", "106"):
        assert figure in text, (
            f"WHY THIS IS A FAILURE: the four-gate funnel omits {figure}. The deliverable in "
            "source A is the filter and its rejection ledger, not the instance count, and a "
            "funnel missing a gate is not a funnel"
        )
    assert "not a measurement" in text.lower(), (
        "WHY THIS IS A FAILURE: the report presents a single-instance outcome without stating "
        "that a delta on one instance is not a measurement (PREREGISTRATION.md:154-155)"
    )


def test_a_report_carrying_only_one_source_is_refused() -> None:
    """Both sources or nothing (`PREREGISTRATION.md:142-143`).

    Neither is published alone and neither is held back pending the other, regardless of which
    looks better — because the choice of which to publish, made once a result is visible, is the
    whole failure mode. Enforced as a refusal rather than as a warning: a warning is a thing a
    caller reads past on the night the private source disappoints.
    """
    entrant = _entrant("small", billions=3.0, private=[Outcome.SOLVED])
    only_private = Entrant(
        contender=entrant.contender,
        private=entrant.private,
        public=Sweep(candidate="small", status=Status.PASS, steps=()),
    )

    with pytest.raises(MissingSource) as refusal:
        build_report(
            entrants=[only_private],
            provenance=PROVENANCE,
            contract=CONTRACT,
            funnel=FUNNEL,
        )
    assert "source a" in str(refusal.value).lower(), (
        f"WHY THIS IS A FAILURE: the refusal does not name the missing source. Got "
        f"{str(refusal.value)!r}"
    )


def test_a_disagreement_between_the_sources_is_reported_as_a_finding() -> None:
    """Public gain with private flat is the contamination signature, and it is published as one.

    `PREREGISTRATION.md:145-147` refuses to resolve a disagreement by choosing the flattering
    source. The fixture below is that exact shape: a candidate that solves its source-A instance
    and nothing on source B.
    """
    entrants = [
        _entrant(
            "large",
            billions=14.0,
            private=[Outcome.NOT_SOLVED, Outcome.NOT_SOLVED],
            public=Outcome.SOLVED,
        ),
        _entrant("small", billions=3.0, private=[Outcome.SOLVED], public=Outcome.NOT_SOLVED),
    ]
    text = _build(entrants).lower()

    assert "disagree" in text, (
        "WHY THIS IS A FAILURE: one candidate solved its public instance and nothing private, "
        "which is the contamination signature PREREGISTRATION.md:145-147 pre-registers as itself "
        "worth publishing, and the report says nothing about it"
    )


# --------------------------------------------------------------------------------------------
# AC9 — the selection rule, as the report renders it
# --------------------------------------------------------------------------------------------


def test_an_all_zero_bake_off_selects_nothing_and_reports_the_pivot_signal() -> None:
    """The degenerate run, rendered: no base named, § 7.3 left open, pivot signal published.

    The rule itself is asserted in `test_selection.py`; this is the report's obligation to
    *publish* what it returned rather than quietly printing the top of a ranking of zeroes.
    """
    entrants = [
        _entrant("small", billions=3.0, private=[Outcome.NOT_SOLVED, Outcome.NO_DIFF]),
        _entrant("large", billions=14.0, private=[Outcome.NO_DIFF, Outcome.NO_DIFF]),
    ]
    text = _build(entrants).lower()

    assert "no base is selected" in text, (
        "WHY THIS IS A FAILURE: every candidate solved zero and the report still names a base. "
        "A selection published on no evidence closes PREREGISTRATION.md § 7.3 on nothing"
    )
    assert "7.3" in text and "stays open" in text, (
        "WHY THIS IS A FAILURE: the report does not record that PREREGISTRATION.md § 7.3 remains "
        "open. An item recorded as closed is one nobody revisits"
    )
    assert "pivot signal" in text and "fired" in text, (
        "WHY THIS IS A FAILURE: the pivot signal at docs/ROADMAP.md:387-389 fired and was not "
        "published. Unreported, an all-zero bake-off reads as a weak field rather than as the "
        "instruction it is — an easier task stratum or a larger base, never a looser verifier"
    )


# --------------------------------------------------------------------------------------------
# AC10 / AC11 — non-comparability, and the provenance block
# --------------------------------------------------------------------------------------------

#: `PREREGISTRATION.md:136-137`, quoted. Required beside any side-by-side presentation, because
#: two candidates differ in model revision, which is a pinned input (`:131`).
NON_COMPARABILITY = (
    "A figure measured on one side of a changed pinned input may not be compared with one "
    "measured on the other."
)


def test_the_ranking_carries_the_non_comparability_sentence() -> None:
    """Candidates differ in a pinned input, so the table is a ranking and says what it is not.

    The ranking is permitted — `PREREGISTRATION.md` fixes a delta as one quantity across a
    *fixed* base, and this table crosses the revision. What is refused is presenting the rows as
    comparable figures without the sentence that says they are not.
    """
    text = _build(_standard())

    assert NON_COMPARABILITY in text, (
        "WHY THIS IS A FAILURE: the report presents several candidates side by side without "
        "PREREGISTRATION.md:136-137's sentence. Each row was measured under a different model "
        "revision, which is a pinned input (:131), so the rows are ranked against each other and "
        "are not comparable figures"
    )
    assert text.index(NON_COMPARABILITY) < text.index("| Rank |"), (
        "WHY THIS IS A FAILURE: the non-comparability sentence is printed after the table it "
        "bounds. A bound a reader meets after the number is a bound they meet too late"
    )


def test_the_provenance_block_carries_all_five_pinned_inputs_and_the_contract() -> None:
    """`PREREGISTRATION.md:131-132`'s five, plus the generation contract, disclosed as not a sixth.

    The generation contract is the interesting field. It determines the number — the prompt
    template, the sampler, the token budget and the extractor all move it — and it is *not* among
    the five pinned inputs. Publishing it inside the block without that distinction would quietly
    promote it; leaving it out would hide the input this project already knows moves `N`.
    """
    text = _build(_standard())

    for field in ("revision", "task set", "environment pins", "seeds", "tool versions"):
        assert field in text.lower(), (
            f"WHY THIS IS A FAILURE: the provenance block omits {field!r}, one of the five pinned "
            "inputs at PREREGISTRATION.md:131-132. A missing pinned input makes it unknowable "
            "later whether a second measurement crossed a change to it"
        )
    for value in ("sha-large", "0.5.11", "3.12.13", "greedy", "600", "a" * 64):
        assert value in text, (
            f"WHY THIS IS A FAILURE: the provenance block names a field without its value "
            f"({value!r} missing), which records that somebody thought about it rather than what "
            "it was"
        )
    assert "not among the five" in text.lower(), (
        "WHY THIS IS A FAILURE: the generation contract is published in the provenance block "
        "without being distinguished from the five pinned inputs. It determines the number and is "
        "not pinned — a reader who assumes it is pinned will read a later, non-comparable N as "
        "comparable"
    )


def test_a_provenance_block_missing_a_field_is_refused() -> None:
    """An incomplete block fails the build rather than rendering a blank.

    A rendered blank is worse than a refusal: it looks like a field that was considered, and it
    survives review because the block *looks* complete.
    """
    with pytest.raises(IncompleteProvenance) as refusal:
        build_report(
            entrants=_standard(),
            provenance=Provenance(
                task_set="source B, 66 tasks",
                environment_pins="",
                seeds="0",
                tool_versions={"git": "2.43.0"},
                recorded_on="2026-07-31",
            ),
            contract=CONTRACT,
            funnel=FUNNEL,
        )
    assert "environment_pins" in str(refusal.value), (
        f"WHY THIS IS A FAILURE: the refusal does not name the empty field. Got "
        f"{str(refusal.value)!r}"
    )


def test_a_dev_subset_task_that_reached_the_scored_set_is_refused() -> None:
    """M7b: the tasks the contract was developed against may not be scored by it.

    Iterating the prompt and the extractor against a task and then scoring that task is
    optimising on the outcome. The dev subset is declared in the contract and excluded from the
    run; this refuses the case where the exclusion did not happen, because the report is the last
    place it can be noticed.
    """
    leaked = _entrant("small", billions=3.0, private=[Outcome.SOLVED])
    contaminated = Entrant(
        contender=leaked.contender,
        private=_sweep("small", [_rollout("small", "dev-a", Outcome.SOLVED)]),
        public=leaked.public,
    )

    with pytest.raises(ScoredDevSubset) as refusal:
        build_report(
            entrants=[contaminated],
            provenance=PROVENANCE,
            contract=CONTRACT,
            funnel=FUNNEL,
        )
    assert "dev-a" in str(refusal.value), (
        f"WHY THIS IS A FAILURE: the refusal does not name the leaked task. Got "
        f"{str(refusal.value)!r}"
    )


# --------------------------------------------------------------------------------------------
# AC12 — the writer is deterministic
# --------------------------------------------------------------------------------------------


def _payload() -> str:
    """The JSON sidecar for a fixed synthetic bake-off. Called in-process and in a subprocess."""
    return build_report(
        entrants=_standard(), provenance=PROVENANCE, contract=CONTRACT, funnel=FUNNEL
    ).payload


def test_the_same_records_and_inputs_produce_a_byte_identical_payload(tmp_path: Path) -> None:
    """Twice in this process, and twice more in fresh ones under different hash seeds.

    A report that differs run to run cannot be the committed evidence for a decision, because a
    reader who regenerates it and gets different bytes has no way to tell a re-render from a
    re-measurement. The subprocess half is not ceremony: mapping iteration order and set
    iteration order are the two things that vary across processes and not within one, and
    `PYTHONHASHSEED` is what makes that variation actually happen rather than merely be possible.
    """
    first = write(
        build_report(
            entrants=_standard(), provenance=PROVENANCE, contract=CONTRACT, funnel=FUNNEL
        ),
        tmp_path / "one",
    )
    second = write(
        build_report(
            entrants=_standard(), provenance=PROVENANCE, contract=CONTRACT, funnel=FUNNEL
        ),
        tmp_path / "two",
    )
    for left, right in zip(first, second, strict=True):
        assert left.read_bytes() == right.read_bytes(), (
            f"WHY THIS IS A FAILURE: two runs over identical records produced different bytes in "
            f"{left.name}. Committed evidence that cannot be regenerated is not evidence"
        )

    program = (
        f"import sys; sys.path.insert(0, {str(REPO_ROOT / 'tests')!r});"
        "from bakeoff.test_report import _payload; sys.stdout.write(_payload())"
    )
    outputs = {
        seed: subprocess.run(
            [sys.executable, "-c", program],
            capture_output=True,
            check=True,
            text=True,
            env={"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": seed},
        ).stdout
        for seed in ("0", "1")
    }
    assert outputs["0"] == outputs["1"] == _payload(), (
        "WHY THIS IS A FAILURE: the sidecar's bytes depend on the process that produced them, so "
        "some mapping or set is being serialised in iteration order. Sort it: the report is a "
        "committed artefact and its diff must mean something"
    )


def test_the_writer_writes_only_where_it_was_told_to(tmp_path: Path) -> None:
    """Two files, both under the destination, and nothing anywhere else.

    Asserted because this suite must leave `reports/` absent — the real report is produced by a
    real run, and a test that wrote one would commit a number no model produced.
    """
    into = tmp_path / "baseline"
    written = write(
        build_report(
            entrants=_standard(), provenance=PROVENANCE, contract=CONTRACT, funnel=FUNNEL
        ),
        into,
    )

    assert {path.name for path in written} == {"report.md", "report.json"}, (
        f"WHY THIS IS A FAILURE: the writer produced {[path.name for path in written]}. The "
        "committed document and its machine-readable sidecar are the artefact"
    )
    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")) == [
        "baseline",
        "baseline/report.json",
        "baseline/report.md",
    ], "WHY THIS IS A FAILURE: the writer touched a path outside the destination it was given"
    assert json.loads((into / "report.json").read_text(encoding="utf-8"))["measurement"], (
        "WHY THIS IS A FAILURE: the sidecar does not name which measurement it is. The document "
        "says so in prose; anything reading the JSON instead would be left to guess"
    )


# --------------------------------------------------------------------------------------------
# Required content: the bounds and disclosures a reader must not discover afterwards
# --------------------------------------------------------------------------------------------


def test_the_report_carries_every_disclosure_it_promised() -> None:
    """The control arm, the wall-clock, the held-out clash, the network, and source B's bound.

    Each of these is a thing a reader would otherwise find out after the number, and
    `PREREGISTRATION.md:191-193` states the reason they are up front: a limitation disclosed in
    advance is a bound on the claim, and the same limitation found afterwards reads as something
    that was hidden.
    """
    text = _build(_standard())
    lowered = text.lower()

    assert "control arm" in lowered and "intact" in lowered, (
        "WHY THIS IS A FAILURE: the report publishes counts without the control arm's outcome. An "
        "all-zero column and a harness that graded nothing are the same table, and the control "
        "arm is the only thing that tells them apart"
    )
    assert "wall-clock" in lowered and "seconds" in lowered, (
        "WHY THIS IS A FAILURE: measured wall-clock is missing. docs/ROADMAP.md:594-596 makes "
        "Apple Silicon capacity an open question the bake-off is supposed to answer"
    )
    assert "387" in text and "242-247" in text, (
        "WHY THIS IS A FAILURE: the held-out clash is not recorded. docs/ROADMAP.md:387 states "
        "the pivot signal over a held-out task; PREREGISTRATION.md:242-247 leaves the held-out "
        "split open until P3. The two do not agree and the disagreement is a finding"
    )
    assert "clone" in lowered and "human-run" in lowered, (
        "WHY THIS IS A FAILURE: the network disclosures are missing. Source A clones from GitHub "
        "on each verification and the weights are fetched in a human-run step; "
        "docs/ROADMAP.md:574-576 declares exactly one network exception and these are two"
    )
    assert "byte-for-byte" in lowered and "recipe" in lowered, (
        "WHY THIS IS A FAILURE: source B's non-reproducibility bound is missing "
        "(PREREGISTRATION.md:222-228). An outsider gets the recipe and the liveness ledger and "
        "cannot reproduce our instances byte-for-byte; that is the honest cost of locality"
    )


def test_the_funnel_matches_the_committed_rejection_ledger() -> None:
    """The four-gate figures in this file are the ledger's, not a memory of them.

    The funnel is passed into the writer so the document stays a pure function of its inputs. That
    is only safe if the values passed in are the committed ones, so this reads
    `tasks/public/ineligible.json` and holds the constant to it.
    """
    assert funnel_from_ledger(REPO_ROOT / "tasks" / "public" / "ineligible.json") == FUNNEL, (
        "WHY THIS IS A FAILURE: the four-gate funnel this suite asserts on has drifted from "
        "tasks/public/ineligible.json. The ledger is the evidence; a figure quoted from memory "
        "beside it is the thing that goes stale"
    )


def test_the_authoritative_documents_still_hold_no_figure_about_a_model() -> None:
    """AC13: the report is the only home for a number, and this tree is still a report short.

    `tests/test_docs.py` owns the two document guards; this asserts the third fact that belongs to
    this aspect — that building and rendering a report leaves `reports/` absent, because the real
    one comes from a real run and nothing here has run a model.
    """
    reports = REPO_ROOT / "reports"
    stray = sorted(path.as_posix() for path in reports.rglob("*")) if reports.exists() else []
    assert not stray, (
        f"WHY THIS IS A FAILURE: {stray} exists in a tree where no model has been run. A "
        "committed report is a claim about a measurement, and no measurement has happened — "
        "every report this aspect produces is written into a temporary directory"
    )
    # Flattened, because the sentence wraps inside a blockquote and a guard that a re-wrap could
    # silence is a guard that stops describing the document without anybody noticing —
    # `tests/test_docs.py` collapses the same two things for the same reason.
    raw = (REPO_ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
    roadmap = " ".join(raw.replace("\n>", "\n").split())
    assert "No performance figure appears anywhere in this document" in roadmap, (
        "WHY THIS IS A FAILURE: docs/ROADMAP.md:7-9's own rule is gone, so the document that "
        "forbids a figure about a model no longer says so. reports/baseline/ is the only "
        "sanctioned home for one"
    )
    prereg = (REPO_ROOT / "PREREGISTRATION.md").read_text(encoding="utf-8").lower()
    assert not any(token in prereg for token in ("%", "percent", "percentage")), (
        "WHY THIS IS A FAILURE: a proportion reached PREREGISTRATION.md. It is committed before "
        "the first measurement, so a proportion in it is either a target smuggled in as a result "
        "or a number that leaked back from one"
    )
