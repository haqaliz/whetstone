# PRD — night-corpus-remine

**Unit:** `feat/night-remine-before-draw/aliz` · **Slug:** `night-corpus-remine` · **Written:**
2026-10-11 · **Type:** feature, on the loop (off the reward path). **Source:** inline brief
(`docs/planning/_card/issue.md`); no GitHub issue exists.

**Core loop element:** ② the nightly improvement loop — the night grows the corpus it learns from.
③ is constrained: the held-out split is the gate's scoring input and must stay fixed and sealed.
① is untouched.

## Problem Statement

Whetstone's nightly loop is built, but its corpus is frozen. `whetstone run --night` reads the
task directories it is handed and never mints new ones (`src/whetstone/loop/night.py:240` is the
only private-corpus read). `whetstone mine` exists and produces verified tasks from a real
donor's commits (`src/whetstone/tasks/mine.py:154`), but it is operator-invoked only — nothing in
`src/whetstone/loop/` imports it.

`docs/ROADMAP.md:794-800` (§ 13) names the consequence as a gap in the thesis: *"Expert iteration
against a fixed task set converges by construction: a night can only ever exhaust what the base
can already do. 'A model that gets better over time' needs new verified tasks arriving, and the
honest source of those is the user's own new commits — not a generator."* The product promise is
*"point it at your tasks"*; a corpus that never grows makes that a one-shot experiment rather
than a loop.

**The ask.** Before it draws, the night re-mines the user's declared donor repo(s) — using the
existing miner — so the pool it learns from grows with the user's own commits, while the
pre-registered held-out split stays exactly where it is.

**Evidence it is real, not hypothetical.** The miner and its liveness proof already run offline
against a local donor and are covered by tests (`tests/test_mine_cli.py`, `tests/test_donor.py`,
`tests/test_liveness.py`). The only missing piece is the loop calling it. The gap was named for
promotion out of post-horizon by § 13 and listed as a roadmap "gap … named, not built" by
`docs/planning/whole-function-edit-finding/prd.md:245-246`.

## Goals & Success Metrics

- **The night grows its own corpus, incrementally.** Given a donor path and label, a night mines
  only candidates whose commit sha is not already in the corpus, bounded by a declared limit, and
  draws against the grown pool.
- **The held-out split does not move.** The committed held-out document's `membership` and
  `document_digest` are byte-unchanged, and the corpus recomputation test stays green.
- **The growth is attributable.** The run ledger records which tasks the night added, so a reader
  can attribute a training set to a corpus that grew — no file contents, ids and labels only.
- **Nothing new is a no-op, never a failure.** A donor with no new candidates (or an absent or
  unprovisionable donor) lets the night proceed on the existing corpus and say so.
- **The reward and the gate are untouched.** `src/whetstone/verify/` byte-identical; the AST
  guard green; a night without the re-mine flags is byte-identical to today.

Success is a merged, green tree with a synthetic-donor night test proving the increment (new
tasks land, are drawn, are recorded) and the invariants above. **Not** a yield claim: a bigger
pool says nothing about whether any candidate improves.

## User Personas & Scenarios

- **The founder/operator pointing the loop at their own repos.** They add commits to their repo
  during the day; the next night picks up the new fixable bugs as training tasks, so the loop
  keeps having something to learn from. Scenario: operator runs `whetstone run --night … --remine
  /path/to/repo --remine-label donor-a --remine-out tasks/local/remined --remine-limit 5`; the
  night mints the new commits, draws against them plus the existing corpus, and the morning
  report shows the pool grew.
- **The reader of a night's evidence.** Wants to see, from the ledger alone, which tasks were
  added this night and that the held-out split was unchanged — without reading the corpus.

## Requirements

Decisions confirmed in the requirements interview: **the pinned input is the *scoring* held-out
split, not the training pool** (training-pool growth needs no `PREREGISTRATION.md` amendment; the
night records the delta); **re-mined tasks live in a separate training-only root** (the document's
corpus roots are untouched); **the first slice is a bounded re-mine block on the night door**,
proven against the synthetic donor.

### Must-have

- **M1 — Incremental re-mine.** Given donor path(s) and label(s), the night mints only candidates
  whose trailing-12-hex commit sha is not already present in the corpus the night will draw from,
  bounded by a declared limit. This is new behaviour: `mine()` today re-attempts the same
  oldest-by-sha candidates on every call (no dedup, `src/whetstone/tasks/mine.py:197-218`), so the
  filter must be added (a skip-set parameter on `mine()` or a thin re-mine wrapper).
- **M2 — Separate training-only root.** New manifests are written under an operator-named root
  outside `tasks/local/donor-a` / `tasks/local/donor-b` (e.g. `tasks/local/remined/`). The night
  unions that root into the corpus it loads. The donors' roots — which the committed held-out
  document's `corpus` is bound to by `tests/loop/test_heldout_document.py:139` — are never
  written.
