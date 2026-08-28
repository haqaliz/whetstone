# PRD — the signed morning report (`whetstone report --last-night`)

**Unit:** `morning-report` · **Branch:** `feat/morning-report/aliz` · **Core-loop element:** ④
**Date:** 2026-08-28 · **Source:** `docs/planning/_card/issue.md`, `docs/planning/_card/understanding.md`

## Problem Statement

Whetstone's promise is *"you wake up to a measurably better private model"* (`CLAUDE.md`), and
`VISION.md:12` calls the thing you wake up to **a signed proof that the gains are real and the
model didn't cheat**. That artifact does not exist. A night writes a ledger, a dataset document
and per-draw evidence into a gitignored `runs/<id>/`; a gated evaluation writes a promotion
record into `runs/promotions/<id>.json`. Both print a disclosure to the terminal and then the
terminal scrolls away. **The evidence is durable and the proof is not.**

The cost of the status quo is specific, not aesthetic. An operator who ran a night last week has
no way to answer "what did it do?" without opening two JSON documents and knowing which fields
matter. And the project's demoable surface — the one sentence a reader outside this repository
would understand — is the one surface it has never built.

**Evidence this is the right next unit:** `docs/ROADMAP.md` § 12 (2026-08-26) pulled it out of
post-horizon (`:592-593`) and placed it *ahead of the dashboard*, because "the report writers,
ledger and gate record it renders already exist." The previous unit named it its own successor
and put it out of scope (`docs/planning/honest-number-report/prd.md:80`, `:222`).

**What it is not.** It is not a P4 exit criterion. If this is never built, the honest number is
still publishable from `reports/honest-number/`. This unit buys daily usability and the demo,
and the PRD says so rather than inflating it.

## Goals & Success Metrics

This unit **produces no figure about a model**, so it has no metric of that kind and must not
acquire one. Success is entirely property-shaped, and each property is a test:

1. `whetstone report --last-night` renders a durable note from a night's sealed evidence.
2. The note is **sealed to its evidence**: every figure carries the digest of the document it
   came from, and re-rendering from the same evidence reproduces it byte-for-byte.
3. Every honest-but-unflattering state renders as itself: a zero-strict-PASS night, a night with
   no gated evaluation, and a gate that returned `UNVERIFIED`.
4. Nothing leaves the box and nothing is published: the home is gitignored, the note carries
   hashes and verdicts and never task contents.
5. **It reads as a report, not a dump.** The markdown opens with a lede a human reads first —
   one sentence naming the night, what the reward kept over what was drawn, and whether a
   candidate exists — and its shape is pinned in a test, on the `night.disclosure` /
   `gate.disclosure` precedent (`night.py:349-382`, `gate.py:679-703`). Without this criterion
   every other one is satisfied by a JSON dump with a `.md` extension, which is the failure this
   unit exists to end.

## User Personas & Scenarios

**The operator (the ICP).** Ran a night before bed. In the morning runs one command and reads
one page: what was drawn, what the reward kept, whether a candidate exists, and — if a gate ran
— whether it promoted. They will not trust a gain they cannot check, so every number on the
page names the document it came from.

**The reader of the repository.** Wants to see what the product's output actually looks like.
Today there is nothing to show them between the terminal disclosure and the published P4 report.

## Requirements

### Must-have

1. **`whetstone report` subcommand**, with `--last-night`. This is the **fourth** documented
   function-local edge from a guarded root into the exempt `loop` package
   (`tests/test_reward_path_scope_is_partitioned.py:152-158`), on the
   `run_check_leakage_cli` template (`cli.py:815-844`). Both halves of the partition guard move
   test-first, and the `loop` exemption's prose ("exactly THREE documented edges", `:128`) moves
   with the constant.
2. **A fail-closed typed reader for the run ledger.** `ledger.read` (`ledger.py:211`) checks the
   schema and returns a raw `Mapping`; there is no typed reader. Every field this report renders
   is one an optimistic parse would default, and a defaulted count records nothing while
   succeeding — the reader refuses by name, field by field, in the `read_promotion_record`
   (`gate.py:902-917`) shape.
3. **The "last night" rule, stated and enforced.** The run id is operator-declared
   (`cli.py:328`) and `recorded_on` is *"an input, never the clock"* (`ledger.py:151`), so
   selection reads the greatest declared `recorded_on` across the runs root — **never mtime and
   never the clock**. A tie is **ambiguity refused by name**, telling the operator to name one
   with `--run`. An empty runs root is refused, never rendered as an empty morning.
