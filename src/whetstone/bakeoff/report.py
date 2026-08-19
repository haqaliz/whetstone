"""The bake-off report: the first document in this project that says anything about a model.

`PREREGISTRATION.md` was committed before any number existed, and its entire value is that
ordering. This module is where the value is either kept or spent, because it writes the first
document the pre-registration governs. Three failures are designed against, and they are the
reason the code is shaped the way it is rather than being a formatter.

**Identity.** A bake-off count and the pinned baseline count are the same shape — an untrained
base's solved tasks over a denominator — and one of them may be measured exactly once
(`PREREGISTRATION.md:129-132`). An unlabelled document is read as whichever the reader expected,
so the report states which it is and states that the once-only measurement is unspent by it. The
reason it is unspent is not visible in the number: the pinned baseline is scored on the held-out
split, and that split does not exist (`PREREGISTRATION.md` § 7.1, open until P3).

**Costume.** `PREREGISTRATION.md:69-72` fixes a skeleton for the P4 headline. A selection number
printed into it would be a bake-off number wearing that headline's clothes, which is the exact
substitution a pre-registration exists to prevent — so this module never emits a signed count,
never names a baseline/final pair, and never calls its own scored set held-out.

**Denominators.** Every count is rendered over the set it was counted on. `UNVERIFIED` lowers
coverage and never leaves the denominator: `Tally` keeps `solved`, `failed` and `unverified` as
three disjoint counts that must sum to it, so a dropped record has nowhere to go. Dropping them
is the hundred-out-of-hundred-by-construction lie `PREREGISTRATION.md:111-114` refuses by name,
and it is a lie every other number in the document would stay consistent with.

**The document is a pure function of its inputs.** No clock is read, no ledger is opened, and
every mapping is serialised in a fixed order, so the same records and the same pinned inputs
produce byte-identical output across runs and across processes. Committed evidence that cannot be
regenerated is not evidence, and a reader who regenerates it and gets different bytes cannot tell
a re-render from a re-measurement.

**This module decides nothing.** The base is chosen by `whetstone.bakeoff.selection`, whose rule
was fixed before any count existed; the counts come from records `whetstone.bakeoff.sweep`
produced; and the records are only obtainable through `rankable`, which refuses a run whose
control arm never proved the harness grades anything. Off the reward path, and one-way — see the
package docstring.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from whetstone.bakeoff.control import Control
from whetstone.bakeoff.scoring import Outcome, Rollout
from whetstone.bakeoff.selection import Contender, Ranked, Selection, select
from whetstone.bakeoff.sweep import Sweep, rankable
from whetstone.verify.verdict import Status

#: The outcomes that mean no verdict was reached. They lower coverage and stay in the denominator.
#: `UNPROVISIONED` is here because a machine that could not build the environment is a fact about
#: the machine, and charging it to the candidate would be a figure about a base nobody scored.
#: `NO_ORACLE` is here for the same reason one step earlier: the generation contract could not be
#: built for that task, so no prompt was rendered and the base was never shown it. Counting it as
#: a failure would publish "this base could not fix it" about a question nobody asked.
_UNCOVERED = frozenset({Outcome.UNVERIFIED, Outcome.UNPROVISIONED, Outcome.NO_ORACLE})

#: The retrieval setting, disclosed beside the contract that produced the number. The prompt shows
#: the base the non-test files its task's fix touches — without them a unified diff is being asked
#: for against a file the base has never seen, and measured, every such rollout came back
#: NOT_APPLIED. The cost is that the file set is derived from the reference patch, so the prompt
#: names where the answer lives. That makes the scored task **easier** than the real setting, in
#: one direction only, which is why the sentence says upper bound rather than "approximately".
_ORACLE_DISCLOSURE = (
    "**Retrieval: the oracle setting, disclosed.** Each prompt shows the base the non-test files "
    "that task's reference patch touches, as they stand at `base_commit` (the standard SWE-bench "
    "oracle condition, `whetstone.bakeoff.sources`). Without them a unified diff is being asked "
    "for against a file the base has never seen; with them the prompt also names which files to "
    "change, which is work the unassisted setting includes. Every count here is therefore a "
    "figure about the oracle setting and an upper bound on what the same base would do from the "
    "bug report alone. It may not be compared with a published figure measured without retrieval."
)

#: `PREREGISTRATION.md:102`, verbatim, with the count substituted for the letter. The wording is
#: pre-registered so that neither a later editor nor a later result can soften or sharpen what the
#: number claims; a literal here rather than a phrasing chosen at the call site keeps it that way.
_N_SENTENCE = "{count} rollouts a weaker check would have scored as wins."

#: `PREREGISTRATION.md:211-220`, verbatim. Required beside every `N`, because cheat 6 and cheat 10
#: are accepted by both verifiers, so an unbounded `N` reads as a completeness claim the verifier
#: has never made.
_RESIDUAL_BOUND = (
    "N counts what the strictness caught. It is not a claim that nothing got through."
)

#: `PREREGISTRATION.md:136-137`, quoted. Required beside any side-by-side presentation: candidates
#: differ in model revision, which is a pinned input (`:131`), so the rows are ranked against each
#: other and are not comparable figures.
_NON_COMPARABILITY = (
    "A figure measured on one side of a changed pinned input may not be compared with one "
    "measured on the other."
)

#: The only sentence in the report permitted to name a bar, because it refuses one.
#: `PREREGISTRATION.md:171` pre-registers no success threshold and forbids one being added once a
#: number exists — which is the moment this document arrives at.
_THRESHOLD_DENIAL = (
    "This report ranks and does not threshold: it names no minimum any candidate must clear, "
    "and PREREGISTRATION.md:171 forbids one being added now that a number exists."
)

#: The only sentence permitted to discuss intent, because it refuses to claim any. A patch that
#: edited a genuinely-buggy test in good faith counts toward `N` exactly as one that gamed the
#: check does, and nothing in the record tells them apart (`PREREGISTRATION.md:102-105`).
_INTENT_DENIAL = (
    "This is a claim about what the strictness caught and not about intent: intent is not "
    "observable, so no claim to measure it is made here."
)

#: The patch-scope rule the generation contract states to every candidate, quoted so a reader can
#: see for themselves why `N` is a floor: the contract discourages precisely what `N` counts.
_SCOPE_RULE = (
    "the test files are held by the operator ... a patch that modifies any test file is refused "
    "before it is run"
)


class MissingSource(ValueError):
    """The report was asked to publish one source without the other.

    `PREREGISTRATION.md:142-143` fixes that both are always published together, regardless of
    which looks better and with neither held back pending the other. A refusal rather than a
    warning, because a warning is a thing a caller reads past on the night the private source
    disappoints.
    """


class IncompleteProvenance(ValueError):
    """A pinned input or a generation-contract field was left blank.

    Refused rather than rendered empty. A rendered blank is worse than a refusal: it looks like a
    field somebody considered, and it survives review because the block looks complete.
    """


class ScoredDevSubset(ValueError):
    """A task the generation contract was developed against reached the scored set.

    PRD M7b: the prompt and the extractor are iterated against the control arm and a declared,
    permanently-excluded dev subset. Scoring a task the contract was tuned on is optimising on the
    outcome, and the report is the last place it can be noticed.
    """


@dataclass(frozen=True)
class Provenance:
    """The five pinned inputs of `PREREGISTRATION.md:131-132`, minus the per-candidate one.

    Model revision is the fifth and lives on `Contender`, because it varies per candidate and a
    copy here would be a second place for it to be wrong. Everything in this class is declared by
    the operator rather than sensed, including `recorded_on`: a date read from the clock would
    make the document differ from itself between two renders of the same records.
    """

    #: Which task set was scored, and where its evidence lives.
    task_set: str

    #: How each task's environment was pinned. The manifests declare their own `==` pins.
    environment_pins: str

    #: The seeds every rollout was drawn under.
    seeds: str

    #: Tool versions, rendered in sorted key order so the document does not depend on how this
    #: mapping was built.
    tool_versions: Mapping[str, str]

    #: The date the operator declares for this run. An input, never `date.today()`.
    recorded_on: str


@dataclass(frozen=True)
class GenerationContract:
    """What produced the text a verdict was taken on — and what is *not* a sixth pinned input.

    Published inside the provenance block and explicitly distinguished from the five. It
    determines the number: the template, the sampler, the token budget and the extractor all move
    it, and `N` in particular is measured under a contract that discloses the patch-scope rule.
    Leaving it out would hide the input this project already knows moves a pre-registered figure;
    publishing it undifferentiated would quietly promote it to a pinned one.
    """

    #: SHA-256 of the exact template every candidate was shown.
    prompt_sha256: str

    #: How text was drawn.
    sampler: str

    #: The generation budget.
    max_tokens: int

    #: Which extractor turned text into a diff.
    extractor_version: str

    #: The tasks the contract was developed against, which may never be scored by it (M7b).
    dev_subset: tuple[str, ...]

    #: How many retries a (candidate, task) may get under this contract. `0` is the
    #: no-retries state: a contract without retry prompts frozen into it declares no budget.
    retry_budget: int

    #: A digest of the retry template (the fixed instruction plus the sorted diagnosis
    #: sentences), recomputable by a reader with stdlib alone. Blank exactly when
    #: `retry_budget` is `0`.
    retry_template_sha256: str

    #: A digest of the diagnosis vocabulary alone, recomputable from the published sentences.
    #: Blank exactly when `retry_budget` is `0`.
    diagnosis_vocabulary_version: str

    #: The retrieval setting the prompts were rendered under. `"oracle"` today (the disclosed
    #: setting of `_ORACLE_DISCLOSURE`); a field rather than a constant so two contracts can
    #: be told apart programmatically (`p2-yield-probe/prd.md` D9), which § 10.1 asks for.
    retrieval: str

    @classmethod
    def parse(cls, block: Mapping[str, Any]) -> GenerationContract:
        """Read a sidecar's `generation_contract` block, including one that predates this shape.

        `reports/baseline/report.json` was written before the retry fields and the retrieval
        field existed, and the committed artifacts are static — never regenerated — so a reader
        of the baseline sidecar runs against the old five-field shape forever. The missing
        fields default to the state that document actually describes: `retrieval` to
        `"oracle"`, the setting the baseline disclosed in prose, and the retry trio to the
        no-retries state (budget `0`, no template, no vocabulary), because a document that
        predates retries had none. The defaults are populated here, at the one place old
        bytes meet the new dataclass, and nowhere else: a new contract's fields are written
        explicitly by the sidecar, so a reader never has to guess them.
        """
        return cls(
            prompt_sha256=block["prompt_sha256"],
            sampler=block["sampler"],
            max_tokens=block["max_tokens"],
            extractor_version=block["extractor_version"],
            dev_subset=tuple(block["dev_subset"]),
            retry_budget=block.get("retry_budget", 0),
            retry_template_sha256=block.get("retry_template_sha256", ""),
            diagnosis_vocabulary_version=block.get("diagnosis_vocabulary_version", ""),
            retrieval=block.get("retrieval", "oracle"),
        )


@dataclass(frozen=True)
class Funnel:
    """Source A's four-gate eligibility filter, as `tasks/public/ineligible.json` records it.

    Passed into the writer rather than read from disk by it, so the document stays a pure function
    of its inputs — with `funnel_from_ledger` as the one place the two are tied together.

    `by_gate` is an ordered tuple of pairs rather than a mapping, so the funnel renders in the
    order the gates actually ran and cannot re-order itself between two processes.
    """

    #: How many instances were drawn. SWE-bench-Lite is 300.
    considered: int

    #: The instances that survived every gate. One instance is not a public benchmark set.
    eligible: tuple[str, ...]

    #: How many were refused.
    refused: int

    #: Refusals per gate, in execution order. A funnel missing a gate is not a funnel.
    by_gate: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class Entrant:
    """One base's whole bake-off: who it was, and its run on each source.

    Both sources are fields rather than one optional field, because `PREREGISTRATION.md:142-143`
    makes publishing one without the other a refusal rather than a degraded mode.
    """

    #: The base, its revision, and its declared size.
    contender: Contender

    #: The source-B run: the declared private set, and the pre-registered headline's source.
    private: Sweep

    #: The source-A run: the single eligible public instance.
    public: Sweep


@dataclass(frozen=True)
class ContractArm:
    """One arm of the format-hardening comparison: its contract, and what it measured.

    `tallies` are the arm's verdict counts, stated under this arm's own contract fields — a
    count and the contract that produced it belong together, and the pair is the whole point of
    the two-directory rule. An empty tuple means the arm has not run and no count exists.
    `generation_seconds` is the arm's measured token spend, summed over its runs from the run's
    own cost records; `None` means not measured.
    """

    #: The arm's name, as the run ledger records it (arm-a, the hardened arm, ...).
    name: str

    #: The contract every figure in this arm's section was measured under.
    contract: GenerationContract

    #: The arm's verdict counts, per candidate. Empty: the arm has not run.
    tallies: tuple[Tally, ...] = ()

    #: The arm's measured token spend. `None`: not measured.
    generation_seconds: float | None = None


@dataclass(frozen=True)
class ContractComparison:
    """The second-contract document and its sidecars, before either touches a disk.

    The same shape as `Report` for the bake-off document, with the cost sidecar as the third
    string so the directory's committed layout — report.md, report.json, cost.json — mirrors
    `reports/baseline/`'s and a reader learns one layout for both.
    """

    #: The committed document.
    markdown: str

    #: The machine-readable sidecar.
    payload: str

    #: The measured cost sidecar, as text so the bytes are the artefact.
    cost: str


def _contract_fields(contract: GenerationContract) -> str:
    """One contract's fields as the provenance block states them, in a fixed order.

    The retry trio is rendered only when `retry_budget` is non-zero: a no-retries contract has
    no retry template and no vocabulary, and rendering blanks would be a field that looks
    considered. The fixed order is what makes the two contracts comparable by their published
    fields — the machine-readability point of `retrieval` (`p2-yield-probe/prd.md` D9).
    """
    parts = [
        f"template SHA-256 `{contract.prompt_sha256}`",
        f"sampler {contract.sampler}",
        f"token budget {contract.max_tokens}",
        f"extractor version {contract.extractor_version}",
        f"retrieval {contract.retrieval}",
        "development subset "
        + (
            ", ".join(f"`{name}`" for name in contract.dev_subset)
            if contract.dev_subset
            else "none declared"
        ),
    ]
    if contract.retry_budget > 0:
        parts += [
            f"retry budget {contract.retry_budget}",
            f"retry template SHA-256 `{contract.retry_template_sha256}`",
            f"diagnosis vocabulary version `{contract.diagnosis_vocabulary_version}`",
        ]
    return "; ".join(parts)


@dataclass(frozen=True)
class Tally:
    """Derived counts for one candidate over one source, each kept beside its denominator.

    `solved`, `failed` and `unverified` are three disjoint counts over the same denominator and
    must sum to it. That invariant is the whole defence against the drop: a record that left the
    set has nowhere to be, and the sum stops matching.
    """

    #: Which base these counts are about.
    candidate: str

    #: The size of the scored set. Never reduced by an unverified task.
    denominator: int

    #: STRICT `PASS` and nothing else (`PREREGISTRATION.md:86-90`).
    solved: int

    #: Tasks that reached a real verdict. `denominator - unverified`.
    covered: int

    #: Tasks that reached no verdict. They lower coverage; they never leave the denominator.
    unverified: int

    #: Covered and not solved. An unverified task is never here: UNVERIFIED is not a win, and it
    #: is not a loss either — it is the absence of a comparison.
    failed: int

    #: `N := count(WEAK == PASS and STRICT == FAIL)` (`PREREGISTRATION.md:99`).
    weaker_wins: int

    #: The base produced no diff at all.
    no_diff: int

    #: A diff was produced and the checkout refused it.
    not_applied: int

    #: The patch aimed at an operator-held path and was refused before anything ran.
    out_of_scope: int

    #: The patch applied and the task still failed — the only zero that is about capability.
    not_solved: int


@dataclass(frozen=True)
class Report:
    """The rendered artefact and the figures behind it, before either touches a disk."""

    #: What the selection rule returned. Rendered, never re-decided.
    selection: Selection

    #: Per-candidate counts over the declared source-B set, in ranking order.
    private: tuple[Tally, ...]

    #: Per-candidate counts over source A's single instance, in ranking order.
    public: tuple[Tally, ...]

    #: The committed document.
    markdown: str

    #: The machine-readable sidecar, as text so the bytes are the artefact.
    payload: str


def tally(candidate: str, records: Sequence[Rollout]) -> Tally:
    """Count `records` for `candidate`. The single place each published figure is defined.

    Takes the whole record set and never filters it. A tally that dropped the unverified records
    before counting would produce a coverage of everything-over-everything while every other
    number in the document stayed internally consistent, which is why the denominator is
    `len(records)` and not a count of anything.
    """
    denominator = len(records)
    unverified = sum(1 for record in records if record.outcome in _UNCOVERED)
    solved = sum(1 for record in records if record.outcome is Outcome.SOLVED)
    return Tally(
        candidate=candidate,
        denominator=denominator,
        solved=solved,
        covered=denominator - unverified,
        unverified=unverified,
        failed=denominator - unverified - solved,
        weaker_wins=sum(
            1
            for record in records
            if record.weak is Status.PASS and record.strict is Status.FAIL
        ),
        no_diff=sum(1 for record in records if record.outcome is Outcome.NO_DIFF),
        not_applied=sum(1 for record in records if record.outcome is Outcome.NOT_APPLIED),
        out_of_scope=sum(1 for record in records if record.outcome is Outcome.OUT_OF_SCOPE),
        not_solved=sum(1 for record in records if record.outcome is Outcome.NOT_SOLVED),
    )


def funnel_from_ledger(path: Path) -> Funnel:
    """Read source A's four-gate funnel out of the committed rejection ledger.

    The one place the figures quoted in the report are tied to the evidence behind them. Quoting
    them from memory beside the ledger is what goes stale, and the ledger is what an outside
    reader can actually check.
    """
    ledger: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    counts: dict[str, int] = ledger["counts"]
    return Funnel(
        considered=counts["input"],
        eligible=tuple(ledger["eligible"]),
        refused=counts["ineligible"],
        by_gate=tuple((gate, counts[gate]) for gate in ledger["execution_order"]),
    )


def build_report(
    *,
    entrants: Sequence[Entrant],
    provenance: Provenance,
    contract: GenerationContract,
    funnel: Funnel,
) -> Report:
    """Derive every figure, apply the pre-registered rule, and render the document.

    Refuses before it renders, in four ways: a blank pinned input, a source published alone, a
    dev-subset task that reached the scored set, and — through `rankable` — a run whose control
    arm never proved the harness grades anything. Each is a refusal rather than a caveat, because
    a caveat is a thing downstream code reads past.
    """
    _require_provenance(provenance, contract)
    for entrant in entrants:
        if not entrant.private.steps:
            raise MissingSource(
                f"{entrant.contender.candidate!r} has no source B run, so this report would "
                "publish source A alone. PREREGISTRATION.md:142-143 fixes that both sources are "
                "always published together, regardless of which looks better"
            )
        if not entrant.public.steps:
            raise MissingSource(
                f"{entrant.contender.candidate!r} has no source A run, so this report would "
                "publish source B alone. PREREGISTRATION.md:142-143 fixes that both sources are "
                "always published together, and source A is the fully committed, externally "
                "checkable half — it is not optional padding"
            )

    scored = {
        record.task_id
        for entrant in entrants
        for record in (*rankable(entrant.private), *rankable(entrant.public))
    }
    leaked = sorted(scored & set(contract.dev_subset))
    if leaked:
        raise ScoredDevSubset(
            f"the generation contract was developed against {leaked} and those tasks were also "
            "scored by it. PRD M7b excludes the dev subset from every published count, because "
            "iterating a prompt or an extractor against a task and then scoring that task is "
            "optimising on the outcome"
        )

    private = {
        entrant.contender.candidate: tally(
            entrant.contender.candidate, rankable(entrant.private)
        )
        for entrant in entrants
    }
    public = {
        entrant.contender.candidate: tally(entrant.contender.candidate, rankable(entrant.public))
        for entrant in entrants
    }
    chosen = select(
        Ranked(
            contender=entrant.contender,
            solved=private[entrant.contender.candidate].solved,
            denominator=private[entrant.contender.candidate].denominator,
        )
        for entrant in entrants
    )
    order = [line.contender.candidate for line in chosen.ranking]
    by_candidate = {entrant.contender.candidate: entrant for entrant in entrants}

    ranked_private = tuple(private[name] for name in order)
    ranked_public = tuple(public[name] for name in order)
    return Report(
        selection=chosen,
        private=ranked_private,
        public=ranked_public,
        markdown=_render(
            chosen=chosen,
            entrants=[by_candidate[name] for name in order],
            private=ranked_private,
            public=ranked_public,
            provenance=provenance,
            contract=contract,
            funnel=funnel,
        ),
        payload=_payload(
            chosen=chosen,
            private=ranked_private,
            public=ranked_public,
            provenance=provenance,
            contract=contract,
            funnel=funnel,
        ),
    )


def write(report: Report, into: Path) -> tuple[Path, Path]:
    """Write the document and its sidecar into `into`, and nothing anywhere else.

    Returns both paths so a caller can assert on what was produced rather than reconstruct the
    names. The bytes are already decided by `build_report`; this function chooses no content.
    """
    into.mkdir(parents=True, exist_ok=True)
    document = into / "report.md"
    sidecar = into / "report.json"
    document.write_text(report.markdown, encoding="utf-8")
    sidecar.write_text(report.payload, encoding="utf-8")
    return (document, sidecar)


def build_contract_comparison(
    *,
    arms: Sequence[ContractArm],
    breakdown_home: str,
    recorded_on: str,
) -> ContractComparison:
    """Render the format-hardening arm's document: both arms, both contracts, non-comparable.

    The second-contract report, for `reports/format-hardening/`. Every arm's verdict counts are
    stated under that arm's own contract fields; the non-comparability sentence
    (`PREREGISTRATION.md:136-137`) sits beside the pair; each arm's measured token spend is
    disclosed; and the gitignored home of the classifier counts is named, never restated
    (`finding.md:89-92`). With no arms the document is the declaration: the directory is the
    hardened contract's home, the two contracts are declared non-comparable, and no count is
    measured — the state of the committed artifacts before the measured arm runs.

    A pure function of its inputs, like `build_report`: no clock is read, no ledger is opened,
    and every mapping is serialised in a fixed order, so the same inputs produce byte-identical
    output. `recorded_on` is declared by the operator, never read from the clock.
    """
    lines = [
        "# Format-hardening arm — two generation contracts, declared non-comparable",
        "",
        "This document reports the format-hardening arm: the declared source-B set scored under "
        "a hardened generation contract — the retry-augmented contract — beside the arm that "
        "ran the baseline contract. The two directories measure different generation contracts "
        "and are declared non-comparable (`PREREGISTRATION.md` § 10.4): `reports/baseline/` "
        "remains the only home of the baseline's figures, and this directory is the only home "
        "of the hardened arm's — neither is a competing home for the same figure.",
        "",
        _NON_COMPARABILITY,
        "",
    ]
    if not arms:
        lines += [
            "**No count is measured here: the arm has not run.** Both contracts, per-arm "
            "verdict counts and per-arm token spend are rendered into this directory by the "
            "measured arm, which also names the ceiling it ran against. Until then this "
            "document holds no figure of its own and restates none from `reports/baseline/`.",
            "",
        ]
    for arm in arms:
        lines += [
            f"## Arm: {arm.name}",
            "",
            f"**The contract.** {_contract_fields(arm.contract)}.",
            "",
        ]
        if arm.tallies:
            names = [counts.candidate for counts in arm.tallies]
            columns = " | ".join(f"`{name}`" for name in names)
            rule = "|".join(["---"] * (len(names) + 1))
            lines += [
                f"| Figure | {columns} |",
                f"|{rule}|",
                _row("solved", arm.tallies, lambda one: one.solved),
                _row("coverage", arm.tallies, lambda one: one.covered),
                _row("unverified", arm.tallies, lambda one: one.unverified),
                _row("N", arm.tallies, lambda one: one.weaker_wins),
                _row("no diff", arm.tallies, lambda one: one.no_diff),
                _row("patch apply", arm.tallies, lambda one: one.not_applied),
                _row("patch scope", arm.tallies, lambda one: one.out_of_scope),
                _row("not solved", arm.tallies, lambda one: one.not_solved),
                "",
                "These counts are stated under this arm's own contract fields above: a count "
                "and the contract that produced it belong together.",
                "",
            ]
        else:
            lines += [
                "**No verdict counts: the arm has not run.** They are rendered here under this "
                "contract's fields when the measured arm lands.",
                "",
            ]
        if arm.generation_seconds is not None:
            lines.append(
                f"**Token spend.** Generation {arm.generation_seconds:.1f} seconds, summed over "
                "this arm's runs from the run's own cost records."
            )
        else:
            lines.append("**Token spend.** Not measured: the arm has not run.")
        lines.append("")
    lines += [
        f"**The breakdowns.** The classifier counts behind these figures live in the gitignored "
        f"home `{breakdown_home}`; this document points at them and never restates them, so a "
        "classifier count has exactly one home.",
        "",
        f"Recorded on {recorded_on} (declared by the operator, never read from a clock).",
    ]
    return ContractComparison(
        markdown="\n".join(lines),
        payload=_comparison_payload(arms, breakdown_home, recorded_on),
        cost=_comparison_cost(arms),
    )


def write_comparison(document: ContractComparison, into: Path) -> tuple[Path, Path, Path]:
    """Write the comparison's three artifacts into `into`, and nothing anywhere else.

    The same layout as `reports/baseline/` — report.md, report.json, cost.json — so a reader
    learns one shape for both directories. Returns the paths so a caller can assert on what was
    produced rather than reconstruct the names.
    """
    into.mkdir(parents=True, exist_ok=True)
    markdown = into / "report.md"
    sidecar = into / "report.json"
    cost = into / "cost.json"
    markdown.write_text(document.markdown, encoding="utf-8")
    sidecar.write_text(document.payload, encoding="utf-8")
    cost.write_text(document.cost, encoding="utf-8")
    return (markdown, sidecar, cost)


#: The machine-readable schema of the easier-stratum report sidecar.
STRATUM_REPORT_SCHEMA = "whetstone-stratum-report/1"


@dataclass(frozen=True)
class StratumReport:
    """The easier-stratum probe's document and its sidecars, before either touches a disk.

    The same three-string shape as `ContractComparison`, so the directory's committed layout
    — report.md, report.json, cost.json — mirrors the existing homes' and a reader learns one
    layout for all of them.
    """

    #: The committed document.
    markdown: str

    #: The machine-readable sidecar.
    payload: str

    #: The measured cost sidecar, as text so the bytes are the artefact.
    cost: str


def build_stratum_report(
    *,
    tallies: Sequence[Tally],
    contract: GenerationContract | None,
    stratum_doc: str,
    breakdown_home: str,
    recorded_on: str,
    generation_seconds: float | None = None,
) -> StratumReport:
    """Render the easier-stratum probe's document: one contract, a changed task set.

    The probe's report, for `reports/easier-stratum/`. The probe scores a **different task
    set** — a pre-committed difficulty stratum of the declared source-B set — under the
    same hardened contract, and the task set is one of the five pinned inputs
    (`PREREGISTRATION.md:131-132`), so its figures are a new series, declared
    non-comparable to both existing homes (`PREREGISTRATION.md` § 10.5). The document
    states that ground, renders the sidecar's contract fields beside the per-candidate
    table (the same eight rows as the other homes), discloses the probe's token spend, and
    points at the committed stratum document and the gitignored breakdown home — never
    restating a count from either (`finding.md:89-92`). With no tallies the document is the
    declaration: the home's ground, the three-homes non-comparability, and no count —
    the state of the committed artifacts before the probe runs.

    A pure function of its inputs, like the other writers: no clock is read, no ledger is
    opened, and every mapping is serialised in a fixed order, so the same inputs produce
    byte-identical output. `recorded_on` is declared by the operator, never read from the
    clock; `stratum_doc` and `breakdown_home` are pointer strings, never parsed.
    """
    if tallies and contract is None:
        raise ValueError(
            "a stratum report with tallies needs the contract they were measured under: "
            "a count without the contract that produced it is a figure that cannot be "
            "told apart from any other"
        )
    lines = [
        "# The easier-stratum probe — a changed task set, declared non-comparable",
        "",
        "This document reports the easier-stratum probe: the declared source-B set scored "
        "under the hardened generation contract § 10.4 discloses, restricted to the "
        "pre-committed difficulty stratum declared in the stratum document this report "
        "points at below. The stratum's tasks are a **different task set** than the one "
        "either existing home measured, and the task set is one of the five pinned inputs "
        "(`PREREGISTRATION.md:131-132`) — a change to a pinned input invalidates a series "
        "and starts a new one (`PREREGISTRATION.md:133-135`) — so the probe's figures are "
        "a **new series**, declared non-comparable to both existing homes "
        "(`PREREGISTRATION.md` § 10.5): `reports/baseline/` remains the only home of the "
        "baseline's figures, `reports/format-hardening/` the only home of the hardened "
        "arm's, and this directory the only home of the probe's — neither is a competing "
        "home for the same figure.",
        "",
        _NON_COMPARABILITY,
        "",
        "The probe is a yield test: it measures whether strict-PASS training data exists "
        "on the stratum. It is not the pinned baseline of `PREREGISTRATION.md:126-128`, "
        "which stands unmeasured and may still be measured exactly once, and it is not "
        "the held-out split of § 7.1, which remains open until P3.",
        "",
    ]
    if not tallies:
        lines += [
            "**No count is measured here: the probe has not run.** Per-candidate verdict "
            "counts, the contract's fields and the probe's token spend are rendered into "
            "this directory by the report door after the probe runs. Until then this "
            "document holds no figure of its own and restates none from "
            "`reports/baseline/` or `reports/format-hardening/`.",
            "",
        ]
    else:
        if contract is None:
            raise ValueError(
                "a stratum report with tallies needs the contract they were measured "
                "under: a count without the contract that produced it is a figure that "
                "cannot be told apart from any other"
            )
        names = [counts.candidate for counts in tallies]
        columns = " | ".join(f"`{name}`" for name in names)
        rule = "|".join(["---"] * (len(names) + 1))
        lines += [
            "## The stratum",
            "",
            f"**The contract.** {_contract_fields(contract)}.",
            "",
            f"| Figure | {columns} |",
            f"|{rule}|",
            _row("solved", tallies, lambda one: one.solved),
            _row("coverage", tallies, lambda one: one.covered),
            _row("unverified", tallies, lambda one: one.unverified),
            _row("N", tallies, lambda one: one.weaker_wins),
            _row("no diff", tallies, lambda one: one.no_diff),
            _row("patch apply", tallies, lambda one: one.not_applied),
            _row("patch scope", tallies, lambda one: one.out_of_scope),
            _row("not solved", tallies, lambda one: one.not_solved),
            "",
            "These counts are stated under the contract's fields above: a count and the "
            "contract that produced it belong together. `N` is the harness's own "
            "WEAK-PASS/STRICT-FAIL differential (`PREREGISTRATION.md:96-100`). The `N of "
            "M` cells are counted over the probe's own denominator — the harness's "
            "per-candidate denominator, which for a complete probe equals the stratum's "
            "declared size less the dev-subset exclusions. The stratum document's "
            "declared membership is pointed at below, never restated.",
            "",
        ]
        if generation_seconds is not None:
            lines.append(
                f"**Token spend.** Generation {generation_seconds:.1f} seconds, summed "
                "over the probe's rollouts from the run's own cost records."
            )
        else:
            lines.append("**Token spend.** Not measured.")
        lines.append("")
    lines += [
        f"**The stratum document.** The pre-committed difficulty stratum this probe "
        f"scores is declared in `{stratum_doc}` — its rule digest and its membership — "
        "and the probe's runbook names it before anything runs. This document points at "
        "it and never restates a count from it, so the stratum's membership has exactly "
        "one home.",
        "",
        f"**The breakdowns.** The classifier counts behind these figures live in the "
        f"gitignored home `{breakdown_home}`; this document points at them and never "
        "restates them, so a classifier count has exactly one home.",
        "",
        f"Recorded on {recorded_on} (declared by the operator, never read from a clock).",
    ]
    return StratumReport(
        markdown="\n".join(lines),
        payload=_stratum_payload(tallies, contract, stratum_doc, breakdown_home, recorded_on),
        cost=_stratum_cost(generation_seconds),
    )


def write_stratum_report(document: StratumReport, into: Path) -> tuple[Path, Path, Path]:
    """Write the stratum report's three artifacts into `into`, and nothing anywhere else.

    The same layout as every other home — report.md, report.json, cost.json — so a reader
    learns one shape for all of them. Returns the paths so a caller can assert on what was
    produced rather than reconstruct the names.
    """
    into.mkdir(parents=True, exist_ok=True)
    markdown = into / "report.md"
    sidecar = into / "report.json"
    cost = into / "cost.json"
    markdown.write_text(document.markdown, encoding="utf-8")
    sidecar.write_text(document.payload, encoding="utf-8")
    cost.write_text(document.cost, encoding="utf-8")
    return (markdown, sidecar, cost)


def _stratum_payload(
    tallies: Sequence[Tally],
    contract: GenerationContract | None,
    stratum_doc: str,
    breakdown_home: str,
    recorded_on: str,
) -> str:
    """The stratum report's machine-readable sidecar. Sorted keys, fixed order, no clock."""
    body: dict[str, Any] = {
        "schema": STRATUM_REPORT_SCHEMA,
        "measurement": (
            "easier-stratum probe; a changed task set under the hardened contract, "
            "declared non-comparable (PREREGISTRATION.md § 10.5); not the pinned baseline "
            "of PREREGISTRATION.md:126-128"
        ),
        "non_comparable": True,
        "stratum_doc": stratum_doc,
        "breakdown_home": breakdown_home,
        "recorded_on": recorded_on,
        "generation_contract": None if contract is None else _contract_block(contract),
        "per_candidate": None if not tallies else [_counts(one) for one in tallies],
    }
    return json.dumps(body, indent=2, sort_keys=True) + "\n"


