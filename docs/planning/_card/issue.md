# feat p1-task-ingestion — `tasks/` ingestion and the on-disk task format (ROADMAP P1, slice 2)

## Source

**FALLBACK path.** No GitHub issue exists. `gh issue list --limit 10` returns "No Issues"
against `haqaliz/whetstone`, and the `id` is a slug, not a number. This is the expected case
for this repo — the same path P0 (`3662255`) and P1 slice 1 (`621831e`) took.

The upstream spec is committed: `docs/ROADMAP.md` § 4 "P1 — Task contract + verifier"
(exit criteria at `:243-247`) and § 1 "The task family" (`:13-48`). The roadmap, not this
card, is the authority on P1's exit criteria.

## Brief

Reproduced verbatim from the `whetstone-next` handoff the user acted on by invoking
`wbf feat p1-task-ingestion`:

> Build `tasks/` ingestion and the on-disk task format — the remaining unblocked P1 exit
> criterion (docs/ROADMAP.md:243-245). Source B (private: a local commit that turns a failing
> test green) is the on-thesis headline and must be pure and offline; source A (SWE-bench-Lite,
> pure-Python subset) follows docs/ROADMAP.md:420-422 — human-run fetch, committed output,
> seeded offline draw. This slice owns two things slice 1 handed forward: per-instance
> environment provisioning, flagged High/deferred/UNESTIMATED at
> docs/planning/p1-verifier-core/prd.md:358 and named as P1's schedule risk at :378-380 — size
> it in the dig and scope source A down if it doesn't fit rather than faking coverage — and the
> open question at :365 of whether `whetstone verify` takes a task directory or a manifest file.
>
> Acceptance criteria (written first — the repo is test-first):
> 1. A documented on-disk task format; an ingested task round-trips through `load_task`
>    unchanged, with `test_blobs` byte-identical (no str decode — src/whetstone/verify/task.py).
> 2. Source B ingestion runs offline over a local repo and emits a valid manifest with committed
>    provenance; a test asserts no network call on this path.
> 3. Source A's draw is deterministic: same seed -> same instance set, asserted over repeats.
> 4. Liveness, not vacuity: for every ingested task, the empty patch yields STRICT FAIL (the
>    fail_to_pass tests really fail at base_commit) and the reference patch yields STRICT PASS.
>    A task that passes with no patch is an ingestion bug and must fail the build.
> 5. Cheat 10 (docs/ROADMAP.md:160-166): the format declares a held test's transitive
>    dependencies, and ingestion either populates them or records the gap as the documented
>    residual with a test asserting it — never silence.
> 6. `uv run ruff check .` and `uv run mypy src/` exit 0; CI green on macos-latest.
>
> No model is invoked anywhere in this slice; the reward-path import guard
> (tests/test_no_inference_on_reward_path.py) must stay green.

## Why this slice, per the `whetstone-next` ranking

- It is the only **unblocked** P1 exit criterion. `docs/ROADMAP.md:243-247` leaves three open:
  `tasks/` instances from both sources with committed provenance, a bake-off report under
  `reports/baseline/`, and `PREREGISTRATION.md`. Neither `tasks/` nor `reports/` exists on
  `master` (verified 2026-07-28).
- The bake-off is defined as running **against the working verifier** (`docs/ROADMAP.md:210`),
  so it needs task instances — ingestion is its hard dependency, and P2's rollouts depend on
  both.
- Ingestion is where cheat 10 gets narrowed: `docs/ROADMAP.md:160-166` assigns the
  undeclared-dependency residual to task ingestion explicitly — *"declaring a held test's
  transitive dependencies when the task is minted"*.

## The upstream spec (authoritative)

`docs/ROADMAP.md:243-247`, P1's six exit criteria, and which this slice takes:

