# Whetstone: Project Context for Claude Code

This file orients a coding agent working in this repository. Read it first.

> **Status:** greenfield. Nothing is built yet. The next step is a planning session that
> produces `docs/ROADMAP.md` (a 2–3 month phased plan + milestones). Until then, this file
> and `VISION.md` are the source of truth. Keep them in sync as direction firms up.

---

## What this project is

**Whetstone** is a system that lets a model **train itself overnight — and proves it didn't
cheat.** Point it at your tasks; each night a local loop runs self-play / RL against an
**unhackable, execution-grounded verifier** (never an LLM judge it can fool), distills the
wins into a small local model, and produces a signed morning report: *"+X% on your real
tasks, zero reward-hacking, here's the proof."* You wake up to a measurably better
**private** model.

**The name.** A *whetstone* sharpens a blade through patient, repeated honing. Whetstone
sharpens a model the same way — a little better each night, against a hard, honest edge.

---

## The wedge (read this before proposing any feature)

The frontier is **RLVR — reinforcement learning from *verifiable* rewards**. Its open wound
is **reward-hacking**: a policy learns to game a soft/LLM-judge reward instead of getting
genuinely better. Whetstone's entire reason to exist is that **the reward is deterministic
re-execution**, so the policy *cannot* game a judge — the classic RLVR failure mode is
designed out.

- **We do NOT build a frontier base model.** We take an open base and make it better on the
  user's tasks, locally.
- **We do NOT reward with an LLM judge.** The reward is execution-grounded (observed-vs-
  claimed state / checkable end-state). If a task drifts toward "let a model grade the
  model," stop and flag it.
- The company/reputation is the **verified self-improvement loop**: the unhackable reward,
  the never-regress promotion gate, and the honest number.

---

## Key strategic constraints (do not violate)

1. **The reward must be verifiable, never a judge.** Execution-grounded, deterministic. This
   is the moat and the reason reward-hacking can't win here.
