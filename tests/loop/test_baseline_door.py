"""The § 3 baseline measurement's door — first the seam, then the measurement.

This file is the aspect's test surface (`docs/planning/baseline-measurement/measurement-door/`),
written first. Task A pins the one new machine seam — `baseline_engine` — in the gate's own
posture: the factory exists, is callable, is smoke-tested only (never invoked by a test —
`mlx` is an optional extra and every test injects a stub engine), and its module holds no
`mlx`/`mlx_lm` import at module scope, on the loop package's rule.

Later tasks (B to D) add the measurement core, the measured-once guard and the module door to
this same file.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from whetstone.loop import baseline

#: The guarded module under test, walked over its own bytes rather than this process's
#: `sys.modules` — the loop package's rule is about what executing the module loads.
MODULE = Path(__file__).resolve().parents[2] / "src" / "whetstone" / "loop" / "baseline.py"

#: The import roots that may appear only inside function bodies in `baseline.py`.
FORBIDDEN_IMPORT_ROOTS = frozenset({"mlx", "mlx_lm"})


def test_baseline_engine_is_a_smoke_tested_factory() -> None:
    """The seam exists, is callable, and is never invoked by this test.

    `mlx` is an optional extra and every test in this aspect injects a stub engine, so the
    factory's real body is exercised only by the operator's GPU pass. This smoke test pins
    that the seam exists and is a factory whose signature names the three inputs the
    composition point is fixed on — `weights`, `checkpoint`, `max_tokens` — and that its
    token default is `DEFAULT_MAX_TOKENS` **by identity**, imported, never re-declared.
    Calling it is deliberately not part of the test.
    """
    from whetstone.bakeoff.mlx_runtime import DEFAULT_MAX_TOKENS

    assert callable(baseline.baseline_engine)

    parameters = inspect.signature(baseline.baseline_engine).parameters
    assert "weights" in parameters, f"signature {parameters} names no weights"
    assert "checkpoint" in parameters, f"signature {parameters} names no checkpoint"
    assert "max_tokens" in parameters, f"signature {parameters} names no max_tokens"
    assert parameters["max_tokens"].default is DEFAULT_MAX_TOKENS, (
        "the baseline's token budget must be the bake-off's own constant by identity, "
        "never a second number written beside it"
    )


def test_baseline_module_imports_no_mlx_at_module_scope() -> None:
    """The loop package's own rule, walked over `baseline.py`'s bytes with `ast`.

    `baseline_engine` imports `mlx_lm` inside its body — the factory is the seam, and the
    seam is reached only when an operator's GPU pass invokes it. A module-scope
    `mlx`/`mlx_lm` import would execute on every `import whetstone.loop.baseline` and put
    an inference library on the loop's import graph unconditionally, so the walk forbids
    it: an import whose root is `mlx` or `mlx_lm` may appear only inside a function body.

    Anti-vacuity: the walk also demands that the module define `baseline_engine` at module
    scope, so an empty module fails this test rather than passing it by containing no
    imports at all.
    """
    tree = ast.parse(MODULE.read_bytes(), filename=str(MODULE))

    assert any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "baseline_engine"
        for node in tree.body
    ), "baseline.py defines no baseline_engine — this walk has nothing to guard"

    function_local: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(node):
                if isinstance(inner, (ast.Import, ast.ImportFrom)):
                    function_local.add(inner.lineno)

    at_module_scope = [
        f"line {node.lineno}: "
        + ", ".join(alias.name for alias in node.names)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and node.lineno not in function_local
        and any(alias.name.split(".")[0] in FORBIDDEN_IMPORT_ROOTS for alias in node.names)
    ]
    assert not at_module_scope, (
        "baseline.py imports an inference library at module scope: "
        + "; ".join(at_module_scope)
        + "\n\nWHY THIS IS A FAILURE: a module-scope import executes on every import of the"
        " module, so `import whetstone.loop.baseline` would load mlx even when no GPU pass"
        " ever asked for it. The loop package's rule is that every mlx import is"
        " function-local inside the factory, reached only when the operator invokes the"
        " seam"
    )