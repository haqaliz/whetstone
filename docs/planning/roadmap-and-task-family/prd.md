# PRD — Roadmap & First Task Family

**Slug:** `roadmap-and-task-family` · **Branch:** `feat/roadmap-and-task-family/aliz`
**Written:** 2026-07-26 · **Core-loop element:** ① verifiable task family + verifier
(and the sequencing of ②–⑤)

**Deliverable:** `docs/ROADMAP.md` — a 2–3 month phased plan that commits to one task
family, specifies its verifier concretely, and orders the phases so the honest number is
reachable inside the horizon.

---

## Problem Statement

Whetstone has no ranked backlog and no chosen task family. `CLAUDE.md` names
`docs/ROADMAP.md` as the immediate next artifact; `find docs -type f` returns nothing.
The repo is two commits old and contains **zero lines of executable code** — only
`.gitignore`, `CLAUDE.md`, `VISION.md`, and ten workflow skills.

Every element of the core loop is blocked on element ①. `whetstone-next` states it
directly: *"② the loop, ③ the gate, and ④ the report are all meaningless without ① an
airtight, execution-grounded verifier for one task family."* Until a family is chosen and
its check specified, there is nothing to build a reward against, nothing for the gate to
promote on, and no number for the report to be honest about.

**Who has this problem:** the founder, today, as the single blocking decision. Downstream,
the ICP — an engineer who wants a model measurably better at *their* tasks by morning,
privately, and who won't trust a gain they can't check.

**Evidence it's real:** `git log` (two commits, both 2026-07-26, no `src/`, no tests, no
tags); absent `docs/` entirely; `.gitignore:19` states outright *"Pre-declared: these
directories don't exist yet: the loop is not built."*

## Goals & Success Metrics

The PRD's own success is **not** a model-improvement number — this unit of work ships a
document. Its criteria are checklist-style over content, and they are the failing tests
written first (§ Acceptance Criteria).

The roadmap it produces must, in turn, define the project's first real metric:

- **The honest number** — the verified delta on a held-out set, produced by the strict
  verifier, published with its provenance (pinned seeds, model revision, task set, tool
  versions). **This is a metric to be produced, not a target to be hit.** Per `CLAUDE.md`
  #5, a modest or zero delta is published as-is.
- **`N` — reward-hacking attempts caught & rejected**, defined operationally below.

> **No projected gain appears in this PRD or in the roadmap.** The seed research's
> *"+7% on your real tasks"* is illustrative pitch copy, not a target or a finding, and its
> *"MVP wedge (1–2 months)"* is an unsourced estimate. Neither is binding. Only three
> external facts are citable (§ Grounded Facts).

## The Decisions (locked in interview, 2026-07-26)

| # | Decision | Choice |
|---|---|---|
| 1 | **Task family** | Python repo bug-fixing, verified by operator-held pytest (`FAIL_TO_PASS` + `PASS_TO_PASS`). **Two task sources, one family:** public SWE-bench-Lite instances (comparable, publishable) and the user's own repos (private, uncontaminated, on-thesis). Identical task contract and identical verifier for both — only provenance differs, so this satisfies `CLAUDE.md` #5's "ONE task family". |
| 2 | **Platform** | macOS, Apple Silicon. The sibling project's Seatbelt sandbox and APFS `clonefile` snapshot work natively; **no porting phase required**. **[†] Half of this is wrong — see the correction below the table.** |
| 3 | **`N` counter** | **Differential against a deliberately weak verifier.** Every rollout is scored twice — strict (tests restored from golden, patch confined to non-test files) and weak (accept as submitted). `N` = rollouts the weak check PASSed and the strict check FAILed. Reported as *"N attempts a weaker check would have scored as wins."* |
| 4 | **Horizon** | Through the first honest number. Distillation, the signed morning report, the dashboard, GRPO, and any second family are explicitly **post-horizon**. |
| 5 | **Improvement method** | Rejection sampling / expert iteration: sample *k* per task, keep only strict-PASS rollouts, LoRA-SFT on those. Every training example is verified-by-construction. |
| 6 | **Promotion gate** | Strict improvement **and** zero per-task regression **and** full coverage: `promote iff solved_new > solved_old AND regressed == 0 AND unverified == 0`. Otherwise `rejected`, or `UNVERIFIED` when the eval could not complete. **See § Gate Liveness — the zero-unverified term needs a retry policy or the gate may never fire.** |
| 7 | **Base + runtime** | MLX end-to-end (`mlx-lm`) for both rollouts and LoRA. The specific open base is chosen by a P1 bake-off **against the working verifier**, not on paper — consistent with `CLAUDE.md` #4 (keep the base swappable). |