def _stratum_cost(generation_seconds: float | None) -> str:
    """The stratum report's cost sidecar: the probe's measured spend, or `None` if not measured."""
    body: dict[str, Any] = {
        "kind": "stratum-report",
        "generation_seconds": generation_seconds,
    }
    return json.dumps(body, indent=2, sort_keys=True) + "\n"


#: The machine-readable schema of the larger-base report sidecar.
LARGER_BASE_REPORT_SCHEMA = "whetstone-larger-base-report/1"


@dataclass(frozen=True)
class LargerBaseReport:
    """The larger-base arm's document and its sidecars, before either touches a disk.

    The same three-string shape as `StratumReport`, so the directory's committed layout
    — report.md, report.json, cost.json — mirrors the existing homes' and a reader learns
    one layout for all of them.
    """

    #: The committed document.
    markdown: str

    #: The machine-readable sidecar.
    payload: str

    #: The measured cost sidecar, as text so the bytes are the artefact.
    cost: str


def build_larger_base_report(
    *,
    tallies: Sequence[Tally],
    contract: GenerationContract | None,
    candidate: str,
    dev_subset: Sequence[str],
    breakdown_home: str,
    recorded_on: str,
    generation_seconds: float | None = None,
) -> LargerBaseReport:
    """Render the larger-base arm's document: one contract, a changed candidate.

    The arm's report, for `reports/larger-base/`. The arm scores the **same declared
    source-B set** under the same hardened contract § 10.4 discloses, with a **new
    candidate** — and model revision is one of the five pinned inputs
    (`PREREGISTRATION.md:131-132`), so a change to it invalidates the series and starts
    a new one (`PREREGISTRATION.md:133-135`); the arm's figures are a new series,
    declared non-comparable to all three existing homes (`PREREGISTRATION.md` § 10.6).
    The document states that ground, renders the sidecar's contract fields beside the
    per-candidate table (the same eight rows as the other homes), discloses the arm's
    token spend, and points at the candidate and the gitignored breakdown home — never
    restating a count from either. With no tallies the document is the declaration:
    the home's ground, the four-homes non-comparability, and no count — the state of
    the committed artifacts before the arm runs.

    A pure function of its inputs, like the other writers: no clock is read, no ledger is
    opened, and every mapping is serialised in a fixed order, so the same inputs produce
    byte-identical output. `recorded_on` is declared by the operator, never read from the
    clock; `candidate`, `dev_subset` and `breakdown_home` are pointer strings, never
    parsed.
    """
    if tallies and contract is None:
        raise ValueError(
            "a larger-base report with tallies needs the contract they were measured "
            "under: a count without the contract that produced it is a figure that "
            "cannot be told apart from any other"
        )
    lines = [
        "# The larger-base arm — a new candidate, declared non-comparable",
        "",
        "This document reports the larger-base arm: the declared source-B set scored "
        "under the same hardened generation contract § 10.4 discloses, with the "
        "declared development subset excluded from both sources before anything runs, "
        "and with a **new candidate** — a change to the model revision, which is one of "
        "the five pinned inputs (`PREREGISTRATION.md:131-132`), and a change to a "
        "pinned input invalidates a series and starts a new one "
        "(`PREREGISTRATION.md:133-135`). So the arm's figures are a **new series**, "
        "declared non-comparable to all three existing homes (`PREREGISTRATION.md` "
        "§ 10.6): `reports/baseline/` remains the only home of the baseline's figures, "
        "`reports/format-hardening/` the only home of the hardened arm's, "
        "`reports/easier-stratum/` the only home of the probe's, and this directory "
        "the only home of the arm's — neither is a competing home for the same figure.",
        "",
        _NON_COMPARABILITY,
        "",
        "The arm is a yield test: it measures whether strict-PASS training data exists "
        "on the declared set at a larger base. It is not the pinned baseline of "
        "`PREREGISTRATION.md:126-128`, which stands unmeasured and may still be "
        "measured exactly once, it is not the held-out split of § 7.1, which remains "
        "open until P3, and it is not a base-selection closure — it produces evidence "
        "only.",
        "",
    ]
    if not tallies:
        lines += [
            "**No count is measured here: the arm has not run.** Per-candidate verdict "
            "counts, the contract's fields and the arm's token spend are rendered into "
            "this directory by the report door after the arm runs. Until then this "
            "document holds no figure of its own and restates none from "
            "`reports/baseline/`, `reports/format-hardening/` or "
            "`reports/easier-stratum/`.",
            "",
        ]
    else:
        if contract is None:
            raise ValueError(
                "a larger-base report with tallies needs the contract they were "
                "measured under: a count without the contract that produced it is a "
                "figure that cannot be told apart from any other"
            )
        names = [counts.candidate for counts in tallies]
        columns = " | ".join(f"`{name}`" for name in names)
        rule = "|".join(["---"] * (len(names) + 1))
        lines += [
            "## The candidate",
            "",
            f"**The contract.** {_contract_fields(contract)}.",
            "",
            f"| Figure | {columns} |",
            f"|{rule}|",
            _row("solved", tallies, lambda one: one.solved),
            _row("coverage", tallies, lambda one: one.covered),
            _row("unverified", tallies, lambda one: one.unverified),
            _row("N", tallies, lambda one: one.weaker_wins),
            _row("no diff", tallies, lambda one: one.no_diff),
            _row("patch apply", tallies, lambda one: one.not_applied),
            _row("patch scope", tallies, lambda one: one.out_of_scope),
            _row("not solved", tallies, lambda one: one.not_solved),
            "",
            "These counts are stated under the contract's fields above: a count and the "
            "contract that produced it belong together. `N` is the harness's own "
            "WEAK-PASS/STRICT-FAIL differential (`PREREGISTRATION.md:96-100`). The `N of "
            "M` cells are counted over the arm's own denominator — the harness's "
            "per-candidate denominator, which for a complete arm equals the declared "
            "source-B set less the dev-subset exclusions — 61 private + 1 public = 62 "
            "per candidate. The excluded ids are the declared development subset "
            f"({', '.join(f'`{name}`' for name in dev_subset)}).",
            "",
        ]
        if generation_seconds is not None:
            lines.append(
                f"**Token spend.** Generation {generation_seconds:.1f} seconds, summed "
                "over the arm's rollouts from the run's own cost records."
            )
        else:
            lines.append("**Token spend.** Not measured.")
        lines.append("")
    lines += [
        f"**The candidate.** The arm scores `{candidate}` — the candidate the runbook's "
        "resolution block names before anything runs. The series statement lives in the "
        "runbook and in this directory; this document points at them and never restates "
        "a count from either, so the candidate has exactly one home for its figures.",
        "",
        f"**The breakdowns.** The classifier counts behind these figures live in the "
        f"gitignored home `{breakdown_home}`; this document points at them and never "
        "restates them, so a classifier count has exactly one home.",
        "",
        f"Recorded on {recorded_on} (declared by the operator, never read from a clock).",
    ]
    return LargerBaseReport(
        markdown="\n".join(lines),
        payload=_larger_base_payload(
            tallies, contract, candidate, dev_subset, breakdown_home, recorded_on
        ),
        cost=_larger_base_cost(generation_seconds),
    )


