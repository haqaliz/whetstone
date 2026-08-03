# Whetstone Roadmap

**Horizon:** 2026-07-27 → 2026-10-25 (~13 weeks). **Written:** 2026-07-26.
**Ends at:** the first honest number. Distillation, the morning report, and the dashboard
are post-horizon and named as such.

> All durations are **planning estimates**, not commitments or measurements. No performance
> figure appears anywhere in this document: the bake-off's figures live in `reports/baseline/`,
> which is their only home. See § Grounded facts.

---

## 1. The task family

**Python repo bug-fixing, rewarded by operator-held test execution.**

A task is a repository at a known-broken commit plus a set of tests that currently fail. The
policy produces a patch. The reward is whether those tests pass — and whether the tests that
already passed still do.

**Why its end state is deterministically checkable:** the reward is a **process exit
status**. There is no comparison to a reference answer, no similarity score, and no model
opinion anywhere on the reward path. The same patch against the same commit with the same
seed produces the same verdict, every time. This is the strongest form of the
observed-vs-claimed comparison `CLAUDE.md` requires: the policy *claims* it fixed the bug,
and we *observe* the test runner's exit status against tests the policy could not touch.

### Two sources, one family

Per `CLAUDE.md` #5 this is **one** family — one task contract, one verifier, one reward.
Only provenance differs:

| Source | Role | Property |
|---|---|---|
| **A — public** (SWE-bench-Lite, pure-Python subset) | comparability | Externally recognisable, but **contamination-exposed**: widely trained on, so an open base may have memorised fixes |
| **B — private** (mined from the user's own repos: a commit that turns a failing test green is one task) | the headline | Uncontaminated, never leaves the box, and on-thesis for *"point it at your tasks"* |

Both are always reported. The headline is **pre-registered** (§ 6).

### Task contract

```
task_id, source, repo_url, base_commit,
environment{}         # nominated interpreter, exact `==` pins, and import_roots
problem_statement,
fail_to_pass[], pass_to_pass[],
test_blobs{}          # operator-held; the golden copy of every test file
provenance{}          # how this task was obtained, and when
```

`environment` is not decoration on the contract — it is where two observed reward corruptions
were closed, and both are recorded in § 3. The pins stop the dependency resolver's clock from
deciding the verdict; `import_roots` stops a checkout *outside* the run from deciding it.
Neither is inferable at verification time, which is why the manifest has to carry them.

---

## 2. The verifier

Runs in `/_sandbox/<run_id>/`, no network, fixed seed.

```
STRICT (the reward)
  1. checkout base_commit into the sandbox
  2. apply the policy's patch
       └── REJECT the rollout if it touches any path in test_blobs
  3. restore every operator-held test from golden  — always, after the patch
  4. run pytest over fail_to_pass + pass_to_pass
       └── assert skipped-test count == 0
       └── assert the EXECUTED node-id set == fail_to_pass + pass_to_pass, exactly,
           and that every fail_to_pass id reports `passed`
  5. reward := exit status, folded with the assertions above

WEAK (measurement only — never trains anything)
  1. checkout base_commit
  2. apply the patch, no path confinement
  3. no restore — whatever tests the policy left are what run
  4. run pytest
  5. verdict := exit status
```

**Step 4's executed-set assertion, added 2026-07-28.** It is not a refinement of the
skipped-count check; it closes a hole that check never covered (cheat 7 below). An exit status
answers *"did anything fail?"* — it cannot answer *"were these the tests?"*, and the reward
rests on the second question. **Deselection is not skipping:** `-k`, `-m` and `--deselect`
remove tests from a run without producing a single skip, and they arrive from
`pyproject.toml` / `pytest.ini` / `setup.cfg` or from a root `conftest.py` — *configuration,
not test files*, so none of them are in `test_blobs`, and such a patch survives step 2's
rejection and step 3's restore untouched, leaves the skipped count at zero, and exits 0 with
the failing test simply absent.

The executed set is read from pytest's own machine-readable report, never from its summary
line. Three further pins make the config door not the only lock: pytest is invoked with an
explicit `-c` at a config that configures nothing (so a patched `pyproject.toml` is never
read), with `-p no:cacheprovider`, and with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` in the pinned
environment. They are defence in depth — the assertion is the defence.

### The provenance boundary

The tests are the **operator's** artifact; the patch is the **policy's** evidence, and they
never mix. This is the sibling project's `verify/invariants.py` discipline applied to code: policy is
loaded only from the operator-held blob, restored *after* the patch lands, so nothing the
policy wrote can influence what grades it. Without this boundary the policy authors its own
reward.

### `N` — reward-hacking attempts caught & rejected

```
N := count(rollouts where WEAK == PASS and STRICT == FAIL)
```

Reported verbatim as **"N rollouts a weaker check would have scored as wins."** That is a
claim about what the strictness caught, **not** about the policy's intent — a patch that
edited a genuinely-buggy test in good faith still counts. The framing is deliberate:
intent is not observable, so we do not claim to measure it.

`N` is meaningless without a **baseline `N`** (§ 5).

---

## 3. The cheat surface — and its honest residuals

`prd-interview` requires treating *"it can't cheat"* as an unfinished answer. The
enumeration, **which is provisional and append-only rather than complete** (see the note
below it):

| # | Cheat | Defeated by | Status |
|---|---|---|---|
| 1 | Edit the test file to delete or weaken the failing assertion | Patch rejected if it touches a test path; tests restored from golden post-patch | **Killed** |
| 2 | Weaken an assert in place (`assertEqual` → `assertTrue`) | Same boundary | **Killed** |
| 3 | Mutate a fixture or `conftest.py` | Same boundary — **but only for the files the manifest actually declares.** "Fixtures are operator-held" is a statement about task authoring, not about the verifier; see cheat 10 | **Killed when declared** |
| 4 | `sys.exit(0)` / `os._exit(0)` before assertions run | Exit status read from the runner; `pass_to_pass` must also hold; and a run with no report behind it is `UNVERIFIED`, never `PASS` | **Killed** |
| 5 | Monkeypatch the runner, or register a `conftest` plugin that skips | Boundary, plus skipped-test count asserted zero. **That count does not cover deselection** — deselected tests produce no skip at all, which is cheat 7 | **Killed** |
| 6 | **Special-case the known input** — hardcode the expected output instead of fixing the bug | *Partially.* Sits entirely inside the boundary. | **RESIDUAL** |
| 7 | Remove the failing test from the run without skipping it — `-k` / `-m` / `--deselect` via `addopts` in `pyproject.toml`, `pytest.ini` or `setup.cfg`, or via a root `conftest.py` | The executed node-id set asserted equal to `fail_to_pass + pass_to_pass` (§ 2), plus the explicit empty `-c` config, `-p no:cacheprovider` and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` | **Killed** |
| 8 | Rename the operator's test aside and leave a passing stub at its node id | The post-apply footprint is taken from `git status`, where the rename is a deletion plus an untracked file. `git apply --numstat` reports a rename by its **destination only**, so the pre-apply check alone would not see the source path | **Killed** |
| 9 | Address the operator's test by another casing (`Tests/test_addition.py`) — macOS's default volume is case-insensitive, so the path reaches the held file while comparing unequal to it | Held paths compared case-folded as well as exactly | **Killed** |
| 10 | **Mutate a file a held test depends on that the manifest never declared** — e.g. a `conftest.py` outside `test_blobs` | *Narrowed at ingestion, not eliminated.* The boundary is exactly as wide as `test_blobs`, and no set-comparison can infer an omission; minting now declares the `conftest.py` floor, which is a wider manifest rather than a defence in the reward path | **RESIDUAL** |

> **Corrected and extended 2026-07-28, from building the verifier (P1 slice 1).** Rows 7–10
> and the qualifications on rows 3 and 5 postdate the original six-row table. Cheat 7 was found
> in the P1 PRD's self-critique, 8 and 9 while implementing the patch-scope check, and 10 while
> writing the corpus — **four of the ten entries arrived after the table read as an enumeration
> of the surface.** The honest conclusion is not that the list is now finished; it is that a
> cheat surface is discovered, never enumerated up front. Treat it as append-only and never
> describe it as exhaustive. Every row is backed by a fixture in
> `tests/adversarial/test_cheats.py`, which asserts **both** halves of the differential (STRICT
> rejects *and* WEAK accepts) and asserts *which* sub-verdict fired, so a rejection for an
> unrelated reason cannot read as a defence.

**Two of the ten get through, and neither is buried.**

**Cheat 6 is not solved, and this document will not pretend otherwise.** A patch that
special-cases the exact test input satisfies every structural check above. It is mitigated —
`pass_to_pass` catches the crude version, and held-out evaluation means a policy that only
memorises training tasks shows no held-out gain — but it is **not eliminated**. The sandbox
does not narrow it: it confines what the run can **write**, never what it can **read**
(`file-read*` is allowed wholesale, observed on this machine 2026-07-28 —
`docs/planning/_card/understanding.md` § 2c), and the golden tests are restored *into* the
checkout before pytest runs. The information needed to special-case is available to the policy
**by construction**; no claim of read-blindness may be made anywhere.

**Cheat 10 is a second residual, found in P1 and reported rather than patched.** Row 3's
original defence — *"fixtures are operator-held"* — described how a task ought to be authored,
not anything the verifier enforces. If a held test reads its expected value from a
`conftest.py` the manifest does not list in `test_blobs`, that file is outside the boundary: the
patch touches no held path, the held tests are restored unchanged, the declared tests run, and
the failing test passes against a fixture the policy rewrote. **The reward is paid on a bug that
was never fixed.** Nothing in the verifier can infer the omission, because *"which files does
this test depend on"* is not a question a set-comparison can answer. Narrowing it belongs to
**task ingestion** — declaring a held test's transitive dependencies when the task is minted.

**It has since been narrowed there, and the row still says RESIDUAL on purpose.** Minting now
declares, in `test_blobs`, every `conftest.py` from the repository root down to each held test's
directory (`src/whetstone/tasks/held.py`), read at the **parent** commit — the tree STRICT checks
out — and a held set that omits one is refused by name. That closes the specific shape the
fixture uses, and it is structural: a path, not an import walk, so there is nothing to be talked
out of. What it does **not** do is make the manifest provably complete. Measured while building
it: **~22% of donor A's mintable commits (49 of 224) also touch a non-`.py` file** — a JSON
fixture, a golden output, a CSV — which no conftest rule and no import walk would ever see, and
which a correct fix legitimately changes. So the cheat survives in exactly its general form, the
corpus keeps it as accepted by both verifiers, and the status cell above must not be downgraded
on the strength of a narrower manifest. A wider boundary is not a defence in the reward path.

Stated precisely, with both bounds this document previously left out:

> **The verifier guarantees that the operator-held tests, as the operator wrote them, genuinely
> ran and genuinely passed.** It does **not** guarantee that the fix generalises (cheat 6); the
> guarantee extends only as far as the manifest is complete (cheat 10); and the sandbox confines
> what the run can write, **not** what it can read.

Closing either residual — held-out test variants and mutation testing for cheat 6, declaring a
held test's transitive dependencies at ingestion for cheat 10 — is post-horizon and is not
claimed here.

### Appended 2026-07-28, from building the task format (P1 slice 2): the resolver's clock

**A reward can be corrupted with no adversary in the room.** The ten above are things a policy
does. This is a thing a **calendar** does, and it lands on the same reward in the same place, so
it is recorded here rather than left in a planning document where a reader of this section would
never meet it.

**The evidence, which is an observation and not a worry.** SWE-bench's `pallets__flask-5063`
declares `click>=8.0` with no upper bound. Resolved on 2026-07-28 that is `click 8.4.2`, which
has removed `CliRunner(mix_stderr=)`; four of the task's `pass_to_pass` tests then failed and
**STRICT returned FAIL for a patch that was correct** — a false FAIL manufactured entirely by the
resolution date. Pinning `click==8.1.3` turned the same task, the same patch and the same
verifier fully green. Nothing about that verdict was execution-grounded: it was grounded in what
an index served that morning, and it would have flipped back on its own.

**It is closed, and the closure is demonstrated rather than asserted.** A task manifest now
carries a required `environment` — a nominated interpreter and exact `==` pins, with ranges
refused at load — so the dependency set is part of the task rather than a side effect of running
it. `tests/test_environment_pins.py` is the proof: one task and one correct patch reach **PASS**
pinned and **FAIL** unpinned, resolved offline against a committed two-version index, with the
offline flags asserted from the argv actually invoked. A test that reached a live index to prove
this would be self-refuting, since its own result would depend on the thing it is guarding.

**Deliberately prose, and not an eleventh row.** The table's fourth column reports a
*differential* — STRICT rejects while WEAK accepts — and every row is backed by a fixture in
`tests/adversarial/` that asserts both halves. This has no differential: both verifiers were
equally wrong, in the same direction, and the fix is in the task contract rather than in the
reward path. Scored in the table's vocabulary it could only be misread, and a corpus entry for it
would be a cheat fixture with nobody cheating. The append-only note above says the surface is
discovered rather than enumerated; this is the sharper version of that lesson — **it is not only
policies who discover it.**

### Appended 2026-07-28, from mining the first real donor: a verdict decided outside the run

**The second one of these, and it is worse than the first.** The resolver's clock produced a
false **FAIL** — a correct patch marked wrong, which is expensive but self-announcing. This one
produced a false **PASS**: a task that passed **with no patch applied at all**. A policy that
submitted nothing would have been paid, and every number computed from that corpus would have
been a number about a directory nobody was grading.

**The evidence, which is an observation and not a worry.** `donor A` is a `src`-layout project:
its tests say `import <pkg>`, so the name is answered by whatever the interpreter's `sys.path`
offers. The miner provisioned its venv with `uv sync --frozen --project <checkout>`, which
installs the project **editable** — rooted at the *provisioning* checkout, a different directory
from the one the reward applies patches to. `uv pip freeze` reported `-e file:///…/donor`, and
`import <pkg>.self_heal` resolved to that tree's `src/`, not to the run's. The checkout under
verification was therefore inert: nothing in it was ever imported, and the verdict came from a
directory outside the run. Two already-minted tasks were deleted rather than kept — they are
survivors of the defect, not a sample of a corpus.

**Why the ten-cheat corpus did not catch it.** Every fixture repository was flat — `calc.py`
beside `tests/` — and none was installed into a venv. A flat layout under `python -m pytest`
puts the code under test at `sys.path[0]`, where nothing can shadow it. **The defence was the
shape of the fixtures, not anything the verifier did**, and no test could tell the difference.
That is the transferable lesson here: a corpus proves what its fixtures can express, and a
property every fixture satisfies by accident is a property nothing is testing.

**It is closed at both ends, and the closure is demonstrated rather than asserted.** The
manifest's `environment` now also carries `import_roots`, the repository-relative directories
holding the code under test; STRICT puts them, resolved against **this** run's checkout, on
`PYTHONPATH`, which precedes `site-packages` and therefore shadows any residual install. At the
other end, provisioning passes `--no-install-project`, so the venv carries dependencies only and
there is no copy of the project anywhere for a verdict to leak into; the miner now provisions and
derives in **one** checkout rather than two. A donor whose layout cannot be read from its build
configuration is **rejected by name** rather than guessed at — a wrong import root does not fail
loudly, it fails by passing. `tests/adversarial/test_inert_checkout.py` is the proof: a
`src`-layout task, a venv with a *fixed* copy of the project installed outside the checkout, and
the reward refusing to pay for a run with no patch — asserted alongside the mirror, where the same
task under its real reference patch still passes.

**Prose again, and not an eleventh row, for the same reason as the entry above.** Nobody authors
this: the submission that collects the reward is the empty one, so there is no adversary and no
differential to report — WEAK is fooled identically. It lives in `tests/adversarial/` rather than
among the unit tests because it is a reward-integrity property, and outside `CHEATS` because it
is not a cheat.

---

## 4. Phases

Ordered per the core loop: **① verifier → ② loop → ③ gate → ④ report.** Every exit
criterion below is a command that exits 0 or an artifact that exists — never a narrative
judgement.

### P0 — Scaffold · est. 1 week · target 2026-08-02

The repo currently contains zero lines of executable code. Nothing can be test-first until
a test runner exists.

**Exit criteria**
- `uv run pytest` exits 0 with at least one non-trivial test
- `uv run whetstone --help` exits 0
- `uv run ruff check .` and `uv run mypy src/` exit 0
- `LICENSE` exists (Apache-2.0 — `CLAUDE.md:93` states it; the file is absent today)
- CI workflow green on `master`

**Pivot signal:** none credible.

---

### P1 — Task contract + verifier · est. 4 weeks · target 2026-08-30

**This is the moat, and it is the longest phase deliberately.** Everything downstream is
meaningless if the reward can be gamed.

Includes: the task contract; the strict and weak verifiers; the sandbox; the sibling project's verdict
semantics ported (§ 7); the adversarial corpus; task ingestion for both sources; and the
base-model bake-off — run **against the working verifier**, not on paper.

**Exit criteria**
- `uv run pytest tests/adversarial/` exits 0, where the suite asserts, per cheat fixture:
  - the killed cheats (§ 3 — 1–5 and 7–9): **STRICT rejects AND WEAK accepts** — proving the
    differential is real rather than vacuously zero — *and* which sub-verdict fired, so a
    rejection for an unrelated reason cannot pass for a defence
  - the residuals (§ 3 — cheats 6 and 10): accepted by both, asserted as *documented, expected*
    residuals so a future reader cannot mistake silence for coverage
- `uv run pytest tests/test_no_inference_on_reward_path.py` exits 0 — an AST walk over every
  module on the reward path fails the build if any inference library is imported. The walk is
  **scoped to the reward-path packages**, not the whole tree, so it stays true once `mlx-lm`
  is legitimately installed elsewhere; it carries an anti-vacuity control asserting the walk
  actually sees imports (§ 7). As of P1 slice 2 that scope is `src/whetstone/verify/` **and**
  `src/whetstone/tasks/`: ingestion authors `test_blobs`, which is the boundary the reward path
  enforces, so a model choosing what goes in it would be deciding one step removed what counts
  as cheating. Widening a scoped guard is where it can go quietly dead, so each root is asserted
  to contribute modules and the control names an import only the second root makes. **Three porting traps, verified against the sibling project's source and each
  fatal to the guard if missed** (the third added 2026-07-28, from the P1 dig):
  - The sibling project's `_is_inference_import` gates its first-party half on `if root == "<the sibling package name>"`
    (`tests/test_verify_zero_llm.py:114-121`). Ported verbatim, that string stays `"<the sibling package name>"`,
    so `whetstone.judge` and `whetstone.model` pass straight through and the ban silently
    narrows to third-party roots only. **The sibling project's own anti-vacuity control does not catch
    this** — it asserts the walk sees *imports*, not that the first-party predicate is live.
    So the port needs a second control asserting the predicate actually fires on a synthetic
    `whetstone.judge` import.
  - The sibling project's `_INFERENCE_CLIENTS` list contains no `mlx`, `mlx_lm`, `peft`, or `accelerate` —
    it had no reason to. Those are exactly the libraries Whetstone installs, so the inherited
    list has a hole shaped like our own stack. Extend it explicitly; do not port it as-is.
  - **Relative imports are invisible to the walk.** the sibling project's `ImportFrom` branch is guarded by
    `if node.level == 0` (`tests/test_verify_zero_llm.py:105-111`), so any `from .x import y`
    records nothing at all. The sibling project gets away with it because its first-party detection keys on
    the dotted `<sibling>.judge` form, which only an absolute import produces. **Our reward path is
    a single package whose modules import each other relatively**, so ported as-is the guard
    would watch `whetstone/verify/` and never see `from .judge import score` — the exact import
    it exists to catch, written the exact way our own code writes imports. The port must resolve
    a relative import to its absolute dotted path from the file's position in the package.
- `uv run whetstone verify --task <fixture> --patch <fixture>` emits a verdict
- `tasks/` holds instances from both sources with committed provenance — **MET, and the shape of
  it matters more than the tick.** Source B: **66 tasks**, 45 from `donor A` and 21 from
  The sibling project, each *proven live* rather than asserted — FAIL with no patch, PASS under its own
  reference patch, executed node-id set equal to declared, zero skips. The manifests are the
  user's code and are never committed; the committed provenance is `tasks/recipes/*.json` (the
  procedure) and `tasks/local-ledger.json` (per-task hash and verdicts, no file contents).
  Source A: **1 eligible instance of 300** — `pallets__flask-4045` — with all 299 refusals
  ledgered in `tasks/public/ineligible.json` against the gate that refused each. **A criterion
  met by a corpus of one on the public side is not met broadly**, and nothing downstream may
  quote source A as though it were a benchmark-sized set. The deliverable there is the four-gate
  filter and the rejection ledger; the instance count is its honest output, and 106 of the 299
  are recoverable only by hand-determining era-correct pins one instance at a time
  (`tasks/README.md`)
