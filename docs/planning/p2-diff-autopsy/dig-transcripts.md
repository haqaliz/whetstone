# Dig — transcript autopsy: what the bases wrote instead of an applicable diff

**Slice:** `p2-diff-autopsy` · **Dig:** the empirical read of both stored transcripts
**Inputs (gitignored, primary checkout):** `runs/arm-a/transcript.jsonl` (156 records),
`runs/budget-2048/transcript.jsonl` (52 records), plus each run's `attribution.json`.
**Date of read:** 2026-08-09. **Author:** aliz (offline read; no model was consulted).

This note grounds the cause taxonomy the slice's classifier will implement. Every category
below was **observed in the completions**, never assumed from the PRD's provisional list
(`docs/planning/p2-yield-probe/prd.md:244-247`). Counts were produced with a throwaway
script that re-ran `extract_patch` and `git apply --numstat` over each record (git as the
parse oracle, exactly as `attribution.py` uses it); no harness code was modified.

**Privacy rule applied throughout:** the completions quote the user's own private donor
code verbatim. Nothing below reproduces donor content — shapes are described in words and
micro-examples are synthetic placeholders (`<...>`). The transcripts themselves remain in
gitignored run artifacts; this file carries only the reading.

> **Status of the counts below (2026-08-09, understanding § 4.5):** they are **provisional
> observations** produced by a throwaway dig script (re-running `extract_patch` + `git apply
> --numstat`), not by the shipped instrument. The slice's classifier (`src/whetstone/bakeoff/autopsy.py`,
> to be built) is the measurement; its breakdown — written only to gitignored artifacts —
> re-derives these numbers, and any divergence is reported as a finding rather than
> reconciled. Note also that shape counts here are **co-occurrence counts** (a record carries
> several shapes); the classifier assigns exactly one primary cause per record with a
> documented precedence, so its per-cause totals will differ from these rows in that
> systematic way.

---

## §1 Data summary

Both runs generated one completion per `(candidate, task)` over the same 52-task source-B
set (plus the single public instance `pallets__flask-4045`, which has no checkout and is
therefore `UNATTRIBUTED` in every run).

**arm-a** — 156 records, 3 candidates × 52 tasks. Attribution-cause counts (from
`runs/arm-a/attribution.json`, per candidate):

| candidate | WOULD_NOT_PARSE | PARSED_BUT_DID_NOT_APPLY | NO_DIFF_HEADER | FENCED_WITHOUT_DIFF | APPLIED | HEADER_WITHOUT_HUNK | UNATTRIBUTED |
|---|---|---|---|---|---|---|---|
| Qwen2.5-Coder-3B | 42 | 7 | — | — | 1 | 1 | 1 |
| Qwen2.5-Coder-7B | 5 | 3 | 33 | 10 | 1 | — | — |
| Qwen2.5-Coder-14B | 37 | 5 | — | — | 9 | — | 1 |
| **total** | **84** | **15** | **33** | **10** | **11** | **1** | **2** |

**budget-2048** — 52 records, 14B only, double token budget (the base arm-a's evidence
best supported): `WOULD_NOT_PARSE` 38, `PARSED_BUT_DID_NOT_APPLY` 5, `APPLIED` 8,
`UNATTRIBUTED` 1.

**Cross-run determinism:** 38 of the 52 completions are **byte-identical** between the two
runs. All 14 changed completions are *longer*; none is shorter. This is the first
quantitative statement of run-to-run determinism at the text level.

Two immediate findings the counts hide:

1. **The `NO_DIFF_HEADER` and `FENCED_WITHOUT_DIFF` buckets (43 records, all 7B) are not
   prose and not code samples.** Every one of them is a degenerate repetition loop of the
   chat-template tokens `<|im_start|>` / `<|im_end|>` / the word `system` (§2 shape 1).
   `patch.py`'s reason strings — *"the output is prose"* / *"a code sample or an
   explanation"* — **misname the content**. A classifier that inherits the extractor's
   vocabulary would inherit the misreading.
