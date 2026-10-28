# Understanding — torch-baseline-door

**Unit:** `feat/torch-baseline-door/aliz` · **Written:** 2026-10-28 · **Source:** the inline brief
in `docs/planning/_card/issue.md`, from the `whetstone-next` pick and the `torch-mps-series`
PRD's own follow-up note.

## What the work is really asking

The § 3 baseline is the "before" of every P4 delta: the untrained base scored on the held-out
split, by the same STRICT verifier, measured once and re-measured never
(`PREREGISTRATION.md:121-138`, `docs/ROADMAP.md:504-514`). The door that does it exists
(`python -m whetstone.loop.baseline`), but it binds `gate.baseline_engine`, and that engine
imports `mlx_lm` unconditionally (`src/whetstone/loop/gate.py:560-599`). The main series is now
`Qwen/Qwen3-8B` on Torch/PEFT/MPS (`PREREGISTRATION.md` § 10.21), so **the current series has no
way to produce its own baseline**. The § 3 artifact on disk is a declaration —
`reports/baseline-measurement/report.json` says `"measured": false` — and
`honest_report.py:61-62` refuses to render a delta against it.

This unit gives the baseline door a Torch runtime: an optional `--runtime {mlx,torch}` that
dispatches the base-only greedy engine by identity, records the backend in the evidence and the
committed artifact, and refuses an ambiguous or unavailable runtime by name. It does **not**
spend the measurement. The baseline is the one-shot number, and § 12 deliberately puts it last so
a base that changes cannot strand it (`docs/ROADMAP.md:684-693`); the § 10.25 probe is still the
next measurement that decides whether the 8B base survives.

## Current code, precisely

- **The door.** `baseline.measure` composes the gate's own `_score_side` / `_retry_side` /
  `_heldout_tasks` by identity and scores the untrained checkpoint over the held-out membership
  plus source A (`baseline.py:538-666`). Its engine argument is the module-level
  `baseline_engine = gate_module.baseline_engine` (`baseline.py:107-111`), and the CLI passes it
  explicitly (`baseline.py:1316`).
- **The engine.** `gate.baseline_engine` loads `mlx_lm.utils.load(adapter_path=None)` and wraps
  it in `_CheckpointGenerator` with `sampler_for(1)` (`gate.py:560-599`). The Torch sibling,
  `torch_runtime.torch_gate_engine`, already handles an untrained checkpoint by loading the base
  alone and decodes greedily with `do_sample=False` (`torch_runtime.py:508-531`). It is the
  right engine by construction.
- **The evidence.** `write_evidence` writes `whetstone-baseline-run/1` with base, checkpoint,
  held-out digest, rollouts, retries, counts and `tool_versions` — hashes and verdicts, never
  contents (`baseline.py:669-739`). The `_read_evidence` render side validates the fields it
  reads, fail-closed (`baseline.py:764-883`).
- **The artifact.** `whetstone-baseline/1` is written by `bakeoff.report.build_baseline_report`
  / `write_baseline_report`; the loader `read_baseline_document` validates the schema, known
  fields, counts, series and seal (`baseline.py:382-495`). The known/digested field sets live in
  `report.py:1171-1199`.
- **The series key.** `SeriesIdentity` is exactly `(repo_id, revision, heldout_digest)`
  (`baseline.py:162-188`), and the measured-once guard compares that identity
  (`baseline.py:620-640`, `:977-993`). The runtime is **not** part of it, by the confirmed
  decision: it is provenance, not the key.
- **The honest-number chain.** `honest_report` reads the baseline document fail-closed, checks
  the promotion record and both checkpoints against the baseline's series, and refuses a
  declaration-state baseline by name (`honest_report.py:1-20`, `:61-62`). A measured,
  series-matching baseline is what unblocks the render.

## Runtime facts the unit builds on

- `backend.detect(prefer=...)` = `choose` (imports nothing; `NoBackend` when the named runtime is
  absent, `AmbiguousBackend` when two are installed and none named) then `describe` (imports the
  winner to record library, version, device, memory and precision)
  (`backend.py:182-239`).
- `Backend.recorded()` writes the seven-field JSON block (`backend.py:125-139`); `family(name)`
  maps a recorded name to `MLX`/`TORCH` and tolerates the legacy `torch-*` spelling
  (`backend.py:142-159`).
