# PRD — `p2-diff-autopsy`

**Card:** `docs/planning/p2-diff-autopsy/card.md` · **Dig:**
`docs/planning/p2-diff-autopsy/dig-transcripts.md` (empirical read),
`docs/planning/p2-diff-autopsy/dig-code.md` (reuse map and seams) ·
**Understanding:** `docs/planning/p2-diff-autopsy/understanding.md`
**Upstream:** `docs/ROADMAP.md` § 4 (P1 pivot signal `:387-389`, P2 `:393-406`),
`docs/planning/p2-yield-probe/prd.md` (esp. the correction at `:65-89`),
`PREREGISTRATION.md` § 10.1.

---

## 1. The problem

The yield-probe correction (`docs/planning/p2-yield-probe/prd.md:84-89`) demands a fourth fix
be proposed only after someone reads what the unparseable diffs contain. **That read has now
been done by hand** — `dig-transcripts.md` classifies all 208 stored completions from
`runs/arm-a/` and `runs/budget-2048/` (gitignored, primary checkout) into fifteen
data-grounded shapes and answers the fork's question: the wall is **formatting**, not
reasoning and not extraction (`dig-transcripts.md` § 4). The roadmap's named responses — an
easier task stratum or a larger base (`docs/ROADMAP.md:387-389`) — are unsupported by this
data; a format-hardening response is what the data names.

**But a hand-read is a hypothesis, not a measurement.** The dig was done by a reader with a
throwaway script that re-ran `extract_patch` + `git apply --numstat`
(`dig-transcripts.md:9-12`). It is not reproducible, not tested, not reusable on the next
transcript, and its shape counts are co-occurrence counts rather than a partition. The
yield-probe PRD's own 🔴 (`prd.md:244-247`) was exactly this: *"the taxonomy is asserted, not
yet grounded."* This slice ships the **instrument** — a deterministic, stdlib-only, offline
classifier that assigns any stored completion exactly one grounded content-shape cause — and
re-derives the breakdown with it, so the finding is machine-checkable rather than hand-read,
and every future transcript gets the same autopsy for free.

**And nothing on the reward path is touched.** The classifier is pure rules over stored
text, with `git` consulted exactly where `attribution.py` already consulted it — and, by
design, not even that: the coarse cause comes from the run's own `attribution.json`, which is
already measured.

## 2. What is already decided upstream (not re-litigated)

| Decided | Where |
|---|---|
| The reward is a pytest exit status; no model on the reward path | `CLAUDE.md`, `docs/ROADMAP.md` § 2 |
| The generation contract is not a pinned input, and it moves the numbers | `PREREGISTRATION.md:333-354` |
| No fourth fix before someone reads the unparseable diffs | `p2-yield-probe/prd.md:84-89` |
| Two contract fixes (search/replace; the token budget) are falsified | `p2-yield-probe/prd.md:65-89` |
| `UNVERIFIED` is never a win; `UNATTRIBUTED` is named, never folded | `attribution.py:117-120` |
| Figures about a model live in exactly one home; nothing is restated | `CLAUDE.md`; `tests/bakeoff/test_report.py:961-994` |
| The classification instrument is a figure-producing analysis, published nowhere | `p2-yield-probe/instrumentation/spec.md:92-95` (AC9) |
| Completions quote private donor code: transcripts refused under published output; fixtures synthetic | `run.py:886-907`; `card.md:68-70` |
| `whetstone bakeoff` must not exist as a CLI subcommand | `bakeoff/run.py:7-13` |
| The dig's counts are provisional observations, kept and marked | interview decision, `dig-transcripts.md` status block |

## 3. Decisions taken in this slice

**D1 — The slice ships the instrument, not the reading.** The dig is done; the deliverable
is `autopsy.py` — a classifier that re-derives the dig's partition and an asserted
fine→coarse mapping — plus the committed finding document. The finding says walls, not
numbers (`understanding.md` § 4.1, 4.5). **And the measurement may overturn the dig.** The
dig was a hypothesis read by a hand; the autopsy is the measurement. If the partition
reclassifies the dig's headline (e.g. the precedence rule moves loop-dominated stubs from
`im-start-loop` to `hunk-dies-early`), the finding reports what the autopsy measured — the
dig is provisional by design, and "the dig was wrong in this respect" is an honest outcome,
never a reason to smooth the classifier until it agrees.

