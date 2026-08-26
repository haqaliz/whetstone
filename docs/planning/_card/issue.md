# Card — baseline-measurement

## Brief

P4 slice 1: the `PREREGISTRATION.md` § 3 baseline, built before the night trains anything
(`docs/ROADMAP.md` § 4 P4, § 5; the gate-runbook names the missing piece: a checkpoint the
night deliberately does not write). Build a baseline-checkpoint writer that materializes the
untrained open base (the 32B the night runbook resolves — record its identity as a pinned
input; do not claim § 7.3 closure) in the `checkpoints/<id>/` format with weights-style
hashing and `sft.verify_checkpoint` by identity, a measurement door that scores the single
checkpoint on `tasks/heldout/source-b.json` through the fail-closed loader by identity with
STRICT and WEAK both run so baseline `N` is measured, and a committed baseline artifact
(schema `whetstone-baseline/1`, locality discipline: counts, verdicts, provenance — never
task contents) whose loader refuses a second measurement by name — the measured-once guard,
watched failing first.

Acceptance criteria, written first (repo is test-first):

1. The door refuses a gitignored `--out` by name.
2. The checkpoint re-hash verifies (`verify_checkpoint` by identity).
3. A re-measurement is refused, naming the first artifact.
4. Both sources and both denominators + coverage appear.
5. Baseline `N` is the weak==PASS & strict==FAIL count over the held-out set.
6. The AC2 pins and the reward-path partition guard hold.
7. A runbook scripts the operator's GPU pass (the measurement is operator-executed, like
   every arm).

Caveats the dig must meet: the number itself is spent by the operator, exactly once, and
the artifact must state the § 7.3-open base identity without closing it. No baseline door,
checkpoint writer for the untrained base, or baseline artifact exists anywhere in
`src/whetstone/cli.py` or `src/whetstone/loop/` today — the gate compares two checkpoints
and the baseline is a single one, so the door is new. The reward path
(`src/whetstone/verify/`, `tasks/`, `patch.py`, `attribution.py`) must stay byte-untouched.

## Source

Inline brief (no GitHub issue — slug id, `feat baseline-measurement`), handed off from the
`whetstone-next` session (2026-08-26).
