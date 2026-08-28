# Spec — `local-home`

**Unit:** `morning-report` · **Aspect 3 of 4** · PRD: `docs/planning/morning-report/prd.md`

## Problem slice

The morning report writes the user's own data — counts and digests derived from private donor
code — and its home was pre-declared before the loop existed: `.gitignore:16-23` reserves
`/reports/local/` with a comment naming **"the morning reports"**. But the guard that protects
every other private artifact would refuse that home: `night._refuse_published_root`
(`night.py:617-635`) rejects **any** path with a `reports` component, and `reports/local/` is
inside `reports/`.

So the rule this aspect writes is the narrower sibling, and the carve-out is not invented here —
it is already recognised twice in the tree: by `.gitignore:23`, and by the one-home guard, which
excludes `reports/local/` by name with the argument *"`.gitignore` reserves it for the user's own
nightly output, which is their data and never ours to assert on"*
(`tests/bakeoff/test_report.py:2076-2077`, `:2087`).

**User outcome:** a morning report can never be written where an outside reader would find it,
and the guard that ensures this cannot be satisfied by pointing at the wrong `reports/`.

## In scope

1. **`_refuse_published_root_outside_local(root, flag)`** — refuse a root inside a `reports/`
   directory **unless** it is under the `reports/local/` carve-out. Reuses `night.PUBLISHED` and
   raises `TranscriptNotPrivate` **by identity**, so this repository keeps one name for "private
   evidence was pointed at a published path".
2. **Checked on the resolved path**, for the reason `night.py:620-622` gives: `reports/../reports/x`
   and a symlinked scratch directory both name a path inside `reports/` while comparing unequal.
3. **`LOCAL = "local"`** as a named constant beside `PUBLISHED`, so the carve-out is a line
   someone has to change rather than a string buried in a predicate.
4. **The documented home is asserted gitignored** via `git check-ignore -v`, trailing-slash form
   (`tests/bakeoff/test_transcript_locality.py:31-40` precedent). This is the assertion that
   actually catches the regression: a `.gitignore` edit is the one change that turns every
   private artifact in this project into a commit.
5. **The one-home guard does NOT move.** It already carves `reports/local/` out. A test asserts
   the carve-out is still there and still argued, so a later tightening that removed it would
   fail here rather than silently making every morning report a published figure.

## Out of scope

- The writer (aspect 2) and the CLI (aspect 4).
- Any change to `night._refuse_published_root` — the night's rule is correct for the night.
- Any change to the one-home guard's file list.

## Acceptance criteria

1. `reports/nightly/x` is refused, naming the flag and `reports`.
2. `reports/local/nightly/night-001` is **accepted** — the control, without which a predicate
   that refused unconditionally would pass every other assertion here.
3. `reports/local/../baseline/x` is refused **on the resolved path**, proving the check is not
   string comparison.
4. A symlink whose target resolves inside `reports/` but outside `reports/local/` is refused.
5. `TranscriptNotPrivate` is raised **by identity** (asserted `is` against the bake-off's class),
   and `PUBLISHED` is the night's own constant (asserted `is`).
6. `reports/local/` is gitignored, asserted via `git check-ignore`, with the invocation proven
   able to fail (a path known not to be ignored is asserted not ignored, so a broken invocation
   cannot pass vacuously).
7. The one-home guard still excludes `reports/local/` — asserted by reading its own filter.
8. **Adversarial:** a morning report written to an accepted path is confirmed not to appear in
   `git status --porcelain` — the end-to-end version of criteria 6, catching the case where the
   ignore rule exists but the path shape dodges it.

## Dependencies & sequencing

Independent of aspects 1 and 2; buildable in parallel. Blocks aspect 4.

## Open questions / risks

- `reports/local/` already holds `arm-a/` and `budget-2048/` from the yield probe, each a
  three-artifact report. The `nightly/` namespace keeps the morning reports from colliding with
  them; the predicate does not police sub-layout, and does not need to.
