# Spec — measurement-run

**Slice:** `whole-function-edit-finding` / `measurement-run` · **Written:** 2026-10-01 ·
**PRD:** `docs/planning/whole-function-edit-finding/prd.md` § 4.1 (M1–M8).

## Problem slice

No run has ever prompted under a whole-function contract, so the direction must be **measured
before it is built** — the rule fixed **before** the run and exposed as a command exit
(0 GO / 1 NO-GO / 2 refusal), exactly the `patch-representation` and `edit-contract-finding`
unit shape. On NO-GO this aspect is the whole unit: nothing is built beyond it, and no
amendment is made.

## In scope

- The whole-function renderer (a sibling of `render_prompt` and `render_line_range_prompt`),
  off the reward path, plugged through the measurement driver.
- The measurement driver's renderer seam: default byte-identical to v0.17.0; the
  whole-function renderer selectable for this run.
- The offline instrument: stdlib-only, deterministic, no model, on the
  `bakeoff/addressability.py` boundary, with the pre-committed rule below.
- The guarded runbook commanding the operator's GPU pass from the primary checkout.
- The finding (committed after the operator's run).

## Out of scope

- **Any change to `rendering.py`, `run.py`, `night.py`** — a NO-GO must leave them
  byte-identical.
- **Any change under `verify/` or `tasks/`** — the reward path and the gate's rule stay
  byte-identical (the card's guardrail).
- The GO-gated contract aspect (`whole-function-contract`, PRD § 4.2) and the GO-gated
  amendment (`amendment-10-x`, PRD § 4.3) — unplanned here, by design.
- Any yield claim, any success threshold, any loosening of the pre-committed rule.

## Acceptance criteria (written first — these are the failing tests)

- **AC1 — the renderer.** A whole-function renderer exists under `bakeoff/`, poses the
  grammar of § "Format" below, is byte-deterministic, and refuses held-test sources by name
  (the `HeldTestInSources` precedent). The default prompt path (`render_prompt`) is
  byte-identical.
- **AC2 — the driver seam.** The measurement driver gains a renderer choice whose **default
  reproduces v0.17.0 behavior byte-identically** (a test asserts the default path's output is
  unchanged). The whole-function run: K = 1 greedy by identity, retries 0, `RUN_SEED = 1`
  declared, `pool=None`, the **verifier never entered** — every rollout row is `UNVERIFIED`
  with the measurement detail — and per-task `prompt_sha256` recorded.
- **AC3 — the population, pinned by identity.** The 16 tasks of § "Population" below; a
  run whose task set differs is refused (`PopulationMismatch`), and a held-out member is
  never a rollout target.
- **AC4 — refusals write nothing.** Every named refusal exits 2, prints the reason to
  stderr, and writes no evidence. Exit 0 only when journal, transcript **and** manifest are
  all on disk, the manifest written last.
- **AC5 — the control arm.** The control probe per task, folded over every draw, must be
  `INTACT`; otherwise the run refuses (`ControlNotIntact`) and writes no evidence.
- **AC6 — the instrument's classes.** Per-class fixtures assert every class and the
  worst-first ladder of § "Classes" below; `UNCLASSIFIED` stays in the denominator; the rule
  sentence is cross-pinned into every output document (schema `whetstone-resolvability/1`);
  an empty population is **refused, never decided**.
- **AC7 — the decision.** `GO iff count(RESOLVABLE) * 2 > population` — the inequality
  constant cross-pinned to this spec's sentence; the decision is the command exit 0 GO /
  1 NO-GO / 2 refusal.
- **AC8 — the runbook, guarded code-first.** A test module guards the runbook: the sheet
  spells all 16 tasks (length asserted 16), pins the candidate
  (`mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`, § 10.10), pins the two documents by
  digest, pins the renderer (`whole-function`), names no worktree, and commands absolute
  paths from the primary checkout. The guard is written first and watched failing against a
  deliberately wrong stub sheet, then against the real sheet.
- **AC9 — the finding.** A committed finding (doc; review-verified): decision and exit,
  the rule restated, the partition in full with the population-equality join check, the
  control arm `INTACT` on every draw, completions described in words, corroboration beside
  and never pooled, disclosures (§ "Proxies" below), what is not claimed, and roadmap
  placement naming the remaining pre-committed responses (raise *k*, the portability arm's
  CPU dtype). **On NO-GO it records that nothing was built and no amendment was made.**
- **AC10 — hygiene.** The AST inference guard, the reward-path partition guard, the one-way
  import test, and `tests/bakeoff/reward_amendments.py` (the `verify/` freeze) stay green;
  nothing under `verify/` or `tasks/` changed.

## Dependencies & sequencing

- The pinned base's weights verified locally (`weights/`, § 10.10 revision
  `d1e3b690c8e225d7795bccddf971ca6be68b2012`) — machine-level, referenced by absolute path
  from the primary checkout, never fetched in the worktree.
- The two sealed documents (`tasks/stratum/easier.json`, `tasks/heldout/source-b.json`),
  consumed through their fail-closed loaders.
- The v0.17.0 measurement machinery as the template (`measure.py`, `addressability.py`,
  `tests/bakeoff/test_measure_runbook_guards.py`).
- Sequence: renderer → driver seam → instrument → runbook + guards → (human checkpoint) →
  operator's run → finding.

## Open questions / risks

- **R1 — the parse proxy.** The gate is a standalone `ast.parse` of the body **wrapped in a
  synthetic `def`**. It is sharp at fragments (grammatical only in context) and sharp at
  indentation (a body at column 0 fails the wrap). The class rule fixes the second: a
  wrapped-parse failure that is an `IndentationError` is **MALFORMED** (the format requires
  the body at the function's indentation); any other parse failure is **NOT_PARSEABLE**.
  Splice-in-context is the sub-count beside the gate, never decisive; the finding discloses
  the sharpness.
- **R2 — one exposure.** The base meets the format once; NO-GO says the necessary condition
  failed on first exposure, never a yield claim. The finding says so.
- **R3 — NO-GO is a result.** The direction is then measured and spent; the unit ships the
  instrument, the finding and nothing else.
- **R4 — the format's bounds.** Body-only replacement cannot express signature-changing
  fixes; one function per rollout cannot express multi-function fixes. Bounds disclosed in
  the finding, not repaired.
- **R5 — no scorable filter on the stratum band.** The three `NO_ORACLE` members get no
  prompt and stay in the denominator; the pre-committed rule claims no filter (the
  edit-contract disclosure, `edit-contract-finding/measurement-run/finding.md:75-80`).
- **R6 — a better base would change the answer.** Pinned to the § 10.10 base; a base change
  is a further Type 1 amendment.

---

## The pre-committed rule (fixed before any rollout runs)

### Population

The **16** tasks of the easier-stratum band's membership (19) minus the held-out document's
membership (12), the overlap being exactly three members —
`donor-a-6884ed72a9e9`, `donor-a-c6e4d4c4de87`, `donor-a-c7cee63e3cab` — derived by
**identity** from the two documents through their fail-closed loaders:

```
donor-a-128bcb99b701   donor-a-16213e62eae1   donor-a-2ef3383b0ce7
donor-a-2f4e497580ff   donor-a-34daf85182d5   donor-a-5e25b106874c
donor-a-6005d7ec06f5   donor-a-7975de5439dc   donor-a-b7c53b77453a
donor-a-d601ff2d0ec0   donor-a-ec3af08b913d   donor-a-f100a90e47f2
donor-b-0f8651175ef8   donor-b-45740535725b   donor-b-c57246c7841a
donor-b-dbf19c8009dd
```

Three members are `NO_ORACLE` (`donor-a-128bcb99b701`, `donor-a-16213e62eae1`,
`donor-b-45740535725b`): no prompt is rendered for them, they are `UNCLASSIFIED`, and they
**stay in the denominator**. The stratum document digest is `87954587a51e72921e8f6d9a1e9c22a73031720bd5fd0a31d5c3fc108eed1dd9`; the
held-out document digest is `6b5fbd49e5d20fada7c53c53d5076cf846210ea6a4522046e1ba025142e9980d`.

### Run

One greedy attempt per task (K = 1, `sampler_for(1)` — the bake-off's greedy sampler by
identity), retries 0, `RUN_SEED = 1` declared, the pinned candidate
`mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`, the **verifier never entered**, the control
arm probed per task and required `INTACT` on every draw, `pool=None` always, `--timeout 900`
(the night door's own value). Evidence (journal, transcript, manifest) written only when the
whole run succeeded; the manifest written last. The run's `prompt_sha256` is new by
construction — the finding states the figures are comparable to nothing prior.

### Format

The completion is one block, pinned by the prompt:

```
EDIT <repo-relative path>
FUNCTION <name>
<<<<<<< REPLACE
<body — the new function body, at the function's indentation>
>>>>>>> END
```

- `<path>` names one of the shown source files (the oracle sources at `base_commit`).
- `<name>` names one **module-level** `def`/`async def` in that file; the harness finds its
  extent (decorators + signature from the original, body replaced) via AST at `base_commit`.
- The body is the only replacement surface: **no def line, no signature restatement** — the
  format never asks the model to transcribe existing code.
- One block per rollout; a completion with more than one block is `MALFORMED`.

### Classes

Worst-first, per rollout:

```
UNCLASSIFIED > MALFORMED > NO_FILE > AMBIGUOUS > UNKNOWN_FUNCTION > NOT_PARSEABLE > RESOLVABLE
```

- **UNCLASSIFIED** — no graded transcript record, task not offered, `prompt_sha256`
  disagreement with the manifest, checkout not materialisable, non-UTF-8 file, or the
  `NO_ORACLE` members. Stays in the denominator; never a refusal.
- **MALFORMED** — the grammar of § "Format" is violated: missing `EDIT`/`FUNCTION` header,
  stray or unclosed markers, more than one block, a def line or signature restatement in the
  body, or a body whose wrapped parse fails with `IndentationError`.
- **NO_FILE** — the `EDIT` path is not a shown source file (or is absent from the checkout
  at `base_commit`).
- **AMBIGUOUS** — the `FUNCTION` name resolves to more than one module-level function in
  the named file.
- **UNKNOWN_FUNCTION** — the name is not a module-level function in the named file.
- **NOT_PARSEABLE** — the body fails the wrapped standalone parse (any failure that is not
  an `IndentationError`).
- **RESOLVABLE** — path in the shown set and present, name unique and module-level, body
  passes the wrapped parse.

### Decision

**GO iff `count(RESOLVABLE) * 2 > population`; otherwise NO-GO.** The rule is a go/no-go for
building the contract — never a claim about yield, never a grade of correctness. Exit 0 GO,
1 NO-GO, 2 refusal. An empty population is refused, never decided.

### Sub-counts (beside the partition, never decisive)

- **splice_in_context** — re-parse the file at `base_commit` with the body spliced over the
  resolved extent; the count of RESOLVABLE rollouts whose file still parses. The sharp
  proxy, reported beside.
- **outside_shown_set** — the count of completions whose `EDIT` path is real but outside the
  shown set (including any held-test path). The scope-adjacency signal, reported beside.

### Proxies, disclosed in the finding

The wrapped-parse gate (fragment sharpness; the indentation class rule), the one exposure,
the new `prompt_sha256`, the `NO_ORACLE` denominator members, and the format's bounds
(body-only, one function per rollout) are each disclosed in the finding — never hidden behind
the letter of the rule.