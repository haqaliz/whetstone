# Runbook — the Pascal 4-bit night (`x202`, `torch 2.14.1+cu126`)

**Unit:** `pascal-4bit` · **Aspect:** `night-door` · **Branch:** `feat/pascal-4bit/aliz` ·
**Run from:** `$REPO` on `x202`. Every path below is anchored to `$REPO`, so export it first — an
exported variable expands before the command runs, which is what makes the path the subprocess
receives absolute.

This sheet moves the main series to the founder's own host **`x202`**: 3× NVIDIA GTX 1080 8 GB,
**Pascal `sm_61`**. The quantized base is spread over **every visible GPU by an explicit layer
range** (36 layers → 12 per card), with `embed_tokens` on card 0 and `norm`/`lm_head` on the last
card. `"auto"` and `"balanced"` were both measured packing the model onto two cards while the
third sat idle, and the fuller card OOM'd at prefill (§ 10.30). The installed wheel is
**`torch 2.14.1+cu126`**
— the same version the series pinned, with the CUDA build changed to the Pascal-capable one,
because the pinned `cu130` build has no `sm_61` kernels. The base and revision are **unchanged**:
`Qwen/Qwen3-8B` at `b968826d9c46dd6066d109eabc6255188de91218`.

The precision is **4-bit NF4 with bf16 compute**, declared by the `quantize.json` sidecar beside
the weights. `--precision bfloat16` is the **compute dtype**; the weights are 4-bit NF4. The
sidecar is a recorded input: `whetstone.bakeoff.weights.load_weights` accepts it as an extra file
beside the 15 recorded ones, and `TorchGenerator.provenance()` records
`"quantization": "nf4/bf16/double"`. A run whose provenance says only `bfloat16` is not this run.

The measured pre-flight on x202: **6.75 new tokens/s**, 64 tokens in 9.5 s, **6.07 GB VRAM** of
7.92 GiB, through the harness's own `TorchGenerator` with the quantized loader
(an explicit layer range, `.to()` skipped), under `TORCHDYNAMO_DISABLE=1` and
`TORCH_COMPILE_DISABLE=1`. This is a pre-flight measurement, not the probe below: **no count has
been measured** under § 10.28 or § 10.29, and the § 3 baseline remains unspent.

## The chunked-SDPA shim

Torch on Pascal (`sm_61`) has only the **math SDPA** kernel; memory-efficient and flash report
`Invalid backend`. A 10,001-token prefill tried to allocate **7.38 GiB** on a 7.92 GiB card and
OOM'd. The committed shim
`docs/planning/pascal-4bit/night-door/sitecustomize.py` chunks the query axis at `_CHUNK = 256`,
gated by `WHETSTONE_PASCAL_SDPA=1`, and changes **no arithmetic**: a causal 700-token comparison
gave **max diff 0.0**, and a synthetic 10k GQA prefill peaked at **3.63 GB**. With
the layer range and the shim, the real `TorchGenerator` completed a **10,001-token prompt,
16 new tokens in 95.7 s**.

The MPS series is **not retired** and not extended. Every figure here is **non-comparable** to
the MPS series and to any bf16 CUDA figure: different device, different CUDA build, 4-bit weights,
and a different sample.

## The environment

```bash
export REPO=/home/foresight/whetstone
export PATH=$HOME/probe-tools:$REPO/.venv/bin:$PATH
export UV_CACHE_DIR=$HOME/whetstone-cache
export UV_PYTHON_INSTALL_DIR=$HOME/whetstone-python
export HF_HOME=$HOME/whetstone-hf
export PYTHONPATH=$REPO/docs/planning/pascal-4bit/night-door
export WHETSTONE_PASCAL_SDPA=1
export TORCHDYNAMO_DISABLE=1
export TORCH_COMPILE_DISABLE=1
export WHETSTONE_REPO_MIRRORS='{"/home/foresight/whetstone-donors/contig": "/home/foresight/whetstone-donors/contig", "/home/foresight/whetstone-donors/belay": "/home/foresight/whetstone-donors/belay", "https://github.com/pallets/flask.git": "/home/foresight/whetstone-donors/flask.git"}'
```

The manifests' `repo_url` already names the two donor checkouts at
`/home/foresight/whetstone-donors/contig` and `/home/foresight/whetstone-donors/belay`; the
mapping makes that explicit for the verifier's subprocesses, and the public task's canonical Flask
URL maps to its local mirror. The mirror is an operator input, never `~/.gitconfig`.

