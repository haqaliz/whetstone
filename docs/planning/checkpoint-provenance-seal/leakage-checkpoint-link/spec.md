# Spec — leakage-checkpoint-link

**Unit:** `checkpoint-provenance-seal` · **Aspect 3 of 3** · **Sequencing:** after `checkpoint-seal`;
independent of `gate-sealed-record`.
**PRD:** `docs/planning/checkpoint-provenance-seal/prd.md` § 5 items 9, 10.

## Problem slice and outcome

`check-leakage` reads a run and a held-out document and never a checkpoint, so the link from a
candidate to the night that trained it is a hex comparison done by eye in the runbook. After this
aspect the command can take the checkpoint, verify it, compare the link mechanically, and say whether
that link was sealed.

## In scope

- `check-leakage --checkpoint <dir>` (optional) in `cli.py` and `loop/check_leakage.py`.
  - the checkpoint is verified with `sft.verify_checkpoint`; the import stays function-local so
    `cli.py` keeps its no-module-scope-import rule;
  - match and sealed: an added output line says the dataset link is sealed and matches the run;
  - match and v1: an added line says "recorded, not sealed"; the command proceeds;
  - mismatch against the run's `dataset.json` digest: exit 2, naming both digests' leading 12 hex;
  - untrained checkpoint: exit 2, saying it has no dataset;
  - `CheckpointUnverified`: exit 2, added to `REFUSALS`.
- The verdict (clean or leaked) and its exit 0/1 are computed exactly as today; the checkpoint
  outcome can only add a refusal or a line.
- The gate runbook step and its guard: the manual hex comparison is replaced by `--checkpoint`, the
  sheet says sealed vs not sealed, and `tests/test_gate_runbook_guards.py:523-541` is tightened so a
  sheet still reading "recorded, not verified" fails.
- Docs: STATUS entry, CHANGELOG `Unreleased` (with the breaking items from aspects 1 and 2), the
  ROADMAP M2 note, and `CLAUDE.md`'s status line. The finding is not edited — it is a dated record.

## Out of scope

- Any change to the leakage verdict, the identity-by-sha12 rule, or its residual.
- Making `--checkpoint` mandatory. The runbook requires it; the command does not.
- Running a gate or producing a candidate.

## Acceptance criteria (written first)

1. Without `--checkpoint`, stdout and the exit code for every existing fixture are byte-identical to
   before; `tests/test_gate_leakage_finding.py` passes unedited. (Corrected 2026-10-06: this said
   "or skips loudly in a worktree". It does not skip: it resolves the primary checkout through git's
   common dir, so it runs in a worktree and passed against the real night-001.)
2. A v2 checkpoint trained from the run: exit as the verdict dictates, with the "sealed, matches the
   run" line.
3. A v1 checkpoint trained from the run: same verdict, with the "recorded, not sealed" line, and
   never the word "verified" for the link.
4. A checkpoint recording a different dataset digest: exit 2, never 0, even when the run itself is
   clean. **Adversarial:** a leaked run plus a checkpoint from another night must not exit 0.
5. A tampered v2 checkpoint (any claim edited, digest untouched): exit 2.
6. An untrained checkpoint: exit 2.
7. A missing `--checkpoint` directory or one without `provenance.json`: exit 2 with a message, not a
   traceback.
8. A source-reading test asserts `cli.py` has no module-scope import into `loop` after the change.
9. The runbook guard fails against the pre-change sheet and passes against the new one.

## Dependencies and sequencing

Needs aspect 1's `sealed` and `dataset_digest` on `Checkpoint`.

## Open questions and risks

- The mismatch exit is a refusal (2) rather than a violation (1): the command cannot say anything
  about a checkpoint that was not trained on this run. If the operator would rather see it as a
  failure, that is a one-line change decided in the plan.
- The real `checkpoints/portability-arm` is v1 and its dataset link matches `night-001`; a run of the
  new flag against it would print "recorded, not sealed". That is the only real-world exercise
  available until a v2 checkpoint exists, and it is the operator's, not a test's.
