# Spec — durability (M1)

**Aspect:** `durability` · **Unit:** `k16-night` · **PRD:** `../prd.md` M1 · **Date:** 2026-10-18

## Purpose

A night's rollouts are the expensive, irreplaceable half of the run. The ledger must survive a
failure in the checkpoint step that follows training, exactly as it already survives a failure in
the trainer.

## Current behaviour (the hole)

`run_night` selects examples, writes the dataset, calls `_train`, then writes the ledger
(`src/whetstone/loop/night.py:388-449`). `_train` surrounds the capacity probe and `sft.train`
with a broad `except Exception` (`night.py:667-699`) — the night-#1 fix. `sft.write_checkpoint`
(`night.py:701-712`) and `sft.verify_checkpoint` (`night.py:716`) are **after** that try, so an
exception from either escapes `run_night` before the ledger write at `night.py:449`. The 832
draws are then unreadable by the morning report, `check-leakage` and the gate.

## Required behaviour

1. An exception from `sft.write_checkpoint` or `sft.verify_checkpoint` returns
   `(None, reason, capacity)` from `_train`; it does not escape.
2. `reason` names the exception's type and message, states that the night's draws and dataset are
   complete and recorded, states that no candidate was produced, and tells the operator the
   checkpoint directory may be partial and a retry must use a fresh run id.
3. `run_night` writes its v3 ledger as usual: `checkpoint.digest is None`,
   `checkpoint.absent == reason`, every `draws_recorded` entry present, `draws == sampling.K`.
4. The partial checkpoint directory is **not** deleted (evidence is never destroyed); the reason
   is the operator's instruction not to reuse it.
5. `cli.run_night` still floors a checkpoint-less night at `FAIL_EXIT`; no new exit code.
6. Nothing under `src/whetstone/verify/`, `tasks/`, the held-out document, or the gate moves.

## Out of scope

`training.write_local` / `write_document` (before training) and `run_ledger.write` itself remain
unguarded. A disk failure there can still leave no ledger; this aspect closes the post-training
checkpoint path only, and the STATUS entry says so.

## Acceptance

- A test monkeypatches `sft.write_checkpoint` to raise and asserts the ledger exists, the
  absence reason names the failure and the partial-checkpoint warning, `checkpoint.digest` is
  `None`, and all declared draws are recorded. Watched failing against the current code.
- A second test does the same for `sft.verify_checkpoint`.
- The existing night suite and the reward-path suite stay green.
