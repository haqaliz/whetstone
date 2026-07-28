# PRD — `tasks/` ingestion and the on-disk task format

**Slice:** ROADMAP P1, slice 2. **Written:** 2026-07-28. **Branch:** `feat/p1-task-ingestion/aliz`.
**Card:** `docs/planning/_card/issue.md`. **Upstream spec:** `docs/ROADMAP.md` § 1, § 4 (exit
criterion 4 at `:244`).

> **No performance figure appears in this document.** Every count below is either a command's
> output reproduced in the dig (and independently re-run by the integrator where marked
> **[verified]**), or is labelled a ceiling / an estimate. Nothing here is a measurement of a
> model, because no model has been run.

---

## 1. Problem Statement

**The verifier grades patches. Nothing has graded a model, because there are no tasks.**

P1 slice 1 shipped the reward — the frozen `Task` contract, STRICT, WEAK, the Seatbelt sandbox,
and a ten-cheat adversarial corpus (`621831e`). But every task it has ever run is a synthetic
fixture built inside `tests/fixtures/repos/__init__.py`. There is no `tasks/` directory on
`master` **[verified]**, no on-disk format, and no way to point the verifier at a real
repository.

This blocks, in order:

- **P1 exit criterion 5** — the base-model bake-off is defined as running *against the working
  verifier* (`docs/ROADMAP.md:210`). It needs runnable task instances.
- **All of P2** — rejection sampling has nothing to sample against.
- **The honest number itself** — the wedge is publishing a verified delta on real tasks. A
  corpus of synthetic fixtures cannot produce one.

**Who has the problem.** The Whetstone ICP: an engineer who wants a model measurably better at
*their* tasks by morning, privately, and who will not trust a gain they cannot check. Today the
system cannot be pointed at their tasks at all.