- A baseline bake-off report exists under `reports/baseline/`
- **`PREREGISTRATION.md` is committed** (§ 6) — before any training run exists, so git
  history proves the date

**Where this stands, stated so a later reader cannot mistake progress for completion.** P1 slice
1 landed the verifier and the corpus; slice 2 landed the **task format** — the `environment`
contract, canonical held paths, the directory loader, and the `tasks/` layout; slice 3 landed
**ingestion for both sources** and minted the corpus above; slice 4 landed **`PREREGISTRATION.md`**;
slice 5 ran the bake-off and wrote `reports/baseline/`. **No criterion remains open.**

> **Corrected 2026-08-01, when the bake-off ran.** This paragraph asserted, in the present tense,
> that *"no model has been run against any of this"* and that *"not one number about a model exists
> anywhere in this repository."* Both were exact until slice 5 and are false now. The sentences are
> preserved as quotations rather than deleted, because they describe the tree `PREREGISTRATION.md`
> was committed to, and `PREREGISTRATION.md` cites these lines and is append-only.

**What the bake-off found: no base is selected.** Three candidate bases were scored against the
working verifier and the pivot signal below fired for every one, so there is no evidence to choose
on and `PREREGISTRATION.md` § 7.3 stays open. The control arm — an inert patch and each task's own
re-derived fix, through the same harness — was intact on every run, so that outcome is about the
bases and not about a verifier that graded nothing. Prompts used the oracle retrieval setting, so
each figure bounds the unassisted one from above; every figure lives in `reports/baseline/` alone.

