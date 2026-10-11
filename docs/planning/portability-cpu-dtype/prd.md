# PRD — portability-cpu-dtype

**Unit:** `feat/portability-cpu-dtype/aliz` · **Written:** 2026-10-11 · **Type:** feature, off the
reward path. **Source:** the inline brief (`docs/planning/_card/issue.md`); no GitHub issue exists.

## Problem Statement

The portability arm — the loop's second runtime (`torch` on a CPU-only Linux host) — is capped at
a 3B base **by this repository's own declaration**, not by the hardware alone.
`src/whetstone/loop/torch_runtime.py:53-57` declares `DEVICE_PRECISION["cpu"] = "float32"`, and
`docs/ROADMAP.md` § 13 states the consequence (`:784-792`):

> The Torch runtime loads `float32` on CPU by declaration. The 3B base already occupies most of
> the declared host's memory; a 7B would need roughly twice what the machine has and cannot be
> loaded at all. So **3B is the largest base this runtime supports as written** …

The arm's three nights (0.5B, 1.5B, 3B) have each selected **zero** strict-`PASS` rollouts, so no
checkpoint exists from the arm (the one real checkpoint, `checkpoints/portability-arm`, was
trained from night #1's Mac-drawn examples). The P2 pivot has fired; the patch-representation axis
is spent NO-GO in all three forms (`docs/planning/whole-function-edit-finding/measurement-run/
finding.md` § 6). § 13 names the two pre-committed responses still untried — raise *k* (demoted,
`docs/ROADMAP.md:991-992`) and **the CPU dtype** (`:788`). This unit builds the dtype response.

The second, quieter problem: the dtype is **recorded nowhere**. `Backend`
(`src/whetstone/loop/backend.py:93-131`) carries `name/library/version/device/device_memory_bytes`
and no precision; `TrainingArgs.recorded()` (`sft.py:262-276`) is runtime-agnostic; the checkpoint
and ledger carry no dtype. So a fp32 checkpoint and a bf16 checkpoint would carry **byte-identical
provenance**, and no reader — human or gate — could tell them apart. § 13 calls the change one
that *"alters what every earlier figure was measured under"* (`:789`); without recording it, that
sentence has no referent in the evidence.

## Goals & Success Metrics

- **The declaration moves, and is pinned.** `DEVICE_PRECISION["cpu"]` is `"bfloat16"`, asserted as
  a module constant (never a flag), in the shape of `sampling.K` (`sampling.py:79`).
- **The precision is attributable.** Every checkpoint and run ledger produced under the Torch
  runtime names the precision it trained/sampled in, so the non-comparability § 13 names is
  enforceable rather than asserted in prose only.
- **The change is pre-registered.** A Type 1 `PREREGISTRATION.md` amendment (§ 10.17) is committed
  **before** the night that records the new dtype, and states the non-comparability of every prior
  arm figure — training, rollouts, and gate verdicts.
- **Nothing else moves.** `src/whetstone/verify/` and `tasks/` are byte-identical; the reward, the
  gate's rule (`unverified == 0`, `R = 3`, three exits) and the § 3 baseline are untouched.
- **No number is claimed.** This unit measures nothing. Whether bf16 lets a larger base fit, and
  whether it yields a strict-`PASS`, is decided by the arm's own probe/night — and
  *"accept the finding"* (`docs/ROADMAP.md:790`) remains a legitimate terminal outcome.

Success is a merged, green tree: the constant changed and pinned, the precision recorded at both
evidence surfaces, the amendment committed, the prose corrected. **Not** a yield.

## User Personas & Scenarios

- **The founder/operator running the portability arm.** Wants the arm to be able to host a base
  whose capacity might clear the patch-representation wall that the small bases hit. Scenario:
  land the dtype change, then run the arm's next base amendment/night on a machine that can now
  load it (or find it still cannot, and record that).

## Requirements

### Must-have

- **M1 — the declaration.** `DEVICE_PRECISION["cpu"]` is `"bfloat16"`
  (`src/whetstone/loop/torch_runtime.py:56`). A test pins the exact value of **every** declared
  device (`cuda`/`mps`/`cpu`), watched failing against the old `float32` first; the existing
  key-presence test (`tests/loop/test_torch_trainer.py:176-187`) is kept.
- **M2 — the record.** `Backend` gains an **optional** `precision: str | None` (default `None`,
  last field so existing constructions are unaffected). `_describe_torch`
  (`backend.py:250-275`) fills it from `torch_device()` + `DEVICE_PRECISION`; `_describe_mlx`
  (`:234-247`) leaves it `None`, because MLX's precision is declared nowhere in this repository
  and inventing one would be an unverified claim. `recorded()` (`:118-131`) includes the key.
- **M3 — the precision reaches the evidence.** The checkpoint's `backend` block
  (`sft.write_checkpoint`, `sft.py:786`) and the run ledger's `backend` block
  (`ledger.py:397`) both carry the precision, via the single `recorded()` writer (no second copy).
  A test asserts each. `sft.verify_checkpoint` (`:917-918, :966`) reads `backend` as a mapping and
  must tolerate the added nested key without a schema bump (the five top-level body keys are
  unchanged; the seal re-hashes the whole `backend` claim).
- **M4 — comparability is enforced.** The gate's existing whole-dict comparison
  (`gate.refuse_cross_backend`, `gate.py:311-332`: `if candidate == incumbent: return`) refuses a
  **bf16-vs-fp32** pair with **no gate-logic change**. Tests pin: same-precision (bf16,bf16) →
  no refusal; cross-precision (bf16,fp32) → `MismatchedBackend`; the untrained-incumbent exemption
  and the "no backend at all" exemption (`:318-322`) still hold.
- **M5 — the Type 1 amendment.** `PREREGISTRATION.md` § 10.17 (append-only, dated) in the shape of
  § 10.13 (`:740-791`): pins the CPU precision `bfloat16` for the portability arm; introduces no
  success threshold; rewords nothing in § 1, § 4, § 6; **does not change § 10.10's base**; states
  that a figure measured under any prior arm night — its training, its rollouts, its gate verdict
  — is **non-comparable**; and carries the standard **What is not claimed** sentence (no training
  has run under this dtype; no count is claimed; the § 3 baseline unspent; zero is possible). Plus
  the matching amendment-log row (`PREREGISTRATION.md:306-325`). A `test_docs.py` guard pins the
  amendment's shape and cross-pins `bfloat16` against `torch_runtime.DEVICE_PRECISION`.
- **M6 — correct every sentence the change makes false**, on the record, not silently
  (§ the repo's convention): `docs/ROADMAP.md` § 13's *"loads `float32` on CPU by declaration"*
  (`:785`) gets a dated correction pointing at § 10.17; § 14's dtype mention is left as a dated
  record unless it reads as present-tense. `torch_runtime.py:50-52`'s docstring — *"A CPU run in
  fp16 is arithmetic that silently produces nothing useful"* — is corrected: bf16 is not fp16 (it
  keeps fp32's exponent range), and the docstring must not now claim bf16 is *better*.
- **M7 — the reward is untouched.** `src/whetstone/verify/` and `tasks/` byte-identical;
  `tests/test_no_inference_on_reward_path.py` green. The dtype change is off the reward path.

### Should-have

- **S1 — the arm's report states its dtype** in the existing run-setup section
  (`reports/portability-arm/report.md`), **without adding a file under `reports/`** and **without
  a new `N of M` figure** (the file set is pinned exactly — `tests/bakeoff/test_report.py:2152-2220`).

> **S0 resolved (was "generator provenance"): run-level attribution is the surface, and it is
> enough.** `TorchGenerator.provenance()` (`torch_runtime.py:358-379`) describes the generation
> *contract* (sampler, token budget), not the backend — it is the engine's own metadata, and no
> module in the loop consumes it to attribute a result. The `Backend` record is the one place the
> runtime is pinned (`backend.py:8-15`), and it reaches every surface a figure is attributable
> through: the checkpoint (`sft.py:786`), the run ledger (`ledger.py:397`), the arm's console
> record (`arm.py:193`) and a fusion record (`fuse.py:152`, which copies the checkpoint's
> `backend` verbatim) — all from the single `recorded()` writer. Adding a second copy to the
> generator's provenance would be a second source that can drift, which this repo's conventions
> forbid. Out of scope; named so it is not silently skipped.

### Nice-to-have

- A committed arm runbook pinning the dtype beside the base, if one is created for the arm's next
  night (none exists today — the map found no `docs/planning/portability-arm/`).

## Technical Considerations

- **One edit, two read sites.** `DEVICE_PRECISION` is read at `torch_runtime.py:138` (the trainer)
  and `:396` (the generator/gate loader), so the change moves **training, rollouts and gate
  scoring** together. The amendment states all three.
- **`Backend` is shared with MLX.** The field is optional and Torch-only to avoid declaring an MLX
  precision the repo does not know. Existing `Backend(...)` constructions keep working (defaulted
  last field); `tests/loop/test_backend.py:150-176`'s **exactly-this-key-set** assertion is updated
  deliberately, watched failing first.
- **The seal does not bump.** `whetstone-checkpoint/2` seals the five top-level body keys; adding a
  nested `backend.precision` changes the `backend` claim's bytes, not the schema. Old checkpoints
  (the v1 arm checkpoint, fp32) still verify unsealed exactly as before; a new one differs in
  `backend` and is therefore refused against it by the gate — which is the intended comparability
  outcome.
- **Machine-derived ceiling unchanged.** `headroom_for` (`sft.py:429-444`) and the probe are
  untouched; bf16 lowers the *measured* peak, which is the point. `TrainingTooLong` and the 24h
  ceiling (`sft.py:80, :508-518`) are unchanged code; a dtype that changes step speed changes
  `projected_seconds`, which the arm's own probe measures.
- **The record propagates from one writer.** `Backend.recorded()` is the single source; the three
  writers (`sft.py:786`, `ledger.py:397`, `arm.py:193`) and `fuse.py:152`'s verbatim copy inherit
  the field with no per-site edit. `Backend(...)` is constructed only in `backend.py:241,269` and
  in tests — never reconstructed from a recorded dict — so a defaulted, last `precision` field
  leaves every existing construction valid.

### Reward integrity & never-regress

- **The reward is off the path and stays execution-grounded.** The reward is the STRICT verifier's
  deterministic re-execution exit status; this change touches `src/whetstone/loop/` only.
  `src/whetstone/verify/` and `tasks/` are byte-identical (M7), and the AST guard
  (`tests/test_no_inference_on_reward_path.py`) stays green.
- **The dtype is not something a policy can set.** It is a module constant reached only through
  `torch_device()`; a rollout cannot influence it. Where a policy *could* once have been accused of
  gaming here, the dtype is a fixed input, and changing it requires a code change **and** a Type 1
  amendment — the opposite of a reward-hacking surface.
- **Never-regress is strengthened, not weakened.** The precision joins the `Backend` comparability
  key, so the gate's existing whole-dict `==` (`gate.py:323`) **refuses** a bf16-vs-fp32 pair with
  no rule change. `UNVERIFIED` remains not-a-win; the three exits, `unverified == 0` and `R = 3` are
  untouched. A reader of a gate decision can now see both sides' precision.
- **Considered alternative — score the pair and note the difference:** *refused.*
  `backend.py:8-15` and `MismatchedBackend`'s docstring (`gate.py:298-308`) already settle that
  different quantisations "do not produce the same rollouts", so scoring the pair would attribute
  the dtype's effect to the improvement — the exact failure never-regress exists to prevent. The
  self-consistent comparison is candidate-vs-incumbent **at one precision**, which is what § 10.11
  already requires of the arm's bases.

## Risks & Open Questions

- **bf16 on CPU may be slow or poorly supported** for these ops. Unverified here by design: the
  instrument is the arm's probe/night, and the amendment **must not** claim bf16 is faster or more
  capable. Mitigation: `accept the finding` is pre-committed.
- **It resets a series for a possible zero.** The arm is 0-for-3; a bf16 night may also yield
  nothing, in which case a non-comparable series was spent for a confirmation. This is the honest
  cost § 13 already priced (`:788-790`), and the reason the amendment leads with what is *not*
  claimed.
- **"Absence is an unknown, not a mismatch" (`gate.py:318-320`).** The added key means a checkpoint
  written with `precision` and one written without differ in the whole-dict `==`. The real cases
  are: new-torch vs old-v1-torch (refused — correct), MLX vs MLX (both `None` — equal), untrained
  incumbent (no backend — exempt). M4 pins each; no new exemption is added.
- **Open (operator's, not code):** does the arm attempt a larger base *before* or *after* a
  dtype-only night? The base is a separate § 10.11 amendment either way, and this unit commits to
  neither ordering.

## Acceptance criteria (testable, written first)

Each is a test that fails on the current tree and passes after the change (the repo is
test-first; `uv run pytest` green on the branch):

1. **AC1 (M1)** — `tests/loop/test_torch_trainer.py`: a test asserts
   `torch_runtime.DEVICE_PRECISION == {"cuda": "bfloat16", "mps": "float16", "cpu": "bfloat16"}`
   (exact value, watched failing against `"float32"` first). The existing key-presence test stays.
2. **AC2 (M2)** — a test asserts `backend._describe_torch(...)`'s `Backend.precision` equals
   `DEVICE_PRECISION[device]` for the running device, and that `_describe_mlx`'s is `None`.
3. **AC3 (M2)** — `tests/loop/test_backend.py`: the `recorded()` key-set test is updated
   deliberately (watched failing first) and pins `precision` among the keys; `recorded()` on a
   `Backend(precision="bfloat16")` returns `"precision": "bfloat16"`.
4. **AC4 (M3)** — a test asserts the precision appears in the checkpoint's `backend` block
   (`sft.write_checkpoint`) and in the run ledger's `backend` block (`ledger.document`), and that
   `verify_checkpoint` still verifies (no schema bump) with the nested key present.
5. **AC5 (M4)** — `tests/loop/test_gate.py`: `refuse_cross_backend` does **not** raise for
   (bf16, bf16), **does** raise `MismatchedBackend` for (bf16, fp32), and still exempts the
   untrained incumbent (backend `None`) and a checkpoint with no `backend` at all.
6. **AC6 (M5)** — `tests/test_docs.py`: a guard pins `PREREGISTRATION.md` § 10.17's shape (Type 1
   line, no-threshold/no-§1/§4/§6-rewording line, non-comparability sentence, the
   "what is not claimed" sentence, the amendment-log row), and cross-pins the string `bfloat16`
   against `torch_runtime.DEVICE_PRECISION["cpu"]` so the doc and the code cannot drift.
   `PREREGISTRATION.md` still contains no `%`/`percent`/placeholder token and keeps its 11 `## `
   sections.
7. **AC7 (M6)** — `tests/test_docs.py` (or a dated-correction guard in the `§ 10.16` pattern)
   asserts `docs/ROADMAP.md` § 13 carries a dated correction that names the change and § 10.17,
   and that no live sentence still says the arm "loads `float32` on CPU by declaration".
8. **AC8 (M7)** — `tests/test_no_inference_on_reward_path.py` and the reward-path suites stay
   green; a source-level assertion that `src/whetstone/verify/` and `tasks/` are unchanged is
   satisfied (the diff touches neither).
9. **AC9 (S1)** — `tests/bakeoff/test_report.py`'s exact 21-file `reports/` list is unchanged;
   `reports/portability-arm/report.md` names `bfloat16` in its run-setup prose, and adds no file
   and no new `N of M` figure.

## Aspect decomposition (proposed)

1. **`dtype`** — change `DEVICE_PRECISION["cpu"]` to `"bfloat16"`; add AC1; correct the module
   docstring (`torch_runtime.py:50-52`). Owns the RED for AC1.
2. **`record`** — `Backend.precision` (optional, last field), `_describe_torch`/`_describe_mlx`,
   `recorded()`; AC2–AC5; the deliberate update of `test_backend.py`'s key-set assertion.
3. **`amendment`** — `PREREGISTRATION.md` § 10.17 + log row; the dated corrections (ROADMAP § 13,
   § 14 if present-tense); AC6, AC7; the arm report's dtype sentence (AC9).
4. **`docs`** — STATUS entry, CHANGELOG under `Unreleased`, ROADMAP/CLAUDE cross-reference; lands
   last, in the same commit as the write-up rule requires.

Sequencing: `dtype` and `record` are independent code aspects (either order); `amendment` depends
on `dtype` (it pins the constant by name); `docs` last. Size: small — the core is a one-line
constant plus an optional dataclass field; the rest is tests and pinned prose.

## Out of Scope

- A larger base. § 10.11's mechanism makes a base its own Type 1 amendment (*"each is a further
  Type 1 amendment naming its base and revision"*, `:662-669`); this unit pins a runtime input.
- Raise *k*, the Mac/32B operator night, the § 3 baseline spend, producing a candidate, running the
  gate.
- Any change to the reward path, the gate's rule, the held-out document, the corpus, or a schema
  version. No new file under `reports/`. No edit to the night-door runbook.
- Any claim about yield, speed, or a larger base fitting — the arm's probe/night decides, and this
  document claims nothing about it.
