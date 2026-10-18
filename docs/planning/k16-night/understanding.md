# Understanding — k16-night

**Unit:** `feat/k16-night/aliz` · **Written:** 2026-10-18 · **Source:** the inline brief in
`docs/planning/_card/issue.md`, derived from the accepted `whetstone-next` handoff.

## What the work is really asking

Run the nightly loop at the draw budget the last unit declared — `sampling.K = 16`
(`src/whetstone/loop/sampling.py:79`, `PREREGISTRATION.md` § 10.19, Type 1, 2026-10-17) — from
the operator sheet at `docs/planning/p2-rollouts/night-door/runbook.md`, and record what
happened. The night is the **last untried pre-committed response** to the fired P2 pivot and the
only identified path to M1's exit criterion (`docs/ROADMAP.md` § 14, M1): a night that selects at
least one strict-`PASS` and writes both a ledger and a checkpoint.

The brief assumed no code change was needed. The dig found one, plus two acceptance criteria that
the sheet only holds as prose. The user's review answers fix the scope:

1. **Harden, then run.** This unit ships the evidence-durability fix and the acceptance pins; the
   night is operator-run from the primary checkout **after** the branch merges. The finding is a
   follow-up commit on the same branch (or a follow-up unit), not part of the code PR.
2. **Run as declared.** The pre-registered held-out split does not move.
3. **Pin both in code.** `check-probe` pins the draw budget; a finding guard pins the held-out
   digest.

## Affected areas

- **The night's evidence order.** `run_night` selects, writes the dataset, trains, writes the
  checkpoint, then writes the ledger (`src/whetstone/loop/night.py:388-449`). `_train` guards the
  capacity probe and the trainer broadly (`night.py:667-699`), so a trainer exception still writes
  the ledger — the night-#1 fix. But `sft.write_checkpoint` (`night.py:701-712`) and
  `sft.verify_checkpoint` (`night.py:716`) sit **outside** that guard, so a checkpoint-writer or
  verifier failure after a complete night still escapes before the ledger write. That is the same
  class of loss as night #1, one stage later.
- **`check-probe`.** It enforces the probe's pre-committed go/no-go — control `PASS` on every
  draw and a non-empty seed map — and it checks `len(draws_recorded) == ledger.draws`, but it
  never compares `ledger.draws` to `sampling.K` and never reads the held-out record
  (`src/whetstone/loop/check_probe.py:119-158`, `:217-251`). A probe at a different budget, or
  against a different split, can print `PROCEED`.
- **The night sheet.** `docs/planning/p2-rollouts/night-door/runbook.md` already declares the
  52-task denominator, passes `--heldout` on both doors, reads the digest back by eye, and runs
  `check-probe` before the night. It is the sheet this unit runs; it is not rewritten.
- **The finding.** The repo's operator-run measurement units commit a finding under
  `docs/planning/<unit>/`, never under `reports/` (`tests/test_gate_runbook_guards.py:679-690`),
  and raw counts live only in the gitignored `runs/` (`docs/planning/whole-function-edit-finding/
  measurement-run/finding.md:6`). The one-home guard admits exactly 21 committed files across 7
  `reports/` homes and refuses a new one (`tests/bakeoff/test_report.py`).

## Contradictions surfaced — flag, do not paper over

**1. The card says "no code change is known to be needed"; the code says otherwise.** The
checkpoint-writer path is unguarded, and `check-probe` does not pin the budget or the split. The
user chose "harden, then run", so the brief's assumption is corrected rather than carried.

**2. The night runs from the primary checkout, but the unit lives in a worktree.** The sheet says
so in its header and its guard refuses a worktree path (`runbook.md:4-11`;
`tests/test_night_runbook_guards.py:411-431`). The worktree cannot run the night: it has no
`.venv`, `weights/`, `tasks/local/`, `runs/`, or `checkpoints/`, and the primary's `.venv` is the
one with `mlx-lm` (and its metadata is stale at 0.24.0, so the sheet's `uv run` sync is
load-bearing). **Consequence:** the code PR merges first; the operator runs from primary
`master`; the finding is committed afterwards.