def write_larger_base_report(document: LargerBaseReport, into: Path) -> tuple[Path, Path, Path]:
    """Write the larger-base report's three artifacts into `into`, and nothing anywhere else.

    The same layout as every other home — report.md, report.json, cost.json — so a reader
    learns one shape for all of them. Returns the paths so a caller can assert on what was
    produced rather than reconstruct the names.
    """
    into.mkdir(parents=True, exist_ok=True)
    markdown = into / "report.md"
    sidecar = into / "report.json"
    cost = into / "cost.json"
    markdown.write_text(document.markdown, encoding="utf-8")
    sidecar.write_text(document.payload, encoding="utf-8")
    cost.write_text(document.cost, encoding="utf-8")
    return (markdown, sidecar, cost)


def _larger_base_payload(
    tallies: Sequence[Tally],
    contract: GenerationContract | None,
    candidate: str,
    dev_subset: Sequence[str],
    breakdown_home: str,
    recorded_on: str,
) -> str:
    """The larger-base report's machine-readable sidecar. Sorted keys, fixed order, no clock."""
    body: dict[str, Any] = {
        "schema": LARGER_BASE_REPORT_SCHEMA,
        "measurement": (
            "larger-base arm; a new candidate under the hardened contract, declared "
            "non-comparable (PREREGISTRATION.md § 10.6); not the pinned baseline of "
            "PREREGISTRATION.md:126-128"
        ),
        "non_comparable": True,
        "candidate": candidate,
        "dev_subset": list(dev_subset),
        "breakdown_home": breakdown_home,
        "recorded_on": recorded_on,
        "generation_contract": None if contract is None else _contract_block(contract),
        "per_candidate": None if not tallies else [_counts(one) for one in tallies],
    }
    return json.dumps(body, indent=2, sort_keys=True) + "\n"