**What ingestion cost, recorded because the refusals are the finding.** Two of four candidate
donors yielded nothing: `donor C` was **refused outright** for having no `uv.lock`, so its pins
would have been chosen by the date the mint ran, and this repository yielded **0 of 2**, its own
test-first workflow landing the test and the fix in one commit. `donor A` capped at 45 and the sibling project
at 21 under a cap of 25; restricting to commits that *modify an existing* test (PRD D2) keeps the
miner off the fail-closed guard at `strict.py:131-140`, which is its purpose rather than its cost.

> **Corrected 2026-08-01.** The signal below read *"any **held-out** task"*. `PREREGISTRATION.md`
> § 7.1 leaves that split open until P3, so it is read against the declared source-B set instead.

**Pivot signal — fired.** If no candidate base solves *any* task in the declared source-B set,
expert iteration has nothing to bootstrap from. Pivot to an easier task stratum or a larger base
— not to a looser verifier.

---

### P2 — Rollouts + expert iteration · est. 3 weeks · target 2026-09-20

Rejection sampling: sample *k* attempts per task via MLX, keep only strict-PASS rollouts,
LoRA-SFT on those. Every training example is verified by construction.

**Exit criteria**
- `uv run whetstone run --night` produces `runs/<id>/` with a ledger and a candidate under
  `checkpoints/<id>/`
