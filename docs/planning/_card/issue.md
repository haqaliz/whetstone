# Card — close-base-7.3

**Type:** feat · **Branch:** `feat/close-base-7.3/aliz` · **Owner:** aliz
**Source:** inline brief (no GitHub issue exists; produced by the `whetstone-next` handoff, 2026-09-02)

## Brief

Close `PREREGISTRATION.md` § 7.3 by a **Type 1 amendment under § 8.1**, committed as its own
change **before night #1 trains**: name the fine-tuned base
(`mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`, pinned revision, hash from
`weights/provenance.json`) and the larger-base arm's evidence it was chosen on, add the
dated § 10 amendment and its log row, and introduce no success threshold while rewording
nothing in § 1, § 4, or § 6.

Acceptance criteria, written first and watched failing:

1. The amendment names the base and the arm evidence, matching the night's pinned input
   byte-for-byte (repo_id + revision + hash).
2. § 7.3 is marked closed with a dated Type 1 log row.
3. No success threshold and no figure about a model in any spelling.
4. `tests/test_docs.py` and the full ruff/mypy/pytest suite stay green.
5. Git history proves the amendment predates any night measurement.

Caveat: reconcile append-only with the stale "§ 7.3 is still **open**" sentence
(`PREREGISTRATION.md:321-324`) and § 7.3's "Naming a base here would be the mistake" line
(`:257`) — the closure states the pinned base for this series without contradicting the
swappable-base principle.

## Notes from the handoff

- The launch-path operator chain (`docs/ROADMAP.md` § 12, corrected 2026-09-01) opens with
  this amendment: § 7.3 Type 1 amendment → night #1 → first gated evaluation (candidate:
  night #1's checkpoint; incumbent: the untrained base) → baseline spend → P4 report →
  finding. This unit is the last in-horizon deliverable that is a committed, guarded
  artifact rather than operator GPU execution — it reads no number.
- § 8.1 (`PREREGISTRATION.md:266-268`): an amendment closing § 7.3 must be committed
  **before the measurement it governs runs** — night #1 cannot legally train until this
  lands.
- The evidence the amendment rests on: the larger-base arm produced the first nonzero
  strict-PASS yield with control intact (`docs/planning/larger-base-arm/finding.md:41-53`),
  and that finding states § 7.3 closes only by a Type 1 amendment committed before the
  measurement it governs runs.
- The base: `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`, pinned at
  `d1e3b690c8e225d7795bccddf971ca6be68b2012`, recorded in `weights/provenance.json` by
  hashing every file (`finding.md:20-24`).
- The model to follow: § 10.7 (closed § 7.1) and § 10.8 (closed § 7.2) — both Type 1
  amendments with log rows, committing the sealed artifact in the same commit.