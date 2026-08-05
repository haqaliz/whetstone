# PRD — `p2-yield-probe`

**Card:** `docs/planning/p2-yield-probe/card.md` · **Dig:**
`docs/planning/p2-yield-probe/understanding.md`
**Upstream:** `docs/ROADMAP.md` § 4 (P1 pivot signal `:387-389`, P2 `:393-406`),
`PREREGISTRATION.md` § 10.1 (`:325-361`), `reports/baseline/`.

---

## 1. The problem

P1 closed with a zero: no candidate base solved any task
(`reports/baseline/report.md`). `docs/ROADMAP.md:387-389` reads that as its pivot signal, whose
premise is *"expert iteration has nothing to bootstrap from"* — a claim about **ability**.

Derived from `reports/baseline/report.json`: of the 152 verdict-reaching source-B rollouts,
**142 never got a patch onto disk** (`no_diff` 43, `not_applied` 99), leaving **10** where the
held tests actually judged a fix. The 3B candidate applied **zero** patches across all 50 of its
covered rollouts.

**The measurement never reached the question the signal is read against.** P2 (`:393-406`) is
rejection sampling over strict-PASS rollouts; started now it would sample from bases whose output
mostly never becomes a patch, and its own pivot signal (`:405-406`) would fire on the same
unexamined premise.

**And nothing on disk can say why.** `NOT_APPLIED` is *"git refused it"*, full stop
(`verify/strict.py:171-183`, `verify/repo.py:100,108,118`) — it conflates a malformed diff, a
mis-anchored one, a correct diff with the wrong path prefix, CRLF endings, a budget-truncated
diff, and rarely an apply-time infrastructure failure. Raw generations were never persisted
(`bakeoff/scoring.py:432-435` consumes `completion` and drops it), so the 142 cannot be
attributed after the fact.

## 2. What is already decided upstream (not re-litigated)

| Decided | Where |
|---|---|
| The reward is a pytest exit status; no model on the reward path | `CLAUDE.md`, `docs/ROADMAP.md` § 2 |
| The generation contract is **not** a pinned input, and it moves the numbers | `PREREGISTRATION.md:333-354` |
| Any report publishing a governed figure states its contract and declares non-comparability | `PREREGISTRATION.md:356-361` |
| `UNVERIFIED` is never a win; coverage lowers rather than excludes | `PREREGISTRATION.md` § 2 |
| A zero or negative result is published as plainly as a positive one | `docs/ROADMAP.md:462-463` |
| `whetstone bakeoff` must not exist as a CLI subcommand | `bakeoff/run.py:7-13` |

## 3. Decisions taken in this slice

**D1 — This is a measurement-validity fix, not a third pivot response.** *(dig)* The roadmap names
two responses to P1's signal and forbids a third thing (a looser verifier). This slice adds
neither: it establishes whether the signal's premise was ever tested. **Consequence:**
`docs/ROADMAP.md` § 4 needs no insertion, which matters because `PREREGISTRATION.md` cites the
roadmap by line range and `tests/test_docs.py:809-851` asserts every range still resolves — the
roadmap is 618 lines and the highest cited range ends at 596, so any insertion above 596 would
break an append-only document's citations.

**D2 — Diagnose before fixing.** *(user decision)* Arm A instruments and re-runs the **existing**
contract before any format changes. Turns "142 unattributed" into a measured breakdown so the
format choice is evidence-led. Cost: one extra generation pass (~1.4h,
`reports/baseline/report.md:82`).

**D2a — Arm A is also a reproduction check, and that is free.** The P1 contract is greedy with no
seeds (`reports/baseline/report.md:91`), so re-running it over the same tasks must reproduce the
same outcome per `(candidate, task)`. If it does, determinism is demonstrated rather than assumed.
**If it does not, that is a finding that outranks everything else in this slice** and the slice
stops until it is explained.

**D3 — The new format is search/replace blocks.** *(user decision)* The model emits exact-match
old text → new text per file; the harness locates the anchor in the oracle source and computes the
unified diff. This removes hunk headers and line-number arithmetic — a documented cause
(`bakeoff/patch.py:43-53`) — while keeping output small enough that truncation stays rare. Whole-file
rewrite was declined: output size makes truncation the dominant failure, and P1 already skipped
tasks whose sources exceeded the character budget (`bakeoff/sources.py:143`).

**D4 — All three candidates over the full declared source-B set.** *(user decision)* 63 tasks × 3
bases, as P1 ran, so the new figures have the same shape (never the same basis — see D6).

**D5 — Raw generations are persisted, locally and gitignored.** Under a `/runs/` or
`/checkpoints/` path (`.gitignore:20-24`), never under `--out`: for source B the completions quote
the user's private donor code, and `--out` is committed. This is what makes every later contract
iteration replayable offline instead of costing another generation pass.