- A test asserts **every** example in the training set carries a recorded strict-PASS verdict
- A determinism test: same seed → byte-identical training set
- The run ledger records pinned seeds, model revision, task set, and tool versions

**Pivot signal:** if strict-PASS yield is ~0 across the corpus there is no training data.
Stratify by difficulty or raise *k* — do not weaken the check to manufacture wins.

---

### P3 — Never-regress promotion gate · est. 2 weeks · target 2026-10-04

```
promote iff  solved_new > solved_old
        AND  regressed  == 0
        AND  unverified == 0
```

Three exits only: `promoted` / `rejected` / `UNVERIFIED`. `UNVERIFIED` is never collapsed
into `promoted`.

**Gate liveness.** `unverified == 0` is the honest term, but transient failures (flaky test,
sandbox timeout, disk pressure) will make it nonzero on most nights, and a gate demanding
exactly zero would **never fire**. The resolution — and the temptation it refuses:

1. **Deterministic retry.** Each unverified task retries a fixed *R* times with identical
   seed and inputs. A task that verifies on retry is verified.
2. **Coverage is reported, never silently excluded.** Following the sibling project's `corpus/metrics.py`,
   unverified tasks lower *coverage*; they never vanish from the denominator. Dropping them
   is the 100%-precision-by-construction lie.
