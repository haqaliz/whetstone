# PRD — edit-contract-finding

**Slug:** `edit-contract-finding` · **Branch:** `feat/edit-contract-finding/aliz` · **Written:** 2026-09-30
**Sources:** `docs/planning/_card/issue.md` (the `whetstone-next` handoff brief, verbatim),
`docs/planning/_card/understanding.md` (this unit's dig). **Roadmap position:** M1 of
`docs/ROADMAP.md` § 14 as the follow-on of the `patch-representation` unit (issue #64): the
finding's § 6 lead. **Core-loop element:** ② the nightly improvement loop — the generation
contract that produces rollouts. It touches ① only at the seam where an edit becomes the patch
STRICT grades, and ① itself does not change.

No figure about a model is stated in this document. Each is pointed at its one home.

---

## 1. Problem statement

A night trains only on strict-`PASS` rollouts, and five nights across three base sizes selected
none (`docs/ROADMAP.md` § 13, § 14). The largest single cause of a rollout never being graded is
that **git refuses the diff the model wrote** — the model decides what to change and then fails
to *transcribe* it: unified diff requires reproducing surrounding context lines and computing
line offsets from memory. The `patch-representation` unit measured the first candidate direction
— search/replace — and got **NO-GO**: over the pinned base's 37 refused rollouts, a minority
quote the file exactly and the majority are near-misses of contiguity (real lines with lines
skipped, indentation shifted, the model's own edit quoted as the original). Exact-anchor
formats cannot forgive those near-misses without the harness choosing the model's answer
(`docs/planning/patch-representation/finding.md:10-49`; the M10 doctrine,
`docs/planning/patch-representation/prd.md:117-121`).

The finding names the one direction its evidence does not rule out (`finding.md:84-92`): **a
representation that never asks the model to quote existing code at all** — the prompt shows a
**numbered source listing**; the model addresses **line ranges** and writes replacement text;
the **harness** renders the diff. It is a lead, not a proposal: "it would need its own finding
before any amendment". This unit is that finding.

**The decisive difference from locatability: there is no stored evidence.** The locatability
instrument classified a *finished* run's transcripts; no run has ever prompted under a
numbered-listing contract. This unit must therefore spend a **small real bake-off** on the
pinned base under the new prompt, then classify its output — with the rule and the population
fixed and committed **before** any rollout runs, mirroring the locatability spec's discipline
(`docs/planning/patch-representation/locatability-finding/spec.md`).

## 2. Goals and success metrics

| Goal | Measured by | Home of the figure |
|---|---|---|
| G1 — the rule and its population are fixed and committed before any rollout runs | the `measurement-run` spec, committed ahead of the operator's run | committed spec in `docs/planning/edit-contract-finding/measurement-run/spec.md` |
| G2 — the unit's *code* is complete and green: instrument, rule, driver, runbook, tests | the aspect's tests pass; the diff touches nothing under `verify/`/`tasks/` and leaves `rendering.py`/`run.py`/`night.py` byte-identical | test suite + git history |
| G3 — the *measurement* is taken: the operator's pass ran, the control arm intact, and the finding written | the run's evidence in gitignored `runs/edit-contract-finding/`; the committed finding states the decision, not the count | the finding (a separate commit from the capability, per the `measured-arm-run` precedent — code ships, the operator's pass follows) |
| G4 (on GO only) — an alternative edit contract that cannot widen the cheat surface | adversarial tests in the contract aspect all pass | test suite |
| G5 (on GO only) — the contract is pinned before any night uses it | `PREREGISTRATION.md` § 10.17 merged before any night records `edit_format = line-range` | git history |

**No yield target is set.** This unit does not claim, predict or target any strict-`PASS`
count. Whether the new contract produces training data is the question the *next* night answers,
under § 10.17, in its own non-comparable home.

## 3. User and scenario

The founder-operator running nights, and behind them the ICP: an engineer who wants a model
measurably better at their own tasks by morning, privately, and will not trust a gain they
cannot check. Today that engineer's nights end with an empty training set and rollouts that die
at the transcription step, not at the reasoning. After this unit: the operator knows — on a
measurement, not a hope — whether a numbered-listing contract removes the quoting burden, and a
GO decision carries a contract designed so the verifier is byte-for-byte unchanged and the
cheat surface does not widen.

## 4. Requirements

### 4.1 Must — the measurement (aspect `measurement-run`)

- M1. **A numbered-listing renderer, off the reward path.** Renders each oracle source file at
  the task's `base_commit` as a numbered listing (1-based line numbers), followed by a
  response-format section asking for `EDIT` blocks: a path line, a line range, and replacement
  text. Byte-deterministic (same rule as `rendering.py:25-36`), stdlib-only, lives in
  `whetstone.bakeoff` — never under `verify/`/`tasks/`, never imported by them
  (`tests/test_no_inference_on_reward_path.py:104-109`; the partition guard).
- M2. **A parser for the measurement format.** Reads `EDIT` blocks from a completion; a
  malformed block (missing path, missing range, unclosed replacement) is a **named refusal
  class**, never repaired, never skipped while others proceed.
- M3. **The measurement driver.** `python -m whetstone.bakeoff.measure` (bake-off-style
  module, deliberately not a `whetstone` subcommand — same reason as `run.py:7-13`): reuses the
  existing machinery — provisioning, sandboxed verification, the journal/transcript codecs, the
  generator seam, the control arm — but renders the numbered-listing prompt instead of the diff
  prompt. **The reuse seam is named: `scoring.score` renders the prompt by a direct call
  (`scoring.py:359-451`); the driver threads a renderer parameter whose default is
  `render_prompt` itself, so every existing caller's behaviour is byte-identical and only the
  measurement run supplies the numbered-listing renderer.** Flags: `--tasks`/`--stratum` (by
  committed document), `--weights`, `--only`, public pool/funnel, `--workspace`, `--journal`,
  `--transcript`, `--out` (report optional; counts never published into `reports/`). One greedy
  attempt per task (`K = 1`), retries 0. **The standard diff path (`rendering.py`, `run.py`,
  `night.py`) is byte-identical when this aspect lands** — a NO-GO must leave it untouched, and
  the driver's renderer is not reachable from the night.
- M4. **The control arm is required.** The driver refuses to produce evidence if the control
  arm is not intact on every draw (the `sweep.rankable` gate, `sweep.py:160-183`): a verdict
  about a verifier that graded nothing is no verdict.
- M5. **The addressability instrument.** Offline, stdlib-only, deterministic, no model — the
  `locatability.py` shape (`locatability.py:1-25`), reading the run's journal + transcript.
  Per-rollout classes, **worst-first**, fixed in the spec before the run:
  `UNCLASSIFIED` (evidence unreachable; stays in the denominator) → `MALFORMED` (no `EDIT`
  block could be parsed) → `NO_FILE` (named path absent at `base_commit`) →
  `OUT_OF_RANGE` (range start > end, start < 1, end > the file's line count, or ranges on one
  file overlap) → `ADDRESSABLE` (every block's range names existing, non-overlapping lines,
  and every replacement text parses as Python — `ast.parse`, a **syntax-only proxy**, never a
  semantics check). Sub-counts, reported beside the partition and never decisive: replacements
  that parse but the file would not import; and blocks addressing a path outside the oracle
  listing's set (e.g. a test file the model could not have been shown) — classified by file
  existence at `base_commit`, counted, and described in the finding.
- M6. **The decision rule, fixed before the run, exposed as a command exit.**
  `python -m whetstone.bakeoff.addressability` exits **0 GO / 1 NO-GO / 2 refused** (the
  `check-probe`/`locatability` convention, `locatability.py:250-254,305-306`).
  **GO iff `count(ADDRESSABLE) * 2 > population`** — the strict-majority inequality inherited
  from locatability. Population = every rollout of the measurement run for the pinned candidate
  `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` (§ 10.10) over the stratum's easier band,
  minus the held-out document's members. Refusal exits for: missing evidence, candidate absent
  from the journal, empty population, unreadable corpus — each naming the reason.
- M7. **The population is pinned by the spec before the run.** The spec names the stratum
  document by digest, the held-out document by digest, the subtraction rule (a held-out member
  is never a rollout target — the night's own exclusion, `night.py:238-249`), and the exact
  member list the run must consume: **16 tasks** (19 easier-band members minus 3 held-out
  members — the overlap is `donor-a-6884ed72a9e9`, `donor-a-c6e4d4c4de87`,
  `donor-a-c7cee63e3cab`). A run whose task set differs from the pinned list is refused.
- M8. **The run is the operator's GPU pass, commanded from a runbook** (the
  `measured-arm-run` precedent). Cost bound from committed metadata: ≈ 258 s/task generation on
  the 32B (`reports/larger-base/cost.json`; `reports/larger-base/report.md:26`), so 16 tasks
  are roughly 45–60 minutes of generation plus control-arm and verification time. The runbook
  is guarded (the runbook-guard pattern); the machine-level GPU is serialized, never shared
  with another run.
- M9. **The finding.** Committed `docs/planning/edit-contract-finding/measurement-run/finding.md`
  stating the decision and pointing at the gitignored breakdown (`runs/edit-contract-finding/`).
  It discloses the proxies (see R1), states that the run's `prompt_sha256` is new and the
  figures are comparable to nothing prior, and — on NO-GO — records that nothing was built.
  On GO it is the operator's checkpoint before the contract aspect starts; the checkpoint can
  stop a GO, it cannot turn a NO-GO into a GO.

### 4.2 Must, on GO — the numbered-listing contract (aspect `numbered-listing-contract`)

- M10. **Format.** One or more blocks: a path line (repository-relative), a line range
  (`<start>-<end>`), then a replacement section (markers pinned in the spec). Blocks may sit
  inside a fence. The prompt's response-format section states this and nothing else about
  editing; the rest of the prompt is byte-identical to the diff contract's.
- M11. **Parsing never repairs.** A malformed block (missing marker, missing path, unparsable
  range) makes the rollout `NOT_LOCATED` with a named reason; no block is ever dropped while
  others proceed.
- M12. **Ranges are exact.** Each range must satisfy start ≥ 1, start ≤ end, end ≤ the file's
  line count at `base_commit`; ranges on one file must not overlap. No tolerance, no
  whitespace folding, no "best match" — the M10 doctrine carried over.
- M13. **New-file creation is out of scope for this contract** (a new file has no lines to
  address) and is stated as such in the amendment.
- M14. **All or nothing.** If any block fails M12, no diff is produced; the rollout records
  `NOT_LOCATED` with a `detail` naming the path, the block index and the reason (`absent`,
  `no such file`, `range beyond end`, `start > end`, `overlaps block K`, `malformed`).
  STRICT is not entered.
- M15. **Scope before location — the rule that keeps `N` honest.** A block naming a path in
  `task.test_blobs` is never refused by the converter. It is rendered (a located block
  normally; an unlocated one as a hunk anchored at line 1 whose old side is the addressed
  lines' text) and handed to STRICT, whose pre-apply scope check refuses it as `patch-scope`
  — the outcome is `OUT_OF_SCOPE`, counted as a caught attempt **because STRICT said so**
  (mirrors `patch-representation/prd.md` M13; the rendered hunk must be grammatical, and a
  test asserts `git apply --numstat` names the held path for the line-1 rendering).
- M16. **Conversion** produces a unified diff (`--- a/<path>` / `+++ b/<path>`, three lines of
  context, git's `\ No newline at end of file` marker where the old or new content lacks a
  final newline) that `git apply --check` accepts against the base checkout whenever every
  block located. Pure function of (blocks, file contents); byte-identical across processes and
  hash seeds.
- M17. **The reward path is untouched.** Nothing under `verify/` or `tasks/` changes or imports
  the new modules; the AST guard, the partition guard and the one-way import test stay green
  (`tests/test_no_inference_on_reward_path.py`; `tests/test_reward_path_scope_is_partitioned.py`).
  STRICT and WEAK receive the same rendered diff string as today (`scoring.py:454-516`).
- M18. **Selector.** An explicit `edit_format` field — `diff` (default, unchanged behaviour,
  byte-identical prompts) or `line-range` — on both the night and the bake-off drivers. The
  night's ledger and the bake-off's provenance block record it
  (`GenerationContract`, `report.py:177-218`). `extractor_version` becomes a digest over every
  module the selected contract's extraction path executes, so it moves when the converter moves
  (`run.py:1133-1141` is the current single-source digest).
- M19. **Retry budget is 0 under `line-range`.** The existing retry triggers diagnose diff
  grammar; a driver asked for `line-range` with a non-zero retry budget refuses to start.
- M20. **`NOT_LOCATED` is added to every consumer that partitions outcomes** — `report.tally`
  (`report.py:426-453`), `gate.py`, `honest_report.py`, the morning report, `baseline.py` — as
  a not-solved, **covered** outcome (the model answered and was wrong; it is not `UNVERIFIED`,
  and it is never a win). An exhaustiveness test fails if a future `Outcome` member is not
  placed (`tests/loop/test_dataset.py:84-91`, `tests/loop/test_gate.py:149-161`,
  `tests/bakeoff/test_honest_number_report.py:47-50`).

### 4.3 Must, on GO — the amendment (aspect `amendment-10-17`)

- M21. `PREREGISTRATION.md` § 10.17, **Type 1 (§ 8.1)**, committed before any night records
  `edit_format = line-range`: pins the edit format, the prompt template SHA-256, the extractor
  version, retry budget 0, and names the non-comparable home `reports/line-range/`
  (declaration only until a night runs). It states that figures under it are comparable to
  nothing prior, sets no threshold, and points at the measurement finding for why it exists.
- M22. `docs/ROADMAP.md` records that M1's lead is spent — by measurement, in either direction —
  and `docs/STATUS.md` gets its entry in the same commit as the capability (repository rule:
  claim and code arrive together).

### Should

- S1. The addressability instrument also classifies the stored diff-contract arms'
  `NOT_APPLIED` rollouts as a **corroboration only** of the same direction (the
  `patch-representation` finding's partition already does this — a cross-check that the new
  instrument's classes agree with the old one's on the same evidence, reported beside, never
  pooled).
- S2. The measurement driver's transcript/journals accept the night draws-directory layout
  (`runs/<id>/draws/draw-NN.*`) so a future night under `line-range` is classifiable by the
  same instrument.

### Nice

- N1. A `line-range`-specific retry vocabulary. Explicitly deferred (§ 7).

## 5. Technical considerations

- **Where it plugs in** — `understanding.md` § *Affected areas*. The measurement aspect is a
  sibling of `bakeoff/locatability.py` and `bakeoff/run.py`, sharing their seams (generator,
  journal/transcript codecs, provisioning, `verify`); the contract aspect (on GO) threads an
  `edit_format` selector through `loop/draws.py` and `bakeoff/run.py` and adds the converter
  between extraction and `_verify`, with the prompt change confined to `rendering._RESPONSE_FORMAT`'s
  counterpart (`rendering.py:131-142`).
- **Reading files at `base_commit`** happens in the harness, off the reward path, read-only,
  from the same repository `sources.oracle_sources` reads. Held test contents may be *read by
  the harness* to render a numbered listing or M15's diff; they are never rendered into a
  prompt (`rendering.HeldTestInSources` is unchanged).
- **`patch.py`'s doctrine — "locate a diff; never author one" — is amended on GO, not
  broken** (`patch.py:20-28`). Under `line-range` the harness *does* author the diff, and the
  doctrine's purpose is carried by M11 (never repair), M12 (exact ranges), M14 (all or
  nothing), M15 (scope before location) and M16 (path-preserving). The new module's docstring
  says this in those words; `patch.py` is not edited.
- **Determinism** — `difflib` output is deterministic, but its handling of missing final
  newlines is not git's; M16's marker handling is the known sharp edge and gets its own
  fixtures.
- **Reward-hacking surface (explicit).** On GO the converter is a new door between policy text
  and the reward. What STRICT receives is still a unified diff that STRICT re-executes against
  the operator's restored tests; nothing the converter does can make STRICT return `PASS` for a
  patch it would not pass as a diff. The new risks are all *conversion* risks (§ 6).
- **Promotion-gate impact.** None to the gate's rule. `NOT_LOCATED` is a covered not-solved
  outcome; `UNVERIFIED` semantics, `R`, and the promote condition are unchanged.
- **Cost of the run.** ~45–60 minutes of generation plus control/verification on the pinned
  base, from `reports/larger-base/cost.json` (258 s/task). The machine-level GPU is serialized
  with any other run; the run is commanded from a guarded runbook.

## 6. Risks and open questions

- **R1 — the measurement is a proxy, and there is no stored evidence.** No run has ever
  prompted under the numbered-listing contract, so the measurement *must* spend the small
  bake-off; and what it measures — range addressability and syntax-only grammaticality — is a
  necessary condition for the contract to help, never a prediction of yield. The finding states
  both, and the command's rule is a go/no-go for building a contract, never a claim about the
  base's ability (the `finding.md:63-75` disclosure pattern).
- **R2 — cost and machine contention.** The run is hours on the pinned base; it is the
  operator's pass, serialized on the machine-level GPU, and bounded by the committed 16-task
  population.
- **R3 — the finding says NO-GO.** Then the numbered-listing direction is also not the wall,
  and that is a result: the unit ships the instrument and the finding, and the roadmap's
  remaining responses are raise *k* and the portability arm's CPU dtype
  (`finding.md:86-92`; `docs/ROADMAP.md` § 14). Not a failure of this unit.
- **R4 (reward-hacking, on GO) — a held-path attempt escapes `N`.** Closed by M15; test: a
  garbage range on a held path records `OUT_OF_SCOPE` with `verdict_kinds == ("patch-scope",)`.
- **R5 (reward-hacking, on GO) — range games.** A range that deletes more than the model was
  shown, or overlaps another block, is closed by M12's exactness + M14's all-or-nothing;
  tests: `start > end`, `end > file length`, and two overlapping blocks are each `NOT_LOCATED`
  with the named reason, never applied.
- **R6 (reward-hashing, on GO) — path escape.** Absolute paths, `..` segments, and symlinked
  paths that resolve outside the checkout are `NOT_LOCATED: no such file`, never read from the
  host (the `locatability._escapes` precedent, `locatability.py:224-227`).
- **R7 — the syntax-only proxy.** A replacement that `ast.parse`s can still be nonsense; the
  proxy never touches the reward path, is pre-committed, and is disclosed in the finding (a
  sub-count of non-importable files is reported, never decisive).
- **R8 — the ripple is the cost (on GO).** Adding `NOT_LOCATED` touches every outcome
  partition (M20); that, not the converter, is most of § 4.2's effort.
- **R9 — a stronger base could reduce the need for the contract.** A base that transcribes
  diffs well makes line-range addressing unnecessary; the durable asset is the harness (the
  contract, the converter, the measurement instrument), which persists and improves *with*
  base quality — this unit answers the pinned base's question now, and the amendment sets no
  threshold, so the contract is never a bet against better bases.
- **OQ1** — whether the measurement driver is a new module or a flag on `bakeoff.run` is left
  to tech-plan; the constraint is fixed: a NO-GO must leave `rendering.py`/`run.py`/`night.py`
  byte-identical, so a separate module is the default shape.
- **OQ2** — the replacement-section markers and the exact wording of the response-format
  section are fixed in the contract aspect's spec (on GO), never in the measurement's.

## 7. Out of scope

- Any change under `verify/` or `tasks/`; any change to STRICT, WEAK, the gate rule or `R`.
- Running a night under `line-range` — the next unit, under § 10.17.
- New-file creation by the contract (M13).
- Fuzzy, whitespace-tolerant or "best match" range resolution; whole-file formats.
- A `line-range` retry vocabulary (N1).
- Raising *k*, the CPU dtype, and any base change.
- The held-out set, publication (M2/M3 of § 14), the dashboard, distillation.

## 8. Aspects

| Aspect | Boundary | Depends on |
|---|---|---|
| `measurement-run` | § 4.1 — renderer, parser, driver, addressability instrument + command exit, spec fixed before the run, runbook, finding | — |
| `numbered-listing-contract` | § 4.2 — format, converter, `NOT_LOCATED`, selector, drivers | **GO** from `measurement-run` |
| `amendment-10-17` | § 4.3 — § 10.17, ROADMAP/STATUS/CHANGELOG | `numbered-listing-contract` |