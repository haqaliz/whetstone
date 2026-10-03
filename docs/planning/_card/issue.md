# feat checkpoint-provenance-seal — seal `provenance.json`'s own claims into the checkpoint digest

**Core loop element:** ③ the never-regress promotion gate (the trust its inputs carry). The reward
(①) does not change.
**Roadmap:** M2 of `docs/ROADMAP.md` § 14 — "Make the gate able to answer"; follow-on of
`docs/planning/gate-leakage-guard/` (its STATUS "Open follow-ups" lists this first).
**Source:** inline brief — the `whetstone-next` handoff (2026-10-03). No GitHub issue exists for
this unit.

## Brief

A trained checkpoint's `provenance.json` is hashed for its files but not for its own claims.
`sft.verify_checkpoint` re-hashes the listed files and checks that `digest` reduces from them, but
`dataset_digest`, `base_repo_id`/`base_revision` and `backend` sit outside any seal.
`check-leakage` and the `whetstone-promotion/2` record both trust `dataset_digest` to name the
candidate's night, so a hand edit could hide a leak (`docs/planning/gate-leakage-guard/finding.md`
§ 5: "RECORDED provenance, not verified"). Seal those fields into the checkpoint digest under a new
checkpoint schema version, written test-first.

## Acceptance criteria (tests first)

1. Editing `dataset_digest`, the base repo or revision, or the backend in a v2 checkpoint's
   `provenance.json` makes `verify_checkpoint` raise `CheckpointUnverified`, naming the field.
2. A v1 checkpoint (the `checkpoints/portability-arm` shape) still verifies, and every consumer
   (`gate`, `check-leakage`, the promotion record) reports its dataset link as "recorded, not
   sealed", never "verified".
3. A v2 checkpoint's dataset link is reported as verified by `check-leakage` and the promotion
   record.
4. Nothing under `verify/` or `tasks/` changes; the gate's rule and exits are byte-identical.
5. The Torch and MLX trainers write the same v2 shape.

## Known caveat (from the handoff)

Changing what `digest` covers changes the digest of every existing checkpoint, and
`checkpoints/portability-arm` (`48eae99b0d32`) is cited by that value in committed docs. Use a
schema bump and leave v1 verifiable. Never rewrite an old checkpoint in place, and never let v1
render as verified. Decide in the dig whether `whetstone-promotion/2` needs a bump or can carry a
`sealed: bool`. Describe the tree as it ships and write nothing about in-flight work; append the
STATUS entry in the same commit that lands the capability.
