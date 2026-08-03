# PRD — P1 Verifier Core (task contract + strict/weak verifier)

**Slug:** `p1-verifier-core` · **Branch:** `feat/p1-verifier-core/aliz` · cut from `origin/master` @ `b8022d0`
**Written:** 2026-07-28 · **Upstream spec:** `docs/ROADMAP.md` § 4 "P1 — Task contract + verifier" (PR #2)
**Core-loop element:** ① verifiable task family + verifier — **the moat itself**

**Deliverable:** an executable, adversarially-tested reward. A task contract, a STRICT verifier
(the reward) and a WEAK verifier (measurement only), the sandbox they run in, ported verdict
semantics, a corpus of cheat fixtures, and a structural guard keeping inference libraries off the
reward path. No model is run. No training happens. No number is produced.

---

## Problem Statement

`master` @ `b8022d0` has a working toolchain and a two-flag CLI, and **nothing that grades
anything**. `src/whetstone/` is 92 lines across two files; the CLI exposes exactly `--help` and
`--version` (`src/whetstone/cli.py:4-6`). There is no task, no reward, no verdict.

Every remaining phase is blocked on this one. P2's rollouts keep "only strict-PASS rollouts"
(`docs/ROADMAP.md:189`); P3's gate promotes on `solved_new > solved_old`
(`docs/ROADMAP.md:206-210`); P4's honest number is a delta measured by "the same strict verifier"
(`docs/ROADMAP.md:268-269`). All three name a verifier that does not exist. `docs/ROADMAP.md:146`
states the stakes directly: *"This is the moat, and it is the longest phase deliberately.
Everything downstream is meaningless if the reward can be gamed."*

The deeper problem is not "we lack a test runner" — it is that **an unverified reward is worse
than no reward**. A loop trained against a gameable check produces a number that looks like
improvement and isn't, which is precisely the failure this project exists to refuse
(`CLAUDE.md` § The wedge).

**Who has this problem:** the founder, today, as the single blocking prerequisite for every
downstream phase. The ICP — an engineer who wants a model measurably better at their tasks by
morning and won't trust a gain they can't check — is not served by this slice directly, and the
PRD should not pretend otherwise. What the ICP eventually gets from it is the only reason to
believe any later number.

**Evidence it's real:** `uv run pytest -q` → 19 passed, none of which touch a reward
(`tests/` covers the CLI, packaging, version, console script, and docs). `grep -r "reward\|verdict\|verify" src/` returns nothing.

## Goals & Success Metrics

**This slice produces no model-improvement number, and none is projected here.** Its success
criteria are commands that exit 0 and artifacts that exist — the same standard
`docs/ROADMAP.md:126` sets for every phase.

The one substantive claim it establishes is a **differential**: that for each of cheats 1–5 and 7,
the weak check accepts and the strict check rejects. That differential is the evidence `N` is a
real measurement rather than a placeholder that reads zero because nothing was ever checked
(`docs/planning/roadmap-and-task-family/prd.md:277-280`).

Metrics this slice *defines but does not yet populate*:

- **`N`** — rollouts where `WEAK == PASS and STRICT == FAIL` (`docs/ROADMAP.md:84-86`). This slice
  makes `N` computable. It does not compute one, because no policy has produced a rollout.
- **The unverified rate** — the share of tasks whose verdict is `UNVERIFIED`. P3 requires it
  reported "from the first eval onward" (`docs/ROADMAP.md:227-229`); this slice is where
  `UNVERIFIED` becomes a value the code can actually return.

## User Personas & Scenarios

**The founder (today).** Runs `uv run whetstone verify --task <fixture> --patch <fixture>` and
gets a verdict grounded in a pytest exit status. Runs `uv run pytest tests/adversarial/` and sees
each cheat killed, with the one that isn't labelled as such.

**A reviewer / future contributor.** Reads `tests/adversarial/` and can answer "isn't this an LLM
judge with extra steps?" without taking anyone's word for it — the AST guard fails the build if a
model reaches the reward path.

**The ICP (not served yet).** Named for honesty: this slice ships no improvement and no report.

## Requirements

### Must-have

- **M1 — The task contract.** The fields at `docs/ROADMAP.md:42-48` as a typed, immutable
  structure: `task_id`, `source`, `repo_url`, `base_commit`, `problem_statement`,
  `fail_to_pass[]`, `pass_to_pass[]`, `test_blobs{}` (operator-held golden test contents), and
  `provenance{}`. Loadable from a file the operator controls; **never** constructible from
  policy-produced data (see M6).
- **M2 — The STRICT verifier**, as specified at `docs/ROADMAP.md:56-66`: checkout → apply patch
  (**reject if it touches any path in `test_blobs`**) → restore every operator-held test from
  golden, always, after the patch → run pytest over `fail_to_pass + pass_to_pass` → assert
  skipped-count is zero → reward is the exit status.
- **M2b — Assert the executed test set, not just the exit status.** STRICT must verify that the
  set of test node-ids pytest actually **ran** equals `fail_to_pass + pass_to_pass` exactly, and
  that each `fail_to_pass` id reports `passed`. See § D.1 — the roadmap's "skipped-count == 0"
  check does not cover deselection, and without this the reward is defeatable by a config edit
  that never touches a test file.
- **M3 — The WEAK verifier**, as at `docs/ROADMAP.md:67-72`: no path confinement, no restore,
  run whatever the policy left. **Measurement only — it never trains anything**, and the code
  must make that hard to misuse.
- **M4 — The sandbox.** `/_sandbox/<run_id>/`, network denied, writes confined, deterministic
  environment, explicit timeout. Our own minimal SBPL profile (decided below), not a vendored
  module.
- **M5 — Verdict semantics**, ported from `<sibling>/verify/verdict.py`: `UNVERIFIED` ranked **above**
  `PASS`, an empty verdict set reducing to `UNVERIFIED`, and worst-status-wins.
- **M6 — The provenance boundary as a structural test.** No callable that produces the
  operator-held test blobs may accept policy-produced data. Ported from the *mechanism* of
  `<sibling>/tests/test_invariants.py:55` — a return-type census of public producers — not from the
  module it guards.
- **M7 — The adversarial corpus.** One synthetic fixture per cheat in `docs/ROADMAP.md:104-109`,
  **plus cheat 7 found in this PRD's self-critique** (§ D.1). Cheats 1–5 and 7 assert **STRICT
  rejects AND WEAK accepts**. Cheat 6 asserts accepted by both, named and documented as the
  expected residual.
- **M8 — The AST inference guard**, scoped to the reward-path package, honouring **three** porting
  traps (two from `docs/ROADMAP.md:166-174`, one found in this dig), with **two** anti-vacuity
  controls.
- **M9 — `whetstone verify`**, emitting a verdict. Requires restructuring `cli.py` to use
  subparsers.
- **M10 — Determinism.** Same task + same patch + same seed → identical verdict.

### Should-have

- **S1 —** A CI step asserting `sandbox-exec` is available and actually denies the network on the
  runner, mirroring the existing mlx step's standard (`ci.yml:36-44`: assert the thing works, not
  that installation exited 0).
