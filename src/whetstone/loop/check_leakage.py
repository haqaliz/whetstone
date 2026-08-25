"""The leakage proof: a night's training set and the held-out membership must not touch.

`docs/ROADMAP.md:449-450` makes this a P3 exit criterion in its own right — *"`uv run
whetstone check-leakage` exits 0 — zero overlap between the training set and the held-out
set"* — and it is deliberately separate from the exclusion that prevents the overlap. The
night already drops the held-out ids at the partition seam, before the contract is frozen;
that is a behaviour, and a behaviour nobody checks is a claim. The one claim this project
cannot afford to make on trust is that its headline was not measured on its own training
data, so the exclusion is *proven* here rather than relied on.

Two decisions carry the honesty, and both are the same kind of decision made elsewhere in
this repository:

- **An overlap is named, never counted.** A leak reported as a number tells an operator that
  something is wrong and nothing about what; the fix for a leak lives in the night that
  produced it, and the id is how that night is found.
- **Both sources are reported together** (`PREREGISTRATION.md:142-147`), each over its own
  denominator (`:157`). The membership is source B's, so source A's overlap is expected to be
  empty — and it is measured rather than assumed, because "that cannot happen" is how a
  finding goes unnoticed.

**The subject is the dataset document, not the ledger's task set.** `runs/<id>/dataset.json`
records what was actually trained on — the strict-PASS selection — and the ledger's task set
records what was *considered*. Only the first can leak into an adapter's weights.

This module prevents nothing. If it ever exits nonzero, the finding is a regression in the
night's partition seam, and the disclosure says so in those words rather than merely
reporting a number.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from whetstone.loop.dataset import DATASET_SCHEMA, read_document
from whetstone.loop.heldout import (
    EmptyHeldout,
    HeldoutDigestMismatch,
    HeldoutSchemaError,
)
from whetstone.loop.heldout import (
    read_document as read_heldout,
)
from whetstone.loop.ledger import LEDGER_FILE, LedgerUnreadable
from whetstone.loop.ledger import read as read_ledger
from whetstone.loop.night import DATASET_FILE, PRIVATE, PUBLIC

#: The two sources, by identity from the night that writes them. A third name here would be a
#: second answer to "which sources exist", and the check would then be able to disagree with
#: the document it is reading.
SOURCES = (PRIVATE, PUBLIC)


class NotARun(ValueError):
    """The directory named is not a night-written run.

    Refused rather than read for what happens to be there: a directory holding a
    `dataset.json` and nothing else could be anything — a copy, a hand-made fixture, an
    aborted run — and a leakage proof over an unidentified training set proves nothing about
    any night.
    """


class UnknownSource(ValueError):
    """A training set carries a source name this check cannot report over.

    Both sources are always published together, so a document naming a third is one this
    check cannot render honestly: it would either drop those examples out of the denominator
    or file them under a source they do not belong to.
    """


class DatasetUnreadable(ValueError):
    """The run's dataset document could not be read as the schema it must declare."""


#: What the CLI turns into a usage error rather than a traceback: everything an operator can
#: fix by retyping the command or by pointing at a different directory.
REFUSALS: tuple[type[Exception], ...] = (
    NotARun,
    UnknownSource,
    DatasetUnreadable,
    LedgerUnreadable,
    EmptyHeldout,
    HeldoutSchemaError,
    HeldoutDigestMismatch,
)


@dataclass(frozen=True)
class SourceLeak:
    """One source's training examples and whatever they touched."""

    #: `"private"` (source B) or `"public"` (source A).
    source: str

    #: Training examples drawn from this source. Examples, not tasks: a night draws `K`
    #: attempts per task and every verified win is its own example.
    examples: int

    #: Every held-out id this source's examples touched, distinct and sorted. Empty is the
    #: only acceptable value, and it is reported rather than assumed.
    overlap: tuple[str, ...]

    #: How many examples touched a held-out task. Distinct from `len(overlap)` because one
    #: leaked task can have been trained on several times.
    leaked_examples: int


@dataclass(frozen=True)
class LeakReport:
    """What the check found, over both sources, with every count over its own denominator."""

    #: How many tasks the held-out document holds out — the set being protected.
    heldout_count: int

    #: Source B's examples and overlap.
    private: SourceLeak

    #: Source A's examples and overlap.
    public: SourceLeak

    @property
    def examples(self) -> int:
        """Training examples across both sources — the denominator of the verdict sentence."""
        return self.private.examples + self.public.examples

    @property
    def overlap(self) -> tuple[str, ...]:
        """Every leaked id across both sources, distinct and sorted."""
        return tuple(sorted({*self.private.overlap, *self.public.overlap}))

    @property
    def leaked_examples(self) -> int:
        """Training examples that touched a held-out task."""
        return self.private.leaked_examples + self.public.leaked_examples

    @property
    def clean(self) -> bool:
        """Whether the two sets are disjoint. The command's exit turns on exactly this."""
        return not self.overlap