| # | P1 exit criterion | This slice |
|---|---|---|
| 1 | `uv run pytest tests/adversarial/` exits 0 | **Shipped** (PR #5) — must stay green |
| 2 | `uv run pytest tests/test_no_inference_on_reward_path.py` exits 0 | **Shipped** (PR #5) — must stay green |
| 3 | `uv run whetstone verify --task <fixture> --patch <fixture>` emits a verdict | **Shipped** (PR #5); this slice may extend its input form (see open question 2) |
| 4 | `tasks/` holds instances from both sources with committed provenance | **In — the whole slice** |
| 5 | A baseline bake-off report exists under `reports/baseline/` | **Out** — blocked on this slice, then needs a base model |
| 6 | `PREREGISTRATION.md` is committed | **Out** — separate, unblocked; named as the `whetstone-next` alternate |

Task family and contract: `docs/ROADMAP.md:13-48`. The two sources (`:28-38`): **A — public**
(SWE-bench-Lite, pure-Python subset; comparability, contamination-exposed) and **B — private**
(mined from the user's own repos; the pre-registered headline, uncontaminated, never leaves the
box). Both are always reported.

**The one declared network exception** (`docs/ROADMAP.md:420-422`): *"fetching public SWE-bench
instances touches the network. Following Belay's precedent, the fetch is human-run, its output
committed, and the draw itself pure and offline. Source B never touches the network at all."*

**P1's pivot signal** (`docs/ROADMAP.md:249-252`) belongs to the bake-off, not to this slice —
this slice runs no model. But it is this slice's ingestion that decides whether the bake-off has
a stratum to run against at all.

## Handed forward from P1 slice 1 (this slice owns both)

| Item | Where recorded | Status |
|---|---|---|
| Per-instance environment provisioning for real SWE-bench instances — Belay's pool carries no `FAIL_TO_PASS`/`PASS_TO_PASS`/test patch, and its `eval/` never executes an instance | `docs/planning/p1-verifier-core/prd.md:358` — **High, deferred, unestimated**; named as P1's schedule risk at `:378-380` | **Open — size it in the dig** |
| Whether `whetstone verify` accepts a task *directory* or a single manifest file | `docs/planning/p1-verifier-core/prd.md:365` — *"deferred to the ingestion slice, which owns the on-disk task format"* | **Open — this slice decides** |

## Shipped state this builds on

- `master` @ `621831e`. P0 (PR #3) and P1 slice 1 (PR #5) merged. No tags; nothing released.
- `src/whetstone/verify/` — `task.py` (the frozen `Task` contract + `load_task`), `verdict.py`,
  `sandbox.py`, `strict.py`, `weak.py`, `repo.py`. `src/whetstone/cli.py` exposes
  `whetstone verify --task <manifest.json> --patch <file>` (`cli.py:93-100`).
- `Task` fields (`src/whetstone/verify/task.py`): `task_id`, `source` ∈ {`public`,`private`},
  `repo_url`, `base_commit`, `problem_statement`, `fail_to_pass`, `pass_to_pass`,
  `test_blobs` (path → **bytes**, base64 in the manifest), `provenance`. The loader is
  **fail-closed**: missing field, unknown field, or empty `test_blobs` is a named `ValueError`.
  Unknown-field rejection means **any new manifest field this slice adds is a contract change**,
  not an additive one.
- `tests/adversarial/` — the ten-cheat corpus; eight killed, cheats 6 and 10 asserted as
  documented residuals.
- Zero runtime dependencies. `mlx-lm` is an optional group; nothing on the reward path imports
  it, enforced by `tests/test_no_inference_on_reward_path.py`.

## Open questions carried in from the selection (for the dig to close)

1. **How far does environment provisioning actually get on macOS with no Docker?** Slice 1's
   corpus used synthetic fixture repos with no third-party dependencies precisely to sidestep
   this. Real source-A instances need per-instance Python environments. Decide with evidence
   whether any SWE-bench-Lite subset is provisionable under `uv` alone on this machine, and if
   the answer is "few", **scope source A down and say so** rather than shipping an empty `tasks/`
   directory that reads as coverage.
2. **Directory or manifest?** The format decision (`prd.md:365`). A directory can carry blobs as
   real files and a committed provenance record; a single JSON keeps `load_task`'s fail-closed
   parse exactly as shipped. Whichever is chosen, `load_task`'s byte-identity discipline for
   `test_blobs` is non-negotiable.
3. **Cheat 10 and the transitive-dependency declaration.** `docs/ROADMAP.md:160-166` says
   narrowing it *"belongs to task ingestion"*. Establish what is actually computable offline
   (import graph? runtime-observed reads?) versus what must be declared by hand — and if the
   honest answer is "the residual stands", it must be re-asserted as a documented residual, not
   quietly dropped.
4. **Source B needs a real donor repo.** "A commit that turns a failing test green" must be mined
   from something. Which local repo(s) are in scope, and does mining them stay inside the
   no-egress guardrail (it should — everything is local by construction)?

## Related work

- **PR #5** (`621831e`) — P1 slice 1, the direct upstream. `docs/planning/p1-verifier-core/` is
  the format precedent for this slice's artifacts.
- **PR #2** (`347655a`) — `docs/ROADMAP.md` and its PRD; the authoritative spec.
- **Belay** (`~/dev/at/belay`) — `eval/instances/` + `eval/scripts/` are listed as **taken**
  (`docs/ROADMAP.md:380`): the SWE-bench-Lite eligibility filter and the pure, offline, seeded
  stratified draw. That is this slice's most direct inheritance, and its known gap is recorded
  above (no `FAIL_TO_PASS`/`PASS_TO_PASS`/test patch in the pool).

## Labels / comments

None — no issue exists, so there are no labels, linked PRs, or comments to gather.

## Note on this file

`docs/planning/_card/issue.md` is id-free by design (`whetstone-begin-fast` § Phase 1) and each
unit of work **overwrites** the previous one's card on its own branch. P0's card is preserved in
history at `3662255`, P1 slice 1's at `621831e`. Flagged as a workflow wart, not a blocker.

## Attachments

None.
