"""The baseline bake-off: the first code in Whetstone that consults a model, kept off the reward.

This package turns a `Task` into a candidate patch by asking a base model, so that P1's last
open exit criterion — *which* open base we start from — is settled by a measurement against the
working verifier rather than by a table of somebody else's benchmark scores. It produces
candidate patches. It never produces a verdict: what a patch earns is decided by
`whetstone.verify`, by re-executing the task's own tests in a sandbox, and nothing here
participates in that.

**It is deliberately OUTSIDE the reward path, and that is a structural claim, not a stylistic
one.** `mlx_lm` is imported by the MLX adapter in this package, legitimately — a bake-off with
no model in it would measure nothing. The identical import inside `whetstone.verify` would turn
the reward from deterministic re-execution into a model's opinion of itself, which is the
up-to-35%-false-positive LLM-as-judge this project exists to replace. The same library is
therefore correct here and fatal there, and the only thing keeping those two facts apart is
where the code lives. Hence the layout: a **sibling** of `verify/` and `tasks/`, never nested
under either, because `tests/test_no_inference_on_reward_path.py` walks its guarded roots with
`rglob` and a nested package would be inside the ban the moment it was created.

**The dependency runs ONE WAY.** `whetstone.bakeoff` imports `whetstone.verify` — for the `Task`
contract and, in later phases, to run the verifier over what a base produced. Nothing under
`verify/` or `tasks/` may import `whetstone.bakeoff`, in any direction or by any spelling,
including a function-local import. Reverse that edge and `mlx_lm` reaches the reward path
transitively while every guard in this repository stays green: the AST ban flags first-party
imports whose dotted name carries an inference-shaped component (`judge`, `model`, `llm`, …),
and neither `bakeoff` nor `generator` is one of those. That gap is closed by
`tests/bakeoff/test_generator_contract.py::test_no_module_on_the_reward_path_imports_the_bakeoff_package`,
which is the assertion this paragraph is worth.

The package's absence from the ban is itself a written, reviewable decision rather than an
oversight: it is listed in `EXEMPT` in `tests/test_reward_path_scope_is_partitioned.py`, which
fails the build both when a package under `src/whetstone/` is neither guarded nor exempted and
when an exemption names something that no longer exists.

**Nothing is re-exported here.** Callers import from the module that owns the thing —
`whetstone.bakeoff.generator` for the model seam. A convenience re-export in this file would
mean that importing the package at all executed every submodule under it, and the one submodule
that must stay importable without `mlx` installed is *this* one: CI runs the suite under a plain
`uv sync` with no `mlx` extra (`.github/workflows/ci.yml:32`), so a re-export of the MLX adapter
would make the whole test suite uncollectable there. The empty namespace is load-bearing.
"""
