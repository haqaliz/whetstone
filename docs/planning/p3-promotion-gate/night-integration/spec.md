# Spec — night-integration (aspect 2 of p3-promotion-gate)

**PRD:** `../prd.md`. **Branch:** `feat/p3-promotion-gate/aliz`. This aspect makes the night loop
exclude the held-out tasks **before training** — the honest design: leakage is prevented, not
merely detected. It mirrors the `stratum-filter` aspect of the easier-stratum unit, which is the
template throughout.

## Problem slice and user outcome

The gate's guarantee — "the candidate provably beats the incumbent on a held-out verified set" —
is empty if held-out tasks ever reach the training set. The user outcome: `whetstone run --night`
accepts the held-out document as a pinned input, excludes its membership at the partition seam
before the contract is frozen, and the ledger records the exclusion so `check-leakage` can prove it.

## In-scope requirements

1. **`--heldout PATH` on the run door** (`python -m whetstone.bakeoff.run` / the night's flags),
   consuming the committed document — aspect 1's loader **by identity** (imported, never copied,
   asserted `is`), with `exclude_heldout` applying the membership against the loaded private corpus
   at the partition seam (the `--stratum` precedent: `include_stratum` applied before freeze, so the
   seal and the scored set cover the exclusion automatically).
2. **Refusals completed, each named**: an unknown field, a duplicated membership, a member the
   document refused rather than measured (all inherited from the loader), plus the run-side refusal
   that names the id **and** the loaded ids (the `UnknownDevSubset` posture).
3. **Overlay semantics**: the dev overlay applies on top — dev ∩ held-out is exclusion, never
   refusal (declared dev ids may fall inside the held-out band). An empty scored private set after
   the overlays is refused **before** freeze. Source A is always scored in full.
4. **Ledger and task-set sentence**: the run ledger records the held-out document digest and its
   membership count; the provenance sentence names the document (the stratum filter's task-set
   sentence precedent).
5. **Byte-identity**: a run without `--heldout` is today's run byte for byte — the byte-identity
   test reproduces the unflagged contract SHA and asserts the provenance sentence is literally the
   pre-heldout sentence.
6. **Adversarial proof, watched failing first**: a doctored document (membership edited to add a
   declared dev id, digest not regenerated) and a hand-edited membership are each refused; a fully
   regenerated doctored document passes the loader by construction — the layered defence is git
   history + ordering + the recomputation test, stated, never reconciled (the stratum filter's Open
   question 5) — and the dev member it smuggles is then proven excluded end-to-end, never scored,
   excluded from both denominators.
7. The held-out path walks inference-free, and the AC2 pins (`src/whetstone/verify/`, `patch.py`,
   `attribution.py`) stay byte-identical to `origin/master`.

## Out-of-scope boundaries

- No split design (aspect 1), no gate decision (aspect 3), no retry mechanism (aspect 4), no
  overlap check (aspect 5).
- No change to how the night generates or trains — only the partition seam moves.

## Acceptance criteria (testable)

- AC1: `run --night --heldout <doc>` (with the stub-generator fixture harness) excludes every
  held-out id from rollouts and from the trainable partition; the ledger records the document
  digest and membership count.
- AC2: an unknown held-out id, a doctored document, and a hand-edited membership are refused by
  name; the smuggled dev member is proven excluded end-to-end.
- AC3: the unflagged run is byte-identical to today's — contract SHA and provenance sentence
  reproduced exactly.
- AC4: an empty scored private set after the overlays is refused before freeze.
- AC5: the loader is imported by identity (`assert ... is ...`); the held-out path imports no
  inference library (the no-inference walk covers it).
- AC6: `uv run pytest` green; ruff and mypy over `src/` green; the AC2 pins byte-identical.

## Dependencies and sequencing

- Depends on aspect 1 (`heldout`): the loader by identity and the committed document.
- Sequence: flags + parser → partition-seam filter → ledger/sentence → byte-identity test → the
  adversarial refusals (each watched failing first).
- Feeds: `check-leakage` (proves what this aspect prevents) and the real night (operator-run,
  post-merge).

## Open questions / risks

- The `--heldout` flag name and the exact flag surface are pinned by the runbook guard (aspect 6)
  — decide them here, in the parser, so the guard has a surface to pin.
- The night's existing `--stratum` and `--dev` flags compose with `--heldout`; the overlay order
  (stratum → dev → held-out) must be stated in the plan and asserted by the byte-identity and
  adversarial tests.