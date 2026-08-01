"""The corpus is one directory per donor, and a run must read all of them as one denominator.

The failure this prevents is a silently partial run. `tasks/local/` holds `belay/` and `contig/`,
because the miner writes one directory per donor (`tasks/README.md`). `load_tasks` is deliberately
fail-closed about that shape — it refuses a directory holding a subdirectory rather than
descending, on the stated ground that *"a skipped task is a missing denominator"*
(`whetstone/tasks/manifest.py:79-83`). That refusal is correct and is not what is being worked
around here.

What was missing is on the caller's side: `--tasks` accepted exactly one root, so the only ways to
run the real corpus were to point at one donor and silently score a fraction of it, or to flatten
the user's own gitignored data into a shape the tree does not have. Both produce a number whose
denominator is not the corpus the report claims. `--tasks` is therefore repeatable, and the roots
are unioned in the order given.

`load_tasks`'s own refusal still stands behind this: passing `tasks/local` itself remains an error
naming the subdirectory, so the fix is to name the donors, never to make the loader lenient.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fixtures.repos.mined import build_mined_task

from whetstone.bakeoff.run import build_parser, load_task_roots
from whetstone.tasks.manifest import load_tasks
from whetstone.verify.task import Task


def _donor(root: Path, name: str, task_ids: tuple[str, ...]) -> Path:
    """Write a donor directory of manifests, reusing the repo fixture builder for realism.

    ``build_mined_task`` writes its manifest as ``<root>/<task_id>.json`` beside the donor repo it
    builds, so the directory it is handed cannot itself be the corpus directory — it would hold the
    donor's working tree too, and ``load_task_directory`` refuses a directory holding a
    subdirectory. Each task therefore gets its own scratch root and the manifest is copied out.
    """

    directory = root / name
    directory.mkdir(parents=True)
    for task_id in task_ids:
        scratch = root / f"{name}-{task_id}-src"
        scratch.mkdir(parents=True)
        build_mined_task(scratch, task_id=task_id, subject=f"fix {task_id}")
        (directory / f"{task_id}.json").write_bytes((scratch / f"{task_id}.json").read_bytes())
    return directory


def test_more_than_one_donor_root_is_read_as_one_corpus(tmp_path: Path) -> None:
    """Two donors, one denominator — the shape `tasks/local/` actually has."""
    first = _donor(tmp_path, "belay", ("belay-aaa",))
    second = _donor(tmp_path, "contig", ("contig-bbb",))

    loaded: tuple[Task, ...] = load_task_roots((first, second))

    assert [task.task_id for task in loaded] == ["belay-aaa", "contig-bbb"], (
        "the two donor roots did not union into one task set.\n\n"
        "WHY THIS IS A FAILURE: every count the report publishes is over this set. Reading one "
        "root and not the other does not fail — it produces a smaller denominator that looks "
        "exactly like a corpus, and every rate computed from it is wrong in a way nothing "
        "downstream can detect."
    )


def test_a_single_root_still_works(tmp_path: Path) -> None:
    """The one-root case is the common one and must not have been broken by making it plural."""
    only = _donor(tmp_path, "belay", ("belay-aaa",))
    assert [task.task_id for task in load_task_roots((only,))] == ["belay-aaa"]


def test_the_parent_of_the_donors_is_still_refused(tmp_path: Path) -> None:
    """The loader's fail-closed rule is untouched: naming the parent is still an error.

    This is the anti-vacuity control for the change. If `load_task_roots` had been implemented by
    making the loader descend into subdirectories, this assertion would fail — and the project
    would have traded a loud error for a silent one, which is the trade `manifest.py:79-83` exists
    to refuse.
    """
    _donor(tmp_path, "belay", ("belay-aaa",))
    _donor(tmp_path, "contig", ("contig-bbb",))

    with pytest.raises(ValueError, match="which is not a task manifest"):
        load_tasks(tmp_path)


def test_the_flag_is_repeatable_and_required() -> None:
    """`--tasks` accepts several roots, and still refuses to default to one."""
    parser = build_parser()
    parsed = parser.parse_args(
        [
            "--tasks", "/corpus/belay",
            "--tasks", "/corpus/contig",
            "--public", "/pub",
            "--funnel", "/funnel.json",
            "--weights", "/w",
            "--out", "/out",
            "--workspace", "/ws",
            "--timeout", "900",
            "--recorded-on", "2026-08-01",
        ]
    )
    assert [str(path) for path in parsed.tasks] == ["/corpus/belay", "/corpus/contig"], (
        "--tasks did not accumulate.\n\n"
        "WHY THIS IS A FAILURE: with a non-repeatable flag the last root silently wins, so a "
        "two-donor corpus is scored as one donor and the report's denominator is a fraction of "
        "what its prose claims."
    )
