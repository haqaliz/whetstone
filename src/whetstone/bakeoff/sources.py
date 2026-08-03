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

**The character budget was raised after a run had been observed, and that has to be said plainly.**
`ORACLE_BUDGET_CHARS` shipped at 40,000 — chosen on paper as "about a third of a 32k window" — and
the first scored bake-off then skipped **20 of 63** private tasks as over-budget: `src/<pkg>/
cli.py`, `src/<pkg>/cli.py`, `CHANGELOG.md` and their neighbours are simply larger than that. The
limit was excluding a third of the corpus from being asked a question at all. It is now 80,000,
with the arithmetic written out at the constant.

Changing a parameter after looking at a run is how tuning starts, so the two facts that make this
one defensible are recorded here rather than in a commit message:

1. **the run that revealed it ABORTED and published no report.** Its control arm refused source A,
   `sweep.rankable` refused the sweep, and nothing about any base was written down. There is no
   number this change could have been made to improve, because there is no number;
2. **it cannot alter any already-posable task.** The budget decides *whether* an oracle is returned
   and never *what* one contains — a task inside the old limit renders the same files, with the
   same contents, in the same order, to the same `prompt_sha256`. The change moves tasks from *not
   posable* to *posable*; it moves no task's outcome.

The second is the load-bearing claim and it is asserted, not asserted-to:
`tests/bakeoff/test_oracle_sources.py::test_raising_the_budget_cannot_move_a_prompt_that_already_fitted`
renders one task under both budgets and requires the two prompts and their hashes to be identical.
Should the budget ever become a truncation point, that test fails before anything is scored.

**Two routes, chosen by what the task carries, and they never blend.** A mined task names a commit
on this machine and the set is re-derived from it. A public SWE-bench instance names no commit —
its fixing commit is not here — so the set comes from the **paths its committed gold patch
touches**, read out of the source-A pool by `verify.repo.declared_paths`: git's own parse of a
diff, performed without applying it. Nothing is derived on that route; the scope is given, and the
only thing taken from the pool is *which files*, never their contents. Those still come from the
checkout at `base_commit`, so what the base is shown is the broken file rather than the answer.

That second route is why source A can be asked anything at all. Under the donor derivation alone
the one eligible instance came back with no oracle and was never posed to a base — a source that
`PREREGISTRATION.md:142-143` requires be published beside source B while contributing a funnel, a
harness verdict, and no scored result.

**Neither route falls back to the other**, in either direction, and `Origin` records which one
ran. A private task whose donor is missing is a skip about that donor: reaching into a public
dataset on an id collision would scope it by a patch for another repository entirely, and the
prompt built from it would be about neither. A public instance has nothing to re-derive from, and
its `repo_url` is a GitHub URL — a fall-through to the donor route would put a network call where
a refusal belongs.

**Held paths never leave here.** The path set is filtered by `is_test_path` and then pre-flighted
against `task.test_blobs` — on **both** routes, and the pool route is the one that needs it most:
that patch is a dataset artefact nobody in this project wrote or re-derived. A collision is a skip
carrying its reason, never a partial answer. `rendering.render_prompt` refuses a held path a
second time, at the point of rendering, because this module is not the only thing that can build a
source map.

**Off the reward path.** `whetstone.bakeoff` imports `whetstone.verify` and `whetstone.tasks`;
neither may import back. Nothing here consults a model — it reads git and a checkout.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from whetstone.tasks.donor import GitFailed, is_test_path, run_git
from whetstone.tasks.fetch import read_pool
from whetstone.verify.repo import CheckoutError, PatchError, declared_paths, materialise
from whetstone.verify.task import Task

#: The provenance keys a mined task carries, and the two the derivation needs. Named because
#: `whetstone.tasks.mine` writes them and this module reads them, and a literal spelled inline at
#: the read site would let the two drift with nothing failing.
_COMMIT = "commit"
_PARENT = "parent"

