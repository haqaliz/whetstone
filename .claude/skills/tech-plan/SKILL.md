---
name: tech-plan
description: Create a phased technical implementation plan from planning artifacts in docs/planning (PRD + aspect spec). Use after prd-interview when ready to execute a specific aspect. Triggers on "tech plan", "implementation plan", "plan from PRD".
tags:
  - planning
  - documentation
metadata:
  status: trial
---

Create a phased technical implementation plan from planning artifacts under `docs/planning/{slug}/`.
Inputs can come directly from `prd-interview`; do not require `prd-generator`.
This is Phase 5 of `whetstone-begin-fast` — the plan it produces is executed in Phase 6 through the agents team under strict TDD.

If the user provided artifacts in context (attached file, pasted content, or referenced path), use them directly.
Otherwise, search the workspace for:

- PRDs matching `docs/planning/*/prd.md`
- Aspect specs matching `docs/planning/*/*/spec.md`

Analyze the current codebase, then create a detailed **Implementation Plan** optimized for autonomous agent execution.
Whetstone is **greenfield**: today the authoritative reading is `CLAUDE.md` (the wedge, the five core-loop elements, the guardrails) and `VISION.md`. `docs/ROADMAP.md`, `docs/technical/ARCHITECTURE.md`, and `docs/product/PRODUCT_SPEC.md` are named in `CLAUDE.md` but not yet written — read them if they now exist and say plainly that they don't if they don't. The loop will live under `src/whetstone/`.
The plan should be structured so the agent team can work through it systematically with minimal human intervention.

## Handoff Contract

- **Feature requirements source:** `docs/planning/{slug}/prd.md`
- **Aspect requirements source (preferred):** `docs/planning/{slug}/{aspect}/spec.md`
- **Plan output (required):** `docs/planning/{slug}/{aspect}/plan_YYYYMMDD.md`

Plan one aspect at a time. If a feature has multiple aspects, create one plan file per aspect.

