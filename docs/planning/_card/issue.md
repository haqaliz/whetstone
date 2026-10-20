# feat torch-mps-series — a universal main series on Torch/PEFT

**Source:** inline brief, from the 2026-10-20 decision after the MPS arm. No GitHub issue exists for
this slug. Branch `feat/torch-mps-series/aliz`, worktree
`.claude/worktrees/feat-torch-mps-series`.

## Brief

The MLX series produces an **MLX adapter**, loadable only on Apple Silicon. The user wants a model
**everyone can use**, and the MPS arm proved the cross-platform path locally: a Torch/PEFT LoRA
(`torch 2.14.1`, `mps`, `float16`, 0.5B base) trained in ~21 minutes and sealed a PEFT adapter that
any `transformers`/`peft` stack can load on CUDA, CPU, MPS, Linux, Windows or Mac. That arm is a
demo, not a model: it trained on night #1's 6 examples and `check-leakage` exits 1 (4 of 6 touch
`donor-a-c6e4d4c4de87`).

This unit plans the **Torch/PEFT main series on the Mac's MPS**, with a base large enough to have a
chance at a strict-`PASS` and small enough to fit the declared MPS headroom. The artifact is a
universal PEFT adapter; the private corpus never leaves the machine. The MLX 32B series remains a
separate, Apple-only evidence series and may be run later.

**The MPS ceiling, measured:** the arm's backend records `device_memory_bytes = 30,150,672,384`
(30.15 GB) and the declared headroom is 0.85 × that = **25.6 GB**. A 7B base at `float16` is ~14 GB
and fits; a 14B at `float16` is ~28 GB and does not fit the declared headroom. The base is
therefore a **7B-class HF model**, not the MLX 4-bit directories on disk (those are MLX format and
the Torch runtime cannot load them).

**Honest risk, stated before anything runs:** the 7B-class base has historically produced **zero**
strict-`PASS` on this task family in the MLX format-hardening arm; the only nonzero yield measured
is the 32B. A Torch/MPS 7B night may also select nothing. A zero is a valid published outcome; the
response is not a looser verifier.

## Acceptance criteria (written first)

1. **A Type 1 `PREREGISTRATION.md` amendment** pins the new main series: runtime `torch` on `mps`,
   precision `float16`, the base repo id and immutable revision, and the fact that its figures are
   **non-comparable** to every MLX figure and to the portability arm's; the MLX series is not
   retired, it is a separate series. The amendment is committed **before** the night that records it.
2. **The base is fetched and recorded** through the existing weight fetch, with `==`-style
   provenance (repo id, revision, hashes), and it fits the MPS headroom as measured by the capacity
   probe.
3. **A Torch/MPS night sheet** exists for the new series, held by a guard: the same corpus, dev
   subset, held-out document and `check-probe` pins as the MLX sheet, but the Torch runtime, the 7B
   base, the torch-only environment, absolute paths, and the pause/resume rule. It names no
   worktree.
4. **A probe on MPS exits 0** through `check-probe` (control `PASS` every draw, seed map non-empty,
   `draws == sampling.K`, held-out digest matches), and the probe's ledger records the Torch/MPS
   backend.
5. **The night** writes a ledger; if it selects at least one strict-`PASS`, it writes a sealed v2
   PEFT checkpoint whose provenance records `torch`/`mps`/`float16`. If it selects none, the ledger
   states the zero and the finding accepts it.
6. **`check-leakage` exits 0** on the night's clean training set, and **`gate` returns
   `promoted`/`rejected`** on the Torch/MPS candidate against the **untrained Torch/MPS incumbent**
   (a cross-runtime comparison is refused, correctly).
7. **The finding** records the partition, the universal artifact (or the zero), the pause/resume
   behaviour actually observed, and no number the ledger does not carry.
8. **Nothing on the reward path moves:** `src/whetstone/verify/`, `tasks/`, the held-out document
   and the gate rule are byte-unchanged; the MLX series and its reports are untouched.

## Core-loop placement

Element **② the nightly improvement loop** (a second production runtime) and element **③ the
never-regress gate** (a Torch/MPS candidate against a Torch/MPS incumbent). The reward (①) is
untouched: the same STRICT verifier, sandbox, operator-held tests and held-out document.

## Roadmap grounding

- `docs/ROADMAP.md` § 14 M1: a night must select ≥ 1 strict-`PASS`; the 32B MLX arm is the only
  base with a measured nonzero, and its artifact is Apple-only.
- `reports/portability-arm/report.md`: the arm exists to demonstrate the loop on a second runtime
  and emit the adapter in the **interchange format**; it claims no delta. `PREREGISTRATION.md`
  § 10.11 and § 10.18 pin the arm and the CPU dtype.
- `docs/STATUS.md`: the portability arm's CPU host (x131) cannot run `bfloat16` — measured at
  13,000–18,500 s/iteration on an AVX2-only i7-8650U — which is why this series runs on MPS.
- `CLAUDE.md` #3/#4/#5: local/private, build what improves with the base, ship the honest number.

## Related issues (context only)

- **#64** (open) — the patch-application wall; the representation directions are spent.
- **#62** (open) — held-out split identity; out of scope.
