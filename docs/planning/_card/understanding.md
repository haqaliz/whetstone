# Understanding — probe-decision-gate

**Branch:** `feat/probe-decision-gate/aliz` · **Date:** 2026-09-05

## What the work is really asking

The night-door runbook pre-commits a go/no-go for night #1 — *"the night proceeds iff the
probe completes with the control arm `PASS` on every draw and a non-empty seed map"*
(`docs/planning/p2-rollouts/night-door/runbook.md:78-80`) — and today an operator enforces it
by reading the probe's ledger by eye. This unit turns that pre-commitment into a command, so
the decision is a process exit, never a narrative judgement — against the roadmap's own
exit-criteria principle (`docs/ROADMAP.md:278`). It is the last buildable unit that de-risks
the launch path's most expensive, least certain, least reversible step (the night) and reads
no number. Modeled on `check_leakage` (`src/whetstone/loop/check_leakage.py`).

## What the code actually shows (all verified in this worktree, 2026-09-05)

1. **A probe run writes no checkpoint and a full ledger.** `run_night(..., probe=N)` narrows
   the private source to its first `N` tasks (`night.py:248-249`), writes no checkpoint
   (`night.py:495-500`), and writes `ledger.json`, `dataset.json`, `data/`, and
   `draws/draw-NN.journal.jsonl` + `.transcript.jsonl` (`night.py:291-332`). The ledger
   (`whetstone-run/1`, `ledger.py:47`) carries the three facts the decision needs:
   `task_set.probe` (int iff a probe), `draws_recorded[].harness` (the per-draw control
   fold), and `seeds` (the seed map). Readable fail-closed via `ledger.read`
   (`ledger.py:211-224`, `LedgerUnreadable`) and the deeper typed `morning.read_ledger`
   (`morning.py:279-328`).
2. **The control fold is `harness_status`**: any `BROKEN` → `UNVERIFIED`, no `INTACT` at all
   → `UNVERIFIED`, else `PASS` (`bakeoff/control.py:472-494`). "Control arm PASS on every
   draw" = every `draws_recorded[].harness == "PASS"`. **A real written probe ledger always
   satisfies this**: `rankable` raises `HarnessNotProven` unless every draw's status is PASS
   (`sweep.py:160-183`), and the night then exits `UNVERIFIED_EXIT` (3) with **no ledger**
   (`cli.py:828-830`). So the exit-1 control-violation case is reachable only through a
   doctored ledger or the journals — the adversarial fixture is the point (the
   `check_leakage` digest-swap posture).
3. **The seed-map subtlety is real.** `Applied` seeds are recorded only when `generate()`
   runs (`sampling.py:203-214`); a fully-replayed **resume** re-appends recorded steps
   verbatim (`draws.py:176-179`) and can therefore write a ledger whose `seeds` array is
   empty even though every draw ran under a seed. `_select` already falls back to the pure
   `attempt_seed(run_seed, task_id, attempt)` derivation (`night.py:462-464`,
   `sampling.py:100-119`). The decision gate must define "non-empty seed map" against this:
   recorded-only (strict) or re-derived-on-miss (matching `_select`). This is the unit's
   sharpest open question. The runbook's killed-night restart (same command, same `--run-id`)
   applies to a probe too, so a resumed probe with an empty recorded seed map is not
   hypothetical.
4. **The go/no-go paragraph is NOT guard-pinned.** `tests/test_night_runbook_guards.py`
   contains no reference to "Decision rule", "night proceeds iff", or the
   "Read runs/night-probe/probe-001/ledger.json" sentence — rewriting it breaks nothing. The
   guard DOES pin **exactly two door blocks** (`test_night_runbook_guards.py:175`), so adding
   a check-probe step to the sheet means extending the guard 2 → 3, in the same commit, code
   first. The pins to preserve: two (→ three) door invocations with flags ⊆ `build_parser()`,
   absolute writable paths, exactly one worktree (`feat-p2-rollouts`), `RETAINED`/`EXCLUDED`
   candidate names, the five dev ids, and the prose strings "zero"/"ceiling", "not a halt",
   "raise `K`", "loosen", "Nothing here is published".
