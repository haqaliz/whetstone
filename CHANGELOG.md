# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Whetstone's contract is that a number appears only where something produced it. That applies
here too: this file records what shipped, not what is planned. Nothing is listed under a
released version until it exists in the code.

## [Unreleased]

### Added

- **The held-out source-B split — P3's first aspect**
  (`docs/planning/p3-promotion-gate/heldout/`). The artifact `PREREGISTRATION.md` § 7.1 named
  open until P3 exists, fixed before it scores anything: `src/whetstone/loop/heldout.py` holds
  the pre-committed rule — three terciles over the 66 source-B tasks ordered by the stratum
  document's per-task difficulty (files / hunks / added+deleted, reused as the ordering key,
  never a new axis), a floor of 10 held-out tasks and 2 per band, and per-band selection by
  `sha256(split_seed, task_id)` with the seed a declared constant — and
  `tasks/heldout/source-b.json` (schema `whetstone-heldout/1`) declares the membership — 12 of
  66, four from each band — sealed by a rule digest and a document digest the loader refuses a
  hand-edit of. The loader is fail-closed by name (unknown fields, duplicated memberships,
  members the document refused rather than measured, digest mismatches, and
  empty/whole-corpus/floor-unmet splits), the door is
  `python -m whetstone.loop.heldout --corpus ... --out ...` with a gitignored `--out` refused
  by name, the membership recomputation test re-derives the document from the machine corpus
  field by field (skipping in CI with the reason named), and the locality canary holds — the
  document carries counts, bands and ids, never task contents. `PREREGISTRATION.md` § 10.7
  (Type 1, dated 2026-08-24) closes § 7.1 with the split size, the stratification rule and the
  document location, committed before the split is used to score anything; §§ 7.2 and 7.3
  remain open.

- **The never-regress promotion gate — `whetstone gate`, P3's third aspect**
  (`docs/planning/p3-promotion-gate/gate-core/`). The core-loop element ③ now exists:
  `whetstone gate --candidate X --incumbent Y --heldout <doc>` scores both checkpoints on the
  held-out source-B membership (plus source A in full) through the STRICT verifier and returns
  exactly one of the three exits the roadmap fixes (`docs/ROADMAP.md:420-427`): `promoted` → 0,
  `rejected` → 1, `UNVERIFIED` → 3, refusals → 2 — no fifth code. The body lives in
  `src/whetstone/loop/gate.py` (EXEMPT on the `loop` precedent), the decision core is a pure
  function over two per-task outcome maps (`promote iff solved_new > solved_old AND regressed
  == 0 AND unverified == 0`), and everything it relies on is composed by identity: both
  checkpoints re-hashed through `sft.verify_checkpoint` (`CheckpointUnverified` refuses naming
  the checkpoint), the held-out document through aspect 1's fail-closed loader, scoring through
  `bakeoff.scoring.score` with `sampler_for(1)`'s greedy sampler (a single-draw gate eval and
  the bake-off are one experiment), per-task verdicts through `verify.verdict.reduce`
  (UNVERIFIED above PASS), and the single definitions of solved and unverified
  (`Outcome.SOLVED`, `report._UNCOVERED`). The decision table is asserted, not described:
  known-better → promoted; known-worse → rejected; equal solves → rejected by the `>` term;
  candidate == incumbent → rejected; one still-unverified task → the whole eval is `UNVERIFIED`;
  a regression rejects even with a solved gain. Source A is reported beside source B with both
  denominators disclosed, coverage is the sibling rule (unverified stays in the denominator),
  and the unverified rate appears as a count over its denominator. The promotion record is the
  gitignored `runs/promotions/<id>.json` (schema `whetstone-promotion/1`): both re-hashed
  digests, the held-out document digest, per-side verdict counts over both denominators, the
  decision with its counts, the retry discipline's fields (see the entry below), tool versions,
  `recorded_on` (an input, never the clock); a runs root inside `reports/` is refused by
  `_refuse_published_root` imported by identity. The partition guard grew test-first from one
  documented function-local edge into the exempt package to exactly two — `whetstone.loop.night`
  and `whetstone.loop.gate` — each watched failing against a planted module-scope import, a
  third failing the build. `gate_engine` (base + LoRA adapter via `mlx_lm`) is the one new
  machine seam, smoke-tested only — every test runs the stub engine against fixture
  checkpoints. **The gate has not been run on real checkpoints** — the fixture pair proves the
  three-exit differential, and the operator's sheet (a later aspect) scripts the first real
  evaluation.

- **The gate's retry discipline — P3's fourth aspect**
  (`docs/planning/p3-promotion-gate/retry-discipline/`). `unverified == 0` is the honest term
  in the gate rule, and a gate demanding exactly zero of a real machine would never fire, so a
  held-out task that reached **no verdict** is scored again up to `R` times — `RETRY_COUNT = 3`
  in `src/whetstone/loop/gate.py`, a declared module constant and never a flag — and a task
  that verifies on retry is verified. What makes it safe is what it cannot do. It never retries
  a **verdict**: the predicate is `report._UNCOVERED` by identity, so `NO_DIFF`, `NOT_APPLIED`,
  `NOT_SOLVED` and `OUT_OF_SCOPE` are final, and a deliberately credulous predicate
  ("anything not SOLVED") is proven to promote a candidate that is not better than its
  incumbent, watched failing first. It never re-generates: `_Replay` answers exactly the
  recorded completion of the first attempt and raises `RetryInputsChanged` on any other prompt,
  and the base is measured as being asked each prompt exactly once however many times a task is
  scored — so *identical inputs* is a check the code performs rather than a property argued
  from greedy sampling. A task with no recorded completion (`UNPROVISIONED`, `NO_ORACLE` —
  neither reaches the generator) is never retried at all: there is nothing to replay, and it
  keeps the eval `UNVERIFIED`, which is the honest direction. The budget is per task, not per
  run; a task still without a verdict after `R` retries keeps the **whole evaluation**
  `UNVERIFIED` — not promoted, not rejected; and the retry sequence is asserted deterministic
  down to the recorded evidence on disk. The promotion record now carries all three retry facts
  (the declared `R`, every task the retry fired on with what it took, and the set that outlasted
  the budget — hashes and verdicts only, never contents), and `whetstone gate`'s output carries
  an **unconditional** liveness line: `R`, what was spent, and the unverified count over its
  denominator, from the first evaluation onward. `PREREGISTRATION.md` § 10.8 (Type 1, dated
  2026-08-25) closes § 7.2, stating that `R = 3` is declared a priori rather than derived — no
  unverified rate has been observed, because no gated evaluation has run — and that its revision
  path is a further dated amendment grounded in a measured rate, never a code edit alone; § 7.3
  remains open.

