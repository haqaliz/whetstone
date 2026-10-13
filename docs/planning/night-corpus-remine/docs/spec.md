# Spec — docs

**Aspect 4 of 4** for `night-corpus-remine` (`../prd.md`). Owns **S2** in full and the repo's
write-up rule: the night sheet's re-mine block, the runbook guard extension, the `docs/STATUS.md`
entry, the `CHANGELOG.md` `[Unreleased]` section, the `docs/ROADMAP.md` § 13 dated note, and the
**boundary reading** of `PREREGISTRATION.md` § 3 plus the guard that pins it. **Unit:**
`feat/night-remine-before-draw/aliz` (`../understanding.md`). **Written:** 2026-10-11.

**Depends on:** the `remine` aspect (`../remine/spec.md` — the `--remine*` flags on
`whetstone run --night`, `cli.py:262-459` per `../remine/spec.md:137-151`, and the four
`run_night` parameters, `../remine/spec.md:115-135`) and the `record` aspect (`../record/spec.md`
— `task_set.remined`, `../record/spec.md:31-53`). Both must be on the branch **before** the
runbook's command is edited, because the runbook guard checks every flag against the shipped
parser (`tests/test_night_runbook_guards.py:349-363`, `_parser_flags` at `:223-235`). As read on
2026-10-11, neither exists in `src/whetstone/` yet (`git status` shows only the planning files
untracked). **Provides:** the sheet the operator runs, and the on-the-record write-up of the
capability. **Depended on by:** nothing.

