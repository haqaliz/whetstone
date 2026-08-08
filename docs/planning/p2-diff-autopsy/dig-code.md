# Dig — `p2-diff-autopsy`: reuse map, constraints, and extension seams

**Dug 2026-08-09**, in `.claude/worktrees/feat-p2-diff-autopsy` (branch `feat/p2-diff-autopsy/aliz`).
Card: `docs/planning/p2-diff-autopsy/card.md`. No code was written; this note is the map for the
parent slice's classifier PRD. Everything cited is `file:line` against this worktree.

**The shape of the task, in one paragraph.** A classifier, offline, deterministic, stdlib-only, reads
stored bake-off transcripts (`src/whetstone/bakeoff/transcript.py` JSON-Lines records) and assigns
each completion a grounded content-shape cause, as a **finer partition of the existing `attribution.py`
buckets** (`card.md:46-47`). It must land in `src/whetstone/bakeoff/` (EXEMPT from the reward-path
AST guard), must not touch `src/whetstone/verify/`, and must publish nothing: breakdowns go to
gitignored roots only (`card.md:44-45`).

---

## §1 The reuse map

Every existing symbol the classifier should call rather than re-implement. "Why reuse" is stated
once per row in the strongest form that exists in this tree: **a copy is a second definition, and a
second definition is a figure that can disagree with itself** (`test_attribution.py:181-195` asserts
identity, not equivalence, for exactly this reason).

### 1.1 The extractor — the coarse pass, verbatim

| Symbol | Where | What it does | Why reuse beats re-implementation |
|---|---|---|---|
| `extract_patch` | `bakeoff/patch.py:148-187` | Locate the first well-formed unified diff in a completion, or return `NoDiff` with a sentence naming what was seen instead | The classifier's layer-1 answer must be **the same function object** the live run called (`scoring.py:435`), not a copy that "agreed on today's fixtures" — `test_attribution.py:181-195` pins this identity and would fail a parallel copy the moment `patch.py` changed |
| `Extracted` / `NoDiff` / `Extraction` | `patch.py:107-122`, `124-139`, `145` | The two-arm result type; `NoDiff` deliberately has **no `.diff`** | Reusing the types keeps the empty-patch confusion structurally impossible (`test_extraction.py:215-239`); a classifier that invents its own result shape recreates the trap `patch.py:8-18` exists to close |
| `_terminated` | `patch.py:313-320` | The single permitted repair: final `\n` if missing | The classifier must classify the *same text* the run extracted; re-implementing the newline rule is a second opinion on a measured fact |

### 1.2 The extractor's internals — the fine pass (the classifier's real dependency)

`extract_patch` collapses to one `Extracted` + four `NoDiff` reasons. The content shapes the card
names — *"prose, fenced code that is not a diff, header-without-hunk, corrupt hunk, wrong-path diff,
truncated mid-hunk"* (`card.md:29-32`) — mostly land **inside** `Extracted` today
(`patch.py:43-53`: absolute paths, CRLF, truncated mid-hunk are all deliberately extracted and left
for git to refuse). So the fine pass must re-walk the completion with the extractor's own eyes:

| Symbol | Where | What it does | Why reuse |
|---|---|---|---|
| `_HUNK_HEADER` | `patch.py:70` | The `@@ -a,b +c,d @@` regex, "the source of truth for where a hunk ends" | A second hunk-regex would disagree about optional counts (`patch.py:274-276`); the extractor's own anchor is what `git apply` measured against |
| `_GIT_HEADER` / `_OLD_FILE` / `_NEW_FILE` | `patch.py:75-77` | The three line-prefixes that open a diff | Same literal discipline; `_opens_a_diff` (`patch.py:226-237`) encodes the `---`-requires-`+++` rule that stops prose looking like a diff — re-implementing it is how a classifier invents a false "wrong-path" bucket |
| `_HEADER_PREFIXES` | `patch.py:82-99` | The metadata lines that may sit between header and hunk | Taken "from git's own output vocabulary"; a classifier that re-lists these will drift from the extractor the run used |
| `_fenced_spans` / `_fence_end` | `patch.py:190-210`, `213-223` | Fenced-block bodies as half-open ranges; an **unclosed fence runs to end of text** — the mid-patch token-limit shape | The unclosed-fence rule (`patch.py:193-196`) is the truncation signal for fenced output; losing it reports "no diff" for the run's most interesting failure |
| `_diff_span` / `_hunk_body` | `patch.py:240-269`, `272-300` | Walk a diff by the hunk headers' declared counts; a hunk that stops short of its count ends the walk | **This is the truncated-mid-hunk detector already written**: "The hunk stopped short of its own count: truncated output, or a miscount" (`patch.py:292-295`). The classifier's truncation cause should be this shape test, not a new one |
| `_bare` | `patch.py:303-310` | Strip terminator for parsing only | CRLF classification (`patch.py:48-51`) needs exactly this distinction: parse like LF, bytes stay CRLF |

