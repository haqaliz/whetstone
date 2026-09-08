# Running what a night produced, on somebody else's machine

A night's output is a **LoRA adapter** — two small files that mean nothing without the base they
attach to. That is the right shape for the loop: a night produces megabytes, not gigabytes, and
the adapter's provenance can name exactly which base and which revision it belongs to. It is the
wrong shape for anybody who just wants to *run* the thing.

This is the path from that adapter to a model that loads in Ollama, LM Studio, Jan or GPT4All,
on macOS, Linux or Windows.

## 1. Fuse the adapter into its base

```
whetstone fuse \
  --checkpoint checkpoints/night-001 \
  --base weights/<the base the adapter names> \
  --revision <the immutable sha it was verified against> \
  --repo-id <the base's repository id> \
  --out fused/night-001
```

The checkpoint is re-hashed before a tensor is read from it, and the fuser is chosen by the
checkpoint's **own recorded backend** rather than by whatever runtime this machine happens to
have. That matters more than it sounds: a Torch adapter and an MLX adapter are different tensor
layouts behind the same filename, and pointing the wrong fuser at one does not raise — it emits
weights, and nothing looks wrong until somebody measures a model that was never trained.

The result is a standalone model directory plus a `fusion.json` recording the base, the
revision, the adapter's digest and the runtime that merged them. Fusing destroys the distinction
the checkpoint made — afterwards there is no adapter left to inspect — so that record is written
at the one moment it is still knowable.

## 2. Convert to GGUF

**This step is documented, not wrapped.** `llama.cpp` owns the GGUF format and its converter;
this repository does not vendor, wrap or version it. A wrapper would mean Whetstone silently
owning llama.cpp's bugs while appearing to own its quality, and the converter moves on its own
schedule for reasons that have nothing to do with this project.

```
git clone https://github.com/ggerganov/llama.cpp
python llama.cpp/convert_hf_to_gguf.py fused/night-001 --outfile night-001.gguf --outtype f16
```

Quantise if you want it smaller — `llama.cpp/llama-quantize night-001.gguf night-001-q4.gguf Q4_K_M`
is the usual choice. Every quantisation is a **different model** from the one the gate scored:
whatever a promotion decision said about the fused weights, it did not say it about a 4-bit
requantisation of them.

## 3. Run it

```
ollama create night-001 -f Modelfile     # FROM ./night-001.gguf
ollama run night-001
```

LM Studio, Jan and GPT4All all sit on llama.cpp and load the same file.

## What travels with the model, and what does not

The fused weights carry `fusion.json`, and the checkpoint they came from carries its own
provenance: the base, the revision, the dataset digest, the training arguments, the runtime and
the capacity the probe measured. What does **not** travel is any claim that the model is better
than its base. That is the promotion gate's question, asked on a held-out set, and a fused model
is not evidence about itself.

If you publish it, `whetstone card` renders the model card from the checkpoint and the night's
ledger — including the unverified count beside the training-set size, because a yield quoted
without its denominator is the number this project exists not to publish.

## Why you cannot skip the fuse step

The adapter itself belongs to the runtime that trained it, and the two this repository supports
disagree about everything except the name of one JSON file:

| | MLX | PEFT / Torch |
|---|---|---|
| weights file | `adapters.safetensors` | `adapter_model.safetensors` |
| tensor key | `…self_attn.q_proj.lora_a` | `base_model.model.…self_attn.q_proj.lora_A.weight` |
| shape of A | `(896, 8)` — `(in, r)` | `(8, 896)` — `(r, in)` |
| config keys | `fine_tune_type`, `num_layers`, `lora_parameters` | `r`, `lora_alpha`, `target_modules`, … |

So `adapter_config.json` is written in **one** vocabulary — the trainer's — and an MLX adapter is
not a PEFT adapter with the wrong metadata. It is a different set of tensors, differently named
and transposed. Fusing is the bridge, and the fused model is a plain `Qwen2ForCausalLM` that
every runtime loads.

**Do not rename the file to make the other loader accept it.**
`mlx_lm.tuner.utils.load_adapters` ends with `model.load_weights(..., strict=False)`. Point it at
a renamed PEFT adapter and it does not raise: none of the keys match, so it loads **nothing** and
hands back a model whose LoRA layers are still at their initialisation. That model runs, produces
plausible output, and is untrained. An error would have been the kinder outcome.
