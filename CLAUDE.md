# Whetstone: Project Context for Claude Code

This file orients a coding agent working in this repository. Read it first.

> **Status (2026-08-31).** `docs/ROADMAP.md` is the **authoritative technical document**
> until `docs/technical/ARCHITECTURE.md` is written; that file does not exist yet. This
> file and `VISION.md` remain the narrative source of truth (thesis, moat, guardrails).
>
> **Built.** P0 (packaging, the `whetstone` CLI, strict ruff/mypy, pytest, CI on
> `macos-latest`). P1 slice 1 — the frozen `Task` contract, the Seatbelt sandbox (network
> denied, writes confined, environment pinned), the **STRICT** verifier (the reward) and
> the **WEAK** verifier (measurement only), with `UNVERIFIED` ranking above `PASS`. P1
> slice 2 — the on-disk task format, with `==` environment pins so a verdict stops
> depending on what the package index served that morning. P1 slice 3 — ingestion and the
> first corpus. P3 — the promotion gate and the held-out split. Most recently, the
> **morning report** unit (`report.md`, `report.json`, schema `whetstone-morning/1`),
> a pure function of two documents, byte-identical across processes. Then the
> **gate-untrained-incumbent** dispatch (2026-09-01): the gate's engine dispatches on
> `Checkpoint.untrained`, so the first gated evaluation compares a night's candidate
> against the untrained base it started from — one night, not two. Then the
> **close-base-7.3** amendment (2026-09-02): `PREREGISTRATION.md` § 7.3 is closed by the
> Type 1 amendment (§ 10.10), naming `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` as
> the base the night fine-tunes, committed before night #1 trains. Then the
> **probe decision gate** (2026-09-05): `whetstone check-probe --run <runs/id>` turns the
> night door's pre-committed go/no-go into a command exit — read-only over one probe run,
> 0 the rule holds, 1 a named violation, 2 a refusal — so night #1's decision is a process
> exit rather than an operator reading a ledger by eye.
>
> **The corpus, stated precisely.** Source B (private, pre-registered headline):
> **66 tasks**, each proven live rather than asserted. Source A (public SWE-bench-Lite):
> **1 eligible instance of 300** — `pallets__flask-4045` — with all 299 refusals ledgered.
> **One instance is not a public benchmark set and must never be quoted as one.**
>
> **Not built, and not measured.** The nightly loop has **never been run**, so no training
> set, checkpoint or yield figure exists — and the gate has therefore **never run on real
> checkpoints**. Its exits and refusals are proven against fixtures only — as are
> `check-probe`'s, which has never been pointed at a real probe. `R = 3` is
> declared a priori because there is no observed unverified rate to set it from. Cheat 6
> and cheat 10 remain **documented residuals**. Cuts v0.3.0 onward publish `whetstonehq`
> to PyPI and a GitHub Release by tag push; last tag 2026-08-26.
>
> **Full history — including the reward-path defect that let a task PASS with no patch
> applied, and how it was closed — is in [`docs/STATUS.md`](docs/STATUS.md).**
>
> Keep this file, `VISION.md` and `docs/ROADMAP.md` in sync as direction firms up.
> Describe the state of the tree this file ships in, and **never write status for work in
> flight** — a status that names in-progress work is stale the moment that work merges,
> which has already happened once here. A capability is written up in the same commit that
> lands it, so the claim and the code arrive together and neither can outlive the other.
> Append new entries to `docs/STATUS.md`, not to this file.
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

## Relationship to the sibling project

The sibling project is the execution-grounded **verification engine**. Whetstone is the
**improvement loop that trains against a verifier like its**. They reinforce each other: the
sibling project proves a run is correct; Whetstone uses that kind of proof as an unhackable
reward.
`docs/ROADMAP.md` § 7 records exactly what we take and what we decline. **Taken:** the verdict
semantics (`UNVERIFIED` ranked above `PASS`), the provenance boundary, the corpus metrics, the
AST guard that keeps inference libraries off the reward path, the **Seatbelt sandbox approach**
(the profile shape and its SBPL escaping — we wrote our own minimal deny-all profile rather than
vendoring the 417-line module), and the eval instances/scripts.
**Declined: the replay substrate** — for four stated reasons: it answers a harder question than
our reward needs (trace fidelity vs. does the end state pass an operator-held check), its
throughput is built for auditing rather than generating rollouts, parallel calls deliberately
yield `UNVERIFIED` so batched rollouts produce no signal, and it exposes no API surface. Revisit
only if a later task family needs trace fidelity. Whetstone is an independent project with its
own thesis (improvement), not a feature of the sibling project.

