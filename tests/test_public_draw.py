"""The seeded draw: the same seed must produce the same file, byte for byte.

The draw decides **which** public instances the gates are spent on, and therefore which
instances a published number is computed over. If it moved between runs, nobody — including us
— could re-derive the corpus that number was measured on, and "reproducible" would be a word
rather than a property.

**Asserted as a byte comparison of the written file, never as an id-set match.** An id-set match
is the assertion that looks equivalent and is not: it stays green while the header drifts, and
the header is where the seed, the size and the denominator are recorded. Belay's
`tests/test_eval_mint_set.py:323-341` makes the same call for the same reason.

**Byte-identity is unconditional here, because the selection carries no clock.** The draw is a
pure function of the pool, the seed and the size; the fetch already timestamps the pool, and a
second timestamp on a derived file would buy nothing and cost exactly this property.

**With an anti-vacuity control.** A draw that ignored its seed entirely would satisfy every
determinism assertion below, so one test requires two seeds to disagree. Determinism without
that control is indistinguishable from a constant.

Pure and offline: these tests build `Instance` records directly and never read the network.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from whetstone.tasks.draw import ShortDraw, draw, read_selection, write_selection

#: The module under test, read as source for the `random.sample` guard below.
MODULE = Path(__file__).parent.parent / "src" / "whetstone" / "tasks" / "draw.py"

from whetstone.tasks.fetch import Instance  # noqa: E402 - grouped with the module under test


def _instance(instance_id: str, repo: str = "pallets/flask") -> Instance:
    """One pool record with only the fields the draw reads populated meaningfully."""
    return Instance(
        instance_id=instance_id,
        repo=repo,
        base_commit="0" * 40,
        environment_setup_commit="0" * 40,
        problem_statement="a statement",
        patch="diff --git a/x b/x\n",
        test_patch="diff --git a/tests/test_x.py b/tests/test_x.py\n",
        fail_to_pass=("tests/test_x.py::test_a",),
        pass_to_pass=(),
    )


def _pool(count: int = 12) -> tuple[Instance, ...]:
    """A pool spread evenly across three repositories, so stratification has something to do."""
    repos = ("pallets/flask", "sphinx-doc/sphinx", "psf/requests")
    return tuple(
        _instance(f"{repos[index % 3].replace('/', '__')}-{index}", repos[index % 3])
        for index in range(count)
    )


# --------------------------------------------------------------------------------------
# The property the corpus rests on
# --------------------------------------------------------------------------------------


def test_the_same_seed_writes_a_byte_identical_file(tmp_path: Path) -> None:
    """Byte-for-byte, not id-for-id. Header drift is exactly what an id match would miss."""
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    write_selection(first, draw(_pool(), size=6, seed=7), seed=7, pool_size=12)
    write_selection(second, draw(_pool(), size=6, seed=7), seed=7, pool_size=12)

    assert first.read_bytes() == second.read_bytes()


def test_the_draw_is_insensitive_to_the_order_the_pool_arrives_in(tmp_path: Path) -> None:
    """Sorted before anything shuffles, so the draw depends on the seed and nothing else.

    A shuffle seeded off an unsorted sequence is only as reproducible as that sequence, and the
    pool's order is a fact about how the dataset server paginated on the morning it was fetched.
    """
    forwards = tmp_path / "forwards.json"
    backwards = tmp_path / "backwards.json"

    write_selection(forwards, draw(_pool(), size=6, seed=7), seed=7, pool_size=12)
    write_selection(
        backwards, draw(tuple(reversed(_pool())), size=6, seed=7), seed=7, pool_size=12
    )

    assert forwards.read_bytes() == backwards.read_bytes()


def test_a_different_seed_draws_a_different_set() -> None:
    """Anti-vacuity: a draw that ignored its seed would pass every test above.

    If this ever fails because two seeds genuinely collide on a small pool, widen the pool
    rather than deleting the control — determinism nobody can distinguish from a constant is
    not the property being claimed.
    """
    one = [instance.instance_id for instance in draw(_pool(30), size=6, seed=1)]
    two = [instance.instance_id for instance in draw(_pool(30), size=6, seed=2)]

    assert one != two


# --------------------------------------------------------------------------------------
# A short draw is a short denominator, and is refused
# --------------------------------------------------------------------------------------


def test_a_pool_smaller_than_the_requested_size_raises() -> None:
    """Returning what there was would silently move the denominator of every later rate.

    The caller asked for a corpus of N. Handing back N-3 and letting the run continue makes
    "the corpus" mean whatever the pool happened to hold, which is the one thing a
    pre-registered number may not depend on.
    """
    with pytest.raises(ShortDraw, match="4"):
        draw(_pool(4), size=10, seed=7)


def test_a_size_of_zero_is_refused() -> None:
    """An empty selection is a malformed invocation, not a corpus — as with `load_tasks`."""
    with pytest.raises(ShortDraw):
        draw(_pool(), size=0, seed=7)


# --------------------------------------------------------------------------------------
# Stratification, so the corpus is not one repository wearing a crowd
# --------------------------------------------------------------------------------------


def test_the_draw_spreads_across_repositories_before_it_doubles_up_on_one() -> None:
    """Three repositories and a draw of three takes one from each.

    An unstratified draw over a pool that is 60% sphinx returns a corpus that is 60% sphinx, and
    a number measured on it says something about sphinx rather than about the model.
    """
    selected = draw(_pool(30), size=3, seed=7)

    assert len({instance.repo for instance in selected}) == 3


def test_stratification_still_fills_the_size_when_one_repository_runs_out() -> None:
    """Round-robin, not one-per-repo: a size larger than the repo count is still filled."""
    selected = draw(_pool(30), size=10, seed=7)

    assert len(selected) == 10
    assert len({instance.instance_id for instance in selected}) == 10


# --------------------------------------------------------------------------------------
# The written file, and what it has to say about itself
# --------------------------------------------------------------------------------------


def test_the_selection_records_the_seed_and_the_denominator_it_drew_from(
    tmp_path: Path,
) -> None:
    """A selection whose seed is not recorded cannot be re-derived by anyone but its author."""
    path = tmp_path / "selected.json"
    write_selection(path, draw(_pool(), size=6, seed=7), seed=7, pool_size=12)

    document = path.read_text()

    assert '"seed": 7' in document
    assert '"pool_size": 12' in document
    assert '"size": 6' in document


def test_a_written_selection_reads_back_as_the_instance_ids_it_drew(tmp_path: Path) -> None:
    path = tmp_path / "selected.json"
    selected = draw(_pool(), size=6, seed=7)
    write_selection(path, selected, seed=7, pool_size=12)

    assert read_selection(path) == tuple(instance.instance_id for instance in selected)


def test_a_selection_that_is_not_a_selection_raises_naming_the_file(tmp_path: Path) -> None:
    path = tmp_path / "selected.json"
    path.write_text('{"schema": "something-else"}')

    with pytest.raises(ValueError, match=r"selected\.json"):
        read_selection(path)


# --------------------------------------------------------------------------------------
# The one algorithm choice worth pinning in a test
# --------------------------------------------------------------------------------------


def test_the_draw_does_not_use_random_sample() -> None:
    """`shuffle`-and-take, never `random.sample`, and the reason is cross-version stability.

    `sample`'s internals have changed across CPython releases — it switches between a selection
    set and a partial shuffle on the ratio of `k` to the population, and it stopped accepting
    sets outright in 3.11. Which branch it takes for a given `k` is not part of its contract, so
    a corpus drawn with it is reproducible only on the interpreter that drew it. `shuffle` is a
    single documented Fisher-Yates pass, and take-the-first-N off it removes that unknown.

    Asserted against the source rather than the behaviour, because the behaviour is identical
    right up until the interpreter that makes it not.
    """
    tree = ast.parse(MODULE.read_bytes(), filename=str(MODULE))

    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "sample"
    ]

    assert not calls, (
        "draw.py calls .sample(); use shuffle-and-take instead, so the corpus a seed produces "
        "does not depend on which CPython drew it"
    )


def test_the_guard_above_would_see_a_sample_call(tmp_path: Path) -> None:
    """Anti-vacuity: the walk is shown catching a planted `.sample(...)`."""
    planted = tmp_path / "planted.py"
    planted.write_text("import random\n\n\ndef d(p):\n    return random.Random(1).sample(p, 2)\n")
    tree = ast.parse(planted.read_bytes(), filename=str(planted))

    assert [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "sample"
    ]
