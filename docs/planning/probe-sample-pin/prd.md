# PRD — probe-sample-pin

**Unit:** `feat/probe-sample-pin/aliz`. **Source:** inline brief, `docs/planning/_card/issue.md`.
**Understanding:** `docs/planning/probe-sample-pin/understanding.md`. **Status:** small follow-on
to `probe-backend-pin` and `torch-mps-series`; no number is measured.

## Problem statement

The § 10.25 repair probe is the only unrun measurement in the repository
(`PREREGISTRATION.md:1319-1358`). It is a 16-private-task + 1-public-task probe at `K = 16`
(**272 draws**), with a pre-committed GO iff at least one draw is strict-`PASS`. Two things stand
between the operator and that measurement:

1. **The sheet runs a different sample.** The Torch/MPS sheet's probe block passes `--probe 2`
   (`docs/planning/torch-mps-series/night-door/runbook.md:145`), and its guard holds it there
   (`tests/test_torch_mps_runbook_guards.py:242`). It was a cheap chain check inherited from the
   § 10.20 sheet; under § 10.25 it is the wrong sample.
2. **The door cannot see the sample.** `whetstone check-probe` reads the control fold, seed map,
   `sampling.K`, the held-out digest and the backend pins, but never the ledger's declared
   sample size (`src/whetstone/loop/check_probe.py:155-162`). A 2-task probe and a 16-task probe
   both pass, and the sheet's "proceeds iff" sentence (`runbook.md:194-197`) states the harness
   rule, not § 10.25's yield GO.

The result is the failure class the repository has already paid for: a sheet that is "ready" but
does not run the pre-registered experiment (`docs/ROADMAP.md:744-749`).

## Goals & success metrics

- `whetstone check-probe --probe N` returns exit 0 only when the ledger's `task_set.probe` is
  exactly `N`; a mismatch is a named exit-1 violation; with no pin the decision and output are
  unchanged; a full night remains the existing exit-2 refusal.
- The Torch/MPS sheet's probe block runs `--probe 16`, its `check-probe` block passes
  `--probe 16`, and the sheet states both decisions: the command's harness rule and § 10.25's
  GO (at least one strict-`PASS` of 272).
- `PREREGISTRATION.md` § 10.26 names the 16 ids and discloses the 4 oracle-budget-excluded
  tasks, without changing § 10.25's sample or GO rule.
- `uv run pytest`, `uv run ruff check .` and `uv run mypy src/` exit 0. No GPU run is part of
  this unit.

## Requirements

### Must-have

1. **A sample-size pin in `run_check`.** Keyword-only `probe: int | None = None`. When passed:
   - the ledger's declared `task_set.probe` must equal it;
   - a mismatch returns `proceed=False` with a violation naming the recorded and pinned values;
   - a pin is reported in `ProbeReport.pins` as `("probe", "<n>")`, first in declaration order;
   - a pin can only add a violation — it never relaxes the fold, seed map, budget, held-out
     digest or backend checks.
2. **The backend checks keep their own enable switch.** `pins` is currently the switch for the
   backend block (`check_probe.py:238`). Split `backend_pins` (runtime/device/precision) from the
   reported `pins`, so `--probe` alone does not demand a recorded backend.
3. **The full-night contract is unchanged.** A ledger whose `task_set.probe` is `None` or not an
   int stays `NotAProbe` → exit 2; a `/2` ledger with no `probe` is refused the same way. Only a
   *recorded probe of another size* is the new exit-1 violation.
4. **The CLI names the flag.** `whetstone check-probe --probe <n>` (optional, `type=int`), passed
   through to `run_check`; the helper text states the mismatch/refusal split; the exact
   flag-surface test grows by exactly this flag.
5. **The sheet is the measurement.** The probe block runs `--probe 16`; the check-probe block
   passes `--probe 16`; the night block still carries no `--probe`. The sheet states the 272
   draws and the 16-task sample, and separates the two decisions:
   - **harness:** control `PASS` on every draw, non-empty seed map, `draws == sampling.K`,
     held-out digest, backend pins — what `check-probe` decides;
   - **yield:** GO iff at least one of the 272 draws is strict-`PASS` — what § 10.25 decides.
   `check-probe` exit 0 is not the GO; a zero yield is a NO-GO even at exit 0.
6. **The stale halt text is corrected.** The "the next response is to raise `K`" sentence
   (`runbook.md:335-336`) and the earlier raise-`K` note (`:271-273`) are replaced with § 10.25's
   rule: a NO-GO returns the lever to a human, never to a loosened verifier. `K` is already 16
   and the 8B night at `K = 16` produced zero; the finding says raising `K` alone is not
   supported (`finding.md:72`).
7. **The repair description matches the code.** The sheet's `:53-54` still describes the § 10.23
   generic repair ("the first prompt plus the verdict, never the test output"). The shipped
   prompt carries the first unpassed declared node id and its junit outcome (§ 10.25,
   `src/whetstone/bakeoff/retry.py:102-126`); the sheet says what the code does, and the guard
   pins it.
8. **§ 10.26 names the sample.** Append a Type 1 amendment naming the 16 ids (15 `donor-b-*` +
   `donor-a-10476d50e5e8`), the roots order, the dev ids, the held-out document and the 272
   draws; disclose that 4 of the 16 are oracle-budget-excluded and their 64 draws are expected
   `NO_ORACLE`, counted as unverified. It introduces no threshold, does not edit § 10.25, and
   states no count has been measured.