**Filename:** `plan_YYYYMMDD.md` (YYYYMMDD is today's date, e.g., `plan_20260726.md`)
**Location:** the aspect directory (e.g., `docs/planning/task-verifier/reward-contract/plan_20260726.md`). Create it if needed.
If the user provided an aspect spec from a different location, write the plan alongside that spec.
If only a PRD is provided (no aspect spec), ask which aspect to plan, create or update `spec.md` for that aspect, then write the plan in that aspect directory.
If the PRD was pasted or attached (no file path), ask the user to confirm both feature slug and aspect name, then write to `docs/planning/{slug}/{aspect}/plan_YYYYMMDD.md`.

## Deliverables

### 1. Project Setup Checklist

- Directory/module structure to create (under `src/whetstone/`, `tests/`, or the dashboard once it exists)
- Configuration needed (pyproject entries, env, pinned tool versions and pinned model/runtime versions for reproducible training and eval)
- Dependencies to add (with specific versions where critical) — Python via `uv add`, dashboard via `npm install`
- **Greenfield:** if `pyproject.toml` / `uv.lock` / `src/` don't exist yet, scaffolding them is part of the plan's first phase — say so explicitly rather than assuming `uv sync` works. Test-first still holds: the failing test comes before the package.

### 2. Implementation Phases

Break the build into sequential phases that can be executed autonomously. For each phase:

**Phase N: [Name]**

- **Goal:** What this phase accomplishes
- **Prerequisites:** What must exist before starting
- **Files to create/modify:** Explicit list
- **Validation:** How to verify the phase is complete (`uv run pytest <path>`, expected outputs; the dashboard's test/build commands for UI work)
- **Commit message:** Suggested commit message for this phase

Each phase is a unit the agents team can own end-to-end under TDD (RED → GREEN → REFACTOR).

### 3. File-by-File Build Order

Ordered list of every file to create, with: filepath, one-line purpose, key functions/components it exports, and dependencies on other files.

### 4. Testing Strategy

- Unit tests to write (mapped to implementation phases) — these are written **first** in Phase 6
- Integration tests
- Manual verification steps
- Test commands: `uv run pytest` (Python core), dashboard test/build commands for UI
- **Adversarial tests are mandatory for anything touching the reward.** A verifier is worth what it rejects. For each reward or gate change, plan the test that a cheating policy would pass under a weaker check and must fail under this one — degenerate solutions, edited timers/asserts, mutated fixtures, claimed-but-not-observed state. "Accepts a correct answer" is half a test.
- **Tests are deterministic and run with no network.** Fixed seeds, fixed task inputs, no wall-clock dependence. Any model call (the BYOK teacher used in distillation) sits behind an injectable seam and never runs in CI. A test whose result depends on a live model is not a test.
- Lift acceptance criteria from the aspect `spec.md` rather than inventing parallel ones.

### 5. Environment, Determinism & Locality

- Environment variables needed (BYOK teacher keys, if any — for distillation only, never for the reward)
- External tools/services to configure (and how they're pinned): local runtime (Ollama / vLLM / transformers), model weights and revisions
- Local setup: `uv sync`; dashboard `npm install`
- Note determinism requirements explicitly — a reported gain has to be reproducible or it isn't a gain. Pin seeds, model revisions, and task sets; record them alongside any result. A number produced by an unpinned run is `UNVERIFIED`.
- **Note the train/held-out boundary.** State which data the phase touches and confirm nothing from the held-out verified set can reach training. Leakage is silent and it invalidates every number downstream — plan the check, don't assume it.
- Confirm nothing in the plan requires the user's tasks, data, or training to leave the machine.

### 6. Edge Cases & Error Handling

- Known edge cases to handle
- Error states to account for, and **what outcome each produces**. Given Whetstone's contract, name the explicit `UNVERIFIED` path with its cause for anything that can fail to evaluate (verifier can't execute the task, run crashed mid-eval, non-deterministic result, held-out set unavailable, checkpoint won't load). A silent pass, or a fallback that promotes anyway, is never acceptable — the gate's default is *don't promote*.
- Fallback behaviors

### 7. Agent Execution Notes

- Suggested checkpoints for human review
- Areas likely to need iteration or debugging
- Sections where the agent should ask for clarification before proceeding

## Guidelines

- Be extremely explicit — assume no implicit knowledge
- Prefer small, testable increments over large monolithic steps
- Each phase should result in runnable (even if incomplete) code, with the suite kept green
- Flag any spec ambiguities that could block implementation
- Note assumptions clearly
- Optimize for autonomous execution by the agents team with minimal back-and-forth
- Don't plan work that trains a frontier base model, or that rewards the policy with a model's opinion instead of re-execution — flag it against the `CLAUDE.md` wedge instead
- Don't plan a capability whose dependencies aren't built. The verifier comes first: the loop, the gate, and the report are all downstream of it. Abstractions are earned by the second implementation, not designed for the first.
- Don't plan a second task family before the first one's verifier is airtight

## Edge Cases

- **Greenfield vs. existing codebase**: For greenfield, include full setup. For existing code, skip scaffolding and focus on integration points and impact analysis. Whetstone is greenfield today — expect the setup path.
- **No aspect spec exists yet**: Derive a candidate aspect list from the PRD, ask the user to choose one, draft `spec.md`, confirm, then plan.
- **Incomplete PRD**: If the PRD lacks testable acceptance criteria or measurable metrics, flag this and recommend running `prd-interview` before planning.
- **PRD with no named held-out set**: For anything that claims an improvement, the plan can't validate without one. Flag it and get the eval set defined before planning the phase that would report a number.
- **Multiple PRDs**: Separate plans per PRD unless they share infrastructure, in which case note shared phases.
- **Multiple planning sessions**: If an aspect has multiple `plan_YYYYMMDD.md` files, base the new plan on the current `prd.md` + `spec.md`. Create a new plan file with today's date.
- **PRD with flagged gaps**: If `prd-interview` produced the PRD via the "just write it" path, gaps may be marked. Note these in the plan and recommend resolution before the affected phase.