**D2 — New module `src/whetstone/bakeoff/autopsy.py`, beside `attribution.py` (dig-code
option A).** `attribution.py` stays frozen: its `Cause` enum, `NO_DIFF_MARKERS`, bijection
test, and CLI schema are untouched, because adding fine members to `Cause` breaks no test but
silently leaks through `to_report_counts` (`attribution.py:299`) and diverges
`compare_to_counts` (`dig-code.md` § 3.3). The autopsy owns its own fine-cause enum, its own
AST-walk test, its own fixture corpus, and its own schema `whetstone-autopsy/1`.

**D3 — Coarse causes come from the run's own `attribution.json`, never a second git pass.**
The autopsy reads the transcript *and its sibling attribution file* (both exist for any run
that used the instrument; both stored runs have them). The mapping assertion compares the
shape-derived expected coarse bucket against the **recorded** coarse cause per record; a
contradiction is reported as a divergence, never reconciled. A missing attribution file is a
usage error naming the reason (the `attribution.py:464-473` shape), never a silent
shape-only run. This removes the checkout layer entirely from the autopsy: no `copytree`, no
`git apply`, no `--tasks` flag.

**D4 — One primary cause per record, with documented precedence; markers are observations,
not causes.** The fine taxonomy is the dig's shapes, promoted and demoted on the dig's own
evidence (`dig-transcripts.md` § 5 Q2):

