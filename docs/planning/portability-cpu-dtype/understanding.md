# Understanding — portability-cpu-dtype

**Written:** 2026-10-11, Phase 2 of `wbf feat portability-cpu-dtype`. Source: the inline brief
(`docs/planning/_card/issue.md`) and the code/docs read below.

## What the work is really asking

One declared constant moves — `DEVICE_PRECISION["cpu"]` from `"float32"` to `"bfloat16"`
(`src/whetstone/loop/torch_runtime.py:53-57`) — so that the CPU-only portability arm can load a
base the machine cannot hold in fp32. The brief names the dtype change; the real ask underneath
it is **the arm's last lever for a nonzero strict-`PASS` yield**, and the honest work is making
that lever *attributable*: a dtype change is a pinned input, so it needs a Type 1 amendment and a
checkpoint that says which precision trained it.

`docs/ROADMAP.md` § 13 states the stakes exactly (`:784-792`): *"The Torch runtime loads `float32`
on CPU by declaration. The 3B base already occupies most of the declared host's memory; a 7B
would need roughly twice what the machine has and cannot be loaded at all. So **3B is the largest
base this runtime supports as written** … change the CPU dtype to `bfloat16`, which is a code
change *and* an amendment *and* alters what every earlier figure was measured under."*

## Where it sits on the core loop

Element **② the nightly improvement loop** (the runtime the loop runs on) and element **③ the
never-regress promotion gate** (comparability of two checkpoints). **Not** ① and **not** the
reward.

- **The reward is untouched.** `src/whetstone/verify/` and `tasks/` are byte-identical; the
  reward stays the deterministic re-execution exit status. This change is entirely off the reward
  path.
- **The gate's rule is untouched.** The three exits, `unverified == 0`, `R = 3` are unchanged.
  But the change is comparability-relevant: the backend module's own thesis
  (`src/whetstone/loop/backend.py:8-15`) is that *"different kernels and a different quantisation
  of the same weights do not produce the same rollouts"* — and a dtype is exactly such a
  quantisation. A bf16 candidate is not comparable to an fp32 incumbent.
- **Local + private (⑤):** unchanged — the arm runs on the user's declared host.

## Affected areas (file:line)

### The declaration and its two read sites
- `src/whetstone/loop/torch_runtime.py:53-57` — `DEVICE_PRECISION = {"cuda": "bfloat16",
  "mps": "float16", "cpu": "float32"}`. The whole change is line 56.
- `:137-138` — the trainer reads it: `dtype = getattr(torch, DEVICE_PRECISION[device])` →
  `AutoModelForCausalLM.from_pretrained(..., dtype=dtype)` (`:147-149`), then PEFT
  (`:150`). **This is training.**
- `:395-396` — the generator/gate loader reads the *same* map →
  `from_pretrained(..., dtype=dtype)` (`:407-409`). Used by `TorchGenerator` for both
  `torch_sampling_engine` and `torch_gate_engine`. **So the change also moves every rollout and
  every gated evaluation, not only training** — the amendment must say so.

### The capacity ceiling (relation, not a read site)
- `src/whetstone/loop/sft.py:59` `CAPACITY_PROBE_ITERS = 8`; `:63` `MACHINE_BYTES`;
  `:70` `HEADROOM_FRACTION = 0.85`; `:74` `CAPACITY_HEADROOM_BYTES`; `:429-444`
  `headroom_for(device_memory_bytes)` = `0.85 × device_memory_bytes`; `:447-476`
  `probe_capacity`; `:479-519` `train` (refuses `CapacityExceeded`, `TrainingTooLong` at
  `:80` `TRAINING_WALLCLOCK_CEILING_SECONDS = 24h`).
- The ceiling is *derived from the machine* (`backend._system_memory_bytes`, `:296-301` →
  `_torch_device_memory`, `:278-293`), not a constant. bf16 halves weight bytes, so it lowers the
  probe's peak and can make a base loadable that fp32 cannot fit; it also changes step speed, so
  `projected_seconds`/`TrainingTooLong` shift. **No code in `sft.py` knows the dtype** — it is
  reached only through the trainer.

### The record (`Backend`) — dtype is currently **absent** everywhere
- `src/whetstone/loop/backend.py:93-131` — `Backend` frozen dataclass with exactly five fields
  (`name`, `library`, `version`, `device`, `device_memory_bytes`) and `recorded()` at `:118-131`.
  **No precision/dtype field.**
- `src/whetstone/loop/sft.py:778-792` — `write_checkpoint` body: `backend.recorded()`,
  `training_args.recorded()` (`:262-276`, no dtype), `tool_versions`, `capacity_probe`.
  **A fp32 checkpoint and a bf16 checkpoint would carry byte-identical provenance.**
