# Spec — finding guard and write-up (M4, M5)

**Aspect:** `finding-guard` · **Unit:** `k16-night` · **PRD:** `../prd.md` M4/M5 · **Date:** 2026-10-18

## Purpose

The night's finding is a quotation of its ledger. A quotation is only honest while it still
equals what the ledger says, so the finding carries a small machine-readable evidence block and a
skip-loudly guard checks it against the real run. The guard is modelled on
`tests/test_gate_leakage_finding.py`: unconditional shape checks, live equality checks when the
primary's gitignored artefacts exist, and a loud skip naming the missing artefact otherwise.

## Finding contract

`docs/planning/k16-night/finding.md` carries the seven sections of the repo's finding precedent
and a fenced `json` evidence block:

```json
{
  "run": "runs/nights/<night-run-id>",
  "probe": "runs/night-probe/<probe-run-id>",
  "draws": 16,
  "heldout_document_digest": "<64 hex>",
  "denominator": 52,
  "selected": 0,
  "unverified": 0,
  "coverage": "0/52",
  "checkpoint": null
}
```

`checkpoint` is the checkpoint's digest string when a candidate was written, else `null`.

## Guard behaviour

`tests/test_k16_night_finding.py`:

- **Unconditionally (the template):** `finding-template.md` exists and carries the seven section
  headings and a parsable JSON block with exactly the keys above. The **real** finding cannot
  exist before the night, so its shape checks run when it is present and otherwise skip loudly.
- **When the primary's `runs/` holds the declared run:** read the ledger through
  `ledger.verify_document` (v3 sealed; a v2 reads unsealed) and assert every ledger-backed block
  value equals the ledger's: `draws`, `task_set.heldout.document_digest`, `dataset.denominator`,
  `dataset.examples`, `dataset.unverified`, `dataset.coverage`, `checkpoint.digest`. Assert the
  held-out digest equals `heldout.document_digest_of(tasks/heldout/source-b.json)`. The `probe`
  value is checked against the finding's own `**Probe:**` line, not the ledger: the ledger carries
  `task_set.probe` as an integer sample size, never a run path.
- **When `checkpoint` is a digest:** `sft.verify_checkpoint(primary/checkpoints/<run-id>)` and
  assert its digest equals the block's.
- **When the primary's run or the finding is absent:** skip loudly, naming the artefact.
- A mismatch raises a named `FindingDisagrees`; the helper is pure so a fixture finding/payload
  can prove the failure offline.

The primary is found from git (`git rev-parse --path-format=absolute --git-common-dir`), never a
literal path — the same helper shape as `tests/test_gate_leakage_finding.py:60-80`.

## Write-up (M5)

The code PR (before the night) adds a `docs/STATUS.md` entry and a `CHANGELOG.md` `Unreleased`
entry in the same commit as the guards. Both say: the guards shipped; **the night is unrun**; no
number is claimed; the finding is a follow-up. `tests/test_docs.py` gains a write-up guard in the
shape of `test_the_write_up_records_the_night_remine` (`:1234-1250`).

The finding commit (after the operator run) updates both with the night's outcome and its
evidence block. It does not rewrite the earlier entry.

## Non-goals

- No finding writer in `src/`; the finding is authored prose plus one checked block.
- No `reports/` artifact; the one-home guard's 21 committed files do not move.
- No number is claimed before the run.
