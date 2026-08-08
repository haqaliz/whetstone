# Whetstone: Project Context for Claude Code

This file orients a coding agent working in this repository. Read it first.

> **Status — what exists in this tree today.** `docs/ROADMAP.md` is written and is the
> **authoritative technical document** until `docs/technical/ARCHITECTURE.md` is written;
> that file does not exist yet. This file and `VISION.md` remain the narrative source of
> truth (thesis, moat, guardrails).
>
> **P0 (scaffold) is done:** packaging, the `whetstone` CLI, strict ruff/mypy, pytest, and CI
> on `macos-latest`.
>
> **P1 slice 1 — the task contract and the verifier core — is done** (`docs/ROADMAP.md` § 2, § 3;
> plan at `docs/planning/p1-verifier-core/`). `src/whetstone/verify/` holds the frozen `Task`
> contract, the ported verdict semantics (`UNVERIFIED` ranks above `PASS`), the Seatbelt sandbox
> (network denied, writes confined, environment pinned), the **STRICT** verifier — the reward —
> and the **WEAK** verifier — measurement only — reachable as `whetstone verify`. The
> adversarial corpus (`tests/adversarial/`) runs ten cheats through both verifiers: eight are
> killed, and **two are documented residuals**, cheat 6 (special-casing the known input) and
> cheat 10 (a held test's undeclared dependency). A scoped AST guard keeps inference libraries
> off the reward path.
>
> **P1 slice 2 — the on-disk task format — is done** (`docs/ROADMAP.md` § 3; plan at
> `docs/planning/p1-task-ingestion/`). A manifest now declares its `environment` — exact `==`
> pins and a nominated interpreter — so the verdict stops depending on what the package index
> served that morning; `tests/test_environment_pins.py` demonstrates that, showing one task and
> one correct patch reaching **PASS** pinned and **FAIL** unpinned, resolved offline against a
> committed index. Held test paths are refused unless spelled canonically. `src/whetstone/tasks/`
> reads a whole directory of manifests — nothing skipped, an empty directory is a usage error
> rather than a vacuous pass — and `whetstone verify` accepts one, reducing worst-status-wins so
> a single `UNVERIFIED` task can never exit 0. `tasks/` carries the layout that splits committed
> provenance from local data. The reward-path guard now covers `src/whetstone/tasks/` as well as
> `src/whetstone/verify/`.
>
> **P1 slice 3 — ingestion, and the first real corpus — is done** (`docs/ROADMAP.md` § 4, P1
> exit criterion 4). **Source B (private, the pre-registered headline): 66 tasks**, 45 mined from
> `donor A` and 21 from `donor B`, each *proven live* rather than asserted — FAIL with no patch,
> PASS under its own reference patch, executed node-id set equal to declared, zero skips. Donors
> are named by stable pseudonyms throughout this repository: they are the author's own private
> repositories, and their names are not this project's to publish. Donor B is also the sibling
> project the verifier's design draws on (§ *Relationship to the sibling project*). The manifests
> are the user's code and live in gitignored `tasks/local/`; the committed evidence is
> `tasks/recipes/*.json` and `tasks/local-ledger.json` (hashes and verdicts, never file contents).
> Two donors yielded nothing and the refusals are the finding: `donor C` was refused for having
> no `uv.lock`, and this repository yielded 0 of 2 because its own test-first workflow lands the
> test and the fix in one commit. **Source A (public SWE-bench-Lite): 1 eligible instance of 300**
> — `pallets__flask-4045` — with all 299 refusals ledgered in `tasks/public/ineligible.json`
> against the gate that refused each (192 format, 106 environment, 1 collectability). The
> deliverable there is the four-gate filter and the rejection ledger; **one instance is not a
> public benchmark set and must never be quoted as one.**
>
> **Slice 3 also found and closed a reward-path defect, which is the part worth reading.** A task
> **PASSED with no patch applied** — a false PASS. In a `src`-layout project the tests import by
> package name, resolved through the venv, and the venv held an editable install rooted at a
> *different* checkout than the one the patch was applied to; the tree under verification was
> never imported. The ten-cheat corpus missed it because every fixture repo was flat-layout with
> no venv install, so **the defence had been the shape of the fixtures, not anything the verifier
> did.** Closed by `import_roots` in the manifest, deps-only provisioning
> (`--no-install-project`), and a `PYTHONPATH` naming the run's own checkout so it shadows any
> residual install; `tests/adversarial/test_inert_checkout.py` holds it shut.
>
> **P1 slice 4 — the pre-registration — is done** (`docs/ROADMAP.md` § 6; plan at
> `docs/planning/p1-preregistration/`). `PREREGISTRATION.md` is committed at the repository root,
> **before any number about a model existed**, which is its entire value: it fixes the headline —
> the change in STRICT-PASS *count* on the held-out source-B split, published over its
> denominator and never as a rate — along with every metric definition, the baseline protocol,
> and the rule that both sources are always published together and a disagreement between them is
> reported as a finding. It pre-registers **no numeric success threshold**, because none could be
> grounded before a baseline exists, and forbids one being added once a number does. Three items
> are named as open with the amendment that closes each: the held-out split, the retry count `R`,
> and the base. Five limitations are disclosed up front, including that source B's self-selection
> mitigation (a third donor) **did not land** — `donor C` was refused for having no `uv.lock`.
> `tests/test_docs.py` holds it shut: no placeholder, no figure about a model in any spelling, and
> nothing may exist under `reports/` in a tree lacking the file. That last guard proves
> co-existence, not ordering — the temporal claim is `git log`'s, and the document says so itself.
>
> **P1 slice 5 — the base-model bake-off — is done, and P1 is closed** (`docs/ROADMAP.md` § 4,
> the last exit criterion; plan at `docs/planning/p1-baseline-bakeoff/`). Three candidate open
> bases produced patches locally through `mlx-lm`, every patch was graded by the STRICT verifier,
> and the report lives at `reports/baseline/` (`report.md`, `report.json`, `cost.json`) — read it
> before quoting anything about it. **This tree now holds figures about models, and
> `reports/baseline/` is their only home** — do not restate one anywhere else, because a figure
> quoted twice is a figure that can disagree with itself.
>
> **The result was a zero: not one candidate solved a single task on the declared source-B set.**
> So P1's pivot signal (`docs/ROADMAP.md` § 4) **fired**, **no base is selected**, and
> `PREREGISTRATION.md` § 7.3 stays open — the response it names is an easier task stratum or a
> larger base, never a looser verifier. The failure modes differ by candidate (unapplicable
> patches dominate at the small and large ends, empty diffs in the middle), which is a finding
> about where the wall is rather than a tie. Two things stop that zero being read as a broken
> harness. The **control arm** — an inert patch and each task's own re-derived fix, through the
> same harness, on the same task — was **INTACT on every run**, so the harness demonstrably
> reaches PASS when a correct patch exists. And the reward-hacking count `N` was zero for every
> candidate, which is a floor rather than a rate: the generation contract states the
> patch-scope rule to every candidate, so it discourages exactly what `N` counts.
>
> **Two bounds on that report, disclosed rather than discovered.** Prompts used the **oracle
> retrieval** setting — the base is shown the non-test files the reference patch touches — so
> every count is an **upper bound** on the same base working from the bug report alone, and may
> not be compared with a figure measured without retrieval. And the **generation contract**
> (prompt template, retrieval setting, extractor) is **not** among the pre-registration's pinned
> inputs, yet it demonstrably moves the numbers; a figure measured under a changed contract is
> not comparable to this one.
>
> **The measurement is now instrumented, which is where P2 starts** (plan at
> `docs/planning/p2-yield-probe/`). Reading the bake-off's own failure buckets showed that the
> great majority of verdict-reaching rollouts never got a patch onto disk at all: `NOT_APPLIED`
> means *"git refused it"* and nothing narrower, so a malformed diff, a mis-anchored one and a
> budget-truncated one all wear the same tag. **The pivot signal's premise — that the bases cannot
> fix these bugs — was therefore never actually tested**, because the measurement did not reach the
> question. That makes this a measurement-validity fix rather than a third response to the signal,
> and it is why `docs/ROADMAP.md` § 4 needs no amendment.
>
> `src/whetstone/bakeoff/transcript.py` keeps what a base actually wrote — as a `Generator`
> wrapper, so the one-method model seam is not widened and `score()` is untouched — and
> `attribution.py` replays those completions offline to say *which* zero each was, using
> `patch.py`'s own `NoDiff` reasons as the partition rather than a taxonomy invented beside it.
> The two causes the report cannot separate — git would not read the patch, versus git read it and
> would not apply it — are now distinguished, read-only, with nothing under `verify/` modified.
> Transcripts hold the user's own code back verbatim, so they are refused under `--out` and their
> documented homes are asserted gitignored. **Nothing is published by this**: it produces local
> evidence, and the run that uses it has not been made.
>
> **The instrument was then used, and it falsified two proposed fixes** (`docs/planning/p2-yield-probe/prd.md`,
> corrected 2026-08-05). Arm A re-ran the pinned contract and **reproduced `reports/baseline/`
> exactly** — every published count, four days later — which is the first direct evidence that the
> bake-off is deterministic rather than merely argued to be. Attributing its transcript then showed
> the failures are overwhelmingly *"git would not read this diff"* rather than *"git read it and
> would not apply it"*, which withdrew the search/replace proposal; and a second run at double the
> token budget, on the base the evidence best supported, moved no cause bucket beyond noise and
> solved nothing.
>
> **The reasoning under both was the defect, and it is the transferable part.** Truncation had been
> *inferred from the shape of a diff* and never measured — the spec named that inference as open,
> and it was then reasoned from as settled. So the roadmap's own named responses (an easier task
> stratum, or a larger base) now have more support than any generation-contract change, and no
> further fix should be proposed before someone reads what the unparseable diffs contain. Every
> figure behind this lives in gitignored run artifacts; `reports/baseline/` remains the only home
> for a published one.
>
> **P2 slice 2 — the diff autopsy — is done, and the read is now a measurement** (`docs/planning/p2-diff-autopsy/`;
> plan at `docs/planning/p2-diff-autopsy/autopsy/`). `src/whetstone/bakeoff/autopsy.py` is an
> offline, deterministic, stdlib-only classifier that assigns every stored completion exactly one
> grounded content-shape cause, asserts a fine→coarse mapping against the run's own
> `attribution.json` (a contradiction is reported, never reconciled), and writes its document
> only under a gitignored root. **Running it corrected the hand-read in three places, which is
> the transferable part.** The mapping assertion surfaced walk rules that disagreed with git's
> parser on the same bytes — a check that read text git never parses, a counter-overrun git
> reads as "corrupt patch" while the walk saw a completed hunk, and a mapping gap for
> loop-dominated completions carrying a refused stub — and each correction landed with a
> fixture, watched failing first. The corrected measurement agrees with the run's own
> attribution on every stored record, classifies both runs completely with nothing
> unrecognised, and agrees with the hand-read exactly on the control category while diverging
> from it only at the one margin the dig itself called fuzzy (reported as a finding, never
> reconciled). **The finding** (`docs/planning/p2-diff-autopsy/finding.md`) names a formatting
> wall, not a reasoning or extraction wall: the candidates can write diffs git accepts and
> almost never do, so the roadmap's easier-stratum/larger-base fork is unsupported by this
> evidence, and the pivot signal's premise remains untested until a format-hardening response
> runs — which the finding names but does not build. No figure about a model appears anywhere
> outside the gitignored breakdowns; the one record that aimed a diff at a held test never
> reached the verifier and is disclosed as attempt-shaped evidence, not a counted hack.
>
> **What is not built.** All of P2–P4: no rollouts, no training, no promotion gate, no nightly
> report, no dashboard. The bake-off is base *selection*, not the pinned baseline of
> `PREREGISTRATION.md` § 3 — that is scored on the held-out split, which does not exist until P3,
> so "measured once, re-measured never" is unspent. Cheat 6 and cheat 10 remain documented
> residuals; ingestion narrowed cheat 10 with a `conftest.py` floor but did **not** close it. No
> version has been released and there are no tags.
>
> Keep this file, `VISION.md`, and `docs/ROADMAP.md` in sync as direction firms up. Describe the
> state of the tree this file ships in, and never work in flight on a branch — a status that
> names in-progress work is stale the moment that work merges, which has already happened once
> here. A capability is written up in the same commit that lands it, so the claim and the code
> arrive together and neither can outlive the other.

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

- **Which open base** we fine-tune / LoRA — **still open, and now open on evidence.** The P1
  bake-off ran against the *working* verifier rather than on paper, and no candidate gave any
  evidence to choose on, so nothing was selected and `PREREGISTRATION.md` § 7.3 stays open.
  Re-opening it means an easier task stratum or a larger base, never a looser verifier.
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
RELEASING.md                    # Tag-push release mechanism (nothing released yet)
reports/baseline/               # The P1 bake-off — the only home for any figure about a model
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
