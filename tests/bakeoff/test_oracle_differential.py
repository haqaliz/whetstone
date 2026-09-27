"""The machine-corpus differential (spec AC9): the predicate and the bakeoff agree, per direction.

`oracle_fittable` (aspect 1 of this unit) decides on immutable git objects whether a task's
oracle fits the budget; `oracle_sources` is the bakeoff's own build. The two share the path
derivation and the budget rule by identity (`test_oracle_fittable.py`), and this file is the
machine-level proof that they agree on the real corpus: for every corpus task with a readable
donor, predicate-false ⟹ `oracle_sources` refuses, predicate-true ⟹ `oracle_sources` builds,
and a refusal is a reason of the **same class, by name** — never a machine-state reason pooled
into a structural bucket.

The reason-class rule is the load-bearing assertion. The bakeoff refuses in two machine-state
sentences — a donor it could not read, a checkout it could not make — and four
structural/budget ones. A task whose donor cannot be read is **skipped-by-name and reported**,
never counted as agreement or disagreement: an exclusion from the held-out draw must be a
structural fact, and a test that pooled the two would bless a transient condition as a
permanent one.

**The machine-level state.** `tasks/local/` is gitignored, so a plain checkout has no
manifests; the corpus lives in the **primary checkout** of this repository, resolved from
`git worktree list --porcelain` the same way `test_heldout_document.py` resolves it, and each
task's donor lives where its manifest's `repo_url` says it does. In CI the corpus is absent and
the test skips with a reason naming exactly what is missing; on the operator's machine the full
66-task corpus is exercised, which takes minutes (66 tasks, git reads and one materialised
checkout per task) and is acceptable — no network and no clock, so the differential is
deterministic.

`test_the_refusal_classes_are_named_and_never_pooled` pins the class rule deterministically and
corpus-independently against the bakeoff's own sentences, so the pooling guard stays green even
where the machine differential must skip.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from whetstone.bakeoff.sources import oracle_fittable, oracle_sources
from whetstone.tasks.donor import GitFailed
from whetstone.tasks.manifest import load_tasks
from whetstone.verify.repo import CheckoutError
from whetstone.verify.task import Task

#: The repository root, for the git calls below. The corpus itself lives in the primary
#: checkout, resolved from this root's own worktree listing.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: The machine-level corpus roots: the two donor directories under the primary checkout's
#: gitignored `tasks/local/` (`tasks/README.md:63-64`).
_CORPUS_ROOTS = ("tasks/local/donor-b", "tasks/local/donor-a")

#: The bakeoff's machine-state refusal classes — a donor it could not read, a checkout it
#: could not make. These may never be pooled with the predicate's structural/budget classes:
#: a task whose oracle `oracle_sources` refuses on machine state is skipped-by-name and
#: reported, never counted as agreement or disagreement (spec AC9).
_MACHINE_STATE_CLASSES = frozenset({"donor-unreadable", "checkout"})

#: The bakeoff's structural/budget refusal classes — the classes the predicate can return
#: `fits=False` with, and the classes `oracle_sources` must refuse with when it does.
_STRUCTURAL_CLASSES = frozenset({"no-non-test-path", "vouched", "budget", "nothing-readable"})

#: One representative sentence per refusal class, spelled as the bakeoff writes them (each is
#: pinned byte-for-byte against the fixtures in `test_oracle_fittable.py`). The classifier
#: names a class by the sentence's distinctive phrase, so a sentence that drifts out of
#: recognition must fail the pooling pin rather than pool.
_CLASS_SENTENCES = {
    "budget": (
        "the source files of task 't' exceed the 80000-character oracle budget at 'bulk.py' "
        "(81234 and counting), so the prompt would overrun the context window. Truncating it "
        "would show the base part of a file, and a diff written from context lines that stop "
        "mid-way is charged NOT_APPLIED — a rollout that ran a different experiment from the "
        "others in its denominator, with nothing recording which"
    ),
    "no-non-test-path": (
        "commit a1b2c3 of task 't' touched no non-test path, so there is neither a reference "
        "patch to apply — `git apply` refuses an empty diff — nor a file to show the base"
    ),
    "vouched": (
        "the fix for task 't' touches operator-held ['conftest.py'], which STRICT refuses as "
        "a cheat before anything runs. Using it as a reference would report the reward's own "
        "scope check as `the harness cannot reach PASS`, and showing it to a base would hand "
        "over the assertions the reward is computed from"
    ),
    "nothing-readable": (
        "none of the 2 non-test paths of task 't' could be read at a1b2c3: every one is "
        "either created by the fix or not UTF-8 text, so there is no source to show and the "
        "prompt would ask for a diff against files the base has never seen"
    ),
    "donor-unreadable": (
        "the donor for task 't' could not be read at '/repo': GitFailed: fatal: not a git "
        "repository"
    ),
    "checkout": (
        "the donor for task 't' could not be checked out at a1b2c3: CheckoutError: could not "
        "clone '/repo': fatal: repository not found"
    ),
}

#: git's environment with the machine's configuration switched off — the discipline every
#: real-git call in this suite inherits (`test_format_hardening_frozen.py:42-67`).
_GIT_ENV = {
    "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_TERMINAL_PROMPT": "0",
}


def _primary_root() -> Path:
    """The primary checkout's root, resolved from `git worktree list --porcelain`.

    The first `worktree` entry is the main checkout; in CI — a plain checkout — that entry is
    this repository itself, and the skip below then fires on the missing corpus. Resolved with
    git's own words rather than assumed, so the test still finds the corpus when the layout
    changes.
    """
    completed = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=_GIT_ENV,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    for line in completed.stdout.splitlines():
        if line.startswith("worktree "):
            return Path(line.split(" ", 1)[1])
    raise RuntimeError(f"git worktree list gave no worktree entry:\n{completed.stdout}")


def _machine_corpus() -> tuple[Task, ...]:
    """The source-B corpus, or a skip naming what is missing.

    The manifests live under the primary checkout's gitignored `tasks/local/`; either root
    absent and the differential has nothing to read. The donors are not checked here beyond
    "is any donor on this machine at all": a task whose own donor cannot be read is
    **skipped-by-name** by the differential, which is exactly the condition this file exists
    to report rather than to refuse.
    """
    primary = _primary_root()
    roots = tuple(primary / root for root in _CORPUS_ROOTS)
    missing = [str(root) for root in roots if not root.is_dir()]
    if missing:
        pytest.skip(
            "the machine-level source-B corpus is absent here: "
            + ", ".join(missing)
            + " do not exist. CI's plain checkout has no gitignored manifests, so this "
            "differential runs only on the operator's machine"
        )
    tasks = tuple(load_tasks(roots[0])) + tuple(load_tasks(roots[1]))
    donors = {Path(task.repo_url) for task in tasks}
    if not any(donor.is_dir() for donor in donors):
        pytest.skip(
            "none of the donor repositories the corpus names exist here: "
            + ", ".join(sorted(str(donor) for donor in donors))
            + ". A differential over manifests whose donors are nowhere on the machine would "
            "skip every task by name, which is the operator's machine being absent — a skip, "
            "not a result"
        )
    return tasks


def _refusal_class(reason: str) -> str:
    """The refusal's class, named by the sentence it carries — machine state first.

    The bakeoff refuses in six sentences, each with a distinctive phrase. The two
    machine-state ones are matched first so a transient refusal is never read as a permanent
    structural one — the pooling rule (spec AC9) made concrete. A sentence that names none of
    them falls through to `unknown`, which the differential treats as a disagreement rather
    than a class.
    """
    if "could not be checked out at " in reason:
        return "checkout"
    if "could not be read at " in reason:
        return "donor-unreadable"
    if "oracle budget" in reason:
        return "budget"
    if "touched no non-test path" in reason:
        return "no-non-test-path"
    if "touches operator-held" in reason:
        return "vouched"
    if "could be read at " in reason:
        return "nothing-readable"
    return "unknown"


def test_the_refusal_classes_are_named_and_never_pooled() -> None:
    """The reason-class rule, pinned deterministically against the bakeoff's own sentences.

    This is the pooling guard (spec AC9) without the machine corpus: each of the six sentences
    `oracle_sources` can leave behind maps to exactly its own class, the machine-state set and
    the structural/budget set are disjoint, and the machine-state classes are exactly the two
    named. The sentences are the bakeoff's own — pinned byte-for-byte against fixtures in
    `test_oracle_fittable.py` — so a sentence that drifts out of recognition fails here before
    the machine differential can pool it.
    """
    for expected, sentence in _CLASS_SENTENCES.items():
        assert _refusal_class(sentence) == expected, (
            f"the bakeoff's {expected!r} sentence is classified as "
            f"{_refusal_class(sentence)!r}. The differential names a refusal's class by the "
            f"sentence it carries, and a sentence this file cannot classify is a sentence the "
            f"machine differential cannot safely count"
        )

    assert frozenset({"donor-unreadable", "checkout"}) == _MACHINE_STATE_CLASSES, (
        "the machine-state class set is not exactly the donor-unreadable and checkout "
        "sentences, so the skip-by-name rule covers classes it was not written for"
    )
    assert not (_MACHINE_STATE_CLASSES & _STRUCTURAL_CLASSES), (
        "a machine-state class has leaked into the structural set, so the differential would "
        "count a transient refusal as a permanent exclusion"
    )


def test_the_machine_corpus_is_the_declared_set() -> None:
    """The corpus is the declared 66: the differential is exercised here, not skipped here.

    The skip above exists for CI; on the machine that generated the corpus it must never fire,
    or the differential would be asserting over nothing.
    """
    tasks = _machine_corpus()
    assert len(tasks) == 66, (
        "the machine-level source-B corpus is the declared set: 21 donor-b + 45 donor-a "
        f"manifests, got {len(tasks)}"
    )


def test_the_differential_over_the_machine_corpus() -> None:
    """The per-direction pin over the real corpus (spec AC9), with reason classes never pooled.

    For every corpus task with a readable donor, both directions are asserted: a task the
    predicate fits must be built by `oracle_sources`, and a task it refuses must be refused by
    `oracle_sources` for a reason of the same structural/budget class. A task whose donor the
    predicate cannot read, or whose build `oracle_sources` refuses on machine state, is
    skipped-by-name and reported — never counted as agreement or disagreement, because pooling
    the two would bless a transient condition as a permanent exclusion.

    The breakdown is printed so the operator's run shows exactly what was counted: how many
    tasks the predicate fitted and the bakeoff built, how many each class excluded, and which
    tasks were skipped-by-name and why.
    """
    tasks = _machine_corpus()

    fitted: list[str] = []
    excluded: dict[str, list[str]] = {}
    skipped: list[str] = []
    disagreements: list[str] = []

    for task in tasks:
        try:
            fit = oracle_fittable(task)
        except (GitFailed, subprocess.SubprocessError, OSError) as exc:
            skipped.append(
                f"task {task.task_id}: the predicate could not read its donor: "
                f"{type(exc).__name__}: {exc}"
            )
            continue
        try:
            sources = oracle_sources(task)
        except (GitFailed, CheckoutError, subprocess.SubprocessError, OSError) as exc:
            skipped.append(
                f"task {task.task_id}: the bakeoff raised while building: "
                f"{type(exc).__name__}: {exc}"
            )
            continue

        if sources.files is None and _refusal_class(sources.reason) in _MACHINE_STATE_CLASSES:
            skipped.append(
                f"task {task.task_id}: the bakeoff refused on machine state "
                f"({_refusal_class(sources.reason)}): {sources.reason}"
            )
            continue

        if fit.fits:
            if sources.files is None:
                disagreements.append(
                    f"task {task.task_id}: the predicate fits but the bakeoff refuses for "
                    f"{_refusal_class(sources.reason)}: {sources.reason}"
                )
            else:
                fitted.append(task.task_id)
            continue

        predicate_class = _refusal_class(fit.reason)
        if sources.files is not None:
            disagreements.append(
                f"task {task.task_id}: the predicate refuses ({fit.reason}) but the bakeoff "
                "builds an oracle"
            )
            continue
        if (
            predicate_class == _refusal_class(sources.reason)
            and predicate_class not in _MACHINE_STATE_CLASSES
        ):
            excluded.setdefault(predicate_class, []).append(task.task_id)
        else:
            disagreements.append(
                f"task {task.task_id}: the predicate and the bakeoff refuse in different "
                f"classes ({predicate_class} vs {_refusal_class(sources.reason)}): "
                f"{sources.reason}"
            )

    total_excluded = sum(len(ids) for ids in excluded.values())
    print(
        f"differential over {len(tasks)} corpus tasks: {len(fitted)} fitted, "
        f"{total_excluded} excluded by class "
        f"({', '.join(f'{cls}={len(ids)}' for cls, ids in sorted(excluded.items()))}), "
        f"{len(skipped)} skipped-by-name"
    )
    for line in skipped:
        print(f"  {line}")

    assert fitted, (
        "the differential counted no task the bakeoff builds. Both directions of the "
        "predicate must be exercised on the real corpus, or this test is asserting over "
        "nothing; a run that skipped every task is a run that verified nothing"
    )
    assert excluded, (
        "the differential counted no task the predicate refuses. Both directions of the "
        "predicate must be exercised on the real corpus, or this test is asserting over "
        "nothing; a corpus in which every oracle fits would not exercise the refusal half "
        "of the pin"
    )
    assert not disagreements, (
        "the predicate and the bakeoff disagree on the real corpus:\n\n"
        + "\n\n".join(disagreements)
    )