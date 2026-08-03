# Understanding — `feat/p1-preregistration/aliz`

Written before any PRD. Every claim below is grounded in a file in this tree or in a sibling
repository, with its citation. Where a committed document turned out to be **wrong**, that is
recorded as a finding rather than quietly worked around.

---

## 1. What the work is really asking

Land `PREREGISTRATION.md` — **P1 exit criterion 6** (`docs/ROADMAP.md:355-356`) — discharging the
contract in § 6 (`:478-488`).

The literal ask is small: one markdown file. **The real ask is a timing artifact.** § 6 says it is
committed *"in **P1**, before any number exists"*. Its entire value is the git timestamp: a
headline rule chosen before results are visible is a constraint; the same words chosen afterwards
are a rationalisation.

P4 then grades against it — `docs/ROADMAP.md:452-453`: *"The headline matches what
`PREREGISTRATION.md` committed to, and both sources are published together."* So the document has
a second, harder requirement: **it must be specific enough to be gradeable.** A commitment nobody
can check later is not a commitment.

## 2. Where this sits on the core loop

`CLAUDE.md` § *The core loop* has five elements. This slice touches **none of them directly** — it
adds no code to ① the verifier, ② the loop, ③ the gate, ④ the report, or ⑤ locality.

What it does is **bind ④ in advance**: it fixes what the eventual report may claim and which
number is the headline. It is a constraint on a future artifact, not an artifact of the loop.

- **The reward is untouched.** No model is invoked; no rollout runs; no verdict is produced. The
  reward-path AST guard (`tests/test_no_inference_on_reward_path.py`) stays green, unchanged scope.
- **The gate is untouched**, but the document restates the gate's honesty contract, because the
  reported number depends on it: `UNVERIFIED` is never a win (`CONTRIBUTING.md:21-23`,
  `docs/ROADMAP.md:412-413`).
- **Locality is untouched**, and is itself part of what must be disclosed: source B's evidence is
  committed but its data never is (`tasks/README.md:75-96`), which bounds what an outside reader
  can audit. That bound belongs in the pre-registration, not in a footnote found later.

## 3. The two hard constraints, and the tension between them

1. **It must precede the first number.** § 6 (`:481-482`). The bake-off — the other open P1
   criterion — produces per-source baseline scores. Those are numbers. So this document lands
   first, and `reports/baseline/` must never appear in a tree that lacks it.
2. **It must not invent numbers.** `CONTRIBUTING.md:29-32`; `CLAUDE.md:119`, quoted verbatim at
   `docs/ROADMAP.md:595-596`: *"If you need a statistic that isn't here, do not invent one; say
   it's unverified."*

These pull against each other. A pre-registration is *supposed* to fix thresholds up front, but
three things it would naturally fix are genuinely undecided (`docs/ROADMAP.md:569-574`):

| Open item | Why it cannot be fixed today | Where it gets fixed |
|---|---|---|
| Held-out split size and stratification | Depends on the corpus's difficulty distribution, unmeasured | P3 (`:436`) |
| Retry count *R* | *"to be set from the observed unverified rate rather than guessed"* (`:572`) | P3 |
| Which open base | Decided **by** the bake-off this document must precede (`:571-574`) | P1, next slice |

**The resolution this slice takes:** pre-register what is decidable now — *which* metric is the
headline, *which* source it comes from, *how* every metric is defined, what counts as failure,
and what the known limitations are — and for each open item, name it, say why it is open, and bind
the **mechanism and the deadline** for closing it (a dated amendment, committed before the
measurement it governs). An honest *"open, fixed by X before Y"* is a real commitment. A guessed
threshold is a fabricated one, and would breach `CLAUDE.md:119` in the one document whose subject
is not fooling yourself.

## 4. A committed claim in this repo is **false**, and this slice must fix it

`docs/ROADMAP.md:456-460` — inside P4, the phase this document governs — reads:

> The failure mode this phase exists to prevent is the sibling project's own: its `PHASE0_RESULTS.md`, the
> document gating PROCEED vs PIVOT, still carries 20 `TO-BE-FILLED` markers.

**Verified directly on 2026-07-29** in the sibling project's repository:

