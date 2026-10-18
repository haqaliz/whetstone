# PRD — k16-night

**Unit:** `feat/k16-night/aliz` · **Written:** 2026-10-18 · **Type:** feature, off the reward
path. **Source:** the inline brief in `docs/planning/_card/issue.md`, derived from the accepted
`whetstone-next` handoff. **Understanding:** `docs/planning/k16-night/understanding.md`.

## Problem Statement

The nightly loop's draw budget is now `K = 16` (`PREREGISTRATION.md` § 10.19, Type 1,
2026-10-17), but **no night has run under it**. `raise-k` deliberately left the night to the
operator (`docs/planning/raise-k/prd.md:29`), and M1's exit criterion — a night that selects at
least one strict-`PASS` and writes both a ledger and a checkpoint — stands open
(`docs/ROADMAP.md` § 14, M1). Five nights across three base sizes have produced zero; the three
alternative edit representations are measured NO-GO; the last pre-committed response is the raised
budget.

The night is expensive and its evidence is still fragile. `run_night` writes the ledger **after**
the training and checkpoint steps (`src/whetstone/loop/night.py:388-449`). `_train` guards the
capacity probe and the trainer broadly (`night.py:667-699`), which is the night-#1 fix — but
`sft.write_checkpoint` (`night.py:701-712`) and `sft.verify_checkpoint` (`night.py:716`) sit
outside that guard, so a checkpoint-writer or verifier failure after a complete night still
escapes before the ledger write. Night #1 lost 26.6 hours to exactly this class of loss, one stage
earlier. A K = 16 night risks ~832 rollouts; the same failure must not be able to erase them.

Two of the night's acceptance criteria are also prose-only today. `check-probe` checks that the
ledger's declared `draws` equals its recorded draws, but never that it equals `sampling.K`
(`src/whetstone/loop/check_probe.py:223-229`); and the held-out digest equality is an operator's
eye on the sheet (`docs/planning/p2-rollouts/night-door/runbook.md:57-62`), not a command exit.

## What this unit is — and is not

**This unit hardens the night's evidence path and pins its acceptance, then the operator runs the
night from the primary checkout.** The code PR does **not** run the GPU night; the sheet requires
the primary checkout (`runbook.md:4-11`), and the worktree has no `.venv`, `weights/`,
`tasks/local/`, `runs/`, or `checkpoints/`. The night and its finding are a **follow-up commit**
after the code merges, on the same branch, or a follow-up unit. The review gate approves this
split.

It does **not** add a lever. The held-out split does not move, the gate rule and its three exits
do not move, the reward path does not move, and no fourth edit representation or base change is
proposed. A zero is a valid, publishable finding; it is not a reason to loosen anything.

## Goals & Success Metrics

Success is a merged, green tree with four properties — **not a yield**:

- **A checkpoint-writer failure cannot erase a night's ledger.** A `write_checkpoint` or
  `verify_checkpoint` exception is recorded as `checkpoint_absent` with its type and message; the
  ledger is still written with every draw recorded. Test-first, watched failing against the
  current code.
- **The probe decision pins the declared budget.** `check-probe` fails with a named violation when
  the probe ledger's `draws` is not `sampling.K` (by identity, never a hardcoded `16`).
- **The probe decision pins the split.** `check-probe --heldout <doc>` fails when the probe
  ledger's held-out digest is not the committed document's digest, and when the ledger records no
  held-out split. The sheet passes the flag; its guard holds it.
- **The finding is checked against its evidence.** A skip-loudly guard reads the finding's
  declared run and asserts the ledger's `draws == sampling.K`, the held-out digest equality, and
  that every count the finding quotes equals the ledger's. A finding that invents a number fails.

**No number is claimed.** The night has not run; whether `K = 16` yields a strict-`PASS` is the
operator's measurement, and *"accept the finding"* remains a legitimate outcome.

## Personas & Scenarios

- **The founder/operator.** Wants to run the declared K = 16 night without risking the evidence,
  and wants the pre-night check to refuse a probe that ran a different budget or a different
  split. Scenario: merge the guards, run the probe from primary, `check-probe` exits 0, run the
  night, then commit the finding.
- **A later reader of the finding.** Needs to see the declared denominator, the held-out digest,
  the per-draw counts, the control arm, and — if zero — the honest confound that the only
  repeatedly-solved task is held out.

## Requirements

### Must-have

**M1 — the ledger survives a checkpoint-writer failure.**
`night._train` wraps `sft.write_checkpoint` and `sft.verify_checkpoint` in the same broad guard
that already covers the capacity probe and the trainer. On an exception it returns
`(None, reason, capacity)`, where `reason` names the exception's type and message, says the
checkpoint may be partial, and says the night selected its examples but produced no candidate.
`run_night` then writes the ledger as it does today, with `checkpoint.digest = None` and
`checkpoint.absent = reason`. The partial directory is not deleted — the operator is told to use
a fresh run id, following the runbook's killed-run rule.