- **M3 — The delta is recorded in the run ledger.** The `whetstone-run/3` ledger gains the minted
  task ids and their donor labels, recorded under `task_set` (ids only, never file contents). A
  night **without** the re-mine flags produces a byte-identical ledger.
- **M4 — Nothing-new is a no-op.** A donor with no un-minted candidates — or an absent,
  non-repository, or unprovisionable donor — does not fail the night: the night proceeds on the
  existing corpus and the delta is empty (recorded). This mirrors the miner's own per-candidate
  rejection discipline (`src/whetstone/tasks/mine.py:216-220`) without inheriting the CLI's
  `FAIL_EXIT` on zero minted.
- **M5 — Held-out invariant.** The held-out membership and `document_digest` are unchanged by a
  re-mine; `whetstone check-leakage` behaves exactly as before (new ids match no held-out member);
  the held-out recomputation test stays green.
- **M6 — Reward untouched.** `src/whetstone/verify/` and the `test_blobs` boundary unchanged;
  `tests/test_no_inference_on_reward_path.py` stays green (the miner already lives under the
  guard's `src/whetstone/tasks/` scope).
- **M7 — Cost-bound and offline.** The re-mine is bounded by a declared limit and the existing
  per-candidate timeout; it runs offline against a warm uv cache; a cold cache (every candidate
  refused `NotProvisionable`, `src/whetstone/tasks/environment.py:557-585`) is a reported no-op,
  not a crashed night.
- **M8 — Determinism scoped to donor state.** Same donor state + same seed → byte-identical
  training set (`dataset.json`, `train.jsonl`). A donor that advanced changes the set by
  construction — that is the point.

### Should-have

- **S1 — CLI shape.** `--remine <donor>` (repeatable), `--remine-label <label>` (repeatable, paired
  by position), `--remine-out <dir>`, `--remine-limit <N>` on `whetstone run --night`; the flags
  are validated (a donor without a label, or a re-mine without a limit, is a usage error).
- **S2 — The night sheet documents the re-mine block**, held by the existing runbook guard
  (`tests/test_night_runbook_guards.py`).

### Nice-to-have

- A standalone `whetstone remine` command that produces the same delta, for an operator who wants
  to mine outside a night. Deferred; the night-door block is the path.

## Technical Considerations

- **Insertion point.** The re-mine runs at the top of `run_night` (`src/whetstone/loop/night.py:179`),
  before `load_task_roots(tasks)` (`:240`), so the grown set is what `freeze()` (`:299`) computes
  the generation contract over. The night must first load the existing corpus's ids to know which
  candidates are new.
- **The miner's cost and offline contract.** One fresh venv build + five sandboxed pytest runs per
  candidate (`mine.py:265-322`); `uv sync … --offline` needs a warm cache (`environment.py:236-254`);
  `warm-cache` is the one network step (`warm.py`). The limit is the cost bound. `mine()` takes
  `scratch` and `timeout` with no defaults to the caller.
- **Where the miner's own ledger/recipes go.** `mine(donor, out, …, tasks_root=…)` writes
  `tasks_root/local-ledger.json` (merged by id) and `tasks_root/recipes/<label>.json`. The re-mine
  points `tasks_root` at the training-only root so the committed `tasks/local-ledger.json` and
  `tasks/recipes/` (the declared-corpus record) are untouched.
- **Ledger field placement.** `_body` writes fields explicitly and every body key is a seal claim
  (`src/whetstone/loop/ledger.py:383-449,51-53`). Nesting the delta under the existing `task_set`
  object changes only the `task_set` claim's bytes, leaving the top-level key set — and
  `morning._KNOWN_FIELDS` (`src/whetstone/loop/morning.py:207,301`) — unchanged. The spec must
  confirm the `/3` reader tolerates (or requires) the nested field; a night without `--remine` must
  not gain it.
- **Held-out binding.** `tests/loop/test_heldout_document.py:139` asserts the document's `corpus`
  (66) equals the task count loaded from the primary's `tasks/local/donor-{a,b}` (`:47,91-110`). A
  separate re-mine root never enters that read, which is why M2 chooses it.
- **Privacy.** Manifests record the donor's absolute local path in `repo_url`
  (`src/whetstone/tasks/mine.py:380`); the training-only root is under gitignored `tasks/local/`, so
  nothing new is committed and nothing leaves the box.
- **No fetch.** The miner reads the donor's local history (`src/whetstone/tasks/donor.py:1-6`); a
  donor that is not already up to date on disk mints nothing new — stated, not hidden.

## Risks & Open Questions

- **🔴 The pre-registration boundary is a policy choice, now made but newly recorded.** The
  interview resolved that § 3's "task set" means the *scoring* held-out split, so training-pool
  growth needs no amendment. That reading is not stated anywhere in `PREREGISTRATION.md` today;
  this PRD records it explicitly, and the docs corrected in this unit must say so plainly rather
  than leave it implied. If the reading is wrong, this unit is the wrong shape.
- **🟡 Mining can cost more than the night.** Hours per candidate vs. a night already measured in
  hours (`docs/planning/p2-rollouts/night-door/runbook.md:194-197`). The limit bounds it; the runbook
  must recommend a small limit first.
- **🟡 Re-mine idempotence across nights.** Without a filter, the same candidates re-mint every
  night with a new `minted_at` (`mine.py:307,369`). M1's skip-set is what makes nights 2..N
  cheap; the spec must pin the filter's definition (sha12 against the loaded corpus).
- **🟡 Cold cache.** An unattended night on a cold uv cache mints nothing and must say so (M7),
  not crash. Whether that is a warning or a refusal is a spec decision.
- **🟢 The declined generator stays declined.** Only the user's own commits are mined; the
  proposer/solver loop (`docs/ROADMAP.md:809-812`) is untouched.
- **Open — placement of the delta field** (nested `task_set.remined` vs. a top-level field) is left
  to the `record` spec; the invariant is no-`--remine` byte-identity.

## Out of Scope

- Re-deriving the held-out split or changing the held-out document — § 10.16 spent that; re-running
  it re-rolls the membership and drops the series.
- Any change to the reward path, the gate's rule/exits/retry discipline, or the corpus's declared
  66-task record (`tasks/local-ledger.json`, `tasks/recipes/`).
- A task generator (proposer/solver) — declined by `docs/ROADMAP.md:809-812`.
- A yield claim, a larger base, raising `k`, the Mac/32B operator night, the § 3 baseline spend,
  running the gate, or publishing.
- Network access of any kind: the miner is offline; `warm-cache` is the operator's separate step.

## Acceptance criteria (testable, written first)

Each is a test that fails on the current tree and passes after the change (strict TDD; `uv run
pytest` green on the branch):

1. **AC1 (M1, M2, M3)** — over the synthetic donor (`tests/fixtures/repos/donor.py`), a night with
   the re-mine flags mints the donor's un-minted candidates into the training-only root, records
   their ids and labels in the ledger's re-mine field, and draws against them (at least one rollout
   is produced for a newly minted task).
