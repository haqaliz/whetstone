# Understanding — honest-number-report

## What this work is really asking

P4 slice 2 (`docs/ROADMAP.md:647-651`, § 12 — the next unit, decided 2026-08-26): the report
that turns the pre-registered shape into a published document — for **both sources**,
baseline score, final score, delta, `N_baseline`, `N_final`, coverage, and the full
provenance block (`PREREGISTRATION.md` § 4 shape: `+a of b held-out tasks (baseline c of b,
final d of b) / coverage e of b / N: f at baseline, g at final`; source A per-instance, never
a rate; both sources always together; zero or negative deltas published as plainly as
positive ones), **plus P4's exit criterion 3** — the harness is public and reproduces the
reported number from the pinned inputs. Buildable while the operator chain proceeds (§ 7.3
amendment → baseline spend → night #1 → night #2 → first gated evaluation → P4 report →
finding); the report render itself is the last operator step, so the machinery and the
runbook land now and the figures land later.

## What the dig established (three agents, mapped `report.py` / `comparison.py` / `baseline.py` / `ledger.py` / `gate.py` / `heldout.py` / `PREREGISTRATION.md` / the guards)

### The pattern to follow (proven, five writers)

- All writers live in `src/whetstone/bakeoff/report.py` as `build_<name>_report` /
  `write_<name>_report` pairs (frozen dataclass with `markdown`/`payload`/`cost`; writer
  returns `tuple[Path, Path, Path]`; deterministic pure functions — "same records and same
  pinned inputs → byte-identical output across runs and processes", asserted in-process and
  across subprocesses under `PYTHONHASHSEED` 0/1). Shared helpers `_row`, `_over`,
  `_contract_fields`, `_contract_block`, `_counts`, `tally` must be reused **by identity**
  (monkeypatch test proves resolution from the module).
