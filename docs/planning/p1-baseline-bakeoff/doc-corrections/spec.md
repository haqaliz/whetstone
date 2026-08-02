# Aspect spec — `doc-corrections`

**Parent PRD:** `docs/planning/p1-baseline-bakeoff/prd.md` (M10, M12, S3, D4).
**Sequence:** fifth, landing in the **same commit** as the report — `CLAUDE.md` requires that a
capability be written up in the commit that lands it, so the claim and the code cannot outlive
each other.

## Problem slice

Four documents currently assert, in the present tense, that no number about a model exists. This
slice makes that false. Correcting them is not tidying: leaving a status block that says the tree
holds no measurement, in a tree that holds one, is precisely the failure mode
`docs/ROADMAP.md:466-473` already records this project committing once before.

Two existing test guards fight the correction, and one of them is coupled to absolute line numbers
in an **append-only** document. That coupling is the whole difficulty of this aspect.

## In scope

1. **`docs/ROADMAP.md` § 4** — P1's status: the criterion is closed; `reports/baseline/` exists.
2. **`CLAUDE.md`** — the status block's "What is not built" paragraph and the bake-off line.
3. **`CHANGELOG.md`** — the entry, as every prior slice kept.
4. **`docs/ROADMAP.md:387`** — correcting "held-out" per D4, and recording the clash with
   `PREREGISTRATION.md:242-247` as a finding rather than a silent edit.
5. **`PREREGISTRATION.md` amendments (S3)** — *only if needed*, appended, dated, in their **own
   commit**, logged at the foot (`:306`, currently "No amendments"): the generation contract as an
   unpinned input; capacity as a bound if it bit; and that with source A at one instance the
   contamination signature § 4 pre-registers is undetectable in practice.

## Out of scope

- Any number. `docs/ROADMAP.md:7-9` forbids a performance figure in the roadmap and
  `PREREGISTRATION.md:163` forbids one there; `reports/baseline/` is the only home (M12).
- Rewording `PREREGISTRATION.md` §§ 1, 4, or 6, or any disclosure — forbidden outright by `:271-274`.
- Fixing the stale `whetstone-next` / `whetstone-worktrees` skill files.

## Acceptance criteria (written first)

**AC1 — the open-criterion guard is updated RED-first.**
`tests/test_docs.py:680-701` currently requires the literal `"One criterion remains open"` in § 4
and forbids `"Two criteria remain open"`. Closing the last criterion makes the required string
false. The guard is updated to assert the **new** truth (no criteria remain open in P1), watched
failing first, and its docstring records that the count moved — the test is slice-scoped by design
and says so itself.

**AC2 — the citation guard still passes, with the falsified sentence preserved as history.**
*(the hard one)*
`tests/test_docs.py:735-777` anchors `PREREGISTRATION.md`'s citation of `docs/ROADMAP.md:364-368` on
the literal sentence *"not one number about a model exists anywhere in this repository"*, checked
**inside those absolute line numbers**, in both directions, against a document that is append-only.
Required outcome: the sentence still occurs within lines 364–368 **as a quoted, dated correction** —
the precedent `docs/ROADMAP.md:466-473` already sets — so it reads as a historical claim about the
tree the pre-registration was committed to, not as a present-tense falsehood. Test passes unchanged.

**AC3 — no citation below § 4 shifts.**
Five of the ten pinned citations live at or after `:458`. The § 4 edit is **line-count-neutral**, and
a test run proves all ten still resolve. (Fallback, only if AC2 proves impossible: a dated amendment
re-pointing the citation plus a lockstep `ROADMAP_CITATIONS` edit — more expensive, touches an
append-only document, and must be reasoned about out loud per `:275-276`.)

**AC4 — no stale claim survives, and no new one is introduced.** *(adversarial)*
`tests/test_docs.py:204-216` forbids five stale strings in `CLAUDE.md`. A test asserts the tree no
longer claims anywhere, in the present tense, that no number about a model exists — the positive
form of the guard, not just the negative. Watched failing against the pre-edit tree.

**AC5 — the branch name never enters `CLAUDE.md`.**
`CONCRETE_BRANCH` (`tests/test_docs.py:45`, `:256-280`) forbids a `feat/…/aliz`-shaped string.

**AC6 — `PREREGISTRATION.md` invariants hold if it is touched at all.**
No `%`/`percent`/`percentage` in any position including code fences (`:528-542`); all eleven `##`
headings intact; no placeholders; every disclosure, open-item and contract phrase still present; the
amendment dated, its own commit, and logged.

**AC7 — the roadmap and pre-registration agree afterwards.**
The held-out clash (D4) is resolved in text: `:387` no longer asserts a set that
`PREREGISTRATION.md:242-247` says cannot exist, and the correction is recorded rather than made
silently.

**AC8 — the suite is green on the commit that lands the report**, not one commit later.

## Dependencies & sequencing

- Depends on `the-run` having produced the report — the corrections describe what landed, and
  writing them earlier would be a status claim about work in flight, which `CLAUDE.md` forbids by
  name ("never work in flight on a branch").
- Any `PREREGISTRATION.md` amendment must be **its own commit** and, per `:266-268`, land **before
  the measurement it governs runs** — so a §7-closing amendment cannot be back-filled after the run.
  The S3 disclosures are type-2 (adding a disclosure), which `:269-270` permits at any time; a
  disclosure discovered during the run is disclosed late rather than not at all.

## Open questions / risks

- **AC2 is the sharpest risk in the whole slice.** The guard's own docstring (`:737-742`) records
  that this exact coupling broke once already, when the pre-registration slice shifted five
  citations. Budget for it; do not discover it at commit time.
- Whether the S3 disclosures are needed at all depends on what the run finds. The default is to
  disclose the generation contract as an unpinned input regardless, because it is true independent
  of the outcome.