5. **CLI subcommand vs module door.** A `whetstone check-probe` subcommand costs a **fifth**
   partition-guard edge: `_DOCUMENTED_EDGES` (`test_reward_path_scope_is_partitioned.py:154-159`),
   the `EXEMPT["loop"]` "exactly FOUR" reason (`:120-147`), the stale "three/four edges"
   docstrings in `cli.py` (`:850-853, 905-906, 938-939`), the module docstring's command list
   (`cli.py:27-37`, guarded by `test_morning_cli.py:212-239`), and the function-local-import
   handler shape (`cli.py:895-924`). A module door (`python -m whetstone.loop.probe_check`,
   the `heldout`/`baseline`/`honest_report` pattern) adds **zero** guard edges — the guard
   walks only guarded roots, never inside the exempt loop package
   (`test_reward_path_scope_is_partitioned.py:435-448`). The card's brief says "modeled on
   `check_leakage`"; `check-leakage` is a CLI subcommand. Decide in the PRD: the runbook is
   the only caller either way.
6. **Exit-code contract for the gate (no fifth code).** 0 = the decision rule holds (proceed
   to the night); 1 = the finding the command exists to report (named violation: a draw whose
   harness is not PASS, or an empty seed map); 2 = refusal an operator can fix (not a probe
   run, unreadable ledger). **No `UNVERIFIED`**: the command reads documents rather than
   running anything ("it either answers or refuses", `cli.py:911-912`). `cli.py:82-93` fixes
   PASS=0 / FAIL=1 / USAGE=2 / UNVERIFIED=3.
7. **No fixture probe directories exist.** Tests build nights at runtime via
   `tests/loop/harness.py` (`corpus`, `pool`, `weights`, `Answers` stub engine) +
   `tests/loop/test_night.py::_night` (`probe=1`, `draws=2`), and hand-build ledgers via
   `run_ledger.Ledger`/`write` (`tests/loop/test_run_ledger.py:53-105`). The decision gate's
   tests need fixture probe run directories — a helper is new code.

## Open questions for the PRD

- **Seed-map semantics on resume.** Recorded-only vs re-derived-on-miss (matching `_select`
  by identity). Strict recorded-only makes a legitimately resumed probe un-runnable;
  re-derivation makes "non-empty" total. Middle path: the runbook forbids *resuming a probe*
  (a killed probe restarts fresh — it is cheap, first-N private tasks) while the gate reads
  recorded-only, which keeps both honest. Recommend deciding this explicitly rather than by
  accident.
- **CLI subcommand vs module door** (§ 5). The partition-guard cost of the CLI is mechanical
  and the house has done it four times; the module door avoids it. The card says "modeled on
  `check_leakage`".
- **Per-draw fold vs per-task detail.** The pre-committed rule's words are the per-draw fold
  (`draws_recorded[].harness`). Reading the journals for per-task `INTACT` detail is stricter
  than the rule and would re-litigate what "control arm PASS" means — recommend the fold,
  with the journals read only to prove each draw actually ran (completeness), never to add a
  bar.
- **Does the gate need a `--heldout`-style second input?** No — it reads one run directory,
  like `check_leakage` reads one run + the heldout doc. Here the probe run is the only input;
  the night's task set is already in the ledger.

## Guardrail placement

- Core-loop element changed: **② nightly improvement loop** — the probe decision gate is the
  door to the night. It is *not* the promotion gate (③): `decide()`, the three exits and the
  retry discipline are untouched.
- Reward stays execution-grounded: the reward path (`src/whetstone/verify/`, `patch.py`,
  `attribution.py`) is untouched; the gate reads evidence documents only.
- `UNVERIFIED` still never a win: the gate has no `UNVERIFIED` exit and promotes nothing; a
  probe that proved nothing already aborts the night at `UNVERIFIED_EXIT` with no ledger
  (`cli.py:828-830`).
- Local/private: reads the gitignored `runs/<id>/`; nothing leaves the box; nothing is
  published. Not redundant with a better base: the pre-committed go/no-go is part of the
  loop's honesty contract, which a stronger base only makes more worth defending.