# Understanding — `feat/roadmap-and-task-family`

Phase 2 dig for the unit of work in `_card/issue.md`. Written 2026-07-26.

---

## 1. What the work is really asking

Write `docs/ROADMAP.md`: a 2–3 month phased plan with milestones. But the *load-bearing*
part is not the phasing — it is **choosing the first task family and specifying its
verifier**, because `whetstone-next` ranked this pick precisely on the grounds that
everything else in the core loop is blocked on core-loop element ①.

A roadmap that lists phases without committing to a family and a concrete check would
leave the blocker exactly where it is, under a new filename. That is the failure mode to
design against.

## 2. Repo state (verified, not assumed)

`git log` — two commits, both 2026-07-26:

```
392baf6 Port the Claude workflow skills from belay/contig
000ccd9 Seed repo with project context and vision
```

No tags. `git diff master feat/roadmap-and-task-family/aliz` is empty — the branch has no
commits of its own yet.

**Complete repo contents:** `.gitignore`, `CLAUDE.md`, `VISION.md`, `.claude/skills/`
(10 skills, 12 markdown files). **Zero lines of executable code in any language.**

Confirmed absent: `pyproject.toml`, `uv.lock`, `src/`, `tests/`, `README.md`, `docs/`
(entirely), `CHANGELOG.md`, `dashboard/`, `.github/`, `RELEASING.md`, `LICENSE` (despite
`CLAUDE.md:93` stating Apache-2.0), `.worktreeinclude`.

`docs/ROADMAP.md`, `docs/technical/ARCHITECTURE.md`, and `docs/product/PRODUCT_SPEC.md`
are all named in `CLAUDE.md` and **none of them is written**.

## 3. Technical commitments already baked in (the roadmap must not contradict these)

These were not in `CLAUDE.md`'s prose — they are encoded in `.gitignore` and the skills,
and they constrain the plan.