**Evidence it is real.** `docs/ROADMAP.md:244` names it as an unmet P1 exit criterion;
`CLAUDE.md`'s status block names it first under "What is not built"; and `docs/planning/
p1-verifier-core/prd.md:378-380` names its unestimated half as *the* schedule risk in P1.

---

## 2. What the dig changed — read this before the requirements

The deferred risk was **aimed at the wrong target**, and the requirements below only make sense
once that is stated plainly.

`docs/planning/p1-verifier-core/prd.md:358` recorded environment provisioning for real
SWE-bench instances as **High, deferred, unestimated**. The dig measured it: **~11 s per
instance** (clone 7.6 s + provision 3.5 s), and drove one real instance — `pallets__flask-5063`
— to a **fully green STRICT verdict through the real Seatbelt sandbox with `strict.py`
unmodified**: 54 declared node ids, `executed == declared`, zero skips, both `fail_to_pass` ids
flipping FAIL→PASS. **The verifier's semantics work on a real instance.** That risk is retired.

What actually binds is an assumption nobody costed — **the pytest-node-id form**:

| Stage | Remaining | Lost to |
|---|---|---|
| SWE-bench-Lite | 300 | — |
| Addressable as pytest node ids | 108 | **−192 (64%)**: django uses the unittest-runner form `test_x (module.Class)`; sympy uses bare names with no file path |
| Not a compiled/scientific stack | 47 | −61: matplotlib, scikit-learn, astropy, xarray, seaborn |
| Node ids not corrupt in the dataset | 35 | −12: whitespace-split parametrised ids |
| Interpreter era not verified-dead | **24** | −11: `requests==2.4.0` cannot import on ≥3.10; `pytest<6.0` needs the removed `imp` on 3.12 |

**24 is a ceiling. One instance is proven.** Sphinx is 14 of the 24 and is the load-bearing
untested assumption — its published `3.5.4` imports on 3.12, but its own suite has never been
run at a base commit. **UNVERIFIED.**

Three findings that change the design rather than the estimate:

1. **Era-pinning is mandatory and is not derivable from repo metadata.** flask declares
   `click>=8.0` with no upper bound; `uv` resolved today's `click 8.4.2`, which removed
   `CliRunner(mix_stderr=)` and failed 4 `pass_to_pass` tests — **a false FAIL**. Three
   hand-chosen pins made it green. **A verdict that depends on what PyPI served that morning is
   not execution-grounded**, and this is the single most important thing the format must fix.
2. **`strict.py:179` hardcodes `sys.executable`.** Per-task interpreters are mandatory. The
   sandbox permits it: reads outside the write scope are allowed wholesale
   (`sandbox.py:12-15`, `:114-121`), and an out-of-scope venv interpreter was verified usable
   under the real profile.
3. **The live SWE-bench-Lite dataset does carry `FAIL_TO_PASS`, `PASS_TO_PASS`, `test_patch`
   and `environment_setup_commit`.** Belay's committed pool carries **none** of them — 166
   records, exactly six keys **[verified]**, and the gold `patch` is absent too. Whetstone
   needs its own fetch; Belay's pool contributes provenance and base commits only.

---

## 3. Goals & Success Metrics

**Goal:** `whetstone` can be pointed at a real repository and produce task instances the shipped
verifier runs — for both sources — with eligibility **proven per instance, never assumed**.

| # | Success metric | How measured | Target |
|---|---|---|---|
| G1 | Every ingested task is **live** | empty patch → STRICT FAIL; reference patch → STRICT PASS, with `executed == declared` | 100% of **all** ingested tasks, both sources; a task passing with no patch **fails the build** |
| G2 | Source A eligibility is **proven, not assumed** | every instance passes all four gates (§ 6.2) or is recorded as ineligible **with the gate that rejected it** | no instance is silently dropped |
| G3 | Source B mines offline | a test asserts no network call on the source-B path | zero network calls |
| G4 | The draw is deterministic | same seed → byte-identical selection file | byte-for-byte, per Belay's `tests/test_eval_mint_set.py:323-341` |
| G5 | Ingestion cannot author its own reward | the provenance census still admits exactly one `Task` producer | `tests/test_task_contract.py:232-236` stays green |
| G6 | The suite stays green | `uv run pytest`, `ruff check .`, `mypy src/` | all exit 0; CI green |

### 3.1 The source-B liveness problem — and the ledger that closes it

G1 is unfalsifiable for source B as the layout stands: `/tasks/local/` is gitignored, so **the
pre-registered headline source is the one source whose liveness no reader can check.** That is
the same shape of hole this project exists to refuse, and it needs an explicit answer rather
than an inference.

**The answer: a committed liveness ledger, `tasks/local-ledger.json`.** For every mined
source-B task it records the `task_id`, a **hash of the manifest** (not its contents), the two
verdicts (empty-patch FAIL, reference-patch PASS), `executed == declared`, the skip count, and
the tool/interpreter versions and date behind them. **The evidence is committed; the user's code
is not.** A reader can then check that every claimed source-B task was proven live, and can
re-derive the ledger themselves from the committed recipe and their own copy of the donor —
without any of the user's data leaving the box.

M8 therefore produces two artifacts, not one: the pass/fail gate during ingestion, and this
ledger as its durable record.

**Held-out set:** out of scope here. This slice *mints* the corpus; splitting it into
train/held-out belongs to P3 (`whetstone check-leakage`, `docs/ROADMAP.md:304`). **The format
must carry enough provenance to make that split auditable later** — that is this slice's
obligation to it, and no more.

**Not a goal:** any number about a model. Nothing here runs a model.

---

## 4. Decisions taken (recorded, not to be re-litigated)

| # | Decision | Rationale |
|---|---|---|
| D1 | **Source A: the narrow proven subset, and the 4-gate eligibility filter is the deliverable** | The filter, not the instance count, is the durable asset. Manifests-only would satisfy exit criterion 4's letter while contributing zero to the bake-off — and source A is the only externally-checkable half, so that would leave the headline resting entirely on data no outside reader can audit |
| D2 | **Restrict source B to commits that MODIFY an existing test** | Avoids relaxing `strict.py:131-140`, a fail-closed guard on the reward path. Costs ~35% of belay and ~50% of rereflect candidates; contig alone still yields ~220 **[verified: 224 by the integrator's classifier, 220 by the dig's]** |
| D3 | **Mine all four local donors**: contig, belay, rereflect, whetstone | rereflect is the subject-diverse one (a services monorepo) and is the strongest available answer to the self-selection critique in § 8.3 |
| D5 | **Corpus target: 60–80 source-B tasks, stratified across all four donors** | Large enough to survive P3's train/held-out split and still leave a held-out set worth reporting a number on. ~120–240 suite runs to mint. Stratification is what makes D3's self-selection mitigation real rather than nominal — a corpus that is 90% contig has not diversified anything |
| D4 | **Cheat 10: the structural floor only** — auto-hold every `conftest.py` on the path from repo root to each held test | Deterministic, no instrumentation, and **measured to cost ~0% of candidates** (contig 0/220 **[verified]**, belay 1/49). The audit-hook widener is deferred: it must subtract the gold patch's touched paths or the restore overwrites the fix, and that subtraction is a sharper design risk than this slice should carry |

---

## 5. The on-disk task format

### 5.1 Layout

```
tasks/
├── public/                     # committed — source A
│   ├── pool.json               # human-run fetch output, provenance header (never re-fetched by tests)
│   ├── selected.json           # the seeded, offline, reproducible draw
│   ├── ineligible.json         # the REJECTION LEDGER — instance -> the gate that rejected it
│   └── instances/<id>.json     # one manifest per eligible instance
├── local/                      # GITIGNORED — source B, the user's own data, never committed
│   └── <donor>/<id>.json
└── recipes/                    # committed — HOW source B is mined, never WHAT it produced
    └── <donor>.json            # donor path, filters, tool versions, mining date