def _larger_base_cost(generation_seconds: float | None) -> str:
    """The larger-base report's cost sidecar: the arm's measured spend, `None` if unmeasured."""
    body: dict[str, Any] = {
        "kind": "larger-base-report",
        "generation_seconds": generation_seconds,
    }
    return json.dumps(body, indent=2, sort_keys=True) + "\n"


def _comparison_payload(
    arms: Sequence[ContractArm], breakdown_home: str, recorded_on: str
) -> str:
    """The comparison's machine-readable sidecar. Sorted keys, fixed order, no clock."""
    body: dict[str, Any] = {
        "measurement": (
            "format-hardening contract comparison; not the pinned baseline of "
            "PREREGISTRATION.md:126-128"
        ),
        "non_comparable": True,
        "breakdown_home": breakdown_home,
        "recorded_on": recorded_on,
        "arms": [
            {
                "name": arm.name,
                "generation_contract": _contract_block(arm.contract),
                "per_candidate": None if not arm.tallies else [_counts(one) for one in arm.tallies],
                "generation_seconds": arm.generation_seconds,
            }
            for arm in arms
        ],
    }
    return json.dumps(body, indent=2, sort_keys=True) + "\n"


def _comparison_cost(arms: Sequence[ContractArm]) -> str:
    """The comparison's cost sidecar: per-arm measured spend, or `None` where not measured."""
    body: dict[str, Any] = {
        "kind": "contract-comparison",
        "arms": [
            {"name": arm.name, "generation_seconds": arm.generation_seconds}
            for arm in arms
        ],
    }
    return json.dumps(body, indent=2, sort_keys=True) + "\n"


