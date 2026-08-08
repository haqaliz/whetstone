# Understanding — `p2-diff-autopsy`

**Dug 2026-08-09**, in `.claude/worktrees/feat-p2-diff-autopsy` at `d9a2315`. Baseline green:
`ruff`, `mypy`, and 643 passed / 2 skipped before anything was touched.

Every claim below carries a `file:line` or a named dig note. The two dig notes —
`dig-transcripts.md` (the empirical read) and `dig-code.md` (the reuse map and seams) — are the
evidence base for this file and for the PRD.

---

## 1. What the work is really asking

The card says "read what the unparseable diffs contain". The dig says the honest framing is a
level up, and it changes what must be shipped.

`docs/planning/p2-yield-probe/prd.md:84-89` (the correction) fires the demand:

> no fourth fix should be proposed before someone reads what the unparseable diffs actually
> contain; the completions are on disk, so that costs a read rather than a run.

**The read has now been done — by hand, with a throwaway script.** `dig-transcripts.md`
classifies all 208 stored completions into fifteen data-grounded shapes and answers the fork's
question: the evidence points at a **formatting wall**, not a reasoning wall (26 of 156 arm-a
rollouts produced diffs git parsed; 11 applied — the bases *can* reach the verifier) and not an
extraction wall (the extractor located a diff in every parse-failed record; its "never repair"
rule correctly refuses to fix what the model wrote). The roadmap's named responses — an easier
task stratum or a larger base (`docs/ROADMAP.md:387-389`) — are **unsupported by this data**;
a format-hardening response is what the data names, and until it runs, the pivot signal's
premise — "the bases cannot fix these bugs" — remains untested, exactly as the yield-probe
correction already said.

**So this slice is not "do the read". The read was done by a hand-reader with a throwaway
script — a hypothesis, not a measurement.** The slice is: turn that read into a **reproducible,
tested instrument** — a deterministic, stdlib-only, offline classifier that assigns any stored
completion a grounded content-shape cause — and re-derive the breakdown from it, so the finding
is machine-checkable rather than hand-read, and every future transcript gets the same autopsy
for free. The dig's counts are provisional observations to be **re-derived by the classifier**;
where they differ, the difference is reported, not smoothed.

**What this slice may not claim.** It does not implement the format-hardening fix (the fourth
fix — out of scope by name). It does not re-measure PASS counts (nothing here is comparable to
`reports/baseline/`). And a hand-read finding is not a measured one: the slice's finding
document describes walls, not numbers.

## 2. Where it sits on the core loop

`CLAUDE.md` § *The core loop*: element **①**'s measurement apparatus — the same shelf as
`attribution.py`. Precisely:

- **The reward is untouched.** Nothing under `src/whetstone/verify/` changes. The AST guard's
  `GUARDED_ROOTS` (`tests/test_no_inference_on_reward_path.py:104-109`) is not widened.
- **All new code lands in `src/whetstone/bakeoff/`** — `EXEMPT` from the reward-path guard by a
  written reason (`tests/test_reward_path_scope_is_partitioned.py:100-117`) — and carries its
  own no-inference AST walk over module and test file, the shape
  `tests/bakeoff/test_attribution.py:538-559` already sets.
- **`UNVERIFIED`/`UNATTRIBUTED` semantics are untouched.** The classifier's terminal for
  "could not be asked" is named, countable, and never folded into a neighbour
  (`attribution.py:117-120`).

This is emphatically **not** a looser verifier and **not** a model's opinion anywhere: the
classifier is pure string/pattern rules over stored text, with `git apply --numstat` used only
as an oracle exactly where `attribution.py` already uses it. No LLM, no judge, no reward-path
change.

## 3. The seam, precisely

**The coarse pass is inherited, not rebuilt.** The classifier calls the *same* `extract_patch`
the live run called (`scoring.py:435`; identity pinned at `test_attribution.py:190-195`) and
derives its coarse bucket through `cause_of_reason` (`attribution.py:168-180`) — never by
re-matching reason strings, and never by re-running the checkout layer, because the coarse
cause already *is* the git-answered parse/apply split.

