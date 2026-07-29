# PRD — `PREREGISTRATION.md` (P1 exit criterion 6)

**Card:** `docs/planning/p1-preregistration/card.md` · **Dig:**
`docs/planning/p1-preregistration/understanding.md` · **Upstream spec:** `docs/ROADMAP.md` § 6
(`:478-488`), § 5 (`:464-474`), P1 criterion 6 (`:355-356`), P4 (`:444-460`).

---

## 1. The problem

`docs/ROADMAP.md` § 6 requires a committed `PREREGISTRATION.md` **before any number exists**, and
P4 later grades the published headline against it (`:452-453`). The file does not exist. Until it
does, the bake-off — the other open P1 criterion — cannot honestly run, because it produces the
first per-source numbers this project will ever hold, and a headline rule chosen after those are
visible is not a commitment.

**The document's value is its timestamp, not its prose.** Everything below serves that.

## 2. What the roadmap already decides (not re-litigated here)

| Decided | Where |
|---|---|
| Source B (private) is the headline; it is on-thesis and uncontaminated | `:484` |
| Both sources are always published together, regardless of which looks better | `:485` |
| A disagreement between them is reported as a finding; public-gain-with-private-flat is the expected contamination signature | `:486-488` |
| A pinned baseline checkpoint, measured once and re-measured never | `:466-471` |
| `N := count(rollouts where WEAK == PASS and STRICT == FAIL)`, and `N` is meaningless without a baseline `N` | `:106-117`, `:472-474` |
| `UNVERIFIED` is never a win, never collapsed into `promoted` | `:404-429` |
| A zero or negative delta is a valid, publishable outcome | `:456-457` |

## 3. Decisions taken in this slice

Two were genuinely open and were put to the user; the rest follow from the dig.

**D1 — The headline figure is the delta in strict-PASS *count* on the held-out source-B split.**
*(user decision)* Published as a count over its denominator, with coverage and `N` beside it, and
**never as a bare percentage**. § 6 fixed the source but never the figure; P4 cannot grade "the
headline" against a file that does not name one. A count is chosen over a rate because the
denominator is small and a rate manufactures precision the corpus cannot support — the same
reasoning Belay used when it declined to threshold its violation rate at n=50.

**D2 — No numeric success threshold is pre-registered, and none may be added later.**
*(user decision)* Publication is already ungated by `:456-457`. Any bar set today would be
invented: no baseline has been measured, no base model chosen, and the held-out split does not
exist. `CLAUDE.md:119` forbids exactly that. The document's teeth are its **reporting rules**, not
a number. The prohibition on adding one afterwards is itself pre-registered, because a threshold
introduced once a result is visible is the post-hoc selection § 6 exists to prevent.

**D3 — Open items are named with a closing mechanism and a deadline, never left blank.** The
held-out split, *R*, and the base model are undecided (`:569-574`). Each is listed with why it is
open, who closes it, and the rule that it is closed in a **dated amendment committed before the
measurement it governs**. Belay's template carried 20 `TO-BE-FILLED` markers for ten days; this
document forbids placeholders outright and a test enforces it.

**D4 — Source A is reported per-instance, never as a rate.** § 6 requires both sources published,
but source A is **1 eligible instance of 300** (`tasks/README.md:13-30`). A delta on n=1 is not a
measurement. Pre-registering the reporting form now stops P4 from discovering the problem with a
result in hand.

**D5 — The stale Belay claim at `docs/ROADMAP.md:456-460` is corrected in this slice, with a
guard.** Verified 2026-07-29: `PHASE0_RESULTS.md` now carries **0** `TO-BE-FILLED` markers (filled
by `77adc8f`, recording a **PIVOT** — 0.00 precision, 1.00 coverage, denominator 16 against a
required ≥50). The roadmap's claim was true at `801b457` and false ~10 hours later. It is a false
claim about honesty, inside the section about honesty, in the document this slice discharges.
The still-valid lesson replaces it: Belay's own *"Ordering: what actually happened"* records that
its criteria were fixed in a **planning file** and were *not* copied into the publishing document
before the run — which is why `PREREGISTRATION.md` lives at the repo root.

