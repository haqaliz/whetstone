# Finding — the night-001 adapter is refused for leakage; no gate was run

**Unit:** `gate-leakage-guard` / `runbook-and-finding` · **Written:** 2026-10-03, after one
`whetstone check-leakage` run on this branch's code. **Instrument:** `whetstone check-leakage`
(`src/whetstone/loop/check_leakage.py`; offline, reads documents, runs nothing). **Local evidence
(the only home of every count below):** `runs/nights/night-001/` and `checkpoints/` (both
gitignored). **Guard:** `tests/test_gate_leakage_finding.py` re-runs the command and fails unless
section 2's block equals its output exactly — the same lines, in the same order, no more and no
fewer, after the one stated redaction.

## 1. What was run

```bash
uv run whetstone check-leakage \
  --run "$REPO/runs/nights/night-001" \
  --heldout "$REPO/tasks/heldout/source-b.json"
```

`$REPO` is the primary checkout, which holds the gitignored run. The command is this unit's
`check-leakage`, in the form the runbook now runs **before** `whetstone gate`:

- **Identity is the trailing 12-hex** of a task id (its sha12), compared per source, so a task
  renamed by a corpus re-mint is still recognised as the same task.
- **A run without a ledger is accepted**: the training set is read from `dataset.json` alone, and
  the output says so.
- **A comparison that compared nothing is a refusal, exit 2** (PRD Amendment 2), so exit 0 can
  only mean "examples were compared and none shared a task identity".

It was run against **night-001's training set** (`runs/nights/night-001/dataset.json`) and the
**committed held-out document** `tasks/heldout/source-b.json` — the split fixed by
`PREREGISTRATION.md` § 10.16.

## 2. What it printed

The block below is the command's standard output verbatim, with **exactly one redaction**: on the
`matched by identity: trained on ...` line, the pre-re-mint label in front of the sha12 is replaced
by `<pre-re-mint label>`. That label names another project and may not appear in a committed file;
the sha12 after it is unchanged. Nothing else is altered.

```text
leakage: LEAKED — 4 of 6 training examples touch a held-out task
held-out membership: 12 task(s)
source B (private): 4 of 6 training examples touch a held-out task; leaked task(s): donor-a-c6e4d4c4de87
source A (public): 0 training examples, not compared — the held-out membership is source B's
leaked task(s): donor-a-c6e4d4c4de87
matched by identity: trained on <pre-re-mint label>-c6e4d4c4de87, held out as donor-a-c6e4d4c4de87
A leak means one of two things, and the operator must find out which: (a) the night's partition seam failed to exclude held-out ids, or (b) the held-out document was derived or re-derived after the night ran (e.g. a corpus re-mint), so the night could not have excluded these ids. Either way the candidate trained on these tasks is not gated; do not exclude these examples after the fact
notice: ledger.json was absent from the run; the training set was read from dataset.json alone, and the run was not identified as complete by its ledger
```

**Exit code: 1.**

A second run, made independently while writing this finding, printed the same eight lines and
exited 1 again.

## 3. The conclusion

**The night-001 adapter is refused.** 4 of its 6 training examples sit on a task that is now a
held-out member (`donor-a-c6e4d4c4de87`). A candidate trained on a held-out task cannot be scored on
that task honestly, so it is not gated, and the four examples are not dropped after the fact to
make it gateable — the tool says so, and the runbook halts on its non-zero exit.

**No gate was run in this unit, and no gate decision exists.** Nothing in this finding is a gate
outcome. One earlier gate run does exist, on a sibling checkpoint, and is not a decision either
(section 5).

## 4. Why this is not a seam regression

The tool names both possible causes and leaves the choice to the operator: (a) the night's
partition seam failed to exclude held-out ids, or (b) the held-out document was derived after the
night ran.

**The most likely reading is (b) — and this is inference, not something the tool established.**
Night-001 ran 2026-09-05 → 09-07. The held-out split it is compared against was re-derived under
the scorable rule by `PREREGISTRATION.md` § 10.16 (2026-09-27), and the corpus re-mint renamed the
task ids, after the night. The night could not have excluded an id that was not yet held out, nor
an id it knew under its pre-re-mint label. Identity by sha12 is exactly what lets the tool see
through the rename: the line `matched by identity` pairs the pre-re-mint label and the held-out id
on the same sha12. Nothing here shows the seam failing on a split that existed when the night ran.

