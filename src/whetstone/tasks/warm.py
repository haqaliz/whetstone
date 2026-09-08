"""Warming this machine's uv cache, so the first mine on it is not a wall of refusals.

**The precondition this exists to satisfy.** `tasks/environment.py` provisions every task
environment with `--offline`, and argues for it well: a donor whose wheels cannot be answered
from uv's own cache or a `--find-links` directory fails **loudly**, naming the command, rather
than a mint quietly resolving against whatever an index served at 3am and pinning what came
back. Nothing here weakens that. This module is the other half of it — the one step that is
*supposed* to reach the network, run once per machine, before any mining starts.

Without it the design fails in the direction it was built to fail in, but wholesale and with a
misleading message: on a second machine with a cold cache, every one of 45 candidates was
rejected with "Network connectivity is disabled, but the requested data wasn't found in the
cache", which reads as a fault in the tooling rather than as a precondition nobody had met.

**Per distinct lockfile, never per commit.** A donor's history is mostly commits that do not
move dependencies. Measured on the two donors this was written for: 664 commits carried **36**
distinct locks, and a second donor's history carried **6**. Warming per commit would do an order
of magnitude more work for a byte-identical cache, and it is slow enough that an operator would
reasonably skip it — which is how a documented precondition becomes an undocumented one again.

**Newest first.** The representative of each lock is the newest commit carrying it, and the walk
runs newest to oldest. A warm is the slow part of bringing a machine up and it will sometimes be
interrupted; ordering it this way means an interrupted run has warmed the locks a mine is most
likely to draw from rather than a random half.

**A failure does not stop the walk.** One donor commit whose resolution can no longer be answered
by any index — a yanked release, a repository that moved — must not cost the operator the other
thirty-five. The failures are named in the report instead, because a count an operator cannot act
on is not a report.

**This module reaches the network and nothing that computes a reward may call it.** It lives
under `whetstone.tasks` and is therefore inside the guarded roots
(`tests/test_no_inference_on_reward_path.py`): it may not import an inference library, and it
does not import one. It is an operator command, invoked before mining, never during it.
"""

from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from whetstone.tasks.donor import GitFailed, run_git, run_git_bytes

#: The donor files a warm needs, and the only two it reads. The lock is the resolution the donor
#: recorded; the manifest is what `uv sync --frozen` checks it against.
LOCKFILE = "uv.lock"
PROJECT_FILE = "pyproject.toml"

#: How many hex characters of the lock's digest name its directory. Long enough that a collision
#: across a donor's few dozen locks is not a thing that happens, short enough to read in a log.
DIGEST_LENGTH = 16

#: The sync that does the warming. **`--offline` is deliberately absent**, and that is the whole
#: point of this module: `tasks/environment.py` puts it on every command it runs, and copying it
#: here would produce a warm that exits 0 having filled the cache with nothing — after which the
#: next mine fails exactly as before, with the remedy apparently already applied.
#:
#: `--frozen` because the lock is the donor's own recorded resolution and re-resolving would warm
#: a resolution the donor never had. `--no-install-project` because a task environment needs the
#: donor's *dependencies*, never the donor's own package — the same reason `environment.py`
#: declines to install it.
UV_SYNC: tuple[str, ...] = ("sync", "--frozen", "--no-install-project")

#: How long one lock's sync may take. Generous: a cold cache on a slow link is the condition this
#: command exists for, and a timeout tuned to a fast one would fail the machines that need it.
SYNC_TIMEOUT = 1800.0

#: Answers "did this project directory sync?". Injected so the decision — which locks, in what
#: order, with which flags — is testable without an index, minutes of wall clock, and someone's
#: wifi deciding whether the suite is green.
Runner = Callable[[Path], bool]


@dataclass(frozen=True)
class LockedCommit:
    """A commit that carries a lockfile, and the digest that made it a representative.

    The digest is part of the record rather than an implementation detail of the dedupe: it is
    what turned 664 commits into 36, and an operator who cannot see it cannot check that claim.
    """

    #: The newest commit carrying this lock.
    sha: str

    #: `DIGEST_LENGTH` hex characters of the lockfile's SHA-256, over its bytes.
    digest: str


