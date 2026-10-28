# feat torch-baseline-door

**Source:** inline brief, from the `whetstone-next` pick on 2026-10-28 and the
`torch-mps-series` PRD's own follow-up note.

## Brief

The § 3 baseline door cannot measure the current main series. `python -m
whetstone.loop.baseline` binds `gate.baseline_engine`, which loads MLX only
(`src/whetstone/loop/gate.py:560-599`), while `PREREGISTRATION.md` § 10.20/§ 10.21 pinned the
main series to Qwen3-8B on Torch/MPS. `src/whetstone/loop/honest_report.py:61-62` refuses a
declaration-state baseline, and the only baseline artifact is a declaration
(`reports/baseline-measurement/report.json`, `"measured": false`) — so the P4 honest number
has no anchor for the series that now exists.

Add `--runtime {mlx,torch}` to the baseline measure door, dispatch the base-only greedy engine
by identity (MLX → `baseline_engine`; Torch → `torch_gate_engine` on an untrained checkpoint),
record the backend name/device/precision in the evidence and rendered artifact compatibly with
the existing sealed declaration, and refuse exit 2 by name when both runtimes are installed
with no flag and when the named runtime is unavailable. The MLX-only path stays byte-identical.
No reward, gate, corpus, held-out set, `K`, `R`, or series-key change.

## Acceptance

- Dispatch by identity for both runtimes; no second sampler.
- Both runtime refusals, named, exit 2.
- The backend round-trips through the evidence and the rendered artifact; the existing sealed
  declaration at `reports/baseline-measurement/report.json` still reads.
- A stub-engine end-to-end fixture where `honest_report` accepts the measured baseline for a
  same-series promotion record.
- The full suite green; no number claimed.
- Caveat: the baseline is spent once and the base may move after the § 10.25 probe, so this
  unit builds the door only; the 8B/Torch measurement is the operator's after the probe
  settles the base. The measurement also includes the public task that produced the MPS
  OOM/mask hang (`docs/planning/torch-mps-series/finding.md:42-61`), which this unit does not
  fix.
