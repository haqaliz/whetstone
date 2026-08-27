# Spec — report-door (aspect 3 of honest-number-report)

## Problem slice

The writer is pure and dumb; the evidence lives in sealed documents. The door is the only
place that may compose them: it reads the baseline artifact, the promotion record, and both
checkpoints, verifies the series, and refuses every half-truth render by name — nothing
written, exit 2, no fifth exit code. It is a **module door** (`python -m
whetstone.loop.honest_report`), so the partition guard and the AC2 pins stay untouched.

## In-scope

- `src/whetstone/loop/honest_report.py`: `build_parser()` (single module-level parser so the
  runbook guard pins against it by identity), `main(argv=None) -> int` (0 clean / 2 refusal,
  never a traceback), a `--render` mode and a `--render-declaration` mode (mutually
  exclusive, on the `loop/baseline.py` door precedent at baseline.py:1137-1378).
- **Composition by identity:** `read_baseline_document` (loop/baseline.py:374),
  `read_promotion_record` (aspect 1), `verify_checkpoint` (loop/sft.py:499), and the writer
  pair (aspect 2) — imported, never copied, asserted `is`.
- **Refusals, each by name, nothing written (PRD requirements 4-5, decisions 3, 5):**
  unmeasured baseline (`measured: false` — a declaration has no counts to delta against);
  missing/unreadable baseline artifact; missing/unreadable promotion record; failed
  checkpoint re-hash (candidate or incumbent); **series disagreement** (promotion record's
  `heldout.document_digest` ≠ baseline series' `heldout_digest`, or the candidate's base
  identity from its provenance ≠ the baseline series' `repo_id`/`revision`); **incumbent
  base disagreement** (candidate and incumbent declare different bases); gitignored `--out`
  (`refuse_committed_out` / `_refuse_published_root` by identity); a second render of the
  same series already at `--out` (the measured-once posture by analogy with
  `BaselineAlreadyMeasured`).
- **The decision semantics (PRD gate-resolution 4):** promoted → candidate is final;
  rejected → incumbent is final, candidate disclosed; UNVERIFIED → no headline, no delta,
  decision + counts, "no comparison was made".
- **The harness-reproduces-the-number check (P4 exit criterion 3, count-level):** the door
  re-derives the report's figures from the two sealed documents (the writer is a pure
  function of them); the promotion record's counts are re-verified consistent on read
  (aspect 1's reader); the render is byte-identical across invocations and subprocesses
  under `PYTHONHASHSEED` 0/1; the baseline-side figures in the output are asserted
  byte-equal to the artifact's own figures (the loader-by-identity exception, proven here
  end-to-end).
- `--recorded-on` is an input, never the clock; a runbook-guarded flag surface (aspect 5
  pins against this module's parser).

## Out-of-scope

- Any `cli.py` subcommand (`whetstone report` is the morning-report unit's edge).
- Re-running the machine: no scoring, no model calls, no rollouts — the door reads
  documents and renders; rollout-level re-derivation is `gate._score_one`'s future, stated
  not blurred.
- The amendment, the one-home guard's sixth move, and the committed declaration artifacts
  (aspect 4); the runbook (aspect 5).
- Anything under `src/whetstone/verify/`, `patch.py`, `attribution.py` — AC2 pins.

## Acceptance criteria

1. `python -m whetstone.loop.honest_report --render ...` exits 0 and writes the three
   artifacts only when: the baseline is measured, both evidence documents read, both
   checkpoints re-hash, the series agrees, and `--out` is committable.
2. Each refusal exits 2 with the reason naming the offending document and field; nothing is
   written (`not out.exists()` asserted).
3. A declaration (`--render-declaration`) writes the pre-run state and is re-runnable (a
   declaration is not a measurement — the baseline precedent).
4. The composition is by identity: each of the five composed functions is asserted `is`.
5. The promoted/rejected/UNVERIFIED decision semantics render per PRD gate-resolution 4.
6. The report's baseline-side figures equal the sealed artifact's figures byte-for-byte,
   end-to-end (fixture artifact + fixture record through the real door).
7. Cross-process byte-identity holds (PYTHONHASHSEED 0/1).
8. The partition guard test still passes (no new edge — the door is inside exempt `loop`);
   the AC2 pins pass; the suite's inference walk covers the new module.
9. The door offers no retry knob, no scoring flag, no seed — its parser surface is exactly
   the render modes + evidence pointers + `--recorded-on` + `--out` + `--run-id` (for the
   record's identity), asserted against the runbook in aspect 5.

## Dependencies & sequencing

- Depends on: aspect 1 (the record reader), aspect 2 (the writer). Both are sequenced before
  this aspect.
- Third of the five aspects; aspect 4 (home/amendment) and aspect 5 (runbook) consume it.

## Open questions

- None — the refusal surface and the decision semantics are fixed by the PRD and its gate
  resolutions.