**Seam note:** these are underscore-private, but the classifier lives in the same package
(`src/whetstone/bakeoff/`), and the identity-discipline precedent (`test_attribution.py:190-195`)
applies: import them, don't copy them. Whether the fine pass *should* call them directly or sit on
top of a thin addition to `patch.py` is a PRD decision — see §4.

### 1.3 The stored evidence

| Symbol | Where | What it does | Why reuse |
|---|---|---|---|
| `Transcribed` | `transcript.py:73-103` | One generation whole: candidate, task_id, prompt_sha256, prompt, completion | Fields are written field-by-field and decoded strict (`transcript.py:228-258`); the classifier reads `record.completion` — never re-deriving it |
| `Transcript.replay()` | `transcript.py:134-164` | Every record keyed by `(candidate, task)`; missing file = empty run; corrupt line = `TranscriptUnreadable`, **never a skip** | `attribution.main` already uses it (`attribution.py:475`). A classifier that re-parses the JSON-Lines itself is a second decoder that can disagree about schema drift |
| `TranscriptUnreadable` | `transcript.py:64-70` | Own exception type so a corrupt transcript is distinguishable from a missing one | Same raise-don't-skip contract (`transcript.py:29-34`): a classifier that dropped a line would attribute over fewer rollouts than the run produced |
| `Key` | `transcript.py:61` | The `(candidate, task_id)` pair | The two stored runs are separate files; both are read the same way (`card.md:44-45`) |

### 1.4 The attribution layer — the thing being made finer