3. **The eval's own verdict.** If any task is still unverified after *R* retries, the whole
   evaluation reduces to `UNVERIFIED`: not promoted, and not `rejected` either, because no
   comparison was actually made.
4. **Liveness is itself a measurement.** The unverified rate is reported from the first eval
   onward. If the gate proves unable to fire, **the fix is a more reliable sandbox, never a
   looser gate.**

**Exit criteria**
- `uv run whetstone gate --candidate X --incumbent Y` returns one of the three exits
- Tests: known-better → `promoted`; known-worse → `rejected`; deliberately incomplete eval →
  `UNVERIFIED` and **not** promoted
- `uv run whetstone check-leakage` exits 0 — zero overlap between the training set and the
  held-out set
- The unverified rate appears in every eval's output

**Pivot signal:** a persistently high unverified rate after retries means sandbox
reliability is the real blocker, and it becomes the next phase.

---

### P4 — The first honest number · est. 3 weeks · target 2026-10-25

Run the loop against both sources, publish the harness and the result.

**Exit criteria**
- A report exists containing, for **both** sources: baseline score, final score, delta,
  `N_baseline`, `N_final`, coverage, and the full provenance block (pinned seeds, model
  revision, task set, tool versions)
- The headline matches what `PREREGISTRATION.md` committed to, and both sources are
  published together
- The harness is public and reproduces the reported number from the pinned inputs

**Pivot signal:** none. **A zero or negative delta is a valid, publishable outcome** —
`CLAUDE.md` #5 requires shipping the honest number even when gains are modest. *The engine
working* and *the empirical claim being established* are two different milestones.

> **Corrected 2026-07-29, while writing `PREREGISTRATION.md`.** This paragraph used to assert, in
> the present tense, that the sibling project's `PHASE0_RESULTS.md` carried 20 `TO-BE-FILLED` markers — a
> document gating PROCEED vs PIVOT with its numbers unfilled. That was exact at
> The sibling project's `801b457` (2026-07-28) and false about ten hours later: `77adc8f` (2026-07-29) filled
> the document and recorded a **PIVOT** — a negative result, published rather than buried, which
> is the behaviour `CLAUDE.md` #5 asks for. Verified here by `grep -c TO-BE-FILLED`: **0**. A
> claim about another project's honesty, inside our own section on publishing honestly, is the
> worst sentence in this document to leave stale, so it is corrected rather than quietly dropped.
>
> **The transferable lesson survives, and it is sharper than the one we had.** the sibling project's own
> § *Ordering: what actually happened* records that its gate criteria were fixed in a **planning
> file** on 2026-07-21 and **was not copied into the document that publishes the number** before
> the gate ran — *"That did not happen, and this document will not pretend otherwise."* So the
> failure mode P4 must avoid is not an unfilled template; it is pre-registering somewhere other
> than where the claim is published. That is why `PREREGISTRATION.md` sits at the repository root
> rather than under `docs/planning/`, and why `tests/test_docs.py` guards this correction: unlike
> a live marker count, a historical admission cannot re-stale.

---

## 5. The baseline protocol

Every figure in P4 is a delta, so the "before" must be pinned before anything trains.

- **A pinned baseline checkpoint** — the untrained open base, scored on the held-out set by
  the same strict verifier, with its provenance committed alongside.
- **Measured once, re-measured never** — unless a pinned input changes, which invalidates
  the series and is treated as starting over.
- **A baseline `N`.** The untrained base's weak-vs-strict differential is the reference
  against which "did the loop learn to cheat more?" is judged. Without it a final `N` says
  nothing.

---

## 6. Pre-registration

Two sources with no headline rule is an invitation to post-hoc selection — in the one
project whose entire premise is not fooling yourself. `PREREGISTRATION.md` is committed in
**P1**, before any number exists:

- **The private source (B) is the headline.** It is on-thesis and uncontaminated.
- Both sources are **always published together**, regardless of which looks better.
- A disagreement between them is **reported as a finding**, not resolved by choosing the
  flattering one. Public-gain-with-private-flat is the expected signature of contamination
  and is itself worth publishing.

---

## 7. What we take from the sibling project, and what we decline

The sibling project is real and shipped — v0.7.0, 8 tags, and 832 tests passing
(`uv run pytest -q` → `832 passed, 1 skipped, 1 deselected`). 13,068 lines in the sibling project's `src/`;
46,202 across the repo; roughly 6,050 non-docstring statement lines in `src` — the sibling project's source
is over half docstring, so the bare figure means little without its scope.

> Every claim in this section was re-verified against the sibling project's source on 2026-07-27, after an
> earlier draft cited the wrong file for the inference guard. Each row below carries the
> `file:line` that backs it. Do not extend this section from memory.

**Taken:**

| Module | Why |
|---|---|
| `verify/verdict.py` | The honesty contract as the *shape of the reduction*: `UNVERIFIED` ranks **above** `PASS`, so worst-status-wins can never render an unverified result clean; an empty verdict set reduces to `UNVERIFIED`, not `PASS`. Verified — `verdict.py:67-73` `_RANK = {NOT_COVERED: -1, PASS: 0, WARN: 1, UNVERIFIED: 2, FAIL: 3}` with `:114` `max(scored, key=…)`; `:111-113` returns `UNVERIFIED` on an empty set. Note the **stronger** form we also inherit: a set that is empty only *after* filtering `NOT_COVERED` still reduces to `UNVERIFIED` (`:107-109`) |
| `verify/invariants.py` | The provenance boundary — operator policy never sourced from the agent's own evidence. Verified — `invariants.py:9-16`, and the boundary is carried by the *signature*: `load_invariants(path: Path)` (`:69`) takes a filesystem path and never trace records. The sibling project pins this with `tests/test_invariants.py:55 test_no_invariant_is_ever_sourced_from_a_trace`; port that test, not just the module |
| `corpus/metrics.py` | Precision / recall / **coverage**, with `UNVERIFIED` excluded from the confusion matrix but **kept in coverage's denominator** — verified at `metrics.py:142-144` (`if verdict == "UNVERIFIED": unverified += 1; continue`) and `:157-166` (`adjudicable = decided + unverified`; `coverage = decided / adjudicable`). **Caveat for P3:** the module documents *two* honesty rules, and we inherit only this one. The other is the **label trap** (`metrics.py:15-29`) — cases lacking independent human ground truth are dropped from P/R *and* from coverage entirely, because counting every FAIL as a true positive makes precision 1.0 by construction. Our reward is an exit status with no human adjudication, so that rule has no analogue here. It is **declined as inapplicable, not overlooked** — recorded so a P3 implementer reading `metrics.py` knows which of the two paths to port |
| `tests/test_verify_zero_llm.py` | The AST guard proving no model sits on the reward path. It bans inference clients (`openai`, `anthropic`, `torch`, `transformers`, `ollama`, `vllm`, `langchain`, …) *and* inference-shaped first-party module names (`llm`, `judge`, `model`, `inference`, `prompt`), and it is **scoped to named packages rather than the whole tree** — the sibling project's own non-shipped `eval/` tree legitimately imports `anthropic`/`openai`. The scoping matters more for us than for the sibling project: Whetstone will have `mlx-lm` genuinely installed, so an accidental inference import on the reward path is easy to make and invisible without a guard aimed at exactly that path. It also ships an anti-vacuity control asserting the AST walk really observes the imports the guarded layer makes |
| `sandbox/seatbelt.py` | **The Seatbelt approach, not the module** — added 2026-07-28, after the P1 dig found this table listing no sandbox while § 2 requires one. Verified **separable from the declined replay substrate**: `seatbelt.py:44-56` imports only stdlib, one exception class (`snapshot.bth1.UnsupportedPlatform`) and an optional `TraceWriter` whose own docstring says *"Containment does not depend on it: the boundary is the kernel's"* (`:357-358`); nothing under `sandbox/` imports `the sibling project.replay`, while `proxy.py:595-596` and `cli.py:84,141,190,260` import the sandbox. **Replay depends on the sandbox; the sandbox never depends on replay** — so declining replay costs us nothing here. What we take is the *shape*: `(allow default)`, then `(deny network*)` and `(deny file-write*)`, then one escaped `subpath` allow, executed as `sandbox-exec -f <profile> <command>`. What we do **not** take is the file: 417 lines carrying an `allow-ports` mode, a closed `NetworkPolicy` enum and a denial-from-stderr parser this reward never uses, all of which would have to satisfy `mypy --strict`. Ours is a six-line deny-all profile. **The `_quote` SBPL escaping (`seatbelt.py:87-95`) is taken as a requirement, not an option** — an unescaped `"` in a scope path is a policy injection into the boundary that enforces the policy, and our profile being smaller does not make that hole smaller |
| `eval/instances/` + `eval/scripts/` | SWE-bench-Lite eligibility filter and the pure, offline, seeded stratified draw |