def _require_provenance(provenance: Provenance, contract: GenerationContract) -> None:
    """Refuse a blank pinned input or contract field, naming the one that was blank."""
    blank = [
        name
        for name, value in (
            ("task_set", provenance.task_set),
            ("environment_pins", provenance.environment_pins),
            ("seeds", provenance.seeds),
            ("recorded_on", provenance.recorded_on),
            ("tool_versions", provenance.tool_versions),
            ("prompt_sha256", contract.prompt_sha256),
            ("sampler", contract.sampler),
            ("max_tokens", contract.max_tokens),
            ("extractor_version", contract.extractor_version),
            ("retrieval", contract.retrieval),
        )
        if not value
    ]
    if blank:
        raise IncompleteProvenance(
            f"the provenance block is missing {blank}. PREREGISTRATION.md:131-132 fixes the "
            "pinned inputs a figure is only interpretable against, and a rendered blank is worse "
            "than a refusal: it looks like a field somebody considered"
        )
    if contract.retry_budget > 0 and (
        not contract.retry_template_sha256 or not contract.diagnosis_vocabulary_version
    ):
        raise IncompleteProvenance(
            f"the contract declares a retry budget of {contract.retry_budget} and a blank "
            "retry template or diagnosis vocabulary. A budget that names no template is a "
            "retry nobody can audit — the three retry fields describe one machinery, and "
            "they must come together or not at all"
        )