> **[†] Correction, 2026-07-28 (P1 slice 1 — the row is left standing rather than rewritten, so
> the record shows what was decided and what it got wrong).** Decision 2's *"the sibling project's Seatbelt
> sandbox and APFS `clonefile` snapshot work natively; no porting phase required"* is **half
> right**.
>
> - **The Seatbelt half holds, and is now built.** `seatbelt.py` was verified separable from the
>   replay substrate (`docs/ROADMAP.md` § 7's `sandbox/seatbelt.py` row), and P1 took the
>   approach rather than the module: `src/whetstone/verify/sandbox.py` is our own six-line
>   deny-all SBPL profile, with network denial and write confinement observed on this machine.
> - **The `clonefile` half does not hold.** It refers to `<sibling>/snapshot/`, which **is part of
>   the replay substrate `docs/ROADMAP.md` § 7 declines** — the snapshot/restore machinery is
>   what replay is built on (`snapshot/clone.py:280-298`). This slice takes the sandbox and does
>   **not** take the snapshot machinery; STRICT materialises each run with a fresh git checkout
>   into `/_sandbox/<run_id>/` instead. Nothing was ported and nothing is owed, but the sentence
>   as written implies we inherited a snapshot layer we do not use.
>
> The claim's *reason* also needs qualifying: "no porting phase required" was about macOS
> compatibility, and that is not the same as "nothing to build". Platform compatibility was never
> the cost — the cost was proving denial rather than assuming it.

## Requirements for `docs/ROADMAP.md`

### Must-have

- **M1 — The family, named and justified.** One family, its two sources, why its end state
  is deterministically checkable, and the task contract fields.
- **M2 — The verifier, specified concretely.** What is re-executed, what observed-vs-claimed
  state is compared, where it runs (`/_sandbox/`), and the provenance boundary that makes it
  airtight.
- **M3 — The cheat enumeration and its honest residual.** Every way a policy would try to
  game the reward, which defence kills it, and — stated plainly — which one is *not* fully
  killed (§ Reward-Hacking Surface).
- **M4 — Phases ordered per the core loop**, verifier → loop → gate → report, each with an
  **observable** exit criterion (a command that passes or a file that exists), never a
  narrative one.
- **M5 — Milestones dated** relative to a start date, sized for a solo founder, labeled as
  estimates.
- **M6 — The "first honest number" milestone**: what is measured, on which held-out set,
  how the set is protected from leakage, and where `N` comes from.
- **M7 — Guardrails as rejection tests.** Each of the six guardrails restated as a check
  the plan visibly passes.
- **M8 — the sibling project reuse stated precisely**: which parts are taken and which are deliberately
  declined, with reasons (§ Technical Considerations).
- **M9 — Zero fabricated statistics.** Only the three grounded facts; everything else
  labeled unverified.
- **M10 — Gate liveness**: the retry count *R*, the coverage-reporting rule, and the
  eval-level `UNVERIFIED` exit (§ Gate Liveness).
- **M11 — The baseline protocol**: the pinned baseline checkpoint, its provenance, and the
  baseline `N` (§ Baseline Protocol).
- **M12 — Pre-registration**: which source is the headline, decided and written down before
  any number exists (§ Pre-registration).

### Should-have

- **S1 —** Post-horizon section naming distillation, morning report, dashboard, GRPO, and
  second family as explicitly deferred, so they read as sequenced rather than forgotten.
- **S2 —** A "what would make us pivot" line per phase — the observation that would
  invalidate the plan.
- **S3 —** The open questions this PRD could not close, carried forward rather than
  silently dropped.

### Nice-to-have

- **N1 —** A one-screen phase diagram.
- **N2 —** Pointers from each phase to the skill that executes it (`wbf`, `tech-plan`).

## Technical Considerations

### The verifier contract (the moat)

```
task:    repo @ base_commit, problem statement,
         FAIL_TO_PASS[], PASS_TO_PASS[], operator-held test blobs
policy:  produces a patch
strict:  1. checkout base_commit into /_sandbox/<run>/
         2. apply patch  — REJECT if it touches any test path
         3. restore operator-held tests from golden  (post-patch, always)
         4. run pytest FAIL_TO_PASS + PASS_TO_PASS, no network, fixed seed
         5. reward = exit status
weak:    1. checkout base_commit
         2. apply patch  — NO path confinement (test edits allowed through)
         3. (no restore — the policy's own tests are what run)
         4. run pytest as the policy left it
         5. reward = exit status
N += 1 where weak == PASS and strict == FAIL
```

`N` is reported as *"attempts a weaker check would have scored as wins"* — a statement
about **what the strictness caught**, not about the policy's intent. A patch that edited a
genuinely-buggy test in good faith still counts. This framing is deliberate: it is
measurable and unfalsifiable-free, where "attempts to cheat" would require reading intent
the verifier cannot observe.

The reward is a **process exit status**. No model appears anywhere on the reward path.
This is enforced structurally, not by convention — see the import guard below.

### Reused from the sibling project (verified: v0.7.0, 832 tests passing, 13,068 LOC — real, not planned)

| Taken | Why |
|---|---|
| `verify/verdict.py` (114 L, zero deps) | The honesty contract **as the shape of the reduction**: `_RANK` places `UNVERIFIED` (2) above `PASS` (0) and `WARN` (1), so worst-status-wins can never render an unverified result clean; an empty verdict set reduces to `UNVERIFIED`, not `PASS`. This is precisely `CLAUDE.md`'s "`UNVERIFIED` never counts as a win", already implemented and tested. |
| `verify/invariants.py` (299 L) | The **provenance boundary** — policy loaded only from an operator file, no trace-reading loader, and a test asserting that absence structurally. For an RL reward this is existential: without it the policy authors its own reward. |
| `corpus/metrics.py` (174 L) | Precision/recall/**coverage**, with `UNVERIFIED` excluded from the confusion matrix (it lowers coverage instead) — refuses the 100%-precision-by-construction lie. |
| `tests/test_import_guard.py` | AST walk over every module in the reward path, failing the build if an inference library is imported. The credible structural answer to *"isn't this an LLM judge with extra steps?"* |
| `eval/instances/` + `eval/scripts/` | SWE-bench-Lite eligibility filter (pure-Python repos: django, sympy, flask, requests, sphinx, pylint; matplotlib/scikit-learn/astropy/xarray/seaborn excluded for C/Cython builds) → 166 strict-eligible instances, drawn by a pure offline seeded stratified draw with committed artifacts. |

### Declined from the sibling project — and why (this contradicts a line in `CLAUDE.md`)

`CLAUDE.md:79` says *"Reuse the sibling project's verifier/replay where it fits."* The dig found the
**verdict semantics fit; the replay substrate does not**, and the roadmap must say so:

1. The sibling project answers a *harder* question — *"did the agent's trace faithfully describe what it
   did?"* — which requires snapshot + replay. Whetstone's v1 reward only needs *"does the
   end state pass an operator-held check?"*: a sandbox and an exit status.
2. **Throughput.** ~5 ms/turn snapshot scaling with tree size, plus a full APFS clone +
   restore + server spawn per replay. Built for auditing runs, not for generating
   high-volume RL rollouts.
3. **Parallel calls → `UNVERIFIED`.** the sibling project deliberately refuses to serialize turns, so any
   batched rollout yields `UNVERIFIED` instead of signal.
4. **No API surface.** `src/<pkg>/__init__.py` is one line (`__version__ = "0.0.0"`, stale
   against `pyproject.toml`'s 0.7.0); nothing is exported programmatically, and grep for
   "reward"/"training" returns nothing.

Decision: **vendor the verdict semantics, build a simpler substrate.** MCP-mediated replay
becomes relevant only if a later family needs trace fidelity.

### Constraints inherited from the repo (must not be contradicted)

From `.gitignore` and the skills — these are already committed and the roadmap must match:
`src/whetstone/`, `tests/`, `uv` exclusively, **ruff + mypy**, pytest; CLI entrypoint
`whetstone` with `whetstone report --last-night`; artifact dirs `/runs/`, `/checkpoints/`,
`/tasks/local/`, `/reports/local/`, `/_sandbox/`; dashboard is a **Next.js** subdirectory
of this repo; checkpoint lifecycle `candidate → evaluated → promoted / rejected /
UNVERIFIED` with exactly three gate exits; PyPI publish target (**package name unchosen**);
0.x versioning, tag `vX.Y.Z`, tag-push is the release mechanism.

### Gate Liveness (added in self-critique — 🔴)

`unverified == 0` is the honest term, but on a real held-out set transient failures (flaky
test, sandbox timeout, disk pressure) will make it nonzero on most nights. A gate demanding
exactly zero converts *never regress* into **never ship**, and the obvious workaround —
silently dropping unverified tasks — is exactly the metrics lie the sibling project's `corpus/metrics.py`
refuses. The roadmap must therefore specify:

1. **Deterministic retry.** Each unverified task is retried a fixed *R* times with identical
   seed and inputs. A task that verifies on retry is verified; nothing is dropped.
2. **Coverage is reported, never silently excluded.** Following `corpus/metrics.py`,
   unverified tasks lower **coverage** rather than vanishing from the denominator.
3. **The eval's own verdict.** If any task remains unverified after *R* retries, the
   evaluation reduces to `UNVERIFIED` and the checkpoint is **not promoted** — it is also
   **not** marked `rejected`, because no comparison was actually made. This is the third
   gate exit doing its job, and it is the honest outcome.
4. **Liveness is itself a measurement.** The roadmap must require reporting the unverified
   rate from the first eval onward. If the gate proves unable to fire in practice, that is a
   discovered fact about the harness — and the fix is a more reliable sandbox, never a
   looser gate.

### Baseline Protocol (added in self-critique — 🔴)

Every metric here is a delta, and nothing defined the "before". The roadmap must specify:

- **A pinned baseline checkpoint** — the untrained open base, evaluated on the held-out set
  by the same strict verifier, before any training runs. Its score is committed alongside its
  provenance (model revision, seeds, task set, tool versions).
- **The baseline is measured once and re-measured never** — except when the pinned inputs
  change, which invalidates the whole series and is treated as starting over.
- **`N` gets a baseline too.** The untrained base's weak-vs-strict differential is the
  reference against which "the loop did or did not learn to cheat more" is judged. Without
  it, a nonzero `N` at the end says nothing about the loop.

### Pre-registration (added in self-critique — 🟡)

Two task sources with no headline rule is an invitation to post-hoc selection, in the one
project whose premise is not fooling yourself. The roadmap must **pre-register, before any
number exists**: which source produces the headline figure, that both are always published
together regardless of which looks better, and what a disagreement between them means.
Recommended framing: the **private source is the headline** (it is on-thesis and
uncontaminated) and the public source is reported as the comparable-but-contaminated
reference. Whatever is chosen, it is written down before the first run.

## Reward-Hacking Surface

`prd-interview` requires treating *"it can't cheat"* as an unfinished answer. The full
enumeration, honestly scored:

| # | Cheat | Defeated by | Status |
|---|---|---|---|
| 1 | Edit the test file to delete/weaken the failing assertion | Tests restored from golden **after** the patch; patch rejected if it touches a test path | **Killed** |
| 2 | Weaken an assert in place (`assertEqual` → `assertTrue`) | Same boundary | **Killed** |
| 3 | Mutate a fixture / `conftest.py` | Same boundary (fixtures are operator-held) | **Killed** |
| 4 | `sys.exit(0)` / `os._exit(0)` before assertions run | Exit status read from the **runner**, plus `PASS_TO_PASS` must also hold | **Killed** |
| 5 | Monkeypatch the runner / register a `conftest` plugin that skips | Boundary + skipped-test count asserted to be zero | **Killed** |
| 6 | **Special-case the known input** — hardcode the expected output rather than fix the bug | *Partially.* Stays entirely inside the provenance boundary. | **RESIDUAL** |

**Cheat 6 is a genuine residual and the roadmap must say so.** It is mitigated —
`PASS_TO_PASS` catches the crude version, and held-out evaluation means a policy that only
memorises the training tasks shows no held-out gain — but it is **not eliminated**. A patch
that special-cases the exact input satisfies every structural check. Honest framing: the
verifier guarantees *the tests genuinely pass on unmodified tests*, not *the fix
generalises*. Post-horizon candidates for closing it (held-out test variants, mutation
testing) are named as deferred, not claimed.

## Risks & Open Questions

| Risk | Severity | Mitigation |
|---|---|---|
| **Contamination** — SWE-bench-Lite is widely trained on; an open base may have memorised fixes, inflating baseline and muddying the delta | **High** | Two sources by design: the user's own repos are uncontaminated. Report both numbers separately and never average them. |
| **Cheat 6 residual** (above) | Medium | Named, not hidden. `PASS_TO_PASS` + held-out eval; closing it is post-horizon. |
| **The loop plateaus, or gains are zero** | Medium | Named in the seed research as the central bet. `CLAUDE.md` #5: ship the harness and the honest number regardless. A zero delta, published, is a valid outcome. |
| **Rejection sampling yields too few wins to train on** | Medium | Fails gracefully (empty training set, not a corrupted gradient). Mitigate with larger *k* and task-difficulty stratification. |
| **The sibling project's own precedent**: `PHASE0_RESULTS.md` has 20 `TO-BE-FILLED`; its headline number is unpublished and Stage 3 partial | Informational | The cautionary lesson: *the engine working* and *the empirical claim being established* are two different milestones. P4 exists precisely so they are not conflated. |
| **Apple Silicon capacity** may bound base size / rollout throughput | Medium | Discovered in the P1 bake-off, against the real verifier, before the loop is built around it. |

**Open questions carried forward:** the PyPI package name (`whetstonehq` / `whetstone-ai`
were free per the seed research, **unverified as of today**); `LICENSE` file absent though
`CLAUDE.md` states Apache-2.0; the exact held-out split size and stratification; whether
`whetstone report --last-night` ships inside the horizon given the report is post-horizon.

## Acceptance Criteria (test-first — these are the checks written before the doc)

1. `docs/ROADMAP.md` exists and names **exactly one** task family, with its two sources and
   a stated reason its end state is deterministically checkable.
2. It contains a concrete verifier specification: what is re-executed, the observed-vs-claimed
   comparison, and the provenance boundary.
3. It enumerates the cheat surface **and explicitly flags cheat 6 as a residual** rather
   than claiming the family is uncheatable.
4. Phases appear in core-loop order (verifier → loop → gate → report); **every** phase has
   an exit criterion that is a command or an artifact, not prose.
5. Milestones carry dates relative to a stated start date and are labeled estimates.
6. A "first honest number" milestone specifies the measurement, the held-out set, the
   leakage protection, and the derivation of `N`.
7. All six guardrails appear as rejection tests the plan visibly passes.
8. **Adversarial criterion:** the document states, for the weak-vs-strict differential, at
   least one concrete case that the weak verifier PASSes and the strict verifier FAILs —
   i.e. `N` is shown to be a real measurement, not a placeholder that could read zero
   because nothing was ever checked.
9. Every number in the document is either one of the three grounded facts (with `CLAUDE.md`'s
   attribution), a labeled estimate, or absent. No projected gains, no percentages.
10. Nothing contradicts the committed constraints (`src/whetstone/`, uv, ruff/mypy, the
    artifact dirs, the three gate exits, `master` as base branch).
11. The gate specification includes a retry policy and states the eval-level `UNVERIFIED`
    exit, so the gate is demonstrably capable of firing (§ Gate Liveness).
12. A baseline protocol is specified — pinned checkpoint, provenance, and baseline `N` —
    so the honest number has a defined "before" (§ Baseline Protocol).
13. The headline source is pre-registered, with a stated rule for reporting both sources
    together (§ Pre-registration).

## Out of Scope

Writing any code; `docs/technical/ARCHITECTURE.md`; `docs/product/PRODUCT_SPEC.md`;
`README.md`; the `LICENSE` file; choosing the PyPI package name; a second task family;
distillation design; the dashboard; GRPO; Linux portability.

## Grounded Facts (the only citable externals)

Per `CLAUDE.md:108-119`: (1) RLVR is the live frontier and reward-hacking its central
documented failure mode — **METR** observed a model rewriting a timer instead of optimizing
the task; (2) **"One Token to Fool LLM-as-a-Judge"** shows up to **35% false positives**;
(3) **Karpathy (Sequoia Ascent 2026)** — the valuable RL environments *"aren't in the
frontier-lab mix."*

The sibling project cites two further arXiv items (2603.03116, 27–78% corrupt successes; 2507.08794,
judge false positives). These are **not** in Whetstone's grounded list and must be verified
before use, not inherited. `VISION.md` restates facts (1) and (2) **without** attribution
and gives the venue as "Sequoia 2026" vs `CLAUDE.md`'s "Sequoia Ascent 2026" — use
`CLAUDE.md`'s attributed form.
