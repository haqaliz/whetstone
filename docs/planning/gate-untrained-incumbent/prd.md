# PRD — gate-untrained-incumbent

**Unit:** `gate-untrained-incumbent` · **Branch:** `feat/gate-untrained-incumbent/aliz` ·
**Date:** 2026-09-01 · **Source:** `docs/planning/_card/issue.md` (inline brief, whetstone-next handoff)

## Problem Statement

The launch path (`docs/ROADMAP.md:684-688`) is: § 7.3 amendment → night #1 → first gated
evaluation → spend the baseline → P4 report → finding. The roadmap decided the first gated
evaluation's incumbent is **the untrained base**, not a second night — "did the night beat the
base it started from?" is the comparison the product actually claims
(`docs/ROADMAP.md:663-671`). Everything for that comparison exists except one line:
`gate_engine` at `src/whetstone/loop/gate.py:480` passes `adapter_path=str(checkpoint.directory)`
unconditionally, so an untrained incumbent (whose directory holds no adapter) cannot be scored.
Until this ships, the operator's chain needs **two** nights (`docs/planning/p3-promotion-gate/gate-runbook/runbook.md:45-47`),
the runbook disagrees with the roadmap, and the unit that closes the gap is the one buildable
while the GPU is busy — it reads no number.

For whom: the operator running the launch chain. The cost of the status quo: a second GPU
night on the critical path and a first gated evaluation that compares two nights rather than
the night against its own starting base.

## Goals & Success Metrics

- `whetstone gate --candidate <trained night checkpoint> --incumbent <untrained base checkpoint>`
  returns one of the three exits (promoted → 0, rejected → 1, UNVERIFIED → 3) with the
  untrained side scored through a base-only load.
- The gate runbook describes one night plus the untrained incumbent, and its guard holds the
  new wording.
- Measured by the test suite (this unit publishes nothing — `reports/` gains no directory, no
  `PREREGISTRATION.md` § 10 amendment is owed). Targets are acceptance criteria below, never
  model figures.

## User Personas & Scenarios

The operator (founder) following `gate-runbook/runbook.md` before/after night #1: materializes
the untrained base with the documented writer, runs the gate, and records a promotion decision
whose provenance does not depend on a second night. A sheet that disagrees with the code fails
*after* a night was spent producing the candidate (`runbook.md:6-12`), so the sheet and the
code ship in the same unit, in that order.

## Requirements

### Must-have (each testable, written first)

1. **Dispatch on `Checkpoint.untrained` inside `gate_engine`** (gate.py:444-489): the trained
   path passes `adapter_path=str(checkpoint.directory)` exactly as today; the untrained path
   loads the base only (no `adapter_path`). A dispatch test captures the kwargs of
   `mlx_lm.utils.load` and stubs `mlx_lm.generate.generate` (both imported function-locally,
   so module attributes are read at call time) and asserts `adapter_path` is the checkpoint
   directory for a trained checkpoint and `None` for an untrained one, without loading a real
   model. `sampler_for(1)` needs no stub — it returns `greedy_sampler` by identity
   (sampling.py:232-233), which imports `mlx.core` only inside its own body
   (mlx_runtime.py:129) — but the test must not *call* `generate()`.
2. **The full decision table holds for a trained candidate vs an untrained incumbent**,
   through `run_gate` with the existing stub engine: known-better → promoted, known-worse →
   rejected, one task unverified → the whole eval `UNVERIFIED` (never promoted), a regression
   rejects even with a solved gain. The existing stub is keyed on checkpoint digest
   (test_gate.py:427-434); the untrained fixture's digest is the constant `sha256("")`, so the
   sides remain distinguishable.
3. **An untrained *candidate* is refused by name, exit 2.** A night's candidate is always
   trained; an untrained candidate would carry the constant `sha256("")` digest
   (sft.py:478, `_digest_of(())`) that cannot discriminate bases — the same reason the
   baseline series identity keys on base identity rather than the digest
   (baseline.py:36-39, 163-166). The refusal fires **after** the per-side re-hash at
   gate.py:574-575 and **names the side** ("an untrained checkpoint is not a candidate").
   New refusal member in `gate.REFUSALS`, asserted through
   `whetstone gate` (CLI test, exit 2) and through `run_gate`.
4. **One engine definition, imported by identity.** The base-only arm lives in `gate.py`;
   `baseline.py`'s `baseline_engine` (baseline.py:490-527) becomes that arm, imported by
   identity and asserted `is` (imported, never copied — the house rule). `baseline.py` already
   imports gate by identity at baseline.py:99-117; the import direction (baseline → gate, never
   the reverse) is unchanged, so no cycle. The baseline door's behavior is byte-unchanged: its
   own suite stays green.
