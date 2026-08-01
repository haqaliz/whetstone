"""Which files a task's fix touches, and what the base is shown of them. Derived once, here.

Two callers need the same fact and must never derive it twice. `control.reference_patch` needs
the set of non-test paths a mined commit touched, so it can re-derive the commit's own fix and
prove the harness can reach PASS. `scoring.score` needs the same set, so it can show the base
those files as they stand at `base_commit` — the **oracle** setting. A second implementation of
"which files does this fix touch" would be a second definition of the task's scope, and the one
that disagreed would be the one nobody looked at.

It lives in its own module rather than in either caller because `control` already imports
`scoring` for the interpreter cache; putting the derivation in `control` and reading it from
`scoring` would close that loop into an import cycle. This module imports neither.

**Why the prompt shows source at all, and what that costs.** Measured against a real base over
three real tasks, every rollout came back `NOT_APPLIED`. The cause was in the rendered prompt
rather than in the model: it carried the problem statement and the failing node ids and **no code
whatever**, and a unified diff is written out of a file's exact context lines. The task as posed
was impossible, so the bake-off would have measured the prompt and published a zero
indistinguishable from P1's genuine pivot signal.

Showing the files fixes that and is **not free**, and the cost is stated here because this is
where it is incurred:

* the file set is derived from the **reference patch** — from where the answer lives. The prompt
  therefore tells the base *which files to change*, which is work the real setting includes;
* so every figure produced under this contract is a figure about the oracle setting. It is an
  upper bound on what the same base would do given only the bug report, and it must be published
  as such rather than quoted as retrieval-free performance.

This is the standard SWE-bench oracle condition and it is adopted deliberately, before any scored
run exists (PRD M7b permits exactly that: develop the contract against a declared dev subset, then
freeze it). It is a bound on what the number means, not a defect to be fixed later in silence.

**Held paths never leave here.** The path set is filtered by `is_test_path` and then pre-flighted
against `task.test_blobs`; a collision is a skip carrying its reason, never a partial answer.
`rendering.render_prompt` refuses a held path a second time, at the point of rendering, because
this module is not the only thing that can build a source map.

**Off the reward path.** `whetstone.bakeoff` imports `whetstone.verify` and `whetstone.tasks`;
neither may import back. Nothing here consults a model — it reads git and a checkout.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from whetstone.tasks.donor import GitFailed, is_test_path, run_git
from whetstone.verify.repo import CheckoutError, materialise
from whetstone.verify.task import Task

#: The provenance keys a mined task carries, and the two the derivation needs. Named because
#: `whetstone.tasks.mine` writes them and this module reads them, and a literal spelled inline at
#: the read site would let the two drift with nothing failing.
_COMMIT = "commit"
_PARENT = "parent"

#: The git statuses whose record carries **two** paths rather than one — a rename and a copy both
#: name a source and a destination. Spelled as a prefix set because git suffixes them with a
#: similarity score (`R100`, `C075`), and a parser that matched the bare letter would consume the
#: destination path as if it were the next status and desynchronise for the rest of the commit.
_TWO_PATH_STATUSES = ("R", "C")

#: How many characters of repository source one prompt may carry, in total across every file.
#:
#: **A bound rather than a truncation point.** The candidate bases in this bake-off are small
#: instruct models with context windows around 32k tokens; Python source runs roughly 3.5
#: characters to the token, so this budget is about 11k tokens — a third of the window — leaving
#: the problem statement, the node ids, the response contract and the 1024-token generation budget
#: (`mlx_runtime.DEFAULT_MAX_TOKENS`) comfortable room. A single vendored parser or generated
#: client would blow through it, and what happens then decides whether a run means anything: a
#: silently truncated file gives the base context lines that stop mid-way, every diff written from
#: them is charged `NOT_APPLIED`, and that rollout has run a different experiment from its
#: neighbours in the same denominator. So over-budget is a **skip with a reason** and the number
#: is written down here so an operator whose repository trips it can see what tripped it.
ORACLE_BUDGET_CHARS = 40_000

#: UTF-8's maximum bytes per character, used to refuse a file that *cannot* fit under the budget
#: without reading it into memory first. A pathological blob is the one case where "read it and
#: then measure" is the wrong order.
_MAX_BYTES_PER_CHARACTER = 4


@dataclass(frozen=True)
class Changed:
    """The non-test paths a task's fix touches, or the reason they could not be established.

    `paths is None` with a populated `reason` is the only other shape. An empty tuple would make
    "the commit touched nothing outside its tests" and "this task has no donor" the same value,
    and those have different responses: the first is a task nobody can pose or control for, the
    second is an ordinary property of a public instance.
    """

    #: Sorted, so two derivations of one task agree byte for byte. `None` if none could be had.
    paths: tuple[str, ...] | None

    #: Why there are none, or an empty string when there are.
    reason: str


@dataclass(frozen=True)
class Sources:
    """The files to show the base, or the reason there are none to show.

    `files is None` is a refusal and never a quiet empty prompt: `scoring.score` records it as
    skipped-with-reason rather than scoring the task, because a rollout asked the sourceless
    question sits in the same denominator as one asked the oracle question while having been asked
    something else entirely.
    """

    #: Path -> contents at `base_commit`, or `None` when the oracle could not be built.
    files: Mapping[str, str] | None

    #: Why there are none, or an empty string when there are.
    reason: str


def changed_paths(task: Task) -> Changed:
    """The non-test paths `task`'s own fix touches, re-derived from its donor.

    Returns rather than raises, because every reason this can fail is an ordinary property of a
    corpus rather than a defect: a public task has no donor commit to diff, a private task's donor
    may not be on this machine, and a commit may legitimately touch a held path. Each of those is
    a skip with a name on it, and a raise would turn the first one into an aborted bake-off.

    The pre-flight against `task.test_blobs` is the assertion worth reading. For the control arm,
    a reference patch touching a held path is refused by STRICT before anything runs — so using it
    would report the reward's own scope check as "the harness cannot reach PASS". For the oracle,
    the same collision would put the graded assertions into the context window. One check, two
    failures, and it is done here so that no caller can obtain a path set this module has not
    already vouched for.
    """
    commit = task.provenance.get(_COMMIT)
    parent = task.provenance.get(_PARENT)
    if not commit or not parent:
        return Changed(
            paths=None,
            reason=(
                f"task {task.task_id!r} carries no donor commit in its provenance, so the set of "
                f"files its fix touches cannot be re-derived: the harness cannot be shown to "
                f"reach PASS on it and the base cannot be shown the code it is asked to patch"
            ),
        )

    donor = Path(task.repo_url)
    try:
        touched = _touched_paths(donor, commit)
    except (GitFailed, subprocess.SubprocessError, OSError) as exc:
        return Changed(
            paths=None,
            reason=(
                f"the donor for task {task.task_id!r} could not be read at {str(donor)!r}: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

    paths = tuple(sorted(path for path in touched if not is_test_path(path)))
    if not paths:
        return Changed(
            paths=None,
            reason=(
                f"commit {commit} of task {task.task_id!r} touched no non-test path, so there is "
                f"neither a reference patch to apply — `git apply` refuses an empty diff — nor a "
                f"file to show the base"
            ),
        )

    collisions = sorted(set(paths) & set(task.test_blobs))
    if collisions:
        return Changed(
            paths=None,
            reason=(
                f"the fix for task {task.task_id!r} touches operator-held {collisions}, which "
                f"STRICT refuses as a cheat before anything runs. Using it as a reference would "
                f"report the reward's own scope check as `the harness cannot reach PASS`, and "
                f"showing it to a base would hand over the assertions the reward is computed from"
            ),
        )
    return Changed(paths=paths, reason="")


def oracle_sources(task: Task) -> Sources:
    """The files `task`'s fix touches, read out of the donor **at `base_commit`**.

    At `base_commit` and nowhere else, for two reasons that both end in `NOT_APPLIED`. The
    checkout `verify_strict` patches is at `base_commit`, so a file quoted from after the fix
    would give the base context lines that are not in the tree its diff is applied to. And it
    would contain the fix, which is not a hint but the answer.

    The checkout is made **here**, into a temporary directory that is removed again, rather than
    borrowed from `scoring.provision_from_lock`. That one is cached per distinct *pin set*, so the
    checkout behind a given environment belongs to whichever task built it first — reading another
    task's tree would show the base a file from the wrong repository, at the wrong commit, with
    nothing failing.

    A path that does not exist at `base_commit` is omitted rather than refused: a commit that
    creates a file is ordinary, and there is nothing at that path yet to show. A path whose bytes
    are not UTF-8 is omitted for the same reason — a binary asset is not something a unified diff
    over text can carry. If nothing readable remains, that is a refusal with a reason, because an
    empty oracle is the sourceless question wearing the oracle's name.
    """
    changed = changed_paths(task)
    if changed.paths is None:
        return Sources(files=None, reason=changed.reason)

    workspace = Path(tempfile.mkdtemp(prefix="whetstone-oracle-"))
    try:
        checkout = workspace / "checkout"
        try:
            materialise(task, checkout)
        except (CheckoutError, subprocess.SubprocessError, OSError) as exc:
            return Sources(
                files=None,
                reason=(
                    f"the donor for task {task.task_id!r} could not be checked out at "
                    f"{task.base_commit}: {type(exc).__name__}: {exc}"
                ),
            )
        return _read(task, checkout, changed.paths)
    finally:
        # Removed whatever happened. An oracle checkout left behind per task per candidate is a
        # copy of the user's repository accumulating in a temporary directory nobody chose.
        shutil.rmtree(workspace, ignore_errors=True)


def _read(task: Task, checkout: Path, paths: tuple[str, ...]) -> Sources:
    """Read `paths` out of `checkout`, refusing the whole set if it is over the budget.

    The budget is checked over the **total**, and the refusal is of everything rather than of the
    largest file. Dropping one file and showing the rest would be truncation with extra steps: the
    base would be patching around a file it was told nothing about, and the rollout would be
    scored beside ones that saw the whole picture.

    A file whose size on disk cannot possibly fit — even at one character per byte — is refused
    without being read, so a vendored blob is not loaded into memory to be measured and discarded.
    """
    files: dict[str, str] = {}
    total = 0
    for path in paths:
        target = checkout / path
        if not target.is_file():
            continue
        if target.stat().st_size > ORACLE_BUDGET_CHARS * _MAX_BYTES_PER_CHARACTER:
            return Sources(files=None, reason=_over(task, path, target.stat().st_size))
        try:
            text = target.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        total += len(text)
        if total > ORACLE_BUDGET_CHARS:
            return Sources(files=None, reason=_over(task, path, total))
        files[path] = text

    if not files:
        return Sources(
            files=None,
            reason=(
                f"none of the {len(paths)} non-test paths of task {task.task_id!r} could be read "
                f"at {task.base_commit}: every one is either created by the fix or not UTF-8 "
                f"text, so there is no source to show and the prompt would ask for a diff against "
                f"files the base has never seen"
            ),
        )
    return Sources(files=files, reason="")


def _over(task: Task, path: str, measured: int) -> str:
    """The one sentence a budget refusal leaves behind. Names the limit, so it can be judged."""
    return (
        f"the source files of task {task.task_id!r} exceed the {ORACLE_BUDGET_CHARS}-character "
        f"oracle budget at {path!r} ({measured} and counting), so the prompt would overrun the "
        f"context window. Truncating it would show the base part of a file, and a diff written "
        f"from context lines that stop mid-way is charged NOT_APPLIED — a rollout that ran a "
        f"different experiment from the others in its denominator, with nothing recording which"
    )


def _touched_paths(donor: Path, commit: str) -> frozenset[str]:
    """Every path `commit` touched, read from git's own name-status record.

    `-z` because a repository is allowed to hold a path with a newline or a quote in it, and
    git's default output quotes those — a parser splitting on newlines would silently drop such a
    file from the reference patch, producing a patch that does not reproduce the commit.

    A rename or a copy record carries **two** paths and every other carries one, so the fields are
    consumed by status rather than by position. Both halves of a rename are kept: the commit
    removed one path and created the other, and a reference patch missing either does not apply.
    """
    raw = run_git(["show", "--format=", "--name-status", "-z", commit], cwd=donor)
    fields = [field for field in raw.split("\0") if field.strip()]

    paths: set[str] = set()
    index = 0
    while index < len(fields):
        status = fields[index]
        wanted = 2 if status.startswith(_TWO_PATH_STATUSES) else 1
        paths.update(fields[index + 1 : index + 1 + wanted])
        index += 1 + wanted
    return frozenset(paths)


__all__ = [
    "ORACLE_BUDGET_CHARS",
    "Changed",
    "Sources",
    "changed_paths",
    "oracle_sources",
]