2. **AC2 (M4)** — a donor with no un-minted candidates (or an absent donor) lets the night proceed
   on the existing corpus with an empty recorded delta; the night does not fail.
3. **AC3 (M8)** — two nights over the same donor state and seed produce byte-identical
   `dataset.json` and `train.jsonl`.
4. **AC4 (M5)** — before/after a re-mine, the held-out document's `membership` and
   `document_digest` are byte-identical; `whetstone check-leakage` on the night's `dataset.json`
   exits as before; `tests/loop/test_heldout_document.py` stays green.
5. **AC5 (M6, M3)** — the diff touches nothing under `src/whetstone/verify/`;
   `tests/test_no_inference_on_reward_path.py` is green; and a night **without** the re-mine flags
   produces a byte-identical ledger and dataset to the pre-change tree.
6. **AC6 (S1)** — CLI validation: a `--remine` donor without a paired `--remine-label`, or a
   re-mine without `--remine-limit`, is a usage error (exit 2), not a silent default.
7. **AC7 (M7)** — a cold-cache / unprovisionable donor is a reported no-op (the night proceeds),
   asserted against an injected miner that raises `NotProvisionable` per candidate.

## Aspect decomposition (proposed)

1. **`remine`** — the incremental miner (skip-set/`remine` wrapper) and the night-door flags +
   root union (`src/whetstone/loop/night.py`, `src/whetstone/tasks/mine.py`, `src/whetstone/cli.py`).
   Owns AC1, AC2, AC6, AC7.
2. **`record`** — the ledger's re-mine delta and the no-`--remine` byte-identity
   (`src/whetstone/loop/ledger.py`; any reader/`_KNOWN_FIELDS` touch). Owns AC1's record half, AC5's
   byte-identity half.
3. **`guards`** — held-out invariant, reward untouched, determinism (tests across
   `tests/loop/`, `tests/adversarial/`). Owns AC3, AC4, AC5.
4. **`docs`** — the night sheet's re-mine block, STATUS, CHANGELOG (`Unreleased`), the ROADMAP § 13
   note, the `PREREGISTRATION`/CLAUDE cross-reference for the boundary reading. Owns S2.

Sequencing: `remine` and `record` are independent code aspects (the record depends on the delta
shape, so `record` can land with or just after `remine`); `guards` wraps both; `docs` lands last
in the same commit as the write-up, per the repo's rule. Size: medium — the miner change is small,
the night wiring and the ledger/reader treatment are the bulk.
