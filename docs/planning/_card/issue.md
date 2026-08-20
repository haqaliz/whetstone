# Card — p2-rollouts

## Brief

Build P2 slice 1 — the nightly rollout loop (rollouts + expert iteration): `whetstone run --night`
samples k attempts per task on the declared source-B set via the hardened generation contract (32B
is the candidate with evidence, named by the larger-base finding), keeps only rollouts carrying a
recorded STRICT-PASS verdict, LoRA-SFTs the 32B on those via mlx-lm, and writes `runs/<id>/` with a
full ledger and `checkpoints/<id>/`.

Acceptance criteria, written first (repo is test-first):

1. A test asserts EVERY training-set example carries a recorded strict-PASS verdict — UNVERIFIED/FAIL
   rollouts are never training data.
2. A determinism test — same seed, byte-identical training set.
3. The ledger records pinned seeds, model revision, task set, tool versions.
4. The run honors the existing contract-seal / transcript / weights-pinning machinery rather than
   bypassing it.

Caveats the dig must meet: the 32B's material unverified rate (~6 tok/s vs the 900 s verification
timeout) is a timing property to be disclosed, and LoRA training memory on the 36 GiB machine is
UNMEASURED — include a D7-style capacity probe before the first full night; low strict-PASS yield is
answered by raising k, never by weakening the check. The reward path (`src/whetstone/verify/`,
`tasks/`, `patch.py`, `attribution.py`) must stay byte-untouched.

## Source

Inline brief (no GitHub issue — slug id, `feat p2-rollouts`), handed off from the `whetstone-next`
session (2026-08-19).