- **`whetstone check-leakage` — P3's fifth aspect**
  (`docs/planning/p3-promotion-gate/check-leakage/`). The roadmap's own exit criterion
  (`docs/ROADMAP.md:449-450`), kept separate from the exclusion it proves: the night drops the
  held-out ids at its partition seam, and a behaviour nobody checks is a claim.
  `whetstone check-leakage --run <runs/id> --heldout <doc>` exits 0 when a night's training set
  and the held-out membership are disjoint, 1 with the leaked task **named**, and 2 on a refusal
  — no fifth code, and no `UNVERIFIED` exit, because the command reads documents rather than
  running anything. A leak is a named violation and the disclosure says what it is evidence of —
  a regression in the partition seam, not something to fix by dropping the examples after the
  fact. Ids and examples are counted in their own units, both sources are reported over their own
  denominators with source A's overlap measured rather than assumed, and a night that trained on
  nothing is "disjoint by truth" in those words. The subject is `runs/<id>/dataset.json` — what
  was actually trained on — and the ledger is read only to identify the directory as a night's
  run. An unreadable dataset is refused rather than treated as empty, a third source name is
  refused rather than filed under one of the two, and the held-out document goes through its
  fail-closed loader before any comparison: a membership edited without regenerating the digest
  is refused. The reward-path partition guard grew to exactly three documented function-local
  edges (`night`, `gate`, `check_leakage`), proven able to fail against a planted fourth and a
  planted module-scope import.

## [0.7.0] - 2026-08-20

### Added

