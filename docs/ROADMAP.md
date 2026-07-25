# Whetstone Roadmap

**Horizon:** 2026-07-27 → 2026-10-25 (~13 weeks). **Written:** 2026-07-26.
**Ends at:** the first honest number. Distillation, the morning report, and the dashboard
are post-horizon and named as such.

> All durations are **planning estimates**, not commitments or measurements. No performance
> figure appears anywhere in this document, because none has been measured yet. See
> § Grounded facts.

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
problem_statement,
fail_to_pass[], pass_to_pass[],
test_blobs{}          # operator-held; the golden copy of every test file
provenance{}          # how this task was obtained, and when
```

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
  5. reward := exit status

WEAK (measurement only — never trains anything)
  1. checkout base_commit
  2. apply the patch, no path confinement
  3. no restore — whatever tests the policy left are what run
  4. run pytest
  5. verdict := exit status
```

### The provenance boundary

The tests are the **operator's** artifact; the patch is the **policy's** evidence, and they
never mix. This is Belay's `verify/invariants.py` discipline applied to code: policy is
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

## 3. The cheat surface — and its honest residual

`prd-interview` requires treating *"it can't cheat"* as an unfinished answer. The full
enumeration:

| # | Cheat | Defeated by | Status |
|---|---|---|---|
| 1 | Edit the test file to delete or weaken the failing assertion | Patch rejected if it touches a test path; tests restored from golden post-patch | **Killed** |
| 2 | Weaken an assert in place (`assertEqual` → `assertTrue`) | Same boundary | **Killed** |
| 3 | Mutate a fixture or `conftest.py` | Same boundary — fixtures are operator-held | **Killed** |
| 4 | `sys.exit(0)` / `os._exit(0)` before assertions run | Exit status read from the runner; `pass_to_pass` must also hold | **Killed** |
| 5 | Monkeypatch the runner, or register a `conftest` plugin that skips | Boundary, plus skipped-test count asserted zero | **Killed** |
| 6 | **Special-case the known input** — hardcode the expected output instead of fixing the bug | *Partially.* Sits entirely inside the boundary. | **RESIDUAL** |

**Cheat 6 is not solved, and this document will not pretend otherwise.** A patch that
special-cases the exact test input satisfies every structural check above. It is mitigated —
`pass_to_pass` catches the crude version, and held-out evaluation means a policy that only
memorises training tasks shows no held-out gain — but it is **not eliminated**.

Stated precisely: **the verifier guarantees that the tests genuinely pass on unmodified
tests. It does not guarantee that the fix generalises.** Closing the gap (held-out test
variants, mutation testing) is post-horizon and is not claimed here.

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

Includes: the task contract; the strict and weak verifiers; the sandbox; Belay's verdict
semantics ported (§ 7); the adversarial corpus; task ingestion for both sources; and the
base-model bake-off — run **against the working verifier**, not on paper.

**Exit criteria**
- `uv run pytest tests/adversarial/` exits 0, where the suite asserts, per cheat fixture:
  - cheats 1–5: **STRICT rejects AND WEAK accepts** — proving the differential is real
    rather than vacuously zero
  - cheat 6: accepted by both, asserted as the *documented, expected* residual so a future
    reader cannot mistake silence for coverage
- `uv run pytest tests/test_import_guard.py` exits 0 — an AST walk over every module on the
  reward path fails the build if any inference library is imported
- `uv run whetstone verify --task <fixture> --patch <fixture>` emits a verdict
- `tasks/` holds instances from both sources with committed provenance
- A baseline bake-off report exists under `reports/baseline/`
- **`PREREGISTRATION.md` is committed** (§ 6) — before any training run exists, so git
  history proves the date

**Pivot signal:** if no candidate base solves *any* held-out task, expert iteration has
nothing to bootstrap from. Pivot to an easier task stratum or a larger base — not to a
looser verifier.

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
2. **Coverage is reported, never silently excluded.** Following Belay's `corpus/metrics.py`,
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
`CLAUDE.md` #5 requires shipping the honest number even when gains are modest. The failure
mode this phase exists to prevent is Belay's own: its `PHASE0_RESULTS.md`, the document
gating PROCEED vs PIVOT, still carries 20 `TO-BE-FILLED` markers. *The engine working* and
*the empirical claim being established* are two different milestones.

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

## 7. What we take from Belay, and what we decline

Belay (`~/dev/at/belay`) is real and shipped — v0.7.0, 8 tags, 13,068 LOC, 832 tests passing.

**Taken:**

| Module | Why |
|---|---|
| `verify/verdict.py` | The honesty contract as the *shape of the reduction*: `UNVERIFIED` ranks **above** `PASS`, so worst-status-wins can never render an unverified result clean; an empty verdict set reduces to `UNVERIFIED`, not `PASS` |
| `verify/invariants.py` | The provenance boundary — operator policy never sourced from the agent's own evidence |
| `corpus/metrics.py` | Precision / recall / **coverage**, with `UNVERIFIED` excluded from the confusion matrix rather than from the denominator |
| `tests/test_import_guard.py` | The AST guard proving no model sits on the reward path |
| `eval/instances/` + `eval/scripts/` | SWE-bench-Lite eligibility filter and the pure, offline, seeded stratified draw |

**Declined — the replay substrate.** `CLAUDE.md:79` says *"reuse Belay's verifier/replay
where it fits."* The verdict semantics fit; the replay engine does not, for four reasons:

1. Belay answers a **harder question** — *did the agent's trace faithfully describe what it
   did?* — which needs snapshot + replay. Our v1 reward needs only *does the end state pass
   an operator-held check?*: a sandbox and an exit status.
2. **Throughput** — a full APFS clone, restore, and server spawn per replay; built for
   auditing runs, not generating rollouts.
3. **Parallel calls yield `UNVERIFIED`** — Belay deliberately refuses to serialize turns,
   so batched rollouts produce no signal.
4. **No API surface** — `src/belay/__init__.py` is one line, and grep for "reward" or
   "training" returns nothing.

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
network. Following Belay's precedent, the fetch is human-run, its output committed, and the
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
- Apple Silicon capacity: whether the chosen base sustains *k* rollouts per task in a night.
  Discovered in the P1 bake-off, before the loop is built around it.

---

## 11. Grounded facts

The only external claims this project cites (`CLAUDE.md:108-119`):

1. **RLVR** is the live frontier for tasks with checkable outcomes, and **reward-hacking** is
   its central documented failure mode — **METR** observed a model rewriting a timer instead
   of optimizing the task.
2. **"One Token to Fool LLM-as-a-Judge"** shows up to **35% false positives** — a judge
   reward is gameable; an execution-grounded reward is not.
3. **Karpathy (Sequoia Ascent 2026)** — the valuable RL environments *"aren't in the
   frontier-lab mix."*

Anything else is **unverified and must be labeled so**. Belay cites two further arXiv items
(2603.03116; 2507.08794) which are **not** inherited here and would need verifying before
use. `VISION.md` restates facts 1 and 2 without attribution and gives the venue as "Sequoia
2026" — `CLAUDE.md`'s attributed form is the one to quote.

> `CLAUDE.md:119` — *"If you need a statistic that isn't here, do not invent one; say it's
> unverified."*