**M2 — `check-probe` pins the declared draw budget.**
`run_check` compares `payload["draws"]` to `whetstone.loop.sampling.K` imported by identity. A
mismatch is a **named violation** (`proceed=False`), with a message naming the expected and the
recorded budget. The value is never a literal `16` in the check. A probe at `K` proceeds exactly
as today; a probe at any other budget now fails (the existing `draws=2` fixture is updated to
`K`).

**M3 — `check-probe --heldout <doc>` pins the split.**
A new optional flag on the `check-probe` parser. When passed, the check reads the probe ledger's
`task_set.heldout.document_digest` and compares it to `heldout.document_digest_of` the committed
document (the same loader and digest function the night uses, imported by identity). A mismatch,
or a probe ledger with no held-out record, is a named violation. The sheet's `check-probe` block
gains `--heldout $REPO/tasks/heldout/source-b.json`, and
`tests/test_night_runbook_guards.py` pins the flag. The rule is **tightened, never loosened**:
the probe still proceeds iff every draw's control arm is `PASS` and the seed map is non-empty,
and now also iff the declared budget and split match.

**M4 — the finding guard.**
`tests/test_k16_night_finding.py`, modelled on `tests/test_gate_leakage_finding.py`: resolve the
primary checkout through git's common dir; skip loudly, naming the artefact, when the primary
holds no `runs/` or the finding is absent. When present, read the finding's declared
`**Run:** runs/nights/<id>` path and assert:
- the ledger reads through `ledger.read` (sealed, v3) and `draws == sampling.K`;
- `task_set.heldout.document_digest == heldout.document_digest_of(tasks/heldout/source-b.json)`;
- every count the finding quotes (selected examples, denominator, unverified, coverage,
  checkpoint digest or its absence) equals the ledger's;
- a checkpoint the finding names verifies through `sft.verify_checkpoint`.
A finding that quotes a number the ledger does not carry fails.

**M5 — the write-up lands with the code.**
`docs/planning/k16-night/prd.md` and `understanding.md` (this unit); a `docs/STATUS.md` entry at
the top and a `CHANGELOG.md` `Unreleased` entry in the same commit as the guards. Both state that
the **guards** shipped, the **night is unrun**, and **no number is claimed**. The night sheet's
`check-probe` line and its guard are updated in the same commit (code first).

**M6 — nothing on the reward path moves.**
`src/whetstone/verify/`, `tasks/`, `tasks/heldout/source-b.json`, and the gate's rule and exits
are byte-unchanged; the existing reward-path and held-out guards stay green. `src/whetstone/loop/`
and `src/whetstone/loop/check_probe.py` are the only source files that move.

### Should-have

**S1 — the operator run follows the merge.** The night runs from the primary checkout on
`master`, through the sheet's existing probe and night blocks, with operator-declared
`--probe-run-id`, `--night-run-id`, `--run-seed`, and `--recorded-on`. The waiting state is
stated in the STATUS entry so a reader knows the unit is not "done" until the finding lands.

**S2 — the finding's required content.** `docs/planning/k16-night/finding.md` carries: the
declared denominator (52 tasks: 51 private + 1 public), `K = 16`, the held-out document digest and
its equality to the committed document, per-draw counts, the control arm's status, the selected
example count and task ids (no file contents), the checkpoint digest or the stated absence reason,
and — either — `check-leakage` exit 0 plus the gate's exit, or a zero accepted with its confound.
If the clustered task is excluded, the finding says so by id and does not claim K = 16 was the
only variable.

**S3 — the 12 `NO_ORACLE` tasks are reported, not hidden.** The finding names the unverified
share and states that those tasks were drawn and cannot yield an example under the sealed budget.
No scorable-pool filter is added in this unit.

### Nice-to-have

**N1 — a per-task yield table from the ledger** (task ids, attempts, solved counts; never file
contents), so a reader can see where the yield came from and that `donor-a-c6e4d4c4de87` is
absent by exclusion.

## Acceptance Criteria (testable, written first)

1. **Durability.** A new test in `tests/loop/test_night.py` monkeypatches `sft.write_checkpoint`
   to raise; the night still writes a readable v3 ledger whose `checkpoint.digest` is `None`, whose
   `checkpoint.absent` names the exception and the partial-checkpoint warning, and whose
   `draws_recorded` is complete. A second test does the same for `sft.verify_checkpoint`. Both are
   watched failing against the current code.
2. **Budget pin.** `tests/loop/test_check_probe.py`: a probe at `draws == sampling.K` proceeds; a
   probe at `K - 1` fails with a violation naming both values; the expected value is imported from
   `sampling.K`. Watched failing against the current code (which proceeds at any consistent
   `draws`).