- **S2 —** The three committed-document corrections this dig found (§ Technical Considerations E).
- **S3 —** `UNVERIFIED` reachable and tested — a task whose sandbox fails is not a FAIL.

### Nice-to-have

- **N1 —** A `--json` output mode on `verify`, since P2's ledger will want machine-readable
  verdicts.
- **N2 —** The verdict's `observed`/`expected` fields carrying the pytest summary line, so a
  human reading a FAIL sees why without re-running.

## Technical Considerations

### A. Where the reward path lives, and what the guard watches

```
src/whetstone/verify/          ← THE REWARD PATH. GUARDED_ROOTS = [this directory]
├── task.py                    M1  the task contract + its operator-file loader
├── verdict.py                 M5  ported Status / Verdict / reduce
├── sandbox.py                 M4  SBPL profile + confined subprocess execution
├── strict.py                  M2  the reward
└── weak.py                    M3  measurement only
```

Scoping the guard to `verify/` rather than the whole tree is deliberate and load-bearing:
`mlx-lm` is a legitimate optional dependency of this project (`pyproject.toml:25-29`) and will be
imported by the rollout code in P2. A tree-wide ban would be false the moment P2 lands, and a
guard that must be weakened is a guard that gets weakened. `docs/ROADMAP.md:159-160` requires
exactly this scoping.

