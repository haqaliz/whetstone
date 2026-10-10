# Aspect spec — sheet

**Unit:** `night-heldout-seam` · **Aspect:** `sheet` · **PRD:** `docs/planning/night-heldout-seam/prd.md`.
**Scope:** `docs/planning/p2-rollouts/night-door/runbook.md` only — the night sheet. No
historical sheet is rewritten.

## Problem slice

The sheet is the operator's verbatim command list for the next night, and it must live in the
post-§ 10.16 world: ids that exist, the held-out document pinned and excluded, run ids the
operator actually declares, arithmetic that matches the shipped exclusion order, and a
leakage step at the source.

## In-scope requirements (PRD R1-R7, R10; N12)

- Both command blocks pass `--heldout $REPO/tasks/heldout/source-b.json` (probe first, then
  night) and the five dev ids in their `donor-b-*` form; no `belay-`/`contig-` id anywhere.
- A new "held-out set" passage: the § 10.16 citation (Type 1, 2026-09-27), the scorable rule,
  the two dev ids that are held-out members, the "exclusion, never refusal" statement, and
  the digest read-back halt (the ledger's held-out record must name the committed document's
  digest) — the gate runbook's Step-5 wording adapted to the ledger.
- Run ids `<declared-at-run-time>` in both commands; `probe-001`/`night-001` appear nowhere
  as run ids; the paths in the sheet's prose (`runs/night-probe/<run-id>/ledger.json`,
  `runs/nights/<run-id>/draws/…`, `checkpoints/<run-id>/provenance.json`, the post-night
  `check-probe --run` path) resolve from the declared ids.
- The denominator passage states 51 private (66 − 5 dev − 10 held-out not already
  dev-excluded) + 1 public = 52 tasks drawn `K` times, with the exclusion-order reason.
- "After the night" gains the `whetstone check-leakage --run <the night> --heldout
  $REPO/tasks/heldout/source-b.json` step with the halt rule and the "unchanged when the
  candidate is absent" note (no-example nights stay exit 0; a leak names the task and halts
  here, before a checkpoint exists).
- Framing and continuity edits (the sheet now commands a *next* night): the probe-decision
  rule's fresh-id sentence, the v3-ledger note for the probe (N12), "the first night" header
  adjusted where it now says "the next night".
- The sheet's prose keeps its existing honest content: candidate resolution, GPU
  serialization, dev-overlay + `K`-is-not-a-flag + retries-on-by-default notes, absolute
  paths, `reports/` refusal, `--timeout 900`, `--recorded-on` as an input, halt conditions
  (incl. zero-yield as a published outcome), the killed-night resume rule, the read-back
  order and the byte re-verification step — updated only where the run-id/paths make them
  follow the declared ids.

## Out-of-scope boundaries

- No other runbook; no `src/` change; no change to `check-leakage`'s or `check-probe`'s
  output; no new flag names (the sheet uses only shipped flags).
- No numbers beyond the verifier's: the denominator is corpus arithmetic, stated as
  arithmetic, never as a measured figure.

## Acceptance criteria

1. Every command in the new sheet parses against the shipped parser (`whetstone.cli.
   build_parser`) — proven by the guard suite, not by hand.
2. The guard suite (aspect `guards`) is GREEN against this sheet; every new pin's RED was
   already demonstrated against the old sheet.
3. The sheet contains no `belay-`, `contig-`, `probe-001` as a run id, `night-001` as a run
   id, `§ 10.7`, or the "62 tasks" sentence.
4. The two overlap ids and the 51/52 arithmetic are stated in the sheet, and the stated
   arithmetic follows the shipped exclusion order (`night.py:249-261`).

## Dependencies and sequencing

Second aspect: consumes the `guards` RED. The rewrite is prose; each paragraph that a guard
pins is written to the wording the guard asserted (the two sides land in one commit).

## Open questions / risks

- The exact halt-step position within "After the night" (before or after the byte
  re-verification) — decided in the plan; neither order changes what the step proves.
- The wording of the digest read-back must match the gate runbook's shape closely enough for
  a future reader to see they are the same discipline — the plan quotes the source sentence.