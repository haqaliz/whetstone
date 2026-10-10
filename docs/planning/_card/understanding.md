# Understanding — night-heldout-seam

**Core-loop element:** ③ the never-regress promotion gate — at the exclusion its inputs carry
(the night's training set must be disjoint from the held-out set for `check-leakage` to pass and
M2's exit criterion to be reachable); ② the nightly loop's launch chain. ① the reward does not
change: nothing under `verify/`, `tasks/`, `loop/`'s reward path or the gate's rule moves; this
unit changes an operator's sheet and the guards that hold it.

## What the work is really asking

The night runbook (`docs/planning/p2-rollouts/night-door/runbook.md`) is the operator's sheet
for the next night, and it still describes the world before `heldout-scorable`
(2026-09-27, `PREREGISTRATION.md` § 10.16): task ids in the pre-mint `belay-*` form, no
`--heldout` flag, and run ids that name artifacts that now exist. The CLI changed underneath
the sheet, so the sheet fails on its first command, and if an operator "fixed" the ids by eye
without `--heldout`, the night would train on the 12 held-out members — reproducing the
portability-arm leak that `check-leakage` already refused (4 of 6 examples:
`docs/planning/gate-leakage-guard/finding.md`). The gate chain halts at `check-leakage` and
M2's exit criterion — `whetstone gate` returns `promoted`/`rejected` on a real pair
(`docs/ROADMAP.md` § 14) — stays unreachable. M2 was the previous unit's mandate; this is its
loose end.

## Facts the dig established (all verified against the worktree @ 4967f57)

- **`--heldout` is deliberately optional on the night CLI** (`cli.py:414-429`):
  *"Off by default: without the flag the night is today's night, byte for byte."* Code that
  made it required would break byte-compat determinism; the sheet is the surface that commits
  the real night to the pinned input. Do **not** make it a required flag.
- **A stale dev id is a hard refusal, not a silent no-op:** `UnknownDevSubset`
  (`src/whetstone/bakeoff/run.py:1033-1052`) fires after both corpora load, for probe and
  night alike (same `_partition` path, `night.py:255-257`), naming the unmatched ids. So the
  current sheet's five `belay-*` ids refuse the run before a single draw (runbook.md:73-77,
  117-121).
- **The exclusion order is dev-overlay first, held-out second** (`night.py:249-261`): the
  partition excludes the five dev ids, then the held-out membership is filtered from the
  post-overlay tasks. A dev id inside the held-out band is exclusion, never a refusal
  (`night.py:227-230`). **New denominator: 51 private (66 − 5 dev − 10 held-out not already
  dev-excluded) + 1 public = 52 tasks drawn `K` times** — the sheet's current "62 tasks"
  sentence (runbook.md:127) is wrong twice over.
- **Two of the five dev ids are now held-out members:** `donor-b-353359e9ac6e` and
  `donor-b-3e3051c4192a` (membership of `tasks/heldout/source-b.json`; all five exist in the
  re-minted corpus). The gate scores dev ids — `run_gate` has no dev-exclusion; the eval is
  exactly the held-out membership resolved against loaded tasks (`gate.py:760, 1604-1615`).
  So keeping the five is safe: the two are excluded from training by two rules, and are
  legitimately scored by the gate.
- **The sheet names artifacts that already exist.** Probe block: `--run-id probe-001`
  (runbook.md:71) and `check-probe --run $REPO/runs/night-probe/probe-001` (:87) — but
  probe-001's ledger is `whetstone-run/1`, which every reader refuses by name
  (`docs/STATUS.md` 0.21.0 entry), so the sheet's own post-probe step commands a refusal
  today. Night block: `--run-id night-001` (:115) — rerunning verbatim would rewrite the real
  night-001 documents ("read unsealed, never rewritten"). The sheet already says run ids are
  operator-declared (:46-50); the hardcoded ids contradict it.
- **The pattern to mirror is the gate runbook's guard** (`tests/test_gate_runbook_guards.py`):
  `test_the_sheet_cites_the_amendment_that_re_derived_the_split` (:802-824), the § 10.7
  refusal (:827-843), the scorable-rule sentence (:846-870), and the digest-equality halt
  (:873-894). The gate runbook's Step-5 text (runbook.md:264-267) is the wording to adapt.
- **Scope is tight.** Inventory of every `belay-*`/`contig-*` reference: only the night-door
  runbook's two commands and `test_night_runbook_guards.py`'s `DECLARED_DEV` pin
  (:84-90) are stale in the fixable sense. The larger-base and format-hardening sheets are
  historical records with remint-aware guards; the baseline-measurement sheet already passes
  `--heldout` (post-§ 10.16); autopsy/remint fixtures use old ids deliberately.
- **No other reader coupling:** `check-probe` never reads the ledger's held-out record; the
  probe still writes no checkpoint; nothing else consumes the night sheet's text.

## Contradictions with the brief

1. **The brief names one held-out dev id; the dig finds two**
   (`donor-b-353359e9ac6e` in addition to `donor-b-3e3051c4192a`). Both, not one, must be
   stated in the sheet.
2. **The brief says "re-pin the five dev ids"; the dig shows the sheet's denominator and
   run-id claims are stale too.** The five ids alone do not make the sheet commandable. The
   unit's real scope is: ids, `--heldout` + its pin, the denominator sentence, and the
   probe/night run-id declarations (fresh ids per run; never `probe-001`/`night-001`).
3. **`--heldout` is optional in the CLI by design.** The guard must pin the *sheet's* use of
   it, not the parser's.

## Consequences for the tests

- The guard suite `tests/test_night_runbook_guards.py` is the deliverable's other half:
  extend it in the gate-runbook's shape — refuse `belay-`/`contig-` ids by name, refuse a
  sheet whose probe or night command lacks `--heldout`, refuse a live § 10.7 citation, pin
  the § 10.16 sentence and the digest-readback halt, pin the corrected denominator sentence,
  and refuse a sheet naming `probe-001`/`night-001` as run ids. Each tightened assertion must
  be shown failing against the *current* sheet before the new sheet exists (the repo's
  watched-failing discipline).
- The existing dev-id test (`test_every_declared_dev_id_is_passed_and_matches_the_hardened_
  contract`, :358-371) compresses its pin; the plan decides whether to keep that shape.
- Docs shipped with the unit, in the same commit: `docs/STATUS.md` entry, `CHANGELOG.md`
  `Unreleased`, `docs/ROADMAP.md` M2 note. Nothing under `src/` changes unless the dig's
  remaining open question says otherwise.

## Open questions for the interview

1. **Probe/night run ids.** Make both `/run-id <declared-at-run-time>` (matching the sheet's
   own "Declare the inputs" text and the probe-decision-gate's fresh-id rule), with a guard
   pin that the sheet never names `probe-001`/`night-001`? Or hardcode `probe-002`/`night-002`
   as the next concrete ids?
2. **The five dev ids.** Keep all five (two overlap held-out harmlessly — recommended, the
   overlap is stated and both exclusions already apply), or trade the two overlap ids for
   non-held-out ones (which changes the dev set the contract was "developed against")?
3. **A post-night leakage step in the night sheet?** The gate runbook already commands
   `check-leakage` before the gate; a night sheet ending with the morning report covers the
   chain's own span. Add it or leave the gate step as the only commander?

## What cannot be proven here

No night or probe runs in this unit; the sheet's commands are pinned against the parser and
by the guard suite against the checked-in text, never exercised against a real corpus on a
GPU (which is the operator's step, in the primary checkout, after this merges). The unit
produces no candidate and no number, and must not be written up as advancing yield.