## 5. The provenance link

The checkpoint examined is the one in `checkpoints/portability-arm/`, whose provenance `digest`
begins `48eae99b0d32`; `reports/portability-arm/report.md` calls it the arm's **first**
checkpoint. Its `provenance.json` records
`dataset_digest` `3416702298c36a9a2ce8bada26295e54ddbd94f9666bff7b8088954ab6e4873b`, which **equals** the `digest`
in night-001's `dataset.json`. That is how the candidate's night is named: the adapter says it was
trained on night-001's dataset.

This is **RECORDED provenance, not verified**: `provenance.json` sits outside the checkpoint's
file-hash seal, so nothing proves the record was not edited after training. The checkpoint was
**read directly**, not through the gate. The base the record names, as recorded:

- `repo_id`: `Qwen/Qwen2.5-Coder-0.5B-Instruct`
- `revision`: `ea3f2471cf1b1f0db85067f1ef93848e38e88c25`

`checkpoints/night-001/` holds an adapter but no `provenance.json`, so it carries no recorded link to
any dataset and was not the adapter examined here.

**A sibling checkpoint was gated earlier, and was not examined here.** The same report records a
re-sealed checkpoint, digest `aebae11f5c4b`, trained from the same sealed dataset (digest
`3416702298c3`), and that it was gated as gate-001 (2026-09-26) against the untrained base and
reduced to `UNVERIFIED`: 0 of 12 solved on both sides, 2 unverified. That run scored the
held-out document as it stood **before** `PREREGISTRATION.md` § 10.16, so it is non-comparable
and not a decision. Its provenance was **not re-read here**; only the report's statement is
cited. That the leakage refusal applies to it follows from the report's statement that the
dataset is the same, not from a run of `check-leakage` on it.

## 6. Limits

- **sha12 identity cannot see near-duplicates.** A task that is near-identical to a held-out one
  (the same function, an adjacent commit) has a different sha12. A clean `check-leakage` would
  therefore mean only **no shared task identity**, never "no contamination". This run was not clean,
  so the limit bounds what a future clean run may claim, not this refusal.
- **Not reproducible without gitignored artefacts.** The finding depends on `runs/nights/night-001/`
  and `checkpoints/`, which are gitignored and live only in the primary checkout. Without them the
  guard test skips loudly and this finding cannot be re-checked.
- **No ledger.** `ledger.json` is absent from night-001's run, so the run was **not identified as
  complete by its ledger**; the training set was read from `dataset.json` alone, as the last printed
  line says. Why it is absent is **history from two documents, not something this run showed**:
  `CHANGELOG.md`'s 0.14.1 entry and `docs/STATUS.md`'s night #1 account ("The ledger was written
  last") record that a night then wrote its ledger after training, so the exception in night #1's
  training step took the ledger with it; 0.14.1 made a night write its ledger even when training
  raises.

## 7. The next unit

**A clean candidate — option B: an operator-run retrain on the examples that are not held out.**
Only 2 of the 6 examples are not on a held-out task. The 6-example adapter's own `provenance.json`
records `validation: no valid split (strict-PASS set below floor)`; 2 examples is fewer, so a
retrain on them would also be below the floor — **an inference, not a measurement**. A candidate
trained on them would be **weak evidence** at best; whether it is worth the run is the
**operator's decision**, not this unit's. Option C — gating the contaminated adapter anyway — is out
of scope and is not proposed.

**M2's exit criterion therefore stays open.** `docs/ROADMAP.md` § 14 M2's exit criterion is a gate
decision on a real pair, with `whetstone check-leakage` exiting 0, and no structural `UNVERIFIED`
remaining. The checkpoint examined is refused before the gate, and gate-001's `UNVERIFIED` was scored
against the pre-§ 10.16 document, so no gate decision exists.
