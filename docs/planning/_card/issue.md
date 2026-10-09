# feat run-document-seal — seal the run's own documents (`dataset.json`, `ledger.json`)

**Core loop element:** ③ the never-regress promotion gate (the trust its inputs carry); ④ the
morning report's evidence. ① the reward does not change: nothing under `verify/` or `tasks/` is
touched, and the gate's rule and exits stay byte-identical.
**Roadmap:** M2 of `docs/ROADMAP.md` § 14 — "Make the gate able to answer"; the follow-on named in
`docs/planning/checkpoint-provenance-seal/prd.md` § 7–8 and the first buildable item in
`docs/STATUS.md`'s 0.20.0 open follow-ups.
**Source:** inline brief — the `whetstone-next` handoff (2026-10-07). No GitHub issue exists for
this unit; verified 2026-10-07 that the only open issues are #64 (patch representation) and #62
(held-out split keyed on task id), neither related.

## Brief

Seal the run's own documents — `dataset.json` and `ledger.json` — so both ends of the
checkpoint↔run provenance link are tamper-evident; today only the checkpoint side is
(`whetstone-checkpoint/2`), and `check-leakage` discloses that "the run's dataset.json is not
sealed" (`src/whetstone/loop/check_leakage.py:406`). This is the unit the last PRD named as
separate (`docs/planning/checkpoint-provenance-seal/prd.md` § 7–8) and the first buildable item in
`docs/STATUS.md`'s 0.20.0 open follow-ups. Caveat: `dataset.json` already carries the `digest` a
checkpoint records as `dataset_digest`, so the schema bump must keep that link sound for both old
and new nights — decide that in the dig before writing tests.

## Acceptance criteria (from the handoff)

1. A v2 dataset/ledger document refuses a top-level edit, an unlisted key, or a moved claim by
   name (tamper-evidence, not authentication).
2. v1 documents — night-001's and `checkpoints/portability-arm`'s — still read unchanged, are
   never rewritten, and are never reported as sealed.
3. Every reader (`check_leakage`, `check_probe`, `morning`, `honest_report`, `fuse`) tolerates v1
   and says which side was sealed.
4. Nothing under `verify/` or `tasks/` changes and the gate's rule and exits stay byte-identical.
