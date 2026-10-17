# PRD — raise-k

**Unit:** `feat/raise-k/aliz` · **Written:** 2026-10-17 · **Type:** feature, off the reward
path. **Source:** the inline brief (`docs/planning/_card/issue.md`); no GitHub issue exists.

## Problem Statement

The nightly loop draws a fixed, pre-committed number of seeded attempts per task per night:
`K = 8`, declared at `src/whetstone/loop/sampling.py:79` and deliberately not a flag. P2's
pivot signal — *"if strict-PASS yield is ~0 across the corpus there is no training data"*
(`docs/ROADMAP.md:415-416`) — has fired, and the roadmap pre-committed two responses:
**stratify by difficulty** (tested and exhausted, night #4, `docs/ROADMAP.md` § 13) and
**raise k**. The third lever the arm has, the portability runtime's CPU dtype, shipped
(`PREREGISTRATION.md` § 10.18). So raise k is the **last untried pre-committed response**
(`docs/planning/whole-function-edit-finding/measurement-run/finding.md` § 6).

`docs/ROADMAP.md:775` states the shape plainly: *"Raising k remains untried: `K = 8` is a
declared constant and never a flag, so a change is a Type 1 amendment rather than an
operator's choice."* `src/whetstone/loop/sampling.py:69-78` already anticipates exactly this
edit: *"Raising it is the roadmap's named response to low yield … as an edit to this line, in
a diff, before a night, never as an argument on a command."*

The loop's yield is **clustered, not uniformly thin**: night #1 selected 6 strict-`PASS`
examples, 4 of them from a single task that solved 4 of its 8 draws while 47 of 49 other
verifiable tasks solved none (`docs/STATUS.md:1713-1716`). Raising `K` multiplies the yield
of exactly the tasks the base can already reach — which is the mechanism this change buys.

**This is a declaration-and-record unit, not a measurement.** The night that would test a
raised `K` is operator-run and is *not* built here. This unit changes the constant, pins it,
pre-registers it, corrects the prose that names the old value, and leaves the reward path
byte-identical — the `portability-cpu-dtype` shape (`docs/planning/portability-cpu-dtype/`).

**The honest demotion, stated up front.** `docs/ROADMAP.md:1017-1018` demotes raise k: *"It
buys more samples from a pipeline where most patches never apply; M1 is the same compute
spent on the cause."* That demotion assumed M1's cause-lever — the patch representation — was
available; it is now measured NO-GO in all three forms (`docs/ROADMAP.md:908-920`). Raise k
is therefore the honest remainder, **not a strong lever**, and this unit claims no yield.

## Goals & Success Metrics

Success is a merged, green tree — **not a yield**:

- **The declaration moves, and is pinned.** `sampling.K` is `16`, asserted as a module
  constant in the shape of `DEVICE_PRECISION` (§ 10.18) and of its own existing guard.
- **The budget is attributable.** The night's ledger records the draw budget
  (`ledger.py:403`, `draws`) by identity from the constant, so a raised `K` is visible in the
  evidence; **no schema bumps.**
- **The change is pre-registered.** A new **Type 1** `PREREGISTRATION.md` amendment (§ 10.19)
  pins the new value, supersedes § 10.9's `sampling.K = 8`, and states the non-comparability
  of every prior figure — committed **before** the night that records the new budget (§ 8.1).
- **The prose stops lying.** Every live sentence that names `K = 8` is corrected
  (`docs/ROADMAP.md:775` gets a dated correction blockquote; the inert test docstrings updated).
- **Nothing else moves.** `src/whetstone/verify/`, `tasks/`, the held-out document and the
  gate rule are byte-identical; the reward stays execution-grounded; `UNVERIFIED` is still not
  a win.
- **No number is claimed.** This unit measures nothing. Whether a higher `K` yields a
  strict-`PASS` is decided by the operator's night — and *"accept the finding"*
  (`docs/ROADMAP.md:790`) remains a legitimate outcome.

## User Personas & Scenarios

- **The founder/operator running the nightly loop.** Wants the loop to get the most training
  examples out of the tasks its base can already solve, before spending a night. Scenario:
  land the raised `K` and its pre-registration, then run the next 32B night under it and let
  the gate decide whether the bigger training set bought anything.

## Requirements

### Must-have

- **M1 — the declaration.** `sampling.K == 16` (`src/whetstone/loop/sampling.py:79`). A test
  pins the exact value, watched failing against `K = 8` first. The existing guard
  (`tests/loop/test_sampling.py:202-226`) keeps its `isinstance`/`>= 2` check and its
  `run_night` default-`is`-`K` assertion.
- **M2 — the budget is not a flag, and cannot become one.** Extend the no-flag guard: the
  `run` subcommand must offer **no** option that sets the draw budget — `--k` today (already
  asserted) **and `--draws`** (not asserted; the dig found the hole). Watched failing against
  a planted `--draws` on the parser.
- **M3 — the budget reaches the evidence.** A test asserts the night's ledger records the
  declared `K` (`Ledger.draws` is `K` for a night that did not pass a `draws` override), so a
  night cannot record a budget it did not draw. No schema version changes.
- **M4 — `K` is deliberately NOT a gate comparability key.** Unlike § 10.18's `precision`,
  the draw budget must **not** enter `Backend` / the gate's whole-dict `==`: the gate must be
  able to compare a higher-`K` candidate against a lower-`K` incumbent — that comparison *is*
  the experiment. A test asserts `K`/`draws` does not appear in the `Backend` record and that
  a candidate and incumbent differing only in draw budget are not refused on that account.
- **M5 — the amendment.** Append `### 10.19 <title> — 2026-10-17` to `PREREGISTRATION.md` in
  the § 10.18 (Type 1) shape: the bold `**Type 1 (§ 8.1): …` line, **What changes** (8 → 16),
  **The blast radius**, a comparability paragraph ending *"the old series is not extended"*,
  and a closing **What is not claimed.** paragraph. It must state plainly that **§ 10.9's
  `sampling.K = 8` was the value in force and is superseded here** (its text is preserved
  byte-intact — the document is append-only). Append the matching 4-column amendment-log row.
- **M6 — the missing doc↔code cross-pin.** Add the cross-pin the dig found absent (unlike
  `DEVICE_PRECISION`): a guard asserts the code constant equals the value § 10.19 names
  (`sampling.K == 16`, and `f"sampling.K = {sampling.K}"` appears in the supersession
  sentence), so the document and the constant cannot drift.
- **M7 — the prose sweep.** Add a dated `> **Corrected 2026-10-17 …**` blockquote to
  `docs/ROADMAP.md` § 13 preserving the old sentence (`"Raising k remains untried … `K = 8`"`)
  and naming § 10.19 — never an in-place edit (the § 10.18 precedent). Update the inert test
  docstrings that name `sampling.K = 8` to the new value
  (`tests/test_docs.py:735`, `tests/bakeoff/test_report.py:2065,2159`,
  `tests/bakeoff/test_transcript_locality.py:126`).
- **M8 — § 10.9's guard.** `tests/test_docs.py:748-751` asserts the literal `"sampling.K = 8"`
  in `PREREGISTRATION.md` § 10.9. Because § 10.9's body is preserved, that string survives;
  the guard must be **updated so it no longer reads as a current commitment** — assert the
  § 10.9 disclosure is present *and superseded by § 10.19*, with the current value cross-pinned
  via M6. The three-part § 10.9 assertion must not be silently weakened.

### Should-have

- **S1 — the changelog and status.** A `CHANGELOG.md` entry under `Unreleased` and a
  `docs/STATUS.md` entry, written in the same commit that lands the change (the repo's
  write-up rule). `docs/STATUS.md` is append-only; the new entry goes at the top.
- **S2 — no `reports/` movement.** The 21-file `reports/` list is unchanged; no new home,
  no new figure (`tests/bakeoff/test_report.py`).

### Nice-to-have

- **N1 — the `_card` note.** `docs/planning/_card/issue.md` quotes the old value as the brief;
  leave it (it is the brief as given), or note the landed value. Planning docs are historical
  once merged.

## Technical Considerations

- **The change is one constant.** `K` flows `sampling.py:79` → `night.py:200` (`draws: int = K`)
  → `night.py:378/413` → `ledger.py:403` (`"draws"`). No plumbing changes.
- **The enforced failure surface is one test.** `tests/test_docs.py:750` pins the literal in
  § 10.9; the rest of the `sampling.K = 8` occurrences are inert docstrings or history.
- **Do not touch (append-only / published):** `CHANGELOG.md:1019`, `docs/STATUS.md` old
  entries, `docs/ROADMAP.md:419` (a dated blockquote), every merged `docs/planning/**` dir,
  and `reports/portability-arm/report.md` (measured under `K=8`).
- **The reward path does not move.** Nothing under `src/whetstone/verify/`, `tasks/`, the
  held-out document, or the gate rule changes; the AST reward-path guard stays green.

## Risks & Open Questions

- **It resets a series for a possible zero.** Raising `K` makes every prior loop figure
  non-comparable (§ 10.19 is Type 1). A night that yields nothing spends a fresh series to
  confirm what § 14 predicted. This is the honest cost and the reason the amendment claims no
  yield. **Mitigation:** declared, not derived; *accept the finding* is pre-committed.
- **Cost scales linearly.** `K` multiplies generation while the control arm's cost does not
  (`docs/planning/p2-rollouts/night-door/runbook.md:230-231`); night #1 was 62 tasks × 8 draws
  ≈ 496 rollouts over 26.6 h (`docs/STATUS.md:1708`). A K=16 night is ~2× that. Bounding the
  testing night (task subset) is **out of scope** — it would conflate the `K` axis with the
  task-set axis night #4 already tested and exhausted — and is the operator's call.
- **§ 13 vs § 10.9 — resolved, with the reasoning on the record.** § 13 calls a `K` change a
  Type 1 amendment; § 10.9 (a Type 2 disclosure) says the sampler contract "is not a pinned
  input." Resolution taken (user-confirmed): the two describe different comparisons. § 10.9 is
  about the baseline-vs-final delta *within one series* (both sides share the contract);
  § 13 is about the constant being pre-committed in a diff before a night, and a change to it
  starting a new series. § 10.19 takes § 13's Type 1 label and states the non-comparability.
- **Open — the "Closes an open item" log column.** § 10.18 (also a Type 1 input-pin that
  closes no § 7 item) records `Yes`. `raise-k` likewise closes no § 7 item and leaves M1's
  exit criterion open. Default to the § 10.18 precedent (`Yes`); flagged for the review gate.
- **Open — how far the prose sweep reaches.** Precedent (§ 10.18) corrects `docs/ROADMAP.md`
  § 13 only; § 14's M1 blockquotes name raise k as untried inside *dated* corrections and are
  left as historical records. Confirm this is enough, or add a 2026-10-17 note there too.
- **Open — S1 status wording.** Whether `docs/STATUS.md`'s new entry may name M1's exit
  criterion as *still open* (it must — no night has run).

## Out of Scope

- The night itself, the § 3 baseline spend, producing a candidate, running the gate.
- Any task-subset or runbook change to bound the higher-`K` night.
- Any reward-path, gate-rule, held-out-document, or corpus change. No schema bump. No new file
  under `reports/`.
- Any change to `sampling.TEMPERATURE`, `TOP_P`, or the sampler shape — only the budget moves.
- Any claim about yield, speed, or a checkpoint.

## Acceptance criteria (testable, written first)

Each is a test that fails on the current tree and passes after the change (`uv run pytest`
green on the branch):

1. **AC1 (M1).** `tests/loop/test_sampling.py`: a test asserts `sampling.K == 16` (exact),
   watched failing against `8` first.
2. **AC2 (M2).** The no-flag guard fails against a planted `--draws` (and `--k`) on the `run`
   parser, then passes with neither present. `_cli_flags()` is reused by identity.
3. **AC3 (M3).** A test asserts a night's `Ledger.draws` equals `sampling.K` (no override),
   so the recorded budget is the drawn budget.
4. **AC4 (M4).** A test asserts `draws`/`K` is absent from `Backend.recorded()` and that the
   gate's `refuse_cross_backend` does not refuse a pair differing only in draw budget.
5. **AC5 (M5, M6).** `tests/test_docs.py`: a guard pins § 10.19's shape (Type 1 line, the
   `8` → `16` move, the non-comparability sentence, the § 10.9-supersession sentence, the
   log row) **by interpolating `sampling.K`**, so code and doc cannot drift.
