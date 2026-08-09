# Understanding — format-hardening-measurement

**Dig run:** 2026-08-09 · three parallel agents (machinery, report/guards, docs-side).
**Card:** `docs/planning/_card/issue.md` · **Branch:** `feat/format-hardening-measurement/aliz`.

## What this work really is

Finish the `p2-format-hardening` measured-arm aspect (plan Phases 3–4). All the machinery
aspects 1–3 built is shipped and tested; the slice's **deliverable — the measured before/after
cause breakdown — is unspent** because the arm itself has not run and the post-run analysis
tooling does not exist yet. This unit builds the deterministic, offline analysis chain that the
runbook's post-run section names but does not provide ("assembled from the autopsy documents by
the Phase 3 comparison tooling", `runbook.md:136-138`), plus the report-assembly door that will
render `reports/format-hardening/` for real, plus the finding and the status-block updates.

## What the dig established

- **The arm has NOT run** (`runs/format-hardening-arm-evidence/` and `runs/format-hardening-arm/`
  absent in the primary). The unit must build for both cases: tooling verified on synthetic
  fixtures (the pre-analysis pattern), real render the moment the operator's run lands.
- **No comparison module exists.** `preanalysis.analyze_document` (preanalysis.py:335) is the
  ready-made strict read of `whetstone-autopsy/1` documents; `preanalysis.combine` (preanalysis.py:352)
  is the summation shape across runs. `diffcheck.trigger_of_cause` (diffcheck.py:76-97) is the
  trigger mapping, to be imported **by identity**, never reimplemented.
- **The stored runs carry everything the report needs.** `runs/arm-a/` and `runs/budget-2048/`
  hold `journal.jsonl` (per-`(candidate, task)` rollout records with `outcome`,
  `verdict_kinds`, `generation_seconds` — enough to derive per-candidate `Tally`s and summed
  token spend; `journal.py` already parses this shape), `transcript.jsonl`, `attribution.json`.
  They hold **no** `report.json`/`cost.json` — the journal is the per-run record of record.
- **The report writer is shipped but has no production caller.** `build_contract_comparison`
  (report.py:577) + `write_comparison` (report.py:673) write exactly
  `reports/format-hardening/{report.md,report.json,cost.json}`; `ContractArm` (report.py:288)
  takes `name, contract, tallies, generation_seconds`. This unit's Phase-4 door is its first
  caller.
- **The one-home guards are names-only.** `test_report.py:1353` and
  `test_transcript_locality.py:73` pin the exact 6-file list under `reports/`; *replacing the
  contents* of the three format-hardening files breaks nothing, *adding a fourth file* breaks
  both. The ceiling (113) therefore can never be committed under `reports/` — it is pointed at
  via `breakdown_home`. The disjointness rule (test_report.py:1259) applies to the synthetic
  document, not the committed one.
- **test_docs.py constrains the docs updates:** no present-tense "no figure about a model"
  claim in `CLAUDE.md`/`CHANGELOG.md` (test_docs.py:248-297); PREREGISTRATION guards are
  satisfied and untouched.
- **A stale claim to fix while the status block is rewritten:** `CLAUDE.md:261` still says
  "No version has been released and there are no tags", but **v0.3.0 is tagged** (`1ebe09c`,
  tag `5d3faf4`).

## Design questions the dig surfaced (for the PRD)

1. **What exactly the comparison tooling reads and asserts.** Proposal: journals (tallies +
   token spend) + autopsy documents (cause breakdowns) + the preanalysis document (ceiling,
   trigger counts); assertions: per-record trigger mapping re-derived via
   `diffcheck.trigger_of_cause` by identity agrees with the preanalysis decisions (contradiction
   reported in the comparison document, never reconciled), and nonzero `mapping_violations` in
   any autopsy document are surfaced, never smoothed.
2. **The comparison output shape.** The runbook names `runs/format-hardening-preanalysis/comparison.md`
   as the home; autopsy/preanalysis write JSON documents. Proposal: both — a schema'd JSON
   document (`whetstone-comparison/1`) and a rendered markdown breakdown, both refused under
   published paths.
3. **The Phase-4 door.** A CLI (`python -m whetstone.bakeoff.comparison` or a sibling) that
   builds the `ContractArm`s from journals + contract sidecars and calls `write_comparison`;
   the before-arms' contracts come from `reports/baseline/report.json`'s `generation_contract`
   block (backfilled by `GenerationContract.parse`); the after-arm's from its own run report.
4. **Whether the report renders when the arm hasn't run.** It stays the committed declaration;
   the door is tested on synthetic arms so the post-run render is one command.
5. **Placement on the core loop:** element ② (nightly improvement loop) is the loop this
   measurement gates; the work itself changes no loop element — it is measurement machinery in
   the harness, offline and deterministic, with `verify/`, `patch.py`, `attribution.py` frozen.
   The reward stays execution-grounded (untouched); nothing leaves the box (journals, autopsy
   documents, and the run's own evidence are all local).

## Open questions for the user

- Scope of the CLAUDE.md stale-claim fix (proposed: fold into the status-block rewrite).
- Whether the comparison tooling should be a new `comparison.py` module or an extension of
  `preanalysis.py` (proposed: new sibling module, the pre-analysis pattern).

## Contradictions / flags

- `CLAUDE.md:261` ("no tags") vs the v0.3.0 tag — stale prose, flagged, fix folded into the
  status-block rewrite.
- `test_report.py:961` cited in test_transcript_locality.py:82 and contract-report/spec.md:62
  is stale (the guard moved to line 1353) — prose-only, no test depends on the citation.
- The runbook's `comparison.md` naming vs the JSON-document precedent (question 2 above).
