# Understanding — gate-untrained-incumbent

**Branch:** `feat/gate-untrained-incumbent/aliz` · **Date:** 2026-09-01

## What the work is really asking

`docs/ROADMAP.md:663-671` names this unit: dispatch the gate's per-side engine on
`Checkpoint.untrained` so `whetstone gate --candidate X --incumbent <untrained base>` reaches a
decision. Today the only obstacle is `gate_engine`'s unconditional
`adapter_path=str(checkpoint.directory)` (`src/whetstone/loop/gate.py:480`). Removing it takes a
whole GPU night off the launch path (`docs/ROADMAP.md:663-671, 684-688`): the first gated
evaluation becomes candidate = night #1's checkpoint, incumbent = the untrained base — the
comparison the product actually claims (did the night beat the base it started from?). The unit
also owns the gate runbook's "needs **two** nights" paragraph
(`docs/planning/p3-promotion-gate/gate-runbook/runbook.md:45-47`), which may not be edited ahead
of the code it would then disagree with.

## What the code actually shows (all verified on this branch)

1. **The one-line obstacle.** `gate_engine` (gate.py:444-489) passes `adapter_path=` at gate.py:480
   with no regard for checkpoint shape. `baseline_engine` (baseline.py:490-527) is its sibling
   differing in exactly that one line, and `mlx_lm.utils.load`'s `adapter_path` is optional
   (`None` = base only), so a conditional is all the code change needs.
2. **Nothing else blocks an untrained incumbent.** `verify_checkpoint` already accepts the
   untrained shape (sft.py:526-535); base resolution is provenance-only (`_base_for`,
   gate.py:1269-1289); `decide`, the retry seam, the counts and the promotion record never see
   the checkpoint. `gate.py` currently contains zero occurrences of "untrained". An untrained
   checkpoint's digest is the constant `sha256("")` — already understood by the baseline series
   identity (baseline.py:36-39, 163-166); the promotion record carries digests only and needs no
   `untrained` field.
3. **The import direction constrains the design.** `baseline.py:78` imports gate; gate must not
   import baseline (cycle). So the untrained arm must live in gate.py — either the dispatch
   folds into `gate_engine` itself (the roadmap's phrasing points at this), with `baseline.py`
   importing the base-only arm from gate **by identity** (asserted `is`, never copied), or the
   dispatch happens at the per-side construction site (gate.py:581-586) with the untrained
   engine living in gate.py.
4. **The runbook's two-nights paragraph is currently UNGUARDED.** `tests/test_gate_runbook_guards.py`
   pins nine properties (flags ⊆ parser, absolute paths, one worktree, `R` by identity, record
   home, fixture-before-real ordering, liveness sentence, no-rerun phrasing, check-leakage block)
   — none references "two nights", so the rewrite is unopposed. The sheet also names the
   incumbent path `/…/checkpoints/night-001` in the candidate-resolution block and the gate
   command (runbook.md:36-39, 88-89) — both must become the untrained base checkpoint. The unit
   should add a *new* pin holding the replacement sentence, watched failing first.
5. **Test seams.** The gate's suites inject a stub engine (`engine=` param of `run_gate`;
   monkeypatch of `gate.gate_engine` in CLI tests). `gate_engine` itself is smoke-tested only
   (test_gate.py:891). A dispatch test can monkeypatch `mlx_lm.utils.load` (imported
   function-locally, so the module attribute is read at call time) to capture `adapter_path`
   without loading a model. The untrained-checkpoint fixture builder already exists in
   `tests/loop/test_baseline_checkpoint.py:43-59` (`_untrained`).
6. **Prose drift to correct alongside the code:** `gate_engine`'s docstring (gate.py:447-456),
   the `NoBaseWeights` docstring/refusal (gate.py:253-260, 1278), the module docstring
   (gate.py:31-32), and `cli.py:484-488` `--weights` help all assert "base + LoRA adapter"
   unconditionally.
7. **Non-goals verified:** the reward path (`src/whetstone/verify/`, `patch.py`,
   `attribution.py`) is untouched by any of this; the partition guard needs no new edge (the
   dispatch lives inside `gate.py`, already an exempt package); `decide()` must not move.

## Open questions for the PRD

- **Dispatch site**: inside `gate_engine` (one conditional on `checkpoint.untrained`) vs. at the
  per-side construction site. Recommendation: fold into `gate_engine` — it is the single seam
  the roadmap names, and the tests inject the whole engine per side, so the dispatch is tested
  exactly where the real machine would hit it.
- **`baseline_engine`'s fate**: with the arm in gate.py, baseline.py should import it by
  identity (`assert baseline.baseline_engine is gate.<arm>`), removing the sibling duplication —
  or keep the name `baseline_engine` in gate.py and have baseline.py re-export. Either way the
  "differing in one line" pair becomes one shape-aware engine.
- **Runbook wording**: what the replacement paragraph says ("one night + the untrained base"),
  what the incumbent path becomes, and what new guard pin holds it.
- **Does the gate need to *refuse* anything new?** An untrained *candidate* would be nonsense
  (a night's candidate always trained). Decide: refuse `candidate.untrained` by name, or leave
  it (an untrained candidate vs untrained incumbent would both be sha256("") digests and equal
  solves → rejected by the `>` term anyway)? Refusing by name is the house style.

## Guardrail placement

- Core-loop element changed: **③ never-regress promotion gate** — its first real incumbent.
- Reward stays execution-grounded: the reward path is pinned byte-identical; this unit changes
  only which weights an engine loads, never what grades a rollout.
- `UNVERIFIED` still never a win: `decide()` and the three exits are untouched.
- Local/private: pure local machinery; nothing leaves the box. Not redundant with a better
  base: the gate and its comparison are the durable moat; a better base only strengthens the
  incumbent.