**This package must stay stdlib-only.** `pyproject.toml:17-20` already commits to it: *"Zero
runtime dependencies … nothing on the future reward path may pull in an inference library."*

### B. The sandbox — decided: our own minimal profile

The dig established that the sibling project's `sandbox/seatbelt.py` **is** separable from the declined replay
substrate (it imports only stdlib, one exception class, and an optional `TraceWriter`; the
dependency runs replay → sandbox, never the reverse). Vendoring it was viable and was **not
chosen**: 417 lines carrying an `allow-ports` mode, a closed `NetworkPolicy` enum, and a
denial-from-stderr parser this slice does not use, all of which would have to satisfy
`mypy --strict`. The reward needs one mode — deny everything.

```
(version 1)
(allow default)
(deny network*)
(deny file-write*)
(allow file-write* (subpath "<escaped /_sandbox/run_id>"))
```

then `subprocess.run(["/usr/bin/sandbox-exec", "-f", profile, sys.executable, "-m", "pytest", …])`,
and the reward is `completed.returncode`.

**Verified by spike on this machine, 2026-07-28** — `/usr/bin/sandbox-exec` exists; under this
profile a probe reported `NET: denied (PermissionError)`, in-scope write allowed, out-of-scope
write denied.

**Three properties this design must carry, each for a stated reason:**

1. **SBPL escaping is mandatory.** A sandbox path containing `"` would close the policy literal
   early and let the remainder parse as SBPL — a policy injection into the boundary that enforces
   the policy. The sibling project guards this at `seatbelt.py:87-95` (`_quote`); we implement the equivalent.
   Not optional because our profile is smaller.
2. **Reads are NOT confined, and nothing may claim otherwise.** The spike confirmed a sandboxed
   process reads outside its scope freely; the sibling project documents it as a property of the profile shape
   (`seatbelt.py:363-366`). See § D.
3. **Timeout and crash reduce to `UNVERIFIED`, never `FAIL`.** A task the sandbox could not run
   is one we could not check, not one the patch got wrong. Collapsing it to FAIL would understate
   the policy and, worse, would hide sandbox unreliability that P3 needs to see
   (`docs/ROADMAP.md:227-229`). This is the ported `_RANK` doing its job at the level of a single
   task.

**Determinism (M10)** is ours to design — the sibling project's `run()` pins no environment. The environment
handed to pytest is fixed and explicit: `PYTHONHASHSEED=0`, a pinned `TMPDIR` inside the sandbox,
`PYTHONDONTWRITEBYTECODE=1`, and pytest invoked with cache and plugin autoloading disabled so a
stray installed plugin cannot reorder collection. What is *not* claimed: determinism of the
repository under test. A task whose own tests are timing-dependent is a flaky task, and the honest
handling is the retry-then-`UNVERIFIED` policy P3 specifies, not a pretence that the sandbox
removed the flakiness.

### C. The AST guard — three traps, two controls

Verified against `<sibling>/tests/test_verify_zero_llm.py`:

