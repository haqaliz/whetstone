"""The held set: which paths a minted task puts beyond the policy's reach, and why exactly those.

`test_blobs` is the whole boundary (`verify/task.py`): the paths a patch may not touch, and the
files STRICT restores from golden before pytest runs. This module decides that set for a mined
candidate, and it is wrong in two directions, neither of which is visible from a verdict.

**Too few is cheat 10.** A held test that depends on a `conftest.py` the manifest never declared
can be made to pass by rewriting that conftest — the patch touches no held path, the held tests
are restored unchanged, the declared tests run, and the reward is paid on a bug nobody fixed
(`tests/adversarial/test_cheats.py:426` observes STRICT PASS with every sub-verdict passing).
The floor below — every `conftest.py` from the repository root down to each held test's directory
— is PRD D4/M5's answer, and it is a **structural** one: no instrumentation, no import walk,
nothing to be talked out of.

**It narrows cheat 10. It does not close it, and this module is not where that gets claimed.**
Measured: ~22% of contig's mintable commits (49/224) also touch a non-`.py` file — a JSON
fixture, a golden output, a CSV — which no conftest rule and no import walk would ever see, and
which the gold patch legitimately carries. Cheat 10 therefore stays `BOTH_ACCEPT` in
`tests/adversarial/corpus.py` and must not be downgraded on the strength of this file.

**Too many is worse, and it is the direction that gets added by accident.** If a held path is one
the gold patch must change, `strict.py:180-183`'s restore writes the parent's bytes back over the
fix. The task becomes permanently unpassable and reports as an ordinary **FAIL** — not
UNVERIFIED, not a malformed-task complaint, nothing anywhere in the verdict pointing at the
manifest. So the intersection is checked and a candidate that violates it is **rejected at mint
time**, by name. A corpus is allowed to be smaller than it could have been; it is not allowed to
contain a task nobody can ever pass.

Git plumbing and set arithmetic. No model, no network, nothing executed.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from whetstone.tasks.donor import Candidate, run_git

#: The one filename the floor is about. pytest gives `conftest.py` its directory-scoped meaning;
#: no other filename in a repository is loaded implicitly by virtue of where it sits.
_CONFTEST = "conftest.py"


class HeldSetError(ValueError):
    """A candidate whose held set cannot be both correct and complete. Never minted."""


class OverDeclaration(HeldSetError):
    """A would-be-held path is one the gold patch changes. The restore would undo the fix."""


class UnderDeclaration(HeldSetError):
    """A declared held set is missing a `conftest.py` on the path to one of its own tests."""


def held_paths(donor: Path, candidate: Candidate) -> tuple[str, ...]:
    """Everything the minted task holds: the modified test files plus the conftest floor.

    Sorted, so a re-mint of the same candidate produces the same manifest bytes — a ledger keyed
    on a manifest hash is worth nothing if the hash moves with dictionary ordering.

    Raises `OverDeclaration` if the floor and the gold patch overlap. That is a refusal, not a
    repair: dropping the conflicting path from the held set would silently hand the policy a file
    a held test depends on, and dropping it from the gold patch would mint a task whose reference
    patch is not the commit. Both repairs trade a small corpus for a dishonest one.
    """
    floor = conftest_floor(donor, candidate)
    held = tuple(sorted({*candidate.held_tests, *floor}))

    gold = set(candidate.source_paths) | set(candidate.other_paths)
    overlap = sorted(gold.intersection(held))
    if overlap:
        raise OverDeclaration(
            f"commit {candidate.sha} ({candidate.subject!r}) would hold {overlap} and also "
            f"change them in its gold patch. STRICT's restore rewrites every held path from "
            f"golden AFTER the patch is applied, so the fix would be overwritten and the task "
            f"would be permanently unpassable — reported as an ordinary FAIL, with nothing in "
            f"the verdict pointing at the manifest. The candidate is refused rather than minted"
        )
    return held


def conftest_floor(donor: Path, candidate: Candidate) -> tuple[str, ...]:
    """Every `conftest.py` from the repository root down to each held test's directory.

    **Read at the parent**, because the parent is the tree STRICT checks out. A floor read at the
    child would hold a `conftest.py` the commit itself added — a path absent from the checkout,
    which `strict.py:151-160` answers UNVERIFIED for. That task could never be verified by
    anyone, and nothing about it would say so until it had been run.

    A path, not a glob: a `conftest.py` in a sibling directory cannot affect these tests, and
    holding it would forbid the policy a file the task has no relationship to while adding a blob
    the manifest carries for nothing.
    """
    tree = _tree(donor, candidate.parent)
    floor: set[str] = set()
    for test in candidate.held_tests:
        parts = PurePosixPath(test).parent.parts
        for depth in range(len(parts) + 1):
            path = "/".join((*parts[:depth], _CONFTEST))
            if path in tree:
                floor.add(path)
    return tuple(sorted(floor))


def check_held(declared: Sequence[str], *, donor: Path, candidate: Candidate) -> None:
    """Refuse a held set that omits a `conftest.py` on the path to one of its own tests.

    The ingestion-time gate for cheat 10, applied to a set someone already wrote down — a
    manifest under review, a hand-authored task — rather than to one this module just computed.
    It is a separate function precisely so that it can be pointed at a task `held_paths` did not
    produce, because that is where the omission actually happens.

    The message names the rule, not just the missing file. A task rejected for a reason nobody
    can identify gets "fixed" by declaring whatever silences it, and a defence that cannot be
    told apart from an unrelated error is not one anybody can rely on.
    """
    missing = sorted(set(conftest_floor(donor, candidate)) - set(declared))
    if missing:
        raise UnderDeclaration(
            f"the held set for commit {candidate.sha} omits {missing}, which sit on the path "
            f"from the repository root to {list(candidate.held_tests)}. pytest loads a "
            f"conftest by position, so a held test can depend on one without naming it — and a "
            f"patch that rewrites an undeclared conftest is refused by nothing and passes the "
            f"declared tests against fixtures it wrote itself. That is cheat 10, and this rule "
            f"(PRD M5, the conftest floor) is what refuses it here"
        )


def _tree(donor: Path, sha: str) -> frozenset[str]:
    """Every file path in the commit's tree. One git invocation, then set membership."""
    raw = run_git(["ls-tree", "-r", "-z", "--name-only", sha], cwd=Path(donor))
    return frozenset(path for path in raw.split("\0") if path)


__all__ = [
    "HeldSetError",
    "OverDeclaration",
    "UnderDeclaration",
    "check_held",
    "conftest_floor",
    "held_paths",
]
