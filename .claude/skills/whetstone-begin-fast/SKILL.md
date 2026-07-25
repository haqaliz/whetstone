---
name: whetstone-begin-fast
description: Use when starting work on a Whetstone unit of work (a GitHub issue id or an inline brief) and you want the fast path straight to an implementation plan. Triggers on "whetstone-begin-fast", "wbf", "wbf bug 12", "wbf feat task-verifier", "begin fast".
arguments: "type id"
---

# Whetstone Begin (Fast Track)

## Overview

Turn a single unit of work into shipped, test-driven code. The fast track is: **isolate → gather → dig → PRD → plan → implement (TDD).** No proposal/diagram deliverables (use `whetstone-begin` / `wb` when you need those).

**Two non-negotiables for this whole pipeline:**
- **Always work through the agents team.** Every phase with independent units of work is dispatched to agents and synthesized — never done serially in the main thread. See *Agents team (mandatory)*.
- **Implementation is always test-first**, via `superpowers:test-driven-development`, and is itself executed by the agents team. See Phase 6.

**Invocation:** `wbf <type> <id>` — e.g. `wbf bug 12`, `wbf feat task-verifier`, `wbf chore pin-uv-version`.

- `type` ∈ `bug | feat | feature | task | chore` (normalize `feature` → `feat`).
- `id` = a **GitHub issue number** when one exists, otherwise a short descriptive **slug** for the work.
- Owner is `aliz`.

## Task source: GitHub issue, tolerate absence

Whetstone's tracker is GitHub Issues, but the repo/issues may not be reachable (`gh` unauthenticated, Issues disabled, or the work was never filed). The pipeline degrades gracefully:

- If `id` is numeric and `gh issue view <id>` succeeds → use it as the source (Phase 1).
- Otherwise → ask the user for a one-paragraph **inline brief** and treat that as the source. Skip the `gh` fetch; everything else is identical.

## Pipeline

Run phases in order. **Do not skip the review gate.** Every phase runs through the agents team, and Phase 6 is strict TDD — never do parallelizable work or implementation serially in the main thread.

### Phase 0 — Isolate in a worktree

**REQUIRED SUB-SKILL:** Use `whetstone-worktrees`.

- Branch name: `<type>/<id>/aliz` (e.g. `bug/12/aliz`, `feat/task-verifier/aliz`).
- Worktree dir: `.claude/worktrees/<type>-<id>` (e.g. `.claude/worktrees/bug-12`).
- Create from `origin/master` — Whetstone's base branch is **`master`**, never `main`. Whetstone has no `.worktreeinclude` files to copy today.
- **Greenfield:** `origin/master` exists (project context and vision are pushed), but there is still no `pyproject.toml`, so `uv sync` will fail. Run `uv sync` in the worktree only once the Python core is scaffolded — if your work *is* the scaffolding, the failing test comes first. See `whetstone-worktrees`.
- All subsequent work (context dump, PRD, plan) happens **inside this worktree.**

### Phase 1 — Gather context (`gh`, or inline brief)

Pull what's available and save a raw dump to `docs/planning/_card/issue.md` in the worktree so later phases (and the PRD) have a single source. (Filename is id-free on purpose — the id lives in the branch/PR; the worktree is already dedicated to one unit of work.)

Gather: the issue body, labels, linked/related issues and PRs, and **comments**. If there's no reachable issue, write the user's inline brief into the same file under a "Brief" heading.

**Commands and parsing:** see `references/gather-context.md`.

### Phase 2 — Deep dig

Before any PRD work, understand the real problem and the code it touches.

- Read the saved dump.
- Map the relevant code paths. Whetstone is **greenfield** — today only `CLAUDE.md`, `VISION.md`, and the skills exist. `docs/ROADMAP.md`, `docs/technical/ARCHITECTURE.md`, and `docs/product/PRODUCT_SPEC.md` are named in `CLAUDE.md` but **not yet written**; read them if they now exist and say plainly that they don't if they don't. Once the loop exists it will live under `src/whetstone/`.
- Produce a short written "understanding" note: what the work is really asking, affected areas, ambiguities, and open questions.
- Surface contradictions between the issue/brief and the code/docs — flag them, don't paper over them.
- Honor the strategic constraints in `CLAUDE.md`. The moat is the **verified self-improvement loop** — the execution-grounded verifier, the never-regress promotion gate, and the accumulated verified-improvement data. It is **not** a frontier base model, and it is **not** an LLM judge. If the work drifts toward training a base model from scratch, toward rewarding with a model's opinion, or toward anything that requires the user's data or training to leave the machine, flag it before planning.
- Place the work on the **core loop** (the five elements in `CLAUDE.md` § *The core loop*): ① verifiable task family + verifier, ② nightly improvement loop, ③ never-regress promotion gate, ④ signed morning report, ⑤ local + private. Say which element the work changes. If it touches the reward, state explicitly how the reward stays execution-grounded. If it touches the gate, state what counts as a win and confirm `UNVERIFIED` still counts as **not** a win.

### Phase 3 — Requirements interview

