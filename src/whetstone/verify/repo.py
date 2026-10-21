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

**The mirror is an explicit harness input.** `WHETSTONE_REPO_MIRRORS` is a JSON object mapping
a canonical URL to a local repository. Because a public task is processed last and a night can
outlive the network, a mapping lets an operator say "this URL is on this disk"; the task's
manifest keeps the canonical URL. It is an environment variable rather than git config on
purpose — `_git` nulls the machine's global and system config so no `insteadOf` or `hooksPath`
can change what gets verified, and the mirror must not reopen that door. A mapped path that is
missing, malformed or not a repository is a `CheckoutError` naming both, and the canonical URL
is *not* attempted: an offline run has to fail rather than quietly reach the network.

**A populated destination is reused, never replaced.** A clean work tree rooted exactly at the
destination and already at `base_commit` is returned untouched; a clean one at another commit is
detached onto `base_commit` when that object is present locally. A dirty tree, a populated
non-git directory, a destination nested inside another repository, or a base object that is not
there is refused by name. Deleting or cloning over an operator's checkout is exactly how a
pre-warmed workspace would be thrown away, so neither happens. A missing or empty destination
still clones, byte for byte as before.

**Hooks are neutralised on every git invocation.** A reused or operator-supplied checkout may
carry a repo-local hook, and `checkout` would run it here — outside the sandbox. `_git` passes
`-c core.hooksPath=/dev/null` so none can run, and `GIT_NO_LAZY_FETCH=1` so a partial clone
cannot silently fetch over the network.

Stdlib and a subprocess. No model, no network of our own.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from whetstone.verify.task import Task

#: Long enough for a large clone on a slow disk, short enough that a wedged git does not hang
#: a nightly loop forever. Distinct from the caller's pytest timeout: this is the operator's
#: own machinery, not the run being measured.
_GIT_TIMEOUT = 300.0

#: The explicit mirror mapping. An operator input to this harness, not machine configuration;
#: see the module docstring for why that distinction is load-bearing.
_MIRRORS_ENV = "WHETSTONE_REPO_MIRRORS"


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
    """Make `destination` a clean checkout of `task.base_commit`, from a mirror if mapped.

    Detached on purpose: `base_commit` is a commit, and resolving it through a branch name
    would let the default branch decide what got verified.

    A populated destination is reused (see `_reuse`) rather than deleted or cloned over; only a
    missing or empty one is cloned into, and then from `_clone_source` rather than blindly from
    the canonical URL.
    """
    destination = Path(destination)
    if destination.is_dir() and any(destination.iterdir()):
        _reuse(task, destination)
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        _git(
            [
                "clone",
                "--quiet",
                "--no-checkout",
                "--no-hardlinks",
                _clone_source(task.repo_url),
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


def _clone_source(repo_url: str) -> str:
    """The local path `repo_url` is mirrored to, or `repo_url` itself when there is no mapping.

    A mapping exists to make a run offline, so a broken one is a refusal, never a fallback: the
    canonical URL is not returned once an entry for it has been seen.
    """
    raw = os.environ.get(_MIRRORS_ENV, "").strip()
    if not raw:
        return repo_url
    try:
        mapping = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CheckoutError(
            f"{_MIRRORS_ENV} is not valid JSON ({exc}); refusing to clone {repo_url!r} without "
            "knowing whether a mirror was meant"
        ) from exc
    if not isinstance(mapping, dict):
        raise CheckoutError(
            f"{_MIRRORS_ENV} is a JSON {type(mapping).__name__}, not an object of "
            f"URL -> local path; refusing to clone {repo_url!r}"
        )
    if repo_url not in mapping:
        return repo_url

    mirror = mapping[repo_url]
    if not isinstance(mirror, str) or not mirror.strip():
        raise CheckoutError(
            f"{_MIRRORS_ENV} maps {repo_url!r} to {mirror!r}, which is not a local path"
        )
    path = Path(mirror)
    if not path.is_dir() or not (
        (path / ".git").exists() or ((path / "HEAD").is_file() and (path / "objects").is_dir())
    ):
        raise CheckoutError(
            f"{_MIRRORS_ENV} maps {repo_url!r} to {mirror!r}, which is not a git repository; "
            "refusing to clone the canonical URL instead"
        )
    return str(path)


def _reuse(task: Task, destination: Path) -> None:
    """Reuse a populated checkout, or refuse by name. Never deletes, never clones over."""
    try:
        top_level = _git(["rev-parse", "--show-toplevel"], cwd=destination).strip()
    except _GitFailed as exc:
        raise CheckoutError(
            f"{destination} is not a git work tree, so it cannot be reused for "
            f"{task.repo_url!r}: {exc}"
        ) from exc
    if Path(top_level).resolve() != destination.resolve():
        raise CheckoutError(
            f"{destination} is not the root of a git work tree (it belongs to {top_level!r}), "
            f"so it cannot be reused for {task.repo_url!r}"
        )
    try:
        head = _git(["rev-parse", "HEAD"], cwd=destination).strip()
    except _GitFailed as exc:
        raise CheckoutError(
            f"the checkout at {destination} has no HEAD, so it cannot be reused for "
            f"{task.base_commit!r}: {exc}"
        ) from exc
    try:
        dirty = _git(["status", "--porcelain", "--untracked-files=all"], cwd=destination)
    except _GitFailed as exc:
        raise CheckoutError(f"could not read the status of {destination}: {exc}") from exc
    if dirty.strip():
        raise CheckoutError(
            f"the checkout at {destination} is not clean, so it cannot be reused for "
            f"{task.base_commit!r}; refusing to discard or clone over local changes"
        )
    if head == task.base_commit:
        return
    try:
        _git(["cat-file", "-e", f"{task.base_commit}^{{commit}}"], cwd=destination)
    except _GitFailed as exc:
        raise CheckoutError(
            f"the checkout at {destination} is at {head!r}, not {task.base_commit!r}, and "
            f"{task.base_commit!r} is not in it: {exc}"
        ) from exc
    try:
        _git(["checkout", "--quiet", "--detach", task.base_commit], cwd=destination)
    except _GitFailed as exc:
        raise CheckoutError(
            f"could not check out {task.base_commit!r} in the existing checkout at "
            f"{destination}: {exc}"
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

    `core.hooksPath=/dev/null` is not redundant with that: it covers a *repo-local* hook in a
    reused or operator-supplied checkout, which `checkout` would otherwise run here, outside
    the sandbox. `GIT_NO_LAZY_FETCH=1` keeps a partial clone from reaching the network to fill
    in an object the verifier asked for.
    """
    environment = dict(os.environ)
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_NO_LAZY_FETCH": "1",
        }
    )
    completed = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *args],
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
