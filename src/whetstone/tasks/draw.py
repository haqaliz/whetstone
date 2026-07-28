"""Which public instances the gates are spent on: a seeded, stratified, offline draw.

The draw decides what a published number is measured over, so it has one job beyond picking:
**the same seed must produce the same corpus on any machine, on any day**. Everything below is
in service of that, and each piece closes a specific way it could quietly stop being true.

- **Sorted before anything shuffles.** The pool arrives in whatever order the dataset server
  paginated it on the morning it was fetched. A shuffle seeded off an unsorted sequence is only
  as reproducible as that sequence.
- **`shuffle`-and-take, never `random.sample`.** `sample` switches internally between a selection
  set and a partial shuffle depending on the ratio of `k` to the population, and which branch it
  takes is not part of its contract — it has changed across CPython releases. `shuffle` is one
  documented pass. `tests/test_public_draw.py` asserts the absence of `.sample(` in this file,
  because the two behave identically right up until the interpreter on which they do not.
- **No clock in the written file.** The selection is a pure function of the pool, the seed and
  the size; the pool already carries `fetched_at`, and a second timestamp on a derived file would
  buy nothing and would cost byte-identity — the property the whole module exists for.
- **A short draw raises.** Handing back fewer than asked would let "the corpus" mean whatever the
  pool happened to hold, and every later rate would have a denominator nobody chose. That is the
  same refusal `load_task_directory` makes for an empty directory, one step earlier.

**Stratified by repository, and that is not cosmetic.** SWE-bench-Lite is dominated by a handful
of projects; an unstratified draw over a pool that is 60% sphinx returns a corpus that is 60%
sphinx, and a number measured on it is a statement about sphinx. The draw therefore goes
round-robin over the repositories in sorted order, taking from each one's shuffled list, and only
doubles up on a repository once the others are exhausted.

Pure: stdlib `json` and `random`, no clock, no network, no model.
"""

from __future__ import annotations

import json
import random
from collections.abc import Sequence
from pathlib import Path

from whetstone.tasks.fetch import Instance

#: Names the shape of the committed file, as with the pool and the ledger.
SELECTION_SCHEMA = "whetstone-source-a-selection/1"

#: The rule, recorded in the written file so a reader can re-derive the draw without reading
#: this module. A procedure described only in prose is one nobody can reproduce.
DRAW_RULE = (
    "sort the pool by instance_id; group by repo; shuffle each group with random.Random(seed) "
    "in sorted repo order; take round-robin across the groups until size is reached. "
    "shuffle-and-take rather than random.sample, whose internal branch is not part of its "
    "contract and has changed across CPython releases"
)


class ShortDraw(ValueError):
    """The pool cannot supply the requested size, or the size is not a corpus.

    Raised rather than returning what there was. A draw that silently came up short would move
    the denominator of every rate computed over the corpus, and would do it invisibly — the file
    would look exactly like a full draw of a smaller pool.
    """


def draw(pool: Sequence[Instance], *, size: int, seed: int) -> tuple[Instance, ...]:
    """Draw `size` instances out of `pool`, deterministically under `seed`.

    Deterministic in the strong sense: the result depends on the pool's *contents*, the seed and
    the size, and on nothing else — not on the order the pool arrived in, not on the interpreter,
    not on the day. `tests/test_public_draw.py` asserts each of those separately, and asserts
    that two different seeds disagree, so determinism cannot be satisfied by a constant.

    Raises `ShortDraw` if `size` is below one or exceeds what the pool holds.
    """
    if size < 1:
        raise ShortDraw(
            f"a draw of {size} is not a corpus; an empty selection is a malformed invocation "
            f"rather than a set of tasks that all happened to pass"
        )
    if size > len(pool):
        raise ShortDraw(
            f"the pool holds {len(pool)} instance(s) and {size} were asked for. Returning the "
            f"{len(pool)} there are would silently move the denominator of every rate computed "
            f"over this corpus, so the draw is refused instead"
        )

    ordered = sorted(pool, key=lambda instance: instance.instance_id)
    groups: dict[str, list[Instance]] = {}
    for instance in ordered:
        groups.setdefault(instance.repo, []).append(instance)

    rng = random.Random(seed)
    for repo in sorted(groups):
        rng.shuffle(groups[repo])

    selected: list[Instance] = []
    queues = [groups[repo] for repo in sorted(groups)]
    index = 0
    while len(selected) < size:
        queue = queues[index % len(queues)]
        if queue:
            selected.append(queue.pop(0))
        index += 1
    return tuple(selected)


def write_selection(
    path: Path, selected: Sequence[Instance], *, seed: int, pool_size: int
) -> None:
    """Write the draw, with everything needed to re-derive it and nothing that would move.

    `pool_size` is recorded because the draw is only meaningful against the denominator it came
    out of: the same seed over a re-fetched, larger pool is a different corpus, and a reader
    comparing two selections needs to be able to see that rather than infer it.
    """
    document = {
        "schema": SELECTION_SCHEMA,
        "seed": seed,
        "size": len(selected),
        "pool_size": pool_size,
        "rule": DRAW_RULE,
        "instances": [instance.instance_id for instance in selected],
    }
    location = Path(path)
    location.parent.mkdir(parents=True, exist_ok=True)
    location.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")


def read_selection(path: Path) -> tuple[str, ...]:
    """The drawn instance ids, in draw order, or `ValueError` naming the file.

    Order is preserved rather than sorted: it is the order the gates will be spent in, and a
    run that stopped early stopped at a reproducible place.
    """
    location = Path(path)
    try:
        raw = json.loads(location.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"selection {str(location)!r} could not be read: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema") != SELECTION_SCHEMA:
        raise ValueError(
            f"selection {str(location)!r} is not a source-A selection: expected an object whose "
            f"schema is {SELECTION_SCHEMA!r}"
        )
    instances = raw.get("instances")
    if not isinstance(instances, list) or not all(isinstance(item, str) for item in instances):
        raise ValueError(f"selection {str(location)!r} carries no list of instance ids")
    return tuple(instances)


__all__ = [
    "DRAW_RULE",
    "SELECTION_SCHEMA",
    "ShortDraw",
    "draw",
    "read_selection",
    "write_selection",
]
