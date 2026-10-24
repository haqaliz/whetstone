# Publishing the selected model to Hugging Face

**Status: no model has been selected. This is the readiness runbook, not an upload record.** The
14B format pre-flight and a night under § 10.22 must produce a checkpoint, and the leakage check
must exit 0, before any of the commands below run.

## What is published

- The **PEFT adapter** (`adapter_model.safetensors`, `adapter_config.json`) and the model card.
- The **base is not uploaded**: `Qwen/Qwen3-14B` is Qwen's Apache-2.0 release. The card names
  `Qwen/Qwen3-14B` at `40c069824f4251a91eefaf281ebe4c544efd3e18` and the NF4 load, so a reader
  reproduces the artifact against the same bytes.
- The private corpus, the journals, the ledger and the gate record are **never** uploaded. They
  stay in the gitignored `runs/` store.
- The adapter is a **QLoRA** adapter trained on an NF4 base. Loading it needs the base directory
  with its `quantize.json` sidecar (NF4, double quantization, `float16` compute) and
  `bitsandbytes`; the card states the base, the revision and the sidecar. The card must not imply
  the adapter is self-contained.

## The gate, in this order — never reordered

1. **A checkpoint exists.** The night selected at least one strict-`PASS` example and trained.
   A zero night publishes nothing and needs no card: `whetstone card` refuses a night with no
   checkpoint, repeating the night's own reason.
2. **Leakage exits 0.**

   ```bash
   uv run --extra torch whetstone check-leakage \
     --run "$REPO/runs/torch-mps/<run-id>" \
     --heldout "$REPO/tasks/heldout/source-b.json"
   ```

   Exit 0 means source-B training examples were compared and none shared a task identity with the
   held-out membership. Exit 1 names a leak; exit 2 names a refusal. **Either non-zero exit stops
   here.** No card, no upload, no announcement. This is the one check that stands between private
   donor code and a public artifact.
3. **Render the card.**

   ```bash
   uv run --extra torch whetstone card \
     --run "$REPO/runs/torch-mps/<run-id>" \
     --checkpoint "$REPO/checkpoints/torch-mps/<run-id>" \
     --out "$REPO/runs/torch-mps/<run-id>/README.md"
   ```

   Read it before uploading: base and revision, NF4, the dataset digest, the training arguments,
   the tool versions, the capacity record, and the validation sentence. The card is derived from
   the checkpoint's own evidence; a hand-written card is not a substitute.
4. **Review against the finding.** The finding under `docs/planning/torch-mps-series/` states the
   partition and the gate decision. A card advertising more than the finding measured is a halt.
5. **Upload**, with a write token.

## Credentials and the target

- A Hugging Face **write** token, scoped to the target repo, exported as `HF_TOKEN` for the upload
  session (or `hf auth login` interactively). The token is never committed and never written into
  a run directory.
- The **namespace and repo name are the operator's decision**; nothing in this repository
  hardcodes them. A model card naming the wrong namespace is worse than no card.
- The upload is the only step that leaves the machine. The private corpus never does.

## Commands (to run only after steps 1–4)

```bash
export HF_TOKEN=...                     # the operator's write token; never in the repo
hf repo create <namespace>/<model-name> --repo-type model
hf upload <namespace>/<model-name> \
  "$REPO/checkpoints/torch-mps/<run-id>" adapter_model.safetensors adapter_config.json \
  --repo-type model
hf upload <namespace>/<model-name> "$REPO/runs/torch-mps/<run-id>/README.md" README.md \
  --repo-type model
```

## What is not claimed

- A zero night publishes nothing. A leakage refusal publishes nothing. A `CapacityExceeded`
  night publishes no checkpoint. None of those is a failure of the upload; each is the gate
  working.
- A published adapter is **non-comparable** to the 7B, 8B or MLX series (§ 10.20–§ 10.22), and the
  card must not restate one series' figure as another's.
- The fused model is not produced from a 4-bit checkpoint by this runbook. Fusion is a separate
  artifact with its own check; the adapter plus its base is what is published first.
