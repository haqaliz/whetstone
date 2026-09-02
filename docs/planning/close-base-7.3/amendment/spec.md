# Spec — amendment (close-base-7.3)

**Aspect:** `amendment` — the only aspect of the unit. **Written:** 2026-09-02.
**PRD:** `docs/planning/close-base-7.3/prd.md` · **Understanding:** `../understanding.md`.

## Problem slice and user outcome

Close `PREREGISTRATION.md` § 7.3 ("Which open base is fine-tuned") by a Type 1 amendment
under § 8.1, committed before night #1 trains, so the launch path's first operator step is
satisfied and the pre-registration's § 8.4 honesty discipline holds. The reader of
`PREREGISTRATION.md` can then answer "which base did the night fine-tune, and was it fixed
before the measurement?" from § 10.10 + the amendment log, and verify the timestamp with
`git log` (§ 9).

## In-scope requirements

1. § 10.10 amendment (Type 1, closes § 7.3): base repo_id
   `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`, immutable revision
   `d1e3b690c8e225d7795bccddf971ca6be68b2012`, provenance home `weights/provenance.json`
   (per-file sha256, re-hashed on every run, no aggregate digest minted), evidence cited
   (`docs/planning/larger-base-arm/finding.md`, `reports/larger-base/`) never restated, and
   the pinned no-measurement sentence.
2. Amendment log row appended (Date | "…; § 7.3 is closed by the amendment below (§ 10.10)"
   | "1 — closes an open item" | "Yes").
3. Status paragraph (`:321-324`): the three § 7.3-specific sentences replaced by the closure
   sentence; nothing else above § 10 changes.
4. Shape guard in `tests/test_docs.py`, RED first (exact pinned strings in the plan).
5. ROADMAP dated correction blockquote after `docs/ROADMAP.md:370-372`; CLAUDE.md "Still
   open" bullet settles; STATUS.md top entry; CHANGELOG `## [0.13.0] - 2026-09-02` section.
6. Honesty constraints: no success threshold, no `%`/`percent`/`percentage`, no
   placeholders, no figure about a model in any spelling, no new unguarded roadmap citations.

## Out-of-scope boundaries

No change under `src/`; no edit to § 7.3's own paragraph, § 10.6, § 10.9, or existing log
rows; no night/gate/baseline run; no aggregate weights digest; no new data leaves the box.

## Acceptance criteria (testable, written first)

1. **AC1** — `PREREGISTRATION.md` carries § 10.10 with "Type 1 (§ 8.1): closes § 7.3",
   the no-measurement sentence, and the repo_id (cross-pinned against
   `test_night_runbook_guards.RETAINED`).
2. **AC2** — the amendment log's last row closes § 7.3 with a Type 1 marker and "Yes".
3. **AC3** — the status paragraph's § 7.3 sentences are gone, replaced by the closure
   sentence; `git diff` shows nothing else above § 10 changed.
4. **AC4** — the new guard fails against today's `PREREGISTRATION.md` (RED) and passes
   after the amendment (GREEN).
5. **AC5** — ROADMAP/CLAUDE/STATUS/CHANGELOG updated; `tests/test_docs.py` (including any
   shifted-anchor fix in `ROADMAP_CITATIONS`) green.
6. **AC6** — `uv run pytest`, `uv run ruff check .`, `uv run mypy src/` all green in the
   worktree.
7. **AC7** — operator-verified: repo_id + revision + per-file hashes match the gitignored
   `weights/provenance.json` in the primary checkout (documented, not automated).

## Dependencies and sequencing

Single sequential chain: RED guard → GREEN amendment → state files → full gate + operator
verification. No parallel aspects. `uv sync` in the worktree precedes everything (no venv
exists there yet).

## Open questions or risks

- **Shifted ROADMAP anchors**: inserting the blockquote after `:375` shifts every later
  line; any `ROADMAP_CITATIONS` anchor below the insertion point must be adjusted in the
  same commit (the test will say which, failing first).
- None else — the dig and interview closed the rest.