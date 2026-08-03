"""Turning a local repository into a corpus: select, provision, derive, prove, record.

This is the source-B pipeline end to end, and every step it composes was built to refuse
something:

1. `donor.candidates` finds commits that turned an existing test green — history only, offline.
2. `held.held_paths` decides what the task holds, and **rejects** a candidate whose gold patch
   touches a held path (the restore would overwrite the fix, and the task would be permanently
   unpassable while reporting an ordinary FAIL).
3. `environment.capture` provisions the donor's DEPENDENCIES from its own lock — never the donor's
   own project — records exact `==` pins and reads where its code lives, or **rejects** the donor
   by name.
4. `derive.derive` runs the tests red, green, and green again, and **discards** any id whose
   outcome is not reproducible.
5. `liveness.prove_live` runs the shipped reward twice and **discards** the task unless it fails
   with no patch and passes with its own — the vacuous-task control.
6. `ledger` commits the evidence, never the data.

**A rejection is a finding, not an error.** Every one is recorded and the mint continues, because
a corpus that stops at the first awkward commit is a corpus whose size was decided by history's
ordering. What is never allowed is the opposite: a task entering the corpus without having been
proved live. So a manifest is written to a scratch directory first, proved there, and only then
copied into `--out` — the corpus directory never holds an unproven task, not even transiently,
which matters because `load_tasks` deliberately refuses to skip anything it finds.

**Selection is deterministic under a seed.** The pool is sorted by sha before anything shuffles
it, so the draw depends on the seed and on nothing else — not on `iterdir`, not on a set's
ordering, not on how many candidates a donor happened to grow since. Two mints at the same seed
produce the same tasks, byte for byte.

**Nothing here reaches the network.** git reads a local repository, uv provisions from a local
lock with `--offline`, and every test runs inside the Seatbelt sandbox, which denies the network
outright. No model is consulted anywhere: what a task declares is decided by what pytest did.
"""

from __future__ import annotations

import base64
import json
import random
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from whetstone import __version__
from whetstone.tasks.derive import PASS_TO_PASS_SCOPE, Derived, NotDerivable, derive, gold_patch
from whetstone.tasks.donor import Candidate, GitFailed, candidates, run_git, run_git_bytes
from whetstone.tasks.environment import Captured, NotProvisionable, capture
from whetstone.tasks.held import HeldSetError, held_paths
from whetstone.tasks.ledger import (
    Clock,
    LedgerEntry,
    Recipe,
    read_ledger,
    record,
    tool_versions,
    utc_now,
    write_ledger,
    write_recipe,
)
from whetstone.tasks.liveness import Liveness, NotLive, prove_live
from whetstone.verify.task import load_task

#: How a mined task is named: the donor's directory name and the short sha of the commit it came
#: from. Both halves are needed — a sha alone says nothing about where to look for it, and a
#: donor name alone is not unique. Neither half is any of the user's code.
#:
#: **This half is local-only, and the recipe's `label` is the committed half.** A task id is
#: written into manifests under `tasks/local/`, which is gitignored; the donor's directory name
#: is the user's own private repository name and must not reach a committed file. The recipe
#: carries an operator-chosen `label` instead — see `_write_recipe`.
_ID_SHA_LENGTH = 12

#: Where the committed evidence lives, relative to the tasks root. Named here because the miner
#: writes them and `tasks/README.md` documents them, and a second spelling would let those two
#: drift apart silently.
LEDGER_NAME = "local-ledger.json"
RECIPES_DIRECTORY = "recipes"

#: The selection rule, recorded verbatim in the recipe. A reader re-deriving the corpus needs to
#: know what was filtered out, and a filter described only in prose is one nobody can reproduce.
SELECTION_FILTERS = (
    "single-parent commits reachable from HEAD; at least one existing test .py modified "
    "(status M); at least one non-test .py touched"
)