#: The provenance key a source-A manifest carries in place of a commit. `whetstone.tasks.public`
#: writes the instance id into both this key and `task_id`; both are consulted below, in that
#: order, so a manifest that ever stops using its instance id as its task id still resolves.
_INSTANCE = "instance_id"

#: The git statuses whose record carries **two** paths rather than one — a rename and a copy both
#: name a source and a destination. Spelled as a prefix set because git suffixes them with a
#: similarity score (`R100`, `C075`), and a parser that matched the bare letter would consume the
#: destination path as if it were the next status and desynchronise for the rest of the commit.
_TWO_PATH_STATUSES = ("R", "C")

#: How many characters of repository source one prompt may carry, in total across every file.
#:
#: **A bound rather than a truncation point**, and the arithmetic is written out because the number
#: decides which tasks can be posed at all:
#:
#: * every candidate — Qwen2.5-Coder-Instruct at 3B, 7B and 14B — carries a **32,768-token**
#:   context window;
#: * `mlx_runtime.DEFAULT_MAX_TOKENS` reserves **1,024** of those for what the base writes;
#: * Python source runs roughly **3.5 characters to the token**, so 80,000 characters is about
#:   **22,900 tokens**;
#: * 32,768 less 22,900 less 1,024 leaves about **8,800 tokens** — some 31,000 characters — for the
#:   chat template, the problem statement, the failing node ids and the response contract. That is
#:   headroom, not a fit: the whole scaffold measures in the hundreds of tokens and the longest
#:   problem statement in either corpus is far short of the rest.
#:
#: What happens at the limit decides whether a run means anything: a silently truncated file gives
#: the base context lines that stop mid-way, every diff written from them is charged `NOT_APPLIED`,
#: and that rollout has run a different experiment from its neighbours in the same denominator. So
#: over-budget is a **skip with a reason** naming the limit.
#:
#: **Measured over the real source-B corpus**, by running `oracle_sources` across all 66 manifests
#: at each limit: **46 of 66** posable at 40,000 and **54 of 66** at 80,000. The twelve that remain
#: are not a limit set too low. Two are files no model should be shown whatever the budget —
#: `belay-bffecd967c60` touches `uv.lock` (298,403 characters) and `contig-289854d0a7a2` a 2 MB
#: `.jsonl` corpus — and most of the rest are a single `cli.py` of 85,000 to 125,000 characters,
#: which at 3.5 characters to the token is 24,000 to 36,000 tokens and does not fit in the window
#: at any bound this contract could honestly set. Raising further would also spend the headroom the
#: arithmetic above rests on: at 3.0 characters to the token — the estimate being wrong in the
#: direction that hurts — 80,000 characters is still only 26,700 tokens and fits, while 100,000
#: would be 33,300 and would not.
ORACLE_BUDGET_CHARS = 80_000

#: UTF-8's maximum bytes per character, used to refuse a file that *cannot* fit under the budget
#: without reading it into memory first. A pathological blob is the one case where "read it and
#: then measure" is the wrong order.
_MAX_BYTES_PER_CHARACTER = 4


class Origin(str, Enum):
    """Where a task's fix — and therefore its scope — came from. Recorded, never inferred later.

    `str` mixin so it serialises as its name into the journal and reads as itself in a report,
    matching `Status` and `Control`.

    Defined here rather than in `control`, which is where it is also used: `control` imports this
    module for the path derivation, so the enum both of them record has to live at the end that
    does not import back. It is re-exported from `control` for the callers that already read it
    there.

    The two live routes are not equally strong evidence, which is the whole reason this exists.
    `DONOR` means the fix was computed here, now, from a commit on this machine. `POOL` means it
    was read verbatim out of a committed dataset artefact that nobody in this project re-derived
    from anything. Publishing both as "the task's own fix" would claim the first for the second.
    """

    #: Re-derived from `provenance.commit` against `provenance.parent` in the task's own donor.
    DONOR = "DONOR"

    #: Read from the source-A pool's `patch` field, keyed by instance id. Source A only.
    POOL = "POOL"

    #: Nothing was obtained. Distinct from the two above rather than folded into a `None`, so a
    #: skip can never be read off the record as a derivation that happened.
    NONE = "NONE"


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

    #: Which route produced them — the user's own commit, or the committed pool — or `NONE` when
    #: neither did. Carried rather than reconstructed from `task.source` afterwards, because the
    #: route is chosen by what the task carries and a later reader guessing from the source label
    #: would be re-deriving a fact this module already knew.
    origin: Origin


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

    #: Which route decided *which files* these are. The contents are always the checkout's, on
    #: both routes; this says where the scope came from, and it is the same distinction `control`
    #: records about the reference patch.
    origin: Origin


