"""The leakage proof: a night's training set and the held-out membership must not touch.

`docs/ROADMAP.md:459-460` makes this a P3 exit criterion in its own right — *"`uv run
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
  denominator (`:157`). The membership is source B's and identity matching applies to
  source B only: source A's examples are counted and disclosed as *not compared*, never as a
  measured zero, because a structural constant printed as a count reads as a measurement.
- **Exit 0 means exactly one thing:** source B examples were compared and none shared a task
  identity. A training set with source A examples and no source B example compared nothing and
  is a refusal (exit 2, Amendment 2 of the gate-leakage-guard PRD); a training set with no
  example at all stays disjoint by truth.

**The run input is the dataset document; the ledger is optional.** `dataset.json` is
required, the ledger is validated when present, and a run without one is checked and says so
in a notice (a night can write its dataset and raise before its ledger lands).

**The subject is the dataset document, not the ledger's task set.** `runs/<id>/dataset.json`
records what was actually trained on — the strict-PASS selection — and the ledger's task set
records what was *considered*. Only the first can leak into an adapter's weights.

**The `--checkpoint` link.** Given a checkpoint, `run_check` verifies it and compares the
`dataset_digest` it records with the digest in the run's `dataset.json`; a mismatch is a
refusal, decided before any overlap is compared. Each side's seal state is conditional on its
generation: the checkpoint's claim is sealed when it is a v2 checkpoint and recorded, not
sealed, when it is v1; the run's document is read through the verifying reader and is sealed
when it is a v2 dataset, recorded, not sealed, when it is v1. The two link lines say which is
which. Neither side's seal authenticates a writer, and neither is proof that the recorded digest
equals the digest of what was actually trained on.

This module prevents nothing. If it ever exits nonzero, the disclosure names two possible
causes and asserts neither: the night's partition seam failed to exclude held-out ids, or
the held-out document was derived or re-derived after the night ran. It says so in those
words rather than merely reporting a number.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from whetstone.loop.dataset import (
    DATASET_SCHEMA,
    DatasetUnverified,
    VerifiedDataset,
    verify_document,
)
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
from whetstone.loop.sft import CheckpointUnverified, verify_checkpoint

#: The two sources, by identity from the night that writes them. A third name here would be a
#: second answer to "which sources exist", and the check would then be able to disagree with
#: the document it is reading.
SOURCES = (PRIVATE, PUBLIC)


class NotARun(ValueError):
    """The directory named holds no `dataset.json`, so there is no training set to check.

    Refused rather than read as an empty training set: an absent dataset and a night that
    trained on nothing are different facts, and only the second is disjoint by truth. A
    missing ledger alone is not a refusal; the dataset is the document that records what was
    trained on.
    """


class UnknownSource(ValueError):
    """A training set carries a source name this check cannot report over.

    Both sources are always published together, so a document naming a third is one this
    check cannot render honestly: it would either drop those examples out of the denominator
    or file them under a source they do not belong to.
    """


class DatasetUnreadable(ValueError):
    """The run's dataset document could not be read as the schema it must declare."""


class UnrecognisedIdentity(ValueError):
    """A task id carries no trailing 12-hex identity, so it cannot be matched by identity.

    Refused rather than compared as a string: a corpus re-mint renames ids (`legacy-a-X` became
    `donor-a-X`) and keeps the trailing identity, so an exact-string match calls a renamed
    leak clean. An id this check cannot read an identity from is an id it cannot prove
    disjoint, and the fix is an amendment that says how the id maps, not a looser match.
    """


class NothingCompared(ValueError):
    """The training set holds source A examples and no source B example, so nothing was compared.

    Identity matching is source B's alone, so such a run has no example the held-out membership
    could have touched. Refused rather than reported: an exit code that cannot tell "checked"
    from "nothing compared" is the wrong signal for a guard the runbook halts on
    (`docs/planning/gate-leakage-guard/prd.md`, Amendment 2). A training set with no example at
    all is a different fact: nothing trained, nothing to leak, disjoint by truth.
    """


class CheckpointHasNoDataset(ValueError):
    """The checkpoint is the untrained base: it was trained on nothing, so there is no dataset.

    Refused rather than reported: there is no recorded training set to compare with the run's,
    and a link that cannot exist must not read as one that was checked and found clean.
    """


class CheckpointNotThisRun(ValueError):
    """The checkpoint's recorded dataset digest is not the run's: another night trained it.

    A verdict about this run says nothing about that checkpoint, so none is given. The fix is
    to point `--checkpoint` at the checkpoint this night wrote, or `--run` at the night that
    wrote this checkpoint.
    """


