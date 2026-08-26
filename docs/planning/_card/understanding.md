# Understanding — baseline-measurement

## What this work is really asking

P4 slice 1: turn `PREREGISTRATION.md` § 3's baseline protocol from a rule into machinery. The
pre-registration commits to a **pinned baseline checkpoint** — the untrained open base — scored
on the held-out set by the STRICT verifier, with provenance committed, **measured once,
re-measured never**, and a baseline `N` (the untrained base's weak-vs-strict differential) so a
final `N` later answers "did the loop learn to cheat more?" (`docs/ROADMAP.md:494-503`). Today
that protocol is **unspent and unbacked by code** — there is no baseline door anywhere in
`src/whetstone/` (confirmed by the dig: `grep -rn "baseline"` over `src/` hits only prose).

Three deliverables:
1. A **baseline-checkpoint writer** that materializes the untrained open base as a
   re-verifiable checkpoint (weights-style hashing; `sft.verify_checkpoint` by identity).
2. A **measurement door** that scores that single checkpoint on `tasks/heldout/source-b.json`
   through the fail-closed loader by identity, running **STRICT and WEAK both** so baseline `N`
   is measured (`report.tally`'s `weaker_wins`, the one place N is defined —
   `src/whetstone/bakeoff/report.py:443-447`).
3. A **committed baseline artifact** (schema `whetstone-baseline/1`) whose loader refuses a
   second measurement by name — the measured-once guard.

The night has not run; this is the "before" that every P4 delta is computed from, and § 5 pins
it **before anything trains** (`docs/ROADMAP.md:496-498`).

## Core-loop placement

Element ③/④ boundary: it does not touch the reward (the verifier stays byte-untouched,
execution-grounded — this unit only *scores* through it) and does not change the gate's
promote rule. It is the "before" anchor that makes element ④ (the honest number) and the
never-regress gate's comparisons provable. `UNVERIFIED` handling is inherited wholesale from
`tally`/`verdict.reduce` (UNVERIFIED ranks above PASS; unverified stays in the denominator).

## Affected areas (from the dig, with file:line)

- **`src/whetstone/loop/sft.py`**: checkpoint format is **training-shaped** — `write_checkpoint`
  requires `TrainingArgs`, `CapacityProbe`, `dataset_digest`, `run_seed`, `valid_split`
  (`sft.py:400-411`); `sft.train` refuses `examples < 1` (`sft.py:328-334`); `verify_checkpoint`
  refuses an empty `files` list and an empty directory (`sft.py:421-426, 480-483`). **No
  "untrained base" materialization exists.** The baseline writer is new.
- **`src/whetstone/loop/gate.py`**: the reuse seam. `gate_engine(weights, checkpoint, ...)`
  always passes `adapter_path=checkpoint.directory` to `mlx_lm.utils.load` (`gate.py:472-476`);
  whether `mlx_lm==0.31.3` tolerates an adapter-less checkpoint dir is **unverified in-tree**
  (fixture checkpoints always carry a stub adapter). `_score_one`/`_score_side` are the
  per-task scoring seam (`gate.py:932-981`). **`SideCounts` and the promotion record carry no
  N** (`gate.py:290-317, 1116-1125`) — baseline N needs raw `Rollout`s through `report.tally`,
  not the gate's counts. `_refuse_published_root` imported by identity (`gate.py:83`) is the
  published-root refusal to reuse.
- **`src/whetstone/loop/heldout.py`**: the fail-closed loader (`read_document`, `heldout.py:407-594`),
  digest discipline (`document_digest_of`), `refuse_committed_out` (`heldout.py:667-689`), the
  `python -m whetstone.loop.heldout` door precedent. The held-out membership is **source-B only**
  (12 of 66); source A is scored separately in full (the gate precedent, `gate.py:588, 597`).
- **`src/whetstone/bakeoff/scoring.py`**: `score(...) -> Rollout` runs STRICT then WEAK with the
  same interpreter (`scoring.py:452-509`); `Rollout` carries both `strict` and `weak` on every
  record (`scoring.py:133-200`). This is the existing "both verifiers" path — reuse it.
- **`src/whetstone/bakeoff/report.py`**: `tally` (`report.py:425-452`, the single place each
  published figure is defined), `_over`/`_row`/`_counts`, `_UNCOVERED`, `Outcome.SOLVED`,
  the `_N_SENTENCE` ("N rollouts a weaker check would have scored as wins."), the
  `_NON_COMPARABILITY` sentence, and the deterministic pure writer pattern.
- **`src/whetstone/cli.py`**: five subcommands; the exit-code contract (0/1/2/3, no fifth).
  A `whetstone baseline` subcommand would be a **fourth function-local edge into the EXEMPT
  `loop` package**, tripping `_DOCUMENTED_EDGES` (`tests/test_reward_path_scope_is_partitioned.py:154-158`)
  until extended; the `python -m whetstone.loop.<module>` door (the heldout precedent) avoids
  `cli.py` entirely.
- **One-home guard**: `reports/baseline/` is **taken by the P1 bake-off** (base selection,
  explicitly *not* the pinned baseline). A new committed home — e.g. `reports/baseline-measurement/`
  — trips both guards until they move a **fifth time "on the argument"**: the exact 12-file list in
  `tests/bakeoff/test_transcript_locality.py:122-135` and the disjointness scans in
  `tests/bakeoff/test_report.py:1294-1384+`. A `k of 12` baseline figure collides with no
  existing figure (existing denominators: 1, 20, 62, 63, 64, 189, 299, 300).
- **Runbook guards**: `tests/test_night_runbook_guards.py` / `tests/test_gate_runbook_guards.py`
  pin flag surface via `build_parser`, absolute writable paths, one worktree. The baseline's
  operator sheet follows this pattern.

## Ambiguities / open questions for the interview

1. **What is an "untrained base checkpoint"?** The checkpoint format is an adapter (LoRA) on a
   base; an untrained base has no adapter. Options: (a) a `whetstone-checkpoint/1` directory
   whose `provenance.json` declares `untrained: true` with an explicit empty/absent adapter set
   and a `verify_checkpoint` extension to permit it (watched failing first); (b) materialize as
   a directory whose "files" are the base weights themselves, reusing the `Weights` hashing;
   (c) some other shape. Must keep `verify_checkpoint` by identity and stay honest that the
   bytes being re-hashed are what will be scored.
2. **Does the measurement go through `gate_engine` (base + `adapter_path`), or a new base-only
   engine path?** `mlx_lm` behavior with an adapter-less checkpoint dir is unverified — the PRD
   must decide and the tests must smoke-test (stub engine, like `gate.py:453-455`).
3. **Door form**: `whetstone baseline` subcommand (4th documented edge — extend the guard) vs
   `python -m whetstone.loop.baseline` module door (heldout precedent, no cli edge). The brief
   says "the door refuses a gitignored `--out` by name", the heldout/stratum pattern.
4. **Committed home**: a new `reports/baseline-measurement/` (one-home guard moves a fifth time,
   § 10 amendment declaring the new series) — or another committed location. § 3 says "that
   score is committed"; figures about a model may only live in a `reports/` home.
5. **§ 7.3**: the base identity is recorded as a pinned input **without** closing § 7.3 (the
   brief is explicit). But CHANGELOG notes § 7.3 "closes only by a Type 1 amendment before P3's
   baseline" — whether a § 10.9 amendment belongs in this unit or a later one must be settled in
   the interview. Whichever way, the artifact states the base identity (§ 3 pinned input) and
   the amendment log records the decision.
6. **Both sources**: § 4 requires both published together. The held-out split is source-B only;
   source A (`pallets__flask-4045`, the gate precedent scores it in full) is scored beside it,
   both denominators disclosed, disagreement-as-finding sentence.
7. **Control discipline**: the gate scores without `control.probe`/`rankable`; the bake-off
   reports are gated on `rankable`. Does the baseline measurement run a control arm? (The brief
   does not require one; the honest floor is that the harness "reaches PASS when a correct patch
   exists" — likely a fixture/self-check rather than a per-task control.)
8. **`recorded_on`** is an input, never the clock (the gate pattern) — the baseline artifact
   carries it the same way.

## Contradictions between brief and code

- The brief says "materializes the untrained open base ... in the `checkpoints/<id>/` format with
  weights-style hashing and `sft.verify_checkpoint` by identity" — but the checkpoint format and
  `verify_checkpoint` are adapter-shaped and refuse empty file sets. This is the unit's central
  design tension, not a hard contradiction: the writer is genuinely new.
- The brief's "measurement door ... with STRICT and WEAK both run so baseline N is measured" is
  directly supported: `scoring.score` returns both statuses per rollout and `tally.weaker_wins`
  is the one N definition. No gap there.
- `reports/baseline/` is taken by the bake-off and is explicitly not the pinned baseline — so the
  brief's "committed baseline artifact" needs a fresh home; nothing in the brief names one, which
  is open question 4.

## Guardrails (verified pass)

Reward stays execution-grounded (scores through the existing STRICT verifier; `verify/` untouched).
No LLM judge. No data egress (local runs; the artifact carries counts/verdicts/provenance, never
task contents — locality canary pattern). `UNVERIFIED` never counts as a win (inherited from
`tally`/`verdict.reduce`). Nothing here gets made redundant by a better base — it gets *more*
meaningful (the baseline is a new pinned series per base revision).
