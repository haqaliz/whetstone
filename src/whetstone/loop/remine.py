"""The incremental re-mine: grow the corpus the night will draw from, before it draws.

The night reads a frozen corpus (`whetstone.loop.night`). This module is the block that lets it
grow that corpus first, from the user's own new commits, without ever touching the pre-registered
held-out split. It is deliberately small, because the honesty it protects lives elsewhere:

* **Incremental (M1).** Each donor is mined with a `skip`-set of the trailing-12-hex shas already
  in the corpus (`mine(skip=...)`), so a commit already minted is never re-provisioned. The set
  accumulates across donors and onto `existing`, so a second donor in the same night cannot
  re-mint a commit the first one did.
* **A separate training-only root (M2).** Every `mine()` call writes manifests into the
  operator-named `out` and takes a **sibling** evidence root
  (`out.parent/(out.name + "-evidence")`) as its `tasks_root`, so `mine()`'s `local-ledger.json`
  and `recipes/<label>.json` land there — never inside `out` (which the night loads, and whose
  strict loader refuses any non-manifest entry) and never beside the committed
  `tasks/local-ledger.json` / `tasks/recipes/`.
* **Nothing-new, absent, or unprovisionable is a no-op (M4, M7).** A donor that mints nothing —
  because it has no un-minted candidates, because it is absent or not a repository (`MintFailed`),
  because its path does not exist (`FileNotFoundError`, an `OSError` from `subprocess(cwd=...)`),
  or because it is unprovisionable (`NotProvisionable`) — is recorded as a `DonorOutcome` with an
  `absent` reason and the loop continues. A re-mine never raises; the night proceeds on the
  corpus it already has.
* **Offline.** `mine()` reads the donor's local history and provisions from its own lock with
  `--offline`; nothing here reaches the network.

The held-out invariant is a consequence of the skip-set, not a second check: `existing` is the
sha12 set of the loaded `--tasks` corpus, and the night's held-out exclusion requires every
membership id to resolve in that same corpus — so every held-out member's sha12 is already in
`skip` before the first candidate is considered, and no re-mine can reintroduce one.
"""

from __future__ import annotations

import re
from collections.abc import Sequence, Set
from dataclasses import dataclass
from pathlib import Path

from whetstone.tasks.environment import NotProvisionable
from whetstone.tasks.ledger import Clock, utc_now
from whetstone.tasks.mine import MintFailed, MintReport, mine
from whetstone.verify.task import Task

#: The trailing-12-hex suffix a mined task id carries (`label-sha12`, `mine._ID_SHA_LENGTH`).
#: Matched at the **end** of the id so a synthetic harness id (`t-11`, `alpha`) is answered by
#: its whole self rather than refused — the loop's fixture ids are not shas, and a raising helper
#: would make every injected-miner test unusable.
_SHA12 = re.compile(r"[0-9a-f]{12}$")


def trailing_sha(task_id: str) -> str:
    """The sha12 a task id is keyed by, or the whole id when it carries no sha12 suffix.

    Tolerant by design (spec Open questions): the real corpus ids end in the candidate's commit
    sha, but the synthetic harness corpus (`tests/loop/harness.py`) uses readable ids, and the
    skip-set must still be computable over them without raising.
    """
    found = _SHA12.search(task_id)
    return found.group(0) if found else task_id


def corpus_shas(tasks: Sequence[Task]) -> frozenset[str]:
    """The sha12 set of a loaded corpus — the `existing` set a re-mine is incremental against."""
    return frozenset(trailing_sha(task.task_id) for task in tasks)


@dataclass(frozen=True)
class DonorOutcome:
    """What one donor contributed, or why it contributed nothing.

    `absent` is empty when the donor was read; otherwise it is the reason it was not (a
    `MintFailed` or `NotProvisionable` message). This is the per-donor record the night can print
    without re-reading any manifest.
    """

    label: str
    donor: Path
    minted: tuple[str, ...]
    rejected: tuple[tuple[str, str], ...]
    absent: str = ""


@dataclass(frozen=True)
class RemineReport:
    """The re-mine's result: the `(task_id, donor)` pairs the ledger records, and per-donor detail.

    `minted` is sorted by `task_id`, because the miner's iteration order is the donor's commit
    order and a consumer that serialized minting order would produce different bytes for the same
    delta.
    """

    minted: tuple[tuple[str, str], ...]
    donors: tuple[DonorOutcome, ...]


def remine(
    donors: Sequence[tuple[str, Path]],
    *,
    out: Path,
    limit: int,
    scratch: Path,
    timeout: float,
    existing: Set[str],
    seed: int | None = None,
    clock: Clock = utc_now,
) -> RemineReport:
    """Mine each `(label, donor)` into `out`, skipping commits already in the corpus.

    One `mine()` call per donor. `out` is the manifest destination the night loads; the miner's
    `tasks_root` is the sibling evidence root `out.parent/(out.name + "-evidence")`, so the
    re-mine's ledger and recipes never enter the loaded root. The accumulated skip-set is
    `existing` plus every sha12 minted earlier in this call. An absent, nonexistent, or
    unprovisionable donor is a recorded no-op, never an exception.
    """
    destination = Path(out)
    # The miner writes its own evidence (`local-ledger.json`, `recipes/`) into `tasks_root`, and
    # the night's strict loader refuses **any** non-manifest entry in a root it loads
    # (`manifest.load_task_directory`). So the evidence goes to a sibling of `out`, never into
    # `out` — and never `out.parent` alone, which for a `tasks/local/<name>` root is where the
    # committed `tasks/local-ledger.json` / `tasks/recipes/` live. Derived in one place, here.
    evidence = destination.parent / f"{destination.name}-evidence"
    scratch_root = Path(scratch)
    accumulated: set[str] = set(existing)
    pairs: list[tuple[str, str]] = []
    outcomes: list[DonorOutcome] = []
    for label, donor in donors:
        donor_path = Path(donor)
        try:
            report: MintReport = mine(
                donor_path,
                destination,
                label=label,
                limit=limit,
                scratch=scratch_root / label,
                tasks_root=evidence,
                timeout=timeout,
                seed=seed,
                clock=clock,
                skip=frozenset(accumulated),
            )
        except (MintFailed, NotProvisionable, OSError) as exc:
            outcomes.append(DonorOutcome(label, donor_path, (), (), str(exc)))
            continue
        minted = tuple(one.task_id for one in report.minted)
        accumulated.update(trailing_sha(task_id) for task_id in minted)
        pairs.extend((task_id, label) for task_id in minted)
        outcomes.append(
            DonorOutcome(
                label,
                donor_path,
                minted,
                tuple((one.sha, one.reason) for one in report.rejected),
                "",
            )
        )
    return RemineReport(
        minted=tuple(sorted(pairs, key=lambda pair: pair[0])), donors=tuple(outcomes)
    )


__all__ = [
    "DonorOutcome",
    "RemineReport",
    "corpus_shas",
    "remine",
    "trailing_sha",
]
