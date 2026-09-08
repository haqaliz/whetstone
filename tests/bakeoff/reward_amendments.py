"""The one way the reward path is allowed to move, and the shape that permission has to take.

Three guards freeze `src/whetstone/verify/` byte-identical against `origin/master`, because a
branch that publishes counts must not also change the thing those counts were graded against —
a modified verifier means the measurement and the measured drift apart, and *nothing in the
output would look wrong while it happened*. That reasoning is sound and this module does not
weaken it.

What it changes is the answer to "then how does the verifier ever improve". Before this, the
answer was "it does not": the freeze was unconditional and undocumented, so making the reward
cross-platform — or fixing a defect in it — was impossible on any branch. A protection with no
legitimate path through it does not get respected, it gets deleted by whoever needs to move
next, and then nothing is protected.

So the freeze holds by default and a **declared amendment** is the only way past it. Each names
the exact files, the date, and a reason long enough to have required thought. The point is not
that the file makes changing the reward easy — it is that it makes changing the reward
**impossible to do quietly**. An amendment is a committed artefact, reviewed in the diff that
carries it, and permanent.

The comparison is deliberately not "is this file in a list": a diff touching a file no amendment
names fails, an amendment naming a file the diff does not touch is stale and fails too. Both
directions matter, because a permission left lying around after the change it authorised is a
permission nobody is reading any more.
"""

from __future__ import annotations

import json
from pathlib import Path

#: Where the declarations live. Repo root rather than `docs/`, because this is a machine-read
#: control and not prose about one.
AMENDMENTS_FILE = "reward-path-amendments.json"

#: The document's declared shape, checked before anything is read out of it — a defaulted
#: amendment list would permit everything while succeeding, which is the failure mode every
#: fail-closed reader in this repository exists to refuse.
AMENDMENT_SCHEMA = "whetstone-reward-amendment/1"

#: How much reason an amendment must carry. A word count rather than a non-empty check: "fix" is
#: non-empty and explains nothing, and the point of the file is that the reasoning survives to
#: whoever reads the diff in six months.
MINIMUM_REASON_WORDS = 25


class AmendmentUnreadable(ValueError):
    """The declarations file is missing, malformed, or does not declare its schema.

    Refused rather than treated as "no amendments": an unreadable file would silently become
    permission for nothing, which reads in CI exactly like a clean tree — and the first person
    to hit it would learn that the freeze can be lifted by breaking a JSON file.
    """


def declared_paths(repo_root: Path) -> frozenset[str]:
    """Every repository-relative path a committed amendment permits to move.

    Raises rather than returning empty when the document cannot be read, for the reason
    `AmendmentUnreadable` gives.
    """
    document = Path(repo_root) / AMENDMENTS_FILE
    try:
        raw = json.loads(document.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise AmendmentUnreadable(f"{str(document)!r} could not be read: {error}") from error

    if not isinstance(raw, dict) or raw.get("schema") != AMENDMENT_SCHEMA:
        raise AmendmentUnreadable(
            f"{str(document)!r} does not declare schema {AMENDMENT_SCHEMA!r}. Refused rather "
            "than parsed optimistically: a defaulted amendment list permits nothing while "
            "succeeding, and a reader cannot tell that from a clean tree"
        )

    amendments = raw.get("amendments")
    if not isinstance(amendments, list):
        raise AmendmentUnreadable(f"{str(document)!r} has no `amendments` list")

    permitted: set[str] = set()
    for entry in amendments:
        if not isinstance(entry, dict):
            raise AmendmentUnreadable(f"{str(document)!r} holds a non-object amendment")
        for field in ("id", "recorded_on", "paths", "reason"):
            if field not in entry:
                raise AmendmentUnreadable(
                    f"amendment {entry.get('id', '<unnamed>')!r} is missing {field!r}. Every "
                    "field is required: an amendment without a reason is a permission with no "
                    "argument behind it, which is what the freeze exists to prevent"
                )
        reason = str(entry["reason"])
        if len(reason.split()) < MINIMUM_REASON_WORDS:
            raise AmendmentUnreadable(
                f"amendment {entry['id']!r} gives {len(reason.split())} words of reason and "
                f"{MINIMUM_REASON_WORDS} are required. The file exists so the argument survives "
                "to whoever reads the diff later; 'fix' is non-empty and explains nothing"
            )
        paths = entry["paths"]
        if not isinstance(paths, list) or not paths:
            raise AmendmentUnreadable(f"amendment {entry['id']!r} names no paths")
        permitted.update(str(one) for one in paths)
    return frozenset(permitted)


def undeclared(moved: frozenset[str], repo_root: Path) -> frozenset[str]:
    """The moved paths no amendment permits. Empty means the change is declared."""
    return frozenset(moved) - declared_paths(repo_root)
