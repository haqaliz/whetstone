# Card — honest-number-report

## Brief

P4 slice 2 (`docs/ROADMAP.md:647-651`, § 12 — the next unit named by the launch path): the
honest-number report writer, plus P4 exit criterion 3 (the harness is public and reproduces
the reported number from the pinned inputs). Build a pure, deterministic report writer and a
report-door mode rendering, for BOTH sources together: baseline score (read from the
committed `reports/baseline-measurement/` artifact through its fail-closed loader **by
identity**), final score, delta, `N_baseline`, `N_final`, coverage, and the full provenance
block (pinned seeds, model revision, task set, tool versions) — in the `PREREGISTRATION.md`
§ 4 shape (source A per-instance, never a rate; every rate carries its denominator; zero or
negative deltas published as plainly as positive ones; both sources always published
together). Reuse `report.py`'s shared helpers (`_row`, `_over`, `tally`,
`_contract_fields`, `_contract_block`, `_counts`) by identity, on the four existing writers'
precedent; the report door follows the `comparison.py` three-mode precedent
(`--render-report` / `--render-stratum-report` / `--render-larger-base-report`), with the
same missing-journal / unproven-control / zero-arms refusals by name.

Acceptance criteria, written first (repo is test-first):

1. The door renders the three-artifact shape (report.md/report.json/cost.json) only when an
   arm has run: missing journals, an unproven control, zero arms, or a missing baseline
   artifact are refused by name — never a half-truth render.
2. The writer is pure and deterministic: byte-identical output across invocations, and the
   report's figures re-derive from the pinned inputs (harness-reproduces-the-number check).
3. Source A appears per-instance (never a rate — one eligible instance of 300), source B over
   its own denominator, both always together.
4. Baseline score is read from the committed baseline artifact, never recomputed or restated
   from another home.
5. The one-home guard admits the report's home on the argued series basis (a § 10 amendment
   before any figure, if it is a new series); a silent home-list extension is refused.
6. The AC2 pins (`src/whetstone/verify/`, `patch.py`, `attribution.py`) and the reward-path
   partition guard hold; `PREREGISTRATION.md` gains no proportion in any spelling.
7. A runbook scripts the post-run render (the report door is part of the operator's post-run
   chain, behind the first gated evaluation).

Caveats the dig must meet: no real runs exist yet (the night has never run, the gate has
never run on real checkpoints, the baseline number is unspent) — so the writer and the
reproducibility check are proven on fixture/recorded evidence first, exactly as the gate's
three exits were. The report's home must be argued on the one-home guard's series argument
(same held-out split and base as the baseline series — either the baseline home reads as
"before" by identity or a new home is declared on the changed-series argument), and the § 7.3
Type 1 amendment and the operator chain (baseline spend → two nights → first gated eval) stay
outside this unit. The reward path must stay byte-untouched.

## Source

Inline brief (no GitHub issue — slug id, `feat honest-number-report`), handed off from the
`whetstone-next` session (2026-08-27).