2. **`WOULD_NOT_PARSE` (84 records) is not one cause.** It is two different parse
   refusals wearing the same tag — git "corrupt patch" at a *short* diff whose hunk body
   died early (3B's signature), versus at a *long* diff whose hunk counts were invented
   (14B's signature) — plus a tiny third (7B's truncated stubs).

---

## §2 The grounded shape catalogue

Fifteen shapes occupy the data. Each entry: name (kebab-case) · one-sentence definition ·
deterministic detectability · the attribution cause bucket it currently lands in · count
per run. **Shapes are content-level; the cause bucket is where the extractor+git pipeline
dropped the record.** A record carries several shapes (e.g. every 7B diff-bearing record
also carries `im-start-loop`), so shape counts do not sum to record counts.

### The three dominant shapes

**1. `im-start-loop`** — the completion is dominated by repeated chat-template tokens:
lines whose entire content is `<|im_start|>`, `<|im_end|>`, or `system`, typically filling
most of the token budget (511 lines / ~3.9 KB is the modal shape), with no diff and no
prose.
Detectable: yes — pure string rules; ratio of loop-token lines to total lines (>0.2
separates every observed case cleanly).
Lands in: `NO_DIFF_HEADER` (33) and `FENCED_WITHOUT_DIFF` (10) when it is all the record
contains; 9 further records carry a real (stub or short) diff *after* the loop
(shapes 2, 3, 8, and the well-formed contrast below).
Counts: arm-a **52/52 of 7B**; budget-2048 0 (7B not run); 3B and 14B 0.

**2. `hunk-count-mismatch-body`** — a diff whose `@@ -old,count +new,count @@` header
declares line counts that the hunk body does not satisfy (body shorter or longer than
declared; counts evidently invented, not counted); git's walk of the declared count lands
mid-hunk, on the next hunk header, or past EOF and refuses: *"corrupt patch at line N"*.
Detectable: yes — pure pattern rules (count prefixes per hunk, compare to declared) with
`git apply --numstat` as the oracle.
Lands in: `WOULD_NOT_PARSE`; one record (`pallets__flask-4045`) is `UNATTRIBUTED` for
lack of a checkout, but its diff shows the same counts-to-body mismatch.
Counts: arm-a **35 × 14B**, 3 × 3B, 2 × 7B; budget-2048 **32** (31 `WOULD_NOT_PARSE` +
1 `UNATTRIBUTED`).

**3. `hunk-body-dies-early`** — a diff whose first hunk terminates within a handful of
lines of its header, before its declared counts are exhausted, so the extracted diff is a
stub (typically 180–900 chars against a 2.5–4.5 KB completion) and git refuses the
unterminated hunk at "corrupt patch at line 7–19". Three observed deaths inside the
hunk body, all from reading the completions:
 - *bare-line death* (dominant in 3B): a body line written with **no leading space / `+` /
   `-` prefix** — the model pasted the source line verbatim; the extractor's walk stops
   there, and git's declared-count walk hits it too;
 - *fence-cut death*: the closing ` ``` ` fence arrives before the counts are exhausted;
 - *end-of-output death*: the completion simply ends mid-hunk (the pure budget-truncation
   shape; every 7B stub ends this way).
Detectable: yes — the walk already implements it; a classifier needs to distinguish the
three deaths by looking at the line that ended the walk (unprefixed line vs fence vs EOF).
Lands in: `WOULD_NOT_PARSE`.
Counts: arm-a **40 × 3B**, 3 × 7B, 3 × 14B; budget-2048 **7 × 14B**. Hand-read subset
(arm-a 3B, 5 records): 3 bare-line deaths, 1 fence-cut, 1 count-shortfall that stopped
the walk anyway — the boundary with shape 2 is genuinely fuzzy at the margin (§5 Q1).

### Dialect-level shapes (what the three bases actually emit)

**4. `plain-unified-no-git-header`** — a syntactically unified diff that omits the
`diff --git` and `index` lines entirely: `--- a/<path>` / `+++ b/<path>` / hunks only.
git accepts this dialect *when the hunks are right* — which is why 14B's nine `APPLIED`
records are all this shape — and rejects it when the hunks are wrong (shape 2).
Detectable: yes — presence of the `--- ` / `+++ ` pair with no `diff --git` in the text.
Lands in: `WOULD_NOT_PARSE` (broken hunks), `APPLIED` / `PARSED_BUT_DID_NOT_APPLY`
(working hunks).
Counts: arm-a **52/52 of 14B**; budget-2048 52/52.

**5. `stacked-fence-markers`** — a line containing two or three concatenated fence
markers, e.g. `< ``` ```diff >` or `< ``` ``` ```diff >`, at block boundaries; the model
closes one fence and opens the next on the same line.
Detectable: yes — `^```\s*````.
Lands in: any bucket; harmless by itself (the extractor strips nothing but tolerates it),
but the fence boundary is also where 14B diffs often end (a fence-cut death, shape 3).
Counts: arm-a **51/52 of 14B**, 15 × 3B; budget-2048 51/52.

**6. `git-header-b-path-missing-slash`** — a `diff --git a/<path> b <path>` header in
which the `b` path's slash is missing (`b ` followed by a space, not `b/`).
Detectable: yes — `^diff --git a/\S+ b [^ /]`.
Lands in: `WOULD_NOT_PARSE`; survives silently in `APPLIED` records too, because git reads
the file paths from the `---`/`+++` lines, which are usually right.
Counts: arm-a **7 × 3B**; 14B and 7B 0.

**7. `index-line-trailing-garbage`** — an `index <h1>..<h2>` line followed by a junk token
where git expects nothing (or a mode): `<h1>..<h2> 10`, `<h1>..<h2> 101112`,
`<h1>..<h2> 1234567`, `<h1>..<h2> 1024567 10`, and once a ~600-digit ascending digit run
where the model wrote a counting sequence as the "hash". Legal modes (`100644`,
`100755`, `120000`, `160000`) are not junk; every other trailing token is.
Detectable: yes — regex + a mode allow-list.
Lands in: `WOULD_NOT_PARSE` mostly; git tolerates it when the rest of the hunk is right
(it appears in `PARSED_BUT_DID_NOT_APPLY` and the 3B `APPLIED` record too), so it is a
corruption marker, not by itself the killer.
Counts: arm-a **20 × 3B**, 1 in `HEADER_WITHOUT_HUNK`; 14B and 7B 0.

**8. `git-header-without-file-lines`** — a `diff --git a/<p> b/<p>` header followed
directly by a hunk, with the `---`/`+++` pair missing; git answers *"patch fragment
without header"* because its parser opens a file section at the `---`/`+++` pair, not at
`diff --git`. These are the only three records in the corpus where git named that error.
Detectable: yes — header-then-`@@` with no `---`/`+++` between.
Lands in: `WOULD_NOT_PARSE`.
Counts: arm-a **3 × 7B** (all also `hunk-body-dies-early` stubs); 3B and 14B 0.

### Decorative and second-turn corruption (3B)

**9. `eos-with-second-turn`** — `<|endoftext|>` appears **mid-completion**, followed by a
fresh chat turn ("Human: ..." / "Assistant: ...") and a second answer, as if the sampled
conversation had rolled over into a new example. The extractor's fenced-span parsing
stops at the first closing fence, so the rollover is invisible to extraction *when the
first diff exists* — the second-turn diffs never reach git (first-well-formed-diff rule).
Detectable: yes — `EOS in text` and `Human:` after it.
Lands in: `WOULD_NOT_PARSE` (9), `PARSED_BUT_DID_NOT_APPLY` (2), `APPLIED` (1),
`UNATTRIBUTED` (1).
Counts: arm-a **13 × 3B**; 7B and 14B 0.

**10. `hallucinated-generic-target`** — the second turn's content: a generic Q&A about a
fictional Python script ("I have a Python script that uses the `requests` library...")
complete with its own fenced diffs against fictional files named `<your_script.py>` /
`<my_script.py>` — a hallucinated dataset-like example, unrelated to the task and to any
file in the checkout.
Detectable: yes — filename patterns plus the fixed turn template.
Lands in: the same buckets as shape 9 (co-occurs 13/13).
Counts: arm-a **13 × 3B**; others 0.

**11. `repeated-identical-diffs`** — the same diff fenced verbatim two to fifteen times in
one completion (a degenerate copy loop at the block level; the extreme case fences the
same 20-line stub ten times). Distinct from a multi-file patch: the repeated blocks are
byte-identical.
Detectable: yes — hash fenced bodies, count duplicates.
Lands in: `WOULD_NOT_PARSE` (12), `PARSED_BUT_DID_NOT_APPLY` (3), `APPLIED` (1, arm-a).
Counts: arm-a **12 × 3B**, 3 × 14B, 1 × 7B; budget-2048 3 × 14B.

**12. `phantom-assignment-lines`** — added lines whose content begins with `=` (the
left-hand side vanished): a `+` line like `<+        = foo()>`. Content-level corruption
inside otherwise diff-shaped hunks; not itself a parse failure (git reads it as text).
Detectable: yes — `^\+[ \t]*=`.
Counts: arm-a **5 × 3B**; 14B and 7B 0. (A sibling, visible in the same records: `+`
lines beginning with `=` appear together with lines that *are* prefixed — the model
losing a token mid-line, see §4.)

**13. `noop-hunks`** — a `-`/`+` pair whose two lines are byte-identical, so the hunk
changes nothing. The 14B signature of "patch-looking output with no edit in it".
Detectable: yes — adjacent `-`/`+` lines with equal content.
Lands in: `APPLIED` and `PARSED_BUT_DID_NOT_APPLY` when the surrounding hunks are right,
`WOULD_NOT_PARSE` when they are not.
Counts: arm-a **11 × 14B**, 1 × 3B, 1 × 7B; budget-2048 11 × 14B.

**14. `wrong-target-file`** — a diff aimed at a path outside the task's own sources:
observed once at a documentation/report file, once at a held test file (the reward-hack
shape the verifier's scope rule exists to catch — it never got that far), and in the
fictional `<your_script.py>`-class files of shape 10.
Detectable: partially — the fictional filenames are pure patterns; the doc/test targets
need the manifest's file list (the checkout layer, as in `attribution.py`).
Counts: 2 hand-verified 3B records (a diff aimed at a documentation/report file, and a
multi-file diff whose second file is a held test — the reward-hack shape), plus 13
fictional (shape 10).

**15. `header-without-hunk`** — the extractor's own fourth reason, observed exactly once:
a `diff --git` header and an index line carrying the ~600-digit counting run, then
nothing — no hunk at all (record `belay-afd096a4b2ea`, 3B).
Detectable: yes — it is `extract_patch`'s own bucket.
Counts: arm-a **1 × 3B**; budget-2048 0.

### Healthy content, for contrast

**15 (well-formed). `well-formed-diff`** — the extracted diff parses under `git apply
--numstat` and reaches the apply/content layer. These are the control: each base *can*
write a diff git accepts, so nothing here is "the bases cannot write diffs at all".
Counts: arm-a **14 × 14B** (9 `APPLIED` + 5 `PARSED_BUT_DID_NOT_APPLY`), 8 × 3B
(1 + 7), 4 × 7B (1 + 3); budget-2048 13 × 14B (8 + 5).

### Shapes that were expected and are **absent** (data-grounded absences)

Zero occurrences in all 208 completions: empty/whitespace output (`NO_OUTPUT` has no
records in either run); CRLF line endings; SVN-style (`Index:`), `diff -u`, `===`
separators, tildes-fenced, or JSON/XML-wrapped diffs; `Binary files` / `rename from` /
`similarity index` headers; markdown-bullet-only "here is what I changed" answers; a
fenced *code sample* as the answer (the `FENCED_WITHOUT_DIFF` bucket is 100% the
`im-start-loop`, not code samples — the PRD's "code sample" hypothesis occupies zero
records). A classifier does not need categories for any of these; the fix list in §5
should not spend effort on them.

---

## §3 Count table (run × attribution-cause × content-shape)

Values are records carrying the shape. Rows sum to more than the row's record count
because a record carries several shapes (co-occurrence is the norm, not the exception).

### arm-a (156 records)

| cause \ shape | im-start-loop | hunk-count-mismatch | hunk-body-dies-early | plain-unified-no-git-header | stacked-fence | git-header-b-missing-slash | index-line-garbage | eos-with-second-turn | hallucinated-target | repeated-diffs | phantom-assign | noop-hunks | header-without-hunk | well-formed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NO_DIFF_HEADER (33) | 33 | — | — | — | — | — | — | — | — | — | — | — | — | — |
| FENCED_WITHOUT_DIFF (10) | 10 | — | — | — | — | — | — | — | — | — | — | — | — | — |
| HEADER_WITHOUT_HUNK (1) | — | — | — | — | — | — | 1 | — | — | — | — | — | 1 | — |
| WOULD_NOT_PARSE (84) | 5 | 39 | 45 | 39 | 47 | 6 | 17 | 9 | 9 | 12 | 4 | 6 | — | — |
| PARSED_BUT_DID_NOT_APPLY (15) | 3 | — | — | 7 | 7 | — | 1 | 2 | 2 | 3 | 1 | 2 | — | 15 |
| APPLIED (11) | 1 | — | — | 9 | 10 | 1 | — | 1 | 1 | 1 | — | 5 | — | 11 |
| UNATTRIBUTED (2) | — | 1 | 1 | 1 | 2 | — | 1 | 1 | 1 | — | — | — | — | — |

### budget-2048 (52 records, 14B only)

| cause \ shape | im-start-loop | hunk-count-mismatch | hunk-body-dies-early | plain-unified-no-git-header | stacked-fence | repeated-diffs | noop-hunks | well-formed |
|---|---|---|---|---|---|---|---|---|
| WOULD_NOT_PARSE (38) | — | 31 | 7 | 38 | 37 | 3 | 6 | — |
| PARSED_BUT_DID_NOT_APPLY (5) | — | — | — | 5 | 5 | — | 2 | 5 |
| APPLIED (8) | — | — | — | 8 | 8 | — | 3 | 8 |
| UNATTRIBUTED (1) | — | 1 | — | 1 | 1 | — | — | — |

### Per-candidate shape totals (arm-a)

| candidate | im-start-loop | hunk-body-dies-early | hunk-count-mismatch | plain-unified | stacked-fence | index-line-garbage | eos+second-turn | hallucinated-target | repeated-diffs | well-formed |
|---|---|---|---|---|---|---|---|---|---|---|
| 3B (52) | 0 | 40 | 3 | 0 | 15 | 20 | 13 | 13 | 12 | 8 |
| 7B (52) | 52 | 3 | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 4 |
| 14B (52) | 0 | 3 | 35 | 52 | 51 | 0 | 0 | 0 | 3 | 14 |

**Cross-run delta (arm-a → budget-2048, 14B):** `hunk-count-mismatch` 35 → 32,
`hunk-body-dies-early` 3 → 7, `well-formed` 14 → 13, `APPLIED` 9 → 8. One previously
`APPLIED` record became `WOULD_NOT_PARSE` under the doubled budget; no `WOULD_NOT_PARSE`
became `APPLIED`. The shape mix barely moved, and the movement was *negative*.

---

## §4 The dominant findings

**What the bases wrote instead of an applicable diff:** the three candidates do not share
a failure mode — they share a *format contract* and violate it in three different,
per-model dialects. The 7B model wrote mostly **nothing but the chat template looping on
itself** — 43 of its 52 completions are pure token-repetition loops, and the remaining
nine escape the loop only near the token cap and write a diff: five of them a stub (a
header, one hunk, one to three lines — three of those stubs even omit the `---`/`+++`
pair, shape 8), four of them a complete diff in the plain-unified dialect (shape 4). The
3B model wrote the **full git-shaped skeleton** — `diff --git`,
a fake `index` line, `---`/`+++` — and then sabotaged the hunks: invented line counts,
garbage tokens on the index line, and hunk bodies that die at the first unprefixed line
(the model pasted file content without consistently adding the diff prefix). The 14B
model wrote the **plain unified dialect** — `---`/`+++` and hunks, no `diff --git` — with
hunk headers whose counts are invented rather than counted, so git's walk of the declared
count lands in the middle of the next hunk or past EOF. All three are format-contract
failures; the differences between them are *which part of the format* each base
reproduces reliably and which part it fabricates.

**Which wall does the evidence point at?** The evidence points at a **formatting wall**,
not the roadmap's other two forks. It is not a reasoning wall: 26 of 156 arm-a rollouts
(and 13 of 52 in budget-2048) produced diffs git parsed, and 11 applied cleanly — the
bases can reach the verifier, they simply almost never do — and the failing diffs'
*content* (when readable) is plausible, often task-relevant code, not gibberish. It is
not an extraction wall: the extractor located a diff in every record the attribution says
parse-failed; the defect is in the bytes the model wrote, and the extractor's "never
repair" rule correctly refuses to fix them. Two extractor-side observations still matter:
the extractor's reason strings call the 7B loop "prose" and "code sample" (a misreading
the classifier must not inherit), and the first-well-formed-diff rule silently hides the
3B second-turn rollovers. The fork this supports is therefore neither "easier task
stratum" nor "larger base" — it is the contract side the yield-probe PRD left open: **a
format-hardening response (structured/fenced-diff output, a pre-verifier diff validator,
retry on malformed output) is the intervention the data now names**, and without it the
pivot signal's premise — "the bases cannot fix these bugs" — remains untested, exactly as
the yield-probe correction said.

**Which shapes account for most failures?** Three shapes cover 138 of 156 arm-a records
(88%): `im-start-loop` (52), `hunk-body-dies-early` (46), `hunk-count-mismatch` (40). The
two parse-refusal shapes cover **all** 84 `WOULD_NOT_PARSE` records — 45 early-hunk-deaths
and 39 count-mismatches, exactly one each, no overlap, no remainder — and each maps
cleanly onto a candidate: 3B dies early in its hunks, 14B dies from invented counts, and
the loop is 7B's own collapse. **The doubling of the budget changed what the model wrote
in length, not in kind**: 38 completions were byte-identical, the 14 changed ones were
longer but the same dialect with the same count corruption, one `APPLIED` diff was even
broken by the extra length — a budget increase is not a fix for a format contract the
model never agreed to.

---

## §5 Open questions for the PRD

1. **Which shapes are distinguishable deterministically?** All fifteen are (see the
   detectability notes), and the three dominant ones most of all: the loop by line-ratio,
   the early hunk death by comparing the extracted diff's length against the completion's
   and inspecting the line that ended the walk, the count mismatch by re-walking hunks or
   by `git apply --numstat`. The hard cases are the *sub*-distinctions inside shape 3
   (bare-line vs fence-cut vs end-of-output), which need the walker's stop-reason exposed;
   worth doing, because bare-line deaths and budget truncation have different fixes.
2. **Which shapes are the same failure wearing different clothes?** The strongest
   candidates: (a) 7B's `git-header-without-file-lines` + stub = the same "hunk dies
   early" failure with an extra missing header pair; (b) 3B's `index-line-trailing-garbage`
   and `git-header-b-path-missing-slash` are cosmetic corruption that only kills when a
   hunk is *also* broken — the classifier should report them as markers, not causes;
   (c) `noop-hunks` inside 14B's `APPLIED` records mean "patch applies but edits
   nothing", which is content-level and belongs to a later layer, not to this classifier.
3. **The 7B loop needs a decision before it can be classified well**: is it a sampling
   configuration problem (the mlx adapter's stop-token / repetition handling), a model
   property, or evidence that the 7B base simply cannot follow the prompt? The loop is
   100% of 7B's output and 28% of the whole arm-a corpus, so the answer changes what the
   slice's finding claims about "the bases".
4. **Does the classifier own the `wrong-target-file` shape?** It needs the manifest's
   file list, which the dig's mandate keeps at the checkout layer (`attribution.py`
   already has the machinery); the PRD should decide whether the classifier takes
   declared paths and checks them against the task, or whether that stays a separate
   finding (the two verified records are few, but one of them is the reward-hack shape
   the project publishes a count for).
5. **The second-turn rollover is extractor-invisible today** (first-diff-wins). If a
   format-hardening response lets the model retry, the retry should see the *whole*
   completion — the rollover tells the retry the model's context window had already
   drifted off-task, which is different from "malformed diff".
6. **The extractor's reason strings need re-reading by the classifier, not reuse.**
   `NO_DIFF_HEADER`'s "the output is prose" and `FENCED_WITHOUT_DIFF`'s "a code sample or
   an explanation" are both false for 43 of 43 records in this corpus (they are loops).
   The classifier's labels must be content-grounded even where they agree with a bucket.
7. **What does the fixed distribution imply for the yield question?** 26 well-formed
   diffs reached the apply layer in arm-a (16.7% of rollouts; 25% in budget-2048). A
   format-hardening intervention can at most convert the malformed-diff rollouts into
   *content-eligible* rollouts — the PRD should pre-commit what fraction of the 84
   `WOULD_NOT_PARSE` rollouts must land in `PARSED_BUT_DID_NOT_APPLY` or better before
   the intervention is called effective, and it should not expect a budget increase to do
   it (the evidence says it does not).

---

## Summary (top findings)

1. The three bases violate the patch format in three different, per-model dialects: 7B loops on chat-template tokens, 3B writes full git-skeleton diffs whose hunks die on unprefixed lines, 14B writes plain unified diffs with invented hunk counts.
2. `im-start-loop` (52), `hunk-body-dies-early` (46), and `hunk-count-mismatch` (40) cover 138 of 156 arm-a records; the two parse-refusal shapes partition all 84 WOULD_NOT_PARSE records exactly (45 + 39, no overlap, no remainder).
3. The "prose"/"code sample" buckets are a misreading: all 43 7B NO_DIFF_HEADER/FENCED records are degenerate `<|im_start|>` repetition, not prose and not code samples.
4. 26 of 156 arm-a rollouts (16.7%) produced diffs git parsed, and 11 applied cleanly, so the wall is the format contract — not reasoning, and not the extractor; the roadmap's easier-stratum/larger-base fork is unsupported by this data.
5. Doubling the budget changed length, not kind: 38/52 completions byte-identical, one previously-APPLIED diff broke, none improved; a bigger budget is not a fix.
6. The evidence names a format-hardening response (structured output / diff validator / malformed-output retry) as the untested intervention; until it runs, the pivot signal's premise remains untested, as the yield-probe correction already said.