**D6 — The disclosure of source B's self-selection ships *without* its stated mitigation.**
`docs/planning/p1-task-ingestion/prd.md:343-344` claims *"D3's inclusion of rereflect is the
mitigation."* `rereflect` was refused for having no `uv.lock` (`tasks/README.md:171`). Carrying
§ 8.3 verbatim would ship a false mitigation; the document states the disclosure and records that
the mitigation did not land.

**D7 — Planning artifacts live in `docs/planning/p1-preregistration/`, not `docs/planning/_card/`.**
Three live citations point into `_card/understanding.md` by section number
(`docs/ROADMAP.md:159`, `tests/adversarial/test_cheats.py:270`, `tests/test_docs.py:50`). The
skill's overwrite-the-card convention would break them. Recorded in `card.md` as a skill defect.

## 4. Requirements

### R1 — The document exists at the repo root and is committed in this PR
`PREREGISTRATION.md`, root level. Not under `docs/` — per D5's lesson, the pre-registration must
live where the claim is published, not in a planning directory.

### R2 — It contains no placeholder
No `TO-BE-FILLED`, `TBD`, `TODO`, `FIXME`, `XXX`, `???`, or bare `_____`. Everything is decided at
commit time or named as open with its closing mechanism (D3).

### R3 — It contains no figure about a model, and no percentage at all
No model has been run (`docs/ROADMAP.md:364-368`), so any performance figure here would be
invented. Enforced mechanically: **the document contains no `%` character.** Legitimately citable
percentages (the 35%-false-positive judge result) belong in `docs/ROADMAP.md` § 11, not here. Any
illustrative example uses placeholder letters, never plausible-looking digits.

### R4 — It carries the § 6 contract
Source B is the headline; both published together; disagreement is a finding; the
public-gain-with-private-flat signature is named.

### R5 — It defines every metric before any of them is measured
The headline (D1), `solved`, the delta, `N` and baseline `N` with the verbatim reporting phrase
*"N rollouts a weaker check would have scored as wins"* and its intent caveat, coverage, and the
rule that every rate is published with its denominator.

### R6 — It carries the baseline protocol, including a non-comparability rule
Pinned baseline checkpoint with committed provenance; measured once, re-measured never; a changed
pinned input invalidates the series and is treated as starting over; numbers measured across such
a change may not be compared.

### R7 — It carries the honesty contract the eventual number depends on
`UNVERIFIED` is never a win and never rendered as `PASS`; coverage lowers rather than excludes;
the three gate exits; a zero or negative delta is published as plainly as a positive one.

### R8 — It discloses, up front, what a reader would otherwise discover later
1. **Source B self-selection** — the author's own repos, largely written by Claude Code under
   strict TDD, `belay`/`contig` being *about* verification and sandboxing; red→green selection
   over-represents the test-written-first shape; **the stated `rereflect` mitigation did not
   land** (D6).
2. **Source A is 1 eligible instance of 300**, refusals 192 format / 106 environment / 1
   collectability; **not a benchmark set**, reported per-instance (D4).
3. **Two documented cheat residuals** (6 and 10) survive into any reported `N`, with the
   verifier's stated bound: it confines what a run may **write**, not what it may **read**, and
   its guarantee extends only as far as the manifest is complete.
4. **Source B's data never leaves the box**, so an outside reader can re-derive the corpus from
   the committed recipe but cannot reproduce our instances byte-for-byte.
5. **Pre-registration is a timing control, not an independence control** — solo project; the same
   person writes the criteria, runs the loop, and publishes the result.

### R9 — It names what is open, with the mechanism and deadline for closing it
Held-out split size and stratification; retry count *R*; the open base. Plus the amendment rule:
append-only, dated, committed **before** the measurement it governs, never silently, and never a
threshold added after a number exists (D2).

