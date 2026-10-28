# Understanding — probe-backend-pin

**Unit:** `feat/probe-backend-pin/aliz` · **Written:** 2026-10-29 · **Source:**
`docs/planning/_card/issue.md`, from the `torch-mps-series` PRD's N1 follow-up.

## What the work is really asking

The § 10.25 probe is the next measurement (`docs/planning/torch-mps-series/finding.md:114-125`):
272 draws on `Qwen/Qwen3-8B`, Torch/MPS `float16`, with a pre-committed GO iff at least one
strict-`PASS`. Its door is `whetstone check-probe`, which reads the sealed ledger and decides
from the control fold, the seed map, `sampling.K` and (with `--heldout`) the committed split
(`src/whetstone/loop/check_probe.py:1-31`). It does **not** read the runtime. The ledger does
record it (`ledger.py:405`, `"backend": ledger.backend.recorded()`), and the Torch sheet reads it
back by eye (`docs/planning/torch-mps-series/night-door/runbook.md:88-90`). The operator's eye is
not an exit code.

This unit adds optional `--runtime`, `--device` and `--precision` pins to the door. They can only
add a violation; with no pins the decision is byte-for-byte the one it makes today.

## Current code, precisely

- `run_check(run, *, heldout=None)` (`check_probe.py:147-232`) reads the ledger through
  `ledger.read` by identity, validates the probe identity and completeness, then returns the
  first named violation among: budget ≠ `sampling.K`, a held-out digest mismatch/missing record,
  a non-`PASS` harness, an empty seed map.
- `ProbeReport` (`:120-145`) carries `proceed`, `violation`, `draws`, `draws_recorded`,
  `sources`, `probe`, `seeds`; `_report` is the only constructor.
- `disclosure` (`:236-253`) prints the decision and counts; the violation line when refused.
- The CLI parser is at `cli.py:703-740`; the handler `run_check_probe_cli` (`:1341-1370`) maps
  `REFUSALS` to exit 2 and returns `PASS_EXIT`/`FAIL_EXIT`.
- The ledger writes `backend.recorded()` (`ledger.py:405`); `backend.family` classifies a
  recorded name and tolerates `torch-*` (`backend.py:142-159`). The `whetstone-run/3` schema
  requires the block; the `/2` tolerance path may not carry it.
- The Torch sheet guard asserts the sheet says "check-probe does not pin the backend"
  (`tests/test_torch_mps_runbook_guards.py:453-471`). That premise becomes false here and the
  guard must be updated with the sheet.

## Core-loop placement

**② the nightly improvement loop's evidence** and **③ the gate's inputs**: the probe decision is
the door in front of the repair night. The reward (①) is untouched — the check reads a sealed
document, never executes a task. `UNVERIFIED` is not a new exit; the command still either
answers (0/1) or refuses (2).

## Contradictions / risks

- The pin is only as good as the ledger's record. A `/2` ledger can lack the block; with a pin
  that must be a named violation, not a crash. The v3 reader already refuses a `/3` document
  missing a required field, so the only absence path is the documented v2 tolerance.
- The sheet's read-back stays: the command pin and the operator's read are independent checks.
  The guard's sentence changes, not the read-back.
- The § 10.25 amendment already pins the runtime; this unit adds no measurement input and needs
  no amendment.

## Affected areas

`src/whetstone/loop/check_probe.py` (signature, report, pin comparison, disclosure),
`src/whetstone/cli.py` (three flags, handler), `tests/loop/test_check_probe.py`,
`tests/loop/test_check_probe_cli.py`, `tests/test_torch_mps_runbook_guards.py`,
`docs/planning/torch-mps-series/night-door/runbook.md` (the check-probe block and the read-back
sentence), plus the write-up.