| # | Trap | Evidence | Fix |
|---|---|---|---|
| 1 | First-party gate hardcodes `if root == "<the sibling package name>"` | `:114-121`, quoted verbatim in `understanding.md` § 3 | Use `"whetstone"`; assert the predicate fires |
| 2 | `_INFERENCE_CLIENTS` has no `mlx`, `mlx_lm`, `peft`, `accelerate` | 29-entry list read in full; those four absent | Extend explicitly — the inherited list has a hole shaped like our own stack |
| 3 | **Relative imports are invisible** — `if node.level == 0` | `:105-111` | Resolve relative imports to absolute dotted paths from the file's package position |

**Trap 3 is new** — it appears in no committed document, and it matters more for us than for
The sibling project. Our reward path is one package whose modules will naturally import each other relatively;
`from .judge import score` inside `verify/` records nothing under the sibling project's walk.

**Two anti-vacuity controls**, because the sibling project ships only the first:

- **Control A** (ported): the walk observes real imports the guarded package actually makes.
  The sibling project's version at `:156-175`.
- **Control B** (new): `_is_inference_import("whetstone.judge")` returns `True`. The sibling project's control
  asserts the walk sees *imports*, never that the first-party predicate is *live* — so trap 1 could
  land silently with the sibling project's own control still green.

`ast.walk` (`:105`) already catches function-local imports, so indentation is not a bypass.

### D. Reward-hacking surface — one new cheat, and a sharpened residual

The enumeration is `docs/ROADMAP.md:104-109` and is not re-litigated. Cheats 1–5 are killed by the
provenance boundary (patch rejected if it touches a test path; tests restored from golden *after*
the patch; skipped-count asserted zero; exit status read from the runner). Each gets a fixture
asserting **both** halves of the differential.

#### D.1 — Cheat 7: change which tests run, without touching a test file

**Found in this PRD's self-critique; it is not in the roadmap's table, and the roadmap's stated
defence does not cover it.**

Cheat 5's defence is *"Boundary, plus skipped-test count asserted zero"* (`docs/ROADMAP.md:108`).
But **pytest deselection is not skipping.** A patch may edit `pyproject.toml`'s
`[tool.pytest.ini_options] addopts` — or `pytest.ini`, `tox.ini`, `setup.cfg` — to add `-k`, `-m`,
or `--deselect`, removing the failing test from the run entirely. Those are **configuration files,
not test paths**: they are not in `test_blobs`, so the patch survives the path-rejection check and
the golden restore leaves them untouched. The run then exits 0 reporting **zero skipped**. The
same shape is reachable via a planted `sitecustomize.py` or a `.pth` file, which execute at
interpreter startup inside the sandbox.

This defeats the reward while satisfying every check the roadmap lists, and it is cheap for a
policy to stumble into — narrowing a test selection is an ordinary thing to do to a repo.

**Defence (M2b): assert the executed set, not the exit status alone.** STRICT parses the machine-
readable report of what pytest ran and requires the executed node-id set to equal
`fail_to_pass + pass_to_pass` exactly, with every `fail_to_pass` id reporting `passed`. An exit
status answers *"did anything fail?"*; it cannot answer *"were these the tests?"* — and the second
question is the one the reward actually depends on. Defence in depth, not instead: pytest is also
invoked with plugin autoloading disabled and an explicit config path, so the ambient config is not
trusted in the first place.

This becomes **cheat fixture 7** in the corpus, asserting the differential like cheats 1–5: WEAK
accepts the deselecting patch, STRICT rejects it.

**Cheat 6 (special-case the known input) remains a residual, and this dig sharpens why.** The
sandbox confines *writes*, not *reads*, and the golden tests are restored into the sandbox before
pytest runs — so the code under test can read the assertions it must satisfy. Precisely:

> **The verifier guarantees that the unmodified operator-held tests genuinely passed. It does not
> guarantee that the fix generalises, and it does not make the policy blind to the tests.**

`docs/ROADMAP.md:116-118` states the first half. The second half is new here and belongs in the
roadmap. Mitigations remain `pass_to_pass` and held-out evaluation; closing it (held-out test
variants, mutation testing) stays post-horizon and is **not** claimed.

