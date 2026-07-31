# feat p1-baseline-bakeoff — the base-model bake-off and `reports/baseline/` (ROADMAP P1, slice 5)

## Source

**FALLBACK path.** No GitHub issue exists. `gh issue list --state all --limit 30` returns
"No Issues" against `haqaliz/whetstone`, and the `id` is a slug, not a number. This is the
expected case for this repo — every prior unit of work took it (P0 `3662255`, P1 slice 1
`621831e`, slice 2/3 PR #6, slice 4 `f317b89`).

The upstream spec is committed: `docs/ROADMAP.md` § 4 "P1" exit criterion 5 (`:354`), its
status note (`:364-374`), the pivot signal (`:387-389`), the baseline protocol (§ 5, `:486-496`),
and `PREREGISTRATION.md` §§ 2–4 and § 7.3. **The roadmap and `PREREGISTRATION.md`, not this card,
are the authority** — and where they disagree with each other, `PREREGISTRATION.md` is the
committed public commitment and wins.

## Brief

Reproduced verbatim from the `whetstone-next` handoff the user acted on by invoking
`wbf feat p1-baseline-bakeoff`:

> Close the last open P1 exit criterion (docs/ROADMAP.md:354, :364): a base-model bake-off run
> against the working STRICT verifier, committing reports/baseline/ with full provenance (candidate
> model revisions, seeds, task set hash, interpreter and tool versions), scoring each candidate open
> MLX base on the 66 source-B tasks (tasks/local-ledger.json) and on source A's single instance
> pallets__flask-4045 — reported per-instance, never as a rate, per PREREGISTRATION.md:149-155.
> Its output closes PREREGISTRATION.md §7.3 (which base is fine-tuned).
>
> Caveat to settle in the dig before any code: this is base SELECTION, not the pinned baseline.
> PREREGISTRATION.md:126-138 scores the pinned baseline on the held-out source-B split, which does
> not exist yet (§7.1, closed in P3), and "measured once, re-measured never" must not accidentally
> bind to a bake-off number. The report must state which measurement it is. Also: inference enters
> the repo here for the first time — put rollout/generation in a NEW package, do not widen
> tests/test_no_inference_on_reward_path.py to cover it, and keep the model boundary injectable so
> the suite still runs without mlx (pyproject.toml:25-29).
>
> Acceptance criteria, written first (test-first repo):
> 1. A test proves the reward path guard still passes with the new inference package present, and
>    that the guard's scope was not widened to include it.
> 2. A test proves the scoring harness runs end-to-end against a fake/stub model with zero mlx
>    import, and that a model-authored patch touching a held test file is REFUSED by STRICT.
> 3. A determinism test: same seed + same pinned inputs -> byte-identical bake-off report payload.
> 4. A test asserts the committed report carries every provenance field PREREGISTRATION.md:126-128
>    names, and that it labels itself base-selection rather than the pinned held-out baseline.
> 5. A docs test asserts CLAUDE.md and docs/ROADMAP.md are updated in the SAME commit, so "no number
>    about a model exists" stops being claimed the moment one does.

## Why this slice, per the `whetstone-next` ranking

- It is the **only open P1 exit criterion**. `docs/ROADMAP.md:364` — *"One criterion remains open,
  and it is not nearly done. `reports/baseline/` does not exist."* Slices 1–4 tick the other five.
- Its **ordering is now legal**. `PREREGISTRATION.md:255-259` (§ 7.3) says which base is fine-tuned
  is decided *by* this bake-off, and the report's commit *"must be later than this file's"* — that
  file landed in `f317b89`, so the bake-off is both unblocked and pre-registered.
- It is the **only** work that can fire P1's pivot signal (`docs/ROADMAP.md:387` — *"if no candidate
  base solves any held-out task, expert iteration has nothing to bootstrap from"*) or answer the
  Apple Silicon capacity question (`:594-596`, *"discovered in the P1 bake-off, before the loop is
  built around it"*). P2's rollouts are blocked on knowing which base to sample from.
- It produces **the project's first number about a model.** Every status block in the repo
  currently asserts that none exists; those assertions become false in this commit.

## The upstream spec (authoritative)

`docs/ROADMAP.md:305-356`, P1's six exit criteria, and which this slice takes:

| # | P1 exit criterion | This slice |
|---|---|---|
| 1 | `uv run pytest tests/adversarial/` exits 0 | **Shipped** (PR #5) — must stay green |
| 2 | `tests/test_no_inference_on_reward_path.py` exits 0 | **Shipped** (PR #5, widened PR #6) — must stay green, and **must not be widened to the new inference package** |
| 3 | `whetstone verify --task … --patch …` emits a verdict | **Shipped** (PR #5/#6) — this slice becomes its first programmatic caller |
| 4 | `tasks/` holds instances from both sources with committed provenance | **Shipped** (PR #6) — 66 source-B, 1 source-A; this slice is the first thing to *score* them |
| 5 | A baseline bake-off report exists under `reports/baseline/` | **In — the whole slice** |
| 6 | `PREREGISTRATION.md` is committed | **Shipped** (`f317b89`) — this slice must not contradict it |

## The one thing this card exists to prevent

**This bake-off is base *selection*. It is not the pinned baseline.** They are different
measurements with different task sets and different rules, and merging them would corrupt the
headline this project has already pre-registered.

- `PREREGISTRATION.md:126-128` — the pinned baseline is *"the untrained open base, scored on the
  **held-out set**"*.
- `PREREGISTRATION.md:242-247` (§ 7.1) — **the held-out split does not exist**, is open, and is
  closed in P3 *"by a dated amendment … committed before the split is used to score anything"*.
- `PREREGISTRATION.md:129-138` — *"measured once, re-measured never"*, and a change to any pinned
  input *"invalidates the series"*.

So: a bake-off number computed over all 66 source-B tasks **cannot** be published as the pinned
baseline, and must not be allowed to bind the once-only rule. `docs/ROADMAP.md:354` names the
artifact *"a baseline bake-off report"* and `:370` describes its job as *"scores candidate bases per
source"* — selection. The report must say so in its own text, in a form a test can check.

## Shipped state this builds on

- `master` @ `b6f8228`, no tags, nothing released. `uv sync` + `uv run pytest` in this worktree:
  **396 passed** (verified 2026-07-30) — the "greenfield / `uv sync` will fail" language in
  `whetstone-next` and `whetstone-worktrees` is stale.
- `src/whetstone/verify/` — the reward: `task.py` (frozen `Task` + `load_task`), `verdict.py`
  (`UNVERIFIED` ranks above `PASS`), `sandbox.py` (Seatbelt deny-all), `strict.py`, `weak.py`,
  `repo.py`. `strict.py:120-145` is explicit that the reward **resolves nothing and installs
  nothing**: *"A caller that wants a task's declared environment resolves it first and hands the
  answer down."* This slice is that caller.
- `src/whetstone/tasks/` — 14 modules: the manifest contract, `environment`, canonical held paths,
  the directory loader, the source-B miner, the source-A four-gate filter, the liveness prover and
  the ledger.
- The corpus: 66 source-B tasks in gitignored `tasks/local/` with committed evidence in
  `tasks/recipes/*.json` + `tasks/local-ledger.json`; 1 source-A instance `pallets__flask-4045`
  with 299 refusals in `tasks/public/ineligible.json`.
- `pyproject.toml:20` — `dependencies = []`, with `mlx = ["mlx-lm>=0.31"]` as an optional extra
  (`:25-29`) whose comment says the test suite **must not** depend on mlx. This slice is the first
  code to use that extra.

## Open questions carried in from the selection (for the dig to close)

1. **What is the bake-off's task set, given the held-out split doesn't exist?** All 66, or a
   declared subset? Whatever is chosen must not pre-empt § 7.1, and the report must record the set
   by hash so a later held-out split can be defined against a known input.
2. **Which candidate bases, and where do the weights come from?** § 7.3 forbids naming one in
   advance; the bake-off decides it. But downloading MLX weights is a **network operation on a new
   path**, and `docs/ROADMAP.md:420-422` currently declares exactly one network exception (the
   public-instance fetch). Either this is a second declared, human-run, provenance-committed
   exception or it is a violation — decide and write it down.
3. **How does a base model turn a task into a patch?** There is no prompting or diff-extraction
   surface in the tree. What the model is shown (problem statement? repository files? which?) and
   how its output becomes a patch is the whole generation contract, and it is unbuilt.
4. **Can this machine actually run it?** `docs/ROADMAP.md:594-596` makes capacity an open question
   to be answered *here*. Measure it rather than assume it, and if the answer bounds the candidate
   set or the task set, that bound is a finding to publish, not a detail to hide.
5. **What does a bake-off number mean when the generator is untrained and unprompted?** If every
   candidate scores zero STRICT-PASS, that is the pivot signal (`:387`) — and it must be
   distinguishable in the report from "the harness was broken", or the pivot cannot be trusted.
6. **`UNVERIFIED` accounting.** A candidate whose task errors out is not a candidate that failed.
   The report needs the same three-way discipline the verifier has, and `UNVERIFIED` may never be
   folded into the failure count to make a base look worse or better.

## Related work

- **`f317b89`** (P1 slice 4) — `PREREGISTRATION.md`, the direct upstream and the binding
  constraint. `docs/planning/p1-preregistration/` is the artifact precedent.
- **PR #6** (`201be6d`) — slices 2 and 3: the corpus this scores, plus `import_roots` and the
  false-PASS fix that makes scoring an unfamiliar patch trustworthy at all.
- **PR #5** (`621831e`) — slice 1: the STRICT verifier this calls, and the ten-cheat corpus
  (cheats 6 and 10 remain documented residuals).
- **Belay** (`~/dev/at/belay`) — `docs/ROADMAP.md` § 7 lists what is taken; nothing in Belay
  generates rollouts, and the replay substrate is declined explicitly *because* "parallel calls
  deliberately yield `UNVERIFIED` so batched rollouts produce no signal" (`CLAUDE.md`). No help
  is coming from there for this slice's generation half.

## Labels / comments

None — no issue exists, so there are no labels, linked PRs, or comments to gather.

## Note on this file

`docs/planning/_card/issue.md` is id-free by design (`whetstone-begin-fast` § Phase 1) and each
unit of work **overwrites** the previous one's card on its own branch. P0's card is preserved in
history at `3662255`, P1 slice 1's at `621831e`, slice 2/3's at `201be6d`. Flagged as a workflow
wart, not a blocker.

## Attachments

None.
