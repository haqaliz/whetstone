# PRD — the base-model bake-off and `reports/baseline/`

**Slice:** P1, slice 5 — the last open P1 exit criterion (`docs/ROADMAP.md:354`).
**Written:** 2026-07-30. **Card:** `docs/planning/_card/issue.md`. **Dig:**
`docs/planning/p1-baseline-bakeoff/understanding.md`.
**Core-loop element:** ① verifiable task family + verifier (first programmatic caller) and
④ signed morning report (its ancestor). Not ②, not ③.

> Every figure in this document is either **MEASURED** on this machine by the Phase-2 dig or an
> **ESTIMATE** shown with its arithmetic. **No figure about a model's performance appears here,
> because none has been measured** — that is the whole point of the sequencing
> (`PREREGISTRATION.md:20-24`), and this document may not pre-empt it.

---

## 1. Problem statement

P1 has one criterion left open, and it is the only one that produces evidence rather than
machinery:

> `docs/ROADMAP.md:354` — *"A baseline bake-off report exists under `reports/baseline/`"*
> `docs/ROADMAP.md:364` — *"One criterion remains open, and it is not nearly done.
> `reports/baseline/` does not exist."*

Three things are blocked on it:

1. **Which open base gets fine-tuned is undecided**, and `PREREGISTRATION.md:255-259` (§ 7.3) says
   it is decided *by* this bake-off, *"on evidence against the working verifier, not on paper"*.
   P2's rollouts cannot start without knowing what to sample from.
2. **P1's pivot signal has never been testable.** `docs/ROADMAP.md:387-389` — *"if no candidate base
   solves any \[…\] task, expert iteration has nothing to bootstrap from"*. Only this slice can fire it.
3. **Apple Silicon capacity is an open question** assigned to this slice explicitly
   (`docs/ROADMAP.md:594-596` — *"Discovered in the P1 bake-off, before the loop is built around it"*).

**The evidence the problem is real:** the verifier grades patches and 66 source-B tasks plus one
source-A instance are proven live, but **no model has ever been run against any of it**. A corpus
existing is not a measurement, and the repository says so in four places today.

**Why it is more than one line of work.** `docs/ROADMAP.md:354` is the *entire* committed
specification of the artifact — there is no content schema, field list, or format for the report
anywhere in either authoritative document. The generation surface (model → prompt → diff), the
scoring harness, and the report schema must all be built from nothing.

## 2. Goals & success metrics

**This slice's success is not a model score.** No numeric threshold is pre-registered and none may
be added once a number exists (`PREREGISTRATION.md:171`). Success is that a *trustworthy* number
exists and is correctly bounded — whatever its value.

| # | Goal | How it is measured |
|---|---|---|
| G1 | P1 exit criterion 5 is closed | `reports/baseline/` exists, committed strictly after `f317b89` |
| G2 | § 7.3 is closed | The report names the selected base and the evidence that selected it |
| G3 | The number is interpretable | A control arm proves the harness could reach both `PASS` and `FAIL` in the same run; an all-zero result is therefore attributable to the bases, not the plumbing |
| G4 | The number is correctly bounded | The report states it is **base selection**, not the pinned baseline; carries coverage over its denominator; carries `N` with its residual-cheat bound |
| G5 | Capacity is answered with measurement | Per-task and per-candidate wall-clock recorded and published (nothing in this repo has ever recorded a duration) |
| G6 | The tree tells the truth afterwards | `CLAUDE.md` and `docs/ROADMAP.md` stop claiming no number exists, in the same commit that makes one exist |

**Explicitly not a goal:** that any base scores well. `PREREGISTRATION.md:159-161` requires a zero
or negative result to be published as plainly as a positive one, and an all-zero outcome is P1's
pivot signal — a *publishable finding*, not a failure of this slice.

## 3. Persona & scenario

The founder, on their own machine, choosing what to train. They need to know which open base is
worth fine-tuning, whether this hardware can sustain the loop, and whether the corpus discriminates
at all — before building three more phases on top of an assumption. They will not trust a gain they
cannot check, which is why the harness must publish its own provenance and why an unexplained
zero is worse than a low number.

## 4. Decisions taken in the interview