@dataclass(frozen=True)
class WarmReport:
    """What one donor's warm did. Counts locks, never commits."""

    #: The donor that was walked.
    donor: Path

    #: Distinct lockfiles found across its whole history.
    unique: int

    #: How many of them synced.
    warmed: int

    #: The ones that did not, named so the operator can act on them.
    failed: tuple[LockedCommit, ...]

    @property
    def complete(self) -> bool:
        """Every distinct lock warmed. The exit status, and not a judgement about the donor."""
        return not self.failed


def unique_locks(donor: Path) -> tuple[LockedCommit, ...]:
    """One commit per distinct `uv.lock` across the donor's history, newest first.

    Hashes the lockfile's **bytes** and never parses it: a warm does not need to understand a
    lock, and a parser here would be a second opinion about uv's format that could disagree with
    uv's own.

    Commits with no lockfile are skipped rather than failing the walk. Every real donor has a
    prehistory that predates its own lock, and refusing the whole warm over it would make this
    useless on exactly the repositories it was written for.
    """
    donor = Path(donor)
    # Every revision, not `git log -- uv.lock`. The path-filtered form would list only the
    # commits that touched the lock — which is where every distinct content is introduced, so
    # it looks equivalent and is roughly twenty times fewer subprocesses. It is not equivalent:
    # git simplifies history when a path is given, and on a repository with merges it can omit
    # the side of a merge where a lock briefly differed. The walk is seconds against a warm that
    # takes minutes to hours, so the obviously-correct form wins; do not "optimise" this into
    # the filtered one without an argument about history simplification.
    revisions = run_git(["rev-list", "HEAD"], cwd=donor).split()

    seen: set[str] = set()
    found: list[LockedCommit] = []
    for sha in revisions:
        try:
            raw = run_git_bytes(["show", f"{sha}:{LOCKFILE}"], cwd=donor)
        except GitFailed:
            continue
        digest = hashlib.sha256(raw).hexdigest()[:DIGEST_LENGTH]
        if digest in seen:
            continue
        seen.add(digest)
        found.append(LockedCommit(sha=sha, digest=digest))
    return tuple(found)


def materialise(donor: Path, commit: LockedCommit, work: Path) -> Path:
    """Write that commit's lock and manifest into `work/<digest>/`, and return the directory.

    Both files are read from the **same** tree. A lock from one commit beside a manifest from
    another is a state the donor was never in, and `uv sync --frozen` would either refuse it or,
    worse, warm a resolution that never existed. Keyed on the digest rather than the sha so two
    commits sharing a lock cannot produce two directories.
    """
    destination = Path(work) / commit.digest
    destination.mkdir(parents=True, exist_ok=True)
    for name in (LOCKFILE, PROJECT_FILE):
        (destination / name).write_bytes(run_git_bytes(["show", f"{commit.sha}:{name}"], cwd=donor))
    return destination


def warm(donor: Path, *, work: Path, run: Runner | None = None) -> WarmReport:
    """Sync every distinct lock in the donor's history once, and report what did not.

    The walk continues past a failure on purpose — see the module docstring. The report names the
    locks that failed rather than only counting them.
    """
    donor = Path(donor)
    chosen = _uv_sync if run is None else run

    locks = unique_locks(donor)
    failed: list[LockedCommit] = []
    for commit in locks:
        project = materialise(donor, commit, work)
        if not chosen(project):
            failed.append(commit)
    return WarmReport(
        donor=donor,
        unique=len(locks),
        warmed=len(locks) - len(failed),
        failed=tuple(failed),
    )


def _uv_sync(project: Path) -> bool:
    """The real runner: `uv sync --frozen --no-install-project` against one materialised lock.

    Returns a bool rather than raising because the caller's contract is to continue past a
    failure, and an exception per unresolvable lock would make that the caller's problem to
    unpick. What went wrong is uv's stderr, which the operator sees on the command's own output.
    """
    completed = subprocess.run(
        ["uv", *UV_SYNC, "--project", str(project)],
        capture_output=True,
        text=True,
        timeout=SYNC_TIMEOUT,
        check=False,
    )
    return completed.returncode == 0


__all__ = [
    "DIGEST_LENGTH",
    "LOCKFILE",
    "PROJECT_FILE",
    "SYNC_TIMEOUT",
    "UV_SYNC",
    "LockedCommit",
    "Runner",
    "WarmReport",
    "materialise",
    "unique_locks",
    "warm",
]
