"""Reading a whole directory of task manifests, one `load_task` at a time.

**Why this is not in `whetstone.verify.task`, and why that is not a loophole.** The provenance
boundary — a `Task` comes only from an operator-controlled file, never from policy output — is
enforced structurally: `test_no_task_is_ever_sourced_from_policy_output` censuses
`whetstone.verify.task` for public callables whose return annotation mentions `Task` and
asserts the set is exactly `{load_task}`. A `load_tasks(...) -> tuple[Task, ...]` in that module
would fail the census on a technicality (`"Task" in str(tuple[Task, ...])`), and the wrong fix
would be to loosen the census — the one assertion standing between a rollout and the golden
tests it is graded against.

So the directory loader is sited here, **outside** the census. What makes that acceptable is
that it is not a second loader: every `Task` below comes out of `load_task`, and there is no
other route to one in this module — no parsing, no dataclass construction, no defaults. It
composes the boundary rather than bypassing it. A future function here that built a `Task` any
other way would be exactly the hole the census exists to catch, and it would be invisible to
the census, so the rule is stated rather than assumed: **this module may call `load_task`, and
may not construct a `Task`.**

**Fail-closed twice over**, matching `load_task`'s own posture:

- **An empty directory raises.** Not "zero tasks, all of which passed" — a set with nothing in
  it that reduces to success is the vacuous-green lie, and it is the cheapest possible way to
  fake a perfect night. Note that `verdict.reduce` answers UNVERIFIED for an empty sequence,
  which is the right answer to "what did these checks conclude"; it is the wrong answer to
  "what did the operator point me at", and the caller never gets to ask the first question
  because this refuses first.
- **Nothing is skipped.** Every entry in the directory must load, including files with no
  `.json` suffix and including subdirectories. Filtering by suffix would be the friendlier
  behaviour and the dishonest one: a task quietly dropped from the run makes the set smaller
  than the operator believes it is, and every rate computed over it — the verified-gain number
  this project exists to publish — then has a denominator nobody chose. The cost is that a
  stray `.DS_Store` fails the invocation loudly, which is the direction to fail in.

Zero runtime dependencies, no model, no network: this is `iterdir` and a loop.
"""

from __future__ import annotations

from pathlib import Path

from whetstone.verify.task import Task, load_task


def load_tasks(path: Path) -> tuple[Task, ...]:
    """Load one manifest or a directory of them, always as a tuple.

    The two shapes are one call because a caller — the CLI, and later the loop — should not
    have to branch on what the operator pointed at. A single manifest is a corpus of one and
    reduces exactly like a corpus of many.
    """
    location = Path(path)
    if location.is_dir():
        return load_task_directory(location)
    return (load_task(location),)


def load_task_directory(directory: Path) -> tuple[Task, ...]:
    """Load every manifest in `directory`, in sorted order, or raise `ValueError`.

    Sorted so a run's order is a property of the corpus rather than of the filesystem's
    readdir; nothing in the reward depends on the order, but a report that lists tasks in a
    different sequence on every machine is one nobody can diff.

    Raises `ValueError` — never a partial result — if the directory holds no entries or if any
    entry is not a loadable manifest. `load_task`'s own message already names the offending
    file, so the caller can print the exception and be specific about which one it was.
    """
    location = Path(directory)
    entries = sorted(location.iterdir())
    if not entries:
        raise ValueError(
            f"task directory {str(location)!r} contains no task manifests; an empty set of "
            f"tasks is a malformed invocation, not a verdict"
        )

    tasks: list[Task] = []
    for entry in entries:
        if not entry.is_file():
            raise ValueError(
                f"task directory {str(location)!r} contains {entry.name!r}, which is not a task "
                f"manifest; nothing is skipped, because a skipped task is a missing denominator"
            )
        tasks.append(load_task(entry))
    return tuple(tasks)


__all__ = ["load_task_directory", "load_tasks"]
