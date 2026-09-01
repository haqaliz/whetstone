# Card — gate-untrained-incumbent

**Type:** feat · **Branch:** `feat/gate-untrained-incumbent/aliz` · **Owner:** aliz
**Source:** inline brief (no GitHub issue exists; produced by the `whetstone-next` handoff, 2026-09-01)

## Brief

Build the launch-path unit `docs/ROADMAP.md:663-671,689-691` names as next: dispatch the gate's
per-side engine on `Checkpoint.untrained` so `whetstone gate --candidate X --incumbent <untrained
base>` works — today `gate_engine` (`src/whetstone/loop/gate.py:480`) passes `adapter_path=`
unconditionally, while `baseline_engine` (`src/whetstone/loop/baseline.py:490-527`) is its sibling
differing in exactly that one line, and `sft.verify_checkpoint` already accepts `untrained: true`
(`src/whetstone/loop/sft.py:526-535`).

Acceptance criteria, written first and watched failing:

1. The three exits and the full decision table hold for a trained candidate vs an untrained incumbent.
2. The untrained side loads through the base-only engine, identity-reused, never re-decided.
3. The gate runbook's "needs two nights" paragraph (`docs/planning/p3-promotion-gate/gate-runbook/runbook.md`)
   is updated in the same unit, with its guard (`tests/test_gate_runbook_guards.py`) failing first.
4. AC2 pins (`src/whetstone/verify/`, `patch.py`, `attribution.py`) stay byte-identical, and the
   reward-path partition guard still holds exactly four edges.
5. ruff / mypy / pytest green.

**Caveat:** do not edit the runbook sheet ahead of the code it would then disagree with, and
`decide()` stays untouched — the untrained incumbent must still refuse promotion on any unproven gain.

## Notes from the handoff

- The roadmap records the reasoning (`docs/ROADMAP.md:663-671`): `verify_checkpoint` already accepts an
  untrained checkpoint (`untrained: true`, no adapter — `sft.py:526-535`), and `baseline.baseline_engine`
  is `gate.gate_engine`'s untrained sibling, differing in the one line that stacks an adapter. Dispatching
  the per-side engine on `Checkpoint.untrained` takes a whole night off the critical path and makes the
  first gated evaluation the comparison the product actually claims: did the night beat the base it
  started from.
- The unit also owns the gate runbook's "needs **two** nights" paragraph, which may not be edited ahead
  of the code it would then disagree with (`docs/ROADMAP.md:670-673`).
- The launch-path operator chain (`docs/ROADMAP.md:684-688`): § 7.3 Type 1 amendment (pin the base) →
  night #1 → first gated evaluation (candidate: night #1's checkpoint; incumbent: the untrained base) →
  spend the baseline → the P4 report → the finding. This unit is the one still buildable while the GPU
  is busy, and it reads no number.