class MintFailed(ValueError):
    """The mint could not start: the donor is not a repository, or the output path is unusable.

    Distinct from a rejected candidate, which is a finding about a commit. This is "you pointed
    me at the wrong thing", and the two have different remedies.
    """


@dataclass(frozen=True)
class Minted:
    """One task that was proved live and written into the corpus."""

    task_id: str
    manifest: Path
    liveness: Liveness
    python: str


@dataclass(frozen=True)
class Rejected:
    """One candidate that did not become a task, and why. Printed, never committed.

    The reason quotes the donor's own commit subjects and file paths, which is the user's
    information: it goes to the operator's terminal and never into the ledger or the recipe.
    """

    sha: str
    reason: str


@dataclass(frozen=True)
class MintReport:
    """What one mint produced, including what it refused.

    `rejected` is carried rather than dropped so the shortfall is reportable: a mint asked for
    twenty tasks and returning eleven is a fact about the donor, and rounding it up to the target
    is the one thing this project may never do.
    """

    minted: tuple[Minted, ...]
    rejected: tuple[Rejected, ...]
    ledger: Path | None
    recipe: Path | None


def select(pool: Sequence[Candidate], *, limit: int, seed: int | None = None) -> list[Candidate]:
    """The candidates a mint will attempt, in the order it will attempt them.

    **Sorted by sha before anything shuffles**, because `candidates` returns history order and a
    shuffle seeded off an unsorted sequence is only as reproducible as the sequence. With the
    sort in front, the same seed against the same history draws the same commits on any machine.

    `seed is None` means "the oldest first" — also deterministic, and the right default for an
    operator who wants their earliest history mined rather than a sample of it.

    More candidates than `limit` are returned on purpose: a candidate can be rejected at any of
    four later gates, and a selection that handed back exactly `limit` would silently mint fewer
    than asked for whenever any of them fired.
    """
    ordered = sorted(pool, key=lambda candidate: candidate.sha)
    if seed is not None:
        random.Random(seed).shuffle(ordered)
    return ordered


def mine(
    donor: Path,
    out: Path,
    *,
    label: str,
    limit: int,
    scratch: Path,
    tasks_root: Path,
    timeout: float,
    seed: int | None = None,
    clock: Clock = utc_now,
) -> MintReport:
    """Mine up to `limit` proven-live tasks out of `donor`, writing manifests into `out`.

    `timeout` has no default, matching every other step that executes something: a limit
    inherited from somewhere else turns a slow donor into a discard nobody can explain.

    `label` has no default for a different reason: it is the donor's name in every **committed**
    file, and the only default available is the donor's own directory name — which is the user's
    private repository name. A default here would leak it by being convenient, and a leak into a
    committed file is not undone by deleting the line later. The operator chooses a
    non-identifying label and the recipe records that.

    Raises `MintFailed` if the donor cannot be read at all. A candidate that cannot be minted is
    recorded in the report and the mint moves on.
    """
    location = Path(donor).resolve()
    destination = Path(out)
    workspace = Path(scratch).resolve()

    try:
        pool = candidates(location)
        head = run_git(["rev-parse", "HEAD"], cwd=location).strip()
    except GitFailed as exc:
        raise MintFailed(
            f"donor {str(location)!r} could not be read as a git repository: {exc}"
        ) from exc

    destination.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)

    minted: list[Minted] = []
    rejected: list[Rejected] = []
    for candidate in select(pool, limit=limit, seed=seed):
        if len(minted) == limit:
            break
        try:
            minted.append(
                _mint(
                    location,
                    candidate,
                    destination,
                    scratch=workspace / candidate.sha[:_ID_SHA_LENGTH],
                    timeout=timeout,
                    clock=clock,
                )
            )
        # Exactly the five gates, named. A bare `ValueError` here would also swallow
        # `load_task` refusing a manifest this module just wrote — which is not a finding about
        # the commit but a bug in the miner, and it should stop the mint rather than appear as
        # one more rejected candidate among many.
        except (HeldSetError, NotProvisionable, NotDerivable, NotLive, GitFailed) as exc:
            rejected.append(Rejected(sha=candidate.sha, reason=str(exc)))

    if not minted:
        return MintReport(minted=(), rejected=tuple(rejected), ledger=None, recipe=None)

    ledger = _write_ledger(Path(tasks_root), minted, clock=clock)
    recipe = _write_recipe(
        Path(tasks_root),
        label,
        head=head,
        limit=limit,
        seed=seed,
        python=minted[0].python,
        clock=clock,
    )
    return MintReport(
        minted=tuple(minted), rejected=tuple(rejected), ledger=ledger, recipe=recipe
    )