def check_overlap(
    training: Mapping[str, Sequence[str]], heldout_membership: Sequence[str]
) -> LeakReport:
    """Compare a training set against a held-out membership, per source.

    `training` is keyed by source and holds the task id of every training **example**,
    duplicates kept: the denominator is examples, and collapsing them here would make the
    reported count disagree with the document it was read from.
    """
    unknown = sorted(set(training) - set(SOURCES))
    if unknown:
        raise UnknownSource(
            f"the training set names source(s) {unknown!r}, and this check reports over "
            f"{list(SOURCES)!r}. Refused rather than partially read: both sources are always "
            "published together, so examples filed under neither would either vanish from "
            "the denominator or be counted under a source they are not from"
        )
    members = set(heldout_membership)
    leaks = {
        source: _leak_of(source, training.get(source, ()), members) for source in SOURCES
    }
    return LeakReport(
        heldout_count=len(members),
        private=leaks[PRIVATE],
        public=leaks[PUBLIC],
    )


def run_check(run: Path, heldout: Path) -> LeakReport:
    """Read a night's training set and a held-out document, and compare them.

    The order is the design: the run is identified before it is read (a directory without a
    ledger is not a night's run, whatever else it holds), the held-out document goes through
    aspect 1's fail-closed loader by identity (a doctored membership or a digest mismatch
    refuses before any comparison), and only then are the two sets compared. A check that
    read a doctored document and reported "clean" would be worse than no check.
    """
    ledger = run / LEDGER_FILE
    if not ledger.is_file():
        raise NotARun(
            f"{str(run)!r} holds no {LEDGER_FILE!r}, so it is not a night-written run. "
            "Refused rather than read for whatever is there: a leakage proof over an "
            "unidentified training set proves nothing about any night"
        )
    read_ledger(ledger)

    document = _read_dataset(run / DATASET_FILE)
    training = _training_of(document, run / DATASET_FILE)
    return check_overlap(training, read_heldout(heldout).membership)


def disclosure(report: LeakReport) -> tuple[str, ...]:
    """The lines `whetstone check-leakage` prints: the verdict, both sources, the ids.

    A clean night and a night that trained on nothing both satisfy the check, and they are
    different facts about the night — so the empty case says so in its own words rather than
    reading as an ordinary pass.
    """
    subject = f"held-out membership: {report.heldout_count} task(s)"
    if report.examples == 0:
        return (
            "leakage: clean — the run has no training examples, so it is disjoint by truth "
            "rather than by exclusion",
            subject,
            _source_line(report.private),
            _source_line(report.public),
        )
    verdict = (
        f"leakage: {'clean' if report.clean else 'LEAKED'} — {report.leaked_examples} of "
        f"{report.examples} training examples touch a held-out task"
    )
    lines = [verdict, subject, _source_line(report.private), _source_line(report.public)]
    if not report.clean:
        lines.append(f"leaked task(s): {', '.join(report.overlap)}")
        lines.append(
            "This is a regression in the night's partition seam: held-out ids are excluded "
            "there, before the contract is frozen. Fix the night that produced this run; do "
            "not exclude these examples after the fact"
        )
    return tuple(lines)


def _source_line(leak: SourceLeak) -> str:
    """One source's counts over its own denominator, named even when empty."""
    label = "source B (private)" if leak.source == PRIVATE else "source A (public)"
    named = ", ".join(leak.overlap) if leak.overlap else "none"
    return (
        f"{label}: {leak.leaked_examples} of {leak.examples} training examples touch a "
        f"held-out task; leaked task(s): {named}"
    )


def _leak_of(source: str, ids: Sequence[str], members: set[str]) -> SourceLeak:
    """One source's leak, with ids distinct and sorted and examples counted as examples."""
    touched = [task_id for task_id in ids if task_id in members]
    return SourceLeak(
        source=source,
        examples=len(ids),
        overlap=tuple(sorted(set(touched))),
        leaked_examples=len(touched),
    )


def _read_dataset(path: Path) -> Mapping[str, object]:
    """The run's dataset document, through `dataset.read_document` by identity."""
    try:
        return read_document(path)
    except (OSError, ValueError) as error:
        raise DatasetUnreadable(
            f"{str(path)!r} could not be read as a {DATASET_SCHEMA!r} document: {error}"
        ) from error


def _training_of(document: Mapping[str, object], path: Path) -> dict[str, list[str]]:
    """The training set as ids per source, read field by field off the dataset document."""
    examples: Any = document.get("examples")
    if not isinstance(examples, list):
        raise DatasetUnreadable(
            f"{str(path)!r} declares {DATASET_SCHEMA!r} and carries no 'examples' list. "
            "Refused rather than treated as empty: an unreadable training set and a training "
            "set that is empty are different facts, and only one of them is disjoint by truth"
        )
    training: dict[str, list[str]] = {source: [] for source in SOURCES}
    for index, one in enumerate(examples):
        if not isinstance(one, dict) or "task_id" not in one or "source" not in one:
            raise DatasetUnreadable(
                f"{str(path)!r} example {index} carries no task id and source. Refused rather "
                "than skipped: an example this check cannot read is an example it cannot "
                "prove disjoint"
            )
        source = str(one["source"])
        if source not in training:
            raise UnknownSource(
                f"{str(path)!r} example {index} declares source {source!r}, and this check "
                f"reports over {list(SOURCES)!r}. Refused rather than partially read: both "
                "sources are always published together"
            )
        training[source].append(str(one["task_id"]))
    return training


__all__ = [
    "REFUSALS",
    "SOURCES",
    "DatasetUnreadable",
    "LeakReport",
    "NotARun",
    "SourceLeak",
    "UnknownSource",
    "check_overlap",
    "disclosure",
    "run_check",
]
