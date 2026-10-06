# Understanding — checkpoint-provenance-seal

**Core-loop element:** ③ the never-regress promotion gate, at the trust its inputs carry. ① the
reward does not change; nothing under `verify/` or `tasks/` is touched. `UNVERIFIED` still counts
as not a win, and the gate's rule and exits are untouched. Nothing leaves the machine.

## What the work is really asking

`sft.verify_checkpoint` (`src/whetstone/loop/sft.py:801`) re-hashes the files a checkpoint's
`provenance.json` names and checks that `digest` reduces from those file hashes (`_digest_of`,
`:926`). Everything else in the document is outside the seal: `base`, `dataset_digest`,
`run_seed`, `backend`, `training_args`, `tool_versions`, `validation`, `capacity_probe`. The unit
brings the claims consumers rely on inside the digest, under a new checkpoint schema, and keeps
v1 verifiable but never "sealed".

## Facts the dig established

- **One writer for trained checkpoints.** MLX and Torch both go through `sft.write_checkpoint`
  (`night.py:628`, `arm.py:158`); `torch_runtime.py` writes no provenance. Criterion 5 (same v2
  shape) is therefore automatic, and the test is a pin rather than work.
- **A second, separate writer:** `write_baseline_checkpoint` (`sft.py:759`) writes the untrained
  checkpoint. It has no caller in `src/` and records `base` only. Whether v2 covers it is open.
- **`Checkpoint` carries no dataset link** (`sft.py:337-360`: directory, digest, files, untrained,
  backend). `gate.py` re-opens `provenance.json` a second time (`_checkpoint_base` `:1617`,
  `_checkpoint_dataset_digest` `:1629`). A seal verified in one read and consumed from a second
  read is a time-of-check/time-of-use gap; the consumers should take their values from the
  verified object.
- **The promotion record's `training` block is write-only.** `candidate_training` and
  `incumbent_training` are populated on read and consumed by nothing in `src/`; `morning.py` and
  `honest_report.py` do not print them.
- **Strict readers.** `_PROMOTION_TRAINING_FIELDS` (`gate.py:1329`) is checked as both a subset
  and a required set, so a new key under `/2` would make every existing `/2` record unreadable
  while still claiming `/2`. That argues for a bump to `/3` over a silent field.
- **A v2 checkpoint fails closed on an old reader**, since `verify_checkpoint` requires schema
  equality (`:819`).

## Contradictions with the brief

1. **Criterion 3 names a consumer that has no checkpoint.** `check-leakage` reads `--run` and
   `--heldout` only (`cli.py:583-610`, `check_leakage.py:228`). It never opens a checkpoint, and
   the link from a checkpoint's recorded digest to a night's `dataset.json` exists only as a
   manual step in the gate runbook. "`check-leakage` reports a v2 dataset link as verified" has
   nowhere to be true unless the command gains an optional `--checkpoint`. That is a CLI change
   and a new refusal path, and it is a scope decision, not a detail.
2. **"Verified" overclaims what a seal is.** The digest is an unkeyed hash. Anyone able to edit
   `provenance.json` can also recompute the digest, and `verify_checkpoint` has this property for
   the file hashes today. A v2 seal detects an edit that leaves the digest alone, and an edit
   that disagrees with a digest cited elsewhere (reports, promotion records, the runbook). It does
   not authenticate the writer, and it does not prove `dataset_digest` equals the digest of the
   dataset the trainer actually read. The honest state is **sealed**, not **verified**. The flag
   and every sentence that carries it should say `sealed`, and the docs must state this limit.
   The brief's criteria 2 and 3 should be read with "verified" replaced by "sealed".

## Consequences for the tests

- `tests/loop/test_baseline_checkpoint.py:179-193` (`TRAINED_KEYS`) pins `write_checkpoint`'s keys
  byte-for-byte; it will change deliberately.
- `tests/loop/test_gate_cli.py:258` (`_record_backend`) edits `provenance.json` after sealing and
  assumes the seal covers files only; under v2 it must re-seal or the test must say why not.
- `test_baseline_checkpoint.py:147` uses `whetstone-checkpoint/2` as its "wrong schema" value;
  that value becomes legitimate.
- `tests/test_gate_runbook_guards.py:523-541` pins the phrase "recorded, not verified" in the
  runbook; it would still pass if the runbook went stale, so the guard needs tightening.
- `tests/test_gate_leakage_finding.py` reads only the `dataset_digest` key of the real
  `portability-arm` v1 checkpoint and does not call `verify_checkpoint`; it stays valid if v1
  keeps verifying. (Corrected 2026-10-06: it does not skip in a worktree. It resolves the primary
  checkout through git's common dir, so it ran here and passed against the real night-001.)

## What cannot be proven here

`checkpoints/portability-arm` (`48eae99b0d32`) is v1 and stays v1: it is never rewritten in place.
So **no real checkpoint will exist at v2 until a later night or arm writes one**, and this
unit's v2 behavior is proven against fixtures only, as the gate's was. The docs must say so.

## Open questions for the interview

1. Promotion record: bump to `whetstone-promotion/3`, or add `sealed` under `/2`? (Recommendation
   from the dig: bump.)
2. Criterion 3: add `--checkpoint` to `check-leakage`, or limit the unit to the promotion record
   and the runbook step, and leave the command alone?
3. Does v2 also seal the untrained checkpoint's `base`, via `write_baseline_checkpoint`?
4. Exactly which fields does the v2 digest cover? Candidates: `base`, `dataset_digest`, `backend`.
   Others (`run_seed`, `training_args`, `tool_versions`, `validation`, `capacity_probe`) are
   claims too, and a partial seal invites the question of why those were left out.
5. Does the seal also govern `card.py`, which reads `base` and `backend` from the raw JSON and
   discards `verify_checkpoint`'s return (`card.py:227-232`)?