- Primary causes (the partition; exactly one per record):
  `im-start-loop` (the 7B collapse; the dig's correction of `patch.py`'s mislabelling of
  43 records as "prose"/"code sample", `dig-transcripts.md` § 2 shape 1), `hunk-dies-early`
  (detail: `bare-line` | `fence-cut` | `end-of-output` — three deaths with different fixes,
  `dig-transcripts.md` § 5 Q1), `hunk-count-mismatch`, `header-without-hunk`, `well-formed`
  (the control: git-parseable, `dig-transcripts.md` § 2 shape 15), `no-diff` (inherited from
  `patch.py`'s own reasons via `cause_of_reason` — the extractor's vocabulary, detail = its
  reason sentence), and `unrecognised-shape` (the named terminal: never folded, never
  guessed — the autopsy's mirror of `UNATTRIBUTED`).
- Precedence: `im-start-loop` is primary only when the loop dominates the completion and no
  well-formed diff follows it; a real diff's state outranks the loop, which then demotes to
  a marker. `hunk-dies-early` outranks `hunk-count-mismatch` when the walk ends with counts
  remaining (`dig-transcripts.md` § 2 shape 3); a body extending beyond declared counts is
  the mismatch (`shape 2`). The precedence table is part of the module contract and its
  orderings are fixture-tested.
- Markers (optional per-record observations, each with its own detector and fixture):
  `stacked-fence`, `index-garbage`, `b-path-missing-slash`, `second-turn-rollover`,
  `repeated-diffs`, `phantom-assignments`, `noop-hunks`, `loop-present`. Markers are
  reported in the record, not counted as causes — the dig's "cosmetic corruption that only
  kills when a hunk is also broken" (`dig-transcripts.md` § 5 Q2b). **Markers are the
  observed set, not an exhaustive one:** the completeness burden rests on the primary
  partition alone; a marker list is append-only by evidence, and an unlisted marker is
  never *inferred* by the classifier — the distinction between "no marker" and "no
  detector" is stated in the record schema, not hidden.

**D5 — Truncation is a shape cause, labelled *inferred*.** `mlx_runtime.generate` returns a
bare `str` with no finish reason (`mlx_runtime.py:206-232`), so `hunk-dies-early`
(`end-of-output`) is inferred from shape, exactly as every existing document discloses
(`attribution.py:101-104`; `p2-yield-probe/understanding.md:139-146`). The breakdown and the
finding state the inference; the classifier never claims to have measured a token cap.

**D6 — `wrong-target-file` stays out of the classifier.** The fine pass is shape-only: no
manifest, no declared-path comparison (`dig-transcripts.md` § 5 Q4). The two hand-verified
records — one of them a diff aimed at a held test, the reward-hack shape that never reached
the verifier (`dig-transcripts.md` § 2 shape 14) — are reported as a named finding in the
finding document, with the precision that a record the verifier never saw is **not** a caught
hack: `N` counts graded rollouts only.

**D7 — The autopsy CLI mirrors `attribution.py`'s.** `python -m whetstone.bakeoff.autopsy
--transcript X --attribution Y --out Z`; `--out` must be a gitignored path — a non-ignored
`--out` is a usage error (the `_refuse_published_transcript` shape, `run.py:886-907`), not a
warning. Exit 2 with a named reason on a missing transcript or attribution file. No
`--report` flag: the autopsy's only comparison is its own mapping assertion. Document schema
`whetstone-autopsy/1`, per-record fields `(candidate, task_id, cause, detail, markers,
recorded_coarse, coarse_agrees)`.

**D8 — The `verify/`-untouched guard ships in this slice.** No test asserts
`git diff --stat origin/master -- src/whetstone/verify/` is empty today (`dig-code.md` § 5
trap 5; the yield-probe plan named it as a to-add, `plan_20260805.md:218-219`). Card AC5
(`card.md:52-53`) makes it mandatory; it is written watched-failing first
(`CONTRIBUTING.md:56-60`).

**D9 — The dig's counts stay, marked provisional.** Interview decision; the classifier's
breakdown is the measurement and lives gitignored; where it diverges from the dig's
co-occurrence counts — systematically, because the classifier partitions where the dig
counted co-occurrence — the divergence is reported as a finding, not reconciled
(`dig-transcripts.md` status block).

**D10 — Running the autopsy over the stored runs is an operator step, after the code
lands.** The two breakdowns are written to gitignored roots (e.g. `runs/diff-autopsy/`),
mirroring how arm A ran after its instrument landed (`instrumentation/spec.md:100-101`).
The step verifies the completeness control: **zero `unrecognised-shape` in both stored
runs**, and the dig's numbers re-derived with divergences reported.

## 4. Requirements

### R1 — The fine pass re-walks with `patch.py`'s own internals, never a copy
`autopsy.py` imports `extract_patch` and the extractor's privates (`_HUNK_HEADER`,
`_diff_span`, `_hunk_body`, `_fenced_spans`, `_bare`, `patch.py:70,240-300,190-223,303-310`)
— never copies their regexes. A test asserts function identity the way
`test_attribution.py:190-195` does, so a parallel copy fails the suite the moment `patch.py`
changes. `patch.py` itself is not modified.

### R2 — Exactly one primary cause per record; unrecognised is named, never guessed
The precedence table (D4) is implemented and its orderings fixture-tested. A completion
matching no primary cause yields `unrecognised-shape` with the shape that defeated the
detectors in the detail — countable, never folded into a neighbour.

### R3 — The fine→coarse mapping is asserted, per record, against the run's own attribution
A pure mapping from fine cause to the set of coarse causes it may explain (e.g.
`hunk-dies-early` → `{WOULD_NOT_PARSE}`, `im-start-loop` → `{NO_DIFF_HEADER,
FENCED_WITHOUT_DIFF}`, `well-formed` → `{APPLIED, PARSED_BUT_DID_NOT_APPLY}`).
`UNATTRIBUTED` is always allowed in the allowed set: it means "not graded" (no checkout for
the public instance), which is orthogonal to the shape of the completion — the two stored
runs each carry an `UNATTRIBUTED` record whose diff is shape-classifiable
(`dig-transcripts.md` § 2 shape 2 note). Every record's recorded coarse cause is checked
against its allowed set; violations are reported as divergences. A planted missing mapping
entry fails the suite; a synthetic record whose recorded cause contradicts its fine cause
is watched failing against a credulous mapping first.

### R4 — Determinism
Same transcript + attribution → byte-identical document. No iteration over sets or dicts
whose ordering can vary (`test_extraction.py:488-503` pattern).

### R5 — Locality and the CLI contract
`--transcript`, `--attribution`, `--out` required; `--out` under a non-ignored path refused
before any analysis; missing inputs exit 2 with the reason named (`attribution.py:464-473`
shape); schema `whetstone-autopsy/1`; the whole module and its test carry the no-inference
AST walk (`test_attribution.py:538-559`, roots at least as wide as `:113-115`).

### R6 — The reward path provably does not move
New test: `git diff --stat origin/master -- src/whetstone/verify/` is empty (watched failing
first). `GUARDED_ROOTS` unchanged; `tests/test_no_inference_on_reward_path.py` and
`tests/test_reward_path_scope_is_partitioned.py` pass unchanged; no module outside
`bakeoff/` is created.

### R7 — Fixture discipline
Every primary cause and every marker has a fixture: a **synthetic replica of an observed
shape, never a verbatim completion** (`card.md:68-70`; the discipline every committed test
already keeps, `dig-code.md` § Fixture discipline). A planted fifth cause fails the
completeness control; a marker detector with no fixture fails; the anti-vacuity shape of
`test_attribution.py:310-314` is inherited.

### R8 — The operator step and the completeness control
After the code lands, the autopsy runs over both stored runs by absolute path; breakdowns
land only in gitignored roots; zero `unrecognised-shape` across both runs is verified (the
taxonomy is complete over the data it was grounded in — this is the control that says the
"no other bucket" rule actually held); divergence vs the dig's counts is written up as a
finding.

### R9 — The finding document
`docs/planning/p2-diff-autopsy/finding.md` (committed): names the wall the evidence points
at (formatting), states which of the roadmap's named responses the data supports — or that
it supports neither on this evidence (`understanding.md` § 6) — and carries the mandatory
disclosures: truncation is inferred; the dig's counts were provisional; the autopsy's
breakdown lives in gitignored artifacts and is the measurement; the `wrong-target-file`
record aimed at a held test is attempt-shaped evidence, not a counted hack (D6). **The
finding contains no figure about a model** — walls, not numbers (`understanding.md` § 4.5).

## 5. Acceptance criteria

Every one is a command that exits 0 or an artifact that exists.

1. `uv run pytest` green; `ruff check .`, `mypy src/`, `whetstone --help` all exit 0
   (`CONTRIBUTING.md:50`).
2. The new `verify/`-untouched test passes — `git diff --stat origin/master --
   src/whetstone/verify/` empty — having been watched failing first; the reward-path guard
   and its scope partition pass unchanged (R6).
3. A test asserts the fine pass uses `patch.py`'s own functions by identity, and that
   `patch.py` has no diff on this branch (R1).
4. A test asserts determinism: one fixture completion classified twice → identical
   `(cause, detail, markers)` (R4).
5. Tests assert the precedence table's orderings: loop-dominant NoDiff → `im-start-loop`;
   loop + well-formed diff → `well-formed` with `loop-present` marker; counts-exhausted-but-
   body-continues → `hunk-count-mismatch`; walk-ended-with-counts-remaining →
   `hunk-dies-early` with the correct death detail; header-without-hunk → `header-without-
   hunk`; a planted unrecognisable completion → `unrecognised-shape` by name (R2).
6. A test asserts the mapping: a fine cause with a missing entry fails the suite; a record
   whose recorded coarse cause contradicts its fine cause is reported as a divergence,
   watched failing against a credulous mapping (R3).
7. Tests assert the CLI refusals: non-ignored `--out` → usage error; missing transcript or
   attribution → exit 2 with the reason named; `git check-ignore` answers "ignored" for the
   documented breakdown root (R5, trailing-slash form).
8. The AST walk over `autopsy.py` and `test_autopsy.py` asserts no inference import, and its
   anti-vacuity control sees the imports the modules actually make (R5).
9. The operator step is done: breakdowns for both stored runs exist under gitignored roots
   with schema `whetstone-autopsy/1`, zero `unrecognised-shape`, and the divergence list vs
   the dig's counts written beside them (R8).
10. `docs/planning/p2-diff-autopsy/finding.md` exists, names the wall and the supported
    roadmap response, carries the four disclosures, and contains no figure about a model
    (R9).

## 6. Risks

| # | Risk | Mitigation |
|---|---|---|
| R-a | **The stop-reason exposure is the hardest code in the slice.** Distinguishing `bare-line` / `fence-cut` / `end-of-output` deaths means reading `patch.py`'s walker privates correctly, and the margin with `hunk-count-mismatch` is genuinely fuzzy (`dig-transcripts.md` § 5 Q1) | Fixtures for each death kind, watched failing first; the `test_attribution.py:144-162` real-git-oracle pattern for the parse side; the precedence table pinned by tests (AC5) |
| R-b | **The mapping assertion finds real contradictions** (e.g. a fine cause whose recorded coarse cause is impossible) | That is a finding, not a bug — reported verbatim, never reconciled (R3, AC6); the PRD pre-commits that behaviour |
| R-c | **The completeness control fails:** both stored runs do not classify to zero `unrecognised-shape` | The taxonomy is data-grounded; a genuine unrecognised shape is added with a fixture — the correction is to the taxonomy, and the dig's provisional status exists exactly for this (D9) |
| R-d | **The dig's co-occurrence counts vs the classifier's partition are misread as a contradiction** | D9 + the status block: the divergence is expected, systematic, and reported as a finding |
| R-e | **A breakdown or fixture leaks private donor content** | D5/D7 refusals; `git check-ignore` assertions; synthetic-fixture rule with the no-verbatim rule asserted in review; nothing new under `reports/` (AC7, R7) |
| R-f | **The finding overclaims** — reads as a measurement of the bases' ability, or as a recommendation the fix will raise PASS counts | R9's disclosures are mandatory and pinned by the review gate; the finding may not predict a count (`dig-transcripts.md` § 5 Q7) |
| R-g | **The 7B loop is mischaracterised** as a model property rather than classified as a shape | D4's scope discipline: the classifier classifies; the finding says what it does not claim (`dig-transcripts.md` § 5 Q3) |

## 7. Out of scope

- **The format-hardening fix itself** — the fourth fix the read exists to inform; named as
  the finding's consequence, not built here.
- **Any change to `src/whetstone/verify/`, `patch.py`, `attribution.py`, or the reward-path
  guards** — the autopsy imports and asserts; nothing else moves.
- **Re-measuring PASS counts, or anything comparable to `reports/baseline/`** — the autopsy
  is a shape analysis, and the one-home rules are untouched.
- **The held-out split (§ 7.1) and the retry count `R` (§ 7.2)** — both P3.
- **The P2 rollout loop (`whetstone run --night`)** — blocked on the yield question this
  slice's finding informs.
- **`wrong-target-file` classification with declared paths, `noop-hunks`/content-level
  analysis, and explaining the 7B loop's cause** — named findings, deferred layers.
- **Amending `PREREGISTRATION.md`** — no new governed figure is published, so no amendment.
- **Anything touching the network or a model** — the autopsy is offline and stdlib-only.

## 8. Self-critique

Ran through the generator's critique against this document.

| Dimension | Rating | Note |
|---|---|---|
| Problem Definition | 🟢 | The correction's demand + the dig's evidence; framed honestly as hypothesis → instrument |
| Success Metrics | 🟡 | No goal statement (added below in this section) and no effort estimate — stated as unknown rather than guessed, following `p2-yield-probe/prd.md:258` |
| User Understanding | 🟡 | No persona section in the first pass; added below |
| Scope Clarity | 🟢 | In/out explicit; the fix is named and refused by name |
| Edge Cases & Risks | 🟢 | Seven risks with mitigations; the mapping-divergence behaviour pre-committed |
| Stakeholder Alignment | 🟢 | Solo project; the review gate is the approval |
| Feasibility Signal | 🟡 | The stop-reason exposure is flagged as the hard part (R-a) with the fixture-first mitigation; a plan-level estimate belongs to `tech-plan` |
| Reward Integrity & Never-Regress | 🟢 | No model anywhere; `verify/` untouched by construction and by a new diff-stat test; the reward-hack record is explicitly *not* counted in `N` (D6); nothing published |

**Goals & Success (one line).** Success is: the dig's read becomes a reproducible instrument
— deterministic, locality-safe, grounded in `patch.py`'s own walker — whose breakdown of
both stored runs completes with zero `unrecognised-shape`, whose mapping assertions hold,
and whose finding names the wall and the roadmap response the data supports. No numeric
target: this slice produces no governed figure, and the finding may not predict one.

**Persona.** The operator — the founder, running the same offline analysis `attribution.py`
already serves: a transcript in, a per-record cause out, no model, no network, no
publication. The autopsy's future caller is the same persona one phase later, autopsying
every new bake-off run before deciding what to change next — which is precisely the habit
the yield probe's correction was calling for.

### The top gaps this critique found

🔴 **The completeness control's scope must be stated or it will be over-read.** AC9's
"zero `unrecognised-shape` in both stored runs" proves completeness over the *grounding
corpus* — the taxonomy was derived from it, so the control is necessary (it says "the
partition actually covers what we read") and **not** sufficient (it says nothing about
future transcripts). The finding must state that generality to future runs is unproven,
and the fallback when the operator step finds an unrecognised record is fixed in advance:
add the shape with a fixture (a taxonomy correction, R-c) — never extend a neighbouring
cause to swallow it.

🔴 **`no-diff` is inherited, not observed — and its fixture must say so.** Zero records in
either stored run are genuine prose/code-sample answers (`dig-transcripts.md` § 2,
absences); the category exists because `patch.py`'s reasons are the extractor's vocabulary
and the autopsy must classify every record, including future ones. Its fixture is a
faithful replication of the extractor's *documented* shape, not of observed data — the
fixture is labelled `inherited-not-observed` so no reader mistakes it for a grounded one.

🟡 **The `hunk-dies-early` ↔ `hunk-count-mismatch` margin is where the classifier can
silently disagree with `git`.** The walker's counts-vs-body test is the classifier's own
reading; `git apply --numstat` is the oracle the attribution already answered with. The
mapping assertion (R3) is what surfaces disagreement — a record classified
`hunk-dies-early` whose recorded coarse cause is `PARSED_BUT_DID_NOT_APPLY` is reported,
never reconciled. This is the one place the PRD's discipline depends on divergence being
treated as data, and the finding must record it as such.