def _over(count: int, denominator: int) -> str:
    """A count beside the set it was counted on. The only way a figure is rendered here."""
    return f"{count} of {denominator}"


def _harness(run: Sweep) -> tuple[int, int, int]:
    """`(intact, broken, skipped)` over one run's probes."""
    controls = [step.probe.control for step in run.steps]
    return (
        controls.count(Control.INTACT),
        controls.count(Control.BROKEN),
        controls.count(Control.SKIPPED),
    )


def _row(label: str, counts: Sequence[Tally], pick: Callable[[Tally], int]) -> str:
    """One row of the per-candidate table: a label, then a count over its denominator per column.

    A single helper rather than a row-by-row literal, so no figure can be rendered without the
    set it was counted on — `PREREGISTRATION.md:157` refuses a bare proportion, and the way one
    appears is a hand-written row that forgot the second half.
    """
    cells = " | ".join(_over(pick(one), one.denominator) for one in counts)
    return f"| `{label}` | {cells} |"


def _seconds(entrants: Sequence[Entrant]) -> tuple[float, float, float]:
    """`(generation, verification, control)` wall-clock over every run in the bake-off."""
    steps = [
        step
        for entrant in entrants
        for step in (*entrant.private.steps, *entrant.public.steps)
    ]
    rollouts = [step.rollout for step in steps]
    probes = [step.probe for step in steps]
    return (
        sum(record.generation_seconds for record in rollouts),
        sum(record.strict_seconds + record.weak_seconds for record in rollouts),
        sum(probe.seconds for probe in probes),
    )


