"""Which commits in a local repository could become tasks. Git plumbing, offline, no model.

Source B — the pre-registered headline (`docs/ROADMAP.md` § 6) — mints tasks from the operator's
own repositories: uncontaminated by any public benchmark, and never leaving the machine. A task
comes from **a commit that turned a failing test green**, and this module is the half that finds
those commits. It reads history; it runs nothing and it resolves nothing.

**The mechanical insight the whole source rests on.** `base_commit` is the candidate's **parent**
`P`, and `test_blobs` holds the **child** `C`'s version of the test files. STRICT's unconditional
restore (`strict.py:180-183`) then *is* the application of the test patch: it writes `C`'s tests
over a `P` checkout before pytest runs. No separate test-patch mechanism exists here, and none
should be built (PRD § 5.4).

**Selection is deliberately narrow, and the narrowness is a refusal to relax the reward path.**
A commit qualifies only if it modifies at least one existing test `.py` and touches at least one
non-test `.py`. A commit that merely *adds* a test file is excluded — that test does not exist at
`P`, and `strict.py:151-160` answers UNVERIFIED for a task whose held paths are absent from the
checkout. Widening that guard to admit added tests is a change on the reward path, which is
deliberately out of scope for this slice (PRD D2). The measured cost is real and is recorded
rather than hidden: ~35% of belay's candidates and ~50% of rereflect's.

Merges are excluded because a merge has two parents and `base_commit` is one commit; the root
commit is excluded because it has none.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

#: Matches `verify/repo.py`: long enough for a large history on a slow disk, short enough that a
#: wedged git does not hang an overnight mint forever.
_GIT_TIMEOUT = 300.0

#: `git log` records are NUL-separated (`-z`) and their fields separated by a unit separator, so
#: neither a commit subject containing spaces nor one containing a tab can be misread as a field
#: boundary. A subject cannot contain either of these two bytes.
_RECORD = "\0"
_FIELD = "\x1f"

#: Directory names that make everything below them test code. Exactly these two, spelled in full:
#: `testing/` and `contest.py` are not test paths, and a substring match would claim both.
_TEST_DIRECTORIES = frozenset({"test", "tests"})

#: git's name-status letter for "this file existed at the parent and its contents changed". The
#: only status that can yield a held test, because the held path has to exist at `base_commit`.
#: `A` (added) is PRD D2's exclusion; `R`/`C` name a path that is new at the child, and `T` is a
#: mode change we have no reason to mint from.
_MODIFIED = "M"


class GitFailed(RuntimeError):
    """git itself said no — not a repository, an unreadable object, a wedged process.

    Raised rather than folded into an empty candidate list. "Nothing here is mintable" and "you
    pointed me at the wrong directory" are different facts, and only the first is a finding
    about the donor.
    """


@dataclass(frozen=True)
class Candidate:
    """One commit that could become a task, and everything the later phases read off it.

    `parent` is what becomes `base_commit`; `held_tests` is what becomes the core of
    `test_blobs` (Phase 2 adds the conftest floor); and `source_paths` + `other_paths` together
    are the **gold patch** — the commit's diff with the test files taken out. That split is not
    presentational: a path that appears in both the held set and the gold patch produces a task
    that can never pass, because the restore overwrites the fix. `held.py` refuses exactly that.

    `other_paths` — the non-`.py` half — is carried rather than dropped because it is the
    measured shape of the cheat-10 residual: ~22% of contig's mintable commits (49/224) also
    touch a data file that no `conftest` rule and no import walk would ever see.
    """

    sha: str
    parent: str
    subject: str
    held_tests: tuple[str, ...]
    source_paths: tuple[str, ...]
    other_paths: tuple[str, ...]


def is_test_path(path: str) -> bool:
    """Is this path test code? The judgement call the rest of the miner is built on.

    A `.py` file counts as test code when it sits under a `test/` or `tests/` directory, or when
    its own name is `test_*.py` or `*_test.py` — pytest's own default discovery patterns, plus
    the directory convention pytest does not itself require but every donor here follows.

    **A root `conftest.py` is deliberately NOT test code.** It is an ordinary source file that
    the gold patch may legitimately change, and classifying it as a test would move it out of the
    gold patch and into the held set — where `strict.py`'s restore would write the operator's
    golden bytes over the very fix under verification, producing a task that is permanently
    unpassable and reported as an ordinary FAIL. Under `tests/` the same filename *is* test code,
    because a commit that edits it is editing the operator's test scaffolding.

    Written as one named predicate rather than inlined at its three call sites because it is a
    judgement, not a fact, and a judgement that decides which files a policy may not touch
    deserves to be visible, tested, and changed in one place.
    """
    if not path.endswith(".py"):
        return False
    pure = PurePosixPath(path)
    if _TEST_DIRECTORIES & set(pure.parts[:-1]):
        return True
    return pure.name.startswith("test_") or pure.name.endswith("_test.py")


def candidates(donor: Path) -> tuple[Candidate, ...]:
    """Every mintable commit in `donor`, oldest first.

    Walks `HEAD`'s history rather than `--all`: a commit on an abandoned branch is not part of
    the line the repository actually took, and mining one would mint a task from work its own
    author discarded. Oldest-first so a re-mint of the same donor enumerates in the same order —
    the order is nothing the reward depends on, but a corpus that shuffles between runs is one
    nobody can diff.

    Reads history only. No network, no checkout, no test run: the donor's working tree is not
    touched, and this is safe to point at a repository the operator is mid-edit on.
    """
    location = Path(donor)
    found: list[Candidate] = []
    for sha, parents, subject in _history(location):
        if len(parents) != 1:
            # A merge has two parents and the root commit has none; `base_commit` is one commit.
            continue
        held_tests, source_paths, other_paths = _classify(_touched(location, sha))
        if not held_tests or not source_paths:
            continue
        found.append(
            Candidate(
                sha=sha,
                parent=parents[0],
                subject=subject,
                held_tests=held_tests,
                source_paths=source_paths,
                other_paths=other_paths,
            )
        )
    return tuple(found)


def _history(donor: Path) -> tuple[tuple[str, tuple[str, ...], str], ...]:
    """`(sha, parents, subject)` per commit reachable from HEAD, oldest first.

    Merges are filtered here as well as in `candidates`, which is not redundant: `--no-merges`
    keeps a large repository's log from carrying records nothing will read, while the parent
    count in `candidates` is what actually states the rule — a merge and a root commit are both
    "this has no single parent", and one guard says so for both.
    """
    raw = run_git(
        ["log", "--no-merges", "--reverse", "-z", f"--format=%H{_FIELD}%P{_FIELD}%s"],
        cwd=donor,
    )
    commits: list[tuple[str, tuple[str, ...], str]] = []
    for record in raw.split(_RECORD):
        if not record:
            continue
        sha, parents, subject = record.split(_FIELD, 2)
        commits.append((sha, tuple(parents.split()), subject))
    return tuple(commits)


def _touched(donor: Path, sha: str) -> tuple[tuple[str, str], ...]:
    """`(status, path)` for everything the commit touched, from git's own name-status report.

    `-z` because a path may contain anything a filesystem allows, including a newline, and git
    would otherwise quote-escape it into a spelling that matches nothing downstream. A rename or
    copy spends two path fields on one status; both sides are returned and classified
    independently, since neither of them is a *modification* and so neither can be held.
    """
    raw = run_git(["show", "--format=", "--name-status", "-z", sha], cwd=donor)
    fields = iter(field for field in raw.split(_RECORD) if field)
    touched: list[tuple[str, str]] = []
    for status in fields:
        paths = 2 if status[:1] in {"R", "C"} else 1
        for _ in range(paths):
            path = next(fields, None)
            if path is None:
                raise GitFailed(
                    f"git reported status {status!r} for commit {sha} with no path after it, so "
                    f"what the commit touched cannot be read"
                )
            touched.append((status, path))
    return tuple(touched)


def _classify(
    touched: tuple[tuple[str, str], ...],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Split what a commit touched into the held tests, the source files, and everything else.

    The held half takes only status `M`. The other two halves take every status, because the gold
    patch is the commit's whole non-test diff — a source file the commit *deleted* is part of the
    fix as surely as one it edited, and dropping it would produce a gold patch that does not
    reproduce the commit.
    """
    held_tests: list[str] = []
    source_paths: list[str] = []
    other_paths: list[str] = []
    for status, path in touched:
        if is_test_path(path):
            if status == _MODIFIED:
                held_tests.append(path)
            continue
        (source_paths if path.endswith(".py") else other_paths).append(path)
    return tuple(sorted(held_tests)), tuple(sorted(source_paths)), tuple(sorted(other_paths))


