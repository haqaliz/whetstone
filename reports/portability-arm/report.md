# The portability arm — declaration

**No count is measured here: the arm has not trained.** This file exists *before* the training
it governs, which is the whole of its value. `PREREGISTRATION.md` § 10.11 opens the arm and
requires its base to be pinned before it runs; a base named afterwards is not a pinned input.

## What this arm is for

Whetstone's runtime was MLX end to end — Apple Silicon only — so the loop trained on exactly one
class of machine and the adapter it produced was loadable by exactly one runtime. That is a
property of the implementation, not of the thesis: nothing in the wedge (an execution-grounded
reward, a never-regress gate, an honest number) depends on Metal.

This arm demonstrates the loop on a second runtime and a second operating system, and emits its
adapter in the ecosystem's interchange format so that what the loop produces is loadable off the
machine that produced it.

## The pinned inputs

| | |
|---|---|
| Base | `Qwen/Qwen2.5-Coder-0.5B-Instruct` |
| Revision | `ea3f2471cf1b1f0db85067f1ef93848e38e88c25` |
| Base license | Apache-2.0 |
| Runtime | Torch / PEFT (`whetstone.loop.torch_runtime`) |
| Device | CPU — a Linux host with 16 GB of RAM and no accelerator |
| Training data | night #1's sealed training set, digest `3416702298c36a9a2ce8bada26295e54ddbd94f9666bff7b8088954ab6e4873b` |

The revision is the immutable commit sha, never a tag: two people resolving the same tag at
different times do not load the same weights.

## Why this size, and why it is not the arm's ceiling

The arm begins at the smallest base that trains on the hardware to hand, because the question it
answers first is **does the loop run at all off Apple Silicon** — and that question is answered
no better by a larger base than by a smaller one. Larger bases on this runtime are expected and
intended. Each is a further Type 1 amendment naming its base and revision, committed before it
trains; the trainer, the adapter format and the gate take the base as an input and are required
to be indifferent to its size, so scaling up is an amendment and not a rewrite. A guard reads
`torch_runtime`'s own source and fails if it names a model, a parameter count or a quantisation.

## Installing the runtime on a CPU-only host

The default `torch` wheel bundles CUDA. On the Linux host this arm runs on — no GPU — that is
roughly 8 GB of `nvidia-*` packages that can never be used. Three commands, because the CPU
index has to be scoped to the one package that needs it:

```
uv sync
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install transformers peft datasets accelerate
```

Run on a clean clone on a CPU-only Ubuntu 24.04 host: `torch 2.14.0+cpu` with
`torch.cuda.is_available()` False, `transformers 5.16.1`, `peft 0.20.0`, and
`backend.describe(TORCH)` returning a `cpu` device.

**Neither one-liner works, and the earlier draft of this section published one that does not.**
`--index-url` *replaces* PyPI rather than adding to it, so `mlx-lm` — locked for the other extra
— becomes unresolvable and the sync aborts before installing anything. `--extra-index-url`
resolves and then fails to *build* this project: uv's default `first-index` strategy consults the
extra index first for build dependencies too, and the pytorch index serves `hatchling 1.25.0`
where PyPI has 1.32.0, which is old enough to reject `license-files` as a list. Both were
executed on a clean clone before this paragraph was written; the arm's original host had a
hand-assembled environment, which is the only reason a command that cannot work was published as
though it had been run.

The manifest does not pin the CPU build, because a CUDA host wants the CUDA wheel and encoding
one host's answer there would make the other reinstall to undo it.

## Comparability, stated before any number exists

A figure measured under this arm is **not comparable** to any figure from the main series, and
not to any other arm's. Different weights, a different runtime, different kernels and a
different quantisation of the same architecture each sit between them, and each alone is enough
to make the comparison meaningless. The promotion gate refuses to score a candidate from one
runtime against an incumbent from another (`gate.MismatchedBackend`), which is the mechanical
form of this paragraph.

## What will not be claimed

Nothing here will claim the arm's adapter is better than its base. That is the promotion gate's
question, asked on a held-out set, and this arm does not ask it. The training set is night #1's
six strict-`PASS` examples — verified by re-execution, and six.

---

## Appended 2026-09-08, when the arm ran

Everything above was written before the training it governs and is left exactly as it stood —
including its opening sentence, which said the arm had not trained. It had not, then. This
section is what happened, appended rather than folded in, because a declaration edited after the
fact stops being a declaration.

**The run.** 200 iterations on the pinned base, on the declared CPU-only Linux host: 22602 s
(6 h 17 m), peak 6.84 GiB, training loss 2.235 → 2.002. The checkpoint sealed at digest
`48eae99b0d32f3887601547f97416524ddcb22900e2b35db181204f29a428f30`, holding `README.md`,
`adapter_config.json` and `adapter_model.safetensors`.

**What was demonstrated, and it is the arm's whole question.** The checkpoint re-verifies
byte-identically after crossing from ext4 to APFS; its recorded provenance survives the move;
PEFT loads it on macOS with 48 `lora_A` tensors attached, across 24 layers of `q_proj` and
`v_proj`; and `whetstone fuse` merges it into its base to produce a standalone 988 MB
`Qwen2ForCausalLM` in which **exactly the 48 parameters the adapter touched differ** from the
base. The loop runs, and what it produces is loadable, off Apple Silicon.

**What is not claimed, exactly as committed above.** No delta. Nothing here says the adapter is
better than its base; the promotion gate has still never scored a real candidate. The training
set is night #1's six strict-`PASS` examples — verified by re-execution, and six.

### Four defects in this checkpoint's own provenance

Found by reading the sealed record afterwards, and recorded here because the artifact is on disk
and its digest is not rewritten to agree with later code:

| Field | What it says | What is true |
|---|---|---|
| `capacity_probe.seconds` | `22602.024` against `iters: 8` | the full run's duration; no probe ran (#32) |
| `capacity_probe.headroom_bytes` | `32856499814` | `0.85 x 36 GiB`, a machine with 15.5 GiB (#30) |
| `tool_versions."mlx-lm"` | `0.31.3` | PyTorch ran; MLX was never installed (#33) |
| `backend.device_memory_bytes` | `0` | `16637317120` |

All four have one cause. The run was driven by a script written onto the training box, not in
version control, which went **around** `sft`'s constructors and reimplemented the parts of each
it needed (#34). The ceiling defect is the sharpest: a probe on a 15.5 GiB machine was checked
against a ceiling nearly twice that machine's total RAM, and passed — on a measured peak of
6.84 GiB, which is to say on luck rather than on fit.

The driver is now `whetstone train-arm`, in this repository and under test. A re-run through it
would produce a checkpoint whose four fields are true; this one is left as it is, and this table
is the record of what it gets wrong.
