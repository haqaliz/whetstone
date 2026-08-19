# Understanding — larger-base-arm

## What this work really is

The fork's second arm, and the repo's third operator-executed measurement unit (the pattern:
`measured-arm-run`, `stratum-probe-execution`). The probe ran and published (merged
2026-08-15, PR #13): yield == 0 for every candidate with control intact on the easier
stratum, so the **pre-committed fork rule** (`docs/planning/p2-easier-stratum/prd.md:49-51`)
routes to the larger-base arm — never a looser verifier, never a fourth generation-contract
change. The finding states it directly: "The next unit is the **larger-base arm**"
(`probe-run/finding.md:30-32`).

The code phase is small (runbook + guard + the report home machinery + a § 10 amendment);
the operator phases are the run, the post-run chain, and the finding. The harness needs **no
code change to score a larger candidate**: `--only` matches by substring on repo id
(`run.py:404`), a 32B repo id parses via the existing `_SIZE` regex, weights load from
`provenance.json` by immutable sha, and the hardened contract is already frozen
(`--retries`, budget 2, same templates).

## What was verified (dig, file-cited)

- **The fork rule is a routing rule, not a threshold** (`p2-easier-stratum/prd.md:44-55`):
  yield == 0 with control intact → larger-base arm next. M13 (`prd.md:155-162`) requires the
  finding to state in words whether the axis failed or the premise failed.
- **The probe's M13 read** (`probe-run/finding.md:34-53`): **premise failure, not axis
  failure** — the formatting wall receded, well-formed patches applied, and none turned the
  tests green; "git read it, applied it, and the tests still fail". Residuals for the arm's
  runbook: the 14B's `hunk-count-mismatch` persisted through its retry budget; the 3B's
  `hunk-dies-early`/`no-diff` stayed small. The axis is not the binding constraint, so the
  arm re-tests **the declared source-B set** (the pivot signal's own set,
  `docs/ROADMAP.md:387-389`) — not an even-easier stratum.
- **The candidate exists and is the measured family's next rung.** Verified on Hugging Face
  (2026-08-15): `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`, MLX 4-bit, 18.4 GB weights,
  converted from `Qwen/Qwen2.5-Coder-32B-Instruct`, apache-2.0 — the same family as the
  measured 3B/7B/14B candidates. Machine: **36 GiB RAM** — feasible, but tight; the runbook
  must mandate a `--probe` pass (D7, `run.py:959-1006`) before the full arm, and any capacity
  bound is published as a finding, never worked around (`report.py:1184-1186`; the ROADMAP
  § 10 open question). **There is no capacity gate in the harness** — an unloadable model
  aborts at `MlxGenerator` construction.
- **The dev overlay returns.** The probe's "none declared" state was stratum-scoped: the five
  declared dev ids fell outside the 19-task band, so the harness refused the vacuous
  declaration (`UnknownDevSubset`, `probe-run/finding.md:58-68`). On the **full declared set
  the five ids are members again**, so the arm restores the § 10.4 overlay (`--dev-subset`
  × 5, as the measured-arm runbook carried them). No § 10 amendment is needed for the
  none-declared state itself — it is recorded in the probe finding and the probe report's
  contract fields.
- **A new candidate is a pinned-input change.** Model revision is the first of the five
  pinned inputs (`PREREGISTRATION.md:131-132`; `reports/baseline/report.md:15`), so the arm's
  figures are a **new series**, declared non-comparable to all existing homes — which, per
  the § 10.4/§ 10.5 precedent, means a new report home paired with a **Type 2 § 10.6
  amendment**, pre-committed before the run. No § 10.6 exists today (the document ends at
  § 10.5, line 464).
- **The one-home guard admits a directory only on an argument.** The docstring twins
  (`tests/bakeoff/test_report.py:1453-1515` and
  `tests/bakeoff/test_transcript_locality.py:73-129`) assert the exact nine-artifact list
  under `reports/` (excluding `reports/local/`); a new home needs a third admission ground —
  the **changed-candidate-set argument** (D6 was "different contract", § 10.5 was "changed
  task set") — and the planted-overlap control must prove the extension bites. A silent list
  extension is refused.
- **The runbook refresh pattern is established and explicitly anticipates this unit**:
  `stratum-probe-execution/prd.md:135-136` — "the next refresh extends the stale list". The
  probe sheet is now itself becoming a frozen historical pin (like the measured-arm sheet);
  this unit writes a **new sheet** (content differs materially: no `--stratum`, dev ids
  restored, one new candidate, a probe pass) at `docs/planning/larger-base-arm/runbook.md`,
  guarded by a new module importing the parse helpers from `test_probe_runbook_guards.py` by
  identity, with `feat-stratum-probe-execution` joining `STALE_WORKTREES` — **RED watched
  first**.
- **The post-run chain extends to five autopsy documents**: the pre-analysis extension step
  re-reads **all** autopsy documents (arm-a, budget-2048, format-hardening-arm-evidence,
  easier-stratum-evidence, + the new arm's), because the comparison asserts the trigger
  mapping against per-run declared decisions and refuses a run without them
  (`comparison.py:548-557`).
- **§ 7.3 closure is unspecified** — a genuine gap. § 7.3 says "Closed in P1"; P1 selected
  nothing; every later doc only repeats "stays open". The arm's finding may produce the
  first evidence for a base, but it cannot close § 7.3 itself: § 8.1 requires a Type 1
  amendment **before the measurement it governs runs** (P3's baseline). The finding names
  the base as evidence and routes the closure to a Type 1 amendment before P3.
- **CLAUDE.md's status block predates the probe execution** (it ends at "Phase 1 of
  probe-run"); the landing commit refreshes it to the post-probe state + this unit, per the
  file's own "capability written up in the same commit that ships it" rule.

## Affected areas

- New: `docs/planning/larger-base-arm/` (prd.md, understanding.md, runbook.md, finding.md).
- New: `src/whetstone/bakeoff/` — the third report writer + schema
  (`whetstone-larger-base-report/1`) and the third report-door mode
  (`--render-larger-base-report` in `comparison.py`), reusing `_row`, `_over`, `tally`,
  `_contract_fields`, `_contract_block`, `_counts` and `build_contract_arms` **by identity**.
- New: `tests/test_larger_base_runbook_guards.py` (identity imports from
  `test_probe_runbook_guards`), the one-home guard twins' third admission ground
  (test_report.py + test_transcript_locality.py), the planted-overlap control.
- New: `reports/larger-base/` — declaration-only committed artifacts, writer-generated.
- `PREREGISTRATION.md` § 10.6 (Type 2, pre-committed) + amendment log row.
- `CLAUDE.md` status refresh (in the landing commit).
- **Untouched:** `src/whetstone/verify/`, `patch.py`, `attribution.py` (AC2 pins);
  `run.py`'s surface needs no change; all existing report homes' artifacts stay static.

## Core loop placement

Element ② (nightly improvement loop): the arm measures whether strict-PASS training data
exists when the base is larger — the premise test for P2, not a training run. The reward is
untouched: STRICT grades by execution through the existing harness with the control
discipline (`sweep.py:41-47, 160-183`); the gate semantics (`UNVERIFIED` above PASS) are
untouched; nothing leaves the box (MLX local; source B in the primary's gitignored store,
reached by absolute path; the one network exception is the human-run weights fetch, per
`docs/ROADMAP.md:574-576`).

## Open questions (the PRD interview decides)

1. **Report home**: new `reports/larger-base/` (recommended — new series per the pinned-input
   rule; existing homes' artifacts are static and not regenerated) vs. extending the
   hardened arm inside `reports/format-hardening/` (same contract and task set, but requires
   re-rendering a static home and merging journals into one arm — machinery that does not
   exist).
2. **Candidate**: `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` as the single `--only`
   value (recommended; the 7B stays excluded by its measured zero ceiling; the 32B has no
   measured ceiling, so the exclusion rule does not apply to it).
3. **Task set**: the declared source-B set (recommended per M13 and the pivot signal's own
   wording) — denominator 61 private (66 − 5 dev) + 1 public = 62 per candidate.
4. **Dev subset**: restore the five declared ids (recommended — non-vacuous on the full set,
   the § 10.4 overlay as the measured-arm runbook carried it).
5. **§ 10.6 timing**: pre-committed in the unit, before the run (recommended — the § 10.5
   pattern).
6. **Capacity**: 36 GiB machine vs 18.4 GB weights — the mandatory `--probe` pass settles
   it; if it does not fit, the finding records capacity as the blocker and the next unit
   re-picks the candidate.
