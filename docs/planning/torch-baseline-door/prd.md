# PRD — torch-baseline-door

**Unit:** `feat/torch-baseline-door/aliz`. **Source:** inline brief from the `whetstone-next`
pick (2026-10-28), `docs/planning/_card/issue.md`. **Understanding:**
`docs/planning/torch-baseline-door/understanding.md`. **Status:** the § 3 baseline door exists
and is MLX-only; the main series is Torch/MPS since § 10.20/§ 10.21. No number is measured here.

## Problem statement

`PREREGISTRATION.md` § 3 commits to a pinned baseline — the untrained open base scored on the
held-out split by the same STRICT verifier, with provenance, **measured once, re-measured
never** — and every P4 figure is a delta from it (`PREREGISTRATION.md:121-138`,
`docs/ROADMAP.md:504-514`). The door that scores it binds `gate.baseline_engine`, which imports
`mlx_lm` unconditionally (`src/whetstone/loop/gate.py:560-599`,
`src/whetstone/loop/baseline.py:107-111`). The main series is now `Qwen/Qwen3-8B` on
Torch/PEFT/MPS (`PREREGISTRATION.md` § 10.21), so **the series that now exists cannot produce
its own § 3 anchor**.

The gap is already named by the unit that moved the series: the Torch/MPS baseline/headline is
"a follow-up unit with a code change" (`docs/planning/torch-mps-series/prd.md:28-29`,
`:159-160`, `understanding.md:60-63`). The only committed baseline artifact is a declaration
(`reports/baseline-measurement/report.json`, `"measured": false`), and
`honest_report.py:61-62` refuses a declaration-state baseline by name. Without the door, the
honest number can never be rendered for the current series, however many nights run.

**What this unit is not.** It does not spend the baseline. § 12 deliberately puts the one-shot
measurement last so a base that changes cannot strand it (`docs/ROADMAP.md:684-693`), and the
§ 10.25 repair probe is still the measurement that decides whether the 8B base survives. The
unit builds the door; the operator spends it after the base is settled.

## Goals & success metrics

- **The door can measure the current series.** `python -m whetstone.loop.baseline` accepts an
  optional `--runtime {mlx,torch}`, dispatches the base-only greedy engine by identity, and
  records the backend in the evidence and the committed artifact.
- **Ambiguity is refused, never defaulted.** On a machine with both runtimes and no `--runtime`,
  the door exits 2 by name (`AmbiguousBackend`); a named runtime that is not installed exits 2
  (`NoBackend`). The MLX-only command line is unchanged.
- **The honest-number chain composes.** A measured baseline artifact carrying a Torch backend is
  accepted by `read_baseline_document` and by `honest_report` for a same-series promotion record
  — proven on a stub-engine fixture, never a real run.
- **No number is claimed.** The unit's success is the door, the provenance, the refusals and the
  composition test. The measurement itself is unspent, and the unit says so in
  `CHANGELOG.md`, `docs/STATUS.md` and the `CLAUDE.md` status block.

## User personas & scenarios

- **The operator (the author).** After the § 10.25 probe settles the base, runs the § 3
  measurement once on the Mac, under Torch/MPS, with an untrained 8B checkpoint. The door must
  tell them which runtime it used and refuse an ambiguous machine rather than guess.
- **The P4 report writer.** Reads the committed baseline artifact as the "before" of the delta.
  It needs the series identity it already keys on, the counts, and the runtime provenance; it
  must not have to know which engine produced the bytes.
- **A future reviewer.** Must be able to see from the tree that the runtime is recorded but is
  not the series key, and that a same-base runtime change is a future amendment, not a silent
  second measurement.

## Requirements

### Must-have