2. **Never regress.** A new checkpoint ships only when it *provably* beats the last on a
   held-out **verified** set. `UNVERIFIED` never counts as a win (borrow the sibling
   projects' honesty contract: UNVERIFIED is never rendered as PASS).
3. **Local / BYOK / private.** The user's data and the training stay on their machine. A
   cloud teacher model may be used via BYOK for distillation, but the loop and data are
   local by default.
4. **Build the part that gets BETTER as base models improve.** A stronger open base = a
   better starting policy and cleaner distillation; the durable moat is the verifier + the
   loop + the accumulated verified-improvement data, never the base weights.
5. **Ship the honest number even if gains are modest.** Scope to ONE task family where the
   verifier is airtight first; publish the harness and the real delta (including a
   "reward-hacking attempts caught & rejected: N" count), never a hyped one.
6. **No lab required.** RL loop + verifier + distillation + eval is all engineering — the
   founder's edge. No proprietary datasets or credentials.

---

## The core loop (the product surface)

1. **A verifiable task family + verifier** — the reward signal; deterministic, hard to game.
2. **Nightly improvement loop** — self-play / RL / self-distillation against that verifier.
3. **Never-regress promotion gate** — promote a checkpoint only on a proven, verified gain.
4. **Signed morning report** — the verified delta, what changed, and the hack-attempts caught.
5. **Local + private** — runs on the user's machine; the model never leaves.

---

## Relationship to Belay (sibling project)

Belay (`~/dev/at/belay`) is the execution-grounded **verification engine**. Whetstone is the
**improvement loop that trains against a verifier like Belay's**. They reinforce each other:
Belay proves a run is correct; Whetstone uses that kind of proof as an unhackable reward.
Reuse Belay's verifier/replay where it fits, but Whetstone is an independent project with its
own thesis (improvement), not a Belay feature.

---

## Tech direction (proposed — confirm in the planning session)

- **Core: Python.** RL/self-play loop, the verifier harness, distillation, and eval.
- **Models:** open bases (fine-tune / LoRA / distill into a small local model); local runtime
  (Ollama / vLLM / transformers). BYOK cloud teacher optional, for distillation only.
- **Reward:** execution-grounded verifier for one task family first (e.g. code / tool-use
  with a checkable end-state). No LLM-judge reward.
- **Dashboard:** TypeScript (founder's stack) — the nightly report, the verified-gain trend,
  the caught-hack log.
- **Distribution:** OSS, self-hostable, local-first / BYOK. **License:** lean Apache-2.0.

Nothing here is locked. `docs/technical/ARCHITECTURE.md` (to be written) is authoritative
once it exists.

---

## Founder profile

Solo / small-team. **Full-stack developer + ML engineer.** The moat is engineering — the RL
loop, the unhackable verifier, distillation, and the evaluation machinery — which is exactly
the founder's edge. No dependency on proprietary data, credentials, or a frontier lab.

---

## Quick facts for grounding (do not fabricate beyond these)

- **RLVR (RL from verifiable rewards)** is the live frontier for making models better at
  tasks with checkable outcomes; **reward-hacking** is its central, documented failure mode
  (e.g. METR observed a model rewriting a timer instead of optimizing the task).
- **LLM-as-judge rewards are foolable:** "One Token to Fool LLM-as-a-Judge" shows up to
  **35% false positives** — a judge reward is gameable; an execution-grounded reward is not.
- **The verifiable-environment substrate is a named gap:** Karpathy (Sequoia Ascent 2026) —
  the valuable RL environments "aren't in the frontier-lab mix."
- Seed research + rationale for this project: `~/dev/at/ideas/research/b1-verified-self-improvement.md`.

If you need a statistic that isn't here, do not invent one; say it's unverified.

---

## Non-goals / guardrails (restated so the project doesn't drift)

- **No frontier base-model training** — we improve an open base on the user's tasks.
- **No LLM-judge reward** — the reward must be execution-grounded/verifiable.
- **No regressions shipped** — promote only on a proven verified gain; UNVERIFIED ≠ win.
- **No data egress** — the loop and the user's data stay local by default.
- **No hype** — publish the honest delta and the caught hack-attempts, even when modest.
- **Gets better as base models improve** — reject designs a better base would make redundant.

---

## Docs structure (to be created)

```
README.md                       # Repo front door (to write)
VISION.md                       # Narrative thesis, moat, non-goals (seeded — see file)
CLAUDE.md                       # This file
.claude/skills/                 # The repo's own workflow skills (see below)
docs/
  ROADMAP.md                    # 2–3 month phased plan + milestones (NEXT: planning session)
  technical/ARCHITECTURE.md     # The nightly loop / verifier / distillation design (to write)
  product/PRODUCT_SPEC.md       # Product surface, the report, the trend (to write)
```

The immediate next artifact is `docs/ROADMAP.md`. See the planning prompt the founder was
given, or ask them for it.

---

## Workflow skills (`.claude/skills/`)

The repo carries its own skills, mirroring the sibling projects (`~/dev/at/belay`,
`~/dev/at/contig`). Use them rather than improvising a workflow.

| Skill | Alias | What it does |
|---|---|---|
| `whetstone-next` | `wn` | Picks the next capability from the repo's own files; recommends and hands off, never starts the work |
| `whetstone-begin-fast` | `wbf` | Worktree → context → dig → PRD → plan → implement (TDD, agents team) |
| `whetstone-begin` | `wb` | Same, plus diagrams and technical/non-technical proposal PDFs before planning |
| `whetstone-end-fast` | `wef` | Post-merge cleanup: master → pull → remove worktree → delete branch |
| `whetstone-end` | `we` | Same, plus a completion note on Desktop |
| `whetstone-report` | — | The plain-English completion note |
| `whetstone-worktrees` | — | Branch naming, worktree layout, per-worktree setup, cleanup |
| `prd-interview` / `prd-generator` / `tech-plan` | — | The planning chain the begin skills call into |

Conventions the skills assume: base branch **`master`** (never `main`), branch
`<type>/<id>/aliz`, worktree `.claude/worktrees/<type>-<id>`, planning artifacts under
`docs/planning/{slug}/`, and **strict TDD executed through the agents team**.

Every skill enforces the guardrails above — in particular that the reward stays
execution-grounded, that `UNVERIFIED` is never reported as a win, and that no number
appears anywhere the verifier didn't produce it.
