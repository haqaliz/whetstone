# Spec — sheet-alignment (probe-sample-pin)

**PRD:** `../prd.md`. **Branch:** `feat/probe-sample-pin/aliz`. **Date:** 2026-10-31.

## Problem slice

The Torch/MPS sheet runs a 2-task harness probe and states only the harness rule. Under § 10.25
the probe *is* the measurement (16 private + 1 public at `K = 16`, 272 draws), and the GO is a
yield rule the command does not decide. Align the sheet and its guard, and remove the stale
raise-`K` advice the finding has already contradicted.

## In-scope

1. **Probe block** (`docs/planning/torch-mps-series/night-door/runbook.md:143-169`):
   `--probe 2` → `--probe 16`. Keep every other flag and the roots order (`--tasks .../donor-b`
   before `--tasks .../donor-a`).
2. **check-probe block** (`:177-184`): add `--probe 16` after `--precision float16`.
3. **The two decisions** (`:194-199`): replace the single "proceeds iff" sentence with:
   - **Harness rule (what `check-probe` decides):** control `PASS` on every draw, non-empty seed
     map, declared draws `== sampling.K = 16`, the held-out digest, the backend pins, and now the
     declared sample size `16`. Exit 0 answers the harness; exit 1 is a named violation; exit 2
     is a refusal.
   - **§ 10.25 GO (what the measurement decides):** GO iff at least one of the 272 draws is
     strict-`PASS`. `check-probe` exit 0 is **not** the GO. A zero yield is a NO-GO even when the
     command exits 0. A NO-GO returns the lever to a human, never to a loosened verifier.
4. **The sample statement** near the denominator paragraph (`:266-270`): state 16 private + 1
   public = 17 tasks × `K = 16` = **272 draws**, the sample is the 16 named in
   `PREREGISTRATION.md` § 10.26, and 4 of the 16 are oracle-budget-excluded (`NO_ORACLE`, 64
   expected draws, counted as unverified, never dropped).
5. **Halt text**:
   - `:335-336` "The next response is to raise `K` …" → § 10.25's NO-GO sentence: a zero is a
     legitimate published outcome; the next lever is a human decision, never a loosened
     verifier.
   - `:271-273` the earlier "Raising it is the roadmap's named response…" → `K` is declared at
     `16`; the 8B night at `K = 16` produced zero, and the finding states raising `K` alone is
     not supported (`finding.md:72`).
6. **Repair description** (`:53-54`): the § 10.23 generic repair is stale. Say the prompt carries
   the first unpassed declared node id and its junit outcome (`failed`, `error`, `skipped`,
   `absent`) and **no test body, no captured output and no prior completion** (§ 10.25).
7. **Remove the "cheap chain check" framing.** The probe is the § 10.25 measurement, not a
   cheap pre-night smoke test. Sweep the sheet for "cheaply", "validate the chain cheaply" and
   the "the probe exists to validate the chain" sentences (`:171-173`, `:262-264`) and replace
   them with the measurement framing; keep the chain-validation facts (weights re-hash, frozen
   contract, control arm, held-out exclusion, seeded draws, journals, ledger) as what the
   measurement also proves. Update the guard docstrings that repeat "cheap" (`:14`,
   `test_the_night_block_documents_the_remine_and_the_probe_does_not`).
8. **The guard** (`tests/test_torch_mps_runbook_guards.py`):
   - update the docstring (including the stale "because `check-probe` does not pin the backend"
     in bullet 6) and the parse test from `--probe 2` to `--probe 16`;
   - assert the check-probe block passes `--probe 16`;
   - assert the night block still has no `--probe`;
   - assert the two-decision sentences: "check-probe exit 0 is not the GO", "at least one of the
     272 draws", "NO-GO", "never to a loosened verifier";
   - assert the 272/16-task sample sentence and the four `NO_ORACLE` ids (or a phrase naming
     them);
   - assert the raise-`K` sentences are absent and the replacement is present;
   - assert the repair description names "first unpassed declared node id" and "junit outcome",
     and says "no test body"/"no captured output"/"no prior completion";
   - keep `test_every_flag_the_commands_pass_exists_in_the_parser` green (the `--probe` parser
     flag lands in `probe-pin` first).
   - Do **not** add a third `whetstone run --night` block: the guard's "exactly two door
     blocks" premise stands.
9. **Stale spec** (`docs/planning/torch-mps-series/night-sheet/spec.md`): a dated supersession
   note at the top, naming the live sheet and § 10.25/§ 10.26. No rewrite.

## Out-of-scope

The probe run itself; the base/runtime; the reward, gate, corpus, held-out document, `K`, `R`;
the § 10.26 text (separate aspect); the MPS hang.

## Acceptance (test-first)

- The guard fails before the sheet changes (it expects `--probe 2`) and passes after.
- The sheet's probe block and check-probe block both carry `--probe 16`; the night block carries
  none.
- The two decisions are distinct and both state the 272-draw GO; no sentence claims the command
  exit is the measurement's GO.
- The raise-`K` advice is gone; the stale generic-repair sentence is replaced.
- `uv run pytest tests/test_torch_mps_runbook_guards.py tests/test_docs.py -q`, `ruff`, `mypy`
  green.

## Sequencing

Last aspect; depends on `probe-pin` for the parser flag and on `sample-amendment` for the ids.
The write-up (`CHANGELOG.md`, `docs/STATUS.md`, `CLAUDE.md`) lands with it.