6. **AC6 (M7).** A guard asserts `docs/ROADMAP.md` § 13 carries a dated correction naming
   § 10.19, and that no live (unquoted) sentence still says `"Raising k remains untried"` or
   `"K = 8"`. The inert test docstrings are updated (not asserted).
7. **AC7 (M8).** The § 10.9 guard now asserts the disclosure is present **and** superseded,
   with the current value cross-pinned; the three § 10.9 substrings remain asserted.
8. **AC8 (guardrails).** `tests/test_no_inference_on_reward_path.py` and the reward-path
   suites stay green; a source-level assertion that `src/whetstone/verify/` and `tasks/` are
   unchanged holds (the diff touches neither).
9. **AC9 (S2).** The 21-file `reports/` list is unchanged; no new home and no new figure.

## Aspect decomposition (proposed)

1. **`declaration`** — `sampling.K` → `16`; AC1, AC3, AC4; the `--draws` no-flag widening
   (AC2). Owns the RED for the constant and the parser guard.
2. **`amendment`** — `PREREGISTRATION.md` § 10.19 + log row; the doc↔code cross-pin; the § 10.9
   guard update; AC5, AC7. Depends on `declaration` (it pins the constant by name).
3. **`prose`** — `docs/ROADMAP.md` § 13 dated correction + guard; the inert test docstrings;
   `CHANGELOG.md` + `docs/STATUS.md`; AC6, AC9. Lands last, in the same commit as the
   write-up rule requires.