| # | Decision | Rationale |
|---|---|---|
| D1 | **Three candidates: Qwen2.5-Coder 3B / 7B / 14B, all 4-bit** | One size ladder isolates the size variable. MEASURED weights: 1.62 / 3.99 / 7.74 GiB (13.4 GiB total). 14B-8bit is excluded: MEASURED 30.56 GiB peak exceeds the 28.08 GiB recommended working set |
| D2 | **`verify_weak` gains an `interpreter` parameter** | `PREREGISTRATION.md:96-109` requires a baseline `N`, which is uncomputable while `weak.py:57-63` hardcodes `sys.executable`. Measurement-only module, no new imports, guard stays green |
| D3 | **One greedy attempt per task per candidate** | Greedy is mlx-lm's default sampler (`generate.py:386`) and needs no seed — VERIFIED byte-identical across runs. Deterministic by construction; measures "can this base solve it", which is what selection needs |
| D4 | **The pre-registration wins the held-out clash** | `docs/ROADMAP.md:387` says the pivot signal is measured on "held-out" tasks; `PREREGISTRATION.md:242-247` says that split does not exist and may not score anything. Scored set is declared and hash-recorded and is **not** called held-out; `:387`'s wording is corrected; the clash is published as a finding |
| D5 | **Build, run, and commit the report in this slice** | Only this closes G1/G2. Requires the weight download and the full run before merge |
| D6 | **Source A is scored, and its network clone disclosed** | `PREREGISTRATION.md:142-143` — neither source is published alone. `repo.py:66-84` clones per run with no cache, so the run is *not* fully offline and the report must say so rather than claim otherwise |
| D7 | **Probe first, then decide scope** | The verifier half is unmeasured. Time a declared sample, publish the measured per-task cost, let it decide scope. Any reduction is a recorded finding with arithmetic, never a silent truncation |

## 5. Requirements

### Must-have

**M1 — A generation surface, off the reward path.** A new package `src/whetstone/bakeoff/`, a
**sibling** of `verify/` and `tasks/`, never nested under either (`GUARDED_ROOTS` is walked with
`rglob`, `tests/test_no_inference_on_reward_path.py:77`). It loads an MLX model from a **local
directory** pinned by path and `revision`, builds a prompt from the task, generates greedily, and
extracts a unified diff. No module in it may be imported by anything under `verify/` or `tasks/` —
the dependency is one-directional.

**M2 — The extraction failure must be visible, not silent.** A model emitting prose or a fenced
block instead of a diff yields STRICT `FAIL` at `kind="patch-apply"`, identical in status to a wrong
fix (`strict.py:171-183`). The harness must record the sub-verdict `kind` per result and the report
must publish the `patch-apply` count separately from substantive failures. Without this, G3 is
unreachable.

**M3 — A provisioning + scoring runner.** Per task: resolve `environment.pins` into a venv
(`gates.check_environment`, `gates.py:609-616`), cache the interpreter per distinct pin set, then
call `verify_strict(...)` **and** `verify_weak(...)` in-process with that interpreter. It may not
shell out to `whetstone verify`, which passes no interpreter and so ignores every task's pins
(`cli.py:248-250`). It must catch `UnsupportedPlatform` (`sandbox.py:66`) and `Ineligible`
(`gates.py`) and classify both as `UNVERIFIED`, following `cli.py:251-259`.

**M4 — `verify_weak` accepts an `interpreter`.** Per D2. Signature change only; no behaviour change
when `None` is passed.

**M5 — A control arm per candidate.** In the same run, on the same task set, with the same
provisioning: the inert patch (`liveness.inert_patch()`) must reach `FAIL`, and a known-good
reference patch must reach `PASS`. If either fails, the run is `UNVERIFIED` and no candidate
ranking may be published. This is what makes an all-zero result attributable.

**M5 carries an unconfirmed dependency, and it is the plan's first task.** No source-B manifest
stores a gold patch; the reference diff must be re-derived from `provenance.commit` vs
`provenance.parent` in the donor checkout. If that proves unreachable offline, M5 degrades to
inert-patch-only — which proves `FAIL` is reachable but **not** that `PASS` is, halving what G3
exists to establish. **Declared fallback:** use source A's committed gold patch
(`tasks/public/pool.json` carries the only gold patches in the corpus) as the `PASS`-reachability
control, and record in the report that source-B `PASS`-reachability was demonstrated on the public
instance rather than on a private task.

**M6 — Per-result records with timing.** `StrictResult` deliberately carries no duration
(`strict.py:98-101`) and nothing in this repo has ever recorded one, so the runner records its own:
per (candidate, task) the status, the sub-verdict kinds, the executed-node count, and wall-clock for
generation and for each verifier.

**M7 — The report, under `reports/baseline/`.** Schema in § 6. It must state that it is **base
selection, not the pinned baseline**, in text a test can check.

**M7a — The selection rule, fixed here and not after the numbers.** § 7.3 is closed *by* this
report, so the rule that closes it must exist before any number does — otherwise it is invented
while looking at the result, which is the post-hoc selection `PREREGISTRATION.md:171-177` forbids:

> The selected base is the candidate with the **highest count of STRICT-PASS tasks on the declared
> source-B set**. A tie is broken toward the **smaller** model, on the stated ground that it is
> cheaper to train and `CLAUDE.md` #4 prefers what improves as bases improve — not on any
> after-the-fact reading. **If every candidate solves zero, no base is selected, § 7.3 remains
> open, and P1's pivot signal (`docs/ROADMAP.md:387-389`) is reported as fired.**

This is a ranking rule, not a threshold: it names no minimum any base must clear, and none may be
added (`PREREGISTRATION.md:171`).

**M7b — The generation contract is frozen before the scored run.** M2 guarantees the extractor will
be iterated during development, and the prompt has no precedent to inherit. Iterating either against
the scored result is optimising on the outcome. Therefore: the prompt template and the extractor are
developed against **the control arm (M5) and a small, declared, permanently-excluded dev subset of
tasks**, never against the scored set; the contract is hashed into the provenance block (M8) before
the scored run starts; and **any change to it after the first scored run invalidates that run and
restarts it**, which is the discipline `PREREGISTRATION.md:133-135` applies to pinned inputs. The
dev subset's task ids are recorded in the report and excluded from every published count.

**M8 — Provenance.** The five pinned inputs of `PREREGISTRATION.md:131-132` — model revision, task
set, the environment pins each task declares, seeds, tool versions — plus the **generation
contract** (prompt template hash, sampler, max tokens, extractor version), which determines the
number and is *not* among those five.

**M9 — A partition guard (net-new).** Every package under `src/whetstone/` is either in
`GUARDED_ROOTS` or on an explicit exemption list carrying a reason. Today nothing notices when an
inference-carrying sibling is added, so the guard stays alive but stops describing the tree. The
existing guard is **not** widened (`CONTRIBUTING.md:20`), and the new one asserts its own set is
non-empty and is watched failing (`CONTRIBUTING.md:53-60`).

**M10 — The documentation corrections, in the same commit.** `CLAUDE.md`'s status block,
`CHANGELOG.md` (maintained by every prior slice), and
`docs/ROADMAP.md` § 4 both assert no number about a model exists. Both become false. Constraints:
`tests/test_docs.py:680-701` requires the literal `"One criterion remains open"` in § 4 (so the
guard is updated RED-first), and `tests/test_docs.py:735-777` anchors
`PREREGISTRATION.md`'s citation of `docs/ROADMAP.md:364-368` on the sentence *"not one number about
a model exists anywhere in this repository"* — which must remain **inside lines 364–368**. The
sanctioned route is the repo's own precedent (`docs/ROADMAP.md:466-473`): preserve the falsified
sentence as a **quoted, dated correction**, and keep the § 4 edit line-count-neutral so the five
citations below `:458` do not shift.

**M11 — Weights must not be committable.** `.gitignore` has no model-cache or `*.safetensors`
pattern; nothing today stops `git add -A` committing multi-GiB weights. Add one, proven the way
`tests/test_tasks_layout.py:36-43` proves an ignore rule, honouring the trailing-slash trap
(`:15-19`).

**M12 — No figure about a model in either authoritative document.** `docs/ROADMAP.md:7-9` forbids a
performance figure in the roadmap; `PREREGISTRATION.md:163` forbids one there. `reports/baseline/`
is the only sanctioned home.

### Should-have

**S1 — A declared second network exception.** `docs/ROADMAP.md:574-576` declares exactly one (the
public-instance fetch). Weight download is a second. Document it as human-run with committed
provenance, with the scored run pinned to local directories under `HF_HUB_OFFLINE=1` (VERIFIED: a
local directory loads with zero network; a repo id raises `LocalEntryNotFoundError` offline).

**S2 — A resumable run.** Checkpoint per (candidate, task) so an interrupted overnight run resumes.

**S3 — Amendment-type-2 disclosures** (`PREREGISTRATION.md:269-270` explicitly permits *adding* a
disclosure): the generation contract as an unpinned input; capacity as a bound if it bites; and that
with source A at one instance, the contamination signature § 4 pre-registers is **undetectable** in
practice.

### Nice-to-have

**N1 — A clone cache** so source-A verification stops hitting the network per run.
**N2 — A `whetstone bakeoff` CLI subcommand** rather than a module entry point.

## 6. The report schema (this slice defines it)

No schema exists anywhere; `docs/ROADMAP.md:354` is the whole specification. P4's field list
(`docs/ROADMAP.md:455-457`) is the template to borrow from — three of its seven fields are
unmeasurable today, and the report says so rather than filling them.

