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

import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from whetstone.bakeoff.control import Control, Origin, Probe
from whetstone.bakeoff.diffcheck import Trigger, diagnosis_of, diagnosis_vocabulary_sha256
from whetstone.bakeoff.journal import Step
from whetstone.bakeoff.report import (
    ContractArm,
    ContractComparison,
    Entrant,
    Funnel,
    GenerationContract,
    IncompleteProvenance,
    MissingSource,
    Provenance,
    ScoredDevSubset,
    StratumReport,
    build_contract_comparison,
    build_report,
    build_stratum_report,
    funnel_from_ledger,
    tally,
    write,
    write_comparison,
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
                # These are source-B-shaped records, so the reference is the donor's. Source A's
                # is read from the committed pool instead, and the record says which — see
                # `control.Origin`.
                origin=Origin.DONOR,
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
    retry_budget=2,
    retry_template_sha256="b" * 64,
    diagnosis_vocabulary_version="c" * 64,
    retrieval="oracle",
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


#: The gitignored home the format-hardening report points at for its classifier counts. The
#: stored baseline arms' breakdowns live here; the hardened arm's land here too (measured-arm,
#: R5). A pointer the tests can assert on.
BREAKDOWN_HOME = "runs/format-hardening-arm/"

#: A declared-not-yet-measured date for the comparison document. An input, never the clock.
RECORDED_ON = "2026-08-09"


def _comparison_arms() -> tuple[ContractArm, ContractArm]:
    """Two synthetic arms: the baseline-shaped contract and the hardened one, with distinct figures.

    The figures are chosen to collide with nothing in `reports/baseline/` — denominator 11 and
    no count that appears in the baseline report — so the no-restatement test can assert
    disjointness without arithmetic acrobatics. `arm-a` is the no-retries shape (a
    retries-disabled run's contract is byte-identical to the baseline's, `freeze(retry=False)`)
    and `arm-b` the hardened shape (retry budget, retry template digest, vocabulary digest).
    """
    first = ContractArm(
        name="arm-a",
        contract=GenerationContract(
            prompt_sha256="a" * 64,
            sampler="greedy",
            max_tokens=600,
            extractor_version="1",
            dev_subset=(),
            retry_budget=0,
            retry_template_sha256="",
            diagnosis_vocabulary_version="",
            retrieval="oracle",
        ),
        tallies=(tally("one", _records("one", [Outcome.SOLVED] * 5 + [Outcome.NOT_SOLVED] * 6)),),
        generation_seconds=111.0,
    )
    second = ContractArm(
        name="arm-b",
        contract=GenerationContract(
            prompt_sha256="b" * 64,
            sampler="greedy",
            max_tokens=600,
            extractor_version="2",
            dev_subset=("dev-x",),
            retry_budget=2,
            retry_template_sha256="d" * 64,
            diagnosis_vocabulary_version="e" * 64,
            retrieval="oracle",
        ),
        tallies=(tally("two", _records("two", [Outcome.SOLVED] * 7 + [Outcome.NOT_SOLVED] * 4)),),
        generation_seconds=222.0,
    )
    return (first, second)


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


def test_a_five_field_contract_constructed_the_old_way_fails() -> None:
    """The retry fields and retrieval are required, so the old shape cannot mean "no retries".

    A contract built without them would publish a hardened run's figure under a contract that
    says nothing about its retries or its retrieval — the indistinguishability § 10.1 obliges
    the report to end. Old *documents* are handled by `GenerationContract.parse`, which fills
    the defaults at the one place old bytes meet the new dataclass; a caller constructing by
    hand has no such excuse.
    """
    with pytest.raises(TypeError):
        GenerationContract(
            prompt_sha256="a" * 64,
            sampler="greedy",
            max_tokens=600,
            extractor_version="1",
            dev_subset=("dev-a", "dev-b"),
        )


def test_a_contract_round_trips_through_the_sidecar() -> None:
    """The nine fields survive the sidecar and parse back to the same contract.

    A reader that recomputes a contract from the published JSON must get the contract the
    report was rendered under. The sidecar is the machine-readable half of the provenance,
    and a field lost in it is a field no program can tell apart.
    """
    report = build_report(
        entrants=_standard(), provenance=PROVENANCE, contract=CONTRACT, funnel=FUNNEL
    )
    block = json.loads(report.payload)["generation_contract"]
    assert GenerationContract.parse(block) == CONTRACT


def test_the_committed_baseline_sidecar_still_parses_under_the_new_dataclass() -> None:
    """`reports/baseline/report.json` predates the new fields and must keep parsing.

    The committed artifacts are static and never regenerated, so a reader of the baseline
    sidecar runs against the old five-field shape forever. `retrieval` defaults to `"oracle"`
    — the setting the baseline disclosed in prose — and the retry fields default to the state
    that document actually describes: no retries existed, so there is no budget, no retry
    template and no diagnosis vocabulary.
    """
    baseline = REPO_ROOT / "reports" / "baseline" / "report.json"
    block = json.loads(baseline.read_text(encoding="utf-8"))["generation_contract"]
    parsed = GenerationContract.parse(block)

    assert parsed.retrieval == "oracle", (
        "WHY THIS IS A FAILURE: the baseline ran under the oracle retrieval setting, disclosed "
        "in its prose; parsing it under any other setting would mislabel every baseline figure"
    )
    retry_fields = (
        parsed.retry_budget,
        parsed.retry_template_sha256,
        parsed.diagnosis_vocabulary_version,
    )
    assert retry_fields == (0, "", ""), (
        "WHY THIS IS A FAILURE: the baseline predates retries, so a parsed contract claiming a "
        "retry machinery would describe a contract the baseline never used"
    )
    "retry machinery would describe a contract the baseline never used"
    for field in ("prompt_sha256", "sampler", "max_tokens", "extractor_version"):
        assert getattr(parsed, field) == block[field], (
            f"WHY THIS IS A FAILURE: parsing the old sidecar changed {field!r}, so a reader "
            "recomputing the baseline contract from its published JSON gets a different "
            "contract than the one the figures were measured under"
        )
    assert parsed.dev_subset == tuple(block["dev_subset"]), (
        "WHY THIS IS A FAILURE: the baseline's declared development subset did not survive "
        "parsing. The exclusion is part of what the counts mean"
    )


def test_the_sidecar_writes_the_new_contract_fields_explicitly() -> None:
    """The four new fields are written, never defaulted — a reader must not guess them.

    `retrieval` in particular is stated per contract: the field exists so two contracts can be
    told apart programmatically (`p2-yield-probe/prd.md` D9), and a default that hides it would
    publish indistinguishability in machine-readable form.
    """
    block = json.loads(_payload())["generation_contract"]
    for field, expected in (
        ("retry_budget", CONTRACT.retry_budget),
        ("retry_template_sha256", CONTRACT.retry_template_sha256),
        ("diagnosis_vocabulary_version", CONTRACT.diagnosis_vocabulary_version),
        ("retrieval", CONTRACT.retrieval),
    ):
        assert block[field] == expected, (
            f"WHY THIS IS A FAILURE: the sidecar does not write {field!r} explicitly. A reader "
            "of the JSON would have to guess the value, and a guess is how two contracts come "
            "to look alike"
        )


def test_a_retry_budget_without_its_template_is_refused() -> None:
    """A budget that names no template would publish a retry nobody could audit.

    The three retry fields describe one machinery — budget, template digest, vocabulary
    digest. A contract declaring a budget and a blank template is a contract that retried
    under a template its own report cannot name, refused the same way any blank contract
    field is.
    """
    with pytest.raises(IncompleteProvenance) as refusal:
        build_report(
            entrants=_standard(),
            provenance=PROVENANCE,
            contract=GenerationContract(
                prompt_sha256="a" * 64,
                sampler="greedy",
                max_tokens=600,
                extractor_version="1",
                dev_subset=(),
                retry_budget=2,
                retry_template_sha256="",
                diagnosis_vocabulary_version="c" * 64,
                retrieval="oracle",
            ),
            funnel=FUNNEL,
        )
    assert "retry" in str(refusal.value), (
        f"WHY THIS IS A FAILURE: the refusal does not name the retry fields. Got "
        f"{str(refusal.value)!r}"
    )


def test_the_diagnosis_vocabulary_version_is_a_digest_of_the_sorted_sentences() -> None:
    """The contract field a reader can recompute with stdlib alone.

    The version is a digest over the sorted diagnosis sentences, spelled here so a reader can
    reproduce it without importing anything beyond the standard library — the same
    construction `test_retry.py` pins for the retry template hash. A sentence edit moves the
    digest and voids any run frozen before it, like any other template change.
    """
    material = "\n".join(sorted(diagnosis_of(trigger) for trigger in Trigger))
    expected = hashlib.sha256(material.encode("utf-8")).hexdigest()
    assert diagnosis_vocabulary_sha256() == expected, (
        "WHY THIS IS A FAILURE: the vocabulary version is not the digest over the sorted "
        "sentences, so a reader cannot recompute the contract field from the published "
        "vocabulary"
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


# --------------------------------------------------------------------------------------------
# AC14 — the second-contract report: both arms, both contracts, non-comparability declared
# --------------------------------------------------------------------------------------------


def _comparison_document(arms: Sequence[ContractArm] = _comparison_arms()) -> ContractComparison:
    """The rendered comparison document for the synthetic arms, and its sidecars."""
    return build_contract_comparison(
        arms=arms, breakdown_home=BREAKDOWN_HOME, recorded_on=RECORDED_ON
    )


def _stratum_document() -> StratumReport:
    """The rendered stratum document for the synthetic probe tallies, and its sidecars.

    The synthetic tallies' denominators (37 and 41) are chosen to collide with nothing in
    the six existing artifacts — their own denominators are 1, 62, 63, 64, 189, 299 and
    300 — so the disjointness guard holds by construction, exactly like
    `_comparison_arms`' denominator 11.
    """
    return build_stratum_report(
        tallies=(
            tally("one", _records("one", [Outcome.SOLVED] * 5 + [Outcome.NOT_SOLVED] * 32)),
            tally(
                "two",
                _records(
                    "two",
                    [Outcome.SOLVED] * 7
                    + [Outcome.OUT_OF_SCOPE] * 3
                    + [Outcome.NO_DIFF] * 5
                    + [Outcome.NOT_SOLVED] * 26,
                ),
            ),
        ),
        contract=CONTRACT,
        stratum_doc="tasks/stratum/easier.json",
        breakdown_home="runs/easier-stratum-arm/",
        recorded_on=RECORDED_ON,
        generation_seconds=333.0,
    )


def test_a_two_contract_report_renders_both_contracts_fields_distinctly() -> None:
    """Each arm's figures sit under that arm's own contract fields — the pair is the point.

    The whole reason the directory exists is that a count and the contract that produced it
    belong together (`PREREGISTRATION.md:356-361`): told apart programmatically by their
    published fields. `arm-a` is the no-retries shape and must not claim a retry machinery;
    `arm-b` is the hardened shape and must state every retry field. The non-comparability
    sentence sits beside the pair, because the two contracts are declared non-comparable.
    """
    document = _comparison_document()
    _, first, second = document.markdown.split("## Arm: ")

    assert "retry budget" not in first, (
        "WHY THIS IS A FAILURE: the no-retries arm claims a retry machinery. Its contract "
        "predates retries (budget 0, no template, no vocabulary), and a reader of its section "
        "must be told that"
    )
    assert "retry budget 2" in second and ("d" * 64) in second and ("e" * 64) in second, (
        "WHY THIS IS A FAILURE: the hardened arm's section does not carry its retry fields — "
        "budget, retry template digest, diagnosis vocabulary digest — so the two contracts are "
        "not distinguishable from their published fields"
    )
    assert ("a" * 64) in first and ("b" * 64) in second, (
        "WHY THIS IS A FAILURE: the arms' prompt hashes are not stated beside their own "
        "figures, so a reader cannot tell which contract a count was measured under"
    )
    assert "retrieval oracle" in first and "retrieval oracle" in second, (
        "WHY THIS IS A FAILURE: a section omits the retrieval setting, so the pair is not "
        "machine-told-apart even though the field exists for exactly that"
    )
    assert NON_COMPARABILITY in document.markdown, (
        "WHY THIS IS A FAILURE: the two arms are presented side by side without "
        "PREREGISTRATION.md:136-137's sentence. They differ in an unpinned input — the "
        "generation contract — and the report must say they are not comparable figures"
    )


def test_the_two_contract_report_discloses_token_spend_per_arm() -> None:
    """The arm's measured generation seconds, summed from its own cost records.

    A bucket shift between the arms must not be misread as the model improving at formats when
    the harness bought three draws (`p2-format-hardening/prd.md` R6): the report states each
    arm's spend, in prose and in the cost sidecar.
    """
    document = _comparison_document()
    cost = json.loads(document.cost)

    assert "111.0" in document.markdown and "222.0" in document.markdown, (
        "WHY THIS IS A FAILURE: a token-spend disclosure is missing from one of the arms. The "
        "hardened arm spends up to three draws per task against the baseline arm's one, and "
        "the comparison must carry that asymmetry in each arm's own section"
    )
    assert [arm["generation_seconds"] for arm in cost["arms"]] == [111.0, 222.0], (
        f"WHY THIS IS A FAILURE: the cost sidecar does not carry the per-arm spend. Got "
        f"{cost['arms']!r}"
    )


def test_the_two_contract_report_points_at_the_breakdown_home() -> None:
    """The pointer rule: the classifier counts' home is named, and nothing from it is restated.

    `finding.md:89-92`: any document quoting a classifier count must point at the gitignored
    breakdown as its home, or it creates a second home for the same figure. The home is named
    in prose and in the sidecar, and the no-restatement half is asserted next.
    """
    document = _comparison_document()
    payload = json.loads(document.payload)

    assert BREAKDOWN_HOME in document.markdown, (
        "WHY THIS IS A FAILURE: the report names no home for the classifier counts behind its "
        "figures. A count without a stated home is a count the next reader cannot check"
    )
    assert payload["breakdown_home"] == BREAKDOWN_HOME, (
        "WHY THIS IS A FAILURE: the sidecar does not name the breakdown home, so a program "
        "reading the JSON cannot find the counts either"
    )
    assert "never restates" in document.markdown.lower(), (
        "WHY THIS IS A FAILURE: the pointer does not say that this document does not restate "
        "the breakdowns. An unnamed prohibition is a prohibition nobody can check"
    )


def test_the_two_contract_report_restates_no_baseline_figure() -> None:
    """*(adversarial)* No rendered figure in the new report lives in `reports/baseline/`.

    The pointer rule as a test, asserted the strongest way available: every `N of M` figure the
    new document renders is disjoint from every `N of M` figure the committed baseline report
    renders. A figure that appears in both is a figure with two homes, which is exactly how two
    disagreeing numbers come to exist.
    """
    document = _comparison_document()
    written = " ".join((document.markdown, document.payload, document.cost))
    figures = {pair for pair in re.findall(r"\b(\d+) of (\d+)\b", written)}
    assert figures, (
        "WHY THIS IS A FAILURE: the report renders no figures at all, so this test's "
        "disjointness assertion would pass vacuously over an empty document"
    )
    baseline = (REPO_ROOT / "reports" / "baseline" / "report.md").read_text(encoding="utf-8")
    baseline_figures = {pair for pair in re.findall(r"\b(\d+) of (\d+)\b", baseline)}
    overlap = figures & baseline_figures
    assert not overlap, (
        f"WHY THIS IS A FAILURE: the new report restates {overlap}, which already lives in "
        "reports/baseline/report.md. A figure quoted twice is a figure that can disagree with "
        "itself, and the one-home rule exists so that cannot happen"
    )


def test_the_stratum_report_restates_no_figure_from_an_existing_home() -> None:
    """*(adversarial)* No rendered stratum figure lives in any of the six existing artifacts.

    The changed-task-set home joins the guard on the same rule the earlier homes joined it
    on, asserted the strongest way available: every `N of M` figure the synthetic stratum
    document renders is disjoint from every `N of M` figure the six committed artifacts
    render (`reports/baseline/` and `reports/format-hardening/`, each report.md,
    report.json and cost.json). A figure that appears in both is a figure with two homes,
    which is exactly how two disagreeing numbers come to exist.
    """
    document = _stratum_document()
    written = " ".join((document.markdown, document.payload, document.cost))
    figures = {pair for pair in re.findall(r"\b(\d+) of (\d+)\b", written)}
    assert figures, (
        "WHY THIS IS A FAILURE: the stratum document renders no figures at all, so this "
        "test's disjointness assertion would pass vacuously over an empty document"
    )
    existing_figures: set[tuple[str, str]] = set()
    for directory in ("baseline", "format-hardening"):
        for name in ("report.md", "report.json", "cost.json"):
            artifact = (REPO_ROOT / "reports" / directory / name).read_text(encoding="utf-8")
            existing_figures |= {pair for pair in re.findall(r"\b(\d+) of (\d+)\b", artifact)}
    assert existing_figures, (
        "WHY THIS IS A FAILURE: none of the six committed artifacts renders an `N of M` "
        "figure, so the disjointness guard has nothing to guard against"
    )
    overlap = figures & existing_figures
    assert not overlap, (
        f"WHY THIS IS A FAILURE: the stratum document restates {overlap}, which already "
        "lives in one of the six existing artifacts. A figure quoted twice is a figure "
        "that can disagree with itself, and the one-home rule exists so that cannot happen"
    )


def test_the_stratum_disjointness_guard_catches_a_planted_overlap() -> None:
    """*(adversarial)* The guard above can see a planted collision.

    The synthetic fixture's denominators (37 and 41) are disjoint from every committed
    artifact by construction; a planted tally over denominator 63 — one the baseline
    report actually renders — must be found by the same scan. A collision the guard
    cannot see is a figure with two homes.
    """
    planted = build_stratum_report(
        tallies=(
            tally(
                "planted", _records("planted", [Outcome.SOLVED] + [Outcome.NOT_SOLVED] * 62)
            ),
        ),
        contract=CONTRACT,
        stratum_doc="tasks/stratum/easier.json",
        breakdown_home="runs/easier-stratum-arm/",
        recorded_on=RECORDED_ON,
    )
    written = " ".join((planted.markdown, planted.payload, planted.cost))
    figures = {pair for pair in re.findall(r"\b(\d+) of (\d+)\b", written)}
    assert ("1", "63") in figures, (
        "WHY THIS IS A FAILURE: the planted tally over denominator 63 did not render "
        "`1 of 63`, so the planted-overlap control is not testing what it claims"
    )
    baseline = (REPO_ROOT / "reports" / "baseline" / "report.md").read_text(encoding="utf-8")
    baseline_figures = {pair for pair in re.findall(r"\b(\d+) of (\d+)\b", baseline)}
    assert figures & baseline_figures, (
        "WHY THIS IS A FAILURE: the planted `1 of 63` / `0 of 63` figures were not found "
        "by the disjointness scan. A collision the guard cannot see is a figure with two "
        "homes"
    )


def test_a_second_contract_report_with_no_measured_arm_states_so() -> None:
    """The committed state of the directory: declared, not yet measured, and holding no figure.

    The arm has not run, so the committed artifacts cannot carry a figure — neither the arm's
    own (none exists) nor the baseline's (restating it is forbidden). The declaration says
    exactly that, names the two contracts non-comparable, and holds no figure of its own.
    """
    document = _comparison_document(arms=())

    assert "has not run" in document.markdown, (
        "WHY THIS IS A FAILURE: a directory whose arm has not run says nothing about that. A "
        "reader finding counts here later could not tell when they appeared"
    )
    assert "non-comparable" in document.markdown, (
        "WHY THIS IS A FAILURE: the declaration does not state that the two contracts are "
        "declared non-comparable — the argument the directory's existence rests on"
    )
    assert "reports/baseline/" in document.markdown, (
        "WHY THIS IS A FAILURE: the declaration does not name which directory's figures it "
        "does not restate"
    )
    assert not re.search(r"\d+ of \d+", document.markdown), (
        "WHY THIS IS A FAILURE: the declaration renders a figure, but no measurement exists. "
        "A count here would be either a restated baseline figure or an invented one"
    )


def test_the_comparison_writer_writes_the_three_artifacts_and_nothing_else(
    tmp_path: Path,
) -> None:
    """report.md, report.json and cost.json — the same shape as `reports/baseline/`'s.

    A reader learns one layout for both directories; a fourth file in either is a stray with a
    figure-shaped home. Nothing is written outside the destination.
    """
    into = tmp_path / "format-hardening"
    written = write_comparison(_comparison_document(), into)

    assert {path.name for path in written} == {"report.md", "report.json", "cost.json"}, (
        f"WHY THIS IS A FAILURE: the writer produced {[path.name for path in written]}. The "
        "directory's committed shape is the same three artifacts as reports/baseline/"
    )
    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")) == [
        "format-hardening",
        "format-hardening/cost.json",
        "format-hardening/report.json",
        "format-hardening/report.md",
    ], "WHY THIS IS A FAILURE: the writer touched a path outside the destination it was given"


def test_the_comparison_document_is_a_pure_function_of_its_inputs() -> None:
    """The same inputs render byte-identical output, like the bake-off document.

    The format-hardening report is committed evidence once the arm runs; a reader who
    regenerates it and gets different bytes cannot tell a re-render from a re-measurement. The
    three strings are asserted together, so no half of the document can drift on its own.
    """
    first = _comparison_document()
    second = _comparison_document()
    assert (first.markdown, first.payload, first.cost) == (
        second.markdown,
        second.payload,
        second.cost,
    ), (
        "WHY THIS IS A FAILURE: two renders of the same inputs differ, so the committed "
        "document could not be regenerated byte-for-byte and its diff would mean nothing"
    )


def test_the_authoritative_documents_still_hold_no_figure_about_a_model() -> None:
    """AC13: `reports/baseline/` and `reports/format-hardening/`, each the only home of its own.

    **What this guard asserts moved when the bake-off ran, and the guard moved with it.** It was
    written while this aspect could only render into a temporary directory, and it asserted that
    `reports/` was absent outright — the honest form of *"nothing here has run a model"*. Slice 5
    ran one, so that literal is now false and the invariant underneath it is what survives:
    `reports/` holds each report's three artifacts and nothing besides. A report appearing in a
    directory that is not its home is a second home for a figure, and two homes is exactly how
    two figures come to disagree with each other.

    **The guard moved again when the format-hardening arm's home landed, and only on the D6
    argument.** `reports/format-hardening/` joined the list on the ground that the two
    directories measure **different generation contracts** and are declared non-comparable
    (`PREREGISTRATION.md` § 10.4), so neither is a competing home for the same figure: the
    baseline's figures live in `reports/baseline/` and the hardened contract's in
    `reports/format-hardening/`. A figure from one appearing in the other is still the
    two-homes failure the paragraph above refuses, and a silent list extension remains refused —
    the permission is the argument, in this docstring.

    **The guard moved a third time when the easier-stratum probe's home landed, and only on
    the changed-task-set argument.** The task set is one of the five pinned inputs
    (`PREREGISTRATION.md:131-132`), and a change to any pinned input invalidates the series
    and starts a new one (`PREREGISTRATION.md:133-135`). The probe scores a **different task
    set** — a pre-committed difficulty stratum of the declared source-B set — under the same
    hardened contract, so its figures are a new series, declared non-comparable to both
    existing homes (`PREREGISTRATION.md` § 10.5): the baseline's figures live in
    `reports/baseline/`, the hardened arm's in `reports/format-hardening/`, and the probe's
    in `reports/easier-stratum/` — each the only home of its own. A silent list extension
    remains refused: the permission is the argument, in this docstring.

    `reports/local/` is excluded because `.gitignore` reserves it for the user's own nightly
    output, which is their data and never ours to assert on.

    The document half is unchanged and is the part that never moves: `docs/ROADMAP.md` still
    forbids a performance figure inside itself, and `PREREGISTRATION.md` still carries no
    proportion in any spelling.
    """
    reports = REPO_ROOT / "reports"
    relative = (
        path.relative_to(REPO_ROOT).as_posix() for path in reports.rglob("*") if path.is_file()
    )
    held = sorted(name for name in relative if not name.startswith("reports/local/"))
    assert held == [
        "reports/baseline/cost.json",
        "reports/baseline/report.json",
        "reports/baseline/report.md",
        "reports/easier-stratum/cost.json",
        "reports/easier-stratum/report.json",
        "reports/easier-stratum/report.md",
        "reports/format-hardening/cost.json",
        "reports/format-hardening/report.json",
        "reports/format-hardening/report.md",
    ], (
        f"WHY THIS IS A FAILURE: reports/ holds {held}. The bake-off's three artifacts, the "
        "format-hardening arm's three and the easier-stratum probe's three are the sanctioned "
        "homes for a figure — each directory its own, on the D6 argument that the two "
        "contracts differ and the changed-task-set argument that the probe scores a "
        "different task set (`PREREGISTRATION.md` § 10.5), all declared non-comparable. A "
        "file missing means the report is incomplete; a file extra means there is a second "
        "place a figure can live, and the next reader has no way to tell which of two "
        "disagreeing numbers is the real one"
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