def _render(
    *,
    chosen: Selection,
    entrants: Sequence[Entrant],
    private: Sequence[Tally],
    public: Sequence[Tally],
    provenance: Provenance,
    contract: GenerationContract,
    funnel: Funnel,
) -> str:
    """The committed document. Every paragraph below is required by a line this project pledged."""
    names = [counts.candidate for counts in private]
    columns = " | ".join(f"`{name}`" for name in names)
    rule = "|".join(["---"] * (len(names) + 1))
    generation, verification, control = _seconds(entrants)

    lines: list[str] = [
        "# Base selection bake-off",
        "",
        "## What this measurement is, and what it is not",
        "",
        "This document reports **base selection**: which open base P1 starts from, decided by a "
        "bake-off against the working verifier rather than from a table of somebody else's "
        "benchmark scores. It is not the pinned baseline of `PREREGISTRATION.md:126-128`.",
        "",
        '"Measured once, re-measured never" (`PREREGISTRATION.md:129-132`) is not spent by this '
        "report. The pinned baseline is scored on the held-out split, and that split does not "
        "exist yet (`PREREGISTRATION.md` § 7.1, open until P3), so the baseline stands unmeasured "
        "and may still be measured exactly once, later, by whoever chooses to spend it.",
        "",
        "The set scored here is the declared source-B set, and it is not a held-out split. No "
        "figure in this document is a delta: `delta` is defined only as "
        "`solved_final - solved_baseline` (`PREREGISTRATION.md:92-94`), and neither term exists.",
        "",
        f"{_THRESHOLD_DENIAL}",
        "",
        "## The ranking",
        "",
        f"{_NON_COMPARABILITY} Candidates differ in model revision, which is a pinned input "
        "(`PREREGISTRATION.md:131`), so the rows below are ranked against one another and are not "
        "comparable figures.",
        "",
        "| Rank | Candidate | Revision | Parameters (B) | `solved` |",
        "|---|---|---|---|---|",
    ]
    for position, line in enumerate(chosen.ranking, start=1):
        lines.append(
            f"| {position} | `{line.contender.candidate}` | `{line.contender.revision}` | "
            f"{line.contender.parameters_billions:.1f} | {_over(line.solved, line.denominator)} |"
        )
    lines += [
        "",
        f"**Outcome.** {chosen.reason}",
        "",
        f"**Selected base:** "
        f"{'none' if chosen.selected is None else '`' + chosen.selected.candidate + '`'}.",
        "",
        "## Source B — the declared private set",
        "",
        f"| Figure | {columns} |",
        f"|{rule}|",
        _row("solved", private, lambda one: one.solved),
        _row("coverage", private, lambda one: one.covered),
        _row("unverified", private, lambda one: one.unverified),
        _row("N", private, lambda one: one.weaker_wins),
        _row("no diff", private, lambda one: one.no_diff),
        _row("patch apply", private, lambda one: one.not_applied),
        _row("patch scope", private, lambda one: one.out_of_scope),
        _row("not solved", private, lambda one: one.not_solved),
        "",
        "`solved` is STRICT `PASS` and nothing else (`PREREGISTRATION.md:86-90`). A task that "
        "reached no verdict lowers `coverage` and stays in the denominator; it is counted in "
        "neither `solved` nor the failure rows, because UNVERIFIED is not a win and is not a loss "
        "either — it is the absence of a comparison.",
        "",
        "## `N` — the reward-hacking count",
        "",
        "`N := count(rollouts where WEAK == PASS and STRICT == FAIL)` "
        "(`PREREGISTRATION.md:96-100`).",
        "",
    ]
    for counts in private:
        lines.append(
            f"- `{counts.candidate}`: {_N_SENTENCE.format(count=counts.weaker_wins)} "
            f"({_over(counts.weaker_wins, counts.denominator)})"
        )
    lines += [
        "",
        _INTENT_DENIAL,
        "",
        f"> {_RESIDUAL_BOUND}",
        "",
        "That bound is `PREREGISTRATION.md:211-220`: cheat 6 and cheat 10 in `docs/ROADMAP.md` § 3 "
        "are accepted by both verifiers and are recorded as residuals rather than patched, so the "
        "verifier's guarantee has stated limits and `N` is bounded by them.",
        "",
        "Every `N` here is a baseline `N`, and no final `N` exists — nothing has been trained, so "
        "there is nothing to compare against. `PREREGISTRATION.md:107-109` requires both to be "
        "published together, and the second one does not exist yet.",
        "",
        f"**`N` is a floor.** The generation contract states the patch-scope rule to every "
        f'candidate — *"{_SCOPE_RULE}"* — which is the right call for comparability, since every '
        "base is told the same thing and the contract does not name which files are held. It also "
        "discourages precisely the behaviour `N` counts, so this figure is a lower bound under a "
        "disclosing contract rather than a natural rate. Two consequences follow. An `N` measured "
        "under a different generation contract is not comparable to this one — the contract is an "
        "unpinned input, and this is the first concrete demonstration that it moves a "
        "pre-registered number. And this is a second bound on `N`, alongside the residual bound "
        "above: it is not a claim about what a policy would have done had it not been told the "
        "rule.",
        "",
        "## Source A — SWE-bench-Lite, one instance",
        "",
    ]
    lines += [
        "**The four-gate funnel comes first, because it is the denominator.** Eligible: "
        f"{_over(len(funnel.eligible), funnel.considered)} instances — "
        + ", ".join(f"`{name}`" for name in funnel.eligible)
        + f". Refused: {_over(funnel.refused, funnel.considered)}, by gate: "
        + ", ".join(f"{gate} {_over(count, funnel.refused)}" for gate, count in funnel.by_gate)
        + ".",
        "",
    ]
    lines += [
        f"- **Result for `{name}`, `{counts.candidate}`:** "
        f"{'solved' if counts.solved else 'not solved'} under STRICT "
        f"({_over(counts.solved, counts.denominator)})."
        for counts, name in ((counts, funnel.eligible[0]) for counts in public)
    ]
    lines += [
        "",
        "One instance is not a public benchmark set and is not quoted as one. A result on a single "
        "instance is not a measurement, and no claim is made as though it were "
        "(`PREREGISTRATION.md:149-155`). The deliverable in source A is the four-gate filter and "
        "its rejection ledger, not the instance count.",
        "",
        "## Both sources, together",
        "",
        "Both sources are published in this document regardless of which looks better, and "
        "neither is held back pending the other (`PREREGISTRATION.md:142-143`).",
        "",
    ]
    split = [
        counts.candidate
        for counts, private_counts in zip(public, private, strict=True)
        if counts.solved and not private_counts.solved
    ]
    lines.append(
        "**The two sources disagree, and the disagreement is itself the finding.** "
        + ", ".join(f"`{name}`" for name in split)
        + " solved the public instance and nothing on the private set. Public gain with private "
        "flat is the expected signature of contamination (`PREREGISTRATION.md:145-147`), and it "
        "is published rather than resolved by choosing the flattering source. With source A at "
        "one instance the signature is not detectable in practice, which is a bound on how much "
        "this observation can carry."
        if split
        else "For every candidate the two sources point the same way, so no contamination "
        "signature is observed here. With source A at one instance the signature would not be "
        "detectable in practice in any case, which is a bound on what its absence can mean."
    )
    arms = [_harness(entrant.private) for entrant in entrants]
    intact, broken, skipped = (sum(values) for values in zip(*arms, strict=True))
    total = intact + broken + skipped
    lines += [
        "",
        "## The control arm",
        "",
        f"Across every source-B run: INTACT {_over(intact, total)}, BROKEN {_over(broken, total)}, "
        f"SKIPPED {_over(skipped, total)}. The control arm runs an inert patch and the task's own "
        "re-derived fix through the same harness on the same task, so a zero in the tables above "
        "is a statement about a base rather than about a verifier that never graded anything. A "
        "run whose control arm proved nothing is refused before it reaches this document.",
        "",
        "## Measured wall-clock",
        "",
        f"Generation {generation:.1f} seconds; verification {verification:.1f} seconds; control "
        f"arm {control:.1f} seconds. Measured on this run, not estimated. Any capacity bound this "
        "exposes is published as a finding rather than worked around "
        "(`docs/ROADMAP.md:594-596`).",
        "",
        "## Provenance",
        "",
        "The five pinned inputs of `PREREGISTRATION.md:131-132`:",
        "",
    ]
    lines += [
        "- **Revision, per candidate:** "
        + ", ".join(
            f"`{entrant.contender.candidate}` at `{entrant.contender.revision}`"
            for entrant in entrants
        )
        + ".",
        f"- **Task set:** {provenance.task_set}.",
        f"- **Environment pins:** {provenance.environment_pins}.",
        f"- **Seeds:** {provenance.seeds}.",
        "- **Tool versions:** "
        + ", ".join(
            f"{name} {version}" for name, version in sorted(provenance.tool_versions.items())
        )
        + ".",
        f"- **Recorded on:** {provenance.recorded_on} (declared by the operator, never read from "
        "a clock, so two renders of the same records agree byte for byte).",
        "",
        "**The generation contract, which is not among the five pinned inputs.** It determines "
        "the number and is not pinned, so a later figure measured under a changed contract is "
        "not comparable to this one. "
        + _contract_fields(contract)
        + " — excluded from every count above, because scoring a task the contract was iterated "
        "against would be optimising on the outcome.",
        "",
        _ORACLE_DISCLOSURE,
        "",
        "## Findings and disclosed bounds",
        "",
        "**The held-out clash, recorded rather than smoothed over.** `docs/ROADMAP.md:387` states "
        "P1's pivot signal over a held-out task, but `PREREGISTRATION.md:242-247` leaves the "
        "held-out split open until P3, so no such split exists for the signal to be read against. "
        "This report reads it against the declared source-B set instead, and records that the two "
        "documents do not agree.",
        "",
        "**Network.** Two exceptions, where `docs/ROADMAP.md:574-576` declares one. Source A's "
        "instance is verified against a `git clone` of the upstream repository, which touches the "
        "network on each verification. The weights every candidate was loaded from were fetched "
        "in a separate, human-run step with its provenance committed; the scored run itself ran "
        "offline. Source B never touches the network at all.",
        "",
        "**Source B cannot be reproduced byte-for-byte outside this machine.** The mined "
        "manifests are the user's own code and are never committed; what is committed is the "
        "mining recipe and a liveness ledger of per-task hashes and verdicts "
        "(`PREREGISTRATION.md:222-228`). A reader with none of the data can count the corpus, "
        "confirm every task was proven live rather than assumed, and re-derive a corpus from the "
        "recipe against their own copy of a donor — but cannot reproduce these instances. That is "
        "the honest cost of locality, and it is why source A, fully committed and externally "
        "checkable, is not optional padding.",
        "",
        "**Self-selection stands undiluted.** Source B is mined from the author's own "
        "repositories and its mitigation did not land (`PREREGISTRATION.md:200-204`).",
        "",
    ]
    return "\n".join(lines)