```

**This resolves a conflict the roadmap did not notice.** `.gitignore:16-24` pre-declares
`/tasks/local/` as *"the user's own data [that] never belongs in the repo"*, while
`docs/ROADMAP.md:244` requires `tasks/` to hold instances from **both** sources with *committed*
provenance. Both cannot be literally true for source B. **The resolution: source B's committed
artifact is the recipe and the provenance record, never the mined instances.** `/tasks/local/`
is already ignored and `/tasks/` is not **[verified]**, so the split the gitignore anticipated
is exactly this one. This must be stated in the report, not left for a reader to infer.

### 5.2 The manifest — and the breaking contract change

`load_task` rejects unknown fields (`task.py:163-170`), by design: *"a typo'd key would
otherwise verify the task against less than the operator declared."* There is no version field
and no `extra` escape hatch. **Therefore every field this slice adds is a breaking contract
change**, requiring `_FIELDS` (`task.py:51-63`), the `Task` dataclass (`:66-86`), the
constructor call (`:143-153`), and `tests/fixtures/repos/__init__.py:172-184` to change
together — which will transiently fail ~19 tests in `test_task_contract.py` plus every
fixture-built verifier and adversarial test. **That is the expected RED, and the plan must
sequence it as one atomic task, not spread it across several.**

One field is added:

```
environment {
  python: "3.12"                  # the interpreter to run this task under
  pins: ["click==8.1.3", ...]     # resolved, era-correct, exact ==
}
```

**Why it is not optional.** Without it the reward is decided by the resolver's clock (§ 2,
finding 1). `pins` must be exact `==` — a range re-opens the same hole.

Everything else is unchanged: `task_id`, `source`, `repo_url`, `base_commit`,
`problem_statement`, `fail_to_pass`, `pass_to_pass`, `test_blobs` (path → base64 bytes),
`provenance`.

### 5.3 Constraints the ingester must satisfy (all from the shipped verifier)

| # | Constraint | Source | Consequence if violated |
|---|---|---|---|
| C1 | Every `test_blobs` path must **already exist at `base_commit`** | `strict.py:131-140` | UNVERIFIED on every such task. This is D2's whole reason |
| C2 | Node ids must be **fully parametrised**, class-qualified, rootdir-relative POSIX | `strict.py:282-309`, `:399-412` | A bare parametrised id makes pytest expand it → `executed != declared` → FAIL |
| C3 | Blob paths must be **git's exact canonical spelling** | `strict.py:423-434` | `./tests/x.py` loads cleanly but drops out of the patch-**rejection** set. The unconditional restore still covers the reward, so this is a defence-in-depth hole, not a live reward hole — but ingestion must normalise |
| C4 | `pass_to_pass` must not overlap `fail_to_pass`; no duplicates | `task.py:135-141`, `:194-199` | `ValueError`. SWE-bench lists commonly overlap — dedupe at ingest |
| C5 | `provenance` values must be **flat strings** | `task.py:271-276` | `{"minted": 2026}` rejected; no nested objects or lists |
| C6 | The multi-task loader must **not** live in `whetstone/verify/task.py` | `tests/test_task_contract.py:232-236` | The census asserts exactly one public callable returns a `Task`. A `load_tasks(...) -> tuple[Task, ...]` there fails it |
| C7 | Ingestion modules must not be named `model(s)`, `judge`, `prompt`, … | `tests/test_no_inference_on_reward_path.py:119-121` | The first-party inference-name ban flags them. Name the schema module `manifest.py`, never `models.py` |

### 5.4 The elegant consequence of C1 + the restore

`base_commit` is the **parent** `P` of the red→green commit `C`, and `test_blobs` holds `C`'s
version of the test file. STRICT's unconditional restore (`strict.py:160-163`) then **is** the
test-patch application. **No separate test-patch mechanism is needed, and none should be
built** — for either source.

---

## 6. Requirements

### 6.1 Must-have

- **M1 — the format.** `tasks/` layout (§ 5.1), the `environment` field (§ 5.2), and the loader
  changes, as one atomic change. Round-trips through `load_task` with `test_blobs`
  **byte-identical**.
- **M2 — `strict.py` takes a per-task interpreter.** Replaces the hardcoded `sys.executable`
  (`:179`). Defaults to current behaviour so no existing test changes meaning.
- **M3 — source B miner.** Offline, over a local donor path. Selects `--no-merges` commits
  touching ≥1 test `.py` **modified** and ≥1 non-test `.py`; derives node ids by running the
  suite twice under junit XML; emits a manifest + a committed recipe. A test asserts no network
  call on this path.
- **M4 — node ids derived through `strict.py`'s own reader.** Expose `_read_report`/`_node_id`
  rather than duplicating them. Ids minted by a different code path than the one the verifier
  compares against can drift in exactly the ways `_node_id` exists to prevent.
- **M5 — the cheat-10 structural floor.** Auto-hold every `conftest.py` from repo root to each
  held test's directory, plus the held test files themselves.
- **M6 — source A: the 4-gate eligibility filter** (§ 6.2) plus the human-run fetch, the
  committed pool, and the seeded offline draw.
- **M7 — the rejection ledger.** Every ineligible instance recorded with the gate that rejected
  it. Never a silent drop.
- **M8 — liveness on every ingested task, plus the committed ledger.** Empty patch → FAIL;
  reference patch → PASS with `executed == declared`. A task that passes with no patch fails the
  build. For source B the result is recorded in `tasks/local-ledger.json` (§ 3.1) — hashes and
  verdicts, never contents — so the headline source's liveness is checkable without egress.

### 6.2 The four gates (M6, in order — each must *prove*, never assume)

1. **Format** — every `fail_to_pass` and `pass_to_pass` id parses as a pytest node id. Kills
   django and sympy (64%).
2. **Collectability** — every id is collectable in the **real checkout**. Assumption-free, and
   the only reliable detector for the 12 truncated-id instances.
3. **Environment** — the pinned env resolves **and imports** on the nominated interpreter.
   **Install-exit-0 is not evidence** — the same false-green the CI `mlx` step already guards
   against (`.github/workflows/ci.yml`).
4. **Liveness** — the full two-run FAIL-then-PASS check with `executed == declared`.

### 6.3 Should-have

- **S1** — `whetstone verify` accepts a **directory**, resolving the open question at
  `docs/planning/p1-verifier-core/prd.md:365`. Constraint: the four exit codes are pinned as
  four distinct values (`tests/test_verify_cli.py:220-224`), so a multi-task run must reduce
  worst-status-wins via the existing `verdict.reduce`, **not** add a fifth code.
- **S2** — the ingestion package added to `GUARDED_ROOTS`
  (`tests/test_no_inference_on_reward_path.py:62`). Ingestion authors `test_blobs`, the artifact
  the whole boundary rests on; it is reward-adjacent and should be guarded.
- **S3** — lift Belay's offline-purity AST guard (`tests/test_eval_pool_fetch.py:323-400`),
  which asserts the network client appears only inside `main`.

### 6.4 Nice-to-have

- **N1** — a bare-clone + detached-worktree cache (Belay's `eval/minting_driver/workspace.py`),
  so N instances of one repo cost one clone. Matters for P2 throughput, not for P1 correctness.
- **N2** — `rereflect` per-service ingestion targets. **Deliberately last**: it has no root
  `pyproject.toml`, so each service needs its own environment, and it is the only donor whose
  cost is unbounded by this slice's estimate.

---

## 7. Technical Considerations

**Core-loop element: ① a verifiable task family + verifier.** This slice completes the "task
family" half. It touches no other element.

**How the reward stays execution-grounded.** It is unchanged: a pytest exit status folded with
the executed-set assertion. Ingestion never grades anything. **No model is invoked anywhere in
this slice**, and the reward-path AST guard must stay green (S2 widens it).

**Reward-hacking surface — the honest statement.** Ingestion does not sit on the reward path,
but it **authors the boundary the reward path enforces**. Three specific holes:

1. **Under-declared dependencies** — cheat 10 verbatim. Narrowed by M5, not closed (§ 8.1).
2. **The resolver's clock** — closed by the `environment` field (§ 5.2). This one is new and
   was not in the ten-cheat enumeration; it is not a *policy* cheat but it corrupts the reward
   identically, and the cheat table is append-only by construction (`docs/ROADMAP.md:134-143`).
3. **A vacuous corpus** — a task that passes with no patch pays reward for nothing. M8 is the
   defence, and it must be watched failing (per `CONTRIBUTING.md:56-60`) against a deliberately
   vacuous task before it is trusted.

**Locality.** Source B is `git` + local pytest against a local path; `repo.py:57-84` clones
whatever string the manifest carries, and a plain local path is proven to work
(`tests/fixtures/repos/__init__.py:177`). Nothing leaves the box. Source A's fetch is the **one
declared network exception** (`docs/ROADMAP.md:420-422`): human-run, output committed, draw pure
and offline. Tests never fetch.

**Gate impact:** none. P3 is untouched. The format's provenance obligation to it is § 3.

**Doc-consistency coupling.** `tests/test_docs.py` pins substrings, not line numbers. Two
constraints bind here: `docs/ROADMAP.md` § 3 must keep the string `"task ingestion"`
(`test_docs.py:277-296`) — which is the pointer at this very slice — and **`CLAUDE.md` must not
name a concrete working branch** (`:168-192`), so the status block may not mention
`feat/p1-task-ingestion/aliz`.

---

## 8. Risks & Open Questions

### 8.1 Cheat 10 is narrowed, not closed — and the claim must say so

After M5 the honest claim is:

> Ingestion declares, in `test_blobs`, every `conftest.py` on the path to each held test. The
> boundary is therefore wider than the test files alone. It is still exactly as wide as the
> manifest, and the manifest is still not provably complete.

**What may not be claimed:** that undeclared-dependency mutation is defeated. It is not.
**~22% of contig's mintable commits also touch a non-`.py` file [verified: 49/224]** — data
files no `conftest.py` rule and no import walk would ever see. Cheat 10 **stays `BOTH_ACCEPT`
in the corpus** (`tests/adversarial/corpus.py`), because its fixture's manifest omission is
hand-authored and no ingestion rule makes it stop being true. ROADMAP § 3's row 10 gains
*"narrowed at ingestion, not eliminated"*; its status cell stays **RESIDUAL**, keeping
`test_docs.py:216-242` green.

### 8.2 Risk table

| Risk | Severity | Mitigation |
|---|---|---|
| **Sphinx (14 of the 24 source-A survivors) has never had its suite run at a base commit** | **High** | Gate 3 + gate 4 discover it per instance. If sphinx fails wholesale, source A collapses to ~10 and **that number is reported, not hidden** |
| **Two full suite runs per candidate commit** — ~440–660 executions for contig alone | **High** | One-time, offline, parallelisable. It is the dominant cost of the slice and must be budgeted, not discovered |
| **The breaking contract change transiently reds ~19 + all fixture tests** | Medium | Sequence as ONE atomic task |
| **Over-declaring `test_blobs`** — if a held path is one the gold fix must change, the restore silently overwrites the fix and the task is permanently unpassable, reported as an ordinary FAIL | **High** | M5 holds only tests + `conftest.py`, never source. A test must assert a held path is never one the reference patch touches |
| **Flaky `pass_to_pass`** admits a task whose verdict is noise | Medium | A repeat run at mint time; discard non-deterministic ids |
| **`rereflect` per-service environments are unbounded by this estimate** | Medium | N2 is last; if it overruns, ship the three `pyproject.toml` donors and say so |
| **CI cannot host real-repo liveness** | Medium | Excluded from CI — not for time, but because reprovisioning ~10 environments per run makes a red build ambiguous between "the task regressed" and "the network flaked", and an ambiguous red is a verdict decided by the harness. Commit the liveness result as a dated artifact; re-verify locally |

### 8.3 Source B's self-selection — for `PREREGISTRATION.md`, stated up front

The private headline is measured on **the author's own repos**, largely written by Claude Code
under strict TDD, and belay/contig are *about verification and sandboxing* — a closer loop than
*"point it at your tasks"* implies. Selecting commits by red→green also over-represents the
test-written-first shape, which is not what a real bug backlog looks like. D3's inclusion of
rereflect is the mitigation. **None of this disqualifies source B** — it is uncontaminated and
on-thesis, which is what it is pre-registered for. It must appear in `PREREGISTRATION.md`, not
be discovered by a reader later.

### 8.4 Open questions

1. Does sphinx actually run at a base commit? Gate 4 answers it; the PRD does not assume it.
2. Held-out split size and stratification — P3's (`docs/ROADMAP.md:439`).
3. Whether `pins` should be a resolved lockfile rather than a list. Starting with `==` pins;
   revisit if resolution proves non-reproducible.
4. Whether the 12 truncated-id instances are worth repairing. Default: **no** — record them as
   ineligible and move on. Repairing dataset corruption is not this project's job.

---

## 8.5 Effort and fit against the P1 target

**Estimate: 9–12 working days. A planning estimate, not a commitment, and nothing here has been
measured.** `docs/ROADMAP.md:203` sizes P1 at 4 weeks to **2026-08-30**; slice 1 estimated 8–10
days and consumed roughly half the phase, so this slice consumes most of what remains. **If it
overruns, the honest response is to cut N2 (rereflect) and then source A's breadth — never the
liveness check or the gates**, because those are what make the corpus worth having.

Rough shape: the format + loader breaking change ~1 day (small, but atomic and it reds the
suite); the per-task interpreter in `strict.py` ~0.5 day; the source-B miner ~2–3 days (the
two-run derivation and flake detection are most of it); the cheat-10 structural floor ~0.5 day;
source A's fetch, pool, seeded draw and the 4-gate filter ~3–4 days (gate 3's era-pinning is the
unknown); the liveness harness and ledger ~1 day; directory support in `verify` ~0.5 day; doc
updates ~0.5 day.

**The dominant runtime cost is not in that estimate**: mining source B is ~2 suite runs per
candidate commit, and a third for flake detection. That is one-time, offline and parallelisable,
but at the corpus sizes in § 8.4 Q1 it is hours of wall-clock, not minutes.

---

## 9. Out of Scope

`PREREGISTRATION.md` (unblocked, separate); the base-model bake-off and `reports/baseline/`;
relaxing `strict.py:131-140` to admit added test files (D2 — a reward-path change deserving its
own adversarial reasoning); the cheat-10 audit-hook widener (D4); any rollout, model invocation
or training (P2); the promotion gate and `check-leakage` (P3); the honest number (P4);
distillation, the morning report, the dashboard, GRPO, a second task family, closing cheat 6,
Linux portability (all post-horizon); a non-pytest execution path for django/sympy — that is a
**second reward surface**, not ingestion work, and nothing in P1 budgets for the adversarial
corpus it would require.

---

## 10. Acceptance Criteria (test-first — these are the failing tests written before the code)

1. An ingested task round-trips through `load_task` with `test_blobs` **byte-identical**;
   a non-UTF-8 blob survives (extends `tests/test_task_contract.py:84-96`).
2. A manifest missing `environment` is rejected by name; `pins` containing a non-`==` specifier
   is rejected. **Watched failing first.**
3. Source B mining over a local donor emits a valid manifest + recipe, and **a test asserts no
   network call on that path**.
4. Source A's draw is **byte-identical** across repeated runs at the same seed, and insensitive
   to input ordering.
5. **Liveness, per committed task:** empty patch → STRICT FAIL; reference patch → STRICT PASS
   with `executed == declared` and zero skips. **A deliberately vacuous task — one that passes
   with no patch — must fail the build**, and this control is watched failing first.
6. **Adversarial (required for reward-adjacent work):** a task whose `test_blobs` omit a
   `conftest.py` on the path to a held test is **rejected at ingestion** by M5's rule. The same
   task hand-authored without M5 is accepted by both verifiers — the cheat-10 differential — so
   the rule is proven to be what rejects it, not an incidental failure.
7. **Adversarial, and HARD — no escape hatch:** an ingested task whose `environment.pins` are
   removed resolves to a **different verdict** than one with them — the resolver's-clock hole,
   demonstrated rather than asserted. Determinism is achieved by resolving against a **recorded
   local package index** (two pinned states of one dependency), never the live network, so the
   test is reproducible in CI and does not itself depend on what PyPI serves. This criterion may
   not be downgraded to a documented residual: it is the one new reward-corrupting hole this
   slice found, and it was demonstrated concretely on `pallets__flask-5063` before it was
   written down.
8. Node ids are derived through `strict.py`'s own `_node_id`; a parametrised test yields a
   fully-parametrised id, asserted end-to-end.
9. A held path is never one the reference patch touches (the over-declaration guard).
10. The provenance census still admits exactly one `Task` producer
    (`tests/test_task_contract.py:232-236`), with the directory loader sited outside
    `whetstone/verify/task.py`.
11. `uv run ruff check .` and `uv run mypy src/` exit 0; CI green on `macos-latest`.

---

## 11. Grounded Facts

Per `CLAUDE.md:108-119`, unchanged and not extended: (1) RLVR is the live frontier and
reward-hacking its central documented failure mode — **METR** observed a model rewriting a timer
instead of optimizing the task; (2) **"One Token to Fool LLM-as-a-Judge"** shows up to **35%**
false positives; (3) **Karpathy (Sequoia Ascent 2026)** — the valuable RL environments *"aren't
in the frontier-lab mix."*

Everything else in this document is either cited to a file, reproduced from a command in the
2026-07-28 dig, or explicitly labelled a ceiling / estimate / UNVERIFIED.