### E. Corrections to committed documents (confirmed with the user)

1. `docs/ROADMAP.md` § 7's "Taken" table (`:303-311`) gains a sandbox row — it lists no sandbox
   module while `:54` requires one.
2. `docs/ROADMAP.md:166-174` gains porting trap 3.
3. `docs/planning/roadmap-and-task-family/prd.md:58` is corrected: the Seatbelt half of *"work
   natively; no porting phase required"* holds, the `clonefile` snapshot half does not —
   `<sibling>/snapshot/` is part of the replay substrate § 7 declines.
4. **`docs/ROADMAP.md`'s cheat table (`:104-109`) gains cheat 7**, and cheat 5's defence column is
   corrected — "skipped-test count asserted zero" does not cover deselection (§ D.1). The
   verifier spec at `:56-66` gains the executed-set assertion. This is the substantive correction
   of the four: the others are documentation drift, this one was a hole in the reward.

### F. CLI exit codes

`cli.py:23` already binds `USAGE_ERROR = 2`. The verdict codes must not collide with it, because
"the eval could not be completed" and "you typed the command wrong" are different facts and the
whole point of the third verdict is that it stays legible:

| Outcome | Code |
|---|---|
| `PASS` | 0 |
| `FAIL` | 1 |
| usage error (existing) | 2 |
| `UNVERIFIED` | 3 |

`UNVERIFIED` deliberately does **not** get 0. A caller that checks only `rc == 0` must never read
an unverified result as a win — the honesty contract has to hold at the process boundary too, not
only inside the reduction.

### G. Guardrails as rejection tests

| Guardrail (`CLAUDE.md`) | How this slice visibly passes |
|---|---|
| Reward verifiable, never a judge | Reward is `completed.returncode` from pytest. Enforced by M8's AST guard, not by convention |
| Never regress; `UNVERIFIED` ≠ win | M5's ranked reduction; § B.3 makes timeout/crash `UNVERIFIED`, and S3 tests it |
| Local / BYOK / private | Nothing leaves the box. The verifier *denies* the network to the process under test. No model is invoked at all |
| Gets better as base models improve | The verifier is base-agnostic; it grades patches, whatever produced them |
| Ship the honest number even if modest | No number is produced here; cheat 6 is documented as unfixed rather than hidden |
| No frontier base-model training | Nothing is trained. Nothing is even inferred |

### H. Integration points

| File | Change |
|---|---|
| `src/whetstone/cli.py` | Restructure `build_parser()` (`:28-37`) for subparsers; `main()` (`:51-72`) dispatches instead of always returning `USAGE_ERROR`. Preserve the bare-invocation contract (`:56-62`) and the "commands appear only when something stands behind them" rule (`:5-6`) |
| `src/whetstone/verify/` | New package (§ A) |
| `tests/adversarial/` | New. Auto-collected — `pyproject.toml:53` sets `testpaths = ["tests"]` |
| `tests/test_no_inference_on_reward_path.py` | New |
| `.github/workflows/ci.yml` | S1's sandbox assertion step |
| `docs/ROADMAP.md`, `docs/planning/roadmap-and-task-family/prd.md` | § E corrections |

`pyproject.toml` and `.gitignore` are untouched — `/_sandbox/` is already pre-declared
(`.gitignore:23`), and the verifier adds no dependency.

**House style** (from `tests/test_cli.py`): module docstrings naming *the failure this prevents*;
sentence-shaped test names; assertions on both a return code and observable output; anti-vacuity
controls documented as *"watched failing … before being trusted"* (`:52`). mypy is strict over
`src/` only; ruff is `E,F,I,UP,B,SIM,RUF` at 100 columns.

## Data Model — the task contract

