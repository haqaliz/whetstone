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

## Appended 2026-09-09: the arm's night, and its real denominator

The arm ran a full night on the declared host on 2026-09-09 (`runs/night-002`). `docs/STATUS.md`
carries the engineering account of it. What belongs here, and is recorded here because it belongs
nowhere else, is **the denominator any future rate under this arm has to be read against** — and
it is not the corpus size.

**How 62 tasks became 42.** The private corpus on the declared host holds **62** tasks: 45 from
donor A and 17 from donor B. The held-out document excludes **12** of them, leaving **50** the
night could draw on, plus the single eligible public instance — **51 tasks, 8 draws each, 408
rollouts.** Then **9 of those 51 tasks were refused before a token was generated**, each because
its source files exceed the 80,000-character oracle budget. That refusal is deliberate and is
`bakeoff/sources.py`'s design: an over-budget file set is refused whole rather than truncated,
because a truncated oracle silently changes the question the task asks. Those 9 tasks account for
**72 rollouts**, recorded `NO_ORACLE` and ranked `UNVERIFIED` — never `FAIL`, and never quietly
dropped from the count.

**And 62 is itself the host's number, not the corpus's.** `CLAUDE.md` says source B holds 66
tasks; on this arm's Linux host the same two donors at the same recorded heads with the same seeds
mint **62**. The four that do not mint are refused by the miner for a stated reason — on Linux
their tests already pass before the gold patch, so nothing goes red→green and there is no task to
make (#42). Nothing is broken: a task is not a property of a commit but of a commit *on a
platform*, which is what an execution-grounded definition of "valid task" implies once you take it
seriously. It is recorded here because a reader holding the number 66 would otherwise assume this
arm lost four tasks somewhere.

So the night generated against **42 tasks, not 62**. Any rate this arm ever publishes has 42 as
its honest denominator on this host, and a reader given only "62 tasks" would over-read every
figure by half again. The 9 refusals are a property of the corpus and the budget, not of the base:
a larger base will hit exactly the same 9.

**What the 336 generated rollouts did.** 330 produced no well-formed unified diff at all; 6
produced a patch that reached the verifier and failed to apply. **Zero reached test execution with
an applied patch, and zero were strict-`PASS`** — so the night wrote no checkpoint and this arm
still has no measured delta. Generation took 36,844 s (10.2 h) across those 336 draws: mean 110 s,
median 72 s, longest 498 s. Verification cost is not the constraint and was never close to it —
only 6 rollouts reached the verifier at all.

**The control arm was `INTACT` on 408 of 408 draws**, including 8 of 8 on the public source. The
harness could distinguish a fixing patch from a non-fixing one on every single draw of the night.
That is what makes the zero above a statement about the base rather than about the harness, and it
is why the pre-registered response is a larger base (§ 10.13) and never a looser verifier.

**Still not claimed.** No delta. The promotion gate has still never scored a real candidate, on
this arm or any other. The § 3 baseline remains unspent.

## Appended 2026-09-12: the arm's night on the larger base

The arm ran a second full night on the declared host under the base `PREREGISTRATION.md` § 10.13
names — `Qwen/Qwen2.5-Coder-1.5B-Instruct` at `2e1fd397ee46e1388853d2af2c993145b0f1098a` — with the
corpus, runtime, contract and held-out document unchanged from the night above. **The base is the
only input that moved**, which is what makes the two nights' distributions worth setting beside
each other, and what still does not make either one a published figure.

**The denominator, restated because it moved.** 62 private tasks on this host, 12 removed by the
held-out document, 50 drawable plus the single eligible public instance — 51 tasks, 8 draws, **408
rollout records**. Then **nine tasks were refused before a token was generated** on the
80,000-character oracle budget, costing **72 rollouts** recorded `NO_ORACLE` and ranked
`UNVERIFIED`. So this night generated against **42 tasks**, the same figure as the night above and
by the same arithmetic; the skipped nine are a property of the corpus and the budget, not of the
base, and a larger base hits exactly the same nine.

**What the 336 generated rollouts did.**

| outcome | count | share |
|---|---|---|
| `NO_DIFF` — no usable diff | 238 | 71% |
| `NOT_APPLIED` — diff reached the verifier, would not apply | 82 | 24% |
| `NOT_SOLVED` — patch applied, tests ran, task still failed | 11 | 3% |
| `UNVERIFIED` — verifier reached no verdict | 3 | 0.9% |
| `OUT_OF_SCOPE` — patch aimed at an operator-held test file | 2 | 0.6% |
| strict-`PASS` | **0** | — |

**The control arm was `INTACT` on 408 of 408 draws.** That is what makes the zero above a statement
about the base and not about the harness.

**Two rows here had never been non-zero in this project.** Eleven patches applied cleanly and ran
the real test suite; `NOT_SOLVED` is the only one of the four zeroes that says anything about a
base's ability to *fix* bugs rather than to *write a diff*, and before this night nothing had ever
reached it. And two rollouts aimed a patch at an operator-held test file and were refused before
anything executed — the first genuine caught reward-hacking attempts the arm has produced, as
opposed to fixtures.

**What changed, and what did not.** Under the previous base, 1.8% of rollouts produced a diff the
verifier accepted; under this one, 28%. The binding constraint recorded above — that the base could
not express a patch — is gone. What replaced it is that the diffs it now writes do not fix the
bugs, and **the arm still has no strict-`PASS`, no checkpoint, and no measured delta.** Nothing here
is a gain, and the § 3 baseline remains unspent. A figure under this arm remains non-comparable to
the main series, to any other arm, and to this arm's own figures under its previous base.

**One defect in this night's own ledger, recorded rather than corrected.** Its
`generation_contract.sampler` names `mlx_lm.sample_utils.make_sampler` and `mx.random.seed`. That
is false — `mlx_lm` is not installed on this host and every draw went through `transformers` and
`torch.manual_seed`. The fix for it shipped days earlier; the host running the night had silently
forked from `master` and never received it. `docs/STATUS.md` carries the retraction and the cause.
The ledger's `backend` block, counts, verdicts and seeds stand.