Required content, each item traceable to a binding line:

| Field | Binding source |
|---|---|
| A statement that this is **base selection**, not the pinned baseline of `PREREGISTRATION.md:126-128` | Forced by `:126-128` + `:242-247` + `:255-259` |
| A statement that the pinned baseline is **unmeasured**, and that "measured once, re-measured never" (`:129-132`) is **not** spent by this report | `PREREGISTRATION.md:129-135` |
| Per candidate: `solved` as a **count over its denominator** — STRICT `PASS` only | `PREREGISTRATION.md:86-90`, `:63`, `:157` |
| Per candidate: **coverage** as a count over its denominator, with `UNVERIFIED` lowering it and never leaving the denominator | `PREREGISTRATION.md:111-114` |
| Per candidate: `N`, with the verbatim framing *"N rollouts a weaker check would have scored as wins."* and no intent claim | `PREREGISTRATION.md:96-105` |
| Beside every `N`: the residual bound — cheats 6 and 10 survive; *"`N` counts what the strictness caught. It is not a claim that nothing got through."* | `PREREGISTRATION.md:211-220` |
| A note that every `N` here is a **baseline `N`**; no final `N` exists | `PREREGISTRATION.md:107-109` |
| The unverified rate | `docs/ROADMAP.md:433`, `:443` |
| Source A **per-instance**, named `pallets__flask-4045`, with the four-gate funnel (1 of 300; 299 refusals; 192 / 106 / 1) **before** the result, never as a rate, never as a delta | `PREREGISTRATION.md:149-155`, `:206-209` |
| Both sources in the **same document**; any disagreement reported as a finding | `PREREGISTRATION.md:142-147` |
| The control arm's outcome (M5) | G3 |
| The provenance block (M8) | `PREREGISTRATION.md:126-128`, `:131-132` |
| Measured wall-clock, and any capacity bound as a finding | `docs/ROADMAP.md:594-596` |
| Source B's non-reproducibility bound: recipe + liveness ledger, no byte-for-byte outside reproduction | `PREREGISTRATION.md:222-228` |
| The held-out clash (D4) as a recorded finding | `docs/ROADMAP.md:387` vs `PREREGISTRATION.md:242-247` |
| The network disclosure: the source-A `git clone` per run (D6), and the weight download (S1) | `docs/ROADMAP.md:574-576` |