- `grep -c "TO-BE-FILLED" docs/technical/PHASE0_RESULTS.md` → **0**.
- Filled by `77adc8f` (2026-07-29, *"Phase-0 hand-audit: the default tests/ invariant has 0.00
  precision (#14)"*). The count was exactly 20 at `801b457` (2026-07-28), so the roadmap was right
  when written and went stale within about ten hours.
- Substantively the claim **inverted**: the document now records a **PIVOT** with its numbers —
  0.00 precision at 1.00 coverage, 0 true positives, a denominator of 16 against a required ≥50.
  The sibling project did not fail to fill its gating document. It filled it with a negative result and
  published it, which is exactly what `CLAUDE.md` #5 asks for.

Why this matters three ways:

1. **It is precisely the drift `tests/test_docs.py` exists to catch**, in a document that file
   guards, and no guard covered that sentence. Leaving it would have this repo overclaiming about
   a sibling's honesty — inside the section about not overclaiming.
2. **The cautionary tale survives, and is sharper.** the sibling project's own `### Ordering: what actually
   happened` admits the criteria were fixed in `docs/planning/phase0-live-mint/prd.md`
   (2026-07-21) but were **not copied into the document that publishes the number before the run**
   — *"That did not happen, and this document will not pretend otherwise."* The real lesson is
   **pre-register into the publishing document, not into a planning file**, which is exactly why
   `PREREGISTRATION.md` belongs at the repo root rather than under `docs/planning/`.
3. **It supplies the shape.** the sibling project's template wrote every section in advance and left blanks only
   under `## The Numbers` and `### Decision`, with commented-out example result lines showing the
   *shape* of an answer without asserting one.

**Decision:** correct `docs/ROADMAP.md:456-460` in this slice, and guard it so it cannot silently
re-stale. In scope: it is a false claim about the very subject of the file being written, and
`CLAUDE.md` requires the write-up and the change to land together.

## 5. What to adopt from the sibling project — and what must not be copied

**Adopt:**

- **Pre-registration is a timing control, not an independence control.** the sibling project states it outright:
  *"This is a solo project: the same person writes the criteria, runs the mint, hand-audits the
  flags, and publishes the result. Nothing here makes the audit independent."* Whetstone is in the
  identical position and must say so.
- **Publish the denominator with every rate**; state coverage and the unflattering figure; write a
  negative result as plainly as a positive one (the sibling project's six *Honesty Properties*).
- **Provenance by commit hash, verifiable with `git log`**, not by assertion.
- **Non-comparability clauses** — a number measured on one side of a changed input may not be
  compared across it. That is the operational form of § 5's *"measured once, re-measured never"*
  (`docs/ROADMAP.md:470-471`), a phrase neither sibling uses, so this document must define it.

**Do not copy: the blanks.** the sibling project's template carried 20 placeholders for ten days. A
`PREREGISTRATION.md` containing `TBD` is worse than none, because it reads as a commitment while
committing to nothing. Everything here must be decided at commit time; anything undecidable is
named as open with its closing mechanism — never left as a blank to be filled.

`donor A` has **no** analogous document (verified: no preregistration, no results contract). It
mechanises the same instinct instead — a frozen held-out baseline with a deliberate, reviewed
`--update-baseline` refreeze path. Useful precedent for the re-measurement rule; no document shape.

## 6. What the document must carry, and where each fact already lives

| Content | Source (committed) |
|---|---|
| Source B is the headline; both always published together; disagreement is a finding | `docs/ROADMAP.md:478-488` |
| `N := count(rollouts where WEAK == PASS and STRICT == FAIL)`, reported as *"N rollouts a weaker check would have scored as wins"* — about what strictness caught, **not** about intent | `docs/ROADMAP.md:106-117` |
| `N` is meaningless without a baseline `N` | `docs/ROADMAP.md:117`, `:472-474` |
| Pinned baseline checkpoint; measured once, re-measured never | `docs/ROADMAP.md:466-471` |
| `UNVERIFIED` never a win; three gate exits; coverage never silently excluded | `docs/ROADMAP.md:404-429`; `CONTRIBUTING.md:21-25` |
| What the verifier does and does not guarantee (writes confined, **reads not**; guarantee extends only as far as the manifest) | `docs/ROADMAP.md:187-190` |
| Cheats 6 and 10 are documented residuals and survive into any reported `N` | `docs/ROADMAP.md:134`, `:138`, `:151-194` |
| Source B self-selection | `docs/planning/p1-task-ingestion/prd.md:338-346` |
| Source B shape: 66 tasks (45 `donor A`, 21 the sibling project); evidence committed, data never | `tasks/README.md:8-11`, `:36-49`, `:75-96` |
| Source A: 1 eligible of 300; 192 format / 106 environment / 1 collectability; **not a benchmark set** | `tasks/README.md:13-30` |
| P4 reports, for both sources: baseline, final, delta, `N_baseline`, `N_final`, coverage, provenance | `docs/ROADMAP.md:448-454` |

**One correction to carry forward.** `docs/planning/p1-task-ingestion/prd.md:343-344` offers a
mitigation for source B's self-selection — *"D3's inclusion of donor C is the mitigation."*
**That mitigation did not land:** `donor C` was refused for having no `uv.lock`
(`tasks/README.md:171`, `docs/ROADMAP.md:371-373`). The disclosure must therefore be carried
**without** its mitigation, and say so. Copying § 8.3 verbatim would ship a claim that is no
longer true.

## 7. Contradictions and ambiguities found

1. **The stale the sibling project claim** (§ 4). Resolved: correct it here, and guard it.
2. **The unlanded mitigation** (§ 6). Resolved: state the disclosure, record that the mitigation
   was refused.
3. **"Both sources always published together" vs. a corpus of one.** § 6 requires both published;
   source A is a single instance, which cannot carry a rate — a delta on n=1 is not a measurement.
   The document must pre-register *how* source A is reported rather than letting P4 discover the
   problem. The honest answer available today: report it per-instance and with its denominator,
   never as a percentage, never as a benchmark result.
4. **The headline metric itself is undefined anywhere.** § 6 fixes *which source* is the headline;
   it never says what the headline *number* is. `docs/ROADMAP.md:449-451` lists what a report must
   contain. This slice must pick the headline figure from that list and commit to it.
   **Proposal:** the delta in **strict-PASS count on the held-out source-B split, published with
   its denominator and its coverage** — the only figure that is both execution-grounded and the
   thing the product actually claims.
5. **The card-directory convention is unsafe** — `docs/planning/_card/understanding.md` is cited by
   section from `docs/ROADMAP.md:159`, `tests/adversarial/test_cheats.py:270` (§ 2c) and
   `tests/test_docs.py:50` (§ 5G/§ 5H). Overwriting it per the skill would break live citations.
   Resolved: this slice writes its artifacts under `docs/planning/p1-preregistration/` and leaves
   `_card/` alone. Recorded in `card.md`; the skill should be amended.
6. **`_section()` cannot slice the last `##` section of a file** — it needs a following `\n## `
   (`tests/test_docs.py`, verified in the dig). Any guard over `PREREGISTRATION.md` must avoid
   `_section` on the final section, or the document must end with an unguarded section.

## 8. Guardrail check (`CLAUDE.md`)

| Guardrail | Status for this slice |
|---|---|
| Reward execution-grounded, never a judge | **Untouched.** No model invoked; the document *reasserts* the constraint |
| No frontier base-model training | **Untouched.** The base is chosen later, by the bake-off |
| `UNVERIFIED` never a win | **Reinforced** — the document binds the eventual report to it |
| No data egress | **Untouched**, and disclosed: source B's data stays local, which limits auditability |
| No hype / no invented numbers | **The whole risk of the slice.** The document must contain no figure about a model, because none exists — enforced mechanically, not by good intentions |
| Gets better as base models improve | **Neutral** — the document is base-agnostic by design; naming a base would be the mistake |

## 9. Scope

**In:** `PREREGISTRATION.md`; guards in `tests/test_docs.py` (content, no-blanks,
no-invented-number, and the `reports/`-ordering guard with real controls); the correction to
`docs/ROADMAP.md:456-460` plus a guard; the P1 status update in `docs/ROADMAP.md` and `CLAUDE.md`
from two open criteria to one; a `CHANGELOG.md` entry.

**Out:** the bake-off and `reports/baseline/` (the next slice, and the reason this one exists);
anything that runs a model; the held-out split, *R*, and the base choice (named as open, not
decided); closing cheat 6 or 10; `docs/technical/ARCHITECTURE.md`.
