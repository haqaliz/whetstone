# feat k16-night — run the pre-registered K = 16 night

**Source:** inline brief, derived from the accepted `whetstone-next` handoff (2026-10-18).
No GitHub issue exists for this slug; the open-issue list is #62 and #64, neither of which is
this work. Branch `feat/k16-night/aliz`, worktree `.claude/worktrees/feat-k16-night`.

## Brief

Run the nightly loop at its newly declared draw budget — `sampling.K = 16`
(`src/whetstone/loop/sampling.py`, `PREREGISTRATION.md` § 10.19, Type 1, 2026-10-17) — from the
operator sheet at `docs/planning/p2-rollouts/night-door/runbook.md`, and ship the finding. This
is the last untried pre-committed response to the fired P2 pivot and the only identified path to
M1's exit criterion: a night that selects at least one strict-`PASS` and therefore writes both a
ledger and a checkpoint (`docs/ROADMAP.md` § 14, M1).

The unit is **operator-run**, not a new lever: `docs/planning/raise-k/prd.md` deliberately left
the night that tests the raised budget to the operator, and no code change is known to be needed.
Any run-blocking defect the night exposes is fixed test-first, in the unit, the way night #1's
three trainer defects were fixed in 0.14.1.

Acceptance criteria (written first):

1. `whetstone check-probe --run <probe-run-id>` exits 0 — the control arm `PASS` on every draw
   and a non-empty seed map.
2. The night's ledger records `draws: 16`, and its held-out `document_digest` equals the digest
   of the committed `tasks/heldout/source-b.json`; a change is a halt, never a rerun.
3. If at least one strict-`PASS` is selected: a checkpoint exists under
   `checkpoints/<id>/`, its dataset is sealed, and
   `whetstone check-leakage --run … --checkpoint …` exits 0; then
   `whetstone gate --candidate … --incumbent <untrained base>` returns one of its three exits.
4. If none is selected: a committed finding records the per-draw partition and accepts the zero.

The reward path (`src/whetstone/verify/`), `tasks/`, the held-out document and the gate rule
stay byte-unchanged. A zero is a valid, publishable outcome; it is never answered with a fourth
edit representation or a looser verifier.

**Operational caveat.** The night is a long GPU run (52 tasks × 16 draws = 832 rollouts, against
night #1's measured 496), the GPU must be serialized, and the sheet requires the run from the
**primary checkout** — the worktree holds the unit's planning, guards and finding, but the night
itself runs from `$REPO`.

## Core-loop placement

Advances core-loop element **② the nightly improvement loop**. If the night writes a checkpoint
and the gate runs, it also exercises element **③ the never-regress promotion gate** — but the
gate's rule is untouched: `UNVERIFIED` still counts as not a win, and promotion still requires a
proven gain on the held-out verified set. The reward (①) is untouched: the same STRICT verifier,
the same sandbox, the same operator-held tests.

## Roadmap grounding

- `docs/ROADMAP.md` § 13 (the pivot fired; stratify exhausted, raise *k* declared) and § 14 M1
  (a night selecting ≥ 1 strict-`PASS` unblocks `check-leakage`, `card` and every later
  milestone). The representation axis is spent in all three forms:
  `docs/planning/whole-function-edit-finding/measurement-run/finding.md` § 6.
- `PREREGISTRATION.md` § 10.19 (Type 1, 2026-10-17): `sampling.K = 16`; every prior figure under
  `K = 8` is non-comparable and the old series is not extended.
- `docs/planning/raise-k/prd.md`: this unit's code; the night is operator-run and not built here.
- `docs/STATUS.md`, night #1 entry: 496 rollouts, control `INTACT` 496/496, 6 strict-`PASS`
  selected, then `KeyError: 'dropout'` before training; the three defects are fixed in 0.14.1,
  including the ledger written last.
- `docs/planning/p2-rollouts/night-door/runbook.md`: the post-§ 10.16 sheet — 52-task
  denominator, held-out digest read-back, `check-probe`, post-night `check-leakage`.

## Related issues (context only)

- **#64** (open) — 83% of night-006's rollouts died on patch application; the three proposed
  representation directions are measured NO-GO, so the raised budget is the remaining response
  to the same signal, not a fourth contract.
- **#62** (open) — the held-out split is keyed on the task id; out of scope here.
