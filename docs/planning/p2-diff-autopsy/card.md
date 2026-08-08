# Card — `p2-diff-autopsy`

**Type:** feat · **Branch:** `feat/p2-diff-autopsy/aliz` · **Owner:** aliz
**Started:** 2026-08-09 · **Source:** inline brief (no GitHub issue; the id is a slug)

---

## Why there is no issue body

Whetstone's tracker is GitHub Issues, but this unit of work came out of a `whetstone-next`
ranking run over the repository's own files on 2026-08-09, immediately after the P2 yield
probe closed with no fix chosen. The id is therefore a descriptive slug rather than a number,
and the brief below is the source of truth for Phases 2–5.

**Artifacts live here rather than in `docs/planning/_card/`** following the precedent set by
`docs/planning/p2-yield-probe/card.md:56-66`: three live citations point into
`_card/understanding.md` by section number (`docs/ROADMAP.md:159`,
`tests/adversarial/test_cheats.py:270`, `tests/test_docs.py:50`), so the `_card` path is not a
safe place for this unit's documents.

## Brief

Read what the unparseable diffs actually contain. The p2-yield-probe correction
(`docs/planning/p2-yield-probe/prd.md:84-89`) demands a fourth fix be proposed only after
someone reads the stored completions — they are on disk in the gitignored `runs/arm-a/` and
`runs/budget-2048/` transcripts in the primary checkout — and the fork it feeds is the
roadmap's own: an easier task stratum or a larger base (`docs/ROADMAP.md:387-389`).

Build an offline, deterministic, stdlib-only classifier (no `mlx` import, asserted by AST walk
like `attribution.py`) that grounds a cause taxonomy in what the completions actually contain —
prose, fenced code that is not a diff, header-without-hunk, corrupt hunk, wrong-path diff,
truncated mid-hunk, and any other shapes the read reveals — with every category backed by a
fixture and no "other" bucket (the `attribution.py` bijection discipline).

**The verifier is out of scope and must not be touched:** nothing under `src/whetstone/verify/`
changes, the reward stays execution-grounded, and the reward-path guard and its scope partition
pass unchanged. All new code lands in `src/whetstone/bakeoff/`, which is `EXEMPT` from the
guard with a written reason.

## Acceptance criteria (test-first)

1. Each category has a fixture from a real or faithfully replicated completion, and the
   classifier is deterministic (same input → same category).
2. A per-`(candidate, cause)` breakdown is produced for **both** stored runs (`arm-a`,
   `budget-2048`), written only into gitignored run artifacts.
3. The taxonomy explains the existing `attribution.py` buckets rather than replacing them —
   the new cause is a finer partition of an existing bucket, and the mapping is asserted.
4. A written finding states which wall the evidence points at — format, anchoring, or
   reasoning — and which of the roadmap's named responses it supports; no figure about a model
   is published outside the gitignored artifacts, and `reports/baseline/` stays the one home
   for any published figure.
5. `git diff --stat origin/master -- src/whetstone/verify/` stays empty and the reward-path
   guards pass unchanged.

## Known caveat, carried from the ranking

The PRD of the slice that produced the transcripts flags its own assumed taxonomy as
**"asserted, not yet grounded"** (`docs/planning/p2-yield-probe/prd.md:244-247`): the categories
must be derived from what the transcripts actually contain, allowed to change once read, and
never collapsed into an "other" bin — the same discipline `attribution.py` applies to
`patch.py`'s reasons. The list of shapes in the brief above is provisional and may not match
what the read reveals.

Two further constraints from the worktree skill and the transcript precedent:

- **Run state is never copied between worktrees.** The transcripts are read by absolute path
  from the primary checkout (`/Users/aliz/dev/at/whetstone/runs/`); the worktree keeps none.
- **Completions quote private donor code.** Test fixtures must be **synthetic** replicas of
  observed shapes, never verbatim completions; raw output and derived breakdowns stay in
  gitignored roots and never reach a committed file.
