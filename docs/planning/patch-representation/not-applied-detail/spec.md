# Spec — `not-applied-detail`

**PRD:** `../prd.md` § 4.1 (M1–M3).

## Problem slice

A `NOT_APPLIED` rollout records no reason. STRICT's `patch-apply` verdict carries one — a
`PatchError` message wrapping git's own report (`verify/repo.py:100,118`, surfaced at
`verify/strict.py:171-183`) — but `scoring._verify` copies only each verdict's `kind`, so the
message never reaches `Rollout.detail`. Night-006's 279 refusals had to be diagnosed by joining
transcripts to journals by hand (GitHub #64).

## In scope

- `scoring._verify`: when `_classify` returns `Outcome.NOT_APPLIED`, set `detail` to the sole
  `patch-apply` verdict's `message`.
- The `Rollout.detail` field comment updated to say so.

## Out of scope

- Any change to `verify/` — the message already exists.
- Back-filling `detail` into existing journals (they are evidence; they are not rewritten).
- Any other outcome's `detail`.

## Acceptance criteria (each becomes a failing test first)

1. A diff git refuses to parse yields `outcome == NOT_APPLIED` and a `detail` containing
   `"could not be parsed"` (the `declared_paths` path).
2. A diff git parses but will not apply yields `NOT_APPLIED` and a `detail` containing
   `"did not apply"` (the `apply_patch` path).
3. `SOLVED`, `NOT_SOLVED` and `OUT_OF_SCOPE` rollouts keep `detail == ""` — the change is scoped to
   `NOT_APPLIED`, and a patch-scope refusal is not re-described.
4. `strict`, `weak`, `verdict_kinds` and `outcome` are unchanged for every case above.
5. A journal step carrying the new `detail` round-trips through `journal._encode`/`_decode`.