**From `.gitignore`** (which states outright at line 19: *"Pre-declared: these directories
don't exist yet: the loop is not built"*):

| Path | Implication |
|---|---|
| `/runs/` | per-night run-state directory |
| `/checkpoints/` | the artifact the promotion gate promotes or rejects |
| `/tasks/local/` | a `tasks/` tree where committed/shareable task defs sit beside the user's private ones |
| `/reports/local/` | morning-report artifacts, same public/private split |
| `/_sandbox/` | **the isolated re-execution area** — i.e. the verifier runs candidate solutions here |
| `.mypy_cache/`, `.ruff_cache/` | mypy + ruff are intended (named *nowhere else* in the repo) |
| `.next/` | the dashboard is **Next.js** specifically, not just "TypeScript" |
| `*.egg-info/`, `dist/` | the Python core is a packaged, distributable project |

**From the skills:**

- CLI entrypoint is **`whetstone`**; the only named subcommand anywhere is
  **`whetstone report --last-night`** (`whetstone-report:87`).
- Package layout `src/whetstone/`, tests in `tests/`, `uv` exclusively (no pip/poetry).
- Dashboard is a **subdirectory of this repo** (`.claude/worktrees/<n>/dashboard`), not a
  separate repo.
- **Checkpoint lifecycle:** `candidate → evaluated → promoted / rejected / UNVERIFIED`
  (`proposals.md:17`). The gate has **exactly three exits** and `UNVERIFIED` is never
  collapsed into `promoted`.
- **Pipeline shape**, stated consistently three times: `task family → verifier →
  self-play/RL → distillation → promotion gate → morning report`.
- The technical-proposal contract names the data-model surface: *"task format, verifier
  contract, reward signal, checkpoint/eval artifacts, report schema"* (`proposals.md:47`).
- **Adversarial test taxonomy** (`tech-plan:72`): *"degenerate solutions, edited
  timers/asserts, mutated fixtures, claimed-but-not-observed state."*
- Tests are deterministic, no network; any BYOK teacher call sits behind an injectable
  seam and never runs in CI.
- PyPI is the implied publish target; **no package name chosen**. 0.x versioning, tag
  `vX.Y.Z`, tag-push is the entire release mechanism.

## 4. What Belay actually gives us (this changes the plan)

Belay (`~/dev/at/belay`) is **real and shipped**, not vaporware: v0.7.0, 8 tags, 13,068
LOC across 49 modules, **832 tests passing in ~16s** (run and confirmed). Apache-2.0, CI,
CHANGELOG, zero runtime dependencies.

Its verifier is genuinely execution-grounded and genuinely zero-LLM — enforced by an **AST
walk** (`tests/test_import_guard.py`) that parses every module under `src/belay` and fails
the build if the verdict path imports an inference library. That is the credible answer to
"isn't this an LLM judge with extra steps?", and it is cheaply portable.

### What is cheaply reusable (the crown jewels)

| Module | Why it matters to Whetstone |
|---|---|
| `verify/verdict.py` (114 L, zero deps) | The honesty contract **as the shape of the reduction**: `_RANK` puts `UNVERIFIED` (2) *above* `PASS` (0) and `WARN` (1), so worst-status-wins can never render an unverified turn clean. An empty verdict set reduces to `UNVERIFIED`, not `PASS`. |
| `verify/invariants.py` (299 L) | The **provenance boundary**: policy is loaded only from an operator file; there is no trace-reading loader, and a test asserts that absence structurally. For an RL reward this is existential — otherwise the policy authors its own reward. |
| `snapshot/bth1.py` (449 L) | Deterministic tree hash over path bytes, mode (incl. setuid), mtime_ns, st_flags, uid/gid, content sha256, symlink targets, xattrs, hardlink identity. Domain-independent. |
| `corpus/metrics.py` (174 L) | Precision/recall/**coverage** vs human labels, with UNVERIFIED excluded from the confusion matrix (it lowers coverage instead) — refuses the "100%-precision-by-construction lie". |
| `tests/test_import_guard.py` | The no-model-in-the-verdict-path guard. |
| `eval/instances/` + `eval/scripts/` | SWE-bench-Lite eligibility filter + pure offline seeded stratified draw, with committed `pool.json` / `selected.json`. |

### What does NOT fit — and this is the important finding

`CLAUDE.md:79` says *"Reuse Belay's verifier/replay where it fits."* The dig says the
**verdict semantics fit; the replay substrate probably does not**, for four reasons:

1. **macOS-only.** Sandbox is Seatbelt, snapshot is APFS `clonefile`; off macOS the sandbox
   *raises* rather than degrading. If training runs on a Linux GPU box, this is unusable
   as-is and is the single biggest porting cost.
2. **Parallel tool calls → UNVERIFIED.** Belay deliberately refuses to serialize turns, so
   any batched rollout produces UNVERIFIED rather than signal. A batching training loop and
   Belay's replay are structurally incompatible.
3. **Throughput.** ~5 ms/turn snapshot on a 400-file tree, scaling with tree size, plus a
   full APFS clone + restore + server spawn per replay. Built for *auditing* runs, not for
   generating high-volume RL rollouts.
4. **No API and no reward surface.** `src/belay/__init__.py` is one line (`__version__ =
   "0.0.0"` — and stale; `pyproject.toml` says 0.7.0). There is no exported programmatic
   surface, and grepping for "reward"/"training" returns nothing.

**Why this matters:** Belay solves a *harder* problem than Whetstone's v1 needs. Belay asks
*"did the agent's trace faithfully describe what it did?"* — which requires snapshot +
replay. A v1 code-fixing reward only needs *"does the end state pass an operator-held
check?"*, which needs a sandbox and an exit status. Whetstone should take Belay's **verdict
semantics and provenance discipline** and build a much simpler substrate, rather than
inheriting a macOS-locked, MCP-locked, latency-heavy replay engine it does not need yet.

### Cautionary finding

Belay's `docs/technical/PHASE0_RESULTS.md` — the doc that gates PROCEED vs PIVOT — contains
**20 occurrences of `TO-BE-FILLED`**. Its headline violation rate is unpublished, Stage 3 is
partial, and the only real numbers (Stage 2: 2/9 = 22.2% instance violation rate, 2/130 =
1.5% per-turn FAIL) live in an **uncommitted worktree**. Belay is admirably honest about
this. The lesson for our roadmap: **the engine working and the empirical claim being
established are two different milestones**, and conflating them is exactly the mistake the
"first honest number" milestone exists to prevent.

## 5. The task family — candidates and the leading one

**No family is chosen anywhere in the repo.** The only concrete candidate named in any
source is parenthetical, in `CLAUDE.md:88` and again in the seed research: *"code/tool-use
tasks with checkable end-state."* The recurring `task-verifier` slug in the skills is an
illustrative example, not a decision.

The leading candidate (to be settled in the PRD interview, not here):

> **Python repo bug-fixing, SWE-bench-Lite style, rewarded by operator-held test execution
> (`FAIL_TO_PASS` / `PASS_TO_PASS`).**

Why it looks strong:
- The reward is a **process exit status**, not a comparison — about as deterministic and
  as un-judge-like as a reward gets.
- Belay already built the corpus machinery for exactly this domain: a filter to pure-Python
  repos (django, sympy, flask, requests, sphinx, pylint — matplotlib/scikit-learn/astropy/
  xarray/seaborn excluded for needing C/Cython builds), yielding 166 strict-eligible
  instances, drawn by a pure, offline, seeded stratified draw with committed artifacts.
- The cheat surface is **known and enumerable**, which is what makes "airtight" testable
  rather than aspirational: edit the tests, weaken an assert, mutate a fixture, `sys.exit(0)`,
  monkeypatch the runner, special-case the input. The defence is the provenance boundary —
  tests are operator-held and restored from the golden commit after the patch is applied,
  and the patch is confined to non-test files. That is `invariants.py`'s discipline applied
  to a code family.

Open risk on it: it may be **contaminated** — SWE-bench-Lite is widely trained on, so an
open base may already have memorised fixes, which would inflate the baseline and muddy the
delta. This needs a stated answer in the roadmap (held-out construction, or a private task
source, or both).

## 6. Guardrail check

| Guardrail | Status |
|---|---|
| Reward execution-grounded, never a judge | **Held.** Leading family's reward is a test-suite exit status. No model on the reward path. |
| No frontier base-model training | **Held.** Sharpen an open base; nothing here proposes pretraining. |
| Never regress / `UNVERIFIED` ≠ win | **Held**, and strengthened — Belay's `_RANK` gives us a proven implementation shape to port. |
| Local / BYOK / no data egress | **Held**, with one flag: SWE-bench instance fetching touches the network. Belay's pattern (human-run fetch, committed output, pure offline draw) is the precedent to follow. |
| Gets better as base models improve | **Held.** A stronger base is a better starting policy; the verifier and the accumulated verified-improvement record are the durable part. |

Nothing in this work drifts toward an LLM judge or toward base-model training.

## 7. Contradictions and open questions

**Contradictions surfaced (not papered over):**

1. `CLAUDE.md:79` "Reuse Belay's verifier/replay where it fits" reads as though the replay
   engine is the reusable asset. The dig says the opposite: the **verdict semantics** are
   the asset; the replay substrate is macOS-locked, MCP-locked, and throughput-hostile.
   The roadmap should say which parts it takes and which it deliberately does not.
2. `VISION.md` drops the attributions that `CLAUDE.md` carries — the 35% figure appears
   unsourced, and the timer-rewriting claim appears unsourced. Venue also differs
   ("Sequoia Ascent 2026" vs "Sequoia 2026"). If the roadmap cites either, use
   `CLAUDE.md`'s attributed form.
3. The seed research's **"+7% on your real tasks"** is *illustrative pitch copy*, not a
   target or a finding, and its **"MVP wedge (1–2 months)"** is an unsourced gut estimate
   against `CLAUDE.md`'s "2–3 month" horizon. Neither may be quoted as a commitment.

**Open questions for the PRD interview:**

- **Q1 — the family.** Confirm the leading candidate, or name another. This is the decision
  the whole roadmap hangs on.
- **Q2 — training platform.** macOS (where Belay's substrate works) or a Linux GPU box
  (where it does not)? This changes what is reusable and adds or removes a porting phase.
- **Q3 — contamination.** How is the held-out set protected from a base model that may have
  memorised SWE-bench? Private tasks, or a decontamination step, or an accepted caveat?
- **Q4 — the "reward-hacking caught & rejected: N" counter.** No source names how a hack
  attempt is *distinguished* from an ordinary failure. Without that distinction the counter
  is not implementable. Needs a definition.
- **Q5 — base model + runtime.** Ollama / vLLM / transformers are always listed as
  alternatives, never chosen. Which, and which open base?
- **Q6 — roadmap scope.** Does `docs/ROADMAP.md` phase only to the first honest number, or
  through distillation and the dashboard as well?

## 8. Grounded facts available to cite (exactly three)

Per `CLAUDE.md:108-119` and re-enumerated in `whetstone-next:126` and `prd-generator:89`:

1. RLVR is the live frontier; reward-hacking is its central documented failure mode —
   **METR** observed a model rewriting a timer instead of optimizing the task.
2. **"One Token to Fool LLM-as-a-Judge"** shows up to **35% false positives**.
3. **Karpathy (Sequoia Ascent 2026)** — the valuable RL environments *"aren't in the
   frontier-lab mix."*

Anything else is **unverified and must be labeled so**. Note that Belay cites two further
arXiv items (2603.03116 corrupt successes 27–78%; 2507.08794 judge false positives) — these
are *not* in Whetstone's grounded list and must be verified before use, not inherited.
`CLAUDE.md:119`: *"If you need a statistic that isn't here, do not invent one; say it's
unverified."*