- `src/whetstone/loop/torch_runtime.py:358-379` — `TorchGenerator.provenance()`: no dtype.
- `reports/portability-arm/report.md` — declares base/revision/device ("CPU — a Linux host with
  16 GB of RAM and no accelerator") but **never a dtype**; `report.json` still pins the 0.5B
  base and § 10.11.

### Comparability at the gate
- `src/whetstone/loop/gate.py:311-332` `refuse_cross_backend`: **`if candidate == incumbent:
  return`** — a whole-dict comparison. So *if* the backend record gains a `precision` key, a
  bf16-vs-fp32 pair is refused by the existing code with **no gate-logic change**. The docstring
  at `:318-320` already exempts an absent backend (old checkpoints: "an unknown is not a
  mismatch").

### Amendment + prose
- `PREREGISTRATION.md:306-325` amendment log; `:638-951` § 10.11-§ 10.16 (the arm's Type 1
  amendments). The nearest precedent is § 10.13 (`:740-791`): pins an input for an existing arm,
  states non-comparability, states what is not claimed.
- `docs/ROADMAP.md:784-792` (§ 13) and `:882-894` (§ 14's 2026-10-11 correction) — both name the
  CPU dtype; § 13's *"loads `float32` on CPU by declaration"* becomes false.
- `src/whetstone/loop/torch_runtime.py:50-52` docstring: *"A CPU run in fp16 is arithmetic that
  silently produces nothing useful"* — the reason written for `float32`; becomes stale.

### Tests that will move
- `tests/loop/test_torch_trainer.py:176-187` — `test_every_declared_device_has_a_stated_precision`
  asserts **key presence only**, not the value. Changing the value breaks **nothing**; a new test
  pinning the value is the missing guard.
- `tests/loop/test_backend.py:150-176` — asserts `Backend.recorded()` is **exactly**
  `{name, library, version, device, device_memory_bytes}`. **Adding a field breaks this test** —
  deliberately, on the record (watched failing first).
- `tests/loop/test_sft.py:166-184` — provenance records `capacity_probe.iters`; `:577-628`
  projected-rate/ceiling tests; `:546-574` `headroom_for`.
- `tests/loop/test_arm.py:101-157,233-249` — probe run, machine-derived ceiling, `UnknownMachine`.
- `tests/test_docs.py` — `PREREGISTRATION.md` must keep its 11 `## ` sections (`:568-595`),
  may contain **no `%`/percent/placeholder token** (`:598-653`), and the `__` ROADMAP citations
  (`:141-152`, `:1101-1143`) must still resolve. **No § 13/§ 14 citation exists**, so editing
  those sections moves no cited block.
- `tests/bakeoff/test_report.py:2152-2220` and `tests/bakeoff/test_transcript_locality.py:163-185`
  — pin the **exact 21-file list** under `reports/`. **Do not add a file under `reports/`.**

## Ambiguities and open questions

1. **Is "record the precision" in scope?** § 13 says the dtype change *"alters what every earlier
   figure was measured under"* — but today the dtype is recorded **nowhere**. If it stays
   unrecorded, the *amendment* is the only record of what dtype was in force, and a reader cannot
   tell two checkpoints apart. Recording it (in `Backend.recorded()`) makes the non-comparability
   enforceable and is the honest form of the change — but it ripples (`Backend` is shared with
   MLX; the exact-key test moves; the gate's whole-dict `==` then refuses a precision mismatch,
   which is arguably correct). **Recommendation:** include it, minimally and Torch-only.
2. **If recorded, what is MLX's precision?** It is declared **nowhere** in this repo
   (`mlx_runtime.py`/`sft.py` have no dtype). Inventing one would be an unverified claim. The
   shape that avoids inventing anything is an **optional** `precision: str | None`, filled only
   by the Torch describer, `null` for MLX.
3. **Base unchanged or larger?** § 10.11's mechanism makes a *base* its own Type 1 amendment
   ("each is a further Type 1 amendment naming its base and revision"). This unit pins a runtime
   input, not a base — so the base stays 3B here, and a 7B (the point of halving memory) is a
   **separate** base amendment. Confirm.
4. **Does the gate need to refuse a bf16↔fp32 pair explicitly?** If the precision is recorded, the
   existing whole-dict `==` already refuses it — no gate change. Confirm that's the intended
   reading, and add a test pinning it.
5. **Does the change move rollouts/gate as well as training?** Yes — one map, two read sites
   (`:138`, `:396`). The amendment must state non-comparability of prior **rollouts and gate
   verdicts**, not only prior training.
6. **Is CPU bf16 training sound?** Unverified here. bf16 keeps fp32's exponent range (unlike fp16,
   the reason `float32` was chosen), so the "silently produces nothing" failure does not apply —
   but the amendment must **not** claim bf16 is faster or better; the arm's probe/night is the
   test, and `accept the finding` remains a pre-committed outcome (§ 13:790-792).
7. **Reward-path guard.** `tests/test_no_inference_on_reward_path.py` scopes `verify/` and
   `tasks/`; this unit touches neither, and `src/whetstone/loop/torch_runtime.py` already imports
   torch function-locally. No new inference import reaches the reward path.

## Contradictions flagged (do not paper over)

- `docs/ROADMAP.md:785` *"loads `float32` on CPU by declaration"* and
  `src/whetstone/loop/torch_runtime.py:50-52` *"A CPU run in fp16 is arithmetic that silently
  produces nothing useful"* both become false/stale: the first because the value changes, the
  second because bf16 is not fp16. Both need dated corrections, not silent rewrites (the repo's
  convention: append a dated note; correct every sentence the change makes false).