```
Task
  task_id            str                      stable identifier
  source             "public" | "private"     provenance only; the contract is identical
  repo_url           str
  base_commit        str                      the known-broken commit
  problem_statement  str                      what the policy is asked to fix
  fail_to_pass       tuple[str, ...]          must go green
  pass_to_pass       tuple[str, ...]          must stay green
  test_blobs         Mapping[str, bytes]      OPERATOR-HELD. path → golden contents
  provenance         Mapping[str, str]        how obtained, and when
```

`test_blobs` is the operator's artifact and the whole boundary: it is both the **restore source**
(step 3 of STRICT) and the **rejection set** (step 2's path check). Bytes, not `str` — a path
decoded to text reintroduces the unicode-normalisation trap the sibling project avoids
(`invariants.py:18-24`), and the byte-prefix comparison must run on the same bytes throughout.

Frozen and loaded only from an operator-controlled file. M6's test asserts structurally that no
public callable returning a `Task` accepts a patch, a diff, or a rollout.

## Risks & Open Questions

| Risk | Severity | Mitigation |
|---|---|---|
| **`sandbox-exec` unavailable or restricted on `macos-latest`** — the spike proves this machine, not CI | **High** | S1 asserts it in CI explicitly. If it fails, the honest response is a loudly-skipped suite with a named marker, never a silent green. Decide on evidence, not in advance |
| **`sandbox-exec` is deprecated by Apple** | Medium | the sibling project depends on it too. No supported macOS replacement exists without Docker. Isolate behind `sandbox.py` so the mechanism is swappable; do not design it into five call sites |
| **Cheat 6 residual**, sharpened by read-non-confinement (§ D) | Medium | Named, documented, tested-as-residual. Closing it is post-horizon and not claimed |
| **A vacuously-green adversarial suite** — STRICT rejecting for the wrong reason reads as proof | **High** | Every cheat fixture asserts both halves (STRICT rejects AND WEAK accepts). Each control is watched failing before being trusted, per house style |
| **Env provisioning for real SWE-bench instances is unsolved and unestimated** — the sibling project's pool carries no `FAIL_TO_PASS`/`PASS_TO_PASS`/test patch, and its `eval/` never executes an instance | **High, deferred** | Out of scope here by decision. Recorded so it is discovered in the ingestion slice, not in P2 |
| **Cheat 7 — deselection via config (§ D.1)** — defeats the reward while passing every check the roadmap lists | **High** | M2b asserts the executed node-id set; fixture 7 proves the differential; plugin autoload disabled and config path explicit |
| **An eighth cheat nobody enumerated.** Cheat 7 was found by critiquing this PRD, not by the roadmap's enumeration — which is evidence the table is a living list, not a closed one | Medium | Treat the corpus as append-only and the enumeration as provisional. Every future cheat found gets a fixture before a fix. Do not describe the table as exhaustive anywhere |
| Test-order/plugin nondeterminism defeating M10 | Low | Pinned env, autoload disabled, cache disabled (§ B) |

**Open questions carried forward:**

- Whether `whetstone verify` should accept a task *directory* or a single manifest file — deferred
  to the ingestion slice, which owns the on-disk task format.
- The retry count *R* (`docs/ROADMAP.md:371`) stays P3's, to be set from an observed unverified
  rate rather than guessed here.
- Whether `Verdict` keeps the sibling project's `axis` field. **Provisional decision: drop it, keep `kind`** —
  The sibling project's axes ("A1"/"A2"/"A3") describe a taxonomy Whetstone does not have, and an always-constant
  field is a lie about structure. Revisit if a second verdict axis ever appears.

## Effort and fit against the P1 target

**Estimate: 8–10 working days. A planning estimate, not a commitment, and nothing here has been
measured.** `docs/ROADMAP.md:144` sizes all of P1 at 4 weeks to **2026-08-30**; this slice takes 3
of its 6 exit criteria and, on this estimate, leaves roughly half the phase budget for the three
deferred ones — of which `tasks/` ingestion carries the unestimated environment-provisioning work
identified in `understanding.md` § 5.2. **That is the schedule risk in P1, and it sits in the
deferred slice rather than this one.**

Rough shape: the sandbox and determinism ~2 days (the profile is small; pinning the environment
and proving denial is the work); task contract and verdict port ~1 day (both are largely lifting);
STRICT + WEAK + the executed-set assertion ~2–3 days; the 7-fixture adversarial corpus ~2 days
(each fixture must be watched failing before it is trusted, which is most of the cost); the AST
guard with three traps and two controls ~1 day; CLI restructuring and doc corrections ~1 day.

## Acceptance Criteria (test-first — these are the failing tests written before the code)

1. `uv run pytest tests/adversarial/` exits 0, with one fixture per cheat: for cheats 1–5 **and 7**,
   **STRICT rejects AND WEAK accepts**; for cheat 6, both accept, asserted as the documented
   residual.
1b. **Cheat 7 specifically** (§ D.1): a patch that touches no test path but adds `-k`/`--deselect`
   to `[tool.pytest.ini_options] addopts` is rejected by STRICT — and the test asserts the
   rejection reason is *the executed set did not match*, not an incidental failure, so the check
   cannot pass for the wrong reason.
2. `uv run pytest tests/test_no_inference_on_reward_path.py` exits 0, with **both** anti-vacuity
   controls: the walk observes real imports, **and** `_is_inference_import("whetstone.judge")` is
   `True`.
3. The guard resolves relative imports — a planted `from .judge import x` inside the reward path
   is caught (trap 3).
4. `uv run whetstone verify --task <fixture> --patch <fixture>` emits a verdict and returns the
   exit code mapped in § F (PASS 0 / FAIL 1 / UNVERIFIED 3, never colliding with the existing
   `USAGE_ERROR = 2`); `UNVERIFIED` is never rendered as `PASS` and never exits 0.
5. **Determinism:** same task + patch + seed → identical verdict, asserted over repeated runs.
6. **The reduction's honesty contract:** an empty verdict set reduces to `UNVERIFIED`; a set of
   {PASS, UNVERIFIED} reduces to `UNVERIFIED`, not `PASS`.
7. **The provenance boundary:** a structural test asserting no public callable returning a `Task`
   accepts policy-produced data.
8. **The sandbox denies the network** — a fixture whose test attempts a connection is denied, and
   the denial is observed rather than assumed.
9. **A sandbox failure reduces to `UNVERIFIED`, not `FAIL`.**
10. **A patch touching a path in `test_blobs` is rejected by STRICT before any test runs** — the
    rejection is not merely "the tests failed afterwards".
11. `uv run ruff check .` and `uv run mypy src/` exit 0; CI green.

## Out of Scope

`tasks/` ingestion from either source and the on-disk task format; the base-model bake-off and
`reports/baseline/`; `PREREGISTRATION.md`; per-instance environment provisioning for real
SWE-bench repos; any rollout, any model invocation, any training (P2); the promotion gate (P3);
the honest number (P4); distillation, the morning report, the dashboard, GRPO, a second task
family, closing cheat 6, and Linux portability (all post-horizon). Also out of scope: the
`CHANGELOG.md` 0.1.0-without-a-tag discrepancy (`understanding.md` § 8).

## Grounded Facts

Per `CLAUDE.md:108-119`, unchanged and not extended: (1) RLVR is the live frontier and
reward-hacking its central documented failure mode — **METR** observed a model rewriting a timer
instead of optimizing the task; (2) **"One Token to Fool LLM-as-a-Judge"** shows up to **35%**
false positives; (3) **Karpathy (Sequoia Ascent 2026)** — the valuable RL environments *"aren't in
the frontier-lab mix."*

Every other figure in this document is either a line count, a file citation, or a command output
taken from this repository or the sibling project's on 2026-07-28. **No performance figure appears here, because
none has been measured.**
