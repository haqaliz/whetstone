# Spec — measurement-door (aspect 1 of torch-baseline-door)

**PRD:** `../prd.md`. **Branch:** `feat/torch-baseline-door/aliz`. This aspect makes the § 3
baseline door able to score a Torch checkpoint and record the runtime, without changing the
reward, the counts or the series key.

## Problem slice and user outcome

`measure()` scores the untrained checkpoint through the module-level `baseline_engine`, which
loads MLX only (`baseline.py:107-111`, `gate.py:560-599`). The current main series is Torch/MPS
(`PREREGISTRATION.md` § 10.21), so the door cannot produce the series' § 3 anchor. The user
outcome: the operator runs the same module door with `--runtime torch` (or on a Torch-only
machine without the flag) and gets evidence and an artifact that name the runtime that actually
ran, while an ambiguous or unavailable runtime is refused by name.

## In-scope requirements

1. **Dispatch by identity.** `engine_for(name)` returns the module global `baseline_engine` for
   MLX and `torch_runtime.torch_gate_engine` for Torch, importing `torch_runtime` inside the
   function. `backend.family` is the classifier.
2. **`measure` resolution.** New keyword-only `prefer` and `backend`; `engine` defaults to
   `None`. If `engine is None`, resolve `backend = backend or detect(prefer=prefer)` and
   `engine = engine_for(backend.name)`; an injected engine without a backend is a named
   `ValueError`. Detection happens after the measured-once guard. `BaselineMeasurement` carries
   the backend and `disclosure()` prints a `runtime:` line.
3. **Evidence.** `write_evidence(..., backend)` writes `backend.recorded()` and calls
   `tool_versions(backend=backend)`. `_read_evidence` requires and validates the block: a
   mapping with string `name`, `library`, `version`, `device`; integer
   `device_memory_bytes >= 0`; `precision` a string or `None`; `backend.family(name)` must
   resolve.
4. **Artifact.** `build_baseline_report(..., backend=None)` requires a backend when
   `measured=True`, writes it, and adds `backend` to `_BASELINE_DIGESTED_FIELDS` and
   `_BASELINE_KNOWN_FIELDS`. `render_artifact` reads the evidence's backend and passes it.
   `read_baseline_document` returns `backend` on `BaselineDocument` and requires it for a
   measured document. The declaration carries none.
5. **Parser and refusals.** `--runtime` with `choices=(MLX, TORCH)`; in `_measure_flags`;
   `_measure_main` passes `prefer=args.runtime`; `REFUSALS` gains `NoBackend` and
   `AmbiguousBackend`.
6. **Series key unchanged.** `SeriesIdentity` and `read_series_identity` do not read the
   backend; a same-base artifact under another runtime is refused by the measured-once guard.
7. **Honest-report composition.** A measured baseline artifact with a Torch backend is accepted
   by `honest_report` for a same-series promotion record, on a stub-engine fixture.

## Out-of-scope boundaries

- Spending the measurement, any real weights or GPU run.
- A Torch operator sheet or a new `reports/` home.
- Changing the series key, § 3's protocol, the held-out split, `K`, `R`, the reward path, the
  gate's rule, or the MPS hang.
- Any `whetstone` CLI subcommand.

## Acceptance criteria (test-first; each refusal watched failing first)

1. `engine_for(MLX) is gate.baseline_engine` and `engine_for(TORCH) is
   torch_runtime.torch_gate_engine`; `baseline.py` imports no `mlx`, `mlx_lm` or `torch` at
   module scope (the AST walk extended to `torch`).
2. `measure(..., backend=fake_torch, engine=stub)` writes an evidence document whose `backend`
   equals `fake_torch.recorded()` and whose `tool_versions` contains `torch` at the fake
   version and not `mlx-lm`; the measurement's `disclosure()` includes the runtime line.
3. `measure` with no engine and a monkeypatched `detect` returning a Torch backend dispatches
   the Torch engine by identity; with `detect` raising `NoBackend` or `AmbiguousBackend`, the
   module door exits 2 with the named reason and the stub engine is never asked.
4. `render_artifact` carries the evidence's backend into `report.json`; `read_baseline_document`
   returns it; editing only the backend in the artifact makes the loader refuse the seal.
5. A measured artifact without a backend is refused by name; a declaration without one reads
   with `backend is None`, `measured is False`, and the committed
   `reports/baseline-measurement/report.json` is read unchanged.
6. `--runtime` is in the parser with both choices and in `_measure_flags`; a render mode beside
   it is refused with the usage code.
7. Two artifacts with the same base/revision/held-out digest but different backends have the
   same `SeriesIdentity`; a second measurement of that series is refused by name.
8. The honest-report door renders a same-series promotion record against a measured baseline
   carrying a Torch backend (exit 0, three artifacts), with no change to `honest_report.py`.
9. The full suite is green; no number is claimed; no reward-path file moves.

## Dependencies and sequencing

Consumes the shipped `backend` module, `torch_runtime.torch_gate_engine`, the shipped baseline
door and reporter. The write-up aspect follows the green code. The operator's measurement is
after the § 10.25 probe and is not part of this unit.

## Open questions / risks

- The `detect()` import happens after the measured-once guard; a broken runtime import after
  `find_spec` succeeds is a pre-existing `backend.describe` risk.
- The measured artifact requires a backend, so the fixture writers in
  `tests/loop/test_baseline_document.py`, `tests/bakeoff/test_baseline_report.py` and
  `tests/loop/test_honest_report_door.py` gain a fixture backend. The existing declaration is
  not rewritten.