- The closest template is the baseline writer (`build_baseline_report`, schema
  `whetstone-baseline/1`, report.py:1202-1319) — declaration-only state ("**No count is
  measured here: the baseline has not run.**", written by the writer, never hand-typed),
  digest-sealed document, locality discipline (counts/verdicts/provenance, never contents).
- **The P4 writer must be a NEW writer, never an extension of `build_report`** —
  `test_the_p4_headline_skeleton_is_refused` (test_report.py:323) forbids the bake-off report
  from instantiating the § 4 shape.
- Doors are module doors (`python -m ...`), not `cli.py` subcommands: `comparison.py` holds
  three mutually exclusive `--render-*` modes; refusals happen before anything is written,
  exit 2, `_assert_refused` also asserts `not out.exists()`. The baseline's own door
  (`loop/baseline.py`, `main` at 1358) is the runbook-guarded precedent.
- **No `cli.py` / partition-guard change is needed** for a module door: the writer lives in
  exempt `bakeoff`, the door lives in exempt `loop`; `test_reward_path_scope_is_partitioned`
  pins exactly three function-local edges (`night`, `gate`, `check_leakage`) and a fourth
  (`whetstone report --last-night`) belongs to the morning-report unit, not this one.

### The "before" is ready; the "after" has one gap

- **Baseline (ready):** `loop/baseline.py` `read_baseline_document(path) -> BaselineDocument`
  is the fail-closed loader, docstring verbatim: "what the P4 report writer will read"
  (baseline.py:316-325). Refuses: unreadable, wrong schema, unknown fields, declaration
  state (`measured: false` — **the P4 writer must refuse a delta against an unmeasured
  baseline**), unreadable series, per-count validation, `weaker_wins > denominator`, and the
  digest seal (hand edits refused). Carries `sides` (source-b/source-a six-field counts:
  denominator/solved/unverified/covered/failed/weaker_wins), `n` (`count`/`denominator`/
  `sentence` = `_N_SENTENCE` by identity), `series` (repo_id/revision/heldout_digest),
  `base` (§ 7.3-open sentence), `retries`, `evidence` (schema + digest pointer), `tool_versions`.
- **Final score + coverage (ready):** the promotion record (`whetstone-promotion/1`,
  `runs/promotions/<id>.json`) carries `sides.candidate.<source>` = the six SideCounts
  (denominator/solved/unverified/covered/failed/status), `decision` (exit/denominator/
  solved_new/solved_old/regressed/unverified/detail), `heldout.document_digest`, re-hashed
  candidate/incumbent digests, `retry_count` (R by identity), retries, unverified_after_retries,
  tool_versions. **BUT the record has no reader today** — gate.py:97 docstring: "checked on
  read by nobody yet — the record is written, never read back by this module — and named so
  a later reader has one answer to 'what shape is this file'". The later reader is this unit:
  a fail-closed `read_promotion_record` must arrive with it.
- **`N_final` — THE GAP (found by the dig, not in the brief):** nothing on disk records the
  final side's `weaker_wins`. `SideCounts` has no `weaker_wins` field, the gate writes no
  journals and no per-rollout evidence. The pre-registered shape `N: f at baseline, g at
  final` cannot render without it. Resolution: extend the promotion record — `SideCounts`
  gains `weaker_wins` (the gate's `_counts(rollouts, tasks)` has the Rollout records at hand;
  `weaker_wins` is `report.tally`'s definition by identity), schema bump documented. The
  record is written-never-read, so no reader breaks; the schema's own docstring anticipated
  this reader. This is a small, in-scope gate change (gate.py is not an AC2-pinned path).
- **Delta semantics:** `PREREGISTRATION.md:92-94` — "a delta computed across a change to any
  pinned input is not a delta". The report must verify series agreement: the promotion
  record's `heldout.document_digest` and the candidate checkpoint's base identity (from its
  provenance, via `sft.verify_checkpoint` by identity — the trained checkpoint carries
  `base: {repo_id, revision}`) must equal the baseline series. Mismatch → refused by name
  (the delta is the document; a non-delta renders nothing). The loop's generation contract
  differs in `sampler` (seeded categorical vs greedy) — recorded in every run ledger, and
  CLAUDE.md pre-commits: "the amendment belongs to whichever later unit first publishes a
  figure measured under it" — **that later unit is this one** (the § 10.9 Type 2 amendment,
  before any figure exists).

### The one-home guard (sixth move) and the disjointness exception

- The guard is two lock-step 15-artifact lists (test_report.py:1941-1957;
  test_transcript_locality.py:134-150) + `_ALL_HOMES` (test_report.py:1322-1327) +
  figures-level disjointness scans (`\b(\d+) of (\d+)\b` over all homes' artifacts) +
  planted-overlap controls. A new directory is admitted by: the argument first, in both
  docstrings; declaration-only artifacts committed first (writer-generated, no `N of M`);
  both lists grow by three lines; `_ALL_HOMES` gains the name; own disjointness + planted
  controls.
- **The exception this home needs:** the pre-registered shape REQUIRES the P4 report to
  render the baseline's counts (`baseline c of b`) — a figure that also lives in
  `reports/baseline-measurement/`. The disjointness rule ("a figure quoted twice is a figure
  that can disagree with itself") must admit figures that arrived **through the fail-closed
  loader by identity** (the report renders exactly the artifact's counts, asserted byte-equal
  to the artifact's own figures — it cannot disagree with itself because it IS the artifact's
  figure), while still refusing figures from the other four homes (`baseline`,
  `format-hardening`, `easier-stratum`, `larger-base`). This is the "reads as 'before' by
  identity" argument the card's caveat names.
- The report home itself: a **new directory** (the delta/final series is a new published
  series under the loop's contract; `reports/baseline-measurement/` stays the sealed § 3
  anchor with its measured-once render guard). Proposed name `reports/honest-number/`,
  schema `whetstone-honest-number/1` (or `whetstone-p4-report/1` — PRD decides), with the
  § 10.9 Type 2 amendment committed before any figure.

### The harness-reproduces-the-number check (P4 exit criterion 3)

- The gate records counts, not rollouts, so reproduction is asserted at the **count level**:
  the report is a pure, deterministic function of the two sealed evidence documents (baseline
  artifact via fail-closed loader; promotion record via a new fail-closed reader) + pinned
  provenance; byte-identical across invocations and processes; the promotion record's
  `sides.candidate` counts are re-verified consistent (solved + failed + unverified ==
  denominator; unverified stays in the denominator). Rollout-level re-derivation is the
  gate's scoring seam, out of scope here — stated, not blurred.
- A zero/negative delta, or an `UNVERIFIED` promotion-record decision, is a **publishable
  outcome** — the report renders it plainly (P4 has no pivot signal).

## Ambiguities / open questions (for the interview)

1. **N_final source**: extend the promotion record with `weaker_wins` (recommended — the
   schema anticipated this reader) vs a separate evidence document.
2. **The report's home**: new `reports/honest-number/` directory (recommended) + § 10.9 Type
   2 amendment in this unit (before any figure) vs extending the baseline home.
3. **Delta-series mismatch**: refuse by name (recommended — the delta is the document) vs
   render with the non-comparability sentence.
4. **Reproducibility scope**: count-level purity + consistency assertion (recommended) vs
   rollout-level re-scoring (out of scope — would re-run the machine).

## Guardrail placement

- Core loop element: ④ signed morning report (the honest number is its substrate; the
  morning report itself is a separate follow-on unit, per `docs/ROADMAP.md:657-661`).
- The reward stays execution-grounded: this unit writes documents, never a reward; nothing on
  the reward path (`src/whetstone/verify/`, `tasks/`, `patch.py`, `attribution.py`) is
  touched — AC2 pins hold byte-identical.
- `UNVERIFIED` is never a win: an `UNVERIFIED` gate decision renders as `UNVERIFIED` (never
  promoted, never a delta that reads as a win), per the promotion record's own `decision`.
- Nothing leaves the box: the report renders local evidence; no egress.
- No figure about a model anywhere except the report's own home: declaration-only until the
  operator chain completes; `PREREGISTRATION.md` gains no proportion in any spelling.