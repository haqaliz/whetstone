# feat night-heldout-seam — the night runbook still lives in the pre-§ 10.16 world

**Core loop element:** ③ the never-regress promotion gate — the exclusion its inputs carry (the
night's training set must be disjoint from the held-out set); ② the nightly improvement loop's
launch chain. ① the reward does not change: nothing under `verify/` or `tasks/` is touched, and
the gate's rule and exits stay byte-identical.
**Roadmap:** M2 of `docs/ROADMAP.md` § 14 — "Make the gate able to answer"; the loose end of the
`heldout-scorable` unit (2026-09-27), which updated the *gate* runbook for § 10.16 and never
touched the *night* sheet.
**Source:** inline brief — the `whetstone-next` handoff (2026-10-10). Verified 2026-10-10 that
the only open issues are #64 (patch representation) and #62 (held-out split keyed on task id),
neither naming this unit.

## Brief

The night runbook (`docs/planning/p2-rollouts/night-door/runbook.md`) and its guard
(`tests/test_night_runbook_guards.py`) still pin the pre-re-mint world:

1. **The five `--dev-subset belay-*` ids no longer exist.** The corpus was re-minted under
   `--label` by `heldout-scorable` (§ 10.16, 2026-09-27): every id is now
   `donor-b-<sha12>`/`donor-a-<sha12>` form. The CLI refuses an id matching no task ("an id
   matching no task is refused, because it would exclude nothing while the ledger said it
   had" — `cli.py`), so the sheet fails on its first command.
2. **The sheet never passes `--heldout` at all.** A night run verbatim draws the full private
   corpus including the 12 held-out members (`night.py` excludes only when the flag is given),
   reproducing the exact seam failure that produced `checkpoints/portability-arm`, refused by
   `whetstone check-leakage` (4 of 6 training examples on a held-out task —
   `docs/planning/gate-leakage-guard/finding.md`). With no `--heldout` the next night's
   training set is *guaranteed* non-clean against `tasks/heldout/source-b.json`
   (schema `whetstone-heldout/1`, re-derived under § 10.16), so the gate chain halts at
   `check-leakage` and M2's exit criterion — `whetstone gate` returns `promoted`/`rejected`
   on a real pair — stays unreachable.

**Scope expectation (verify in the dig):** re-pin the five dev ids in their post-mint
`donor-b-*` forms, add `--heldout $REPO/tasks/heldout/source-b.json` to the probe and night
commands with the § 10.16 pin and digest read-back mirroring the gate runbook's, and extend
the guards (test-first, watched-failing, per this repo's discipline) to refuse a `belay-`/
`contig-` id, a missing `--heldout`, or a live § 10.7 citation.

**Caveats.** One dev id, `donor-b-3e3051c4192a` (ex-`belay-3e3051c4192a`), is now a
**held-out member** under § 10.16; resolve in the dig whether the gate excludes dev ids from
the held-out denominator, and state the overlap in the sheet deliberately rather than silently
keeping or dropping an id. The whole-function measurement run (M1) and the night itself remain
operator-executed: this unit produces no candidate and claims no number, and must not be
written up as advancing yield.

## Acceptance criteria (from the handoff)

1. The runbook's probe and night commands pass `--heldout` at the committed
   `tasks/heldout/source-b.json`, with the § 10.16 pin and digest read-back held by the guard
   (mirroring `test_gate_runbook_guards.py`).
2. The five dev ids are re-pinned in their post-mint `donor-b-*` form; the guard refuses a
   `belay-`/`contig-` id by name; the sheet states the two ids that are now held-out members.
3. The guards are shown **failing against the current stale sheet** before the new sheet exists
   (the repo's watched-failing discipline).
4. Nothing under `verify/`, `tasks/` or the reward path changes; the gate's rule, exits and
   retry discipline stay byte-identical.
5. Docs corrected in the same commit: night runbook header/branch, STATUS entry, CHANGELOG
   (`Unreleased`), ROADMAP M2 note — this unit makes a claim, so it ships its write-up with it.