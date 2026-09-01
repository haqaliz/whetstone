# Spec — engine-dispatch (aspect 1 of gate-untrained-incumbent)

**PRD:** `../prd.md`. **Branch:** `feat/gate-untrained-incumbent/aliz`. This aspect makes the
gate able to score an **untrained** checkpoint as the incumbent: `gate_engine` dispatches on
`Checkpoint.untrained`, an untrained *candidate* is refused by name, and the base-only engine
is one definition, imported by identity.

## Problem slice and user outcome

The launch path's first gated evaluation needs the untrained base as the incumbent
(`docs/ROADMAP.md:663-671`). Today `gate_engine` (`src/whetstone/loop/gate.py:444-489`) passes
`adapter_path=str(checkpoint.directory)` unconditionally (gate.py:480), so an untrained
checkpoint (provenance only, no adapter — `sft.write_baseline_checkpoint`, sft.py:457-496)
dies at load time with a library error, not a named refusal. The base-only load exists only as
`baseline_engine` (baseline.py:490-527), a sibling "differing in exactly one line". User
outcome: `whetstone gate --candidate X --incumbent <untrained base>` reaches the decision
table, the untrained side is scored through the base-only load, and an operator who passes an
untrained checkpoint as the **candidate** is refused by name.

## In-scope requirements

1. **Dispatch inside `gate_engine`** (PRD req 1): the trained path passes
   `adapter_path=str(checkpoint.directory)` exactly as today; the untrained path
   (`checkpoint.untrained` is True) loads the base only. `mlx_lm.utils.load`'s `adapter_path`
   is optional (`None` = base only), so a conditional is the whole code change.
2. **Dispatch test** (PRD req 1): the first test to *invoke* `gate_engine`. Monkeypatch
   `mlx_lm.utils.load` and `mlx_lm.generate.generate` (both imported function-locally, so the
   module attributes are read at call time) to capture kwargs and return dummies. Assert
   `adapter_path` is `str(checkpoint.directory)` for a trained checkpoint and `None` for an
   untrained one. `sampler_for(1)` needs no stub (returns `greedy_sampler` by identity,
   sampling.py:232-233; `mlx.core` imported only inside the sampler's body,
   mlx_runtime.py:129) but the test must never *call* `generate()`. The test is RED on
   master — the current unconditional `adapter_path=` is exactly the credulous behaviour the
   test refuses.
3. **Untrained candidate refused by name** (PRD req 3): a new `UntrainedCandidate(ValueError)`
   in gate.py, added to `REFUSALS` (gate.py:270-281), raised in `run_gate` **after** the
   per-side re-hash (gate.py:574-575), naming the side and the checkpoint path. Only the
   candidate side is refused; an untrained incumbent is the point of the aspect. Asserted
   through `run_gate` (unit) and through `whetstone gate` (CLI test, exit 2).
4. **Decision table with an untrained incumbent** (PRD req 2): through `run_gate` with the
   existing stub engine keyed on checkpoint digest (test_gate.py:427-434): known-better →
   promoted, known-worse → rejected, one still-unverified task → the whole eval `UNVERIFIED`
   (never promoted), a regression → rejected even with a solved gain. The fixture's untrained
   checkpoint is built by `sft.write_baseline_checkpoint` (the real writer, never hand-written
   — the `_checkpoint` precedent, test_gate.py:285-310); its digest is the constant
   `sha256("")`, which the stub keying must keep distinct from the candidate's.
5. **One engine definition, imported by identity** (PRD req 4): the base-only arm is defined
   in gate.py (named `baseline_engine`, with a docstring that states the gate dispatches to it
   on `checkpoint.untrained`); `gate_engine` delegates to it on the untrained branch;
   `baseline.py` deletes its own definition and re-imports by identity
   (`baseline_engine = gate_module.baseline_engine` — baseline.py already imports gate by
   identity at baseline.py:99-117; the import direction baseline → gate is unchanged, so no
   cycle). Asserted `is` in a test. The baseline door's behaviour is byte-unchanged: its own
   suite (`tests/loop/test_baseline_door.py`) stays green untouched.
