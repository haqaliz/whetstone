# Understanding — probe-sample-pin

**Unit:** `feat/probe-sample-pin/aliz` · **Written:** 2026-10-31 · **Source:**
`docs/planning/_card/issue.md`, from the `whetstone-next` pick.

## What the work is really asking

The § 10.25 repair probe is the only unrun measurement in the repository
(`PREREGISTRATION.md:1319-1358`). It is pinned as `whetstone run --night --probe 16 --repair 2`
on the 8B, 16 private + 1 public task at `K = 16` — **272 draws** — with **GO iff at least one
draw is strict-`PASS`**. Everything downstream waits on it: a checkpoint, the first real gate
decision, the § 3 baseline and the P4 honest number.

The Torch/MPS sheet still runs `--probe 2` (`docs/planning/torch-mps-series/night-door/runbook.md:145`),
a cheap harness check it inherited from the § 10.20 sheet, and its guard holds it there
(`tests/test_torch_mps_runbook_guards.py:242`). `whetstone check-probe` has no sample pin: it
reads the control fold, seed map, `sampling.K`, the held-out digest and (since 0.30.0) the
backend, but never the declared sample size (`src/whetstone/loop/check_probe.py:155-162`). So a
2-task probe can print `PROCEED` for a 16-task measurement, and the sheet's "proceeds iff"
sentence (`:194-197`) states the harness rule, not § 10.25's yield GO.

This unit closes the last inch: it makes the declared sample an input to the go/no-go command,
puts the pre-registered sample on the sheet, and states both decisions distinctly.

## Current code, precisely

- `run_check(run, *, heldout=None, runtime=None, device=None, precision=None)`
  (`check_probe.py:155-162`) validates the run, the probe identity, the budget, the held-out
  digest, then the backend pins, then the harness fold and the seed map. `ProbeReport.probe`
  (`:141-142`) already carries the ledger's declared size, but only as a disclosure field.
- `_probe_of` (`:387-402`) raises `NotAProbe` — a **refusal, exit 2** — when `task_set.probe` is
  missing or not an int. A full night is therefore exit 2 today, not a violation.
- `pins` (`:151-152`) is both the reported tuple and the enable switch for the backend checks
  (`:238`). Adding `("probe", ...)` naively would make `--probe` alone demand a backend block.
- The CLI parser (`cli.py:724-791`) exposes `--run`, `--heldout`, `--runtime`, `--device`,
  `--precision`; the handler passes them to `run_check` (`:1443-1449`).
- `TaskSet.probe: int | None` (`ledger.py:160-161`) is written by the night and sealed in
  `whetstone-run/3`; the ledger records the **size**, not the 16 ids. `TaskSet.private` is a
  count (`:146-147`). The per-draw `seeds[].task_id` values are recorded, but with no source
  label, so they are not a clean sample identity.
- The sheet guard parses the two `whetstone run --night` blocks and pins `--probe 2`
  (`tests/test_torch_mps_runbook_guards.py:14,227-246`); it forbids a third door block.
- `tests/test_docs.py:1433-1465` already pins § 10.25's `probe 16`, `272` and `at least one` in
  the pre-registration, but it never reads the sheet.

## The sample, derived from committed records

`load_task_roots` preserves the root order and sorts within each root (`bakeoff/run.py:496-513`,
`tasks/manifest.py:59-70`). `night.run_night` applies the dev overlay, then the held-out
exclusion, then `private_tasks[:probe]` (`night.py:301-347`). With the sheet's `--tasks donor-b`
then `--tasks donor-a`, 5 dev ids and the 12 held-out members, 15 `donor-b-*` survive and the
first `donor-a-*` is `donor-a-10476d50e5e8`:

```
donor-b-0cfbb1590a70  donor-b-0f8651175ef8  donor-b-0fe4582aeac1
donor-b-45740535725b  donor-b-624a42175dda  donor-b-afd096a4b2ea
donor-b-bffecd967c60  donor-b-c3e132b7469b  donor-b-c57246c7841a
donor-b-cc7d3f520f1c  donor-b-ce6425d3101a  donor-b-d900ada906a3
donor-b-dbf19c8009dd  donor-b-ee0841a837c9  donor-b-f589d0e93cc9
donor-a-10476d50e5e8
```

Four of the sixteen — `donor-b-45740535725b`, `donor-b-bffecd967c60`, `donor-b-d900ada906a3`,
`donor-a-10476d50e5e8` — are in `tasks/heldout/source-b.json`'s `excluded` map: their source
files exceed the 80,000-character oracle budget. Their 64 draws are expected `NO_ORACLE`,
counted as unverified, never as failures. No task is dropped or re-drawn: § 10.25's rule is
"the first 16", and changing it would be a different measurement.

## Core-loop placement

**② the nightly improvement loop's evidence**, and the door in front of it. The reward (①) is
untouched: `check-probe` reads a sealed document and never executes a task. No gate rule moves;
`UNVERIFIED` is not a new exit, and a zero-yield probe is a NO-GO, never a win.

## Contradictions surfaced — flag, do not paper over

1. **The card said a full night is exit 1; the code says exit 2.** `_probe_of` raises
   `NotAProbe`, a refusal an operator fixes by pointing at a probe (`check_probe.py:80-86`,
   `tests/loop/test_check_probe.py:132-139`, `tests/loop/test_check_probe_cli.py:73-86`). The
   user chose to keep the existing contract: a **mismatch** is exit 1; a full night stays exit 2.
2. **The sample is under-specified in § 10.25.** It names "the first 16 private tasks" but not
   the roots order, the exclusion order or the ids. It is deterministic only because the sheet
   fixes the roots order and files sort by id. The user chose to append a § 10.26 Type 1
   amendment naming the ids, without changing the sample.
3. **Four of the 16 are known `NO_ORACLE`.** The amendment must disclose this; § 10.25's
   "roughly sixteen near-misses" already reads against evaluable draws, not the raw 272.
4. **The sheet's `--probe 2` was deliberate, not a typo.** It landed 2026-10-20 as a cheap chain
   check (`night-sheet/spec.md:5,19`) before § 10.25 existed. It is stale under § 10.25, and the
   user chose to replace it, not to keep a second probe.
5. **`docs/planning/torch-mps-series/night-sheet/spec.md` is stale** — it pins `--probe 2`, the
   7B candidate and "check-probe does not pin the backend". No test reads it; it needs a dated
   supersession note so a reader cannot follow it.

## Affected areas

`PREREGISTRATION.md` (§ 10.26 + log row), `tests/test_docs.py` (the § 10.26 guard),
`src/whetstone/loop/check_probe.py`, `src/whetstone/cli.py`,
`tests/loop/test_check_probe.py`, `tests/loop/test_check_probe_cli.py`,
`docs/planning/torch-mps-series/night-door/runbook.md`,
`tests/test_torch_mps_runbook_guards.py`,
`docs/planning/torch-mps-series/night-sheet/spec.md` (supersession note),
`CHANGELOG.md`, `docs/STATUS.md`, `CLAUDE.md`.

## Open questions already answered

- Full night under a pin: **keep exit-2 refusal** (user, 2026-10-31).
- Sample identity: **§ 10.26 naming the ids**, sample unchanged (user, 2026-10-31).
- Sheet probe: **replace the 2-task probe with the 16-task measurement** (user, 2026-10-31).