`TORCHDYNAMO_DISABLE` and `TORCH_COMPILE_DISABLE` are set because Triton's helper in torch 2.14
needs a C compiler and the measured run avoided it; `gcc`/`g++` (gcc/g++) are installed anyway so
the helper can build if it is invoked.

## Setup (once on x202)

```bash
sudo apt-get install -y gcc g++
cd "$REPO"
uv sync --extra torch
uv pip install --reinstall torch==2.14.1 --index-url https://download.pytorch.org/whl/cu126

# The committed Pascal SDPA shim is imported at interpreter startup through PYTHONPATH.
test -f "$REPO/docs/planning/pascal-4bit/night-door/sitecustomize.py"

mkdir -p "$REPO/weights/Qwen3-8B"
$REPO/.venv/bin/python - <<'PY'
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="Qwen/Qwen3-8B",
    revision="b968826d9c46dd6066d109eabc6255188de91218",
    local_dir="/home/foresight/whetstone/weights/Qwen3-8B",
)
PY
cat > "$REPO/weights/Qwen3-8B/quantize.json" <<'JSON'
{"bnb_4bit_quant_type": "nf4", "bnb_4bit_compute_dtype": "bfloat16", "bnb_4bit_use_double_quant": true}
JSON

mkdir -p /home/foresight/whetstone-donors
git clone <contig-donor-url> /home/foresight/whetstone-donors/contig
git clone <belay-donor-url> /home/foresight/whetstone-donors/belay
git clone --mirror https://github.com/pallets/flask.git /home/foresight/whetstone-donors/flask.git
```

The two donor URLs are private operator inputs, written here as placeholders for the same reason
`<run-id>` is. The fetch is the only network step besides the wheel index and the donor clones.
The quantized loader passes an explicit per-layer device map and never calls `.to()`; `--precision
bfloat16` is the **compute dtype**, while the weights are 4-bit NF4 declared by the sidecar above.

## The prep root (30 links)

§ 10.27 named 20 private tasks. Two of them cannot be scored on Linux:
`donor-b-c57246c7841a` declares **3 of its 5 declared tests `@darwin_only`** in
`tests/test_replay_batch_server_rooting.py`, and `donor-b-cc7d3f520f1c` carries a module-level
`pytestmark = pytest.mark.skipif(sys.platform != "darwin", ...)` in `tests/test_verify_cli.py`.
They stay in the corpus; this probe's sample excludes them by id, leaving **18 private tasks**.

The near-miss root is `$REPO/tasks/local/near-miss`. It carries **30 links = 18 sample + 12
held-out**: the 18 sample manifests plus the committed document's 12 members, because a held-out
split is defined over the loaded corpus and a document whose members match no loaded task is
refused. The exclusion runs before the probe draws, leaving the 18. The 12 are loaded and
excluded, never drawn.

```bash
mkdir -p "$REPO/tasks/local/near-miss"
for id in donor-a-2f4e497580ff donor-a-34daf85182d5 donor-a-4731e32044c5 \
  donor-a-12a1d8e4d766 donor-a-5e25b106874c donor-a-f100a90e47f2 \
  donor-a-955d9a079c16 donor-a-a93fe36d6e85 donor-a-d601ff2d0ec0 \
  donor-a-99c0e0464c21 donor-a-37a91266029a donor-a-df207b27e82c \
  donor-a-c32d7c672465 donor-a-6d35bb3a4d17 donor-a-3326ca8a116d \
  donor-a-18265334544f donor-a-192f26c402a3 donor-a-6884ed72a9e9 \
  donor-a-74f000a772cf donor-a-b5f840cdf71d donor-a-c6e4d4c4de87 \
  donor-a-c7cee63e3cab donor-a-d2c03949ecf3 donor-a-dc3be3134276; do
  ln -sf "$REPO/tasks/local/donor-a/$id.json" "$REPO/tasks/local/near-miss/$id.json"
done
for id in donor-b-c3e132b7469b donor-b-0fe4582aeac1 donor-b-ce6425d3101a \
  donor-b-353359e9ac6e donor-b-3e3051c4192a donor-b-468e343e9fb5; do
  ln -sf "$REPO/tasks/local/donor-b/$id.json" "$REPO/tasks/local/near-miss/$id.json"
done
```

## The probe pass (the § 10.28 measurement)