9. **The guards hold it.** `tests/test_torch_mps_runbook_guards.py` pins the new
   `--probe 16`, the roots order, the 272/16-task statement, the two-decision sentences and the
   corrected halt text; `tests/test_docs.py` pins § 10.26 and its ids against the committed
   corpus. The stale `night-sheet/spec.md` gets a dated supersession note.

### Should-have

- The `check-probe` description and disclosure name the sample pin beside the backend pins, so
  the operator sees `probe: 16` and `pins: probe=16` in the same block.
- A test that a matching probe pin proceeds on a `/2` ledger with no backend block, proving the
  split switch.

### Nice-to-have

- A `--probe` alias on `run --night`? No: `--probe N` already exists there; the unit does not
  touch the night door.

## Technical considerations

- **The ledger already carries the size.** `TaskSet.probe: int | None` is written by the night
  and sealed in `whetstone-run/3` (`ledger.py:160-161,425-430`). No schema bump.
- **The sample is positional.** `night.run_night` applies the dev overlay, the held-out
  exclusion, then `private_tasks[:probe]` (`night.py:301-347`); the ledger records the size, not
  the ids. § 10.26 names the ids; the sheet guard derives them from the committed
  `tasks/local-ledger.json` + `tasks/heldout/source-b.json` + the five dev ids.
- **Four sample tasks are unscorable.** `donor-b-45740535725b`, `donor-b-bffecd967c60`,
  `donor-b-d900ada906a3` and `donor-a-10476d50e5e8` are in the held-out document's `excluded`
  map. Their 64 draws are likely `NO_ORACLE`; they stay in the denominator, never dropped.
- **No reward/gate movement.** The change is a read-only document check plus a sheet and a
  pre-registration amendment. It cannot promote, train or publish anything.
- **The sheet guard forbids a third door block** (`tests/test_torch_mps_runbook_guards.py:14,234-237`).
  The 16-task probe replaces the 2-task probe; it is not added beside it.

## Risks & open questions

- **The pin is a size check, not an identity check.** `--probe 16` cannot prove *which* 16 ran;
  § 10.26 and the sheet guard pin the roots order and the ids, but a corpus change before the
  probe still shifts the sample. This is disclosed, not solved. Adding the ids to the ledger
  would be a `whetstone-run/4` schema change and is out of scope.
- **The sample's 4 `NO_ORACLE` tasks.** § 10.25's "roughly sixteen near-misses" is read against
  evaluable draws; the raw 272 includes 64 draws that cannot produce a completion. The amendment
  discloses this; the GO rule does not change.
- **`check-probe` exit 0 is not the measurement's GO.** The command's exits are the night-door
  contract; the yield GO is a ledger read. The sheet must say so, or an operator will treat a
  green harness check as a GO.
- **The `--probe 2` sheet was deliberate.** This is a premise change, not a typo fix: the old
  block was a cheap chain check. The guard must be edited with the sheet, never deleted.
- **The amendment timing.** § 10.26 must be committed before the probe runs. The unit commits it
  in the same PR as the code, before the operator's run; the probe remains unrun.

## Out of scope

- Running the § 10.25 probe; changing its base, revision, runtime, precision, budget,
  held-out document, repair vocabulary or GO rule.
- The reward path, the gate rule and exits, the corpus, `K`, `R`, or any `reports/` home.
- Adding the sample ids to the ledger (`whetstone-run/4`).
- A second probe or a smoke-check beside the measurement.
- Fixing the MPS hang (#86) or the patch-representation wall (#64).

## Aspect decomposition

1. **`sample-amendment`** — § 10.26 + the log row + the `test_docs.py` guard + the
   `night-sheet/spec.md` supersession note. Must land first: the sample is named before the
   probe.
2. **`probe-pin`** — `check_probe.py`, `cli.py`, `tests/loop/test_check_probe{,_cli}.py`.
3. **`sheet-alignment`** — the Torch/MPS runbook + `tests/test_torch_mps_runbook_guards.py`.

The write-up (`CHANGELOG.md`, `docs/STATUS.md`, `CLAUDE.md`) is part of the last aspect.

---

## Self-critique (prd-generator workflow)

**🟡 Problem definition.** The problem is real and cited, but the unit is deliberately narrow: it
does not make the probe *succeed*, only *runnable as pre-registered*. That is the correct slice,
but a reader could mistake this for progress on the zero. The PRD says no number is measured; the
write-up must repeat it.

**🟡 Success metrics.** The metrics are command exits and artifacts, not a measured yield. That
is honest for a plumbing unit, but it means the unit cannot claim any movement on the honest
number. The § 10.26 amendment and the sheet are the only evidence that the measurement is now
the pre-registered one.

**🟡 Sample identity.** Naming the ids in a new amendment is the user's choice, but it is a
second pin on top of § 10.25's positional rule. If a future operator reorders the roots, the
amendment and the sheet disagree; the guard must make that a test failure, not a silent rerun.
The deeper fix (record the ids in the ledger) is explicitly out of scope.

**🟢 Scope.** The out-of-scope list is explicit and matches the guardrails: no reward, gate,
corpus, held-out, `K`, `R`, GPU or egress.

**The question I would want answered before greenlighting this:** if the probe returns a GO, the
next step is a ~40 h night on a machine that has already lost nights to MPS hangs — is the
supervisor + resume path enough, or does this unit need to prove a resumed 272-draw probe
completes before the sheet is called ready? This PRD says the latter is the operator's run, not
this unit's, and that is the largest remaining assumption.