def changed_paths(task: Task, *, pool: Path | None = None) -> Changed:
    """The non-test paths `task`'s own fix touches — from its donor, or from `pool`.

    Returns rather than raises, because every reason this can fail is an ordinary property of a
    corpus rather than a defect: a private task's donor may not be on this machine, a commit may
    legitimately touch a held path, and a pool may not carry the instance it was asked for. Each
    of those is a skip with a name on it, and a raise would turn the first one into an aborted
    bake-off.

    **The route is chosen by what the task carries, and only by that** — the same rule, for the
    same reasons, that `control.reference_patch` follows: a donor commit means the donor, no donor
    commit means the pool, and neither falls back to the other. `pool` is an argument rather than a
    path this module knows, because a hardcoded `tasks/public/pool.json` would make every test
    either read a 3.2 MB committed artefact or exercise a different code path from the one that
    runs at night. Omitting it makes every source-A task a skip that says so, and changes nothing
    about source B.

    The pre-flight against `task.test_blobs` is the assertion worth reading, and it applies to
    whichever route ran. For the control arm, a reference patch touching a held path is refused by
    STRICT before anything runs — so using it would report the reward's own scope check as "the
    harness cannot reach PASS". For the oracle, the same collision would put the graded assertions
    into the context window. One check, two failures, and it is done here so that no caller can
    obtain a path set this module has not already vouched for.
    """
    if not (task.provenance.get(_COMMIT) and task.provenance.get(_PARENT)):
        return _from_pool(task, pool)
    return _from_donor(task)


def _from_donor(task: Task) -> Changed:
    """Source B's route: the paths the mined commit itself touched, read from git now."""
    commit = task.provenance[_COMMIT]
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
            origin=Origin.NONE,
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
            origin=Origin.NONE,
        )
    return _vouched(task, paths, Origin.DONOR)