**REQUIRED SUB-SKILL:** Use `prd-interview`.

- Feed it the Phase 1 dump + Phase 2 understanding as the product brief.
- Answer from the gathered context where you can; ask the user only what the context can't resolve.
- Confirm a **descriptive** feature slug (kebab-case, e.g. `task-verifier`) for `docs/planning/{slug}/`. Do **not** name the slug `<type>-<id>` — the id lives in the branch and PR, not in committed doc paths.
- Output: `docs/planning/{slug}/prd.md` (+ aspect `spec.md` files if decomposed).

### Phase 4 — Generate & self-critique the PRD

**REQUIRED SUB-SKILL:** Use `prd-generator`.

- Refine `prd.md`, run its self-critique, and surface the 🔴/🟡 gaps.

### ⛔ Review gate — STOP

Present the PRD and its flagged gaps. **Wait for the user's explicit approval** before planning. Do not auto-advance to tech-plan.

### Phase 5 — Implementation plan

**REQUIRED SUB-SKILL:** Use `tech-plan`.

- Plan one aspect at a time from `prd.md` (+ `spec.md`).
- Output: `docs/planning/{slug}/{aspect}/plan_YYYYMMDD.md`.

### Phase 6 — Implement (TDD, agents team)

Start only after the plan is approved. Implementation is **always test-first** and **always run through the agents team** — never hand-written serially in the main thread.

**REQUIRED SUB-SKILL:** Use `superpowers:test-driven-development` — strict RED → GREEN → REFACTOR; no production code before a failing test.
**REQUIRED SUB-SKILL:** Use `superpowers:subagent-driven-development` to execute the plan — dispatch one agent per independent task from `plan_YYYYMMDD.md`; parallelize independent tasks with `superpowers:dispatching-parallel-agents`.

- Each dispatched agent owns one task and follows the TDD cycle inside it: write the failing test, make it pass, refactor.
- Run the suite after each task and keep the branch green: `uv run pytest` for the Python core; the dashboard's test/build commands for UI work once it exists. If the suite doesn't exist yet, the first task's failing test creates it.
- **Verifier work gets adversarial tests, not just happy-path ones.** A verifier is only worth what it rejects: any change to the reward must come with tests that a reward-hacking policy would pass under a weaker check and fails under this one. "The verifier accepts a correct solution" is half a test.
- Commit per task on the `<type>/<id>/aliz` branch (id lives in the commit/PR, never in code).
- You stay the integrator: sequence dependent tasks, synthesize agent results, and surface blockers at each checkpoint.

## Artifact layout (inside the worktree)

```
docs/planning/
├── _card/issue.md                 ← gh dump or inline brief (Phase 1)
├── {slug}/prd.md                  ← prd-interview / prd-generator
└── {slug}/{aspect}/plan_*.md      ← tech-plan
```

Phase 6 produces **code commits** on the `<type>/<id>/aliz` branch — not documents.

## Agents team (mandatory)

This pipeline is **always** run through a team of agents, never serially in the main thread. For each phase, dispatch agents for the independent units of work and synthesize their results yourself.

**REQUIRED SUB-SKILL:** Use `superpowers:dispatching-parallel-agents` for independent work, and `superpowers:subagent-driven-development` for executing plan tasks in Phase 6.

- **Phase 1–2:** one agent per related issue/PR (5-line summary + relevance) + one agent to map the affected area (the project docs today; `src/whetstone/` once it exists). Keep the `gh` calls themselves batched in a single message.
- **Phase 6:** one agent per independent plan task; each agent works in strict TDD.

Gates, user-facing summaries, and integration stay with you — the agents do the fan-out work.

## Common mistakes

| Mistake | Fix |
|---|---|
| Working in the primary checkout | Always create the Phase 0 worktree first |
| Branching from `main` | Whetstone's base branch is `master`; `main` doesn't exist |
| Slug = `bug-12` | Use a descriptive slug; the id stays in branch/PR |
| Treating a `gh` failure as fatal | Fall back to an inline brief, keep going |
| Treating a missing `pyproject.toml` / roadmap doc as fatal | Whetstone is greenfield — say the file isn't written yet and keep going |
| Rewarding with an LLM judge, or any model's opinion | Stop and flag — the reward is execution-grounded by design; that's the entire wedge |
| Drifting into training a frontier base model | Stop and flag — we sharpen an open base on the user's tasks |
| Promoting a checkpoint without a proven verified gain | Never — the gate ships only on a proven win on a held-out verified set |
| Counting `UNVERIFIED` as a win | Never — `UNVERIFIED` is not `PASS`, in code or in a report |
| A design that needs the user's data or training to leave the box | Stop and flag — local by default is a guardrail, not a preference |
| Testing only that the verifier accepts good work | Also test what it rejects — adversarial cases are the point |
| Inventing requirements the issue doesn't support | Flag as open question in the PRD instead |
| Implementing serially in the main thread | Execute the plan through the agents team (subagent-driven-development) |
| Writing code before a failing test | Implementation is strict TDD — RED before GREEN, always |
