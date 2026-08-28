# Card — feat/morning-report/aliz

**Source:** no GitHub issue. `gh issue list --state all` returns nothing for this repo
(Issues carry no cards; the tracker in practice is `docs/planning/` + the roadmap). The
source below is the inline brief handed off by `whetstone-next` on 2026-08-28.

## Brief

Build the signed morning report: `whetstone report --last-night`, the launch path's next
unit (`docs/ROADMAP.md` § 12; declared out of scope and named as the follow-on by
`docs/planning/honest-number-report/prd.md:80,222`). It composes already-sealed local
evidence by identity — `ledger.read`, `gate.read_promotion_record`,
`baseline.read_baseline_document`, and the `bakeoff/report.py` writers — and renders one
plain-English note per night into the gitignored `/reports/local/` (pre-declared at
`.gitignore:23`; note `arm-a/` and `budget-2048/` already live there). It publishes
nothing, so the one-home guard does not move and no § 10 amendment is owed.

### Caveats carried into the dig

- **"Signed" is undefined in this tree.** No cryptographic signing exists anywhere; the
  only grounded reading is *hashed provenance* (checkpoint digests, ledger and
  promotion-record digests, tool versions). Decide it explicitly and never imply a
  signature the code does not produce.
- **No night and no real gated evaluation has ever run** (`CLAUDE.md` status block), so
  this is provable only against fixture ledgers and fixture promotion records — the gate's
  own posture. The finding must say so.
- **This is the partition guard's fourth documented function-local edge** into `loop/`
  (`tests/test_reward_path_scope_is_partitioned.py` pins exactly three today). Move the
  constant test-first, watched failing in both halves.
- **`reports/local/` already holds `arm-a/` and `budget-2048/`** from the yield probe —
  resolve the layout collision before choosing a subdirectory.

### Acceptance criteria (from the handoff, test-first)

1. The door exists and resolves "last night" by a **stated rule**, refusing ambiguity
   rather than guessing.
2. Every half-truth render is refused **by name** with nothing written: unreadable/absent
   ledger, missing promotion record, failed checkpoint re-hash, series disagreement.
3. A zero-strict-PASS night and a gate that returned `UNVERIFIED` each render as exactly
   those facts — never blank, never a win.
4. `UNVERIFIED` is never rendered as `PASS`.
5. The note carries hashes and verdicts and never task contents (locality canary).
6. The render is deterministic and byte-identical across invocations and under
   `PYTHONHASHSEED` 0/1.
7. The output home is asserted gitignored, and a published root is refused via
   `_refuse_published_root` by identity.
8. The partition guard proves exactly four edges, able to fail against a planted fifth and
   against a planted module-scope import.

## Placement on the core loop

Element ④ — the signed morning report. It reads sealed evidence; it decides nothing,
re-scores nothing, and publishes nothing. The reward path is untouched.