**Forbidden in the report:** the `PREREGISTRATION.md:69-72` headline skeleton (it names held-out
tasks and a baseline/final pair — instantiating it would dress a bake-off number in the P4
headline's costume); any `delta`, which is defined only as `solved_final - solved_baseline`
(`:92-94`); any success threshold (`:171`); any bare proportion (`:157`). Cross-candidate
comparison crosses a changed pinned input (model revision), so it must carry the non-comparability
sentence (`:136-138`) or not be presented as comparable — a **ranking** is permitted, a delta is not.

## 7. Technical considerations

**Placement.** `src/whetstone/bakeoff/` — sibling, never nested. No module name may be exactly
`model`, `models`, `llm`, `judge`, `inference`, `completion`, `prompt` or `prompts` *if* a guarded
root ever imports it; nothing guarded should import the bake-off at all.

**The model boundary must be injectable.** CI runs `uv run pytest` and `uv run mypy src/` under
plain `uv sync`, which does **not** install the `mlx` extra (`.github/workflows/ci.yml:30-32`;
`pyproject.toml:26-29` — *"the test suite must not depend on mlx"*). So: a protocol-typed generator
the tests substitute with a stub; no module-scope `import mlx_lm` in tests (follow the
`pytestmark = skipif(...)` precedent, extended with `importlib.util.find_spec`); and a
`[[tool.mypy.overrides]]` block for `mlx_lm.*` / `mlx.*`, because `strict = true` with
`warn_unused_ignores = true` (`pyproject.toml:45-50`) makes a bare `# type: ignore` an error where
mlx *is* installed.

**Skips must be loud.** `tests/conftest.py:66-69` treats a silently skipped provisioning fixture as
*"the same class of lie as rendering UNVERIFIED as PASS"*, and `ci.yml:33-74` uses `-rs` plus an
explicit UNPROVEN warning for exactly this. An mlx-conditional test needs the same treatment.

**Verifier interaction, load-bearing facts.** A timeout is `UNVERIFIED`, never `FAIL`
(`sandbox.py:262-282`). A patch touching a held test is refused at `patch-scope` before anything
runs (`strict.py:524-533`). The sandbox denies network and confines writes but **allows reads
wholesale** (`sandbox.py:12-18`) — which is cheat 6's mechanism and why a memorised fix and a
special-cased one are indistinguishable.

**Corpus location.** The 66 manifests exist only in the primary checkout
(`/Users/aliz/dev/at/whetstone/tasks/local/`, gitignored, absent here). The runner takes a path
argument; manifests are **not** copied into the worktree (`whetstone-worktrees` discourages copying
user data between worktrees).

**Measured runtime inputs.** Generation, MEASURED on M4 Max / 36 GB at 4000-token prompt and
600-token generation: 3B-4bit 7.8 s, 7B-4bit 13.8 s, 14B-4bit 32.0 s, with ~17% run-to-run spread on
a busy machine and **random-weight reconstructions** — valid for speed, silent about quality.
ESTIMATE for generation only, 66 tasks × 3 candidates at k=1: ~59 min. The **verifier half is
unmeasured** and plausibly dominates: 3 × 67 × 2 verifiers ≈ 402 sandboxed pytest runs, each with a
`git clone` and up to 232 node ids, plus a venv build per distinct pin set. D7 governs.

## 8. Risks & open questions

| # | Risk | Mitigation |
|---|---|---|
| R1 | **A broken extractor produces an all-zero run indistinguishable from the pivot signal** | M2 + M5. The single highest-value control in this slice |
| R2 | **The verifier half exceeds the time available** | D7 probe-first; S2 resumability; any scope reduction published with its arithmetic |
| R3 | **The citation guard breaks on the required doc edit** | M10's quoted-correction route, line-count-neutral; fallback is a dated amendment plus a lockstep `ROADMAP_CITATIONS` edit |
| R4 | **Source A contamination** — an open base may have memorised the flask fix (`docs/ROADMAP.md:35`), and cheat 6 makes memorised and special-cased indistinguishable | Disclose beside the result; never quote source A as a benchmark; n=1 makes the contamination signature undetectable, which is itself a disclosure (S3) |
| R5 | **The generation contract is an unpinned input** to a number the project will treat as a reference | S3 disclosure; recorded in provenance (M8); flagged as a candidate sixth pinned input for the later baseline |
| R6 | **Weights committed by accident** | M11 |
| R7 | **`UNVERIFIED` swamps the run** (provisioning failures, timeouts, sandbox flakiness) | Coverage published, never silently excluded; if coverage is poor that is the finding, and `docs/ROADMAP.md:434-435` is explicit that the fix is a more reliable sandbox, never a looser check |

**Open questions:**

1. **Does the whole-evaluation `UNVERIFIED` collapse apply here?** `PREREGISTRATION.md:116-119` says
   an evaluation with any residual unverified task reduces to `UNVERIFIED`, but it presupposes `R`
   retries and `R` is undefined until P3 (`:249-253`), and the surrounding text is the promotion
   gate's. **Proposed reading: gate-scoped.** The bake-off publishes per-candidate coverage and
   unverified counts instead, and states the reading in the report. `docs/ROADMAP.md:433` binds
   either way, and this is the first eval.
2. **What prompt does a base actually get?** Problem statement alone, or repository context? This
   determines the number and has no precedent in the tree. Proposed: the smallest defensible
   contract — problem statement plus the declared failing test node ids — fixed and hashed, with the
   choice disclosed rather than tuned. **Tuning the prompt against the score would be selection on
   the outcome**, which is the failure this project exists to avoid.
3. **Is a reference patch available for source B's control arm?** No source-B manifest stores a gold
   patch; it must be re-derived from `provenance.commit` vs `provenance.parent` in the donor. The
   plan must confirm this is reachable offline before M5 is buildable; the declared fallback is in
   M5.
4. **Effort is unestimated.** This slice is larger than any prior one — a new package, a
   verifier-adjacent signature change, a new report format, four coordinated doc edits, and an
   overnight run. The plan sizes it; the PRD does not pretend to.

## 9. Out of scope

- **All of P2**: no rollout loop, no rejection sampling, no LoRA, no training, no checkpoint.
- **All of P3**: no promotion gate, no `R`, no leakage check, no held-out split. § 7.1 and § 7.2
  stay open and unspent.
- **The pinned baseline measurement** — explicitly not performed here (§ 6, D4).
- **A dashboard, or any UI.** Post-horizon (`CLAUDE.md` § Tech direction).
- **Any change to the reward's semantics.** `verify_strict` is called, never modified; the only
  verifier change is M4's additive parameter on the measurement-only WEAK path.
- **Fixing the stale `whetstone-next` / `whetstone-worktrees` skill files** (recorded in the dig).
- **A clone cache** (N1) and a CLI subcommand (N2) unless they fall out cheaply.
