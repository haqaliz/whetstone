# Card — `p2-yield-probe`

**Type:** feat · **Branch:** `feat/p2-yield-probe/aliz` · **Owner:** aliz
**Started:** 2026-08-05 · **Source:** inline brief (no GitHub issue; the id is a slug)

---

## Why there is no issue body

Whetstone's tracker is GitHub Issues, but this unit of work was not filed as one: it came out of
a `whetstone-next` ranking run over the repository's own files on 2026-08-04, immediately after
P1 closed. The id is therefore a descriptive slug rather than a number, and the brief below is
the source of truth for Phases 2–5.

## Brief

P1 is closed but its pivot signal fired: `reports/baseline/report.md` records **0 of 63** solved
for all three candidate bases. Deriving from `reports/baseline/report.json`, **142 of the 152
verdict-reaching source-B rollouts never got a patch onto disk** (`no_diff` 43, `not_applied` 99),
leaving **10** where the held tests actually judged a fix. So the zero is dominated by the
generation contract, which `reports/baseline/report.md:58,95` already discloses as an unpinned
input that moves the numbers.

Change what the base is asked to emit — search/replace or whole-file edits, converted to a unified
diff by the harness, with a raised token budget — and re-measure on the same declared source-B
set. **The verifier is out of scope and must not be touched:** this is not a looser reward, and
the PRD must say so and add a dated note to `docs/ROADMAP.md` § 4, since the pivot signal names
only "an easier task stratum or a larger base".

## Acceptance criteria (test-first)

1. The failure-mode split is **derived in `reports/`**, never restated in a planning doc
   (`CLAUDE.md`: one home per figure).
2. The edit-format converter is adversarially tested against
   `docs/planning/p1-baseline-bakeoff/generation/spec.md` AC5: an edit touching a path in
   `task.test_blobs` is converted **unmodified** and still triggers STRICT's `patch-scope`
   refusal. A converter that sanitises turns a caught cheat into an uncaught one — the single
   largest risk in this slice.
3. Raw model output is persisted per rollout (gitignored, local) so the next contract iteration
   replays offline instead of regenerating.
4. The re-run publishes under `reports/` with an explicit disclosure that the contract changed
   and that its figures are **not comparable** to the existing baseline report.
5. If yield is still zero, that is the publishable finding, and it is what finally justifies the
   roadmap's easier-stratum / larger-base responses on evidence.

## Known caveat, carried from the ranking

**Raw generations were not persisted** by the P1 bake-off — `journal.py` writes `prompt_sha256`
and `detail` only, no model text. So (a) any contract change costs a full regeneration
(`reports/baseline/report.md:82`: 5000.9s of generation for 189 rollouts, ~1.4h), and (b)
persisting raw output belongs in this slice so the *next* iteration is free.

`NOT_APPLIED` conflates a malformed diff with a correct-intent-but-wrong-context one, so the 142
shows the zero **is not yet attributable to reasoning** — it does not predict a non-zero yield.

## Skill defect, re-recorded

The `whetstone-begin-fast` skill writes Phase 1 output to `docs/planning/_card/issue.md`.
Three live citations point into `_card/understanding.md` by section number
(`docs/ROADMAP.md:159`, `tests/adversarial/test_cheats.py:270`, `tests/test_docs.py:50`), all
three verified still live on 2026-08-05, so overwriting the card would break them. Artifacts
therefore live in `docs/planning/p2-yield-probe/`, following the precedent set by
`docs/planning/p1-preregistration/prd.md` D7. The skill files are stale in other ways too
(both `whetstone-next` and `whetstone-worktrees` still describe the repository as greenfield with
no `pyproject.toml`), which `docs/planning/p1-baseline-bakeoff/prd.md:317` already records as
out-of-scope-but-known.
