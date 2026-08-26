"""The § 3 baseline measurement's door: score the untrained base, exactly once.

Aspect 2 of `baseline-measurement` (`docs/planning/baseline-measurement/`). The one new
machine seam is `baseline_engine` — gate's `gate_engine` with exactly one difference, no
`adapter_path` — and everything else this door will compose is the gate's own, imported
**by identity**, never copied: `_CheckpointGenerator`, `_CompletionRecorder`, `_score_side`,
`_retry_side`, `RETRY_COUNT`, `report.tally`, exactly as `gate.py` composes the bake-off's.
A baseline draw and a gate eval are one experiment, because the greedy sampler is
`sampler_for(1)` **by identity** in both.

Every `mlx` import is function-local, on the loop package's own rule: this module imports,
type-checks and tests on a machine with no extra, and merely importing it loads no inference
library.
"""

from __future__ import annotations

from whetstone.bakeoff.generator import Generator
from whetstone.bakeoff.mlx_runtime import DEFAULT_MAX_TOKENS
from whetstone.bakeoff.weights import Weights
from whetstone.loop.gate import _CheckpointGenerator
from whetstone.loop.sampling import sampler_for
from whetstone.loop.sft import Checkpoint


def baseline_engine(
    weights: Weights, checkpoint: Checkpoint, max_tokens: int = DEFAULT_MAX_TOKENS
) -> Generator:
    """Load the untrained base `checkpoint` names and return a greedy `Generator`.

    The § 3 baseline's one machine seam — `gate_engine`'s sibling, differing in exactly
    one line. The checkpoint's provenance declares `untrained: true` (the aspect-1 writer),
    so there is no adapter to stack: the base is loaded from `weights.local_dir` (never a
    repo id) at the revision the checkpoint's own provenance names, and decoding is greedy —
    `sampler_for(1)` is `greedy_sampler` **by identity**, so a baseline draw and a gate
    eval are one experiment. The night's trained checkpoints never reach this seam: their
    provenance does not declare `untrained`, and the gate's own engine loads them with
    their adapter.

    Every `mlx` import is function-local, on the loop package's own rule. The factory is
    never *invoked* by the test suite — `mlx` is an optional extra, and every test injects a
    stub engine — so its behaviour is pinned by the smoke test and by the operator's runbook.
    """
    from mlx_lm.generate import generate
    from mlx_lm.utils import load as load_model

    # Indexed rather than unpacked, for the reason `gate_engine` records at its own call
    # site: `load` is typed as returning EITHER `(model, tokenizer)` OR `(model, tokenizer,
    # config)`, selected by a `return_config` argument that defaults to `False`. mypy cannot
    # narrow that union from a default, so `model, tokenizer = load(...)` is an error even
    # though the two-tuple is what arrives here; indexing is total over both arms.
    loaded = load_model(
        str(weights.local_dir),
        revision=weights.revision,
    )
    model, tokenizer = loaded[0], loaded[1]
    return _CheckpointGenerator(
        model,
        tokenizer,
        generate=generate,
        max_tokens=max_tokens,
        sampler=sampler_for(1),
    )


__all__ = [
    "baseline_engine",
]

