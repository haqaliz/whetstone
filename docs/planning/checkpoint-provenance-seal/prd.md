# PRD — checkpoint-provenance-seal

**Core-loop element:** ③ the never-regress promotion gate, at the trust its inputs carry. ① the
reward is untouched: nothing under `verify/` or `tasks/` changes, and the gate's rule and exits are
byte-identical.
**Roadmap:** M2 of `docs/ROADMAP.md` § 14 — "Make the gate able to answer"; follow-on of
`docs/planning/gate-leakage-guard/` (its STATUS "Open follow-ups" lists this first).
**Source:** `docs/planning/_card/issue.md` (the 2026-10-03 `whetstone-next` handoff, verbatim) +
`docs/planning/_card/understanding.md` + the interview decisions of 2026-10-03 (all four
recommended options confirmed).

---

## 1. Problem Statement

A trained checkpoint's `provenance.json` is hashed for its files and for nothing else.
`sft.verify_checkpoint` (`src/whetstone/loop/sft.py:801`) re-hashes the files the document names
and checks that `digest` reduces from them (`_digest_of`, `:926`). Every other field — `base`,
`dataset_digest`, `backend`, `run_seed`, `training_args`, `tool_versions`, `validation`,
`capacity_probe` — sits outside any seal.

That matters because two things read those fields as if they were facts:

- the gate records each side's `dataset_digest` and base into the promotion record
  (`gate.py:1656`), and `docs/planning/gate-leakage-guard/finding.md` § 5 names the candidate's
  night through it;
- the gate runbook asks the operator to compare that digest to the night's `dataset.json` by eye.

`gate.py:328` already states the limit: "Recorded, not verified." Nothing in the tree can say
whether the document was edited after the night wrote it, and the one place that would catch a
leaked candidate depends on the one field nothing protects.

Three further defects sit beside it, found in the dig:

- `check-leakage` has **no checkpoint input** (`cli.py:583-610`). The link from a checkpoint to a
  night exists only as a manual runbook step.