5. **The gate runbook is updated in the same unit, code first.** The "needs **two** nights"
   paragraph (runbook.md:45-47) becomes the one-night + untrained-incumbent sentence; the
   candidate-resolution block (runbook.md:36-39) and the gate command (runbook.md:88-89) name
   the incumbent as an absolute path the operator materializes with `write_baseline_checkpoint`
   (sft.py:457-496) before the gate. The replacement paragraph must state the § 3 boundary in
   words: this is the gate's incumbent, **not** the § 3 baseline measurement — different roles,
   different homes (`docs/ROADMAP.md:678-683`), a disagreement between them published as a
   finding, never reconciled. `tests/test_gate_runbook_guards.py` gains a new pin holding the
   replacement sentence, the materialization step, and the absence of "two nights", **watched
   failing against a deliberately wrong stub sheet first**; all nine existing pins stay green.
   The sheet is not edited ahead of the code (`docs/ROADMAP.md:670-673`).
6. **Prose stops claiming adapters unconditionally**: `gate.py`'s module docstring (31-32),
   `gate_engine`'s docstring (447-456), the `NoBaseWeights` docstring and refusal message
   (253-260, 1278), and `cli.py`'s `--weights` help (484-488).
7. **Integrity invariants hold**: AC2 pins (`src/whetstone/verify/`, `patch.py`,
   `attribution.py`) byte-identical to `origin/master`; the reward-path partition guard still
   holds exactly four function-local edges; `decide()` (gate.py:158-217) untouched; `uv run
   pytest`, `uv run ruff check .`, `uv run mypy src/` green.

### Should-have

- `whetstone gate --help` / `cli.py` prose states that an untrained incumbent is scored
  without an adapter.

## Technical Considerations

- **Core-loop element:** ③ never-regress promotion gate — this is the gate's first real
  incumbent. Core-loop elements ①, ②, ④, ⑤ are untouched.
- **Reward stays execution-grounded:** nothing on the reward path moves (AC2 pins). The unit
  changes only which weights an engine loads — the same STRICT verifier, greedy sampler
  (`sampler_for(1)` by identity) and retry discipline grade both sides. `UNVERIFIED` is still
  never a win: `decide()` is byte-untouched.
- **Design (confirmed 2026-09-01):** dispatch folded into `gate_engine`; `baseline_engine`
  re-imported by identity from `gate.py`; untrained candidate refused by name; runbook
  incumbent is a `write_baseline_checkpoint`-materialized path.
- **Import direction:** `baseline.py:78` imports gate; `gate.py` must not import `baseline`
  (cycle). Hence the arm lives in `gate.py`.
- **Constant digest caveat:** an untrained checkpoint's digest is `sha256("")` for every
  untrained base. The promotion record carries digests only (gate.py:748-788) and needs no
  `untrained` field; the refusal in requirement 3 keeps the constant digest from ever being
  the *candidate* side's identity. The gate's incumbent is **not** a § 3 re-measurement:
  incumbent counts live in the gitignored `runs/promotions/`, never
  `reports/baseline-measurement/` (`docs/ROADMAP.md:678-683`).
- **Downstream consumer checked:** the honest-number report's `BaseMismatch`
  (honest_report.py:75-80) keys on the declared base (`repo_id` + `revision`) of the two
  checkpoints; an untrained checkpoint's provenance names its base (sft.py:480-495), so a
  promotion recorded against an untrained incumbent of the same base passes the check — no
  mismatch, no change needed there.
- **Test seams:** the existing stub engine injection (`engine=` on `run_gate`; monkeypatched
  `gate.gate_engine` in CLI tests); the untrained fixture builder `_untrained` in
  `tests/loop/test_baseline_checkpoint.py:43-59`; a dispatch test monkeypatching
  `mlx_lm.utils.load`/`generate`.
- **Dependencies:** all met — `verify_checkpoint` accepts the untrained shape (sft.py:526-535),
  base resolution is provenance-only (`_base_for`, gate.py:1269-1289), the runbook paragraph is
  currently unguarded (no existing pin references "two nights"), the partition guard needs no
  new edge.

## Risks & Open Questions

- **`mlx_lm` `load` with `adapter_path=None`** — the documented default; the dispatch test
  pins the actual kwargs passed, so a future mlx-lm that changes the semantics fails the test
  rather than silently loading the wrong weights. This is the nearest feasibility risk; the
  dispatch test is the answer, and the runbook's fixture-verification step (runbook.md:63-78)
  catches it before a real pair.
- **A gate scoring an untrained incumbent looks like the baseline measurement.** The roadmap
  settled it (`docs/ROADMAP.md:678-683`): different homes, different roles, and a disagreement
  between them is published as a finding, never reconciled. The runbook's replacement paragraph
  must state this boundary explicitly.
- **Runbook ordering.** The sheet must not be edited ahead of the code
  (`docs/ROADMAP.md:670-673`); the guard's new pin is written as a failing test first.
- **Open:** the exact name of the arm in `gate.py` (`untrained_engine` vs keeping the
  `baseline_engine` name there) — a plan-level detail; the identity `is` pin holds regardless.

## Out of Scope

- Any change to the reward, `decide()`, the three exits, the retry discipline, the promotion
  record schema, or the held-out split.
- The § 3 baseline measurement and its runbook; the night; `check-leakage`; the morning report;
  the honest-number report.
- A second task family, the dashboard, distillation, closing cheats 6/10, and
  `docs/technical/ARCHITECTURE.md` — all remain post-horizon.
- Publishing anything: `reports/` gains no directory and no `PREREGISTRATION.md` § 10
  amendment is owed (no new published series).