Sequencing: `declaration` first; `amendment` depends on it; `prose` last. Size: small — one
constant plus an amendment, guards and pinned prose, in the § 10.18 template.

## Self-critique — areas to strengthen before sharing

Scores: Problem Definition 🟢 · Scope Clarity 🟢 · Feasibility 🟢 · Success Metrics 🟡 ·
Edge Cases & Risks 🟡 · User Understanding 🟡 (the "user" is the solo operator, validated by
the roadmap rather than by a person).

**Gap 1 (🟡) — M2's refusal must be scoped to the `run --night` parser, or it will break the
probe.** The probe legitimately *narrows* the night's draws (`ledger.py:226` — *"`sampling.K`
unless a probe narrowed the night"*), and that narrowing is internal, never a CLI flag. M2's
wording ("the `run` subcommand must offer no option that sets the draw budget") is correct
but must be pinned to `subparsers[0].choices["run"]` in `_cli_flags()` — not a repo-wide flag
ban. *Fix applied in the ACs:* AC2 names the `run` parser explicitly.

**Gap 2 (🟡) — M4 is a deliberate divergence from the § 10.18 precedent and should say so.**
§ 10.18 made the moved input (`precision`) a gate **comparability key** so the gate *refuses*
a cross-value pair. `K` must do the opposite: the gate must *permit* a higher-`K` candidate
against a lower-`K` incumbent, because that comparison is the experiment. The PRD states the
reason, but a reviewer could read the asymmetry as an omission. *Fix:* flagged for an
explicit review-gate decision; downgraded to a should-have so it cannot block the core
declaration if it proves to need its own unit.

**Gap 3 (🟡) — the value `16` is asserted, not derived, and the PRD should say so in one
line.** There is no observed unverified or yield rate to size a new `K` from (exactly the
situation `R = 3` was declared into, § 10.8). `16` is the user's product call — the smallest
step that doubles the clustered yield — and the amendment must say "declared, not derived."

**Areas to strengthen before sharing** are recorded above; none is a 🔴 blocker.

**The question I'd want answered before greenlighting this:** the roadmap *demotes* raise k
(`docs/ROADMAP.md:1017-1018`) and no night has ever run at a higher `k`. What is the single
strongest piece of evidence that a `K=16` night won't simply reproduce the zero? If the only
answer is night #1's clustering on *one* task, is one observation enough to justify spending
a non-comparable series — or should raise k ride *behind* M2's first clean-candidate gate
decision, so the higher-`K` night is spent only once the gate can actually score it?
