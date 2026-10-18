# Finding — the K = 16 night

**Run:** `TO-BE-FILLED` · **Probe:** `TO-BE-FILLED` · **Written:** TO-BE-FILLED, from the run's
ledger, not from memory. **Local evidence (the only home of every count):**
`runs/nights/<night-run-id>/` (gitignored). **Committed held-out document:**
`tasks/heldout/source-b.json`.

> **How to use this template.** Copy it to `finding.md` after the night, fill every
> `TO-BE-FILLED` from the ledger's own fields, and run
> `uv run pytest tests/test_k16_night_finding.py -q`. The evidence block is checked against the
> ledger (`draws == sampling.K`, the held-out digest, the denominator, the selected and unverified
> counts, the coverage and the checkpoint digest); a block still carrying a `TO-BE-FILLED` value is
> skipped loudly by the live guard, never read as a pass. A number here that the ledger does not
> carry fails the guard.

```json
{
  "run": "TO-BE-FILLED",
  "probe": "TO-BE-FILLED",
  "draws": "TO-BE-FILLED",
  "heldout_document_digest": "TO-BE-FILLED",
  "denominator": "TO-BE-FILLED",
  "selected": "TO-BE-FILLED",
  "unverified": "TO-BE-FILLED",
  "coverage": "TO-BE-FILLED",
  "checkpoint": "TO-BE-FILLED"
}
```

## 1. What was run

TO-BE-FILLED. Name the night run id, the probe run id, the run seed, the recorded-on date, the
base and its revision, `K = 16`, and the declared denominator (51 private + 1 public = 52 tasks).

## 2. The decision

TO-BE-FILLED. State the outcome plainly: either M1's exit criterion was met — the night selected
at least one strict-`PASS` and wrote both a ledger and a checkpoint — or the night selected
nothing and this finding **accepts the zero**. Either way, name the gate's result verbatim
(`promoted` / `rejected` / `UNVERIFIED`) only if a gate actually ran; a `checkpoint: null` finding
must name no gate verdict.

## 3. The counts

TO-BE-FILLED. Quote the ledger's own fields: the draw budget, the per-draw `(denominator,
unverified, solved)` tallies, the selected example count, the dataset's denominator, unverified
and coverage, the control arm's status on every draw, and the checkpoint digest or the ledger's
`checkpoint.absent` reason.

## 4. The held-out confound

TO-BE-FILLED. State that `donor-a-c6e4d4c4de87` — night #1's clustered, 4-of-8 task — is a
**held-out member** and was therefore excluded from training. A zero is not clean evidence about
the budget alone; the finding must not claim `K = 16` was the only variable. The held-out split
did not move.

## 5. The control arm

TO-BE-FILLED. State the control arm's status on every recorded draw (`PASS` on every draw is the
probe's go condition) and, when a checkpoint exists, the `check-leakage` exit and the gate's exit.

## 6. What is not claimed

TO-BE-FILLED. State that the 12 `NO_ORACLE` tasks were **drawn** and remain in the training pool;
they cannot yield an example under the sealed budget, and no scorable-pool filter was added. Claim
no delta, no yield, and no number the ledger does not carry.

## 7. The next unit

TO-BE-FILLED. Name what follows from this outcome — a gate/leakage/`card`/`fuse` step if a
checkpoint exists, or the next pre-committed response if the zero is accepted. Do not propose a
looser verifier, a moved split, or a fourth edit representation here.
