"""The nightly improvement loop: the first code in Whetstone that produces *training data*.

The bake-off measures a base. This package is the other half of the project's name — it samples
`K` attempts per task, keeps only the rollouts the STRICT verifier passed, and trains a LoRA
adapter on those. Every training example is verified by construction, which is the whole claim:
the reward is deterministic re-execution, so a rollout cannot talk its way into the dataset.

**It composes; it does not re-decide anything.** The frozen contract and its seal, the control
arm, the weights re-hash, the journal, the transcript, the retry wrapper and — critically — the
single definition of *solved* (`whetstone.bakeoff.report.tally`'s `Outcome.SOLVED`) are all
imported from `whetstone.bakeoff` **by identity**. A second notion of "this rollout was good
enough to train on" is exactly how a verified loop stops being verified, so there is not one.

**It is EXEMPT from the inference ban, for the `bakeoff` reason and no other.** `mlx_lm` is
imported here legitimately — a loop that samples nothing and trains nothing would improve
nothing — and the identical import inside `whetstone.verify` would turn the reward into a
model's opinion of itself. The two facts are kept apart by where the code lives, which is why
this package is a **sibling** of `verify/` and `tasks/` and never nested under either: the AST
ban walks its guarded roots with `rglob`.

**The dependency runs ONE WAY, with exactly two documented edges in the other direction.**
`whetstone.loop` imports `whetstone.bakeoff` and `whetstone.verify`; nothing under `verify/` or
`tasks/` may import this package by any spelling. The two exceptions are both `whetstone.cli`,
a guarded root which owns the two doors that reach this package: the `run --night` door the
roadmap names (`docs/ROADMAP.md:399-400`) and the `gate` door the p3-promotion-gate unit names.
Each holds one **function-local** import — `whetstone.loop.night` in the night handler,
`whetstone.loop.gate` in the gate handler — so `whetstone verify` — the reward's own entry
point — never executes either and never imports `mlx_lm`. Those edges are not holes with
comments on them: they are asserted to be the only ones, and asserted to be function-local, by
`tests/test_reward_path_scope_is_partitioned.py`, and a third such import or a module-scope one
fails the build.

**Nothing is re-exported here.** Callers import from the module that owns the thing. A
convenience re-export would make importing the package execute every submodule under it,
including the one that reaches `mlx_lm`, and CI runs the suite under a plain `uv sync` with no
`mlx` extra (`.github/workflows/ci.yml`). The empty namespace is load-bearing, exactly as it is
for `whetstone.bakeoff`.
"""
