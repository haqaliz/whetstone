"""Materialising a task's checkout, and putting a patch into it. Shared by STRICT and WEAK.

Both verifiers start the same way — a clean tree at `base_commit` with the policy's patch
applied — and differ only in what they check afterwards. That shared start lives here so the
two cannot drift apart: a bug in the checkout that made STRICT stricter than WEAK for an
unrelated reason would corrupt the differential the corpus is built to measure.

**Why git, and why the real thing.** `Task.repo_url` and `Task.base_commit` are a repository
and a commit; anything less than a real clone would make the contract's own fields decorative
and would leave the ingestion slice to discover the gap. `git apply` is used for the same
reason — a hand-rolled patch parser on the reward path would be one more thing to get subtly
wrong, and git's is the parser the patches were produced by.

**Why this runs OUTSIDE the sandbox, deliberately.** A real task's `repo_url` is remote, and
the sandbox denies the network — the checkout could not happen inside it. That is acceptable
because of *whose* input each step consumes: the clone consumes `repo_url` and `base_commit`,
which come from the operator's manifest, while the sandbox exists to confine the one step
that runs **policy-authored code**, which is pytest. `git apply` does not execute anything
from the patch and refuses to write outside the work tree, so applying a policy patch here
does not run policy code. If that ever stops being true — a patch format that can execute, a
git that grew a hook out of a tree file — this step moves inside the sandbox.

Stdlib and a subprocess. No model, no network of our own.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from whetstone.verify.task import Task

#: Long enough for a large clone on a slow disk, short enough that a wedged git does not hang
#: a nightly loop forever. Distinct from the caller's pytest timeout: this is the operator's
#: own machinery, not the run being measured.
_GIT_TIMEOUT = 300.0


class CheckoutError(RuntimeError):
    """The task could not be materialised — a bad `repo_url`, a `base_commit` that isn't there.

    Raised, not returned, because it is a statement about the *task* rather than the patch.
    Callers turn it into UNVERIFIED: a task we could not set up is one we could not check.
    """


class PatchError(RuntimeError):
    """The patch could not be read or could not be applied.

    Unlike `CheckoutError` this is a statement about the *patch*, and callers turn it into
    FAIL: a policy that emitted a diff that does not apply produced a wrong answer, not an
    unverifiable one.
    """


def materialise(task: Task, destination: Path) -> None:
    """Clone `task.repo_url` into `destination` and check out `task.base_commit`.

    Detached on purpose: `base_commit` is a commit, and resolving it through a branch name
    would let the default branch decide what got verified.
    """
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        _git(
            [
                "clone",
                "--quiet",
                "--no-checkout",
                "--no-hardlinks",
                task.repo_url,
                str(destination),
            ],
            cwd=destination.parent,
        )
    except _GitFailed as exc:
        raise CheckoutError(f"could not clone {task.repo_url!r}: {exc}") from exc
    try:
        _git(["checkout", "--quiet", "--detach", task.base_commit], cwd=destination)
    except _GitFailed as exc:
        raise CheckoutError(
            f"could not check out {task.base_commit!r} in {task.repo_url!r}: {exc}"
        ) from exc


def declared_paths(patch: str, checkout: Path) -> tuple[str, ...]:
    """The paths the patch says it touches, read WITHOUT applying it.

    `git apply --numstat` parses and reports; it writes nothing. Asking first means a patch
    aimed at an operator-held test is refused before it has touched the disk at all.

    It reports a rename by its **destination only** — verified against git on this machine —
    so this is not a complete footprint and must not be used as one. `touched_paths` is the
    complete one; this is the early exit.
    """
    try:
        raw = _git(["apply", "--numstat", "-z", "-"], cwd=checkout, stdin=patch)
    except _GitFailed as exc:
        raise PatchError(f"the patch could not be parsed: {exc}") from exc

    paths: list[str] = []
    for record in raw.split("\0"):
        if not record:
            continue
        fields = record.split("\t", 2)
        if len(fields) != 3:
            raise PatchError(f"could not read git's report of what the patch touches: {record!r}")
        paths.append(fields[2])
    return tuple(paths)


def apply_patch(patch: str, checkout: Path) -> None:
    """Apply the patch to the checkout, or raise. No fuzz, no three-way, no partial success."""
    try:
        _git(["apply", "--whitespace=nowarn", "-"], cwd=checkout, stdin=patch)
    except _GitFailed as exc:
        raise PatchError(f"the patch did not apply: {exc}") from exc


def touched_paths(checkout: Path) -> tuple[str, ...]:
    """Every path that differs from `base_commit` after the patch — git's own answer.

    The authoritative footprint, and the reason it exists alongside `declared_paths`: a patch
    that RENAMES an operator-held test away is reported by `--numstat` under its destination
    path only, so the pre-apply check does not see the source. Here the same rename shows up
    as a deletion and an untracked file, and both paths are returned. Untracked files are
    included for the same reason — a patch that creates a `conftest.py` has touched the tree
    whether or not git is tracking it yet.
    """
    raw = _git(["status", "--porcelain", "-z", "--untracked-files=all"], cwd=checkout)
    records = [record for record in raw.split("\0") if record]

    paths: list[str] = []
    pending = iter(records)
    for record in pending:
        # Porcelain v1 is fixed-width: two status columns, one space, then the path verbatim.
        # Splitting on the first space instead would take the status letter to be part of the
        # path for every record — and since ordinary modifications are reported as " M path",
        # every single path would come back wrong while still looking like a path.
        code, path = record[:2], record[3:]
        paths.append(path)
        # A staged rename or copy spends a second record on its source path. We never stage,
        # so this should not arise — it is handled because a footprint that silently dropped
        # half a rename is precisely the hole `declared_paths` already has.
        if code.strip()[:1] in {"R", "C"}:
            paths.append(next(pending, ""))
    return tuple(path for path in paths if path)


class _GitFailed(RuntimeError):
    """git itself said no. Private: callers see `CheckoutError` or `PatchError`."""


def _git(args: list[str], *, cwd: Path, stdin: str | None = None) -> str:
    """Run git with the machine's configuration switched off.

    `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_SYSTEM` are pointed at `/dev/null` so that a
    developer's `~/.gitconfig` or a system-wide one cannot change what gets verified — commit
    signing, a `hooksPath`, a clean/smudge filter, `apply.whitespace=fix` — each of which
    would make the reward depend on the machine it was computed on. `GIT_TERMINAL_PROMPT=0`
    so an unreachable remote fails instead of waiting for a password nobody is there to type.
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
        input=stdin,
        capture_output=True,
        text=True,
        env=environment,
        timeout=_GIT_TIMEOUT,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise _GitFailed(detail or f"git {args[0]} exited {completed.returncode}")
    return completed.stdout


__all__ = [
    "CheckoutError",
    "PatchError",
    "apply_patch",
    "declared_paths",
    "materialise",
    "touched_paths",
]