4. **The report is a pure function of its evidence.** No clock, no filesystem ordering, no
   environment. It carries the night's own `recorded_on` and stamps no render date of its own —
   which makes byte-identity across invocations and across `PYTHONHASHSEED` 0/1 a property of
   the design rather than a thing to be careful about.
5. **Sealed-to-evidence, and `--verify`.** Every figure names the digest of the document it came
   from (the ledger's own bytes, the dataset digest, the checkpoint digest, the promotion
   record's digests). `whetstone report --verify <dir>` re-renders from the same evidence and
   refuses on any byte mismatch. The report's own text says it is **sealed to its evidence, not
   cryptographically signed** — the word "signed" is never used in a way that implies a
   signature this code does not produce.
6. **The unflattering states render as facts.**
   - A zero-strict-PASS night: the ledger's `checkpoint_absent` reason is rendered verbatim; the
     note says no candidate was produced. Never a blank section.
   - No gated evaluation: `--record` is optional, and its absence renders as *"no gated
     evaluation is recorded for this night"* — a fact, never an omission.
   - A gate that returned `UNVERIFIED`: rendered as **no comparison was made**, with both sides'
     counts. `UNVERIFIED` is never rendered as `PASS` and never as a win.
7. **The promotion record must belong to *this* night.** `--record` is optional, but a record
   that is present is checked against the night's **checkpoint digest** (corrected during the
   build: a record's `run_id` is the *gate evaluation's* name, never the night's — see
   `report-writer/plan_20260828.md`), and a mismatch is **refused by name, nothing rendered** — the `RunIdentityMismatch` posture the honest-number door already
   takes (`honest_report.py:83`). Rendering a gate decision from a *different* night beside this
   night's ledger is exactly the half-truth the previous unit spent an aspect refusing, and it is
   the most plausible operator error here: the gate's run id and the night's are both
   operator-declared strings.
8. **Coverage always travels with the count.** The training-set size never appears without the
   denominator and the unverified count beside it (`night.py:349-357`, `dataset.py:169-174`,
   `docs/ROADMAP.md:430-435`). This is the local surface of the same rule.
9. **The home is `reports/local/`, and its guard is the narrow one.**
   `.gitignore:16-23` pre-declares `/reports/local/` naming "the morning reports"; the one-home
   guard **already excludes it by name** (`tests/bakeoff/test_report.py:2076-2077`, `:2087`), so
   **the one-home guard does not move**. But `night._refuse_published_root` (`night.py:617-635`)
   refuses any path with a `reports` component and would refuse this unit's own home, so the
   rule is its narrower sibling: refuse a published root **except** the `reports/local/`
   carve-out, reusing `PUBLISHED` and raising `TranscriptNotPrivate` by identity, checked on the
   **resolved** path.
10. **Locality.** The note carries hashes, counts and verdicts and never task contents, prompts
   or completions. Proven by a canary that plants donor source text in the evidence and asserts
   it cannot reach either artifact. The documented home is asserted gitignored via
   `git check-ignore` (`tests/bakeoff/test_transcript_locality.py:31-40` precedent).
11. **The two stale claims are corrected in this unit** (user-confirmed): `cli.py:1-13` (says
    "four now do", omits `check-leakage`, and ends "There is still no report") and
    `README.md:229-230` (lists the promotion gate and the held-out split as ❌ Not built when
    both shipped in P3, and says "No tags, no PyPI package, no version" when v0.3.0–v0.10.0 are
    tagged and published to PyPI).

### Should-have

12. `--run <dir>` for naming a night explicitly — also the escape hatch a refused tie points at.
13. `--runs <root>` for where to scan, defaulting to `runs/`.

### Nice-to-have

14. Rendering the per-draw breakdown (`DrawRecord`) rather than only the totals.

## Technical Considerations

**Core-loop element ④.** The reward path is untouched: this reads JSON and renders text. It
imports no inference library and never will — and its CLI edge is function-local anyway, because
the argument is about the module graph of `whetstone verify` (`:511-515`).

**Artifacts.** `reports/local/nightly/<run-id>/` holding `report.md` and `report.json`. **Two
artifacts, not three:** a night produces no cost document, and an empty `cost.json` would be an
artifact asserting a measurement nobody made. `reports/local/` already holds `arm-a/` and
`budget-2048/` from the yield probe, so the `nightly/` namespace is load-bearing.