18 private + the public task `pallets__flask-4045` = **19 tasks × `K = 16` = 304 draws**. `--probe
18` is the private count; the public task is passed separately by `--public`. The sample is
§ 10.27's 20 minus the two Darwin-only tasks, so the GO is evidence on these 18 private tasks and
the public one only — not on the corpus. `K = 16` (§ 10.19), `R = 3` (§ 10.8), `R_repair = 2`, the
verifier, the gate and the held-out document are unchanged.

Run with CWD at `$REPO`:

```bash
$REPO/.venv/bin/whetstone run --night \
  --probe 18 \
  --runtime torch \
  --repair 2 \
  --supervise \
  --stall-seconds 5400 \
  --tasks $REPO/tasks/local/near-miss \
  --public $REPO/tasks/public/instances \
  --pool $REPO/tasks/public/pool.json \
  --weights $REPO/weights \
  --only Qwen/Qwen3-8B \
  --runs $REPO/runs \
  --checkpoints $REPO/checkpoints \
  --workspace $REPO/runs/<run-id>-workspace \
  --timeout 900 \
  --recorded-on <date> \
  --run-id <run-id> \
  --run-seed <seed> \
  --heldout $REPO/tasks/heldout/source-b.json
```

`--run-id`, `--run-seed` and `--recorded-on` are operator inputs typed before the run, never a
clock or a generator; one `<run-id>` per run, never reused. The probe writes no checkpoint. A
killed probe is never resumed: restart it fresh under a new `<run-id>`. The workspace must not
exist or must be empty before its command.

## The probe decision

```bash
$REPO/.venv/bin/whetstone check-probe \
  --run $REPO/runs/<run-id> \
  --heldout $REPO/tasks/heldout/source-b.json \
  --runtime torch \
  --device cuda \
  --precision bfloat16 \
  --probe 18
```

**Harness rule (what `check-probe` decides).** The control arm is `PASS` on every draw, the seed
map is non-empty, the declared draws equal `sampling.K` (`K = 16`, never a flag), the declared
sample size is `18`, the ledger's held-out record equals the digest of the committed
`tasks/heldout/source-b.json`, and the backend pins hold. `--precision bfloat16` pins the compute
dtype; the 4-bit NF4 weights are declared by the `quantize.json` sidecar. Exit 0 answers this
rule; `check-probe` exit 0 is **not the GO**.

**§ 10.28 GO (what the measurement decides).** GO iff at least one of the 304 draws is
strict-`PASS`. A zero yield is a NO-GO even when the command exits 0. A NO-GO returns the lever to
a human, never to a loosened verifier.

## The night (after a GO)

The night draws the full 52-task corpus — 51 private + 1 public — with the five declared dev ids.
It carries no `--probe`. The quantized base is spread over every visible GPU by an explicit layer range; the host is not
time-shared by other jobs.

```bash
$REPO/.venv/bin/whetstone run --night \
  --runtime torch \
  --repair 2 \
  --supervise \
  --stall-seconds 5400 \
  --tasks $REPO/tasks/local/donor-b \
  --tasks $REPO/tasks/local/donor-a \
  --public $REPO/tasks/public/instances \
  --pool $REPO/tasks/public/pool.json \
  --weights $REPO/weights \
  --only Qwen/Qwen3-8B \
  --runs $REPO/runs \
  --checkpoints $REPO/checkpoints \
  --workspace $REPO/runs/<run-id>-workspace \
  --timeout 900 \
  --recorded-on <date> \
  --run-id <run-id> \
  --run-seed <seed> \
  --heldout $REPO/tasks/heldout/source-b.json \
  --dev-subset donor-b-2e149603209a \
  --dev-subset donor-b-353359e9ac6e \
  --dev-subset donor-b-3e3051c4192a \
  --dev-subset donor-b-844db07ed482 \
  --dev-subset donor-b-9dba3ea557f5
```

## The finding, and what is not published

The finding lives at `docs/planning/pascal-4bit/finding.md` — the GO or NO-GO, the partition, the
4-bit precision, or the zero. The raw counts and the run's documents stay in the gitignored
`runs/` store, which is their only home. **Nothing here is published**: no `reports/` path gains a
directory from this series, and no figure here may be restated as the MPS series' or as a
full-precision bf16 figure.

**The corpus-removal rule.** The private corpus runs on the founder's own `x202`, and every file
added there is removed after the measurement. The near-miss root, the fetched weights and the
donor clones are operator inputs; the run's own `runs/` records stay gitignored. Nothing of the
private corpus is copied onto the host permanently.

**No count has been measured.** § 10.28 pins the measurement; it does not report one. The § 3
baseline remains unspent, and a NO-GO is a legitimate published outcome.