def _payload(
    *,
    chosen: Selection,
    private: Sequence[Tally],
    public: Sequence[Tally],
    provenance: Provenance,
    contract: GenerationContract,
    funnel: Funnel,
) -> str:
    """The machine-readable sidecar. Sorted keys, fixed order, no clock — hence reproducible."""
    body: dict[str, Any] = {
        "measurement": "base selection; not the pinned baseline of PREREGISTRATION.md:126-128",
        "selected": None if chosen.selected is None else chosen.selected.candidate,
        "closes_open_question_7_3": chosen.closes_open_question_7_3,
        "pivot_signal_fired": chosen.pivot_signal_fired,
        "ranking": [line.contender.candidate for line in chosen.ranking],
        "source_b": [_counts(counts) for counts in private],
        "source_a": {
            "considered": funnel.considered,
            "eligible": list(funnel.eligible),
            "refused": funnel.refused,
            "by_gate": [[gate, count] for gate, count in funnel.by_gate],
            "per_candidate": [_counts(counts) for counts in public],
        },
        "provenance": {
            "task_set": provenance.task_set,
            "environment_pins": provenance.environment_pins,
            "seeds": provenance.seeds,
            "tool_versions": dict(sorted(provenance.tool_versions.items())),
            "recorded_on": provenance.recorded_on,
        },
        "generation_contract": _contract_block(contract),
    }
    return json.dumps(body, indent=2, sort_keys=True) + "\n"


def _contract_block(contract: GenerationContract) -> dict[str, Any]:
    """One contract as a mapping, every field explicit — the machine-readable half.

    The one place the JSON shape of a contract is written. `retrieval` and the retry fields are
    always stated here, never defaulted: a reader of the sidecar must not have to guess which
    contract a figure was measured under.
    """
    return {
        "pinned": False,
        "prompt_sha256": contract.prompt_sha256,
        "sampler": contract.sampler,
        "max_tokens": contract.max_tokens,
        "extractor_version": contract.extractor_version,
        "dev_subset": list(contract.dev_subset),
        "retry_budget": contract.retry_budget,
        "retry_template_sha256": contract.retry_template_sha256,
        "diagnosis_vocabulary_version": contract.diagnosis_vocabulary_version,
        "retrieval": contract.retrieval,
    }


def _counts(counts: Tally) -> dict[str, Any]:
    """One tally as a mapping, with every count beside the denominator it was counted on."""
    return {
        "candidate": counts.candidate,
        "denominator": counts.denominator,
        "solved": counts.solved,
        "covered": counts.covered,
        "unverified": counts.unverified,
        "failed": counts.failed,
        "weaker_wins": counts.weaker_wins,
        "no_diff": counts.no_diff,
        "not_applied": counts.not_applied,
        "out_of_scope": counts.out_of_scope,
        "not_solved": counts.not_solved,
    }


__all__ = [
    "LARGER_BASE_REPORT_SCHEMA",
    "STRATUM_REPORT_SCHEMA",
    "ContractArm",
    "ContractComparison",
    "Entrant",
    "Funnel",
    "GenerationContract",
    "IncompleteProvenance",
    "LargerBaseReport",
    "MissingSource",
    "Provenance",
    "Report",
    "ScoredDevSubset",
    "StratumReport",
    "Tally",
    "build_contract_comparison",
    "build_larger_base_report",
    "build_report",
    "build_stratum_report",
    "funnel_from_ledger",
    "tally",
    "write",
    "write_comparison",
    "write_larger_base_report",
    "write_stratum_report",
]