6. **Prose stops claiming adapters unconditionally** (PRD req 6): gate.py's module docstring
   (31-32), `gate_engine`'s docstring (447-456), the `NoBaseWeights` docstring (253-260) and
   its refusal message (1278), the `GateEngine` alias docstring (283-286), and `cli.py`'s
   `--weights` help (484-488).
7. **Integrity invariants** (PRD req 7): `decide()` (gate.py:158-217), the three exits, the
   retry discipline, the promotion record schema and the held-out loader are untouched; AC2
   pins (`src/whetstone/verify/`, `patch.py`, `attribution.py`) stay byte-identical to
   `origin/master`; the reward-path partition guard still holds exactly four function-local
   edges; `uv run pytest`, `uv run ruff check .`, `uv run mypy src/` green.

## Out-of-scope boundaries

- No runbook edit (aspect 2 owns `gate-runbook/runbook.md` and its guard).
- No change to `decide`, the exits, the retry discipline, the promotion record, the held-out
  split, or the CLI's flag surface (no new flags).
- No change to what the reward measures, and none to the verifier: `verify/`, `patch.py`,
  `attribution.py` stay byte-identical (the AC2 pins).
- No baseline re-measurement: nothing in this aspect spends or re-runs the § 3 measurement.

## Acceptance criteria (testable)

- AC1: the dispatch test asserts `adapter_path` — checkpoint directory for a trained
  checkpoint, `None` for an untrained one — with `load`/`generate` monkeypatched, and is
  watched failing on master (RED before the code).
- AC2: `run_gate(candidate=<untrained>, incumbent=<trained>)` raises `UntrainedCandidate`
  naming the side; `whetstone gate` with an untrained candidate exits 2; an untrained
  **incumbent** is not refused.
- AC3: the decision table (known-better → promoted, known-worse → rejected, one unverified →
  `UNVERIFIED`, regression → rejected) holds for a trained candidate vs an untrained
  incumbent through `run_gate` with the stub engine.
- AC4: `baseline.baseline_engine is gate.baseline_engine` (asserted `is`); the baseline
  door's suite passes unchanged.
- AC5: the trained path is byte-identical in behaviour — the existing gate suite
  (`test_gate.py`, `test_gate_cli.py`, `test_gate_retry.py`) passes unchanged.
- AC6: AC2 pins byte-identical to `origin/master` (`tests/bakeoff/test_format_hardening_frozen.py`
  green); the partition guard holds exactly four edges
  (`tests/test_reward_path_scope_is_partitioned.py` green); `decide()` untouched; ruff/mypy
  green.

## Dependencies and sequencing

- Depends on: `sft.write_baseline_checkpoint` and `verify_checkpoint`'s untrained branch
  (sft.py:526-535, shipped), the gate's stub-engine seams (test_gate.py), `baseline.py`'s
  existing identity imports.
- Sequence: RED tests (dispatch + refusal + decision table + identity) → GREEN (gate.py:
  refusal, dispatch, engine move; baseline.py: identity import; cli.py prose) → REFACTOR →
  integrity run.
- Feeds: aspect 2 (the runbook names an incumbent the gate can now score).

## Open questions / risks

- The exact position of `baseline_engine` in gate.py and the wording of its moved docstring —
  plan detail, not a decision (the identity pin holds regardless).
- `mlx_lm` `load` semantics with `adapter_path=None` — the documented default; the dispatch
  test pins the actual kwargs, so a future mlx-lm change fails the test rather than loading
  the wrong weights.
- The stub engine's keying on the constant `sha256("")` digest — a second untrained fixture
  would collide with the first; the fixture set uses at most one untrained checkpoint per
  run, and the tests assert sides by role, not by digest equality.