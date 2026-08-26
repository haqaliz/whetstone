# Spec — baseline-checkpoint (aspect 1 of baseline-measurement)

**PRD:** `../prd.md`. **Branch:** `feat/baseline-measurement/aliz`. This aspect materializes
the untrained open base as a pinned, re-verifiable checkpoint — the "checkpoint the night
deliberately does not write" (`docs/planning/p3-promotion-gate/gate-runbook/runbook.md:25-28`).

## Problem slice and user outcome

`PREREGISTRATION.md` § 3 requires a **pinned baseline checkpoint** — the untrained open base,
scored on the held-out set — with provenance committed alongside. The existing checkpoint
format is **adapter-shaped**: `whetstone-checkpoint/1` provenance records a LoRA adapter's
files (`sft.py:74-75`), `write_checkpoint` refuses an empty directory (`sft.py:421-426`), and
`verify_checkpoint` refuses an empty `files` list (`sft.py:480-483`). An untrained base has no
adapter, so nothing in the tree can materialize or re-verify it. The user outcome: the
untrained base exists as a checkpoint directory — hashable, verifiable, honest about having
never trained — and a doctored one cannot pass for the real thing.

## In-scope requirements

1. **`write_baseline_checkpoint`** in `src/whetstone/loop/sft.py` (the checkpoint-provenance
   home; `loop/` is EXEMPT): writes a `whetstone-checkpoint/1` `provenance.json` declaring
   `untrained: true`, `base: {repo_id, revision}` (the immutable commit sha), `tool_versions`
   (sorted, the `write_checkpoint` shape), `files: []`, and `digest` = `_digest_of(())` (the
   digest of an empty adapter set — one digest, `sft.py:540-543`, reused by identity).
   **No training-derived fields** (`training_args`, `capacity_probe`, `dataset_digest`,
   `run_seed`, `validation`): they describe a night, and this checkpoint never trained. The
   function refuses a **non-empty** target directory by name (an adapter beside an untrained
   provenance is the contradiction the flag exists to exclude).
2. **`verify_checkpoint` extended by identity** (`sft.py:453-508`): accepts `files: []` **only
   when** the provenance declares `untrained: true`; refuses `untrained: true` with non-empty
   `files` by name (the label and the bytes disagree); every existing refusal is unchanged
   (missing provenance, unreadable JSON, wrong schema, missing/mismatched files, digest
   self-disagreement — which now also covers the empty case: a doctored untrained provenance
   whose `digest` is not `_digest_of(())` is refused). Returns the `Checkpoint`.
3. **`Checkpoint` dataclass gains `untrained: bool = False`** (`sft.py:268-280`): the default
   keeps the gate's and night's behavior byte-identical; `verify_checkpoint` populates it from
   the provenance.
4. **Byte-identity for the trained path**: `write_checkpoint` and its provenance are
   **untouched** — a trained provenance carries no `untrained` key, and the night's
   determinism tests still pass.
5. **AC2 pins hold**: `src/whetstone/verify/`, `tasks/`, `patch.py`, `attribution.py`
   byte-identical to `origin/master` (this aspect touches only `sft.py` + tests).

## Out-of-scope boundaries

- The base-only **engine** seam (an adapter-less checkpoint loaded by `mlx_lm`) — aspect 2.
- The measurement door, the `whetstone-baseline/1` artifact, and the runbook — aspects 2–4.
- Any change to the trained writer, the gate's decision rule, or the reward path.

## Acceptance criteria (test-first; each refusal watched failing first)

1. `write_baseline_checkpoint` writes a directory whose provenance declares `untrained: true`,
   `files: []`, `base: {repo_id, revision}` with the tool versions sorted, and
   `verify_checkpoint` accepts it — returning a `Checkpoint` with `untrained is True` and
   `digest == sha256(b"").hexdigest()`.
2. A trained checkpoint with no files is **still** refused (`CheckpointUnverified`) — the
   extension did not loosen the trained path.
3. `untrained: true` with non-empty `files` is refused by name.
4. The existing refusals hold for the untrained shape: missing provenance, wrong schema,
   unreadable JSON, and a hand-edited `digest` that disagrees with `_digest_of(())`.
5. `write_baseline_checkpoint` refuses a non-empty target directory by name.
6. Trained provenance is byte-identical to today's (no `untrained` key): the night's
   determinism assertions and `write_checkpoint`'s existing tests pass unchanged.
7. The AC2 pins (`verify/`, `tasks/`, `patch.py`, `attribution.py` vs `origin/master`) hold.

## Dependencies and sequencing

Aspect 1 of 4 (PRD sequencing 1 → 2 → 3 → 4). Aspect 2 consumes `write_baseline_checkpoint`
and `Checkpoint.untrained`. Nothing else in the tree consumes this aspect until then.

## Open questions / risks

- **The `untrained` flag's integrity is provenance-level, not byte-level.** The checkpoint
  digest pins adapter bytes; an untrained checkpoint has none, so its `base`/`untrained`
  fields are sealed by the **committed** artifact (aspect 3's `whetstone-baseline/1`), not by
  the checkpoint's own digest. This is the stratum Open-question-5 posture — git history +
  ordering + the committed seal, stated, never reconciled. A hand edit of a trained
  checkpoint's provenance to add `untrained: true` would not trip the file digest (the digest
  excludes the provenance by design, `sft.py:523-528`); the defence is the seal, and the spec
  says so rather than pretending otherwise.
- **The 32B is recorded as a pinned input, never a § 7.3 closure** (PRD Risks): the writer
  takes `repo_id`/`revision` as parameters; the *choice* of base is the operator's, recorded in
  the runbook (aspect 4), not decided here.