1. **`baseline.engine_for(name)` — the runtime dispatch, by identity.**
   - `engine_for(MLX)` returns the module-level `baseline_engine` (the gate's own factory), so
     the existing stub seam and `test_measure_composes_the_gate_and_report_by_identity`
     (`baseline.tool_versions is ledger.tool_versions`) keep working.
   - `engine_for(TORCH)` imports `whetstone.loop.torch_runtime` **inside the function** and
     returns `torch_runtime.torch_gate_engine`; no torch import at `baseline.py` module scope.
   - `backend.family(name)` is the one classifier; a `torch-*` legacy name maps to Torch.
2. **`measure` resolves and records the runtime.**
   - New keyword-only `prefer: str | None = None` and `backend: Backend | None = None`; the
     `engine` default becomes `None`.
   - Resolution: if `engine is None`, `backend = backend or detect(prefer=prefer)` and
     `engine = engine_for(backend.name)`. If an injected `engine` arrives without a `backend`,
     raise a named `ValueError` (the direct API must say what it stands for; the CLI never does
     this).
   - Detection happens **after** the measured-once guard and before any generation, so a
     refused same-series run loads no runtime.
   - `BaselineMeasurement` carries the `Backend`; `disclosure()` prints a `runtime:` line with
     name, library, version, device and precision.
3. **The evidence records the backend and the runtime's own tool versions.**
   - `write_evidence(..., backend: Backend)` writes `backend.recorded()` and calls
     `tool_versions(backend=backend)` by identity, so a Torch measurement never records
     `mlx-lm` (defect #33, `backend.py:17-20`, `ledger.py:364-388`).
   - The evidence is `whetstone-baseline-run/1`; `backend` is a recorded addition, not a schema
     bump (the `Backend.precision` precedent, 0.24.0).
   - `_read_evidence` requires and validates the block (strings for name/library/version/device,
     an integer memory, a string-or-null precision, a known `backend.family` name); a malformed
     or missing block is refused by name.
4. **The committed artifact carries the backend, sealed.**
   - `build_baseline_report` gains `backend: Mapping[str, Any] | None`; a **measured** document
     requires it and writes it, a declaration carries none. The field is added to
     `_BASELINE_DIGESTED_FIELDS` and `_BASELINE_KNOWN_FIELDS`, so a hand-edited backend breaks
     the seal.
   - `render_artifact` reads the evidence's backend and passes it by identity;
     `read_baseline_document` returns it on `BaselineDocument` and requires it for a measured
     document.
   - **Backward compatibility:** the committed declaration
     `reports/baseline-measurement/report.json` has no `backend` and still reads; the digest
     function includes only keys present, so its seal is unchanged and the file is not
     rewritten.
5. **The module door gains an optional `--runtime {mlx,torch}`.**
   - `choices` are `backend.MLX`/`backend.TORCH`; `--runtime` is in `_measure_flags`, so a render
     mode beside it is refused with the usage code.
   - `_measure_main` passes `prefer=args.runtime` and no engine; `measure` detects and records.
   - `REFUSALS` gains `NoBackend` and `AmbiguousBackend`, so both exit 2 with the named reason.
   - No `--runtime` and exactly one installed runtime uses it (the MLX-only sheet is unchanged);
     no flag and two installed is refused.
6. **The series key does not move.** `SeriesIdentity` stays `(repo_id, revision,
   heldout_digest)`; `read_series_identity` ignores the backend. A same-base artifact measured
   under another runtime is refused by the measured-once guard. This is the confirmed decision,
   documented as a limitation: the runtime is provenance, and a same-base runtime change is a
   Type 1 amendment before it is measured.
7. **The honest-number chain composes.** `tests/loop/test_honest_report_door.py` builds a
   measured baseline artifact with a Torch backend and asserts the clean render exits 0 against
   a same-series promotion record. No change to `honest_report.py` is expected.

### Should-have

- The `runtime:` disclosure line, pinned by a test, so the operator sees the record the artifact
  will carry.
- A test that the committed declaration reads with `backend is None` and `measured is False` —
  the compatibility half of requirement 4.
- A test that two artifacts with the same base/held-out digest but different backends share a
  series identity (the limitation, asserted rather than implied).

### Nice-to-have

- A Torch baseline operator sheet. Deferred: § 12 puts the measurement last, and the base may
  move after the § 10.25 probe; a sheet written now can go stale before it is run.

## Technical considerations

- **Composition, never re-decision:** `gate.baseline_engine`, `torch_runtime.torch_gate_engine`,
  `backend.detect`/`family`/`Backend.recorded`, `ledger.tool_versions`,
  `bakeoff_report.build_baseline_report`/`write_baseline_report` and `report.tally` are imported
  by identity; each `is` is asserted where it matters.
- **The reward path is untouched.** Nothing under `src/whetstone/verify/`, `tasks/`, `patch.py`
  or `attribution.py` moves; the door scores through the same `_score_side` and `_retry_side`.
- **Local and private.** The measurement reads local weights and the local corpus; the evidence
  stays under the gitignored `runs/<run-id>/`; only counts, verdicts and hashes are written.
- **Determinism.** The evidence and artifact remain byte-deterministic for a given runtime,
  `--recorded-on`, checkpoint and seed; the backend block is a property of the runtime, not the
  clock.
- **No `whetstone` subcommand.** This stays a module door; the partition guard's documented-edge
  count is untouched.

## Data model

- `whetstone-baseline-run/1` (gitignored evidence): adds
  `backend: {name, library, version, device, device_memory_bytes, precision}`. Required for a
  measured evidence; no schema bump.
- `whetstone-baseline/1` (committed artifact): adds the same `backend` block to a **measured**
  document. It is in the digested and known field sets. The declaration state carries none. No
  schema bump; the loader reads the old declaration unchanged.
- `SeriesIdentity` (in code, not a document): unchanged — base repo id, base revision, held-out
  document digest.

## Risks & open questions

- **The public-task hang.** The baseline scores source A, the public task that produced the 8B
  night's MPS out-of-memory and corrupted-attention-mask hang
  (`docs/planning/torch-mps-series/finding.md:42-61`). The door does not fix the runtime; the
  operator's measurement carries the same risk, and the write-up says so.
- **The base may move.** If the § 10.25 probe returns NO-GO and the base changes, the 8B/Torch
  baseline becomes a separate, unspent series. The door is durable; the measurement is not. This
  is the reason the unit stops at the door.
- **`detect()` imports the runtime to describe it.** That happens after the measured-once guard
  and before generation. A runtime whose import breaks after `find_spec` succeeds would
  traceback; that is a pre-existing `backend.describe` risk, not a new one.
- **The MLX evidence changes shape.** A measured MLX baseline now carries a backend block and a
  filtered `tool_versions` (the actual installed version, not the pinned constant). No measured
  baseline exists, so no figure moves; the declaration is untouched.
- **The series-key limitation is deliberate.** A same-base MLX/Torch pair is one series and the
  second measurement is refused. If that becomes wrong, it is a Type 1 amendment, never a silent
  second measurement.
- **Open question (deferred):** should the operator sheet for the 8B/Torch baseline be added
  now or after the § 10.25 probe? The PRD says after; the door's `--help` and the existing
  runbook-guard pattern are enough until then.

## Out of scope

- Spending the § 3 measurement, or any real weights/GPU run.
- A Torch baseline/headline operator sheet or a new `reports/` home.
- Changing the series key, § 3's protocol, the held-out split, `K`, `R`, or the reward path.
- Fixing the MPS hang, or changing the § 10.25 repair probe.
- Any `whetstone` CLI subcommand, dashboard or product surface.

## Aspect decomposition

1. **`measurement-door`** — the runtime dispatch, the backend record in evidence and artifact,
   the optional `--runtime`, the refusals, the disclosure and the honest-report composition
   test. One code slice, test-first.
2. **`write-up`** — `CHANGELOG.md`, `docs/STATUS.md`, the `CLAUDE.md` status block, and a dated
   correction to the `torch-mps-series` follow-up note. No code.

Sequencing: `measurement-door` → `write-up`.

## Self-critique (prd-generator pass)

- 🔴 **Resolved before planning:** the runtime is not in the series key (confirmed by the user);
  the measurement is not spent (confirmed); the flag is optional like `run --night` (confirmed).
  The three decisions that could have changed the architecture are fixed.
- 🟡 **Artifact backward compatibility is the sharp edge.** The loader refuses unknown fields, so
  adding `backend` to the known set is mandatory; the digest function's `if key in document`
  filter is what keeps the existing declaration's seal valid. The plan must watch the
  declaration test fail first (by removing the field from the known set) before it passes.
- 🟡 **The existing CLI tests rely on monkeypatching `baseline.baseline_engine`.** The dispatch
  must return the module global at call time, and the test suite gets an autouse `detect` fixture
  so no test loads a real runtime. A dispatch that binds the engine at import time would break
  the seam silently; the identity test pins it.
- 🟡 **`tool_versions` is easy to forget.** The evidence's versions block is the one place the
  runtime's own version reaches the committed artifact. The plan makes
  `write_evidence(..., backend=...)` the only writer and adds a test that a Torch evidence names
  `torch`, not `mlx-lm`.
- 🟢 **No new number, no new threshold, no new comparison.** The only figures are the existing
  baseline counts, unchanged.

**The question I would want answered before greenlighting this:** if the § 10.25 probe returns
NO-GO and the main series moves to another base, is a Torch baseline door still worth shipping
now? The answer this PRD commits to is yes: the door is the only way *any* Torch series can
spend its § 3 baseline, and the base-specific part (the untrained checkpoint and the
measurement) is precisely what stays unspent. A door that only works for the 8B would be the
wrong shape; a door that works for every Torch base is the durable half.