---

## Tech direction

**Locked — decided in the planning artifacts; do not re-litigate.**

- **Core: Python**, package path `src/whetstone/`, tests in `tests/`. RL/self-play loop, the
  verifier harness, distillation, and eval all live here.
- **Toolchain: uv exclusively** (no pip, no poetry) + ruff + mypy + pytest. CLI entrypoint
  `whetstone`.
- **Local runtime: MLX / `mlx-lm`**, end-to-end — both rollouts and LoRA — on macOS / Apple
  Silicon (`docs/planning/roadmap-and-task-family/prd.md:63` for the runtime, `:58` for the
  platform). *Not* Ollama, vLLM, or transformers; an earlier draft of this file said those,
  and that was superseded by the PRD.
- **Reward:** execution-grounded verifier for one task family first (code / tool-use with a
  checkable end-state). No LLM-judge reward, ever.
- **License:** Apache-2.0 (`docs/ROADMAP.md` § 4 makes it a P0 exit criterion).
- **Distribution:** OSS, self-hostable, local-first / BYOK. 0.x versioning, tag `vX.Y.Z`, and
  **tag-push is the entire release mechanism**. PyPI distribution name **`whetstonehq`** (bare
  `whetstone` is taken); the import package and the CLI stay `whetstone`. See `RELEASING.md`.
- **Dashboard:** TypeScript / Next.js (founder's stack), as a subdirectory of this repo — the
  nightly report, the verified-gain trend, the caught-hack log. **Post-horizon**, not near-term.

**Still open — genuinely undecided, decide with evidence.**

- **Which open base we fine-tune / LoRA — closed 2026-09-02 by the § 7.3 Type 1 amendment**
  (`PREREGISTRATION.md` § 10.10): `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`, chosen on
  the larger-base arm's first nonzero strict-PASS yield. A change of base is a further Type 1
  amendment, never a looser verifier.
- **The BYOK cloud teacher for distillation** — optional, and post-horizon; nothing inside the
  current roadmap horizon calls a cloud model at all.
- Everything `docs/ROADMAP.md` § 10 lists as an open question.

`docs/ROADMAP.md` is authoritative on the technical plan today.
`docs/technical/ARCHITECTURE.md` (to be written) supersedes it once it exists.

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

## Docs structure

```
README.md                       # Repo front door
VISION.md                       # Narrative thesis, moat, non-goals
CLAUDE.md                       # This file
CONTRIBUTING.md                 # Dev setup, test-first contract, ground rules
PREREGISTRATION.md              # What P4 may claim, fixed before any number existed
RELEASING.md                    # Tag-push release mechanism — proven since v0.3.0
reports/baseline/               # The P1 bake-off — the only home of the baseline's figures
reports/format-hardening/       # The hardened arm's report — non-comparable, by the D6 argument
reports/easier-stratum/         # The probe's home — non-comparable, changed task set (§ 10.5)
reports/larger-base/            # The arm's home — non-comparable, new candidate (§ 10.6)
reports/baseline-measurement/   # The § 3 baseline's home — the anchor of every delta (PR #17)
reports/honest-number/          # The P4 delta/final series' only home (§ 10.9)
reports/local/                  # GITIGNORED: the user's own nightly output — morning reports
.claude/skills/                 # The repo's own workflow skills (see below)
docs/
  ROADMAP.md                    # 2–3 month phased plan + milestones — authoritative today
  planning/                     # Per-unit PRDs, specs, implementation plans
  technical/ARCHITECTURE.md     # The nightly loop / verifier / distillation design (to write)
  product/PRODUCT_SPEC.md       # Product surface, the report, the trend (to write)
```

`docs/technical/ARCHITECTURE.md` and `docs/product/PRODUCT_SPEC.md` do **not** exist yet. Until
`ARCHITECTURE.md` does, read `docs/ROADMAP.md` for the technical plan — do not assume the
architecture doc's absence means the design is undecided.

---

## Workflow skills (`.claude/skills/`)

The repo carries its own skills, mirroring the author's sibling projects. Use them rather than
improvising a workflow.

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
