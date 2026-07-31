# Aspect spec — `report`

**Parent PRD:** `docs/planning/p1-baseline-bakeoff/prd.md` (M7, M7a, M7b, M8, M12, § 6).
**Sequence:** third. Consumes `scoring-harness`'s records; its output is what `the-run` commits.

## Problem slice

This is the first artifact in the project that makes a claim about a model, and a pre-registration
is already committed that binds what may be claimed. There is **no schema for it anywhere** —
`docs/ROADMAP.md:354` ("A baseline bake-off report exists under `reports/baseline/`") is the entire
committed specification. So this aspect defines the schema *and* the tests that hold the
pre-registered contract shut, before any number exists to be tempted by.

## In scope

1. **The report schema and writer** — deterministic serialisation of the record set into
   `reports/baseline/`, per PRD § 6's field table.
2. **The selection rule (M7a)**, implemented as code, not applied by hand: highest STRICT-PASS count
   on the declared source-B set; ties to the smaller model; **zero across all candidates ⇒ no base
   selected, § 7.3 stays open, pivot signal reported as fired**.
3. **The derived figures**: `solved` (STRICT `PASS` only), coverage, `N`, the unverified rate, the
   `patch-apply` count — each over its denominator.
4. **The provenance block (M8)**: the five pinned inputs of `PREREGISTRATION.md:131-132` plus the
   generation contract (prompt hash, sampler, max tokens, extractor version) which is *not* among
   them and is disclosed as such.
5. **The contract tests** — the substance of this aspect.

## Out of scope

- Running anything, or producing a real number — aspect 4.
- Editing `CLAUDE.md`, `docs/ROADMAP.md`, `CHANGELOG.md`, or `PREREGISTRATION.md` — aspect 5.
- Any dashboard or rendering beyond a committed document.

## Acceptance criteria (written first)

All of these run against a **synthetic** record set. None requires a model.

**AC1 — the report declares which measurement it is.** *(the load-bearing one)*
The written report states, in text the test matches, that it is **base selection** and **not** the
pinned baseline of `PREREGISTRATION.md:126-128`, and that "measured once, re-measured never"
(`:129-132`) is **not** spent by it. A report missing either statement fails the build.

**AC2 — the P4 headline skeleton is refused.** *(adversarial)*
The report must **not** contain the `PREREGISTRATION.md:69-72` shape (`+a of b held-out tasks …` /
`coverage e of b     N: …`), and must not use the phrase "held-out" to describe its own scored set.
Instantiating the headline's template would dress a selection number in the P4 headline's costume —
the substitution the pre-registration exists to prevent. Test asserts absence.

**AC3 — no threshold, ever.** *(adversarial)*
Given a record set, the writer emits a ranking and never a bar. A test asserts the output contains
no minimum-to-qualify claim, per `PREREGISTRATION.md:171` ("none may be added once a number
exists"). Watched failing against a deliberately threshold-carrying template.

**AC4 — `UNVERIFIED` lowers coverage and never leaves the denominator.** *(adversarial)*
Given records containing unverified tasks, coverage falls and the denominator is unchanged; the
unverified tasks appear in **neither** the solved nor the failed count. A writer that dropped them
would produce the hundred-out-of-hundred-by-construction lie `PREREGISTRATION.md:111-114` refuses by
name. Watched failing.

**AC5 — every count carries its denominator; nothing is a bare proportion.**
Asserted over the rendered text (`PREREGISTRATION.md:157`).

**AC6 — `N` is computed and framed exactly as pre-registered.**
`N := count(WEAK == PASS and STRICT == FAIL)` (`:99`), rendered with the verbatim sentence
*"N rollouts a weaker check would have scored as wins."* (`:102`), with **no intent claim**, beside
the residual bound — cheats 6 and 10 survive, *"`N` counts what the strictness caught. It is not a
claim that nothing got through."* (`:211-220`) — and labelled a **baseline `N`** with no final `N`
in existence (`:107-109`).

**AC7 — source A is per-instance, funnel first, never a rate.** *(adversarial)*
The report names `pallets__flask-4045`, places the four-gate funnel (1 of 300; 299 refusals;
192 / 106 / 1) **before** its result, and states no rate and no delta for it
(`PREREGISTRATION.md:149-155`). Watched failing against a template that reports source A as a
proportion.

**AC8 — both sources in one document.**
A report carrying only one source fails (`PREREGISTRATION.md:142-143`).

**AC9 — the selection rule is total, including the degenerate case.**
Three property-style cases: a clear winner is selected; a tie selects the smaller model; **all-zero
selects nothing, leaves § 7.3 open, and records the pivot signal as fired**. The third is the one
that must not be an afterthought.

**AC10 — cross-candidate figures carry the non-comparability sentence, or are not presented as
comparable.** Candidates differ in model revision, a pinned input (`:131`), so any side-by-side
presentation carries the sentence at `:136-137` (`PREREGISTRATION.md:136-138`).

**AC11 — the provenance block is complete.**
All five pinned inputs plus the generation contract; a report missing any field fails.

**AC12 — the writer is deterministic.**
The same record set and the same pinned inputs produce a **byte-identical** payload across runs and
processes.

**AC13 — no figure about a model leaks into the wrong file.**
`docs/ROADMAP.md` still satisfies its own `:7-9` blockquote and `PREREGISTRATION.md` still contains
no `%`/`percent`/`percentage` (`tests/test_docs.py:528-542`). The report is the only home.

## Dependencies & sequencing

- Depends on `scoring-harness`'s record shape (AC6 there guarantees both verdicts per rollout).
- Blocks `the-run`.
- `reports/baseline/` is committable today: `.gitignore:16-24` ignores only `/reports/local/`, and
  `_reports_without_preregistration` (`tests/test_docs.py:173-185`) short-circuits because
  `PREREGISTRATION.md` exists.

## Open questions / risks

- **Format**: a committed Markdown document with a machine-readable JSON sidecar is the obvious
  shape (the repo's ledgers are JSON; the claim needs prose). The tests should bind the *content*,
  not the prettiness.
- **The `UNVERIFIED` collapse reading** (PRD open question 1): this report takes the gate-scoped
  reading and **states it**, publishing per-candidate coverage and unverified counts rather than
  collapsing the whole bake-off. If a reviewer disagrees, the fix is prose in the report, not a
  changed number.
- The report must also record the held-out clash (D4) and the network disclosures (D6, S1) — content
  requirements, testable as presence.
