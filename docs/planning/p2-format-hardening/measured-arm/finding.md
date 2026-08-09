# Finding — the measured arm's before/after, tooled and held

**Slice:** `p2-format-hardening` measured arm, completed by `format-hardening-measurement` ·
**Written:** 2026-08-10, after the comparison instrument ran over the two stored arms.
**Instrument:** `src/whetstone/bakeoff/comparison.py` (offline, deterministic, stdlib-only),
on the pre-analysis and the autopsy behind it · **Local evidence:**
`runs/format-hardening-preanalysis/{ceiling.json,comparison.json,comparison.md}` (gitignored —
the only home of the numbers).

---

## 1. What this document is

The measured-arm aspect (`docs/planning/p2-format-hardening/measured-arm/`) shipped its
machinery and its runbook and stopped; what it did not ship is the analysis chain the runbook
names. This unit built it, and this finding says what it produced. The operator's run now has
one deterministic post-run chain — attribution, autopsy, comparison, report door — instead of
an improvised read, and the transferable discipline is the one the diff autopsy established:
**the read is a measurement, never a hand-read.** The before/after breakdown is assembled by a
module that re-derives the trigger mapping by identity and asserts it against the decisions the
pre-analysis recorded, so a disagreement between two instruments reading the same bytes is
reported, never smoothed.

**It carries no figure about a model**: the numbers live in the gitignored breakdowns, and a
number quoted here would be a second home for itself.

## 2. The measured before

The stored arms' breakdown — both stored runs, per candidate, with each cause count beside its
delta against the named before run — was produced by the instrument, and the assertion held:
the trigger mapping re-derived by identity agrees with the pre-analysis's own decisions over
every stored record, zero violations, nothing to reconcile. Both runs carry the control
discipline (an `INTACT` probe), so their counts are proven about the bases; the denominators
are disclosed as D6 requires — each run's journal rollouts and its classified completions side
by side, different measurements of the same run, never fused — and the double-token run
carries only the candidate it swept, so its rows keep its own candidate set. The ceiling the
arm was measured against is carried from the pre-analysis document, never recomputed.

The walls, in words, per candidate:

- **One candidate is a loop-collapse wall.** Its breakdown is dominated by completions that
  repeat their own chat-template tokens — nothing that looks like an answer, let alone a
  patch — beside only a sliver of well-formed diffs. This is the shape the dig predicted, and
  the pre-analysis measured the candidate's retry-eligible ceiling as empty: a retry fires on
  a trigger-shaped parse refusal, and a loop collapse is not one.
- **A second candidate is a hunk-count wall.** Its majority shape is `hunk-count-mismatch` —
  the git-shaped skeleton whose hunk headers declare line counts the bodies do not satisfy —
  with a minority of hunks dying early and a well-formed remainder. The double-token rerun
  moved no cause bucket beyond noise: the wall is not shaped by the token budget.
- **The third candidate is a hunk-dies-early spread.** Hunks that die on a line the diff
  grammar does not accept dominate, beside a `hunk-count-mismatch` minority, a rare
  `header-without-hunk`, and a well-formed remainder.

## 3. The hold decision

**The arm itself has not run.** It is the operator's GPU pass, commanded from the runbook
(`docs/planning/p2-format-hardening/measured-arm/runbook.md`); the evidence directory the
runbook names (`runs/format-hardening-arm-evidence/`) does not exist, so there is no journal,
no transcript, and no after arm to compare.

Everything the slice planned to build exists and is verified: the pre-analysis measured the
ceiling before any GPU was spent, the runbook commands the arm, the comparison instrument is
exercised over the stored arms, the report door renders the two-contract report by identity,
and this finding records the state. What is unspent is the before/after itself — stored arms
versus the new arm — which becomes a measurement the moment the arm lands and the runbook's
post-run sequence runs. Until then, `reports/format-hardening/` still holds the declaration
aspect 3 committed: no count, no arm, and no figure the arm didn't produce.

The decision to hold is pre-committed and unchanged — the completing unit's PRD names it
(`docs/planning/format-hardening-measurement/prd.md` R-c), and the slice's own PRD makes a
flat before/after, once the arm lands, a pre-committed publishable outcome
(`p2-format-hardening/prd.md:310`). The slice is complete either way; the hold is not a
placeholder for a hoped-for result.

## 4. What is not claimed

- That the retries will raise any count — **not predicted**: a flat before/after, the new arm
  converting nothing the stored arms didn't, is a valid, publishable outcome, and the report
  will state it plainly if that is what the measurement shows.
- That `PREREGISTRATION.md` § 7.3 is closed — **untrue**: the base question stays open, and
  this slice is not a base-selection signal.
- That a base is selected — **untrue**: the roadmap's easier-stratum/larger-base fork stays
  unsupported until the arm's measurement exists.
- That the tooling measured the arm — **untrue**: it measured the stored runs. The arm's
  measurement is the operator's, unspent until the run lands.
- That this document carries a figure about a model — **it does not**: the numbers live in the
  gitignored breakdowns, and a number quoted here would be a second home for itself.

## 5. Where the evidence lives

- The instrument: `src/whetstone/bakeoff/comparison.py` (and its tests under
  `tests/bakeoff/test_comparison.py`), reusing `preanalysis.py`, the autopsy, and the
  diff-check validator by identity.
- The measurements: `runs/format-hardening-preanalysis/{ceiling.json,comparison.json,comparison.md}`
  and the stored autopsy documents `runs/diff-autopsy/{arm-a,budget-2048}.json` — gitignored,
  the only home of the numbers. The ceiling the arm will be measured against is the one the
  runbook's opening block already commits (`runbook.md:8-10`).
- **The post-run commands run from the primary checkout.** The primary owns the gitignored
  store, so the breakdown's `--out` must resolve under the primary's `runs/` — run the
  worktree's tooling with its own project, invoked from the primary root, e.g.
  `uv run --project <worktree-path> python -m whetstone.bakeoff.comparison …` executed in
  `/Users/aliz/dev/at/whetstone` (the runbook's post-run section, `runbook.md:112-144`).