def _from_pool(task: Task, pool: Path | None) -> Changed:
    """Source A's route: the non-test paths the instance's committed gold patch declares.

    Nothing is derived here — the patch is given — so the only question is which files it names,
    and that is asked of `verify.repo.declared_paths`: `git apply --numstat`, which parses and
    reports without writing. It is the same parse STRICT runs on a patch before applying it, and a
    second parser in this module would be a second answer to "what does this diff touch" with only
    one of them reviewed. The scratch directory it runs in need not be a repository, and nothing
    is applied anywhere.

    Only the **paths** come from the pool. Their contents are read out of the checkout at
    `base_commit` by `_read`, exactly as on the donor route, because the pool's copy of the file
    would be the fixed one — the answer rather than the question.

    The gold patch of a SWE-bench instance touches no test by construction, since the dataset
    splits each record into `patch` and `test_patch` precisely so it does not. That is the
    dataset's claim about itself and it is checked rather than trusted: `is_test_path` filters,
    and `_vouched` then refuses any survivor the operator holds.
    """
    instance = str(task.provenance.get(_INSTANCE) or task.task_id)
    if pool is None:
        return Changed(
            paths=None,
            reason=(
                f"task {task.task_id!r} carries no donor commit in its provenance and no source-A "
                f"pool was offered, so the files its fix touches cannot be established: they are "
                f"declared by the gold patch in the pool, keyed by instance {instance!r}, and "
                f"nothing here was told where that pool is"
            ),
            origin=Origin.NONE,
        )

    try:
        instances = read_pool(Path(pool))
    except ValueError as exc:
        return Changed(
            paths=None,
            reason=f"the source-A pool for task {task.task_id!r} could not be read: {exc}",
            origin=Origin.NONE,
        )

    found = [one for one in instances if one.instance_id == instance]
    if not found or not found[0].patch.strip():
        return Changed(
            paths=None,
            reason=(
                f"the source-A pool at {str(pool)!r} carries no usable gold patch for instance "
                f"{instance!r} of task {task.task_id!r} ({len(instances)} instances read), so "
                f"there is no statement of which files this task's fix touches and the base "
                f"cannot be shown the code it is asked to patch"
            ),
            origin=Origin.NONE,
        )

    try:
        with tempfile.TemporaryDirectory(prefix="whetstone-pool-") as scratch:
            touched = declared_paths(found[0].patch, Path(scratch))
    except (PatchError, subprocess.SubprocessError, OSError) as exc:
        return Changed(
            paths=None,
            reason=(
                f"the gold patch for instance {instance!r} of task {task.task_id!r} could not be "
                f"parsed: {type(exc).__name__}: {exc}"
            ),
            origin=Origin.NONE,
        )

    paths = tuple(sorted(path for path in touched if not is_test_path(path)))
    if not paths:
        return Changed(
            paths=None,
            reason=(
                f"the gold patch for instance {instance!r} of task {task.task_id!r} declares no "
                f"non-test path, so there is no file to show the base — a dataset row whose fix "
                f"is entirely test code is not a task this contract can pose"
            ),
            origin=Origin.NONE,
        )
    return _vouched(task, paths, Origin.POOL)


def _vouched(task: Task, paths: tuple[str, ...], origin: Origin) -> Changed:
    """The pre-flight both routes end in: no path the operator holds, whatever produced it.

    Shared rather than written twice because it is the boundary itself. It matters most on the
    pool route, whose patch is a dataset artefact nobody in this project wrote or re-derived — and
    a path that survived `is_test_path` while sitting in `test_blobs` (a root `conftest.py` is the
    real case) is exactly the one a naming convention would wave through.
    """
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
            origin=Origin.NONE,
        )
    return Changed(paths=paths, reason="", origin=origin)


def oracle_sources(task: Task, *, pool: Path | None = None) -> Sources:
    """The files `task`'s fix touches, read out of the checkout **at `base_commit`**.

    `pool` decides only where the *path set* comes from for a task with no donor commit — see
    `changed_paths`. The contents are read from the checkout on both routes, so what a source-A
    base is shown is the file as it stands at `base_commit`, never the pool's copy of the fix.

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
    changed = changed_paths(task, pool=pool)
    if changed.paths is None:
        return Sources(files=None, reason=changed.reason, origin=changed.origin)

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
                origin=Origin.NONE,
            )
        return _read(task, checkout, changed.paths, changed.origin)
    finally:
        # Removed whatever happened. An oracle checkout left behind per task per candidate is a
        # copy of the user's repository accumulating in a temporary directory nobody chose.
        shutil.rmtree(workspace, ignore_errors=True)


def _read(task: Task, checkout: Path, paths: tuple[str, ...], origin: Origin) -> Sources:
    """Read `paths` out of `checkout`, refusing the whole set if it is over the budget.

    `origin` is carried through rather than re-decided here: what a file is read from is the
    checkout, always, and which route chose the path set was settled by `changed_paths`. A refusal
    returns `Origin.NONE`, because no oracle was obtained and a record saying otherwise would name
    a derivation that produced nothing.

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
            return Sources(
                files=None,
                reason=_over(task, path, target.stat().st_size),
                origin=Origin.NONE,
            )
        try:
            text = target.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        total += len(text)
        if total > ORACLE_BUDGET_CHARS:
            return Sources(files=None, reason=_over(task, path, total), origin=Origin.NONE)
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
            origin=Origin.NONE,
        )
    return Sources(files=files, reason="", origin=origin)


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
    "Origin",
    "Sources",
    "changed_paths",
    "oracle_sources",
]
