"""The re-mine is off the reward path, and the one new loop module consults no model.

The failure this prevents: a re-mine that reaches into ``whetstone.verify/`` — or a new
``whetstone.loop.remine`` that imports an inference client — turns the deterministic reward
into a judge's guess while every other test in the suite stays green. This is exactly the
argument ``tests/test_no_inference_on_reward_path.py:1-14`` makes for the reward path, pinned
over the re-mine seam.

Two source-reading assertions, neither importing a guarded module:

* no module under ``src/whetstone/verify/`` imports ``whetstone.loop`` — the reverse of the
  documented one-way edge (``src/whetstone/loop/__init__.py``); a verifier that reached the
  loop would put ``mlx_lm`` on the reward path by a route the AST guard does not name, since
  neither ``loop`` nor ``night`` is an inference-shaped component.
* ``src/whetstone/loop/remine.py`` imports no name the AST guard calls an inference client, so
  the ``loop`` exemption's reason ("imports ``mlx_lm`` legitimately") is not silently false
  for the one module in that package that needs no model.

The guard's own ``_imported_names``/``_is_inference_import`` are reused **by import**, never
copied: a copy could drift away from the ban it is supposed to be a part of, and the drift
would be invisible while both files stayed green (the
``tests/test_reward_path_scope_is_partitioned.py:59`` precedent).
"""

from __future__ import annotations

from test_no_inference_on_reward_path import (
    GUARDED_ROOTS,
    SRC,
    _imported_names,
    _is_inference_import,
    _modules,
)


def test_no_verify_module_imports_the_loop() -> None:
    """The one-way edge, enforced: ``whetstone.verify`` never reaches ``whetstone.loop``.

    ``loop`` is exempt from the inference ban because it imports ``mlx_lm`` legitimately (it
    samples from a base model), and the exemption is sound only while nothing guarded can
    reach it. The AST ban would not notice this edge being reversed — neither ``loop`` nor
    ``night`` is an inference-shaped name — so it is asserted here, over the source, by the
    same dotted-prefix rule the partition guard uses for the bake-off.
    """
    verify_root = SRC / "whetstone" / "verify"
    modules = sorted(verify_root.rglob("*.py"))
    assert modules, (
        f"no module found under {verify_root} — the walk is asserting over an empty set, so "
        "the assertion below would hold no matter what the reward path imported"
    )

    seen = {dotted for path in modules for dotted, _lineno in _imported_names(path, SRC)}
    assert seen, (
        "the walk observed no imports at all under verify/. A walk that parsed nothing would "
        "satisfy the ban below vacuously — the strongest possible result from the weakest "
        "possible run (`CONTRIBUTING.md:53-60`)"
    )

    offenders = sorted(name for name in seen if name.split(".")[:2] == ["whetstone", "loop"])
    assert not offenders, (
        "the reward path imports the loop package: "
        + ", ".join(offenders)
        + "\n\nWHY THIS IS A FAILURE: loop/ is exempt from the inference ban only because the "
        "dependency runs one way and the loop reaches the verifier, never the reverse. An "
        "import in the other direction puts mlx_lm on the reward path transitively while every "
        "other guard stays green, because the AST ban keys on inference-SHAPED names and "
        "'loop' is not one. Move the shared code, or invert the dependency; do not add the loop "
        "to GUARDED_ROOTS, which would fail the ban honestly and put the pressure on the ban."
    )


def test_the_remine_module_imports_no_inference_client() -> None:
    """The ``loop`` exemption's reason, made executable for the one module that needs no model.

    ``remine`` reads a donor's local git history and writes manifests; it consults no model.
    If it imported one, the exemption's stated reason would be false for it, and the whole
    ``loop`` package would be one step closer to being exempt for a reason nobody can defend.
    """
    remine = SRC / "whetstone" / "loop" / "remine.py"
    assert remine.is_file(), (
        f"{remine} does not exist, so this test would pass without checking anything. The "
        "re-mine module is the remine aspect's; if it moved, point this guard at it rather "
        "than deleting the assertion"
    )

    names = _imported_names(remine, SRC)
    assert names, (
        f"{remine} imports nothing at all, so the ban below asserts over an empty set. A module "
        "with no imports is not a module; the file is misread or empty"
    )

    offenders = sorted(
        f"line {lineno}: {dotted!r}" for dotted, lineno in names if _is_inference_import(dotted)
    )
    assert not offenders, (
        "whetstone.loop.remine imports an inference client:\n  "
        + "\n  ".join(offenders)
        + "\n\nWHY THIS IS A FAILURE: the re-mine reads a donor's local history and writes "
        "manifests; it needs no model. An inference import here makes the loop exemption's "
        "reason ('imports mlx_lm legitimately') false for a module that does not, and the fix "
        "belongs in the remine aspect under its own spec — not by widening GUARDED_ROOTS or "
        "adding this module to EXEMPT."
    )


def test_the_reward_path_guard_still_covers_its_roots() -> None:
    """A pin, green on arrival: the miner's home is inside the AST guard by construction.

    ``src/whetstone/tasks/`` is one of the guard's roots, so the re-mine path is covered without
    this aspect touching the guard at all. This asserts the walk still sees the tasks root
    contributing modules — a moved or emptied root would otherwise leave the re-mine path
    unwatched while this file stayed green.
    """
    modules = _modules()
    assert modules, "the reward-path guard walks no modules at all"

    tasks_root = SRC / "whetstone" / "tasks"
    assert any(path.is_relative_to(tasks_root) for path in modules), (
        f"the guard's walk contributes no module under {tasks_root}. The miner lives there, so "
        "the re-mine path would be outside the guard while every assertion still passed"
    )
    assert GUARDED_ROOTS, "the guard names no roots"