- `ledger.tool_versions(backend=...)` drops every known runtime distribution and names the one
  that ran at its real version — the fix for a Torch run recording `mlx-lm` unconditionally
  (`ledger.py:364-388`, `backend.py:17-20`). The baseline evidence currently calls
  `tool_versions()` with no backend, so a Torch measurement would repeat defect #33 unless the
  backend is passed.
- The night's `--runtime` is the pattern to copy: `choices=("mlx","torch")`, `prefer=args.runtime`,
  and the ambiguity/unavailability refusals are the backend module's own
  (`cli.py:497-508`, `:1224`).

## Core-loop placement

**④ the signed morning report / the honest number**, with **③ the never-regress gate** as its
consumer: the baseline is the gate's and the report's "before". The reward (①) is untouched —
the door still scores through the STRICT verifier and `report.tally` by identity, no new
judgement, no loosened check. `UNVERIFIED` remains in the denominator and is never a win. Local
and private (⑤) is unchanged: the measurement reads the user's local weights and corpus, and
the evidence stays in the gitignored `runs/` home.

## Affected areas

- `src/whetstone/loop/baseline.py`: `measure` (engine/backend resolution), `write_evidence`
  (backend + filtered tool versions), `render_artifact` and the evidence reader (backend
  required for a measured document), `read_baseline_document` / `BaselineDocument` (optional
  backend for a declaration, required for a measured artifact), `disclosure` (print the
  runtime), `build_parser` (`--runtime`), `_measure_flags`, `REFUSALS`, `__all__`.
- `src/whetstone/bakeoff/report.py`: `build_baseline_report` (backend parameter), the digested
  and known field sets, the writer's measured-state check.
- Tests: `tests/loop/test_baseline_door.py` (dispatch, record, refusals, parser, privacy walk),
  `tests/loop/test_baseline_document.py` (round-trip, seal, declaration compatibility),
  `tests/bakeoff/test_baseline_report.py` (writer field set), `tests/loop/test_honest_report_door.py`
  (a Torch baseline renders the honest number), `tests/test_baseline_runbook_guards.py` (the
  existing MLX sheet still parses; `--runtime` is optional).
- Docs: this directory, `CHANGELOG.md`, `docs/STATUS.md`, the `CLAUDE.md` status block, and a
  dated correction to the `torch-mps-series` follow-up note.

## Contradictions surfaced — flag, do not paper over

1. **The door's own docstring says every `mlx` import is function-local and the engine is "the
   gate's own".** Adding a second engine family does not break that rule if the `torch_runtime`
   import stays inside `engine_for`; it does break the unstated assumption that there is one
   engine. The module's docstring and the `baseline_engine` comment must say "the MLX engine"
   rather than "the engine".
2. **The baseline evidence records `tool_versions()` unconditionally.** On a Torch measurement
   that block would name `mlx-lm`, the exact inaccuracy #33 fixed for the ledger. The unit must
   pass the backend; this is not optional polish.
3. **The runtime is not in the series key.** The confirmed decision says provenance only. A
   same base measured under MLX and Torch is therefore one series, and the second measurement is
   refused. That is the correct § 3 reading today (one base, one split, one anchor), and a future
   same-base runtime change is a Type 1 amendment, never a silent second measurement.
4. **The committed declaration has no backend.** The loader must keep reading
   `reports/baseline-measurement/report.json` exactly as it is; the new measured documents
   require a backend, the declaration does not.
5. **§ 12 says the baseline is last.** The unit builds the door only; the 8B/Torch measurement is
   deferred until the § 10.25 probe settles the base. Building the door now cannot strand a
   spent measurement, and it is the only code change that lets the series ever spend one.

## Open questions / risks

- **The public-task hang.** The baseline scores source A (`pallets__flask-4045`), the task that
  produced the 8B night's MPS out-of-memory and corrupted-mask hang
  (`docs/planning/torch-mps-series/finding.md:42-61`). The door cannot fix the runtime; the
  operator's measurement carries the same risk, and the unit says so rather than implying the
  door makes the run safe.
- **`detect()` imports the runtime to describe it.** The runtime is loaded after the
  measured-once guard and before any generation, so a refused same-series run loads nothing. A
  runtime whose import is broken after `find_spec` succeeds would traceback; that is a
  pre-existing `backend.describe` risk, not this unit's.
- **The MLX evidence changes shape.** A measured MLX baseline now carries a backend block and a
  filtered `tool_versions`; no measured baseline exists, so no figure moves. The declaration is
  untouched.