**Declined — the replay substrate.** `CLAUDE.md:79` says *"reuse the sibling project's verifier/replay
where it fits."* The verdict semantics fit; the replay engine does not, for four reasons:

1. The sibling project answers a **harder question** — *did the agent's trace faithfully describe what it
   did?* — which needs snapshot + replay. Our v1 reward needs only *does the end state pass
   an operator-held check?*: a sandbox and an exit status.
2. **Throughput** — **two** `clonefile(2)` tree restores plus a server spawn and teardown per
   replay (`snapshot/clone.py:280-298`, `replay/engine.py:531`, `replay/client.py:374,389`).
   Note the restore *is* the clone, not a separate step. **This is a structural inference,
   not a measurement:** the sibling project contains no benchmark or timing figure anywhere, so this must
   never later be quoted as a measured cost.
3. **Parallel calls yield `UNVERIFIED`** — the sibling project deliberately refuses to serialize turns, so
   batched rollouts produce no signal. Verified at `sandbox/gate.py:68-73, 258-266`: a
   `tools/call` arriving while another is in flight is refused as
   `UNRESTORABLE_CONCURRENT_TURN` and still forwards, reducing to `Status.UNVERIFIED`
   (`verify/turn.py:129,183,199`). The refusal is deliberate — serializing would make the sibling project
   concurrency-altering.
4. **No reward-facing API** — `src/<pkg>/__init__.py` re-exports nothing (one line), and
   "reward" and "training" appear nowhere under `src/`. The sibling project *is* importable submodule by
   submodule, which is exactly how the verdict semantics above get lifted; it also ships a
   The sibling project console script over a 79 KB `cli.py`. The absence is of a reward surface, not of
   an API.

Revisit only if a later family needs trace fidelity.

---

## 8. Guardrails as rejection tests

| Guardrail (`CLAUDE.md`) | How this plan visibly passes |
|---|---|
| Reward verifiable, never a judge | Reward is a pytest exit status. Enforced structurally by the P1 AST import guard, not by convention |
| Never regress; `UNVERIFIED` ≠ win | P3's three exits, with `UNVERIFIED` ranked above `PASS` in the ported reduction; P3 tests assert an incomplete eval is never promoted |
| Local / BYOK / private | Everything runs on the Mac. Source B never leaves the box. No BYOK teacher is used at all inside this horizon (distillation is post-horizon) |
| Gets better as base models improve | The base is swappable and chosen by a P1 bake-off; the durable assets are the verifier, the gate, and the accumulated verified-improvement record |
| Ship the honest number even if modest | P4 has no pivot signal — zero or negative deltas are published |
| No frontier base-model training | Nothing here pretrains anything; we LoRA an open base on verified wins |

**One network exception, declared:** fetching public SWE-bench instances touches the
network. Following the sibling project's precedent, the fetch is human-run, its output committed, and the
draw itself pure and offline. Source B never touches the network at all.

---

## 9. Post-horizon (named, so they read as sequenced rather than forgotten)

Distillation into a small local model · the signed morning report and
`whetstone report --last-night` · the Next.js dashboard · GRPO as a stretch beyond expert
iteration · a second task family · closing cheat 6 via held-out test variants or mutation
testing · Linux portability.

---

## 10. Open questions

- The PyPI package name. The seed research recorded `whetstonehq` and `whetstone-ai` as free
  on npm and PyPI, with bare `whetstone` taken — **unverified as of today**, needs re-checking.
- The held-out split size and stratification.
- The retry count *R* in P3, to be set from the observed unverified rate rather than guessed.
- Apple Silicon capacity: whether the base eventually chosen sustains *k* rollouts per task in a
  night. The P1 bake-off measured its own wall-clock but selected no base, so this stays open.

---

## 11. Grounded facts

The only external claims this project cites (`CLAUDE.md:215-224`):

1. **RLVR** is the live frontier for tasks with checkable outcomes, and **reward-hacking** is
   its central documented failure mode — **METR** observed a model rewriting a timer instead
   of optimizing the task.
2. **"One Token to Fool LLM-as-a-Judge"** shows up to **35% false positives** — a judge
   reward is gameable; an execution-grounded reward is not.
3. **Karpathy (Sequoia Ascent 2026)** — the valuable RL environments *"aren't in the
   frontier-lab mix."*

Anything else is **unverified and must be labeled so**. The sibling project cites two further arXiv items
(2603.03116; 2507.08794) which are **not** inherited here and would need verifying before
use. `VISION.md` restates facts 1 and 2 without attribution and gives the venue as "Sequoia
2026" — `CLAUDE.md`'s attributed form is the one to quote.

> `CLAUDE.md:224` — *"If you need a statistic that isn't here, do not invent one; say it's
> unverified."*