def _mint(
    donor: Path,
    candidate: Candidate,
    out: Path,
    *,
    scratch: Path,
    timeout: float,
    clock: Clock,
) -> Minted:
    """One candidate, all the way through, or an exception naming the gate that refused it.

    The order is chosen so the cheapest refusal comes first: the held set is git plumbing, the
    environment is a provisioning step, and only then is anything executed. A candidate that
    would mint an unpassable task costs one `ls-tree` rather than five pytest runs.

    **One checkout, provisioned and derived in place.** This used to be two — one to provision
    against, one to run the derivation in — and the pair is how the reward came to be decided by
    a tree that was not the one under test: `uv sync` installed the donor's project editable at
    the *provisioning* checkout, so the derivation, and later every verification, imported that
    directory instead of its own. The install is gone (`environment.capture` passes
    `--no-install-project`) and so is the second directory, because the cheapest way to keep two
    checkouts from being confused is to have one.

    The venv is deliberately a sibling of the work tree rather than inside it: the derivation
    grants its sandbox write access to the whole workspace, and an environment the tests under
    derivation could rewrite is an environment nothing can be concluded from.
    """
    held = held_paths(donor, candidate)

    workspace = scratch / "work"
    workspace.mkdir(parents=True, exist_ok=True)
    checkout = workspace / "repo"
    run_git(
        ["clone", "--quiet", "--no-checkout", "--no-hardlinks", str(donor), str(checkout)],
        cwd=workspace,
    )
    run_git(["checkout", "--quiet", "--detach", candidate.parent], cwd=checkout)
    captured = capture(checkout, venv=scratch / "venv")

    derived = derive(
        donor,
        candidate,
        scratch=workspace,
        checkout=checkout,
        timeout=timeout,
        interpreter=captured.interpreter,
        import_roots=captured.import_roots,
    )

    # Written to scratch and proved there. Only a task that has passed liveness is copied into
    # the corpus, because `load_tasks` refuses to skip anything it finds — an unproven manifest
    # sitting in the corpus directory would be verified as though somebody had vouched for it.
    task_id = f"{donor.name}-{candidate.sha[:_ID_SHA_LENGTH]}"
    staged = scratch / f"{task_id}.json"
    staged.write_text(
        json.dumps(
            manifest_for(
                donor,
                candidate,
                derived,
                captured,
                held=held,
                task_id=task_id,
                minted_at=clock(),
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    task = load_task(staged)
    liveness = prove_live(
        task,
        gold_patch(donor, candidate),
        sandbox_root=scratch / "liveness",
        timeout=timeout,
        interpreter=captured.interpreter,
    )

    manifest = out / staged.name
    shutil.copyfile(staged, manifest)
    return Minted(
        task_id=task_id, manifest=manifest, liveness=liveness, python=captured.python
    )


def manifest_for(
    donor: Path,
    candidate: Candidate,
    derived: Derived,
    captured: Captured,
    *,
    held: Sequence[str],
    task_id: str,
    minted_at: str,
) -> dict[str, object]:
    """The manifest for one candidate, in the shape `load_task` accepts.

    **Which commit each blob is read at is the load-bearing detail.** A held *test* file is read
    at the child, because the child's tests are the ones that must go green and STRICT's restore
    is what applies them (the overlay *is* the test patch, PRD § 5.4). Everything else in the held
    set — the `conftest.py` floor — is read at the **parent**, which is the tree STRICT checks
    out; a conftest read at the child could be one the commit itself added, and a held path absent
    from the checkout is answered UNVERIFIED forever.

    `provenance` records what the corpus is about and what was thrown away getting here: the
    `pass_to_pass_scope` decision (D-A) and any id discarded as non-reproducible. Both are
    records — nothing in the reward reads them — and both are things a reader would otherwise
    have to assume.
    """
    tests = set(candidate.held_tests)
    blobs = {
        path: run_git_bytes(
            ["cat-file", "blob", f"{candidate.sha if path in tests else candidate.parent}:{path}"],
            cwd=donor,
        )
        for path in held
    }
    provenance = {
        "donor": donor.name,
        "commit": candidate.sha,
        "parent": candidate.parent,
        "pass_to_pass_scope": PASS_TO_PASS_SCOPE,
        "minted_at": minted_at,
        "miner": f"whetstone {__version__}",
    }
    if derived.discarded:
        provenance["discarded_as_flaky"] = ", ".join(derived.discarded)
    if captured.local:
        provenance["path_installs"] = ", ".join(captured.local)

    return {
        "task_id": task_id,
        "source": "private",
        "repo_url": str(donor),
        "base_commit": candidate.parent,
        "environment": {
            "python": captured.python,
            "pins": list(captured.pins),
            "import_roots": list(captured.import_roots),
        },
        "problem_statement": candidate.subject,
        "fail_to_pass": list(derived.fail_to_pass),
        "pass_to_pass": list(derived.pass_to_pass),
        "test_blobs": {
            path: base64.b64encode(contents).decode("ascii") for path, contents in blobs.items()
        },
        "provenance": provenance,
    }


def _write_ledger(tasks_root: Path, minted: Sequence[Minted], *, clock: Clock) -> Path:
    """Merge this mint's entries into the committed ledger, keyed by task id.

    Merged rather than overwritten because a corpus is mined donor by donor, and a ledger rewritten
    from one donor's run would delete the evidence for every other. A re-mint of the same task id
    replaces its entry — the newer proof is the one that describes the manifest now on disk.
    """
    path = Path(tasks_root) / LEDGER_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = read_ledger(path) if path.is_file() else ()
    tools = tool_versions()
    fresh: dict[str, LedgerEntry] = {entry.task_id: entry for entry in existing}
    for task in minted:
        fresh[task.task_id] = record(
            task.manifest, task.liveness, python=task.python, tools=tools, clock=clock
        )
    write_ledger(path, tuple(fresh.values()))
    return path


def _write_recipe(
    tasks_root: Path,
    label: str,
    *,
    head: str,
    limit: int,
    seed: int | None,
    python: str,
    clock: Clock,
) -> Path:
    """Write the donor's recipe — how this corpus was derived, never what it contains.

    **The recipe is committed, so it is named and filled by `label` rather than by the donor.**
    An earlier version wrote the donor's resolved path here, which put an absolute path from the
    author's machine — and the private repository's name — into a file the repository publishes.
    Neither is usable by an outside reader re-deriving the corpus, who supplies their own donor:
    what they need is the procedure, which is everything else in this document.
    """
    path = Path(tasks_root) / RECIPES_DIRECTORY / f"{label}.json"
    selection: Mapping[str, str] = {
        "filters": SELECTION_FILTERS,
        "limit": str(limit),
        "seed": "none" if seed is None else str(seed),
    }
    write_recipe(
        path,
        Recipe(
            donor=label,
            donor_head=head,
            selection=selection,
            pass_to_pass_scope=PASS_TO_PASS_SCOPE,
            tools=tool_versions(),
            python=python,
            mined_at=clock(),
        ),
    )
    return path


__all__ = [
    "LEDGER_NAME",
    "RECIPES_DIRECTORY",
    "SELECTION_FILTERS",
    "MintFailed",
    "MintReport",
    "Minted",
    "Rejected",
    "manifest_for",
    "mine",
    "select",
]