- **The nightly improvement loop — P2's first slice, and the project's namesake.**
  `whetstone run --night` (`docs/planning/p2-rollouts/`) draws `K` seeded attempts per task
  under the hardened generation contract, keeps **only** the rollouts the STRICT verifier
  passed, and LoRA-SFTs the base on those, writing `runs/<id>/` (a ledger of the pinned
  seeds, model revision, task set and tool versions; the selected dataset; the per-draw
  journals and transcripts) and — when the night selected anything and the declared capacity
  probe fits — a hashed candidate under `checkpoints/<id>/`. All four P2 exit criteria are
  asserted as tests rather than described: the door produces both directories, **every**
  training example carries a recorded strict-PASS verdict, two nights at one seed produce a
  byte-identical training set, and the ledger records the pinned inputs. The new package
  `src/whetstone/loop/` is partitioned `EXEMPT` on the `bakeoff` precedent and **composes
  rather than re-decides**: `freeze`/`Sealed`/`Recording`/`Retry`, `control.probe`,
  `harness_status`, `sweep.rankable`, `Journal`, `Transcript`, `load_weights` and the single
  definition of *solved* (`report.tally`'s `Outcome.SOLVED`) are all imported by identity.
  The one new seam is the sampled draw: `K = 8` is a declared constant and never a flag
  (raising it is the roadmap's named response to a low yield, as a diff before a night), the
  per-attempt seed is `sha256(run_seed, task_id, attempt)` — never the builtin `hash`, which
  is process-salted and would have made the determinism criterion a statement about
  `PYTHONHASHSEED`, asserted by a cross-process test — and `sampler_for(1)` returns
  `mlx_runtime.greedy_sampler` by identity, so a single-draw night and the bake-off are one
  experiment. `Draw` wraps outermost, so a retry re-asks *within* a draw and consumes no new
  seed; one journal and one transcript live **per draw index**, because both are keyed
  `(candidate, task)` and `K` draws of one task would otherwise collapse to the last; the
  control arm runs once per task and is shared across the draws, and a resumed night reuses
  the recorded probe rather than taking a second one. `cli.py` gains this repository's one
  edge from a guarded root into an exempt package — a single **function-local** import of
  `whetstone.loop.night` inside the night handler, so `whetstone verify` never loads a model
  — and `tests/test_reward_path_scope_is_partitioned.py` asserts it is the only such edge
  **and** that it is function-local, both watched failing against planted imports. The
  refusals are the substance: `UNVERIFIED` is not training data and neither is anything else
  (the trainable partition is enumerated against `Outcome` and asserted complete), an example
  must carry `SOLVED` *and* a recorded strict `PASS`, a win from an unproven control arm is
  refused by name, a zero-strict-PASS night writes no checkpoint and states the empty outcome,
  the LoRA capacity probe is declared before it ran with the memory fallback pre-committed on
  (exceeding its headroom is a published capacity finding, not a constant to edit), a valid
  split below its declared floor is *no valid split* stated verbatim in the checkpoint's
  provenance, and the checkpoint is hashed weights-style with a re-verify so P3's gate can
  check the bytes it compares. **Nothing is published**: a night's counts live only in its
  gitignored run directory, the ledger and dataset documents carry hashes and verdicts and
  never contents (canaries plant donor source text and assert it cannot reach either),
  `reports/` gains no directory, and no `PREREGISTRATION.md` § 10 amendment is made because
  § 10 discloses published series and this unit publishes none. **The night has not been
  run** — the operator's sheet is `docs/planning/p2-rollouts/night-door/runbook.md`, held by
  `tests/test_night_runbook_guards.py` and watched failing against a deliberately wrong stub
  sheet.

### Added

- **The larger-base arm ran, and the fork has its first positive result.** The roadmap's
  named second response (`docs/ROADMAP.md:387-389`), executed end to end
  (`docs/planning/larger-base-arm/`): the probe pass (D7) settled the ROADMAP § 10 capacity
  question by measurement, the arm scored
  `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` on the declared source-B set under the
  hardened contract § 10.4 discloses, and the 32B produced the **first nonzero strict-PASS
  yield the harness has ever measured** — so the pre-committed fork rule routes the next
  unit to P2's first slice (rollouts + expert iteration), and the finding names the 32B as
  the first candidate with evidence (base selection itself closes § 7.3 only by a Type 1
  amendment before P3's baseline). The published home is `reports/larger-base/` (schema
  `whetstone-larger-base-report/1`), rendered by the report door's third mode
  `--render-larger-base-report`; the one-home guard admitted it on the changed-candidate-set
  argument, and `PREREGISTRATION.md` § 10.6 (Type 2, 2026-08-15) declared the series
  non-comparable before any figure existed for it. Two disclosures in the finding: the
  material unverified rate (a timing property of the 32B's ~6 tokens/second against the
  verification timeout — the P3 retry discipline is the named response) and the one field
  correction the run surfaced (the post-run chain's autopsy stem did not match the
  journal's run name, the comparison refused it by name, and the guard now pins the
  alignment, watched failing first). No figure about a model appears anywhere outside the
  report home and the gitignored breakdown home.

## [0.6.0] - 2026-08-14

### Added

- **The stratum-probe runbook and its guards.** The fourth aspect of the easier-stratum
  probe (`docs/planning/p2-easier-stratum/probe-run/`), Phase 1: the operator's sheet for
  the stratum probe — `runbook.md` — opens with the candidate resolution (A2), decided
  before the run from the stored pre-analysis ceiling document: the 14B and 3B candidates
  retained on their measured retry-eligible ceilings, and
  `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` — retry-eligible 0, ceiling 0 in both
  stored runs, its `im-start-loop` wall — excluded by name under the pre-committed rule
  (`prd.md:93-103`); the arm command runs the hardened contract (`--stratum`, `--retries`,
  the five declared dev ids, `--only` × 2, absolute writable paths) from the primary
  checkout; and the post-run chain is written out — attribution → autopsy → the mandatory
  pre-analysis extension over all four autopsy documents → the probe's own comparison → the
  stratum-report door. The guard is extended, never parameterized (A1):
  `tests/test_probe_runbook_guards.py` imports the parse helpers from
  `tests/test_runbook_guards.py` by identity (asserted `is`; the pinned module is
  byte-untouched) and re-binds only `RUNBOOK` and `STALE_WORKTREES`, pinning the same seven
  properties (absolute writable paths, every arm flag in `build_parser`, worktree-shaped
  project targets, exactly one worktree everywhere, arm CWD at the primary, no stale worktree
  names, an anti-vacuity parse) plus the A2 resolution property — every `--only` value is a
  name the resolution block records, the excluded name appears in no `--only` value, and the
  block states the zero-ceiling rule. Watched failing first against a deliberately wrong stub
  runbook (relative writable paths, no `--stratum`, a stale worktree name) before the real
  sheet existed. The probe itself is operator-executed (Phases 2–4); no figure about a model
  appears anywhere outside the report home and the gitignored breakdowns.

- **The easier-stratum probe's report home.** The third aspect of the easier-stratum probe
  (`docs/planning/p2-easier-stratum/stratum-report/`): `report.build_stratum_report` /
  `write_stratum_report` render the probe's three-artifact document (schema
  `whetstone-stratum-report/1`) — the declared source-B set scored under the hardened
  contract, restricted to the pre-committed stratum; per-candidate rows over the harness's
  own denominator (via `_row`, by identity); the `_NON_COMPARABILITY` sentence beside the
  changed-task-set declaration; the contract's fields (retry budget, retry template digest,
  diagnosis vocabulary digest, retrieval, dev subset); both pointer sentences (the committed
  stratum document and the gitignored breakdown home — named, never restated); the token
  spend; and the declaration-only state ("**No count is measured here: the probe has not
  run.**"), generated by the writer, never hand-typed. The report door's second mode
  (`--render-stratum-report` in `comparison.py`) takes exactly one arm group, reuses
  `build_contract_arms` unchanged so its refusals (missing journal, empty journal, no
  `INTACT` control probe) hold by identity, refuses zero or two groups by name, and requires
  `--stratum-doc` as a pointer it never parses; `--render-report` and its refusals are
  untouched, and the two modes are mutually exclusive in effect. The one-home guard moved a
  third time, only on the changed-task-set argument in both docstrings: the task set is one
  of the five pinned inputs, the probe scores a different task set under the same hardened
  contract, so its figures are a new series declared non-comparable to both existing homes,
  and each directory is the only home of its own. The disjointness guard now scans all six
  existing artifacts, with the planted-overlap control proven able to fail.
- **`PREREGISTRATION.md` § 10.5** (Type 2, dated 2026-08-14): the easier-stratum probe
  scores a changed task set under the hardened contract; the three reports are declared
  non-comparable (the baseline differs in task set and contract, the hardened arm in task
  set alone); `reports/easier-stratum/` is the only home of the probe's figures, and the
  probe is a yield test — not the pinned baseline, not the held-out split. With its row in
  the amendment log; nothing above § 10 was edited, no placeholder, no proportion in any
  spelling. The committed `reports/easier-stratum/` artifacts are the declaration, holding
  no count until the probe runs and the door renders figures into it.

- **The run-side stratum filter.** The second aspect of the easier-stratum probe
  (`docs/planning/p2-easier-stratum/stratum-filter/`): the bake-off run now accepts
  `--stratum PATH` and scores exactly the committed stratum's tasks from the loaded source-B
  corpora. The document is a pinned input, consumed through aspect 1's loader by identity
  (imported, never copied, asserted `is`), and `include_stratum` applies the membership
  against the loaded private corpus at the partition seam, before the contract is frozen, so
  the sealed prompt set and the scored set cover the subset automatically. The loader's
  membership checks are completed where they stopped: unknown fields, duplicated membership
  entries, and members the rule refused rather than measured are each named refusals, and a
  membership id matching no loaded private task is refused with the loaded ids. The dev-subset
  overlay applies on top (dev ∩ stratum is exclusion, never refusal), an empty scored private
  set after the overlay is refused before freeze, source A is always scored in full, and the
  report's task-set sentence names the stratum document and its membership count. A run
  without the flag is byte-identical to today's run, reproduced by the byte-identity test.
  Doctored documents — membership edited with a stale digest — are refused rather than
  trusted, watched failing against a deliberately credulous loader first; a fully regenerated
  document passes by design, with the dev member it smuggles proven excluded end-to-end.

- **The pre-committed difficulty rule and the easier-stratum document.** The first aspect of
  the easier-stratum probe (`docs/planning/p2-easier-stratum/`) is the task-side test of the
  fork's first arm: select the declared source-B corpus's easier tasks, pre-committed before
  any rollout. `src/whetstone/bakeoff/stratum.py` is the a priori axis — the reference fix's
  shape, measured from the donor at the task's pinned commits, reusing `sources.changed_paths`
  and `derive.gold_patch` by identity (never copied, asserted `is`, and byte-identical to the
  control arm's own composition on all 66 tasks) — with a pre-committed band of one non-test
  file, at most two hunks and at most thirty changed lines, and the rule's own hunk/line walk
  validated as a measurement against git's `--numstat` on the whole corpus. The committed
  stratum document (`tasks/stratum/easier.json`, schema `whetstone-stratum/1`) is the pinned
  input: rule digest, band, the 66-task corpus, per-task difficulty counts, refusals, a
  19-task membership, and a document digest that refuses a hand-edited payload. The loader is
  fail-closed by name (unknown ids, degenerate memberships in both writer and loader, unknown
  schema, digest drift), and the membership recomputation test re-derives the document from
  the machine corpus field by field, skipping in CI with the reason named. The document
  carries counts only — never paths, never patch content — walked structurally with a canary.

## [0.5.0] - 2026-08-12

### Added

- **The measured format-hardening arm ran, and the before/after is measured.** The slice's
  unspent deliverable (`docs/planning/p2-format-hardening/measured-arm/`) is spent: the
  operator's GPU pass completed (`--retries`, the two donor roots, the five declared
  dev-subset ids, evidence in the sibling gitignored directory), the post-run chain ran clean
  (attribution → autopsy → comparison, zero mapping violations, the trigger mapping asserted
  by identity over every record), and `reports/format-hardening/` was rendered by the report
  door with both arms under their own contract fields and the non-comparability sentence. The
  finding (`finding.md`) records the measurement and the fork decision; no classifier count is
  restated anywhere outside the gitignored breakdown home
  (`runs/format-hardening-preanalysis/comparison.md`).
- **The arm's writable paths are absolute, and a guard holds them there.** The first launch
  died with `HarnessNotProven`: a relative `--workspace` made every environment build fail
  (`FileNotFoundError` on `workspace/digest/checkout` — provisioning subprocesses do not share
  the run's CWD), every rollout `UNPROVISIONED`, zero controls `INTACT` — halt condition 1,
  the worktrees skill's documented pitfall, hit in the field. The correction landed
  test-first: `tests/test_runbook_guards.py` now refuses a relative `--out`/`--workspace`/
  `--journal`/`--transcript` in the runbook's arm command (RED on the shipped runbook, GREEN
  after), and the runbook commands absolute paths under the primary's `runs/`. The dead run's
  evidence is quarantined by name, never deleted.
- **The runbook's post-run chain now includes the pre-analysis extension step.** The
  comparison asserts the trigger mapping against the pre-analysis document's per-run
  decisions, and a run without declared decisions is refused by name (exit 2, nothing
  written) — the stored ceiling document covered only the two stored runs, so the comparison
  could not run as the runbook first wrote it. The corrected chain re-runs the pre-analysis
  over all three autopsy documents (`ceiling-with-arm.json`) before the comparison, and the
  runbook names the step mandatory.
- **A refreshed runbook, guarded against the parser and against stale worktrees.** The
  operator sheet now names exactly one worktree everywhere (the previous correction had
  missed the arm command's CWD line), runs from the primary checkout via `uv run --project`,
  carries the before-you-run block (mlx extra, empty workspace, machine-level evidence),
  the killed-run restart procedure (fresh paths, quarantine by name, a `ContractChanged`
  void is not recovered), and run-time-declared `--recorded-on` values. `tests/test_runbook_guards.py`
  pins the flag surface to `build_parser` and the single-worktree structure, RED on the
  pre-refresh runbook and GREEN after.

## [0.3.0] - 2026-08-09

### Added

- **The online diff validator** (`src/whetstone/bakeoff/diffcheck.py`): the autopsy's taxonomy
  consulted at grading time, by identity — `classify_completion` and the cause and death enums
  are the autopsy's own objects, imported never copied and asserted `is` in a test, so the
  online trigger decision and the offline autopsy cannot disagree about the same bytes. The
  trigger mapping is the taxonomy, not a second git pass: `hunk-count-mismatch` and a first-hunk
  death on a bare line or the closing fence fire a retry; `well-formed`, `im-start-loop`, the
  inferred `end-of-output` truncation, `no-diff`, `unrecognised-shape`, and — until the
  measured-arm pre-analysis flips it through the one parameter that exists for exactly that —
  `header-without-hunk` never do. The diagnosis vocabulary is finite and fixed: one constant
  sentence per trigger, no format argument, no digit — a sentence with a hole would make the
  retry prompt set unbounded and the seal unfreezable — and the finiteness rule is asserted in
  the suite. The validator is classify-only: it has no authoring power and no task context, its
  own no-inference AST walk forbids `mlx`/`torch`/`transformers`/`run`, and nothing it does can
  change a byte of the diff it decides on.
- **The transcript now carries the retry.** Every attempt is a record: `Transcribed` gains
  `attempt` (one-based within the run) and `decision` (`"retry"` when a later record follows,
  `"graded"` when it is the decided record for its key), the codec is updated field by field so
  an old-schema line fails decode rather than defaulting, and `replay()` still selects the last
  record per (candidate, task) — the frozen consumers (`attribution.py`, `autopsy.py`) read the
  same transcript as ever. A last record declaring `"retry"` is refused as corruption (a run
  killed between the retry and its completion), raised, never repaired.
- **The anti-credulity proof, watched failing and sub-verdict-pinned.** A held-path edit —
  well-formed, trigger-shaped (the shape a retry fires on), and mixed with a real source fix —
  survives validator and extractor byte-for-byte and reaches STRICT, which refuses it at the
  `patch-scope` sub-verdict specifically while WEAK accepts it: the differential
  `(Outcome.OUT_OF_SCOPE, Status.FAIL, Status.PASS)` is asserted per shape, and a deliberately
  credulous validator that drops held-path hunks (using `test_blobs` as a sanitisation list,
  exactly what R4 forbids) is proven in the suite to lose that differential.
- **The AC2 pins now cover the whole reward path**: `src/whetstone/verify/`, `patch.py` and
  `attribution.py` are asserted byte-identical to `origin/master` — the `attribution.py` pin
  that was missing, added — and the pin is proven able to fail against a synthetic tree with a
  planted change in each path.
- **The autopsy** (`python -m whetstone.bakeoff.autopsy`): an offline, deterministic,
  stdlib-only classifier that reads a bake-off transcript and says which zero each rollout
  was — the content-level read the yield-probe correction demanded before a fourth fix.
  One primary cause per completion (`im-start-loop`, `hunk-dies-early` with its three
  deaths, `hunk-count-mismatch`, `header-without-hunk`, `well-formed`, the inherited
  `no-diff`, and `unrecognised-shape` named and never folded), markers as observations, and
  a fine→coarse mapping asserted per record against the run's own `attribution.json` — a
  contradiction is reported as a divergence, never reconciled. The document is written only
  under a gitignored root (refused otherwise, before anything is read), byte-deterministic,
  schema `whetstone-autopsy/1`.
- **The measurement corrected the hand-read, which is the part worth reading.** Run over
  the two stored runs (arm-a, budget-2048), the mapping assertion surfaced walk rules that
  disagreed with git's parser on the same bytes: a check that read text past the extracted
  diff (which git never parses) and misflagged applied patches; a blind spot where git's
  counter-overrun keeps parsing into "corrupt patch" while the walk saw a completed hunk;
  and a mapping gap for loop-dominated completions carrying a refused stub. Each correction
  has a fixture and was watched failing first. The corrected instrument agrees with the
  run's own attribution on every stored record and classifies both runs completely.
- **The finding** (`docs/planning/p2-diff-autopsy/finding.md`): the wall is formatting, not
  reasoning, not extraction — the candidates can write diffs git accepts and almost never
  do, so the roadmap's easier-stratum/larger-base fork is unsupported by this data, and a
  format-hardening response is what the evidence names. No figure about a model appears
  anywhere outside the gitignored breakdowns.
- **A `verify/`-untouched guard**: the first test asserting the reward path does not move
  (`git diff --stat origin/master -- src/whetstone/verify/` empty), proven able to fail
  against a synthetic tree with a staged `verify/` change, plus the autopsy's own
  no-inference AST walk over module and tests.
- **The retry prompt and the budgeted retry wrapper** (`src/whetstone/bakeoff/retry.py`):
  the convert half of the format-hardening response, on top of the aspect-1 validator. The
  retry prompt is a pure function of `(first-attempt prompt, trigger)` — the first prompt,
  a fixed retry instruction, and exactly one sentence from the finite diagnosis vocabulary,
  never the prior completion — so every retry prompt a retried run may issue is pre-rendered
  at freeze time (`freeze(..., retry=True)` folds `retry_prompt(render_prompt(...), trigger)`
  per task per trigger into the same `posed` map via `setdefault`) and the contract SHA
  covers the whole retry vocabulary. `Retry` is a `Generator` wrapper — the one-method seam
  is not widened — that issues at most two retries per (candidate, task) (`RETRY_BUDGET`,
  three generations total), only on the trigger shapes the validator names, and returns the
  last completion; the decision is `trigger_of(classify_completion(text))` by identity, pure
  and replayable. Every attempt is recorded: the wrapper writes one record per attempt with
  its own `prompt_sha256`, its one-based `attempt`, and its `decision` (`"retry"` when a
  later attempt follows, `"graded"` for the decided record), filed under the task the prompt
  was posed for. A mid-run edit of the retry vocabulary raises `ContractChanged` through the
  seal and aborts the run, like any other template edit — asserted end-to-end through
  `freeze` + the wrapper, with the retry prompts proven sealed by an instrumented engine.
  Retries are off by default (`conduct(..., retries=False)`), composed only when
  `--transcript` names a file, and a retries-disabled run's contract is byte-identical to
  the baseline's. The retry path has its own no-inference AST walk (no `mlx`, no `run.py`,
  no `scoring`), and `retry_template_sha256()` is the digest aspect `contract-report`
  publishes.
- **The generation contract now tells two contracts apart by their published fields.**
  `GenerationContract` gains `retry_budget` (`RETRY_BUDGET`), `retry_template_sha256` (a
  digest of the retry instruction plus the sorted diagnosis sentences), a
  `diagnosis_vocabulary_version` (a digest over the sorted sentences alone, computed by the
  validator's own `diagnosis_vocabulary_sha256()`), and `retrieval` — today `"oracle"`, the
  machine-readability fix (yield-probe D9). A retries-disabled run's contract keeps the
  no-retries shape (budget 0, blank digests), so it stays byte-identical to the baseline's;
  a retried run's declares the whole machinery. The committed baseline sidecar predates all
  four fields and still parses: `GenerationContract.parse` defaults `retrieval` to
  `"oracle"` and the retry trio to the no-retries state, and the baseline report.json keeps
  reading unchanged.
- **The format-hardening report** (`reports/format-hardening/`): a second home, on the D6
  argument. `report.build_contract_comparison` renders both arms' verdict counts under their
  own contract fields, the non-comparability sentence, per-arm token spend, and a pointer to
  the gitignored breakdown home — never restating a classifier count (`finding.md:89-92`).
  The committed artifacts are the declaration: no count, no arm, until the measured arm
  renders them. The one-home guard moved a second time, only with the D6 argument in both
  docstrings (`test_report.py` and its opposite-sign twin in `test_transcript_locality.py`):
  the two directories measure different generation contracts and are declared non-comparable,
  so neither is a competing home for the same figure. `reports/baseline/` is untouched.
- **`PREREGISTRATION.md` § 10.4** (Type 2, dated 2026-08-09): discloses the hardened
  contract — retry budget of two, retry template digest, diagnosis vocabulary digest,
  retrieval stays oracle, a new declared dev subset — and declares the two reports
  non-comparable, with its row in the amendment log. Nothing above § 10 was edited, no
  placeholder, no proportion in any spelling; the dev-subset mechanism is proven as three
  layers (exclusion from both sources before anything runs, `UnknownDevSubset` refusal,
  `ScoredDevSubset` backstop).
- **The retry-eligible pre-analysis** (`src/whetstone/bakeoff/preanalysis.py`): the offline,
  stdlib-only, deterministic read of the stored autopsy outputs (schema
  `whetstone-preanalysis/1`, refused under any published path, its own no-inference AST
  walk) that applies the validator's own trigger mapping by identity and counts the
  retry-eligible ceiling per candidate before any GPU is spent. Run over the two stored
  runs: the retry-eligible subset of the stored parse refusals is a large majority, and one
  candidate's ceiling is zero — its `im-start-loop` wall, a per-candidate finding. The
  numbers live in the gitignored `runs/format-hardening-preanalysis/ceiling.json`, their
  only home. The ceiling is material, so the arm's halt condition did not fire.
- **`--retries` on the run CLI**: the retry switch existed in `conduct` but was unreachable;
  the flag is exposed with parser and wiring tests watched failing first, off by default so
  an unflagged re-run stays the baseline contract.
- **The hardened-arm runbook** (`docs/planning/p2-format-hardening/measured-arm/runbook.md`):
  the operator's command for the arm — the real donor roots (`belay`, `contig`), five
  declared dev-subset ids verified against the corpus, the journal and transcript in a
  sibling evidence directory (the harness refuses a transcript under `--out`), the halt
  conditions, and the post-run attribution/autopsy commands. The arm itself has not run;
  the measured before/after cause breakdown is unspent until it does, and nothing here
  claims a figure it didn't produce.

## [0.4.0] - 2026-08-10

### Added

- **The before/after comparison** (`src/whetstone/bakeoff/comparison.py`): the runbook's
  Phase 3 tooling, now existing — journals, autopsy documents and the pre-analysis ceiling
  document into the per-candidate before/after breakdown (schema `whetstone-comparison/1`,
  refused under any published path, its own no-inference AST walk). The trigger mapping is
  re-derived by identity and asserted against the pre-analysis's own decisions — a
  contradiction is a named violation with a nonzero exit, never reconciled — the control
  discipline is enforced (no `INTACT` probe, no counts), and the D6 denominators are
  disclosed side by side (rollout records vs classified completions, plus the dev-subset
  exclusion a hardened contract declares), never fused. Run over the two stored arms, the
  assertion held over every record — no violations — byte-identical on re-invocation; the
  markdown render lives at the runbook's named home
  (`runs/format-hardening-preanalysis/comparison.md`), gitignored, the only home of the
  numbers.
- **The report door** (`--render-report` in the same module): the first production caller of
  the shipped two-contract writer — journals and contract sidecars into
  `build_contract_comparison`/`write_comparison` by identity, so the post-run assembly of
  `reports/format-hardening/` is one command. A missing journal, an unproven control, or
  zero arms is refused by name — the committed declaration is never re-rendered, and a
  half-truth render is refused; `--recorded-on` is declared by the operator, never read from
  a clock.
- **The measured-arm finding** (`docs/planning/p2-format-hardening/measured-arm/finding.md`),
  closing the slice: the before/after read is now a measurement end to end — the per-candidate
  walls in words, the numbers in the gitignored breakdowns — and the pre-committed hold: the
  arm itself has not run, the before/after stays unspent until it does, and nothing published
  claims a figure the arm didn't produce.


## [0.2.0] - 2026-08-06

**The first published release.** P1 complete — the reward, the contract it grades against, the
first corpus of real tasks, and the bake-off that closes the phase — plus the measurement
instrumentation that followed it. Figures about a model now exist, and `reports/baseline/` is
their only home: nothing in this file restates one, because a figure quoted twice is a figure that
can disagree with itself.

`0.1.0` below was the scaffold. It was never tagged and never published, so this is the first
version anyone can install.

### Added

- The verifier core (`src/whetstone/verify/`): the frozen `Task` contract, verdict semantics in
  which `UNVERIFIED` ranks above `PASS`, a Seatbelt sandbox that denies the network and confines
  writes, and the STRICT verifier — the reward — alongside the WEAK one, which is measurement
  only. Both reachable as `whetstone verify`.
- An adversarial corpus (`tests/adversarial/`) putting ten cheats through both verifiers: eight
  killed, and two reported rather than patched — special-casing the known input, and mutating a
  file a held test depends on that the manifest never declared.
- An AST guard that fails the build if any inference library is reachable from the reward path,
  scoped to the reward-path packages so it stays true once `mlx-lm` is legitimately installed
  elsewhere. Extended in this cycle to cover `src/whetstone/tasks/`, because ingestion authors
  the very boundary the reward path enforces; each guarded root is now asserted to contribute
  modules, so widening the scope cannot leave a root silently watching nothing.
- `environment` on every task manifest — a nominated interpreter and exact `==` pins, with
  ranges refused at load rather than defaulted. Without it a verdict depends on the resolution
  date: `pallets__flask-5063` declares `click>=8.0`, today's `click 8.4.2` has removed
  `CliRunner(mix_stderr=)`, four `pass_to_pass` tests fail, and a correct patch is scored FAIL.
  `tests/test_environment_pins.py` shows one task and one correct patch reaching PASS pinned and
  FAIL unpinned, resolved offline against a committed two-version index.
- A per-task interpreter, so a task is verified under the Python era it was written for instead
  of whichever one happens to be running the verifier.
- Non-canonical held test paths are refused at load — `./tests/x.py`, `tests//x.py`, a trailing
  slash, a bare `.` component, an empty path. Each is a second spelling of a held file that the
  patch-scope refusal compares against git's canonical output and never matches. Refused, never
  silently rewritten: the error names the canonical spelling and stops.
- `whetstone verify --task` accepts a directory of manifests, reducing worst-status-wins through
  the existing verdict semantics, so one `UNVERIFIED` task among passes can never exit 0. No new
  exit code. Nothing is skipped — a non-manifest entry fails the invocation loudly — and an empty
  directory is a usage error rather than a set of zero tasks that all passed.
- The `tasks/` layout, splitting what may be committed from what may not: public benchmark
  instances and the mining recipe and liveness ledger are committed; the user's own mined tasks
  never are. `tasks/README.md` states the rule and `tests/test_tasks_layout.py` asserts git's own
  answer in both directions.
- A miner for source B — the user's own repositories — turning a commit that takes an existing
  test from red to green into a task. **66 tasks minted, 45 from `donor A` and 21 from the sibling project,
  each proven live before it was kept**: FAIL with no patch, PASS under its own reference patch,
  the executed node-id set equal to the declared one, zero skips. A task that cannot be shown to
  discriminate is not written out. The manifests are the user's code and stay in gitignored
  `tasks/local/`; what ships is `tasks/recipes/<donor>.json` — the procedure — and
  `tasks/local-ledger.json`, a per-task manifest hash with the two verdicts and the tool versions
  behind them. A reader with none of the data can still count the corpus, check that every task
  was proven rather than assumed, and re-derive it against their own copy of the donor.
- The `conftest.py` floor at mint time: every `conftest.py` from the repository root down to each
  held test's directory is declared held, read at the parent commit, and a held set that omits one
  is refused by name. This **narrows** cheat 10 and does not close it — ~22% of `donor A`'s
  mintable commits (49 of 224) also touch a non-`.py` file no conftest rule would ever see — so
  the cheat stays a documented residual in the corpus and in `docs/ROADMAP.md` § 3.
- A four-gate eligibility filter for source A (SWE-bench-Lite) — format, environment,
  collectability, liveness — proving eligibility per instance instead of assuming it. **One of 300
  instances is eligible** (`pallets__flask-4045`), and all 299 refusals are committed in
  `tasks/public/ineligible.json` against the gate that refused each: 192 format, 106 environment,
  1 collectability. The rejection ledger is the deliverable; the count is its honest output, and
  one instance is not a benchmark-sized set.
- `environment.import_roots` on every manifest — the repository-relative directories holding the
  code under test — put on `PYTHONPATH` by STRICT, resolved against the run's own checkout.
- Donors whose layout cannot be read from their build configuration, and donors with no lockfile,
  are refused **by name** rather than guessed at. A wrong import root does not fail loudly; it
  fails by passing, and an unpinned donor would have its versions chosen by the date the mint ran.
- `PREREGISTRATION.md`, committed at the repository root **before any number about a model
  existed** — which is the whole of its value, since a headline rule chosen once results are
  visible describes them rather than constraining them. It fixes the headline as the change in
  STRICT-PASS **count** on the held-out source-B split, published over its denominator with
  coverage and `N` beside it and never as a rate; defines every metric before any is measured;
  carries the baseline protocol, including what it means for a changed pinned input to invalidate
  a series; and commits to publishing both sources together, with a disagreement between them
  reported as a finding rather than resolved by picking the flattering one.
- **No numeric success threshold is pre-registered, and none may be added once a number exists.**
  No baseline has been measured and no base chosen, so any bar set today would be invented — and
  one set later would be post-hoc selection wearing the costume of rigour. Three items are named
  as open instead of guessed, each with the dated amendment that closes it and the measurement it
  must precede: the held-out split, the retry count `R`, and which open base is fine-tuned.
- Five limitations disclosed in advance rather than discovered in the result: source B's
  self-selection — **and that its stated mitigation did not land**, since `donor C` was refused
  for having no `uv.lock`; source A being 1 eligible instance of 300 and reported per-instance;
  cheats 6 and 10 surviving into any reported `N`, with the verifier's bound that it confines what
  a run may write and not what it may read; source B's data never leaving the box, which limits
  what an outsider can audit; and that pre-registration is a timing control and **not** an
  independence control, this being a solo project.
- Guards in `tests/test_docs.py` holding the document shut: every section present, **no
  placeholder in any spelling** — the sibling project's `PHASE0_RESULTS.md` carried `TO-BE-FILLED` for ten days
  — **no figure about a model**, banned as glyph and as word so the rule cannot be spelled around,
  and nothing under `reports/` in a tree lacking the file. That last guard is exercised against
  two synthetic trees, because `reports/` does not exist yet and a guard nobody has watched fail
  may be passing vacuously. It proves co-existence, not ordering: a single commit adding both
  would satisfy it, and the document states that limit itself rather than letting the test read
  as stronger than it is.

- **Every `docs/ROADMAP.md` citation the pre-registration makes is resolved against the lines it
  names**, each paired with an anchor that must appear inside that exact range, and the pairing
  asserted exhaustive in both directions so a new citation cannot be added without an anchor. This
  guard exists because the slice broke it: the same commit corrected a paragraph in § 4, which
  pushed every later section down by about twenty lines, and five citations written against the
  pre-edit file pointed into the wrong section by the time it landed. An adversarial review caught
  it and nothing in the suite did, because a substring assertion does not know what line it is on.
  **A document whose stated value is that a stranger can check it cannot ship pointers that
  dissolve when their target moves.**

- **The P1 base-model bake-off** (`python -m whetstone.bakeoff.run`, deliberately not a
  `whetstone` subcommand — it is an operator tool, not part of the product surface), which closes
  the last P1 exit criterion. Three candidate open bases each produce one greedy patch per task
  through `mlx-lm`, every patch is graded by the **STRICT** verifier, and both sources are scored
  and published together. The output is `reports/baseline/report.md` with its machine-readable
  `report.json` and `cost.json`, and it is **the only place in this repository where a figure
  about a model may live**.
- **No base is selected, and the zero is published rather than re-run until it flattered someone.**
  Not one candidate solved a single task on the declared source-B set, so P1's pivot signal fired,
  `PREREGISTRATION.md` § 7.3 stays open, and the response it names is an easier task stratum or a
  larger base — never a looser verifier. The failure modes differ by candidate, which locates the
  wall rather than reporting a tie.
- **A control arm, so that a zero is a statement about a base and not about a harness.** Every
  scored task is also run with an inert patch and with its own re-derived reference fix, through
  the same harness under the same environment pins, and a run whose control arm proved nothing is
  refused before it can reach the report. It was intact on every source-B run. This is the direct
  descendant of the false PASS recorded below: the lesson there was that a verdict can come from
  outside the run, and an uncontrolled zero has exactly the same shape.
- **Two bounds disclosed in the report rather than left to be found in it.** Prompts use the
  **oracle retrieval** setting — each base is shown the non-test files the reference patch
  touches — so every count is an upper bound on what the same base would do from the bug report
  alone, and may not be compared with a figure measured without retrieval. And the **generation
  contract** (prompt template, retrieval setting, sampler, token budget, extractor) is **not**
  among the pre-registration's five pinned inputs while demonstrably moving the numbers, `N`
  included; the contract states the patch-scope rule to every candidate, which makes `N` a floor
  under a disclosing contract rather than a natural rate.

### Fixed (documentation)

- **`docs/ROADMAP.md:387` stated P1's pivot signal over a set that does not exist.** It read *"any
  held-out task"*, while `PREREGISTRATION.md:242-247` leaves the held-out split open until P3 — so
  there was no such set for the signal to be read against. The wording now names the declared
  source-B set, the change is dated in place rather than made silently, and `reports/baseline/`
  publishes the disagreement between the two documents as a finding.
- **`docs/ROADMAP.md` § 4, `CLAUDE.md`, `README.md` and this file each asserted, in the present
  tense, that this repository held no figure about a model.** The bake-off makes that false, and a
  status block
  that denies the measurement it ships beside is the failure `docs/ROADMAP.md` § 4 already records
  this project committing once. All four are corrected in the commit that lands the report. The
  roadmap's copy could not simply be deleted: `PREREGISTRATION.md` is **append-only** and cites
  `docs/ROADMAP.md:364-368` on that exact sentence, so the sentence is kept inside those five
  lines as a **quoted, dated correction** — the precedent § 4 already sets for its claim about
  The sibling project — the § 4 rewrite is line-count-neutral so no later citation shifts, and all ten pinned
  citations still resolve. `tests/test_docs.py` now asserts the claim survives in the roadmap only
  inside a blockquote and nowhere in its running prose, and that P1 records **no** criterion still
  open, both spellings of the older count being forbidden.

- Five stale `docs/ROADMAP.md:NNN-MMM` citations in `PREREGISTRATION.md`, and three
  `CLAUDE.md:NNN` citations — one in `PREREGISTRATION.md`, two in `docs/ROADMAP.md` § 11 — that
  this cycle's own insertion into `CLAUDE.md` pushed further out of place. Two further stale
  citations are **left standing and reported rather than quietly fixed**: `docs/ROADMAP.md:289`
  cites `CLAUDE.md:93` for the licence in a P0 block whose parenthetical *"the file is absent
  today"* is separately stale, and `docs/ROADMAP.md:536` quotes a `CLAUDE.md` sentence that no
  longer exists anywhere in that file — it was removed as a stale claim and `tests/test_docs.py`
  now forbids its return. Both need a decision about historical framing rather than a new line
  number, which is a different change from this one.
- **`docs/ROADMAP.md` § 4, P4 overstated a sibling project's failure.** It asserted that the sibling project's
  `PHASE0_RESULTS.md` carried 20 `TO-BE-FILLED` markers; that was exact on 2026-07-28 and false
  about ten hours later, when the document was filled and recorded a **PIVOT** — a negative
  result, published. Verified by `grep -c`: 0. A claim about another project's honesty, inside our
  own section about publishing honestly, is the worst sentence in the document to leave stale. The
  transferable lesson replaces it and is sharper: the sibling project's criteria were fixed in a **planning
  file** and never copied into the document that publishes the number before the gate ran — which
  is why `PREREGISTRATION.md` sits at the repository root and not under `docs/planning/`.

### Added

- **The bake-off keeps what a base actually wrote** (`src/whetstone/bakeoff/transcript.py`), so a
  later question about a run costs a file read instead of another night of generation. It is a
  `Generator` wrapper rather than a new parameter: the model seam is one method on purpose, and
  widening it would let implementations disagree about which one a caller uses. Composed outside
  the contract seal, so a prompt the frozen contract does not carry raises without leaving a
  completion-less row behind. `--transcript` is undefaulted and is **refused under `--out`** — a
  completion quotes the user's own private repository back verbatim, and `--out` is committed.
- **An offline attributor** (`src/whetstone/bakeoff/attribution.py`) that replays stored
  completions and says which zero each rollout was. `NOT_APPLIED` in a report means only *"git
  refused it"*, which is where a malformed diff, a mis-anchored one, a wrong path prefix and a
  budget-truncated patch all end up wearing one tag; the two that matter most — git would not read
  it, versus git read it and would not apply it — are now told apart, read-only, with nothing
  under `verify/` modified. The partition is read out of the extractor's own reasons, and a
  bijection test fails the suite if a new reason appears without a bucket, so nothing drifts into
  an "other" bin.
- **A reproduction check with its limit stated in the code.** The committed report carries
  per-candidate counts and no per-task field, and the run's journal was never committed, so a
  replay can be compared only on counts — necessary, not sufficient, since one task moving between
  two buckets while another moves back cancels exactly. A run invoked with both `--journal` and
  `--transcript` is per-task checkable afterwards, which is the reason to pass both.

- `python -m whetstone.bakeoff.run --max-tokens` and `--only`. The budget was a constant compiled
  into the runtime until a transcript measurement showed it had decided an earlier answer; it is
  already a `GenerationContract` field, so a run at a different budget discloses that in its own
  provenance block rather than resembling the run before it. Both flags refuse rather than
  resolve: a budget below one token, a `--only` name matching nothing, and one matching several
  are all errors, because each would produce a clean-looking sweep that says nothing.
- `python -m whetstone.bakeoff.attribution`, the operator end of the attributor — a transcript in,
  a per-candidate cause breakdown out, offline and with no model loaded.
- A release workflow (`.github/workflows/release.yml`). `RELEASING.md` had described tag-push as
  the mechanism while stating that pushing a tag "does nothing but create a tag"; it now exists,
  and applies this project's own promotion rule to itself — a `verify` job gates both publishing
  jobs, so a red tag publishes nothing anywhere.
- `SECURITY.md` and `CODE_OF_CONDUCT.md`, and a README that states what the reward does **not**
  guarantee at the same length as what it does.

### Changed

- **Donor repositories are named by stable pseudonym, never by name or path.** Source B is mined
  from the author's own private repositories, and their names — and in two committed files an
  absolute path from the author's machine — had reached documents this project publishes. They are
  now `donor A`, `donor B` and `donor C` throughout, with the key in `tasks/README.md`; the
  sibling verification project this repository ports its verdict semantics, sandbox approach and
  inference guard from is referred to by description. No claim, count, denominator or disclosure
  changed — only identifiers — and the redaction is logged as an amendment in `PREREGISTRATION.md`
  § 10.3 rather than made silently, because that document is append-only and the edit touched
  § 6.1's text.
- `whetstone mine` now requires `--label`, and the committed recipe is named and filled by it.
  The recipe previously recorded the donor's resolved path, which published a private repository
  name and a home directory to no reader's benefit — an outside reader re-deriving a corpus
  supplies their own donor. The flag has no default on purpose: the only default available is the
  donor's own directory name, and a leak into a committed file is not undone by deleting the line
  later. `tests/test_mine_cli.py` asserts the recipe carries neither the donor's path nor a home
  path. **A residual is disclosed rather than closed:** mined task ids are `<donor>-<sha>`, so the
  donors' own names still appear in `tasks/local-ledger.json` and `reports/baseline/`; closing
  that means re-minting the corpus and invalidating all 66 recorded manifest hashes.

### Fixed

- **A false PASS on the reward path: a task passed with no patch applied at all.** For a
  `src`-layout project the tests import by package name, resolved through the venv — and the venv
  carried an editable install rooted at the *provisioning* checkout, a different directory from
  the one the reward applies patches to. The tree under verification was never imported, so the
  verdict came from outside the run and a policy submitting nothing would have been paid. Closed
  at both ends: `import_roots` on `PYTHONPATH` ahead of `site-packages`, and provisioning with
  `--no-install-project` so no copy of the project exists for a verdict to leak into. The
  ten-cheat corpus had missed it because every fixture repository was flat-layout and none was
  installed into a venv — **the defence was the shape of the fixtures, not anything the verifier
  did.** `tests/adversarial/test_inert_checkout.py` is the regression, and it asserts the mirror
  too: the same task under its real reference patch still passes.

## [0.1.0] - 2026-07-27

The scaffold. No verifier, no reward, no loop, no gate, and no model code — P0 exists so that
everything after it can be built test-first.

### Added

- Python packaging: distribution `whetstonehq`, import package and CLI `whetstone`, built with
  hatchling. Zero runtime dependencies — the CLI is stdlib-only.
- `whetstone` console script exposing exactly two behaviours: `--help` and `--version`. No
  subcommand stubs; a command appears only when something stands behind it.
- `whetstone.__version__`, resolved at runtime from installed package metadata rather than
  written as a literal, so it cannot drift from what was built.
- A test suite (`pytest`) covering the CLI's exit codes and output, the version boundary
  between distribution and import package, the wired console script exercised in a real
  subprocess, and an anti-vacuity control over the parser's flags.
- Strict tooling from day one: `ruff` (line length 100) and `mypy --strict` over `src/`.
- Apache-2.0 `LICENSE`.
- CI on `macos-latest`, running ruff, mypy, and pytest, plus a step that installs the optional
  `mlx` extra and asserts `import mlx` actually succeeds — not merely that installation
  exited 0.

[Unreleased]: https://github.com/haqaliz/whetstone/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/haqaliz/whetstone/releases/tag/v0.2.0
<!-- 0.1.0 has no link: it was never tagged and never published. -->