- `gate.py` and `card.py` **re-open `provenance.json`** after `verify_checkpoint` has checked it
  (`gate.py:1617`, `:1629`; `card.py:227-232`, which discards `verify_checkpoint`'s return value).
  A seal verified in one read and consumed from a second is a check-then-use gap.
- The promotion record's `training` block is **write-only**: nothing in `src/` reads it back.

**Evidence it is real:** `finding.md` § 5 ("RECORDED provenance, not verified"), STATUS open
follow-up, `gate.py:328`, and the three defects above, each located by file and line.

## 2. Goals & Success Metrics

The goals are properties asserted by tests, not figures. No number in this document was produced by
a run.

- **A v2 checkpoint is tamper-evident for every claim in its document.** Editing any claim, adding
  an unsealed key, deleting a claim, or downgrading the schema string makes
  `verify_checkpoint` raise `CheckpointUnverified`, and the message names the claim that moved.
- **A v1 checkpoint still verifies and is never reported as sealed.** Every consumer carries the
  distinction: `sealed` is `False` for v1 and `True` for v2, in the verified object, the promotion
  record and `check-leakage`'s output.
- **The consumers read what was verified.** `gate.py` and `card.py` take base, dataset digest and
  `sealed` from the `Checkpoint` that `verify_checkpoint` returned, not from a second read.
- **The link is mechanical.** `whetstone check-leakage --checkpoint <dir>` verifies the checkpoint
  and compares its `dataset_digest` to the run's `dataset.json` digest, instead of the operator
  doing so by eye.
- **Nothing else moves.** The gate's rule, its three exits, the retry discipline and the verifier
  are byte-identical; `check-leakage` without `--checkpoint` prints exactly what it printed.

## 3. What "sealed" means, and what it does not

The digest is an unkeyed hash. Anyone able to edit `provenance.json` can also recompute it, and
`verify_checkpoint` has had that property for the file hashes since it was written. A v2 seal
therefore does **not** authenticate the writer and does **not** prove `dataset_digest` equals the
digest of the dataset the trainer actually read.

What it does catch is the accident-shaped failures — a checkpoint re-fetched, truncated, hand-patched
or confused with another, or a document that no longer agrees with a digest cited elsewhere (a
report, a promotion record, the runbook). This is the argument `weights.verify` already makes for
files, extended to the document's claims.

The flag, the code, the output and the docs therefore say **sealed**, never "verified". The brief's
criteria 2 and 3 used "verified"; this PRD reads them as "sealed".

## 4. User Personas & Scenarios

The Whetstone ICP: the engineer who wants a model measurably better at their own tasks by morning,
privately, and who will not trust a gain they cannot check.

- **The operator gating a candidate.** Runs `check-leakage --run <run> --heldout <doc>
  --checkpoint <dir>` before `whetstone gate`, and reads one line saying whether the checkpoint's
  dataset link is sealed and matches the night. Today they compare two hex strings by eye.
- **The reader of a promotion record.** Sees, per side, whether the recorded dataset link was
  sealed. A v1 candidate reads "not sealed" and is still gateable; the record never implies more.
- **The future operator with a v1 checkpoint** (`checkpoints/portability-arm`, `48eae99b0d32`).
  Nothing about it breaks and nothing about it is upgraded in place.

## 5. Requirements

### Must-have

1. **Checkpoint schema `whetstone-checkpoint/2`.** `write_checkpoint` writes it. The document
   carries a `claims` map of `{top-level key: sha256 of that key's canonical JSON}` for every
   top-level key except `schema`, `digest` and `claims`. `digest` reduces from the sorted claim
   lines. The file hashes stay in the document under `files`, so they are sealed as a claim like any
   other, and `verify_checkpoint` still re-hashes every file on disk.
2. **Verification names what moved.** A claim whose recomputed hash differs from `claims` is named
   in the error. A top-level key with no entry in `claims`, and a `claims` entry with no key, are
   each refused and named. A digest that does not reduce from `claims` is refused.
3. **v1 stays verifiable, as v1.** `whetstone-checkpoint/1` verifies exactly as today and returns
   `sealed = False`. A v2 document whose schema string is rewritten to `/1` fails, because its
   digest no longer reduces from its file hashes alone.
4. **`Checkpoint` carries the verified claims consumers use** — `base_repo_id`, `base_revision`,
   `dataset_digest` (`None` for an untrained checkpoint) and `sealed` — read from the same bytes
   `verify_checkpoint` verified. Existing `Checkpoint(...)` constructors keep working.
5. **The untrained checkpoint is sealed too.** `write_baseline_checkpoint` writes v2, sealing
   `base`, `untrained`, `tool_versions` and `files`, because the gate compares bases.
6. **Torch and MLX write the same v2 shape.** Both already go through `write_checkpoint`; a test
   pins it so a future second writer cannot diverge.
7. **Promotion record `whetstone-promotion/3`.** Each side's `training` block gains `sealed: bool`.
   A `/2` record is refused with its own message, as `/1` is today. `TrainingProvenance` gains
   `sealed`, set from the verified `Checkpoint`.
8. **`gate.py` and `card.py` read the verified object**, not `provenance.json` a second time.
9. **`whetstone check-leakage --checkpoint <dir>`** (optional): verifies the checkpoint, then
   compares its `dataset_digest` to the run's `dataset.json` digest.
   - match, sealed — the output says so and the verdict is unchanged;
   - match, v1 — the output says "recorded, not sealed"; it proceeds, and the verdict is unchanged;
   - mismatch — exit 2, a refusal: the checkpoint was not trained on this run, so the comparison
     says nothing about it;
   - untrained checkpoint — exit 2: it has no dataset;
   - `CheckpointUnverified` — exit 2.
   Without `--checkpoint`, the command's output and exits are byte-identical to today's.
10. **The gate runbook and every sentence reading "recorded, not verified" are updated** to say what
    is now true, and the runbook guard that pins the phrase is tightened so a stale sheet fails.
    Also stale under v2 and corrected in the same commit: the three docstrings that call an
    untrained checkpoint's digest "the same constant for every untrained base"
    (`baseline.py:38-40`, `:169-171`; `gate.py:280`). A v2 untrained digest folds in `base`, so it
    does tell bases apart. Nothing depends on the constancy — `baseline.py` keys its series on base
    identity precisely because the old digest could not discriminate — but the claim stops being
    true for v2 and stays true for v1, and the docstrings must say both.
11. **Claims are hashed after a JSON round trip**, not as in-memory values. A tuple that becomes a
    list on write, or a value that does not survive `json.loads(json.dumps(v))` unchanged, would make
    a freshly written checkpoint fail its own verification. The writer hashes
    `json.loads(json.dumps(value))`, and a test writes a checkpoint carrying every value type the
    document holds (int, float, `None`, nested mapping, list) and verifies it.

### Should-have

12. A v1 checkpoint given to the gate prints the `not sealed` distinction in the gate's output, so it
    does not live only in the JSON record.

### Nice-to-have

13. A one-shot `whetstone` read-only command to show a checkpoint's seal state. Not required; the
    information is reachable through `check-leakage --checkpoint`.

## 6. Technical Considerations

- **Reward and gate.** The reward is untouched and stays execution-grounded. The gate's rule
  (`solved_new > solved_old`, `regressed == 0`, `unverified == 0`), its three exits and
  `UNVERIFIED` never counting as a win are byte-identical. `sealed` is recorded information and
  never enters the decision: an unsealed v1 candidate is gated exactly as before.
- **Cheat surface for the seal** (adversarial tests, each must fail under v2 and pass under the
  weaker file-only seal):
  1. change `dataset_digest` and leave `digest` alone;
  2. add a top-level key the claims do not list;
  3. delete a claim and its key together, leaving `digest` alone;
  4. swap two claims' values;
  5. rewrite the schema string to `/1` to dodge the claims;
  6. change `untrained` on an untrained checkpoint.
  Rewriting the claims **and** the digest together is not caught, by design — see § 3.
- **Fail closed on old readers.** `verify_checkpoint` requires schema equality, so an old reader
  refuses a v2 checkpoint rather than ignoring its claims.
- **Canonical JSON** for claim hashing: `sort_keys=True`, fixed separators, UTF-8, no ASCII escaping
  surprises. A test pins the bytes so a library change cannot move every digest silently.
- **CLI import rule.** `cli.py` stays free of module-scope imports into `loop`; `check_leakage.py`
  gains `CheckpointUnverified` in its `REFUSALS`, and the checkpoint read stays function-local to
  the `--checkpoint` path.
- **Single read.** `verify_checkpoint` parses the document once and returns the claims it verified.
- **Existing tests that change on purpose:** `tests/loop/test_baseline_checkpoint.py:179-193`
  (`TRAINED_KEYS` pins the key set byte-for-byte), `:147` (uses `/2` as its wrong-schema value, so
  it takes a new one), `tests/loop/test_gate_cli.py:258` (`_record_backend` edits `provenance.json`
  after sealing), the `/2`→`/3` record tests in `test_gate_provenance.py` and
  `test_promotion_record_n.py`, and `tests/test_gate_runbook_guards.py:523-541`.
- **Existing tests that must stay green unedited:** `tests/test_gate_leakage_finding.py` (reads only
  the `dataset_digest` key of the real v1 checkpoint and re-runs `check-leakage` without
  `--checkpoint`). *Corrected 2026-10-06: this said it skips in a worktree. It does not: it
  resolves the primary checkout through git's common dir, so it runs in a worktree and passed
  against the real night-001.*
- **Locality.** Everything is offline file reading and hashing. Nothing leaves the machine.
- **Release.** The unit lands the capability and its docs (STATUS, CHANGELOG `Unreleased`, ROADMAP
  M2 note). The version bump is a separate release commit, as `d43cd26` was.

## 7. Risks & Open Questions

- **No real v2 checkpoint will exist.** `checkpoints/portability-arm` (`48eae99b0d32`) is v1 and is
  never rewritten in place. Until a later night or arm writes a v2 checkpoint, this unit's v2
  behavior is proven against fixtures and the stub trainer only, as the gate's was. The docs say so
  and do not claim a real sealed link.
- **A seal can be mistaken for authentication.** § 3 is the mitigation: the word is `sealed`, and the
  limit is stated where the claim is made. A reviewer who reads "sealed" as "signed" is the risk.
- **Breaking changes.** `whetstone-promotion/3` refuses `/2` records, and a v2 checkpoint is refused
  by any older reader. Both are local, gitignored artefacts, and both are listed in the CHANGELOG as
  breaking.
- **Time-of-check/time-of-use is narrowed, not closed.** After this unit the consumers read the
  verified object; a file swapped between `verify_checkpoint` and a later tensor load is the
  existing `weights.verify` residual and is out of scope.
- **The other end of the link is not sealed either.** `check-leakage --checkpoint` compares the
  checkpoint's sealed `dataset_digest` to the digest in the run's `dataset.json`, a gitignored file
  the same operator can edit. The seal narrows the chain; it does not make it end-to-end tamper
  evident. The output states which side was sealed and which was only read. Sealing the run's own
  documents is a separate unit and is named in § 8.
- **Open:** whether the gate's own printed output should carry `not sealed` for v1 (should-have 12).
  Decided in the aspect plan, not here.

## 8. Out of Scope

- A signed or keyed seal, a trusted timestamp, or any authentication of the writer.
- Verifying `dataset_digest` against the dataset the trainer actually read.
- Re-sealing or rewriting any existing checkpoint, including `checkpoints/portability-arm`.
- Sealing a run's own documents (`dataset.json`, `ledger.json`); only the checkpoint's are sealed.
- Any change to the gate's rule, exits, retry discipline, or to anything under `verify/` or `tasks/`.
- Near-duplicate or content-level leakage detection (`check-leakage`'s residual stays as stated).
- Producing a clean candidate or running a gate; those are the operator's, and M2's exit criterion
  stays open.
- The version bump and tag.