#: What the CLI turns into a usage error rather than a traceback: everything an operator can
#: fix by retyping the command or by pointing at a different directory.
REFUSALS: tuple[type[Exception], ...] = (
    NotARun,
    UnknownSource,
    DatasetUnreadable,
    DatasetUnverified,
    UnrecognisedIdentity,
    NothingCompared,
    LedgerUnreadable,
    EmptyHeldout,
    HeldoutSchemaError,
    HeldoutDigestMismatch,
    CheckpointUnverified,
    CheckpointHasNoDataset,
    CheckpointNotThisRun,
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

    #: Each distinct (training id, held-out id) pair that matched on identity, sorted. They
    #: differ in name when a re-mint renamed the task, so both are named.
    matched: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class DatasetLink:
    """The digest a checkpoint and a run agreed on, and each side's seal state.

    `sealed` is the checkpoint's claim state (from `verify_checkpoint`: v2 only); `run_sealed`
    is the run document's, from the verifying reader (v2 only; a v1 document is never sealed).
    The link itself is digest equality — neither side's seal is the link, and neither seal
    authenticates a writer or proves what was trained on.
    """

    digest: str
    sealed: bool
    run_sealed: bool


@dataclass(frozen=True)
class LeakReport:
    """What the check found, over both sources, with every count over its own denominator."""

    #: How many tasks the held-out document holds out — the set being protected.
    heldout_count: int

    #: Source B's examples and overlap.
    private: SourceLeak

    #: Source A's examples and overlap.
    public: SourceLeak

    #: Whether the run directory held no `ledger.json`. The check read the dataset alone and
    #: says so; it is never a reason to pass or to fail.
    ledger_absent: bool = False

    #: Set only when a checkpoint was given and its recorded dataset digest matched the run's.
    link: DatasetLink | None = None

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
    by_identity: dict[str, str] = {}
    for member in sorted(members):
        by_identity.setdefault(_identity(member), member)
    # The membership is source B's, so only the private source is matched against it; the
    # public ids carry no such identity and are counted as examples, never compared.
    for task_id in training.get(PRIVATE, ()):
        _identity(task_id)
    if not training.get(PRIVATE) and any(training.get(source) for source in SOURCES):
        raise NothingCompared(
            "the training set has no source B example, so nothing was compared against the "
            "held-out membership (source A examples are never compared) and no verdict was "
            "reached. Refused rather than reported clean: exit 0 means source B examples were "
            "compared and none shared a task identity"
        )
    leaks = {source: _leak_of(source, training.get(source, ()), by_identity) for source in SOURCES}
    return LeakReport(
        heldout_count=len(members),
        private=leaks[PRIVATE],
        public=leaks[PUBLIC],
    )


def run_check(run: Path, heldout: Path, checkpoint: Path | None = None) -> LeakReport:
    """Read a night's training set and a held-out document, and compare them.

    The contract: `dataset.json` is required (without it there is nothing to check); the
    ledger is optional, validated when present, and its absence is disclosed in a notice. The
    order is the design: the dataset is located before anything is read, the held-out
    document goes through
    aspect 1's fail-closed loader by identity (a doctored membership or a digest mismatch
    refuses before any comparison), and only then are the two sets compared. A check that
    read a doctored document and reported "clean" would be worse than no check.

    The dataset is read through the verifying reader: a v2 document's claims are re-hashed
    before any field is used, so a tampered sealed document refuses before the link and before
    any overlap is compared, with or without a checkpoint. A v1 document performs none of that
    and reads exactly as it always did.

    With a `checkpoint`, it is verified and its recorded dataset digest is compared with the
    run's before the overlap is compared, so another night's checkpoint is refused even when
    the run is leaked.
    """
    dataset_path = run / DATASET_FILE
    if not dataset_path.is_file():
        raise NotARun(
            f"{str(run)!r} holds no {DATASET_FILE!r}, so there is no training set to check "
            "and nothing to prove disjoint from the held-out set. Refused rather than treated "
            "as an empty training set: a night with no dataset is not a night that trained on "
            "nothing"
        )
    # A ledger is validated when present and not required: a night can write its dataset and
    # then raise before its ledger lands, and the dataset is the document that records what
    # was trained on (PRD requirement 2). The absence is carried into the report, not hidden.
    ledger = run / LEDGER_FILE
    ledger_absent = not ledger.is_file()
    if not ledger_absent:
        read_ledger(ledger)

    verified = _read_dataset(dataset_path)
    document = verified.document
    training = _training_of(document, dataset_path)
    link = (
        _link_of(document, dataset_path, checkpoint, verified.sealed)
        if checkpoint is not None
        else None
    )
    report = check_overlap(training, read_heldout(heldout).membership)
    return replace(report, ledger_absent=ledger_absent, link=link)


def _link_of(
    document: Mapping[str, object], path: Path, checkpoint: Path, run_sealed: bool
) -> DatasetLink:
    """Verify the checkpoint and match its recorded dataset digest to the run's, exactly."""
    cp = verify_checkpoint(checkpoint)
    if cp.untrained:
        raise CheckpointHasNoDataset(
            f"{str(checkpoint)!r} is the untrained base: it was trained on nothing, so there is "
            "no dataset to compare with the run's. Point --checkpoint at a night's adapter"
        )
    run_digest = document.get("digest")
    if not isinstance(run_digest, str):
        raise DatasetUnreadable(
            f"{str(path)!r} records no 'digest' string (found {run_digest!r}), so the run "
            "cannot be linked to a checkpoint"
        )
    recorded = cp.dataset_digest
    if recorded != run_digest:
        found = recorded[:12] if isinstance(recorded, str) else repr(recorded)
        raise CheckpointNotThisRun(
            f"{str(checkpoint)!r} records training dataset {found} and this run's dataset is "
            f"{run_digest[:12]}: the checkpoint was not trained on this run, so a verdict about "
            "the run says nothing about it. Point --checkpoint at the checkpoint this night "
            "wrote, or --run at the night that wrote this checkpoint"
        )
    return DatasetLink(digest=run_digest, sealed=cp.sealed, run_sealed=run_sealed)


def disclosure(report: LeakReport) -> tuple[str, ...]:
    """The lines `whetstone check-leakage` prints: the verdict, both sources, the ids.

    A clean night and a night that trained on nothing both satisfy the check, and they are
    different facts about the night — so the empty case says so in its own words rather than
    reading as an ordinary pass. A run with source A examples only never reaches here: it
    compared nothing and `check_overlap` refuses it (`NothingCompared`).
    """
    subject = f"held-out membership: {report.heldout_count} task(s)"
    if report.examples == 0:
        return _with_notice(
            report,
            (
                "leakage: clean — the run has no training examples, so it is disjoint by truth "
                "rather than by exclusion",
                subject,
                _source_line(report.private),
                _source_line(report.public),
                *_link_lines(report.link),
            ),
        )
    # The denominator is the compared examples only: source A's are not matched against the
    # membership, so counting them here would dilute a leak into a smaller-looking fraction.
    compared = report.private.examples
    verdict = (
        f"leakage: {'clean' if report.clean else 'LEAKED'} — {report.leaked_examples} of "
        f"{compared} training {_examples(compared)} {_touch(compared)} a held-out task"
    )
    lines = [verdict, subject, _source_line(report.private), _source_line(report.public)]
    if report.clean:
        lines.append(_RESIDUAL)
    if not report.clean:
        lines.append(f"leaked task(s): {', '.join(report.overlap)}")
        pairs = [pair for leak in (report.private, report.public) for pair in leak.matched]
        for trained, held in sorted(set(pairs)):
            lines.append(f"matched by identity: trained on {trained}, held out as {held}")
        lines.append(
            "A leak means one of two things, and the operator must find out which: (a) the "
            "night's partition seam failed to exclude held-out ids, or (b) the held-out "
            "document was derived or re-derived after the night ran (e.g. a corpus re-mint), "
            "so the night could not have excluded these ids. Either way the candidate "
            "trained on these tasks is not gated; do not exclude these examples after the fact"
        )
    lines.extend(_link_lines(report.link))
    return _with_notice(report, lines)


def _link_lines(link: DatasetLink | None) -> tuple[str, ...]:
    """What the checkpoint link was, and was not: one line per side, sealed or recorded.

    Each side's files are verified either way; the *link* is digest equality and is never itself
    sealed, authenticated or "verified". The checkpoint's claims are sealed when it is a v2
    checkpoint; the run's document is sealed when it is a v2 dataset. A v1 document on either
    side is recorded, not sealed — anyone with write access can edit it — and neither side's
    seal is proof of what was actually trained on.
    """
    if link is None:
        return ()
    head = (
        f"dataset link: the checkpoint's dataset_digest ({link.digest[:12]}) "
        f"matches this run's {DATASET_FILE}; "
    )
    if link.sealed:
        tail = (
            "the checkpoint's claims are sealed (whetstone-checkpoint/2), so an edit to that "
            "dataset_digest that did not also recompute the checkpoint's digest would have been "
            "refused (tamper-evidence, not authentication)"
        )
    else:
        tail = (
            "it is recorded, not sealed (whetstone-checkpoint/1) — provenance.json was outside "
            "that checkpoint's digest, so this is what the document says and not something "
            "that was checked"
        )
    if link.run_sealed:
        run_line = (
            f"the run's {DATASET_FILE} is sealed (whetstone-training-set/2), so an edit to it "
            "that did not also recompute its claims and digest would have been refused "
            "(tamper-evidence, not authentication)"
        )
    else:
        run_line = (
            f"the run's {DATASET_FILE} is recorded, not sealed (whetstone-training-set/1), so "
            "this compares the checkpoint's claim to a document that anyone with write access "
            "to the run can edit"
        )
    return (head + tail, run_line)


#: What a clean verdict rules out, and what it does not. Identity is all the check compares.
_RESIDUAL = (
    "This rules out a shared task identity between source B's training examples and the "
    "held-out membership: no shared task identity was found. It is not a claim of freedom "
    "from contamination: near-duplicate tasks under different identities are not detected"
)


def _examples(count: int) -> str:
    """'example' for exactly one, 'examples' otherwise."""
    return "example" if count == 1 else "examples"


def _touch(count: int) -> str:
    """The verb that agrees with 'of <count> training example(s)'."""
    return "touches" if count == 1 else "touch"


def _with_notice(report: LeakReport, lines: Sequence[str]) -> tuple[str, ...]:
    """The lines, with the ledger-absence notice appended when the run held no ledger."""
    if not report.ledger_absent:
        return tuple(lines)
    return (
        *lines,
        f"notice: {LEDGER_FILE} was absent from the run; the training set was read from "
        f"{DATASET_FILE} alone, and the run was not identified as complete by its ledger",
    )


def _source_line(leak: SourceLeak) -> str:
    """One source's counts over its own denominator, named even when empty."""
    if leak.source != PRIVATE:
        return (
            f"source A (public): {leak.examples} training {_examples(leak.examples)}, not "
            "compared — the held-out membership is source B's"
        )
    label = "source B (private)"
    if leak.examples == 0:
        return f"{label}: no training examples, so nothing to compare"
    named = ", ".join(leak.overlap) if leak.overlap else "none"
    return (
        f"{label}: {leak.leaked_examples} of {leak.examples} training "
        f"{_examples(leak.examples)} {_touch(leak.examples)} a held-out task; "
        f"leaked task(s): {named}"
    )


_IDENTITY = re.compile(r"[0-9a-f]{12}$")


def _identity(task_id: str) -> str:
    """The trailing 12-hex identity of a private task id, or a refusal naming the id."""
    found = _IDENTITY.search(task_id)
    if found is None:
        raise UnrecognisedIdentity(
            f"task id {task_id!r} carries no trailing 12-hex identity, so it cannot be "
            "compared. Refused rather than matched as a string: a corpus re-mint renames ids "
            "and keeps the identity, so a string match can call a renamed leak clean. Fixing "
            "this takes an amendment naming how the id maps, never a looser comparison"
        )
    return found.group(0)


def _leak_of(source: str, ids: Sequence[str], by_identity: Mapping[str, str]) -> SourceLeak:
    """One source's leak, with ids distinct and sorted and examples counted as examples."""
    if source != PRIVATE:
        return SourceLeak(source=source, examples=len(ids), overlap=(), leaked_examples=0)
    pairs = [
        (task_id, by_identity[_identity(task_id)])
        for task_id in ids
        if _identity(task_id) in by_identity
    ]
    return SourceLeak(
        source=source,
        examples=len(ids),
        overlap=tuple(sorted({held for _, held in pairs})),
        leaked_examples=len(pairs),
        matched=tuple(sorted(set(pairs))),
    )


def _read_dataset(path: Path) -> VerifiedDataset:
    """The run's dataset document, through the verifying reader, seal refusals unwrapped.

    A v2 document's claims are re-hashed before any field is read, so a tampered sealed
    document refuses here — before the link and before any overlap comparison, with or without
    a checkpoint. `DatasetUnverified` is deliberately re-raised unchanged: it is a `ValueError`
    subclass, and the wrap below would otherwise rename the seal's refusal as an unreadable
    document, reporting the right claim under the wrong type. A v1 document performs no claims
    check and reads exactly as it always did, `sealed=False`.
    """
    try:
        return verify_document(path)
    except DatasetUnverified:
        raise
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
    "NothingCompared",
    "SourceLeak",
    "UnknownSource",
    "UnrecognisedIdentity",
    "check_overlap",
    "disclosure",
    "run_check",
]