### R10 — The tree cannot hold a report without its pre-registration
A guard fails if anything exists under `reports/` while `PREREGISTRATION.md` does not. Enforces
the ordering mechanically rather than by intention.

### R11 — The status documents are updated in the same commit
`CLAUDE.md`'s status block and `docs/ROADMAP.md` P1 stop listing this as open and show **one**
remaining P1 criterion (the bake-off); `docs/ROADMAP.md:456-460` is corrected per D5;
`CHANGELOG.md` gains an entry. `CLAUDE.md` requires the claim and the code to land together.

### R12 — The suite, lint, and types stay green
`uv run pytest`, `uv run ruff check .`, `uv run mypy src/` all exit 0;
`tests/test_no_inference_on_reward_path.py` unchanged and green; CI green on `macos-latest`.

## 5. The document's shape

```
PREREGISTRATION.md
├── What this is, and what it is not          ← timing control, not independence control
├── Status at the time of writing             ← verifiable claims about this tree
├── 1. The headline                           ← D1, R4
├── 2. The metrics, defined before measurement ← R5
├── 3. The baseline protocol                   ← R6
├── 4. How the result is reported              ← R7, D4, both-sources rule
├── 5. Success, and what is not pre-registered ← D2
├── 6. Disclosed limitations                   ← R8 (five items)
├── 7. Open at the time of writing             ← R9, with closing mechanism per item
├── 8. The amendment rule                      ← R9
└── 9. Provenance                              ← how to verify the ordering with `git log`
```

§ 9 carries no guard, so `_section()`'s inability to slice a file's final section
(`understanding.md` § 7.6) never bites.

## 6. Test plan (RED first, in this order)

| # | Test | Asserts | Anti-vacuity control |
|---|---|---|---|
| T1 | `test_preregistration_exists_and_carries_its_sections` | file `is_file()`; every § heading present | the heading list is non-empty and each is asserted individually |
| T2 | `test_preregistration_contains_no_placeholder` | none of the R2 markers appear | paired with T1, which fails on a gutted file |
| T3 | `test_preregistration_states_no_figure_about_a_model` | no `%` anywhere; the "no number exists" sentence present | the positive half is the control for the negative half |
| T4 | `test_preregistration_carries_the_section_6_contract` | headline=B, both-together, disagreement-is-a-finding, contamination signature | substring loop over an explicit tuple |
| T5 | `test_preregistration_carries_every_disclosure` | all five R8 disclosures, incl. the refused `rereflect` mitigation and the residual bound | each disclosure asserted separately, so one cannot mask another |
| T6 | `test_preregistration_names_what_is_open_without_guessing_it` | split, *R*, base named as open; amendment rule present | asserts the words "open" *and* the closing mechanism, not just the topic |
| T7 | `test_no_report_may_exist_without_its_preregistration` | run over the real repo root | **helper tested against two synthetic trees** in `tmp_path`: `reports/` without the file → offender; with the file → none. Watched failing. |
| T8 | `test_claude_md_no_longer_lists_the_preregistration_as_open` | `"both still open"` added to `STALE_CLAUDE_CLAIMS` | the existing positive control at `test_docs.py:131` |
| T9 | `test_the_roadmap_p1_shows_one_remaining_criterion` | § 4 no longer says "Two criteria remain open" and names the bake-off as the last | positive assertion of the replacement text |
| T10 | `test_the_roadmap_does_not_overstate_belays_unfilled_gate` | the "20 TO-BE-FILLED" claim is gone and the corrected reading is present | both halves asserted — absence alone would pass on a deleted section |

T7 is the one with real teeth: without the synthetic-tree controls it passes vacuously today,
since `reports/` does not exist. `CONTRIBUTING.md:56-60` requires exactly that.