3. **Split pin.** `tests/loop/test_check_probe.py`: `--heldout` with a matching digest proceeds;
   a mismatched digest and a ledger with no held-out record each fail with a named violation.
   `tests/test_night_runbook_guards.py` pins the `--heldout` flag on the `check-probe` block.
   Watched failing against the current code (no such flag).
4. **Finding guard.** `tests/test_k16_night_finding.py` passes on a fixture finding whose numbers
   match a fixture ledger, fails on a finding that quotes a wrong count or digest, and skips
   loudly, naming the artefact, when the primary's `runs/` or the real finding is absent.
5. **No movement.** The existing `tests/test_no_inference_on_reward_path.py`, the adversarial
   corpus, the held-out loader and gate suites stay green; a byte-identity check confirms
   `src/whetstone/verify/`, `tasks/`, and `tasks/heldout/source-b.json` are unchanged.
6. **Green tree.** `uv run pytest`, `uv run ruff check .`, and `uv run mypy src/` exit 0.
7. **Operator acceptance (follow-up, not this PR).** `check-probe` exits 0 on the real probe; the
   night's ledger records `draws = 16` and the committed held-out digest; then either a
   checkpoint with `check-leakage` exit 0 and a gate exit, or a committed finding that accepts the
   zero. This criterion is deferred until the operator run and is not claimed by the code PR.

## Out of scope / guardrails

- **No held-out split move.** § 10.16's document and its digest are fixed. The clustered task's
  exclusion is the honest state, not a bug to route around.
- **No gate change.** The rule, the three exits, `R = 3`, and the untrained-incumbent dispatch are
  untouched.
- **No reward change.** STRICT/WEAK, the sandbox, the operator-held tests, and the corpus are
  untouched. `UNVERIFIED` is still not a win.
- **No new lever.** No fourth edit representation, no base change, no scorable-pool filter, no
  rerun of the § 3 baseline. Each would need its own amendment.
- **No egress.** The night runs locally; the private corpus never leaves the box.
- **No number.** The code PR claims only that the guards work.

## Risks and flagged gaps

🔴 **The night cannot run in this worktree.** The sheet requires the primary checkout and the
worktree lacks the data and venv. The code PR must merge first; the finding is a follow-up. If the
review gate wants one shippable unit, the alternative is to hold the branch open through the run
— slower and harder to review.

🔴 **The clustered task is held out, so K = 16's mechanism is weakened.** Night #1's 4-of-8 task
is `donor-a-c6e4d4c4de87`, a held-out member. The night excludes it. A zero would be confounded
with the exclusion, and the finding must say so; it must not claim the budget was the only
variable. The split does not move.

🟡 **The `check-probe` tightening changes a pre-committed gate.** It tightens (a probe at a
different budget or split no longer proceeds), never loosens. The rule sentence in the sheet is
updated in the same commit, and the existing `draws=2` fixture becomes `draws=K`.

🟡 **The `--heldout` pin is only live if the sheet passes it.** The runbook guard pins the flag;
a future sheet edit that drops it fails the suite.

🟡 **The finding guard depends on the finding's declared run path.** The parser is deliberately
small: one `**Run:**` line. The follow-up commit must fill it; until then the test skips loudly.

🟡 **Residual evidence paths remain unguarded.** `training.write_local` / `write_document`
(before training) and `run_ledger.write` itself are still outside a guard; a disk failure there
can still leave no ledger. This unit closes the checkpoint-writer path, which is the one that can
fail *after* a complete night's training. State it in the STATUS entry rather than implying the
ledger is now unconditional.

🟡 **The 12 `NO_ORACLE` tasks are still drawn.** ~192 of ~832 draws cannot yield an example.
The runbook already expects a material unverified rate; the finding reports it. A scorable-pool
filter is a separate unit.

## Aspects

1. `durability/` — M1, the checkpoint-writer guard and its tests.
2. `probe-pins/` — M2, M3, the `check-probe` budget and held-out pins, the sheet edit and its
   guard.
3. `finding-guard/` — M4, M5, the skip-loudly finding guard and the write-up.
4. `night-run/` — S1–S3, operator-executed after merge; the finding commit. No production code.

## Open questions (for the review gate)

1. **The `check-probe --heldout` mechanism.** The PRD recommends the flag (a command exit before
   the night, in the `check-probe` precedent) over a test-only post-run guard. The flag changes
   the sheet's check-probe line and its guard; the post-run guard alone would not stop a probe
   that ran the wrong split.
2. **The finding commit's home.** The PRD assumes the same branch stays open through the run and
   the finding is a second commit before the single PR merges. A separate
   `chore/k16-night-finding` unit is the alternative; the user chose "harden, then run" without
   fixing this.
3. **The run id and seed.** Operator-declared; the PRD deliberately does not invent them. The
   finding must name both.
