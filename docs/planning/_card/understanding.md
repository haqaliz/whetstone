# Understanding — raise-k

**Unit:** `feat/raise-k/aliz` · **Written:** 2026-10-17 · **Source:** inline brief
(`docs/planning/_card/issue.md`); no GitHub issue exists.

## What the work is really asking

Change the declared sampling budget `K` (`src/whetstone/loop/sampling.py:79`, currently
`8`) to a new pre-registered value, as the last untried pre-committed response to the fired
P2 pivot — *"stratify by difficulty or raise k"* (`docs/ROADMAP.md:416`). Stratification
was tested and exhausted (night #4, `docs/ROADMAP.md` § 13), the portability arm's CPU
dtype response shipped (`PREREGISTRATION.md` § 10.18), so raise k is what remains
(`docs/planning/whole-function-edit-finding/measurement-run/finding.md` § 6).

**It is a declaration-and-record unit, not a measurement.** The night that would test a
raised `K` is operator-run and is *not* built here; this unit changes the constant, pins it,
pre-registers it, corrects the prose that names the old value, and leaves the reward path
byte-identical. This mirrors the `portability-cpu-dtype` unit exactly (a declared input
moved, recorded, and pre-registered before the governed run) — see
`docs/planning/portability-cpu-dtype/` for the template.

## Core-loop placement

Advances core-loop element **② the nightly improvement loop**. The reward path (①) is
untouched: `K` only sets how many seeded draws each task gets, and the reward remains the
STRICT verifier's re-execution of each draw. `K` is still a module constant reached only by
`run_night`'s default parameter — a policy cannot set it and a rollout cannot influence it.
The gate (③) is untouched: `UNVERIFIED` still counts as not a win.

## Affected areas (from the dig)

### The change itself
- `src/whetstone/loop/sampling.py:79` — `K = 8`, with a docstring (`:69-78`) that already
  says *"Raising it is the roadmap's named response to low yield … as an edit to this line,
  in a diff, before a night, never as an argument on a command."*

### Enforced-failure surface (goes red if not touched)
- `tests/test_docs.py:748-751` — asserts the literal `"sampling.K = 8"` is present in
  `PREREGISTRATION.md` § 10.9. **There is no doc↔code cross-pin for `sampling.K`** (unlike
  `DEVICE_PRECISION`); the test pins the literal against the document, not against the
  constant. This unit should introduce the missing cross-pin (assert the code constant
  equals the value the document names), in the `portability-cpu-dtype` shape
  (`tests/test_docs.py:1007-1013`).

### Truth surface that becomes false (no test catches it — must be corrected anyway)
- `PREREGISTRATION.md:574` — § 10.9's disclosure names `sampling.K = 8` explicitly.
- `docs/ROADMAP.md:775` — § 13 live prose: *"Raising k remains untried: `K = 8` is a
  declared constant and never a flag."* The repo convention is a dated
  `> **Corrected …**` blockquote preserving the old sentence, never an in-place edit
  (precedent: § 13's dtype correction, guarded at `tests/test_docs.py:1198-1236`).
- Inert test docstrings that assert nothing but would become false:
  `tests/test_docs.py:735`, `tests/bakeoff/test_report.py:2065,2159`,
  `tests/bakeoff/test_transcript_locality.py:126`.
- `docs/planning/_card/issue.md:37` (this unit's own card, quotes the old value).

### Guards to extend, not just satisfy
- `tests/loop/test_sampling.py:202-226` (`test_k_is_a_declared_constant_and_the_night_uses_it`)
  asserts `isinstance(K, int) and K >= 2`, `run_night`'s `draws` default `is K`, and
  `"--k" not in _cli_flags()`. **`--k` is refused but `--draws` is not asserted**, and no
  test pins the *value*. Acceptance criterion 1 must add a value-pin and widen the refusal
  to any flag that would set the budget.

### Do NOT touch (append-only history / published artifacts)
`CHANGELOG.md:1019`, `docs/STATUS.md:644,1365,1708,1714`, `docs/ROADMAP.md:419` (a dated
blockquote), all merged `docs/planning/**` dirs, `reports/portability-arm/report.md`
(measured under `K=8`; its `8` is history).

### The amendment
- Append `### 10.19 <Title> — <2026-10-17>` to `PREREGISTRATION.md`, copying the § 10.18
  (Type 1) shape: bold Type line, **What changes**, **The blast radius**, a
  comparability/non-comparability paragraph ending "the old series is not extended", and a
  closing **What is not claimed.** paragraph.
- Append one 4-column row to the amendment log at `PREREGISTRATION.md:306` (`| Date |
  Amendment | Type (§ 8) | Closes an open item |`), pinned as an exact substring by a new
  guard, per the § 10.10/§ 10.16/§ 10.17/§ 10.18 precedent.
- **No `## ` section-count guard exists**, and `PREREGISTRATION_SECTIONS`
  (`tests/test_docs.py:89-101`) omits § 10, so the section tuple needs no change.

## Ambiguity surfaced — flag, do not paper over

**Is a raised `K` a Type 1 amendment or a Type 2 disclosure? The documents disagree, and
the PRD must resolve it explicitly.**

- `docs/ROADMAP.md:775` states plainly: *"a change is a **Type 1 amendment** rather than an
  operator's choice."* § 14's M1 (`:881-883`) likewise calls a generation-contract change a
  Type 1 amendment whose figures are non-comparable.
- But `PREREGISTRATION.md:574` (§ 10.9, itself a **Type 2** amendment) says the loop's
  sampler contract *"is not a pinned input (§ 10.1), so the delta against the same series'
  baseline remains legitimate."*

**Reading proposed for the PRD, to be confirmed at the review gate:** both can hold if the
distinction is *which* comparison is at stake. § 10.9 is about the baseline-vs-final delta
*within one series* (both sides share the contract, so the categorical-vs-greedy difference
does not disqualify the delta). § 13 is about the constant being pre-committed *as a diff
before a night*, and about a change to it starting a new series. The unit's amendment should
take § 13's explicit label (Type 1) and state that every prior figure measured under `K=8`
is non-comparable — matching the dtype amendment's treatment of a moved pinned input.

## Open questions (for the PRD / review gate)

1. **The new value.** § 13/§ 14 give no number. `K` multiplies generation cost linearly
   while the control arm's cost does not (`docs/planning/p2-rollouts/night-door/runbook.md:230-231`);
   night #1 was 62 tasks × 8 draws ≈ 496 rollouts over 26.6 h (`docs/STATUS.md:1708`). What
   value, and does the night that later tests it need a bounded task set so it stays
   tractable? **This is the amendment's central parameter and belongs to the user.**
2. **Scope of the prose sweep.** Which live ROADMAP sentences get a dated correction: § 13
   only, or also § 14's M1 blockquotes that still name raise k as untried?
3. **The § 10.9 literal.** § 10.9 is a Type 2 disclosure whose text names `sampling.K = 8`.
   Is the correct move to (a) amend § 10.9 in place (it is a disclosure, arguably
   type-neutral), (b) add § 10.19 superseding it, or (c) cross-pin § 10.9 to the constant?
   The `tests/test_docs.py:750` guard must be updated either way.
4. **Does the `--draws`/budget-flag refusal belong here** (widening
   `test_k_is_a_declared_constant_and_the_night_uses_it`), or is a raised `K` the complete
   acceptance for the no-flag guard?

## Contradictions / guardrail check

- **Reward stays execution-grounded:** yes. Nothing under `src/whetstone/verify/`, `tasks/`,
  the held-out document, or the gate rule moves; `K` changes only draw counts.
- **`UNVERIFIED` is never a win:** unchanged; the gate is untouched.
- **Local / no egress:** unchanged; a night is local by construction.
- **Not redundant with a better base:** complementary — a better base raises the per-draw
  pass rate, which `K` then multiplies into examples.
- **Exactly the demotion § 14 warns of:** this is honest to record (below).

## Honest framing to carry into the PRD

`docs/ROADMAP.md:1017-1018` demotes raise k: *"It buys more samples from a pipeline where
most patches never apply; M1 is the same compute spent on the cause."* That demotion assumed
M1's cause-lever (patch representation) was available; it is now spent NO-GO in all three
forms. Raise k is therefore the honest remainder, not a strong lever — and the amendment
must claim no yield, exactly as § 10.18 does. The mechanism it does have is night #1's
clustering evidence (`docs/STATUS.md:1713-1716`): a task that can be solved solves ~half its
draws, so raising `K` multiplies yield on the tasks the base can already reach.
