# Spec — baseline-report (aspect 3 of baseline-measurement)

**PRD:** `../prd.md`. **Branch:** `feat/baseline-measurement/aliz`. This aspect is the
committed home of the § 3 baseline's score — the artifact the P4 report writer will read as
the "before" of every delta.

## Problem slice and user outcome

`PREREGISTRATION.md` § 3 requires the baseline score be **committed** — "measured once,
re-measured never", with provenance beside it. The measurement door (aspect 2) produces the
evidence (gitignored `runs/<id>/`); nothing yet writes the committed artifact, and the
one-home guard would fail the build the moment a fifth directory appears under `reports/`.
The user outcome: `reports/baseline-measurement/` holds the three-artifact shape
(`report.md`/`report.json`/`cost.json`, schema `whetstone-baseline/1`) — declaration-only
until the operator spends the measurement, then rendered by a report door from the evidence,
and readable by a fail-closed loader that a later P4 report writer composes.

## In-scope requirements

1. **The deterministic pure writer** in `src/whetstone/bakeoff/report.py` (the home of every
   report writer — `build_stratum_report`/`write_stratum_report`, `report.py:713-857`, is the
   template, with `_row`, `_over`, `tally`, `_counts`, `_contract_fields`, `_contract_block`
   reused **by identity**, never copied):
   - `build_baseline_report(*, series: SeriesIdentity, heldout_tally: Tally,
     public_tally: Tally, retries: Sequence[RetryOutcome], retry_count: int, evidence_digest:
     str, base: Mapping[str, str], recorded_on: str, tool_versions: Mapping[str, str]) ->
     BaselineReport` — pure: no clock, no ledger, no filesystem beyond the inputs; the
     `recorded_on` and the digests are inputs.
   - The document (schema `whetstone-baseline/1`): `schema`, `recorded_on`, `series`
     (checkpoint digest + held-out document digest — the aspect-2 identity), `base`
     (`{repo_id, revision}` — the pinned input, with the § 7.3-open sentence stated:
     "the base is recorded as this series' pinned input; PREREGISTRATION.md § 7.3 stays
     open"), `sides: {source-b: {denominator, solved, unverified, covered, failed,
     weaker_wins}, source-a: {…}}` (the `Tally` fields, both sources always present),
     `n: {count, denominator, sentence}` (the `_N_SENTENCE` by identity), `retries:
     {retry_count, spent, tasks: [{task_id, before, after, retries_used}]}`,
     `evidence: {run_id?, digest}` (pointer, never contents), `tool_versions`,
     `non_comparable: True` + the sentence naming the four existing homes and what this is
     (the § 3 anchor — never a figure restated from another home).
   - `write_baseline_report(document, into) -> tuple[Path, Path, Path]` — the
     three-artifact shape (report.md/report.json/cost.json), `indent=2, sort_keys=True`,
     trailing newline; cost.json carries `recorded_on` and the token/generation spend from
     the evidence if present, else the declaration shape.
   - **Declaration-only state**: `build_baseline_report(..., measured=False)` renders
     "**No count is measured here: the baseline has not run.**" with no counts, no contract
     fields, no `N of M` figure in any of the three artifacts (the
     `test_the_larger_base_declaration_carries_no_count_and_no_contract` pattern,
     `test_report.py:1475-1525`).
2. **The fail-closed loader** `read_baseline_document(path) -> BaselineDocument` in
   **`src/whetstone/loop/baseline.py`** (not `report.py`: `bakeoff.report` cannot import
   `loop.baseline` — the loop imports the report, so the loader lives beside its own
   `read_series_identity`, composing it **by identity** and importing the schema/digest
   constants from `bakeoff.report` by identity, the established loop→bakeoff direction) —
   the series fields refused exactly as the door refuses them, plus the full document
   checks: wrong/missing schema, unknown fields, missing `sides` fields, counts not
   integers, a negative count, `weaker_wins` over its own denominator, both sources present
   — each refused by name. The loader is the read side of the measured-once discipline: a
   hand-edited document that changes a count is refused rather than trusted (a document
   digest seals the payload, the heldout/stratum pattern — `document_digest_of` style:
   digest over the digested fields, mismatch refused by name).
3. **The one-home guard moves a fifth time, on the changed-series argument**: a new pinned
   series (the § 3 baseline — a different task set: the 12 held-out + source A, and a
   different role: the anchor, not a probe arm), so:
   - the exact-file list in `tests/bakeoff/test_transcript_locality.py:122-135` gains
     `reports/baseline-measurement/{cost.json,report.json,report.md}`;
   - both docstrings (that file's and `tests/bakeoff/test_report.py:1453`'s copy) gain the
     fifth move's argument — a silent list extension remains refused;
   - the disjointness scans in `tests/bakeoff/test_report.py` (e.g. `:1319-1350`) now scan
     **all seven** artifacts per side; a `k of 12` baseline figure collides with no existing
     figure (existing denominators: 1, 20, 62, 63, 64, 189, 299, 300);
   - the planted-overlap controls (`:1353-1384`, `:1843`) are extended and re-proven able to
     fail against the new home.
4. **The report door**: a `--render` mode on the `python -m whetstone.loop.baseline` door
   (mutually exclusive with measuring; the runbook's post-run chain): reads the evidence
   document (`whetstone-baseline-run/1`, fail-closed by name — a missing or schema-invalid
   evidence is refused, never rendered from nothing), reads the checkpoint provenance for the
   base identity, and writes the artifact via the writer. The render path refuses a
   gitignored `--out` by name (the aspect-2 posture) and refuses when the artifact already
   exists at `--out` (the same-series refusal by identity — the measured-once discipline
   holds on the render side too: a rendered baseline is not re-rendered).

## Out-of-scope boundaries

- The P4 report writer (final score + delta + both `N`s) — a later slice; this aspect only
  anchors the "before".
- Any change to the gate, the reward path, `cli.py`, or the aspect-2 door's measure path.
- Closing `PREREGISTRATION.md` § 7.3 (the artifact states the base as this series' pinned
  input and says § 7.3 stays open).
- A § 10 amendment: none is made by this unit — the baseline is pre-authorized by § 3, not a
  new series requiring a Type 2 disclosure (the one-home guard's docstrings carry the
  argument instead).

## Acceptance criteria (test-first; each refusal watched failing first)

1. `build_baseline_report` is pure and deterministic: identical inputs → byte-identical
   artifacts; `recorded_on` is an input, never the clock.
2. The measured document carries both sources over their own denominators, `N` with the
   `_N_SENTENCE`, the series identity, the base identity with the § 7.3-open sentence, the
   retry facts, the evidence pointer (digest only), and the non-comparability sentence —
   no figure from another home is restated.
3. The declaration-only state carries no count in any spelling (`\d+ of \d+` absent from all
   three artifacts), no contract fields, and the "No count is measured here" sentence —
   generated by the writer, never hand-typed.
4. `read_baseline_document` refuses: missing file, unreadable JSON, wrong schema, unknown
   field, missing/non-integer/negative counts, a `weaker_wins` over its own denominator, a
   missing source, and a hand-edited document whose digest does not seal the payload — each
   by name; and its series read is aspect 2's `read_series_identity` by identity (asserted
   `is`).
5. The one-home guard: the file list and both docstrings gain the fifth move; the
   disjointness scans include the new home; the planted-overlap controls fail on a planted
   overlap (re-proven able to fail).
6. The render door: renders the three artifacts from a valid evidence document; refuses a
   missing/schema-invalid evidence by name; refuses a gitignored `--out`; refuses when the
   artifact already exists (same series); renders the declaration when told the baseline has
   not run.
7. The AC2 pins and the partition guard hold (no `cli.py` change; `report.py` is in
   `bakeoff/`, editable).

## Dependencies and sequencing

Aspect 3 of 4 (after `measurement-door`, before `measurement-run`). Consumes by identity:
aspect 2's `read_series_identity`/`SeriesIdentity`/`BaselineAlreadyMeasured` and the
`whetstone-baseline-run/1` evidence schema; `report.tally`/`_N_SENTENCE`/`_over`/`_row`/
`_counts`/`_contract_fields`/`_contract_block`. The runbook (aspect 4) scripts the render
door's invocation.

## Open questions / risks

- **The evidence digest**: the artifact points at the evidence by digest (sha256 of the
  evidence document's bytes), never by contents — the locality discipline, stated in the
  artifact itself.
- **The document digest's field set** must be declared in one place (the `_DIGESTED_FIELDS`
  pattern, `heldout.py:201-210`) so the loader and the writer cannot disagree about what is
  sealed.
- **The § 7.3 sentence is in the artifact's own words** — written by the writer, asserted by
  a test to contain "§ 7.3" and "stays open"; the runbook (aspect 4) restates the same
  sentence, so both are pinned.
- **The series identity is the base identity, never the checkpoint digest** — corrected
  2026-08-27: an untrained checkpoint records no files, so its digest is `_digest_of(())`,
  identical for every untrained base whatever the `repo_id`/`revision`, and a guard keyed
  on it could not tell two bases apart — a changed base revision (§ 3's legitimate new
  series, `PREREGISTRATION.md:133-135`) would be refused as same-series. The series key is
  exactly `(repo_id, revision, heldout_digest)`; the artifact's `series` block carries
  those three and the `base` block carries only the § 7.3-open sentence (the redundant
  repo_id/revision dropped).