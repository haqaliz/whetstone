# PRD — heldout-scorable

**Unit:** `feat/heldout-scorable` · **Written:** 2026-09-27, after the interview (confirmed:
pairing with the #62 re-mint folded in; schema string kept; re-mint swap scripted as a runbook
step). **Sources:** `docs/planning/_card/issue.md`, `docs/planning/heldout-scorable/understanding.md`,
issue #60 (open), issue #62 (open). **Core loop element:** ③ never-regress promotion gate.

## Problem statement

The promotion gate cannot fire. `gate-001` (2026-09-26) reduced to `UNVERIFIED`: 2 of the 12
members of `tasks/heldout/source-b.json` — `contig-10476d50e5e8`, `contig-16213e62eae1` — are
**permanently `NO_ORACLE`**: their file sets exceed `ORACLE_BUDGET_CHARS = 80_000`
(`src/whetstone/bakeoff/sources.py:150`), refused whole by `_read` (`:465-497`), deterministic
(a pure function of immutable git objects), and unaffected by retrying (`R = 3` went
untouched). Promotion requires `unverified == 0` (`src/whetstone/loop/gate.py:207-208`), so
**no candidate, however good, can ever be promoted against this held-out document** (#60),
and P4's honest-number report reduces to "no headline". The roadmap's pre-committed response
to a gate that cannot fire — "a more reliable sandbox, never a looser gate"
(`docs/ROADMAP.md:451-453`) — assumes transient unverified; `docs/STATUS.md` (2026-09-26)
records that this is structural: "A perfect sandbox changes nothing."

The fix is a property of the **selection**, not of the check (issue #60's own framing): a
held-out set is a *chosen* set, and choosing members whose oracle can be built under the
declared budget is a rule about the selection — the same shape § 10.7 already established (a
pre-committed rule in code, a sealed document, committed before it scores anything).

**What must not happen** (issue #60, binding): the gate loosened; `NO_ORACLE` excluded from
the gate's denominator; the budget raised to make a specific document pass.

## Goals & success metrics

- **The gate can reach a real decision.** The next gated evaluation against a re-derived
  document exits `promoted` or `rejected` when the data supports one — never `UNVERIFIED`
  *because the document itself contains unscorable members*. (Whether the decision is a win
  or a `rejected` 0-0 is the data's answer, not this unit's; a zero is a valid P4 outcome.)
- **The re-derivation is honest by construction.** Every held-out member's oracle can be
  built under the declared budget — *proven by a differential test*, not asserted.
- **Nothing else moves.** Gate decision table, three exits, `unverified == 0`, `R = 3`,
  `NO_ORACLE`-in-denominator, verifier, budget value (80,000): byte-identical to master.
- **The pre-registration is kept.** A dated Type 1 amendment pre-commits the new rule;
  the document is re-derived and committed before any candidate scores against it.

**Success is measurable** by: the differential test passing (excluded set == bakeoff's own
`NO_ORACLE` set), the recomputation test green, the loader refusing stale/hand-edited
documents by name, and a gate runbook whose next operator run uses the new document.

## User personas & scenarios

**The operator (the founder).** Runs the launch chain: night → gated evaluation → baseline
spend → P4 report. Today the chain is blocked at step 2 with no fix reachable by any run. After
this unit: runs the amended gate runbook verbatim and gets a decision.

**A later session (whetstone-next / a new worktree).** Reads the amendment and the document
to know which split is live and why. The rule must be readable from `PREREGISTRATION.md` and
`heldout.py` without archaeology.

## Requirements

### Must-have

1. **A shared oracle-fittability predicate.** A named, tested function in
   `src/whetstone/bakeoff/sources.py` decides, for a task and its donor, whether the oracle
   can be built under `ORACLE_BUDGET_CHARS` — the same budget logic `_read` enforces, lifted
   so the bakeoff and the held-out derivation consume **one** rule by identity (asserted
   `is`). Fittability is a pure function of the task manifest + the donor repo at the mined
   commit + the `base_commit` tree — deterministic and permanent for a fixed corpus.
   **The predicate classifies structurally, never by machine state**: the path set and the
   `base_commit` tree are immutable git objects, so an exclusion is permanent. A task whose
   donor cannot be read at derivation time is a **named refusal** (the bakeoff's own
   skip-with-reason posture), never a classification — a non-permanent exclusion would
   remove a member from the held-out draw for a reason that is not the rule.
2. **The held-out rule excludes the class, by digest.** `heldout.py` gains a rule function
   (added to `_RULE_FUNCTIONS`, `heldout.py:168`) applying the predicate; `_RULE_PARAMETERS`
   gains `oracle_budget_chars`; the derivation **refuses by name** if the parameter disagrees
   with `sources.ORACLE_BUDGET_CHARS`. Any rule edit invalidates the committed document by
   design (the § 10.7 discipline, `PREREGISTRATION.md:514-522`).
3. **Floors over the filtered population.** `select_band` takes the first `_PER_BAND_TAKE`
   members of each *filtered* band — a band with fewer scorable members takes fewer than 4,
   so the floors become the binding statement: `_refuse_unmet_floors` runs over the
   post-exclusion draw (total ≥ `MIN_HELDOUT`, per band ≥ `MIN_PER_BAND`, non-degenerate);
   unmet floors → `EmptyHeldout` — the published finding, never a loosened floor. § 10.7's
   "4 tasks per band" sentence is superseded by the amendment and must be stated as such.
4. **The document records the exclusion.** A new digested field (e.g. `excluded`:
   `{task_id: reason}`) names every corpus task the rule excluded and why; `refusals` keeps
   its stratum meaning ("no difficulty measured") untouched. The two `NO_ORACLE` tasks stay
   in the corpus, in `difficulty`, in `bands` — excluded from the *draw* only.
5. **The loader fails closed on superseded and doctored documents.** A document missing the
   new field (the pre-amendment shape) is refused by name; the existing 22 named refusals
   (rule-digest mismatch, hand-edit, membership/band/difficulty consistency) all stand, plus
   two new ones: a membership naming an `excluded` id, and an `excluded` entry naming an id
   not in the corpus. `check-leakage` keeps reading the document through the same loader.
6. **The pairing with #62, one re-derivation.** The machine corpus is swapped to the staged
   re-mint (`_sandbox/remint/`, primary checkout) by a scripted, guarded operator step;
   `tasks/local-ledger.json`, `tasks/stratum/easier.json` and `tasks/heldout/source-b.json`
   are re-derived/re-labeled and committed **together with the rule change** that produced
   them; `test_the_recomputed_document_equals_the_committed_one_field_by_field`
   (`tests/loop/test_heldout_document.py:129-167`) stays green.
7. **A dated Type 1 amendment** (§ 8.1), committed before any candidate scores against the
   new document: pre-commits the rule; states the § 3 series consequence (prior figures keyed
   to the old document — night denominators, `gate-001` — are non-comparable; the old series
   is never extended); **states in words what a decision on the new document means**: the old
   series is superseded, the two `NO_ORACLE` tasks stay in the corpus with their status
   reported (never hidden), and the new series stands on the new document alone — a
   `rejected` 0-0 is a valid first decision, never dressed as a win; the "does not change"
   clause (§ 10.10's base, the verifier, the gate's terms untouched); the § 9 log row; the
   status-paragraph edit only where the § 10.10 precedent allows; shape guard in
   `tests/test_docs.py` watched RED first.
8. **The gate runbook rewritten code-first** (the `gate-untrained-incumbent` /
   `probe-decision-gate` precedent): the held-out paragraphs point at the new amendment and
   the new document; `tests/test_gate_runbook_guards.py` gains the new pins, watched failing
   against a stub sheet before the sheet is edited.

### Should-have

9. A differential test, per direction, over the machine corpus: predicate-false ⟹
   `oracle_sources` refuses (nothing is excluded that the bakeoff could build); predicate-true
   ⟹ `oracle_sources` builds under a readable donor (nothing is excluded *only* because of
   machine state). The reason-class of a `oracle_sources` refusal is never silently pooled —
   a refusal whose class is not the budget rule is checked by name, not counted.
10. The re-mint apply step is a runbook step with a guard (like the launch-chain sheets:
    `REPO` export, absolute paths), not a prose instruction — including a dry-run or
    verification that the swapped manifests are the staged re-mint (label-form ids, sha12s
    unchanged), and a **snapshot of the pre-swap corpus** (e.g. `_sandbox/pre-remint/`) so
    the evidence behind gate-001 and the portability figures survives the swap (the ledger's
    git history keeps hashes, never manifests).
11. Regression pins: the night's held-out exclusion and `--stratum` banding consume the new
    document unchanged (by identity), and a gate pointed at a pre-amendment document refuses
    by name at the loader.

### Nice-to-have

12. A `whetstone` CLI surface for the derivation (today it is module-only
    `python -m whetstone.loop.heldout`) — **not required**; the runbook invokes the module.

## Technical considerations

- **Where the predicate lives:** `sources.py` (it is the oracle contract's rule). The
  heldout rule function delegates to it by identity; `inspect.getsource` on the wrapper
  covers the wrapper, `_RULE_PARAMETERS` carries the budget *value* so the digest covers the
  number that matters.
- **No checkout needed at derivation time:** the predicate reads the commit's path set
  (`git show --name-status`) and the `base_commit` tree blobs (sizes; contents only where
  the char-count check needs them) — immutable objects, deterministic, no sandbox, no
  network. The derivation runs on the machine with the donors (the recomputation test
  already does).
- **Donor resolution:** `Path(task.repo_url)` per `_from_donor` (`sources.py:263`); under
  the re-mint's label-form `repo_url` the derivation resolves donors exactly as the bakeoff
  does today; a task whose donor cannot be resolved is refused by name at derivation time
  (skip-with-reason — the bakeoff's own posture, `sources.py:268-276`).
- **Gate/check-leakage consumption:** unchanged code paths; the gate's `read_document` by
  identity now also refuses a stale document (must-have 5) — that is a refusal, not a
  semantic change.
- **Test surface:** `tests/loop/test_heldout.py` (module units), `tests/loop/test_heldout_document.py`
  (recomputation/schema pins — the schema-string pin at `:321-326` may need updating),
  `tests/bakeoff/test_oracle_sources.py` (budget semantics), `tests/test_docs.py` (amendment
  shape), `tests/test_gate_runbook_guards.py` (runbook pins). Machine-corpus tests run on
  the operator's machine and skip in CI (established pattern).
- **Machine-state dependency:** the recomputation test resolves the primary checkout's
  corpus via `git worktree list --porcelain` — the re-mint swap happens on the primary, and
  the worktree's tests read it from there. The swap must happen before the derivation
  aspects' tests can pass; the runbook step is part of this unit.

## Risks & open questions

- **Cherry-picking optics (the #62 caution).** Re-rolling a pre-registered input "immediately
  after discovering that input is what stops the gate firing" is exactly what `docs/STATUS.md`
  (2026-09-26) declined to do. This unit's answer is the discipline itself: one dated Type 1
  amendment, rule fixed and committed **before** the draw, the exclusion applied to the
  *class* (oracle-unfittable), never to the two named tasks. The amendment must say this in
  words. (Open: whether the reviewer reads it as sufficient — resolved by the review gate.)
- **The exclusion changes the draw.** With the re-mint's label-form ids, 10 of 12 members
  change by construction (#62's measurement); with the filter, the two `NO_ORACLE` members
  additionally leave the draw. The new membership is *measured during the unit*, never
  predicted here — no number is invented.
- **Schema string kept at `whetstone-heldout/1`.** The new field is required, so a
  pre-amendment document refuses at the loader — the staleness guard. If the reviewer
  prefers an explicit `/2` bump, it is a one-line change + the schema pin updates; decided
  at the review gate.
- **`refusals` vs `excluded` semantics** must not blur: `refusals` = "no stratum difficulty
  measured" (today empty); `excluded` = "measured, but the rule cannot draw it". The loader's
  checks are extended, never overloaded.
- **A `rejected` 0-0 is the likely first decision** (gate-001's sides both scored 0 of 12
  where scorable). The unit is a liveness fix, not a yield fix; the runbook and amendment
  must not imply otherwise — the amendment states it in words (must-have 7).

## Out of scope

The budget value (80,000 stays); the gate's decision table, `unverified == 0`, `R = 3`, the
three exits, and the `NO_ORACLE`-in-denominator semantics; the verifier and the reward path;
the corpus's generation-time `NO_ORACLE` handling (the two tasks stay in the corpus and stay
unscorable — excluded from the held-out *selection* only); raising `K`; the line-range
addressing lead (issue #64); issue #66 (the publish-readiness section); a `whetstone` CLI
surface for the derivation; anything requiring data or training to leave the box.

## Aspect decomposition

| Aspect | Boundary | Depends on |
|---|---|---|
| `oracle-predicate` | `sources.py`: the named fittability predicate, shared by identity with `_read`'s budget rule; differential + unit tests | — |
| `heldout-rule` | `heldout.py`: the rule function, `_RULE_PARAMETERS.oracle_budget_chars`, floors over the filtered population, `excluded` field, loader evolution (stale refusal), document regeneration machinery | `oracle-predicate` |
| `rederivation` | Operator step: staged re-mint applied to the machine corpus (guarded); `local-ledger.json`, `stratum/easier.json`, `heldout/source-b.json` re-derived and committed; recomputation tests green | `heldout-rule` |
| `amendment` | `PREREGISTRATION.md` § 10.x + log row + status paragraph; `docs/ROADMAP.md` dated correction; `tests/test_docs.py` shape guard RED→GREEN | `heldout-rule`; parallel with `rederivation` (amendment states the rule, not the membership) |
| `gate-runbook` | Gate runbook rewritten code-first; `tests/test_gate_runbook_guards.py` new pins RED first | `amendment`, `rederivation` |

Sequencing: `oracle-predicate` → `heldout-rule` → (`rederivation` ∥ `amendment`) → `gate-runbook`.