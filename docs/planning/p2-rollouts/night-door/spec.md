# Spec — night-door (aspect 3 of p2-rollouts)

**PRD:** `../prd.md`. **Branch:** `feat/p2-rollouts/aliz`. This aspect ships the door the roadmap
names: `whetstone run --night` producing `runs/<id>/` with a ledger **and** a candidate under
`checkpoints/<id>/` (`docs/ROADMAP.md:399-400`), plus the runbook and its guard. It composes
aspects `sampling` and `sft`; it builds no new generation, selection, or training logic itself.

## Problem slice and user outcome

The loop exists only as parts. This aspect makes the operator's one command: run a night, get a
runs directory, a ledger, and a candidate — with the same exit-code contract, the same locality
rules, and the same control discipline the harness already enforces. The user outcome is the
first thing the project has ever shipped that *runs a night*.

## In-scope requirements

1. **`whetstone run --night` subcommand** in `cli.py` (a guarded root) that is **thin dispatch
   only**: the `mlx_lm`-reaching body lives in `src/whetstone/loop/` (`run.py:7-13` precedent). The
   command's flags mirror the hardened contract (per `docs/planning/larger-base-arm/runbook.md:120-149`):
   tasks, public, pool, funnel, weights, out, workspace, timeout, recorded-on, dev-subset ×5,
   retries, journal, transcript, plus the loop's own run-seed flag. `--recorded-on` is an input,
   never the clock (the arms' rule).
2. **Run layout:** `runs/<id>/` (journal, ledger, dataset, transcript) and `checkpoints/<id>/`
   (adapter + provenance), both gitignored roots (`.gitignore:20-24`); the transcript is refused
   under `--out` (`run.py:1009-1030`). The run's writable paths are absolute (the 54bea44 / runbook
   correction: a relative workspace dies `UNPROVISIONED`).
3. **Exit codes:** the existing 0/1/2/3 contract (`cli.py:53-74`) — a night that produced a
   candidate exits 0; one with zero strict-PASS rollouts exits per the verdict reduction
   (dataset empty is a valid, *published* outcome, never a silent success); usage/refusal errors are
   2; `UNVERIFIED`-dominant runs reduce per the ported verdict semantics (`verdict.py:8-15`) and
   never exit 0.
4. **Composition and discipline:** the night composes aspects 1–2 by identity — the frozen contract
   seal (`ContractChanged` aborts, `run.py:140-147`), the control arm (`sweep.rankable` refusal,
   `sweep.py:160-183`), the weights re-hash (`weights.py:184-230`) — and runs the SFT only if the
   capacity probe (aspect 2) has passed for this machine+base in this run's own record chain.
5. **Runbook and guard:** `docs/planning/p2-rollouts/night-door/runbook.md` — the operator's sheet
   (absolute paths, worktree/CWD rule, halt conditions, killed-run restart, post-run chain), held
   by a guard on the `tests/test_larger_base_runbook_guards.py` precedent (pins the flag surface to
   the parser, absolute writable paths, exactly one worktree, the declared dev ids, the
   zero-strict-PASS handling).
6. **Disclosure in output:** the night prints/records the unverified rate and coverage beside the
   training-set size and the checkpoint digest (`docs/ROADMAP.md:430-435`).

## Out-of-scope boundaries

- No report home, no figures about a model published (P4; the run's own gitignored artifacts are
  the only home of its counts).
- No promotion gate, no eval of the candidate (P3).
- No change to `src/whetstone/verify/`, `patch.py`, `attribution.py`, `src/whetstone/tasks/`.
- The door does not run the night itself — it makes the command runnable; the operator executes it
  (the arms' pattern: machinery shipped, GPU pass operator-run).

## Acceptance criteria (testable)

- AC1: `whetstone run --night --help` exits 0 and the parser surface equals the runbook's flags
  (guard test); an unknown flag is a 2.
- AC2: with a stub generator and a fixture corpus, `run --night` produces `runs/<id>/` containing
  journal, ledger, and dataset, and — with a strict-PASS fixture — `checkpoints/<id>/` with a
  re-verifiable provenance (aspects 1–2 tested through the door end-to-end).
- AC3: the zero-strict-PASS path exits nonzero-or-UNVERIFIED-reduced, writes no checkpoint, and the
  ledger states the empty outcome.
- AC4: the transcript/locality refusals hold through the door (`--transcript` under `--out` refused).
- AC5: a relative `--workspace`/`--out` is refused by the guard (the runbook's command is absolute).
- AC6: the runbook is executable from disk and its guard suite is green; `uv run pytest` green;
  ruff and mypy over `src/` green.

## Dependencies and sequencing

- Depends on aspects `sampling` and `sft` (both must be merged to the branch first), and on the
  pinned local weights (machine-level, primary checkout).
- Sequence: subcommand + parser → run composition → runbook → guard (watched failing first against
  a deliberately wrong stub runbook, the repo's pattern).
- Feeds: the operator's first night run (post-merge), then P3.

## Open questions / risks

- The 32B at ~6 tok/s with k=8 over 61 private tasks is a long night; the runbook's halt
  conditions and killed-run restart must let a killed night resume from its journal rather than
  restart from zero (journal `Step` records, `journal.py:55-74`).
- Whether the night should also expose a `--probe` short-circuit (small k, declared) — recommended,
  mirroring `run.py:598-610`, so the operator can validate the whole chain cheaply before the full
  night. Decide in the plan.