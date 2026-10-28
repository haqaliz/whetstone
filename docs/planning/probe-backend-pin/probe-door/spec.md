# Spec — probe-door (probe-backend-pin)

**PRD:** `../prd.md`. **Branch:** `feat/probe-backend-pin/aliz`.

## Problem slice

`run_check` (`check_probe.py:147-232`) decides a probe's GO/NO-GO without comparing the runtime
the ledger records. The § 10.25 probe is a Torch/MPS `float16` run; the door must be able to
refuse a run that is not. The user outcome: `whetstone check-probe --runtime torch --device mps
--precision float16` exits 0 only when the ledger's backend matches, 1 on a named mismatch, and
the sheet uses it.

## In-scope

1. `run_check(run, *, heldout=None, runtime=None, device=None, precision=None)`; any non-`None`
   pin activates the backend check after the held-out pin:
   - `backend` must be a mapping; otherwise a violation;
   - `family(recorded_name)` vs `family(runtime)`; an unknown recorded name is a violation;
   - `device`/`precision` exact.
2. `ProbeReport.backend`, `ProbeReport.pins` (tuple of `(name, value)`), `_report` populates both
   from the payload and the passed pins; every existing call keeps the defaults.
3. `disclosure` prints `pins: ...` (when any) and `backend: <name> (<library> <version>, <device>,
   <precision>)` (when recorded), before the violation line.
4. CLI: `--runtime` choices `mlx|torch`, `--device`, `--precision`; pass-through; help text
   states each can only add a violation.
5. The Torch sheet's check-probe block gains the three flags; the guard's read-back test is
   updated to say the door pins it too and still assert the read-back.
6. Tests: matching pin proceeds; each mismatch names both values; a missing backend under a pin
   is a violation; a v2 ledger with no pin still decides; the disclosure line; the CLI surface
   and pass-through; the sheet guard.

## Out-of-scope

The probe itself, the § 10.25 inputs, the reward, the gate, the corpus, `K`, `R`.

## Acceptance (test-first)

- `run_check` with matching pins returns `proceed=True`, `report.backend["name"] == "torch"`,
  `report.pins == (("runtime","torch"),("device","mps"),("precision","float16"))`.
- Each of the three mismatches returns `proceed=False` and names the recorded and pinned values.
- A ledger with no backend block and any pin is a violation, not a refusal/traceback.
- No pin: every existing check-probe test passes unchanged.
- The CLI exposes exactly `--run`, `--heldout`, `--runtime`, `--device`, `--precision`, `--help`;
  the Torch sheet's flags are all in the parser; the sheet guard asserts the new sentence and
  the read-back.
- Full focused suite green; `mypy`/`ruff` clean.

## Sequencing

One code slice, then the sheet/guard and the write-up.
