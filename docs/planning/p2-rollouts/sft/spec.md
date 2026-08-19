# Spec — sft (aspect 2 of p2-rollouts)

**PRD:** `../prd.md`. **Branch:** `feat/p2-rollouts/aliz`. This aspect turns the strict-PASS
dataset (aspect `sampling`) into a trained LoRA adapter under `checkpoints/<id>/` — the "candidate"
the P2 exit criterion requires (`docs/ROADMAP.md:399-400`) — gated by a D7-style capacity probe.
The `run --night` door that composes it is aspect `night-door`.

## Problem slice and user outcome

Training a 32B-class model on this machine is **unmeasured**: the D7 probe settled inference fit
(~8 GiB resident for the 18.4 GB snapshot, `finding.md:25-31`) and nothing else. This aspect
measures the SFT bound before committing a night, then runs `mlx_lm.lora.train` on the verified
dataset and emits a hashed, provenance-carrying checkpoint that P3's gate can later re-verify. The
user outcome is the first candidate the loop has ever produced, provably trained on strict-PASS
rollouts only.

## In-scope requirements

1. **D7-style capacity probe, declared before the run** (never after seeing its output): a small,
   named N of training steps and a stated headroom against the 36 GiB machine, run through the real
   `mlx_lm.lora.train` on a slice of the dataset; the peak recorded in the probe's own record (the
   `--probe` discipline of `run.py:598-610`). A probe that exceeds headroom is a published capacity
   finding, never worked around (`report.py:1184-1186`).
2. **Dataset format:** the aspect-1 dataset rendered into mlx-lm's local format — a directory of
   `train.jsonl` / `valid.jsonl` / `test.jsonl`, one JSON object per line, `text` or `messages`
   (`mlx_lm.tuner.datasets.load_local_dataset`). Every line derives from a strict-PASS record; the
   `valid` split is drawn deterministically from the strict-PASS set (seeded by the run seed), never
   from `UNVERIFIED`. A test asserts a line cannot be traced back to a non-PASS record. **Degenerate
   case, pre-committed:** a valid split below the floor fraction of the strict-PASS set (the floor is
   a named constant in `loop` code) is *no valid split* — training proceeds without validation and
   the checkpoint's provenance states "no valid split (strict-PASS set below floor)" verbatim. A
   silently-validated checkpoint is refused by a test.
3. **Training invocation:** `mlx_lm.lora.train(model, optimizer, train_dataset, args=TrainingArgs(...))`
   (pinned `mlx-lm==0.31.3`), with `TrainingArgs` fields (batch size, iters, `max_seq_length`,
   `grad_checkpoint`, `grad_accumulation_steps`, adapter file name) fixed at construction and
   recorded in provenance — the `mlx_runtime.py:134-142` anti-tuning discipline applied to training
   hyper-parameters: nothing per-night may be varied to chase a better-looking checkpoint.
4. **Checkpoint emission and identity:** `checkpoints/<id>/` holds the adapter weights
   (`adapters.safetensors`), its config, and `provenance.json` — base revision, dataset digest,
   run seed, training args, tool versions — and is **hashed weights-style**: a
   `weights.py:184-230`-style `verify()` that re-hashes every file so P3's gate can re-verify the
   bytes it compares. The run ledger records the checkpoint digest.
5. **Nothing untrained is emitted as a candidate.** A night that produced zero strict-PASS rollouts
   writes no checkpoint and states so in the ledger (`UNVERIFIED` is not a win, and neither is an
   empty candidate).
6. **Local-only by construction:** the dataset and checkpoint live under gitignored roots
   (`.gitignore:20-24`); no download, no egress; the base weights are the already-pinned local
   snapshot (re-hashed before use, `weights.py:184-230`).

## Out-of-scope boundaries

- No evaluation of the trained checkpoint (that is P3's gate), no promotion decision, no held-out
  split (§ 7.1), no report home.
- No change to `src/whetstone/verify/`, `patch.py`, `attribution.py`, `src/whetstone/tasks/`.
- The CLI door and run composition are aspect `night-door`.

## Acceptance criteria (testable)

- AC1: the probe is declared (N, headroom) and its record asserts those declared values; a test
  refuses a probe record that lacks them.
- AC2: the dataset writer emits mlx-lm's local format; a test loads it back through
  `mlx_lm.tuner.datasets.load_local_dataset` (or its pure parser) and asserts every line maps to a
  strict-PASS record with the same prompt/completion hashes.
- AC3: the valid split is deterministic under the run seed and contains no `UNVERIFIED`-derived
  line; below the floor fraction it is *no valid split*, and the checkpoint's provenance states
  that verbatim.
- AC3b: the emitted adapter round-trips through `mlx_lm`'s adapter load against the pinned base
  revision (a load+generate test with a tiny fixture model, or against the real base on the
  machine when present) — a stranded adapter (revision drift, format change) is refused as a
  candidate, not merely hashed.
- AC4: `checkpoints/<id>/provenance.json` exists and records base revision, dataset digest, run
  seed, training args, tool versions; the checkpoint `verify()` re-hash passes; the ledger records
  the checkpoint digest.
- AC5: a zero-strict-PASS night writes no checkpoint and the ledger states the empty outcome.
- AC6: `uv run pytest` green; ruff and mypy over `src/` green.

## Dependencies and sequencing

- Depends on aspect `sampling` (dataset + ledger) and on the pinned local weights (already in the
  primary's `weights/`, machine-level — never copied into the worktree; the SFT run points at the
  primary's weights by absolute path per the worktrees skill).
- Sequence: probe → dataset writer → train invocation → checkpoint emission → hashing/provenance.
- Feeds aspect `night-door` (the composed night command and its runbook guard).

## Open questions / risks

- The honest risk is memory: a failed probe is a published finding, and the fallback (smaller batch,
  `grad_checkpoint=True`) must be **pre-committed** in the spec before the probe runs — decide here,
  not after the probe output exists. (Recommended pre-commit: try `grad_checkpoint=True` +
  `grad_accumulation_steps` before shrinking the model — never a smaller/loser base.)
- Whether the adapter is exported for a *different* sampler than the one it was trained under — the
  adapter is weights; sampling is decided at generation time (P3's problem). Out of scope here.