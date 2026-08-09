# Spec — `contract-report` (aspect 3 of `p2-format-hardening`)

**Boundary:** the generation contract's new fields, the new report directory, the one-home
guard amendment (twice, argued), the `PREREGISTRATION.md` § 10.4 Type 2 amendment, and the
declared dev subset. Depends on `diffcheck` + `retry-loop` (the constants they publish).

## Problem slice

The hardened contract must be distinguishable from the baseline *programmatically* — two
contracts, told apart by their published fields — and its figures must be published without
creating a second home for any baseline figure. The pre-registration must be amended the
Type 2 way: disclosures only, no closed § 7 item, no placeholder, no proportion.

## Decisions

- **C1 — `GenerationContract` gains the retry fields.** `report.py:175-199` gains
  `retry_budget: int`, `retry_template_sha256: str`, `diagnosis_vocabulary_version: str`,
  and — the yield-probe D9 fix (`p2-yield-probe/prd.md:124-128`) — `retrieval: str`
  (`"oracle"`, today's hard-coded `_ORACLE_DISCLOSURE`, `report.py:67-75`). Retrieval stays
  oracle; the field is the machine-readability fix. The baseline's published artifacts are
  static and are not regenerated; any test that constructs a `GenerationContract` with the
  five-field shape is updated in this aspect.
- **C2 — New report directory, argued.** `reports/format-hardening/` with
  `report.md`/`report.json`/`cost.json`. The one-home guard — asserted twice, in lock-step:
  `tests/bakeoff/test_report.py:961-994` (the file list) and
  `tests/bakeoff/test_transcript_locality.py:73-101` (the opposite-sign copy) — is amended
  **only** with the D6 argument in each docstring: the two directories measure different
  generation contracts and are declared non-comparable, so neither is a competing home for
  the same figure. A silent list extension is refused. If the argument cannot be made
  honestly at review, the fallback (PRD D4) is a second labelled contract section inside
  `reports/baseline/`.
- **C3 — § 10.4, Type 2.** `PREREGISTRATION.md` gains § 10.4 per `p2-yield-probe/prd.md:119-122`:
  disclosures (the new contract: retry budget, retry template hash, diagnosis vocabulary;
  the non-comparability of the two reports), a row in the log table (`:308-312`), nothing
  above § 10 edited, closes no § 7 item (not § 7.3), no placeholder, no proportion in any
  spelling (`tests/test_docs.py:554-604`).
- **C4 — Dev subset.** The arm declares 3–5 source-B task ids via `--dev-subset` (existing
  mechanism, `run.py:910-929`); `ScoredDevSubset` (`report.py:139-145, 385-397`) refuses
  any leak. The ids are chosen during `measured-arm`'s pre-analysis (tasks whose prompts
  were used while tuning the retry template) and named in the run's provenance block. This
  aspect provides the mechanism checks; the ids arrive with the arm.

## In-scope requirements

- `src/whetstone/bakeoff/report.py` — the four new contract fields; the report writer
  supports a second directory with both-arms content (both contracts stated, each with its
  fields, the non-comparability sentence `report.py:92-95`, per-arm token-spend disclosure,
  and a pointer to the gitignored breakdowns as their home — never restating classifier
  counts, `finding.md:89-92`).
- The two one-home guard tests amended with the D6 argument (watched failing first: the
  guard fails against the new directory before the docstring argument lands).
- `PREREGISTRATION.md` § 10.4 + log-table row.
- `CHANGELOG.md` + `CLAUDE.md` status updates (in the shipping commit, per repo rule).
- Tests: contract-shape tests updated; a test that a `GenerationContract` under the
  baseline report (committed JSON) still parses under the new dataclass (the committed
  artifacts must not break `report.json` readers); the § 10.4 guards green.

## Acceptance criteria (tests written first)

1. `uv run pytest tests/bakeoff/test_report.py tests/bakeoff/test_transcript_locality.py
   tests/test_docs.py` green.
2. `tests/bakeoff/test_report.py:961`'s list includes `reports/format-hardening/`'s three
   artifacts AND its docstring carries the D6 argument; the opposite-sign copy in
   `test_transcript_locality.py:73-101` agrees in lock-step.
3. `PREREGISTRATION.md` § 10.4 exists with a log-table row; `tests/test_docs.py`'s
   placeholder/proportion guards pass.
4. A `GenerationContract` round-trips with the new fields; the committed baseline
   `report.json` parses unchanged.
5. No figure is restated: the new report's md/json contain no count that lives in
   `reports/baseline/`'s files (asserted by the amended guard's list + the pointer rule).

## Out of scope

- The validator/retry constants themselves — aspects 1–2.
- The arm run, the pre-analysis, the breakdown — aspect `measured-arm`.
- Any change to `verify/`, `patch.py`, `attribution.py`.
- Closing § 7.3 or setting any threshold.

## Open questions / risks

- Whether `retrieval` as a field alters the baseline report's JSON shape — it must not (the
  committed artifacts are static; the field is populated only for new contracts, or defaults
  to `"oracle"` with the baseline sidecar unregenerated — pin this in the plan).
- The dev-subset ids are named by `measured-arm`; if they land late, the mechanism tests
  here use synthetic ids.