**Composition by identity** (the repository's standing rule — imported, never copied, asserted
`is` in a test): `read_promotion_record` and the gate's decision constants, `ledger.read` and
`LEDGER_SCHEMA`, `dataset`'s coverage definition, `night.PUBLISHED`, `TranscriptNotPrivate`, and
`sft.verify_checkpoint` where a checkpoint digest is re-hashed.

**Reward-hacking surface: none directly.** The report is strictly downstream of the reward and
no policy can reach it. The honesty analogue is what the requirements above are for: the failure
mode available *here* is a report that renders an unflattering night as a blank a reader fills
in optimistically, which is why every empty state has a named, tested rendering.

**Promotion-gate impact: none.** This unit reads the promotion record and never writes one, and
it cannot promote anything.

**Locality: nothing leaves the box.** No network, no egress, no cloud teacher.

## Risks & Open Questions

1. **The report becomes a second home for figures.** Mitigated by construction — it renders a
   *local run's own* counts, whose only home is that run's gitignored directory, and the one-home
   guard already carves `reports/local/` out with that argument. It must never restate a figure
   from `reports/baseline/` or any other published home; asserted.
2. **"Signed" over-promises.** Settled: sealed-to-evidence, stated in the report's own text.
   Residual risk is a reader quoting "signed morning report" as a cryptographic claim; the
   mitigation is the sentence in the artifact itself, not a note in a planning file.
3. **The evidence this renders has never existed.** No night and no real gated evaluation has
   run (`CLAUDE.md` status block), so every test here uses fixture ledgers, fixture datasets and
   fixture promotion records. The finding must say so. This is the gate's own posture and is
   disclosed rather than discovered.
4. **A tie on `recorded_on` is plausible, not theoretical** — two nights declared on one date is
   an ordinary thing an operator does. The refusal is the feature; it must be watched failing.
5. **Scan-time evidence integrity, decided out loud.** A run directory with no ledger, or with a
   ledger the fail-closed reader rejects, is **refused by name during the scan — never skipped**.
   Skipping would make a corrupt or killed night *invisible* to the one command whose job is to
   say what happened last night, and the operator would read a clean report about the wrong run.
   An empty runs root is likewise a refusal, not an empty morning.
6. **What "sealed" is actually worth, stated rather than implied.** `--verify` proves the report
   matches the evidence on disk. It does **not** prove the evidence matches the run: a hand-edited
   `ledger.json` re-renders to a consistent report, because the ledger is not self-sealing. The
   one thing that *is* re-derivable from bytes is the checkpoint, via `sft.verify_checkpoint`.
   The report must state this boundary in its own text — the alternative is a document whose
   claim to be "sealed" is larger than what it can check, which is the precise failure this
   project names in everyone else's work.
7. **Open: no operator runbook is planned.** Every prior unit shipped one with a guard, but
   those script GPU passes and multi-step chains with ordering hazards. This is one invocation,
   no spend, no ordering hazard; a sheet would restate `--help` and a guard would pin a sheet
   nobody needs. Flagged for the review gate rather than decided silently.

## Out of Scope

- **The Next.js dashboard** — post-horizon (`docs/ROADMAP.md:588-593`).
- **Any published `reports/` directory, any § 10 amendment.** This unit publishes no series;
  `PREREGISTRATION.md` § 10 discloses published series and gains no row.
- **Running a night or a gate.** Operator GPU passes are the operator chain
  (`docs/ROADMAP.md:652-656`).
- **Re-scoring, re-verifying or re-deriving any verdict.** The report reads verdicts; it never
  produces one.
- **Trend rendering across nights** — the verified-gain trend is the dashboard's, and a trend
  across nights measured under different contracts is a comparison this project would have to
  argue for separately.
- **A looser verifier, an LLM-judge reward, base-model training, data egress** — guardrails, not
  scope.

## Aspects

| Aspect | Boundary |
|---|---|
| `night-evidence` | The fail-closed typed ledger reader and the last-night resolution rule, with every refusal named |
| `report-writer` | The pure render: markdown + json, the honesty rules, digests carried, determinism |
| `local-home` | The `reports/local/` carve-out predicate, the gitignored-home assertion, the locality canary |
| `cli-door` | The `whetstone report` subcommand, the fourth partition edge, `--verify`, and the two doc corrections |