**D6 — Both arms publish into one new report directory, and the one-home guard is amended with an
argument.** `tests/bakeoff/test_report.py:961-994` pins the exact file list under `reports/`
because "a file extra means there is a second place a figure can live." The guard already moved
once — its own docstring records the move from "`reports/` is absent" to "three artifacts" when
slice 5 ran. It may move again **only** on the ground that the two directories measure **different
generation contracts** and are declared non-comparable, so neither is a competing home for the
same figure. The argument goes in the guard's docstring; a silent list extension is refused.

**D7 — A new dev subset, and it may not be the P1 one.** `ScoredDevSubset`
(`bakeoff/report.py:139-145`) refuses the build if a task the contract was developed against
reaches the scored set. The three P1 dev tasks were spent on the old contract; the new format needs
its own declared, excluded subset, and both exclusions must hold in the published denominator.

**D8 — `PREREGISTRATION.md` gains a § 10.4, Type 2.** It adds disclosures (the new contract, the
new dev subset, the non-comparability of the two reports, and whatever Arm A finds). It closes no
§ 7 item — in particular **not** § 7.3, which § 8.1 forbids closing after the measurement. It sets
no threshold and rewords nothing in § 1, § 4, or § 6. It needs a row in the log table at `:308-312`.

**D9 — The retrieval setting becomes a `GenerationContract` field.** `PREREGISTRATION.md:356-361`
names retrieval among the minimum a report must state, but today it is a hard-coded module constant
(`bakeoff/report.py:66-74`) and not a field (`:175-199`). Retrieval stays **oracle** in this slice —
this is a machine-readability fix so two contracts can be told apart programmatically, which is
what § 10.1 asks for.

## 4. Requirements

### R1 — Raw generations are persisted per rollout
Every rollout records the completion text, keyed by `(candidate, task_id)`, alongside the existing
journal record, in a gitignored location. Re-running extraction against a stored completion
produces the same `Extraction` as the live run did.

### R2 — Arm A reproduces P1 and attributes the 142
A run of the unchanged contract over the same 63 tasks × 3 bases reports, per candidate, the
outcome per `(candidate, task)` and a **cause breakdown** of every non-applying rollout, derived
from the stored completions — at minimum: no diff at all, diff present but unparseable, parseable
but did not apply, and truncated at the token budget. The per-`(candidate, task)` outcomes are
compared against `reports/baseline/report.json`, and any divergence is reported as a finding.

### R3 — The prompt asks for search/replace blocks
`rendering.py`'s `_RESPONSE_FORMAT` describes the new format, states the patch-scope rule exactly
as it does today (`rendering.py:100-104` — the same rule to every candidate, still never naming
which files are held), and the template's SHA-256 changes as a consequence.

### R4 — The converter turns blocks into a unified diff
Given a completion and the oracle sources, the converter produces a unified diff or an explicit
no-edit outcome. It never returns `""` — the empty string is charged FAIL at `patch-apply` and is
indistinguishable from a wrong fix (`bakeoff/patch.py:8-18`).

### R5 — **The converter is not credulous** *(adversarial — the centre of this slice)*
An edit naming a path in `task.test_blobs` is converted into a diff that **touches that path** and
handed on, so STRICT's `patch-scope` refusal fires (`verify/strict.py:524-533`) and the rollout is
counted `OUT_OF_SCOPE` — a caught reward-hacking attempt.

This is strictly harder than the passthrough rule it inherits
(`docs/planning/p1-baseline-bakeoff/generation/spec.md` AC5): the old extractor satisfied AC5 by
not modifying, while a converter **constructs** the diff. The oracle sources deliberately exclude
every held path (`rendering.py:151-161`), so the converter has no content to anchor against and the
natural implementation — skip what cannot be resolved — is exactly the silent repair AC5 forbids.
**A cheat P1 caught would become a cheat P2 never sees, with every existing test green.**

The test is watched failing against a credulous converter before the real one exists
(`CONTRIBUTING.md:56-60`), and it asserts the sub-verdict is `patch-scope` specifically, so a
refusal for an unrelated reason cannot read as a defence.

### R6 — Nothing on the reward path changes
No file under `src/whetstone/verify/` is modified. `GUARDED_ROOTS` is not widened. All new code
lands in `src/whetstone/bakeoff/`, already `EXEMPT` with a written reason
(`tests/test_reward_path_scope_is_partitioned.py:100-104`). A test asserts the verifier package is
untouched by this branch.

### R7 — The report declares its contract and its non-comparability
The new report's provenance block carries a prompt-template hash, the retrieval setting, the
sampler, the token budget, and an extractor version (`PREREGISTRATION.md:356-361`), and states
that its figures **may not be compared** with `reports/baseline/`. Both arms are published
together with the contract each was measured under.