**The fine pass re-walks with `patch.py`'s own eyes.** The shapes the card names
(`card.md:29-32`) mostly land **inside** `Extracted` today (`patch.py:43-53`: absolute paths,
CRLF, truncation are all deliberately extracted and left for git to refuse), so the fine
information does not survive `extract_patch`'s collapse. The fine pass imports the extractor's
privates (`_HUNK_HEADER`, `_diff_span`, `_hunk_body`, `_fenced_spans`, `_bare` —
`patch.py:70,240-300,190-223,303-310`) rather than copying their regexes: a second literal
drifts from the extractor the run used and no test would notice.

**The relationship to `attribution.py` is a finer partition, asserted.** The fine causes map
down onto `Cause` (`attribution.py:75-121`) in the `_FOLD` shape (`:257-264`), and the mapping
is asserted both ways — a planted shape fails, a fine cause without a bucket fails, and a
stored record whose fine cause disagrees with its actual coarse cause is reported as a
divergence rather than reconciled. **The taxonomy's anchor is fixture shapes replayed through
real git**, not construction sites in `patch.py`: the extractor has no construction sites for
the `Extracted`-side shapes (the one place the `attribution.py` discipline must be extended,
`dig-code.md` § 3.2).

**The dig's fifteen shapes are the seed taxonomy, and it is provisional.** Three shapes cover
138 of 156 arm-a records (`dig-transcripts.md` § 4): `im-start-loop` (the 7B collapse — 43
records the extractor's own reasons misname as "prose"/"code sample"), `hunk-body-dies-early`
(3B's signature; bare-line death dominates), and `hunk-count-mismatch` (14B's signature). The
two parse-refusal shapes partition all 84 `WOULD_NOT_PARSE` records exactly (45 + 39). Sub-
distinctions inside `hunk-body-dies-early` (bare-line vs fence-cut vs end-of-output) need the
walker's stop-reason exposed and are worth doing — they separate a fixable formatting habit
from pure budget truncation. Some shapes are **markers, not causes** (`index-line-trailing-
garbage`, `git-header-b-path-missing-slash` — cosmetic corruption that only kills when a hunk
is also broken); `noop-hunks` is content-level and belongs to a later layer; `wrong-target-file`
has two hand-verified records, one of them the **reward-hack shape** (a diff aimed at a held
test — the verifier's scope rule never got the chance to fire, `verify/strict.py:524-533`).

## 4. What publishing costs — the constraints that shape the PRD

1. **The classifier publishes nothing.** `tests/bakeoff/test_report.py:961-994` **and**
   `tests/bakeoff/test_transcript_locality.py:73-101` both pin the exact `reports/` file list;
   the one allowed move is argued in the guard's own docstring (`:964-970`) and this slice has
   no such argument. Breakdown output goes to a gitignored root (`/runs/` or `/reports/local/`,
   `.gitignore:20-24`), asserted by `git check-ignore` the way `test_transcript_locality.py:47-71`
   does — with the trailing-slash form load-bearing (`:29-34`).
2. **Completions quote private donor code.** Transcripts are refused under any published output
   (`run.py:886-907`); fixtures are **synthetic replicas of observed shapes, never verbatim
   completions** (`card.md:68-70`), following the fixture discipline every committed test
   already keeps (`dig-code.md` § Fixture discipline).
3. **The `verify/`-unmodified guard does not exist yet.** `dig-code.md` § 5 trap 5: no test
   asserts `git diff --stat origin/master -- src/whetstone/verify/` is empty. The card makes it
   acceptance criterion 5 (`card.md:52-53`); the slice writes it (watched failing first,
   `CONTRIBUTING.md:56-60`), then never touches a `verify/` file.
4. **Truncation stays an inference, disclosed.** `mlx_runtime.generate` returns a bare `str`
   with no finish reason (`mlx_runtime.py:206-232`), so *truncated-mid-hunk* is inferred from
   shape (`patch.py:292-295`) — the exact inference the yield probe was burned by
   (`understanding.md:139-146`). The classifier may implement it as a shape cause, but the
   breakdown must label it *inferred* and the PRD must say which wording carries that.
5. **The dig note's counts are a gray zone, flagged rather than hidden.** The yield-probe PRD
   R8 forbade restating figures in planning documents; this slice's own dig note carries
   per-shape counts in a committed planning file. The resolution proposed: the dig note is
   explicitly a *working evidence note* — provisional observations from a throwaway script,
   superseded by the classifier's breakdown, which is the measurement and lives gitignored; the
   committed finding document carries walls, not numbers. Whether the dig note's counts stay as
   written is a review-gate decision (`card.md` → this file → PRD).

## 5. Contradictions and open questions

1. **The card's example shape list is wrong in two places, and that is the point.** "prose" and
   "fenced code that is not a diff" occupy **zero** records — the 43 records in those buckets
   are `im-start-loop` degeneracy, and `patch.py`'s own reason strings misname them
   (`dig-transcripts.md` § 2, shapes 1; § 5 Q6). The classifier's labels must be content-
   grounded even where they agree with a bucket — and the corpus-provisionally does not need
   categories for what is absent (`dig-transcripts.md` § 2, absences).
2. **Is the 7B loop a sampling-configuration problem or a model property?** It is 100% of 7B's
   output and 28% of the arm-a corpus (`dig-transcripts.md` § 5 Q3). The classifier can only
   *classify* it, not explain it; the finding must say what the classification does and does
   not claim about the base.
3. **Does the fine taxonomy include `wrong-target-file`?** It needs the manifest's declared
   paths — a checkout-layer dependency the dig kept separate (`dig-transcripts.md` § 5 Q4). Two
   hand-verified records, one of them the reward-hack shape this project publishes a count for.
   The PRD should decide: shape-only signals (fictional-filename patterns), declared-path
   comparison against the task, or a named finding with the two records kept out of the
   classifier.
4. **How many fine causes is the right number?** Fifteen shapes is the raw read; the PRD must
   decide the *cause set* — markers demoted to observations, sub-deaths promoted to causes,
   `noop-hunks`/content-level deferred — and each cause needs a fixture and a planted-shape
   test. Too few collapses the three dialects back into `WOULD_NOT_PARSE`; too many invents
   categories the data does not support (`dig-code.md` § 4 Q6; `prd.md:244-247`'s 🔴).
5. **Reproduction of the dig's counts.** The classifier's first honest test against the real
   transcripts is re-deriving the dig's breakdown; divergence is reported as a finding (the
   `compare_to_counts` shape, `attribution.py:304-346`). The operator step — running the
   classifier over the primary checkout's transcripts — belongs after the code lands, exactly
   as arm A was an operator step (`instrumentation/spec.md:100-101`).
6. **What does the finding imply for the yield question?** 26 well-formed diffs reached the
   apply layer in arm-a (16.7% of rollouts; 25% in budget-2048) — but *content-eligible* is
   not *correct*. The finding may say what a format-hardening intervention could convert, and
   must not predict a PASS count (`dig-transcripts.md` § 5 Q7): no invented numbers.

## 6. Guardrail check

| Guardrail (`CLAUDE.md`) | Status |
|---|---|
| Reward verifiable, never a judge | **Held.** No model anywhere; the classifier is deterministic rules over stored text; `verify/` untouched by construction and by a new diff-stat test |
| `UNVERIFIED` ≠ win | **Held.** Untouched |
| Local / BYOK / private | **Held.** Transcripts stay in the primary checkout, read by absolute path; fixtures synthetic; breakdowns gitignored |
| No frontier base-model training | **Held.** Nothing trains |
| No invented numbers | **Held, and load-bearing.** The classifier's breakdown is the measurement; the finding describes walls, not numbers; the dig's counts are explicitly provisional |
| Ship the honest number | **Held.** The finding will say which roadmap response the data supports — even if that answer is "neither of the two named ones, on this evidence" |