| Symbol | Where | What it does | Why reuse |
|---|---|---|---|
| `Cause` | `attribution.py:75-121` | The eight existing buckets: `NO_OUTPUT` (:88), `FENCED_WITHOUT_DIFF` (:92), `HEADER_WITHOUT_HUNK` (:96), `NO_DIFF_HEADER` (:99), `WOULD_NOT_PARSE` (:105), `PARSED_BUT_DID_NOT_APPLY` (:110), `APPLIED` (:115), `UNATTRIBUTED` (:120). "A cause, deliberately not a verdict… **not** ordered, must never be reduced against one another" | The card's requirement is that the new fine causes *explain these rather than replace them* (`card.md:46-47`) — the mapping fine→`Cause` is an assertion, and `Cause` is the vocabulary it must land in |
| `NO_DIFF_MARKERS` | `attribution.py:134-139` | Bucket → verbatim fragment of each `NoDiff` site's sentence; "a fragment rather than the whole sentence because two of the four reasons are f-strings" | The bijection discipline's data. The classifier's coarse pass should flow through `cause_of_reason`, not re-match reasons |
| `cause_of_reason` | `attribution.py:168-180` | Reason → `Cause`, or `None`; `None` "rather than a fallback bucket, and rather than raising" | The **no-other-bucket pattern** the classifier must mirror for its own fine causes: unrecognised shape → named, not guessed (`card.md:33`) |
| `attribute` / `attribute_all` | `attribution.py:183-210`, `213-224` | Replay one/every rollout; checkout-less rollouts are `UNATTRIBUTED` **by name** | The classifier's per-completion entry point should call `extract_patch` the same way (`attribution.py:191`) so the coarse and fine passes share one first result |
| `Attribution` | `attribution.py:142-166` | `(candidate, task_id, cause, detail)` — "the only field anything counts" is `cause` | If fine causes flow as a new field, this frozen dataclass is the shape to extend — see §3 for what that costs |
| `breakdown` | `attribution.py:227-242` | Per-candidate cause counts; causes that did not occur are **absent, never zero** | The classifier's breakdown must copy this: "a zero here would be indistinguishable from a bucket that has stopped matching anything" |
| `_FOLD` | `attribution.py:257-264` | Cause → published report vocabulary (`no_diff`, `not_applied`); `APPLIED` absent (the report splits it three ways), `UNATTRIBUTED` absent (no counterpart) | **The model for how fine causes rejoin published buckets** — see §3 |
| `to_report_counts` / `compare_to_counts` / `_recorded_counts` | `attribution.py:287-301`, `304-346`, `349-364` | Fold causes into the report's vocabulary and compare, absent-is-never-zero | The classifier's mapping assertion should be built in this shape (a pure function + a test that shows it failing) |
| `_against_checkout` / `_refusal` | `attribution.py:367-405`, `396-405` | Ask git parse-vs-apply on a throwaway copy; unknown `PatchError` → `UNATTRIBUTED` | If the classifier needs the parse/apply split per fine cause (e.g. to confirm "wrong-path" reaches git's apply refusal), this is the read-only path — including the copy (`attribution.py:386-388`) so attributing never dirties a shared checkout |
| `_attributed` | `attribution.py:408-415` | One construction site for `Attribution`, "so the key cannot drift" | Any new record type should get the same single-site rule |
| `main` (CLI) | `attribution.py:420-533` | `python -m whetstone.bakeoff.attribution`; missing transcript → exit 2 with a named reason (`:464-473`), never an empty breakdown; document schema `"whetstone-attribution/1"` (`:499`) | The classifier's CLI should mirror this shape: `--transcript` required, `--out` where the breakdown is written, absence of the checkout layer named rather than silent (`:428-431`) |

### 1.5 The live path the replay mirrors

| Symbol | Where | What it does | Why reuse |
|---|---|---|---|
| `score` | `scoring.py:357-449` | The live path: `completion = generator.generate(prompt)` (:432) → `extraction = extract_patch(completion)` (:435) → `NoDiff` never reaches a verifier (:436-440) → `_verify` (:442-449) | The classifier must reproduce **exactly this call order** on the stored text (`test_attribution.py:198-220` proves stored completions re-extract identically); the "no diff → no verifier" branch (:436-440) is what makes `NO_DIFF` a different claim from `NOT_APPLIED` |
| `Outcome` / `_PATCH_APPLY` / `_PATCH_SCOPE` | `scoring.py:87-130`, `:79`, `:84` | The published zero-vocabulary (`NO_DIFF`, `NOT_APPLIED`, `OUT_OF_SCOPE`, `NOT_SOLVED`, …) | Fine causes must eventually explain these tags; `_FOLD` already maps the coarse ones |
| `_verify` / `_classify` | `scoring.py:452-509`, `512-529` | Run both verifiers; `NOT_APPLIED` only when `("patch-apply",)` is the *sole* verdict | Read-only reference for what a fine cause is *explaining*; nothing here is called by a classifier |
| `generator.Generator` | `generator.py:46-70` | The one-method seam | The classifier must **not** import anything that touches this (see §2, no-mlx); `StubGenerator` (`generator.py:73-114`) is the test-double pattern new tests inherit |
| `mlx_runtime` (`DEFAULT_MAX_TOKENS`, `generate`, `_generate`) | `mlx_runtime.py:86`, `206-232`, `287-302` | The token budget (1024 default) and the pinned call shape | **Read-only evidence for the truncation disclosure**: `generate` returns a bare `str` with no finish reason (`mlx_runtime.py:206-232`; `_generate` passes `max_tokens` and `sampler` and nothing else, `:287-302`) — this is why truncation is inferred from shape, never measured (`attribution.py:101-104`, `understanding.md:139-146`) |

### 1.6 The journal / run layer (context, not code to call)

`Journal`/`Step` (`journal.py:55-131`) mirror the transcript's JSON-Lines discipline; the classifier
does **not** read journals. `run.py` flags the classifier's sibling concerns: `--transcript` is
undefaulted and refused under `--out` (`run.py:776-785`, `886-907`; test `test_run_transcript.py:156-184`),
and `--out`/`--workspace` split published from scratch (`run.py:708-717`). The gitignored artifact
roots are `/runs/`, `/checkpoints/`, `/reports/local/` (`.gitignore:20-24`), asserted by
`test_transcript_locality.py:34-101`. The stored transcripts the classifier reads are the arm-A and
budget-2048 runs in the **primary checkout** (`card.md:25-26`); the worktree keeps none
(`card.md:66-67`).

---

## §2 The constraints list

Each guardrail, its enforcing test, and the exact behaviour the new module must satisfy.

| # | Guardrail | Enforcing test | What the new module must do |
|---|---|---|---|
| 1 | **Locality: all new code in `src/whetstone/bakeoff/`** | `tests/test_reward_path_scope_is_partitioned.py:210-230` (partition: nothing neither guarded nor exempt; bakeoff is EXEMPT at `:100-117`), `:233-248` (stale exemptions fail), `:251-266` (exemption must carry a written reason) | Every module lands under `bakeoff/`. A new **top-level** file under `src/whetstone/` fails the partition test on its own; a new module under `verify/` or `tasks/` additionally fails the AST walk (constraint 5) |
| 2 | **One-way dependency: nothing guarded imports bakeoff** | `tests/test_reward_path_scope_is_partitioned.py:356-389` | The classifier may import `whetstone.verify.repo` (`declared_paths`, `apply_patch` — read-only, exactly as `attribution.py:61` does) but the reverse must never happen; the exemption's written reason (`:100-117`) is only sound while that assertion holds |
| 3 | **`src/whetstone/verify/` untouched** | No committed test yet — the pattern is `plan_20260805.md:218-219`: "`git diff --stat origin/master -- src/whetstone/verify/` is **empty** (AC8). Add it as a test if no equivalent exists." Grep of `tests/` confirms **no equivalent exists**. `card.md:52-53` makes it an acceptance criterion of this very slice | The slice must ADD the diff-stat test (watched failing first, `CONTRIBUTING.md:56-60`), then never touch a `verify/` file. Note `test_attribution.py:144-162` and `test_extraction.py:175-193` already exercise real git against fixtures — evidence the verifier's behaviour is pinned from the outside, which is how a classifier tests the parse/apply split without modifying it |
| 4 | **Reward-path guard not widened; `bakeoff/` stays EXEMPT** | `tests/test_no_inference_on_reward_path.py:104-109` (`GUARDED_ROOTS`), `:314-335` (the ban), `:175-204` (`_modules` per-root anti-dead-root) | New code in `bakeoff/` is *inside* the exemption — adding the module requires **no** change to either guard file, which is precisely the point (`prd.md:170-174`) |
| 5 | **No inference import, anywhere in module or test** | `tests/bakeoff/test_attribution.py:538-559` (AST walk over module **and** test file; `FORBIDDEN_IMPORT_ROOTS` at `:113-115` is deliberately wider than `mlx`: torch/transformers/openai/anthropic/huggingface_hub too; anti-vacuity at `:559`) | The classifier gets the same two-file walk; the "no mlx" pattern is explicitly the card's (`card.md:29-30`). Also keep `pyproject.toml`'s `mlx` extra untouched (`plan_20260805.md:19-21`) |
| 6 | **One-home: `reports/` holds exactly the three baseline artifacts** | `tests/bakeoff/test_report.py:961-994` (exact file list, `:984-987`; the move-precedent in its docstring `:964-970`), `tests/bakeoff/test_transcript_locality.py:73-101` (same list, second copy), `tests/test_docs.py:723-744` (no report without its pre-registration) | The classifier publishes nothing. No breakdown JSON, no analysis file, no figure may land under `reports/` — and the guard's docstring records the one allowed move (different generation contract, argued in the docstring); this slice has no such argument (`card.md:49-51`) |
| 7 | **Figures about a model live in exactly one home; nothing restated** | `tests/test_docs.py:577-609` (no `%`/percent in PREREGISTRATION, plus its own stated rule), `:248-297` (no present-tense no-number claims in CLAUDE.md/README.md/CHANGELOG.md; ROADMAP only inside its quoted correction), `tests/bakeoff/test_report.py:998-1010` (ROADMAP's no-figure sentence + prereg no-proportion) | Any count the classifier produces is a figure about a model in the sense of `spec.md:92-95` (AC9: the breakdown "is a figure about a model and may not be written into any document"). Breakdown output goes to a gitignored root; the *finding* goes into the slice's written finding (`card.md:48-49`) without numbers |
| 8 | **Gitignored homes for transcripts and breakdowns** | `.gitignore:20-24` (`/runs/`, `/checkpoints/`, `/reports/local/`, `/tasks/local/`, `/_sandbox/`); `tests/bakeoff/test_transcript_locality.py:47-71` (`git check-ignore` with the trailing-slash form, `:29-34`), `:73-101` (opposite-sign control: `reports/` must stay committable) | Breakdown output must be writable only where `git check-ignore` answers "ignored". The classifier's CLI should either refuse non-ignored `--out` or assert it in tests the way `test_transcript_locality.py` does |
| 9 | **Transcripts under a published output directory are a usage error** | `tests/bakeoff/test_run_transcript.py:156-184`; `run.py:886-907` (`_refuse_published_transcript`, resolved paths) | If the classifier takes a `--transcript` path, the same privacy refusal applies — completions quote private donor code (`run.py:140-151`) |
| 10 | **Bijection discipline: taxonomy read from `patch.py`, never invented; no "other" bucket** | `tests/bakeoff/test_attribution.py:299-332` (every `NoDiff` site covered by exactly one bucket; every bucket covers a site; anti-vacuity `:310-314`), `:335-351` (planted fifth reason fails), `:354-364` (runtime: unrecognised reason → `UNATTRIBUTED` by name) | The classifier's fine causes get the same treatment in new tests: a synthetic planted shape fails, an unrecognised shape is named not guessed (`card.md:33`, `card.md:57-62`). Note the bijection test **only** covers `patch.py` sites — the classifier's own taxonomy needs its own completeness control (see §3) |
| 11 | **Absent is never zero** | `attribution.py:227-242` (breakdown omits what did not occur), `test_reproduction.py:96-104` | New breakdown code copies this; a fine cause with no count is absent, never zero-filled |
| 12 | **`UNVERIFIED`/`UNATTRIBUTED` semantics untouched** | `attribution.py:29-32`, `:117-120`; `test_attribution.py:452-475` | The classifier's terminal for "could not be asked" is named, countable, and never folded into a neighbour |
| 13 | **No placeholders, no invented numbers** | `tests/test_docs.py:554-574` (no placeholder in PREREGISTRATION), `CLAUDE.md:119` ("do not invent one") | The PRD names every open item with the amendment that closes it; no figure appears in any committed document |
| 14 | **Determinism** | `test_extraction.py:488-503` (same text → same extraction), `test_generator_contract.py` (seam) | Same input → same fine cause, asserted (`card.md:42`); no iteration over sets/dicts whose ordering can vary |
| 15 | **The classifier must not need the model back** | `test_attribution.py:27-31` (module docstring: an analysis that needed the model would be "a re-run wearing a replay's name") | Reuse `Transcript.replay()` + `extract_patch`; never `MlxGenerator` |

---

## §3 The extension seams — where the classifier sits, and what moves

### 3.1 The position: beside `attribution.py`, refining its buckets

The card fixes the relationship: *"The taxonomy explains the existing `attribution.py` buckets rather
than replacing them — the new cause is a finer partition of an existing bucket, and the mapping is
asserted"* (`card.md:46-47`). Three structural facts force the seams:

1. **The extractor is one-to-many.** Four `NoDiff` reasons (`patch.py:158-161`, `174-178`,
   `180-183`, `184-187`) ↔ four coarse causes via `NO_DIFF_MARKERS` (`attribution.py:134-139`); but
   `Extracted` is a single value covering CRLF, absolute paths, truncation and correctness
   (`patch.py:43-53`) — exactly the shapes the classifier must split. So the classifier's fine pass
   operates on completions that are already `Extracted`, and must re-walk them with `patch.py`'s own
   internals (§1.2). **It cannot be a pure re-labelling of `attribute()`'s output — the fine
   information does not survive `extract_patch`'s collapse.**
2. **The fine causes map down, not across.** Coarse → published is already a fold (`_FOLD`,
   `attribution.py:257-264`). The classifier's fine → coarse mapping is the same shape one level
   down: e.g. *wrong-path diff → `PARSED_BUT_DID_NOT_APPLY`*, *truncated-mid-hunk → `WOULD_NOT_PARSE`*
   (inferred — see §4), *absolute-path → `PARSED_BUT_DID_NOT_APPLY`*. The mapping is asserted
   (`card.md:47`) in the `_FOLD` style: a pure dict + a test that shows a missing entry fails.
3. **The one-home and figures rules are untouched because the classifier publishes nothing.** The
   comparison machinery (`to_report_counts`/`compare_to_counts`, `attribution.py:287-346`) stays as
   is; the classifier's output is a gitignored local artifact (`card.md:44-45`).

### 3.2 What the bijection test does to a new cause — precisely nothing (and that is the trap)

`test_attribution.py:299-332` walks `patch.py` and asserts a bijection between `NoDiff(...)`
construction sites and `NO_DIFF_MARKERS` keys. It is **silent on `Cause` members**: `claimed ==
set(NO_DIFF_MARKERS)` (`:326-332`) constrains the mapping dict, not the enum. Consequences:

- Adding a fine-cause enum member does **not** fail any existing test — the "no other bucket"
  discipline for the classifier must be enforced by **new** tests, in the shape of
  `test_attribution.py:335-351` (plant a fifth shape, watch it fail) plus a fixture-per-fine-cause
  completeness control (every fixture maps to exactly one fine cause; `card.md:42`).
- The classifier's taxonomy is anchored where `attribution.py`'s is: to **construction sites**. But
  the shapes it splits are mostly `Extracted`-side (`patch.py` has no construction sites for them —
  CRLF/absolute/truncated are all the same `Extracted` call at `patch.py:170`). So the fine
  taxonomy's anchor cannot be "a site in `patch.py`"; it must be *fixture shapes replayed through
  real git* — the `test_attribution.py:144-162` / `test_extraction.py:175-193` pattern (real `git
  apply` against a throwaway checkout). This is the one place the classifier cannot inherit the
  discipline verbatim and must extend it.

### 3.3 What breaks if a new member is added to `Cause`

Nothing fails in tests; two things break semantically:

1. **`to_report_counts` passes unknown causes through**: `_FOLD.get(cause, cause.value.lower())`
   (`attribution.py:299`) — a fine cause not in `_FOLD` would enter the published report vocabulary
   under its own lowercased name. If it *is* folded (the intended use, `card.md:46-47`), the fold is
   the assertion; if it is not, the leak is silent.
2. **`compare_to_counts` then reports a divergence on every such cause**: `_recorded_counts`
   keeps only `_FOLD.values()` fields from the record (`attribution.py:360`), so the replay side
   carries a field the record side lacks → divergence, because absent-is-never-zero
   (`test_reproduction.py:96-104`). A clean replay becomes noisy until the cause is folded or
   dropped — which is the honest behaviour, not a bug, but a caller must know it.
3. **The enum's own stated contract goes stale**: `attribution.py:82-84` — "The first four are
   `patch.py`'s own `NoDiff` reasons… The rest are what a located diff met when it reached git."
   Content-shape causes (truncation, wrong-path, CRLF) are neither; adding them to `Cause` requires
   rewriting that sentence and the module docstring's account (`attribution.py:11-19`).
4. **The CLI document schema is versioned**: `"schema": "whetstone-attribution/1"`
   (`attribution.py:499`) — new cause names flowing into `attribution.json` are a schema change
   whether or not the string is bumped.

### 3.4 Minimal-change options, with costs

| Option | What it is | What it touches | Cost / risk |
|---|---|---|---|
| **A. New module beside** (recommended shape) | `bakeoff/classify.py` (or similar) with its own fine enum, fine→`Cause` mapping asserted, own CLI, own AST-walk test, own fixture-per-cause corpus. Coarse pass = `extract_patch` + `cause_of_reason`, fine pass = `patch.py` internals | Zero changes to `attribution.py`, `patch.py`, `verify/`, or the guards | Two vocabularies that must be kept in step — the cost is the mapping assertion + a test that shows it failing; the reward is that the frozen, heavily-tested attribution module never moves |
| **B. Extend `Cause`** | Add fine members to the existing enum + extend `_FOLD` | `attribution.py` (enum docstring `:75-84`, `_FOLD` `:257-264`, module docstring `:11-19`), possibly `to_report_counts` `:299`, the CLI schema `:499`, and the parametrised corpus `test_attribution.py:95-103` if fine members become reachable causes | Touches the module the whole slice is defined as *extending*; the enum's contract sentence must be rewritten; every later reader of `attribution.py` inherits the fine causes whether they want them or not |
| **C. Replace `NO_DIFF_MARKERS`** | Make the coarse mapping finer in place | `attribution.py:134-139` + the bijection test `test_attribution.py:299-332` | **Rejected**: breaks the one-site-one-bucket anchoring, and the PRD flags an invented taxonomy as its 🔴 (`prd.md:244-247`) — replacing the anchored mapping with a content-based one is exactly the "plausible partition invented here" the discipline refuses |
| **D. Extend `Attribution` with a fine-cause field** | `Attribution.cause` stays the coarse bucket; a second field carries the fine cause | `attribution.py:142-166`, the single construction site `_attributed` (`:408-415`), `main`'s document `:508-516`, and the fold | Needed only if fine causes must ride the *same* records; if the classifier produces its own records beside `Attribution`, this is unneeded. Frozen dataclass + one construction site keeps the cost small (option D is compatible with A) |

The card's own language — *"explains the existing buckets rather than replacing them"*
(`card.md:46-47`) — plus AC4's identity test (`test_attribution.py:181-195`) point at **A (+D if
needed)**: leave the attribution module's eight-cause world intact, assert the refinement as a
mapping, and give the fine taxonomy its own fixture-backed completeness control.

---

## §4 The open items the PRD must decide

1. **Token-cap measurability — the inherited inference, now load-bearing.** `mlx_runtime.generate`
   returns text with no finish reason (`mlx_runtime.py:206-232`, `287-302`); truncation is
   *inferred from shape* (hunk declares more lines than present, `patch.py:250-252`, `292-295`), and
   every existing document says so (`attribution.py:101-104`; `understanding.md:139-146`:
   "Truncation was *inferred from the shape of a diff* and never measured… the spec named that
   inference as open, and it was then reasoned from as settled"). The classifier must decide: is
   *truncated-mid-hunk* a measured shape cause, or an explicitly-labelled inference rendered
   separately from measured causes — and which wording carries that disclosure into the breakdown
   document?
2. **Where the breakdown may be written.** The card fixes "gitignored run artifacts only"
   (`card.md:44-45`), but the mechanics are open: does the classifier's CLI refuse a non-ignored
   `--out` (the `_refuse_published_transcript` shape, `run.py:886-907`), or do tests assert the
   output root via `git check-ignore` (`test_transcript_locality.py:47-71`)? The latter leaves a
   foot-gun for the operator; the former needs a test on the refusal.
3. **New module vs. extension** (§3.4, option A vs B). The recommendation is A; the PRD must say so
   and state why `attribution.py` stays frozen.
4. **How the fine cause maps onto the published bucket so the one-home/figures rules hold.**
   The mapping fine→`Cause` is asserted (`card.md:46-47`); but the coarse `_FOLD`
   (`attribution.py:257-264`) already decides which *published* fields exist. The PRD must pin the
   two-step composition (fine → `Cause` → `no_diff`/`not_applied`) and confirm the classifier's own
   outputs are excluded from `reports/` — which `test_report.py:961-994` enforces.
5. **What "read the unparseable diffs" means as a *method*.** The correction says "no fourth fix
   should be proposed before someone reads what the unparseable diffs actually contain"
   (`prd.md:84-89`); the card says the categories "must be derived from what the transcripts
   actually contain, allowed to change once read" (`card.md:57-62`). But the transcripts are
   gitignored, hold private donor code, and are not in this worktree (`card.md:66-67`). The PRD must
   decide the sampling protocol: how shapes are observed in the primary checkout's runs and turned
   into **synthetic replicas** (`card.md:68-70`) without a verbatim completion ever reaching a
   committed file.
6. **Do fine causes need the checkout layer?** Splitting *wrong-path* (applies to nothing, git's
   numstat parses it — `test_attribution.py:372-390`) from *corrupt hunk* (git refuses to parse —
   `:393-409`) requires real git against a throwaway copy (`attribution.py:386-388`). The PRD must
   say whether the classifier's per-completion pass pays that cost, or whether shape-only signals
   (path spelling, hunk counts) are the partition, with git used only as a confirmation control —
   the cost difference is per-rollout `shutil.copytree` vs. pure string work.
7. **CLI surface.** Mirror `python -m whetstone.bakeoff.attribution` (`attribution.py:420-533`) with
   `python -m whetstone.bakeoff.<classifier>`? Which flags (`--transcript` per run, repeatable for
   arm-a + budget-2048, or one `--runs` root)? Whether `--report` comparison is offered at all in
   this slice.
8. **What the finding document may claim.** AC4 (`card.md:48-51`) requires a written finding naming
   the wall (format / anchoring / reasoning) with **no figure about a model outside gitignored
   artifacts** — the PRD should pre-commit the disclosure sentences (shape-inference, non-public
   artifact location) so the finding cannot drift into publishing.

---

## §5 Traps for the implementer

1. **The bijection test will not save you.** Adding a fine cause to an enum breaks nothing
   (§3.2). The "no other bucket" rule must be built fresh: fixture-per-cause completeness control +
   a planted-shape test, both watched failing first (`CONTRIBUTING.md:56-60`).
2. **Never copy `extract_patch` — and never copy its regexes.** `test_attribution.py:190-195` pins
   function identity; a second `_HUNK_HEADER` or `_HEADER_PREFIXES` literal in the classifier
   drifts from the extractor the run used and no test will notice. Import the privates (§1.2).
3. **The one-home guard is exact and duplicated.** `test_report.py:979-994` **and**
   `test_transcript_locality.py:91-96` both pin the three-file list under `reports/`. A breakdown
   JSON committed anywhere under `reports/` fails both; its docstring precedent
   (`test_report.py:964-970`) records that moving the guard requires an argument this slice does
   not have (`card.md:49-51`). Also `tests/test_docs.py:723-744` — no report without
   `PREREGISTRATION.md`.
4. **EXEMPT ≠ unguarded.** `bakeoff/` is exempt from the *inference* ban
   (`test_reward_path_scope_is_partitioned.py:100-117`), but the classifier still carries its own
   no-inference walk (`test_attribution.py:538-559`) and must not import `mlx_runtime`/`run.py`
   (which pulls `mlx_lm` transitively). The one-way edge is separately enforced
   (`test_reward_path_scope_is_partitioned.py:356-389`) — nothing under `verify/` may import the
   classifier, so keep any shared parse/apply logic on the `bakeoff` side.
5. **`verify/` has no committed unmodified-guard yet.** `card.md:52-53` requires
   `git diff --stat origin/master -- src/whetstone/verify/` empty — no test exists for it (grep of
   `tests/` finds none); the slice must write it. Meanwhile, the *behaviour* of `verify/` is pinned
   from outside by `test_attribution.py:144-162` and `test_extraction.py:175-193` (real git), so a
   classifier that shells out to git must scrub config exactly as `test_attribution.py:118-141` does
   (`GIT_CONFIG_GLOBAL=/dev/null`, etc.) or a developer's `apply.whitespace=fix` changes the split.
6. **Stale claims in docs are guarded.** `tests/test_docs.py` hunts placeholder markers
   (`:554-574`), proportions (`:577-609`), and present-tense no-number claims (`:248-297`); the
   ROADMAP's no-figure sentence is pinned (`test_report.py:998-1004`). A PRD or finding that quotes
   a classifier count, or writes "TBD", fails the suite.
7. **Trailing-slash traps in ignore checks.** `git check-ignore runs` (no slash) answers "not
   ignored" for an absent directory — the load-bearing form is `runs/`
   (`test_transcript_locality.py:29-34`, citing `test_tasks_layout.py`).
8. **Do not restate `reports/baseline/` figures anywhere new** — the "one home" rule is also the
   determinism rule: "a figure quoted twice is a figure that can disagree with itself"
   (`CLAUDE.md`). The classifier's finding describes walls, not numbers, outside the gitignored
   artifacts (`card.md:48-51`).

---

## Fixture discipline (§8 of the brief) — what committed fixtures contain

- **`tests/bakeoff/test_attribution.py` and `tests/bakeoff/test_extraction.py` fixtures are fully
  synthetic**, hand-written one-line toy functions: `adder.py` (`def add(a, b): return a - b`),
  `multiplier.py`, a held `tests/test_addition.py`. None contains donor-derived content. The
  exceptions to "hand-written" are: `test_extraction.py:657-720`, which feeds a **real `git diff`
  produced by git against a synthetic two-file checkout** (`m.py`/`n.py`) — real in *shape*, toy in
  *content* — and `test_attribution.py:118-141`, which shells out to real git against a one-file
  synthetic repo.
- **The repository fixtures** (`tests/fixtures/repos/donor.py`, `mined.py`, `packaged.py`,
  `locked.py`) build synthetic donors: a "calculator with four bugs in it" (`donor.py:301`),
  deliberately toy conftest files (`donor.py:36-97`), a synthetic `uv.lock` produced by real `uv`
  (`packaged.py:112-131`).
- **One place a real-donor fact reaches a committed fixture**: `packaged.py:54-56` — the comment
  that `packages = ["src/calc"]` is "what `donor A` — the first real donor, and the repository this
  defect was found against — declares". That is a metadata *shape* (a pyproject packaging line),
  not donor code, and it is cited as the reason the fixture exists. No other committed test file
  references donor content, and no verbatim completion from any run is committed anywhere.
- **The rule for the new slice is explicit**: fixtures must be *"synthetic replicas of observed
  shapes, never verbatim completions"* (`card.md:68-70`); raw output and derived breakdowns stay in
  gitignored roots. The new module's tests should follow the `test_attribution.py` pattern exactly:
  module-level synthetic completion constants (`:65-103`), a real-git checkout fixture
  (`:144-162`), and a no-inference AST walk over module and test file (`:538-559`).

---

## Summary (6 lines)

The classifier reuses, never copies: `extract_patch` + `Cause`/`NO_DIFF_MARKERS`/`cause_of_reason`
from `attribution.py:134-180`, `Transcript.replay()` from `transcript.py:134-164`, and `patch.py`'s
own internals (`_hunk_body:272-300`, `_opens_a_diff:226-237`) for the fine pass — with identity
asserted the way `test_attribution.py:190-195` pins it. It lands in `bakeoff/` (EXEMPT,
`test_reward_path_scope_is_partitioned.py:100-117`), carries its own AST no-inference walk
(`test_attribution.py:538-559`), and publishes nothing: breakdowns to gitignored roots only, with
`test_report.py:961-994` and `test_transcript_locality.py:73-101` pinning `reports/` untouched and
the `verify/`-unmodified diff-stat test (`card.md:52-53`) still to be written. The fine causes sit
**beside** `Cause` as a finer partition with an asserted fine→`Cause` mapping (`card.md:46-47`);
adding members to `Cause` itself breaks no test but silently leaks into
`to_report_counts:299` and diverges `compare_to_counts`, so option A (new module) is the
minimal-change seam. The bijection test is silent on new causes — the "no other bucket" rule must
be rebuilt as fixture-per-cause completeness plus a planted-shape test. Truncation stays an
inference from shape (`mlx_runtime.py:206-232` has no finish reason; `attribution.py:101-104` says
so), and the PRD must decide the sampling protocol that turns gitignored, donor-quoting transcripts
into synthetic replicas (`card.md:66-70`) — never verbatim content, as no committed fixture does
today.