### R8 — Figures live in exactly one home
The new report directory is the only home for its own figures; `reports/baseline/` is untouched and
keeps its own. No figure from either is restated in `CLAUDE.md`, `docs/ROADMAP.md`, the CHANGELOG,
or any planning document. `tests/bakeoff/test_report.py:961` is amended with the D6 argument in its
docstring.

### R9 — A zero is a publishable outcome
If yield stays zero with patches actually applying, that is the finding, and it is a **stronger**
result than P1's zero because the patches were graded rather than refused. It is what would then
justify the roadmap's named responses on evidence. No threshold is introduced
(`PREREGISTRATION.md:171`).

## 5. Acceptance criteria

Every one is a command that exits 0 or an artifact that exists.

1. `uv run pytest` green; `ruff check .`, `mypy src/`, `whetstone --help` all exit 0
   (`CONTRIBUTING.md:50`).
2. A test asserts a stored completion re-extracts to the same `Extraction` as the live run (R1).
3. A test asserts a held-path edit converts to a diff touching that path and that STRICT returns
   `patch-scope` — watched failing against a credulous converter first (R5).
4. A test asserts `src/whetstone/verify/` is unmodified relative to `origin/master`, and the
   reward-path guard and its scope partition still pass unchanged (R6).
5. `reports/<new>/report.md` and `report.json` exist, carry both arms, and carry the five contract
   fields plus the non-comparability sentence (R7).
6. `tests/bakeoff/test_report.py:961`'s list is extended **and** its docstring carries the D6
   argument (R8).
7. `PREREGISTRATION.md` § 10.4 exists with a log-table row, contains no placeholder and no
   proportion in any spelling (`tests/test_docs.py:554,577`).
8. Arm A's per-`(candidate, task)` outcomes are compared against `reports/baseline/report.json`
   and the comparison is reported (R2, D2a).

## 6. Risks

| # | Risk | Mitigation |
|---|---|---|
| R-a | **The converter silently repairs a scope violation**, turning a caught cheat into an uncaught one | R5, watched failing first; assert the specific sub-verdict |
| R-b | Arm A does **not** reproduce `reports/baseline/` | D2a — treated as a finding that halts the slice, not smoothed over |
| R-c | The new format moves the number, and it is read as a capability gain | R7's non-comparability; the report states the contract changed |
| R-d | Search/replace anchors fail to match (whitespace, duplicates) — a new failure mode replacing the old one | The cause breakdown (R2) is kept for the new arm too, so the failure is visible rather than folded into `not_applied` |
| R-e | Persisted completions leak private donor code | D5 — gitignored path, never under `--out`; a test asserts the path is ignored |
| R-f | Two report directories drift into two homes for one figure | D6's argument is the whole permission; if it cannot be made honestly, the slice publishes into `reports/baseline/` as a second contract section instead |

## 7. Out of scope

- **All of P2 proper**: no rollout loop, no rejection sampling, no LoRA, no training, no checkpoint.
- **Any change to `src/whetstone/verify/`** — the reward is untouched (R6).
- **Closing `PREREGISTRATION.md` § 7.3** (which base) — § 8.1 forbids closing it after the fact.
- **The held-out split** (§ 7.1) and the retry count `R` (§ 7.2) — both P3.
- **Re-minting the corpus** to remove donor names from task ids — the residual disclosed in
  § 10.3.
- **Fixing the stale `whetstone-next` / `whetstone-worktrees` skill files** — still recorded,
  still not this slice (`docs/planning/p1-baseline-bakeoff/prd.md:317`).

## 8. Self-critique

🔴 **The report-directory question is decided but not settled.** D6 permits a second directory on
a non-comparability argument, and R-f names the fallback. A reviewer could reasonably hold that the
one-home invariant should mean literally one directory, forever, and that both contracts belong in
`reports/baseline/` as labelled sections. **This is the strongest objection to the PRD and the
decision most worth overriding at the gate.**

🔴 **R2's cause taxonomy is asserted, not yet grounded.** "No diff / unparseable / did not apply /
truncated" is a plausible partition invented here, not one measured. Arm A may show the real causes
do not fit it. The taxonomy must be allowed to change once the data exists, and the plan should
treat it as provisional.

🟡 **The slice cannot prove the format was the binding constraint.** Even if yield goes non-zero,
the honest claim is "the previous figure was bounded by its harness", not "these bases can fix
bugs". D1 says this; the report must repeat it where the number appears.

🟡 **Arm A costs ~1.4h to answer a question the fix might not need.** If the breakdown shows one
overwhelming cause, the run paid for itself; if it shows four even causes, search/replace addresses
some and not others. Accepted knowingly (D2).

🟡 **No estimate is given for how long the whole slice takes.** Two generation passes plus
verification and control arms, on one machine, serialized. Stated as unknown rather than guessed.

⚪ Whether the retrieval setting should become a field (D9) is a small judgement call that could
equally be left as prose; it is included because § 10.1 names retrieval explicitly.