def run_git(args: list[str], *, cwd: Path) -> str:
    """git with the machine's configuration switched off. Raises `GitFailed` on a non-zero exit.

    The same discipline as `verify/repo.py:_git`, restated here rather than imported because that
    one is the reward path's private helper and this one is ingestion's — coupling them would
    make a change made for the miner's convenience a change to the reward. What must not drift is
    the *discipline*, and it is this:

    - `GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` at `/dev/null`, so a developer's `~/.gitconfig` —
      a `hooksPath`, a clean/smudge filter, commit signing, `diff.noprefix` — cannot change what
      gets mined. A miner whose output depends on the operator's dotfiles mints a corpus nobody
      else can reproduce.
    - `GIT_TERMINAL_PROMPT=0`, so a repository with a remote that wants credentials fails
      instead of blocking an overnight mint on a password nobody is there to type.
    - An explicit timeout, so a wedged git is an error rather than a hang.

    Public because `derive.py` mints through this same wrapper: two git front doors would be two
    sets of environment guarantees, and the second one would be the one nobody checked.
    """
    environment = dict(os.environ)
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    completed = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=environment,
        timeout=_GIT_TIMEOUT,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise GitFailed(detail or f"git {args[0]} exited {completed.returncode}")
    return completed.stdout


__all__ = ["Candidate", "GitFailed", "candidates", "is_test_path", "run_git"]