**3. The `raise-k` rationale's clustering evidence rests on a task that is now held out.** Night
#1 selected 6 strict-`PASS` examples. Four came from `donor-a-c6e4d4c4de87` (4 of its 8 draws),
one from `donor-a-34daf85182d5`, one from `donor-b-c3e132b7469b` (night-001's `dataset.json`,
`runs/nights/night-001`). Under the current § 10.16 split, **`donor-a-c6e4d4c4de87` is a held-out
member** (`tasks/heldout/source-b.json`, `membership`), so the sheet excludes it from training.
The mechanism `raise-k` claimed — "raising K multiplies the yield of exactly the tasks the base
can already reach" (`docs/planning/raise-k/prd.md`) — is therefore unavailable for the one task
that demonstrated clustering. The other two tasks solved once each; at K = 16 they may yield, but
zero remains possible. **The night still runs as declared**, because moving the held-out split
now would re-roll a pre-registered input after seeing this; the finding must state the confound
and must not claim a zero proves K = 16 is insufficient.

**4. The 12 `NO_ORACLE` tasks stay in the training pool.** The held-out document's `excluded`
field names 12 tasks whose oracle cannot be built under the 80 000-character budget; they are not
held out, so the sheet's 51 private tasks include them (12 of 51). At K = 16 that is ~192 draws
that cannot produce a training example regardless of what the model writes. The runbook already
says to report the unverified rate beside the training-set size; this unit does not add a
scorable-pool filter (the user declined that as a separate unit).

**5. The finding cannot land in the same commit as the code that enables the night.** The repo's
rule is that a capability is written up in the same commit that lands it (`CLAUDE.md:81-85`), but
the finding describes an operator run that happens after merge. The code PR writes up the
**guards** and states plainly that the night is unrun and no number is claimed; the finding commit
follows the run and writes up the night. Both are honest about the state of the tree they ship in.

## Core-loop placement

Element **② the nightly improvement loop**. If the night writes a checkpoint and the gate runs, it
also exercises element **③ the never-regress promotion gate**, but this unit does not change the
gate's rule, its three exits, or `R = 3`. The reward path (①) is untouched: the same STRICT
verifier, sandbox, operator-held tests, and held-out document.

## Decisions from the review

| Question | Decision |
|---|---|
| Scope/sequencing | Harden first (durability + pins), merge, then the operator runs from primary; finding is a follow-up commit. |
| Held-out split | Do not move it. Run K = 16 as declared; report the held-out exclusion of the clustered task in the finding. |
| Acceptance pins | `check-probe` pins `draws == sampling.K`; a skip-loudly finding guard pins the run's held-out digest against the committed document. |
| Scorable-pool filter | Out of scope; a separate unit if wanted. |
| Night sheet | Reuse `docs/planning/p2-rollouts/night-door/runbook.md`; do not write a second sheet. |

## Open questions for the PRD / review gate

1. **The held-out pin's mechanism.** `check-probe` currently accepts only `--run`. Adding
   `--heldout <doc>` makes the probe decision compare the ledger's held-out digest to the
   committed document; the sheet's check-probe line would pass the same document it already
   passes to both doors. The alternative is a test-only guard that reads the night's ledger after
   the run. The PRD recommends the `--heldout` flag, because it makes the pin a command exit
   before the night, in the `check-probe` precedent.
2. **The finding guard's run id.** The run id is operator-declared (`runbook.md:86-90`). The guard
   can read the run path the finding declares in a `**Run:**` line, or a module constant the
   finding commit fills in. It must skip loudly when the primary's `runs/` or the finding is
   absent.
3. **How much of the night's per-draw partition the finding must carry.** The ledger records
   per-attempt `(denominator, unverified, solved)` and harness status, not the failure cause of
   each rollout (`src/whetstone/loop/ledger.py:194-210`). The finding can report counts from the
   ledger without joining transcripts; a cause breakdown needs the journals and is a separate
   instrument (`bakeoff.attribution`).
4. **Whether the finding is committed on this branch or a new unit.** The user chose
   "harden, then run"; the PRD assumes the same branch stays open for the finding commit after
   the run, then merges once. A separate `chore/k16-night-finding` unit is the alternative.
