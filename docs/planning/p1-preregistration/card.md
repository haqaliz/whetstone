# Card — `feat/p1-preregistration/aliz`

> **Why this file is here and not at `docs/planning/_card/issue.md`.** The `whetstone-begin-fast`
> skill writes the card to `docs/planning/_card/`, one id-free file overwritten per unit of work.
> That convention is unsafe now: **prior slices cite into that directory by section**, and an
> overwrite would break live references —
> `docs/ROADMAP.md:159` and `tests/adversarial/test_cheats.py:270` both cite
> `docs/planning/_card/understanding.md` **§ 2c** for the observed `file-read*` sandbox finding,
> `tests/test_docs.py:50` cites its **§ 5G / § 5H**, and
> `docs/planning/p1-task-ingestion/prd.md:4` names `_card/issue.md` as its card. Those citations
> are load-bearing (one of them explains why cheat 6 cannot be narrowed by the sandbox), so this
> slice keeps its card and understanding note in its own slug directory and leaves `_card/`
> untouched. **The skill's convention should be amended**; recorded here so the next slice does
> not rediscover it by breaking something.

## Source

**FALLBACK path.** No GitHub issue exists. `gh issue list --state all --limit 20` returns
"No Issues" against `haqaliz/whetstone` (checked 2026-07-29), and the `id` is a slug, not a
number. This is the expected case for this repo — every slice so far was carried by a PR
(`gh pr list`: #1–#6, all merged), never by an issue. Nothing was lost by the fallback.

The upstream spec is committed: `docs/ROADMAP.md` § 6 "Pre-registration" (`:478-488`) is the
contract this document discharges; § 5 "The baseline protocol" (`:464-474`) is what it must
commit to; P1 exit criterion 6 (`:355-356`) is the tick. The roadmap, not this card, is the
authority.

**Branch:** `feat/p1-preregistration/aliz` · **Worktree:** `.claude/worktrees/feat-p1-preregistration`
· **Base:** `origin/master` @ `201be6d` · **Baseline suite:** `uv run pytest` → **384 passed**.

## Brief

Reproduced verbatim from the `whetstone-next` handoff the user acted on by invoking
`wbf feat p1-preregistration`:

> Land PREREGISTRATION.md, P1 exit criterion 6 (docs/ROADMAP.md:355-356, § 6 at :478-488).
> It must be committed BEFORE any bake-off number exists, because its whole value is that
> git history proves the date — so this slice runs no model and produces no measurement.
> Content it must carry: source B (private) is the pre-registered headline; both sources are
> always published together regardless of which looks better; a disagreement between them is
> reported as a finding, and public-gain-with-private-flat is the expected contamination
> signature; UNVERIFIED is never a win; the baseline protocol of § 5 (a pinned baseline
> checkpoint, measured once and re-measured never, and a baseline N without which a final N
> says nothing); source B's self-selection disclosure verbatim in substance from
> docs/planning/p1-task-ingestion/prd.md:338-345; and source A's honest shape — 1 eligible
> instance of 300, never to be quoted as a benchmark set (docs/ROADMAP.md:347-353). The
> caveat to handle in the dig: the held-out split, the retry count R, and the base model are
> still open (§ 10) — decide what is pre-registerable today versus what is named as
> must-be-fixed-before-first-measurement, and do not invent a number to fill either.
>
> Acceptance criteria, written first (this repo is test-first):
> 1. PREREGISTRATION.md exists at the repo root and is committed in this PR.
> 2. A new test in tests/test_docs.py fails if the file is missing, if it stops naming source B
>    as the headline, if it stops asserting both sources are published together, or if either
>    disclosure (source B self-selection, source A corpus-of-one) is dropped.
> 3. A guard asserting the ordering: if any artifact exists under reports/, PREREGISTRATION.md
>    must exist too — so a baseline report can never land without its pre-registration.
> 4. CLAUDE.md and docs/ROADMAP.md are updated in the SAME commit that lands the file, so the
>    status block stops listing PREREGISTRATION.md as open and P1 shows exactly one criterion
>    remaining (the bake-off).
> 5. uv run pytest, uv run ruff check ., uv run mypy src/ all exit 0; CI green on macos-latest;
>    tests/test_no_inference_on_reward_path.py stays green.

## Why this slice, per the `whetstone-next` ranking (2026-07-29)

- It is **one of exactly two open P1 exit criteria**, and it is the unblocked one.
  `docs/ROADMAP.md:364-368` leaves `reports/baseline/` and `PREREGISTRATION.md`, and states
  plainly that **no number about a model exists anywhere in this repository.**
- The ingestion slice's card already classified it: row 6 of its P1 exit-criteria table read
  *"`PREREGISTRATION.md` is committed | **Out** — separate, unblocked; named as the
  `whetstone-next` alternate"* (`docs/planning/_card/issue.md:69`). That alternate is now the head
  of the queue, because the slice that outranked it merged at `201be6d` (PR #6).
- **It must precede the bake-off, not follow it.** § 6 requires it committed *"in P1, before any
  number exists"*. The bake-off scores candidate bases **per source** — the first numbers this
  project will ever hold. Pre-registering the headline rule after seeing which source flatters
  you is the exact self-deception the document exists to prevent.

## P1 exit criteria, and which this slice takes

| # | P1 exit criterion (`docs/ROADMAP.md:305-356`) | This slice |
|---|---|---|
| 1 | `uv run pytest tests/adversarial/` exits 0 | **Shipped** (PR #5) — must stay green |
| 2 | `tests/test_no_inference_on_reward_path.py` exits 0 | **Shipped** (PR #5, widened PR #6) — must stay green |
| 3 | `whetstone verify --task … --patch …` emits a verdict | **Shipped** (PR #5/#6) — untouched |
| 4 | `tasks/` holds instances from both sources with committed provenance | **Shipped** (PR #6) — supplies both disclosures |
| 5 | A baseline bake-off report exists under `reports/baseline/` | **Out** — unblocked now, but must run *after* this slice |
| 6 | `PREREGISTRATION.md` is committed | **In — the whole slice** |

**P4 grades against this document** (`:452-453`): *"The headline matches what
`PREREGISTRATION.md` committed to, and both sources are published together."* So whatever it says
must be specific enough to be checked later.

## Guardrails this slice must not touch

No model is invoked anywhere in this slice; it runs no rollout and produces no measurement. The
reward-path import guard (`tests/test_no_inference_on_reward_path.py`) must stay green. Nothing
here changes the reward, the sandbox, or the task contract — this slice writes a commitment and
the tests that hold it shut.