**Core-loop element:** ② (the night's record of the corpus it grew). The reward (①) is untouched
and the held-out split (③) does not move; `UNVERIFIED` is still not a win.

## Problem slice and outcome

The `remine` and `record` aspects make the night grow its training pool and record the delta.
Neither writes anything an operator or a future reader can act on: the night sheet
(`docs/planning/p2-rollouts/night-door/runbook.md`) still runs a frozen corpus, the pre-registration
never says whether training-pool growth is a § 3 change, and no present-tense document records that
the § 13 gap is closed.

The sharpest open question in the whole unit is a **policy reading that is asserted nowhere in the
repo today** (`../understanding.md:94-96,135-139`): `PREREGISTRATION.md` § 3 lists "the task set"
among the pinned inputs and says a change to any pinned input "invalidates the series"
(`PREREGISTRATION.md:131-135`). Does the *training* pool count? The interview resolved that § 3's
"task set" means the **scoring** held-out split, so training-pool growth needs no amendment and the
night records the delta instead (`../prd.md:67-71,151-155`). This aspect records that reading
explicitly and honestly, pins it with a guard, and does not overclaim it.

Outcome: the operator's sheet re-mines before it draws, the tree's present-tense documents state
the new truth, and a later edit cannot silently drift the boundary reading.

## In scope

### R1 (S2) — the night sheet's re-mine block, held by the runbook guard

`docs/planning/p2-rollouts/night-door/runbook.md` gains a re-mine block on the **night** command
only (`runbook.md:133-154` is the night block; the probe block is `:84-106`), and
`tests/test_night_runbook_guards.py` is extended, **watched failing first**, to hold it.

The block:

- adds `--remine $DONOR --remine-label donor-a --remine-out $REPO/tasks/local/remined
  --remine-limit 5` to the night command, after `--tasks` (`runbook.md:135-136`);
- declares the donor as an operator-declared anchor, exactly as `$REPO` is declared
  (`runbook.md:8-10`), because a committed sheet that names one operator's home directory publishes
  it (`runbook.md:12-13`) — add `export DONOR=/absolute/path/to/your/donor/checkout` beside the
  `export REPO=...` line;
- states, in prose: the re-mine runs at the top of the night, before the corpus is loaded; the
  training-only root is gitignored and never the committed corpus; the `--remine-limit` is the cost
  bound (mining is hours per candidate, `../prd.md:156-158`); a donor that mints nothing — absent,
  non-repository, or unprovisionable — is a no-op, never a failure; the held-out split does not
  move and the delta is recorded in the ledger's `task_set.remined`; a night **without** the flags
  is byte-identical to today.

**The probe block does not re-mine.** The probe validates the chain cheaply before a night is
committed to (`runbook.md:78,108-114`); a re-mine is hours, so paying it in the probe and again in
the night is the cost the limit exists to bound. The probe's task set therefore differs from the
night's by the re-mine delta; the sheet must say so, because the pre-committed decision rule is
about the control arm and the seed map, not the exact task set (`runbook.md:127-129`).

The guard additions (all in `tests/test_night_runbook_guards.py`, in its own `DOOR`-keyed shape,
`:66-220`):

- the night block passes all four `--remine*` flags and the probe block passes none;
- `--remine-out` is anchored (`$REPO/...` or absolute — `_is_anchored`, `:152-153`);
- `--remine` is `$DONOR` and the sheet exports `DONOR` (`_exports_repo`'s donor twin, `:156-158`);
- the prose carries the training-only-root and cost-bound sentences (a `_flat` substring pin, the
  `:161-169` style).

`WRITABLE` (`:131`) is deliberately **not** extended: it is asserted against every door block
(`test_the_night_commands_writable_paths_are_absolute`, `:366-387`), and the probe block has no
`--remine-out`, so a 4th entry there would fail the probe. `--remine-out` is asserted on the night
block by its own test.

### R2 (write-up rule) — the `docs/STATUS.md` entry

A new entry at the top of `docs/STATUS.md` (append-only, newest first — the intro ends at
`STATUS.md:10`, the current top entry begins at `:13`), in the existing style: a bold dated
headline naming the unit slug, then what shipped, then an honest "what did not happen". It must
state, at minimum:

- the night re-mines before it draws (the flags, the skip-set, the training-only root, the ledger
  `task_set.remined`);
- the boundary reading (R5) and where it is recorded;
- that **no night has run with the flags**, no real donor has been mined, the increment is proven
  against the synthetic donor only, and no yield is claimed.

### R3 — the `CHANGELOG.md` `[Unreleased]` section

Add `## [Unreleased]` above `## [0.22.0] - 2026-10-11` (`CHANGELOG.md:12`), Keep-a-Changelog shape
(the file's own rule: "records what shipped, not what is planned", `CHANGELOG.md:8-10`). The link
definition already exists at `CHANGELOG.md:1605`; do not duplicate it. `Added`: the re-mine flags
and the training-only root, the ledger delta, the runbook block, the `PREREGISTRATION` § 10.17
reading and the ROADMAP note. `Changed`: no reward/gate change; the held-out document is unchanged.

### R4 — the `docs/ROADMAP.md` § 13 dated note

§ 13's corpus paragraph (`ROADMAP.md:794-800`) is **made false** by the change: *"The corpus does
not grow"* (`:794`), *"a night reads a frozen directory and never re-mines"* (`:795-796`), and
*"Moving … out of post-horizon is what makes the thesis mechanical"* (`:799-800`, now done). The
repo's convention is a **dated correction blockquote, never an edit of the old text**
(`test_docs.py:947-975`, the § 12/§ 10.16 precedent; § 14's M1/M2 corrections at
`ROADMAP.md:867-894,927-970`). Insert it immediately after `:800`, before the "What this project
is" paragraph (`:802`), so it reads as a correction of the paragraph above it.

The blockquote must say:

- the corpus now grows: the night re-mines the declared donor before it loads its corpus and draws
  against the grown pool;
- the growth is training-only (gitignored root; the committed 66-task corpus and the sealed held-out
  split do not move);
- the boundary reading, pointing at `PREREGISTRATION.md` § 10.17;
- the § 9 reconciliation: § 9's post-horizon list (`ROADMAP.md:598-603`) **never named** re-mining;
  § 13 named it as a gap (`:794-800`) and the gap is now built — so there is nothing to delete from
  § 9, and the promotion § 13 asserted is the one that happened;
- the § 14 reconciliation: re-mining is **not** a lever on the zero strict-`PASS` yield — a bigger
  pool says nothing about whether a candidate improves (`../prd.md:50-52,169-178`) — and § 14's M1
  (`ROADMAP.md:836-894`) remains the only identified lever on the zero;
- what did not happen: no night has run with the flags, no real donor has been mined, the increment
  is proven against the synthetic donor only, and no yield is claimed.

**Line-shift audit (done, recorded here so the executor need not redo it).** Every guarded
`docs/ROADMAP.md:<a>-<b>` cite lives above § 13: `test_docs.py:141-152` (max `:609-614`) and
`tests/test_gate_runbook_guards.py:465-477` (max `:688-693`), and the gate/baseline/honest-number
runbook guards cite § 4–§ 12 only. Inserting a blockquote after `:800` shifts § 14 but no guarded
line. Do **not** add a `docs/ROADMAP.md:<a>-<b>` citation to `PREREGISTRATION.md` (R5): the
citation-resolves guard (`test_docs.py:1101-1143`) would then demand a matching table row, and the
line would drift with the next edit. Cite sections by name.

### R5 (the policy decision) — the boundary reading in `PREREGISTRATION.md` § 3

`PREREGISTRATION.md` is append-only: § 10 begins at `:332`, *"Nothing above this heading is edited
by anything below it"* (`:335`), and § 8.4 forbids a silent change (`:275-276`). The reading is
therefore recorded as a **new § 10.17 subsection, Type 2 (§ 8.2): a disclosure, added** — it closes
no open item, sets no threshold, and rewords nothing in § 1, § 4, or § 6 — with a one-line row
appended to the amendment log (`:306-325`, whose last row is § 10.16 at `:325`).

**The reading, drafted (the plan pins these exact phrases).**

- § 3 pins five inputs — model revision, **the task set**, environment pins, seeds, tool versions —
  and treats a change in any as invalidating the series (`:131-135`).
- **This amendment reads § 3's "the task set" as the scoring set**: the held-out split the baseline
  and every candidate are scored on. The textual basis is § 3 itself — the pinned baseline is
  *"scored on the held-out set by the same STRICT verifier, with its provenance committed
  alongside: seeds, model revision, task set …"* (`:126-128`) — so the "task set" that is a pinned
  input is the set the score is computed on, not the pool the model learns from.
- **Disclosed:** `whetstone run --night` may re-mine the user's declared donor repositories before
  it draws, growing the training pool. The growth is training-only: it lands in a separate,
  gitignored root, the committed corpus and the held-out split's `membership` and `document_digest`
  do not move, and the run ledger records the minted ids and donor labels (`task_set.remined`).
- **This is a reading, not a threshold and not a change of input.** No new baseline is required and
  no series is invalidated, because the figure a candidate is scored on is unchanged. If a later
  reader finds the reading wrong, the correction is a further dated amendment that moves the pinned
  input and starts a new baseline — never a silent edit.
- It states, in the § 10.6/§ 10.9/§ 10.10 disclosure shape
  (`test_docs.py:758-765,794-802,917-924`), that **at the time of this amendment no night has
  re-mined and no count has been measured under it, and none is claimed here**.

The log row: `| 2026-10-11 | The night re-mines the training pool; § 3's pinned "task set" is the
scoring held-out split (§ 10.17) | 2 — adds a disclosure | No |`.

### R6 — correcting every sentence the change makes false, on the record

Only `docs/ROADMAP.md` § 13 carries a sentence the change falsifies (R4). Checked and found clean
on 2026-10-11: `README.md` (`:9,158,258` — "frozen generation contract" is the contract, not the
corpus; the "Not built" list names the dashboard and distillation, not re-mining), `VISION.md`
(no corpus-growth claim), `CLAUDE.md` (`:52-53` "The corpus, stated precisely … 66 tasks" — the
**committed** corpus is still 66; the re-mine writes to a gitignored root, so this stays true), and
`docs/planning/whole-function-edit-finding/prd.md:245-246` (a historical planning artifact; the
repo corrects present-tense documents, not superseded plans — leave it, and say so in the plan).
`docs/ROADMAP.md:709` ("dashboard and distillation remain post-horizon") is untouched and stays
true.

### R7 — the guard that pins the boundary reading

`tests/test_docs.py` (the orienting-documents guard, `:1-34`) gains tests that fail if the reading
or the correction is silently deleted or reworded:

- **the boundary reading** (`test_the_preregistration_states_the_training_pool_reading`): the
  distinctive phrases of R5 are present in `PREREGISTRATION.md` (via `_read`/`_flat`, `:155-178`),
  § 10.17 exists, the log row exists, and the `no night has re-mined … none is claimed here`
  sentence is present. A positive control asserts the section heading, so a gutted file cannot pass
  an absence check (the `:240-251` pattern).
- **the ROADMAP correction** (`test_the_roadmap_records_the_night_remine_by_dated_correction`): the
  blockquote flat text (`test_docs.py:955-975`'s `>`-only `_flat` shape) contains
  `Corrected 2026-10-11`, `re-mines before it draws`, `10.17`, and `not a lever on the zero`.
- **the write-up exists**: `night-corpus-remine` appears in `docs/STATUS.md`, and
  `re-mines before it draws` appears in `CHANGELOG.md` (a substring guard anywhere in the file, so
  it survives a later release moving `[Unreleased]` content under a version — do not pin the
  `[Unreleased]` heading, which a release removes).

### R8 — the `CLAUDE.md` cross-reference (flagged; see the decision below)

`CLAUDE.md`'s "The corpus, stated precisely" paragraph (`:52-53`) is the always-loaded context; a
reader there could otherwise re-derive the boundary reading the wrong way. Add **one clause** to
that existing paragraph — not a new status entry — pointing at the reading, e.g. *"The night
re-mines the training pool into a separate gitignored root; the committed 66 and the held-out split
are unchanged (`PREREGISTRATION.md` § 10.17)."* This does not violate the file's rule that *"a
capability is written up in the same commit that lands it"* and *"append new entries to
`docs/STATUS.md`, not to this file"* (`CLAUDE.md:83-85`): it is a clarification of an existing
claim, not a status entry. **Reviewer decision — see "The decision" below.**

## The decision this aspect records (and how it is flagged)

**Decision (recommended):** record the reading as **`PREREGISTRATION.md` § 10.17, Type 2**, with a
log row, plus the `CLAUDE.md` one-clause cross-reference.

**Justification.** § 3's "task set" is genuinely ambiguous — it is asserted nowhere that it means
the scoring split (`../understanding.md:94-96`) — and the reading is load-bearing: it decides
whether this unit's whole shape is right (`../prd.md:151-155`). The pre-registration's own
discipline is that a change to what it commits to is never silent (`:275-276`), so the reading
belongs **inside** the append-only document, not only in the roadmap. A Type 2 disclosure is the
minimal honest form: it discloses the behaviour and the reading, claims no threshold, closes no
open item, and edits nothing above § 10. The amendment log is append-only, so the row is the
document's own mechanism for a dated addition.

**Not overclaiming.** The note is written as a *reading* with its textual basis, states it is not a
threshold and not an input change, and names the honest correction path if the reading is wrong
(a further dated amendment that moves the input and starts a new baseline). It claims no count.

**Flag for the reviewer.** This is a policy choice, not a fact the tree proves, and the alternative
is defensible: record the reading **only** in `docs/ROADMAP.md` § 13 and `docs/STATUS.md`, leaving
`PREREGISTRATION.md` untouched on the ground that § 3 never pinned the training pool and so nothing
needs disclosing. The spec recommends the § 10.17 note because the PRD explicitly calls out that
the reading "is asserted nowhere in the repo today" (`../prd.md:152-153`) and because leaving it
out of the pre-registration leaves a future reader to re-derive it — possibly the other way. **If
the reviewer rejects § 10.17, R5 and the PREREGISTRATION half of R7 are dropped and the reading
lives in R4/R2 only; the rest of the aspect is unchanged.** The `CLAUDE.md` cross-reference is a
second, smaller reviewer decision: if the file's append-only-status discipline is read strictly,
drop R8 and put the cross-reference in `docs/STATUS.md` instead.

## Out of scope

- **The code aspects.** The `--remine*` flags, `run_night`'s block, the skip-set and the ledger
  field are `remine`/`record` (`../prd.md:204-211`); this aspect only documents and guards them.
- **The invariant tests.** AC3/AC4/AC5 (determinism, held-out invariant, reward untouched) are
  `guards` (`../prd.md:212-213`); this aspect must not break them.
- **`docs/technical/ARCHITECTURE.md` / `docs/product/PRODUCT_SPEC.md`** — they do not exist
  (`CLAUDE.md:262-264`); do not create them.
- **Re-deriving the held-out split, the corpus record, the reward, the gate.** Untouched
  (`../prd.md:169-178`).
- **Editing historical planning artifacts** (`whole-function-edit-finding/prd.md:245-246`,
  `../understanding.md:100-106`). The record is corrected in present-tense documents only.
- **A yield claim.** No number appears anywhere the verifier did not produce (`CLAUDE.md:119`).

## Acceptance criteria (testable, written first)

Strict TDD: each is a test that fails on the current tree and passes after the change
(`uv run pytest` green on the branch). The runbook ones are **watched failing first** against the
unmodified sheet, per `tests/test_night_runbook_guards.py:43-51` and `CONTRIBUTING.md`.

1. **AC-D1 (S2)** — `tests/test_night_runbook_guards.py` refuses the unmodified sheet: the night
   block does not pass the four `--remine*` flags, does not export `DONOR`, and the prose lacks the
   training-only-root and cost-bound sentences; after the sheet edit all are green and the probe
   block still passes none of the four.
2. **AC-D2 (R1)** — `--remine-out` is anchored (`$REPO/...` or absolute), `--remine` is `$DONOR`,
   and `_exports_donor` holds; the probe block passes no `--remine`.
3. **AC-D3 (R5, R7)** — `test_the_preregistration_states_the_training_pool_reading` fails before
   § 10.17 exists and passes after; it pins the reading phrases, the log row, and the
   "no night has re-mined … none is claimed here" sentence.
4. **AC-D4 (R4, R7)** — `test_the_roadmap_records_the_night_remine_by_dated_correction` fails
   before the blockquote exists and passes after; the blockquote carries `Corrected 2026-10-11`,
   `re-mines before it draws`, `10.17`, and `not a lever on the zero`.
5. **AC-D5 (R2, R3, R7)** — `night-corpus-remine` appears in `docs/STATUS.md` and
   `re-mines before it draws` appears in `CHANGELOG.md`.
6. **AC-D6 (R6)** — no present-tense document asserts the corpus does not grow outside a blockquote:
   `test_docs.py`'s existing `test_no_document_still_claims_that_no_number_about_a_model_exists`
   pattern (`:254-303`) still holds, and a new assertion confirms `ROADMAP.md`'s running prose
   (non-`>`) no longer carries "The corpus does not grow".
7. **AC-D7 (invariants)** — `PREREGISTRATION.md` still carries every § heading
   (`test_docs.py:89-101,568-595`), contains no placeholder (`:598-618`) and no `%`/`percent`/
   `percentage` (`:621-653`); `test_every_roadmap_citation_in_the_preregistration_resolves`
   (`:1101-1143`) stays green (no new `docs/ROADMAP.md:<a>-<b>` cite); `test_gate_runbook_guards.py`
   stays green (no § 12 cite drifted).

## Dependencies and sequencing

- **`remine` and `record` first.** The runbook's new flags must exist in `build_parser()`
   (`cli.py:262-459`, `../remine/spec.md:137-151`) before `test_every_flag_the_night_command_passes_
   exists_in_the_parser` (`test_night_runbook_guards.py:349-363`) can pass. The `run_night` block
  (`../remine/spec.md:115-135`) and `task_set.remined` (`../record/spec.md:31-53`) must exist for
  the STATUS/CHANGELOG sentences to be true.
- **`docs` last**, in the same commit as the write-up (the repo's rule, `../prd.md:217-219`;
  `CLAUDE.md:83`). The STATUS/CHANGELOG/ROADMAP/PREREG edits and the guard tests are one commit.
- **`guards`** wraps both code aspects; this aspect must not break `tests/loop/test_heldout_document.py`
  or `tests/test_no_inference_on_reward_path.py`.

## Open questions and risks

- **🔴 The boundary reading (R5/R8) is a reviewer decision** — § 10.17 vs. ROADMAP/STATUS only, and
  whether `CLAUDE.md` is touched. Recommendation and alternative above; the rest of the aspect is
  independent of the answer.
- **🟡 The donor anchor token.** This spec uses `$DONOR` with an `export DONOR=/...` line, mirroring
  `$REPO` (`runbook.md:8-10`), so no home directory is committed. The alternative is a
  `<donor-path>` placeholder the guard treats as a declared token. Either satisfies the anchoring
  property; the `$DONOR` form is the one that mirrors the existing sheet.
- **🟡 The re-mine label.** This spec uses `--remine-label donor-a`, following the PRD's own
  scenario (`../prd.md:57-61`) — source B *is* the author's own donor-a/donor-b repos, so re-mining
  donor-a under the same label is correct and the sha12 skip-set prevents a collision. If the
  operator's re-mine donor is a different repo, the label is a second spec decision; the sheet
  should say which repo `$DONOR` points at.
- **🟡 CHANGELOG guard brittleness.** Do not pin `## [Unreleased]` (a release removes it); pin the
  phrase anywhere in the file.
- **🟢 No new number.** The STATUS entry and the CHANGELOG entry state shipped behaviour and "no
  night has run", never a count.