## 7. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| **The document commits to something P4 cannot deliver** — e.g. a held-out source-B split that the corpus is too small to support | Medium | D1 pins the *form* of the headline, not its size; the split itself is explicitly open (R9) and closed by a dated amendment before it is measured |
| **`%`-ban (R3) is over-tight** and a future legitimate edit needs a percentage | Low | The ban is on this file only; the roadmap remains the place for grounded external statistics. A future amendment may relax it deliberately — that is a visible, reviewed act, which is the point |
| **The ROADMAP correction (D5) re-stales** — Belay keeps moving | Medium | T10 guards the corrected reading; the new wording cites Belay's *ordering* admission, which is a historical fact and cannot un-happen, rather than a live marker count |
| **Scope creep into the bake-off** | Low | Explicitly out (§ 8). This slice runs no model |
| **The document reads as ceremony** — long, and it gates nothing by itself | Medium | Accepted. Its function is the timestamp plus the five disclosures; P4's exit criterion is what gives it force |

## 8. Out of scope

The bake-off and `reports/baseline/` (the next slice, and the reason this one exists); anything
that runs a model; deciding the held-out split, *R*, or the base; closing cheat 6 or 10;
`docs/technical/ARCHITECTURE.md`; amending the `whetstone-begin-fast` skill (D7 records the defect;
fixing it is separate).

---

## 9. Self-critique

### 🔴 Must resolve before implementation

1. **R3's `%` ban could be theatre if the document instead spells "percent".** The guard must ban
   the word as well as the glyph, or it is a trivially-evaded rule that buys false confidence —
   the exact failure `CONTRIBUTING.md:56-60` names. **Resolution:** T3 checks for `%`, `percent`,
   and `percentage`, and the document's own § 4 states the rule in words so a reader knows it is
   deliberate rather than an accident of style.

2. **T7 does not actually prove the ordering — it proves a co-existence.** A tree could commit
   `PREREGISTRATION.md` and `reports/baseline/` in the *same* commit and pass. The real claim is
   temporal. **Resolution:** accept the weaker mechanical guard (it is what a working tree can
   check) and make the *strong* claim provable by `git log` instead — § 9 of the document tells a
   reader the exact command to verify that this file's commit predates every report. State this
   limitation in the test's docstring rather than letting it read as stronger than it is. Belay
   made precisely this mistake in the opposite direction and had to write a self-indicting section
   about it.

3. **D2 forbids adding a threshold later, but D3 permits dated amendments.** Those are in tension:
   an amendment could add a threshold and claim R9's blessing. **Resolution:** the amendment rule
   must name the exception explicitly — amendments may close an open item listed in § 7 and may
   not introduce a success threshold, ever. T6 asserts the exception clause is present.

### 🟡 Worth stating, not blocking

4. **The headline presumes a held-out split exists.** If the 66-task corpus proves too small to
   split without a degenerate held-out set, D1's headline is unmeasurable. The document should say
   what happens then — the honest answer is that the split's feasibility is part of what P3
   determines, and if it fails, *that* is the published finding.

5. **"Measured once, re-measured never" is Whetstone's own coinage** — neither sibling uses it, so
   the document must define it operationally (which inputs are pinned; what a change to one does
   to the series) rather than treating it as a known term.

6. **Five disclosures is a lot, and a reader may skim them.** Accepted: they are the part a later
   reader most needs. They are given their own section with one heading each rather than a
   paragraph, so a skim still lands on each claim.

7. **This slice touches `docs/ROADMAP.md` twice for different reasons** (the P1 status, and the
   P4 Belay correction). They are separable, but both are required by `CLAUDE.md`'s
   land-the-claim-with-the-change rule, and splitting them across commits would leave one of the
   two documents wrong at an intermediate commit.

### Where this PRD is thinner than its predecessors

Deliberately. `p1-verifier-core` and `p1-task-ingestion` were 27–28 KB because they were
specifying executable reward-path behaviour under adversarial pressure. This slice ships one
document and ten guards, runs no model, and touches no reward code. A PRD proportionate to that is
the correct artifact; padding it would not make the commitment stronger.
