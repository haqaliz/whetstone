"""Reading a night's evidence, and deciding which night "last night" was.

The morning report renders a night the operator ran while they were asleep, which makes two
otherwise-dull questions load-bearing.

**What may the report believe about a night?** `ledger.read` (`ledger.py:211`) checks the schema
string and hands back the raw mapping. Every field a report renders is one an optimistic parse
would default, and a defaulted count records nothing while returning successfully — the shape of
every silent failure this repository has already found. So `read_ledger` refuses each missing,
mistyped or unknown field **by name**, in the `gate.read_promotion_record` shape, and returns a
typed document whose fields are the only things the report is allowed to say.

**Which night was last night?** There is no timestamp anywhere in this tree. The run id is
operator-declared (`cli.py:328`) and `recorded_on` is *"an input, never the clock"*
(`ledger.py:151`). Two orderings are available and both are wrong: mtime is a property of the
filesystem rather than of the run — a copied or rsynced directory re-dates itself — and
alphabetical run-id order is not an ordering of nights at all. So `resolve_last_night` reads the
**greatest declared `recorded_on`**, which is the only ordering the evidence actually carries.

That rule has an edge the rule itself cannot resolve, and the refusal is the feature:

* **A tie is `AmbiguousNight`.** Two nights declared on one date is an ordinary thing an operator
  does. Breaking the tie by any incidental order would produce a confident answer about the wrong
  run, so the refusal names both ids and points at `--run`.
* **A night that will not parse refuses the whole scan.** Skipping it would make a killed or
  corrupt night *invisible* to the single command whose job is to say what happened last night,
  and the operator would read a clean report about an older run without learning the newest one
  was unreadable.
* **`recorded_on` is validated as ISO-8601 at read time.** The resolver compares two of them
  lexicographically, which is correct only for that format. Comparing strings of unknown shape and
  calling the greater one "last night" is an ordering wearing the costume of a measurement.

The one directory excluded from the scan is the gate's own `runs/promotions/`, by the gate's own
constant, imported by identity. That is not the "skip what you cannot read" rule this module
refuses: a directory this project writes on purpose, for another purpose, is a different fact from
a night whose ledger will not parse.

Nothing here reaches a model, and nothing here renders. It reads JSON and returns dataclasses.
"""

from __future__ import annotations

import datetime as _datetime
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from whetstone.bakeoff.run import TranscriptNotPrivate
from whetstone.loop.gate import PROMOTIONS_DIR
from whetstone.loop.ledger import LEDGER_FILE, LedgerUnreadable
from whetstone.loop.ledger import read as _read_ledger_payload
from whetstone.loop.night import PUBLISHED

__all__ = [
    "FIELD_SOURCES",
    "LEDGER_FILE",
    "LOCAL",
    "PROMOTIONS_DIR",
    "PUBLISHED",
    "REQUIRED_FIELDS",
    "AmbiguousNight",
    "DatasetCounts",
    "LedgerDocument",
    "LedgerFieldInvalid",
    "LedgerFieldMissing",
    "LedgerUnreadable",
    "ModelRef",
    "NoRuns",
    "RunIdentityMismatch",
    "TaskCounts",
    "TranscriptNotPrivate",
    "load_named_run",
    "read_ledger",
    "refuse_published_out",
    "resolve_last_night",
]


#: The one directory under `reports/` a morning report may be written to. `.gitignore` reserves
#: `/reports/local/` for the user's own nightly output, and the one-home guard filters it out of
#: the published-artifact list by name with that same argument
#: (`tests/bakeoff/test_report.py:2076-2077`). A named constant rather than a string inside the
#: predicate, so widening the carve-out costs a diff someone has to defend.
LOCAL = "local"


class LedgerFieldMissing(LedgerUnreadable):
    """A field the report renders is absent from the ledger.

    A subclass of the ledger's own refusal rather than a new hierarchy: every one of these is a
    ledger that cannot be read, and a caller that wants to catch them all should not have to know
    how many ways there are to fail.
    """


class LedgerFieldInvalid(LedgerUnreadable):
    """A field is present but is not what it declares itself to be."""


class NoRuns(ValueError):
    """The runs root holds no night. Never rendered as an empty morning.

    A report over no runs and a report over a night that produced nothing are opposite facts that
    would exit identically if this returned a blank document instead of refusing.
    """


class AmbiguousNight(ValueError):
    """Two or more nights declare the same greatest `recorded_on`.

    Refused rather than broken. Any tie-break available here — sort order, mtime, directory order
    — answers a question about the filesystem while appearing to answer one about the run, and the
    operator has no way to see which they got. The message names the tied ids and `--run`, because
    a correct refusal with no next step leaves them holding an accurate message and nothing to do.
    """


class RunIdentityMismatch(ValueError):
    """A named run directory holds a ledger declaring a different `run_id`.

    Both are operator-declared strings, so this is a rename or a copy rather than corruption — and
    it is exactly the state in which a report would name one run while rendering another.
    """


@dataclass(frozen=True)
class ModelRef:
    """The candidate, as the ledger recorded it. One of the five pinned inputs."""

    repo_id: str
    revision: str


@dataclass(frozen=True)
class TaskCounts:
    """What the night drew against, as counts and declared ids. Never task contents."""

    private: int
    public: int
    roots: int
    dev_subset: tuple[str, ...]
    probe: int | None
    heldout_digest: str = ""
    heldout_membership: int = 0


@dataclass(frozen=True)
class DatasetCounts:
    """The training set as counts and a digest.

    `denominator` and `unverified` travel with `examples` for the reason `dataset.py:169-174`
    gives: a training-set size on its own grows with the number of draws and says nothing about
    coverage.
    """

    digest: str
    examples: int
    denominator: int
    unverified: int
    coverage: int
    valid_split: str


@dataclass(frozen=True)
class LedgerDocument:
    """A night's ledger, validated. The only things the morning report is allowed to say."""

    run_id: str
    recorded_on: str
    run_seed: int
    draws: int
    model: ModelRef
    contract: Mapping[str, Any]
    task_set: TaskCounts
    dataset: DatasetCounts
    checkpoint_digest: str | None
    checkpoint_absent: str
    tool_versions: Mapping[str, str] = field(default_factory=dict)


#: Which payload key feeds each field of `LedgerDocument`. Asserted total against the dataclass in
#: the suite, so a field cannot be added without declaring where it comes from — a field with no
#: declared source is a field this reader would silently default.
FIELD_SOURCES: Mapping[str, str] = {
    "run_id": "run_id",
    "recorded_on": "recorded_on",
    "run_seed": "run_seed",
    "draws": "draws",
    "model": "model",
    "contract": "generation_contract",
    "task_set": "task_set",
    "dataset": "dataset",
    "checkpoint_digest": "checkpoint",
    "checkpoint_absent": "checkpoint",
    "tool_versions": "tool_versions",
}

#: The top-level keys this reader requires, derived from `FIELD_SOURCES` rather than written twice.
REQUIRED_FIELDS: tuple[str, ...] = tuple(sorted(set(FIELD_SOURCES.values())))

#: Every key the ledger's writer emits (`ledger._payload`). A key outside this set is a schema
#: change nobody declared, and is refused rather than ignored.
_KNOWN_FIELDS: frozenset[str] = frozenset(
    {
        "schema",
        "capacity",
        "draws_recorded",
        "environment_pins",
        "seeds",
        *REQUIRED_FIELDS,
    }
)


def _require(payload: Mapping[str, Any], key: str, path: Path) -> Any:
    if key not in payload:
        raise LedgerFieldMissing(
            f"ledger {str(path)!r} is missing {key!r}. Refused rather than defaulted: every "
            "field this reader needs is one an optimistic parse would fill in, and a defaulted "
            "count records nothing while succeeding"
        )
    return payload[key]


def _text(payload: Mapping[str, Any], key: str, path: Path, *, where: str = "") -> str:
    value = _require(payload, key, path)
    if not isinstance(value, str):
        raise LedgerFieldInvalid(
            f"ledger {str(path)!r}: {where}{key!r} must be a string, got "
            f"{type(value).__name__}"
        )
    return value


def _count(payload: Mapping[str, Any], key: str, path: Path, *, where: str = "") -> int:
    value = _require(payload, key, path)
    # `bool` is an `int` subclass, so the isinstance check alone accepts `true` for a count and it
    # would render as 1 with nobody the wiser. The gate's own reader refuses it the same way.
    if isinstance(value, bool) or not isinstance(value, int):
        raise LedgerFieldInvalid(
            f"ledger {str(path)!r}: {where}{key!r} must be an integer, got "
            f"{type(value).__name__}"
        )
    return value


def _block(payload: Mapping[str, Any], key: str, path: Path) -> Mapping[str, Any]:
    value = _require(payload, key, path)
    if not isinstance(value, dict):
        raise LedgerFieldInvalid(
            f"ledger {str(path)!r}: {key!r} must be an object, got {type(value).__name__}"
        )
    return value


def _iso_date(value: str, path: Path) -> str:
    """`recorded_on`, validated as ISO-8601 before anything compares two of them.

    The resolver orders nights by comparing these strings, which is correct for ISO-8601 and for
    nothing else. Validating here means the refusal arrives when the document is read, rather than
    as a silently wrong ordering later.
    """
    try:
        _datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise LedgerFieldInvalid(
            f"ledger {str(path)!r}: 'recorded_on' must be an ISO-8601 date (YYYY-MM-DD), got "
            f"{value!r} ({exc}). Refused here rather than compared: nights are ordered by "
            "comparing these strings, and comparing two of an unknown format is an ordering "
            "that looks like a measurement"
        ) from exc
    return value


def read_ledger(path: Path) -> LedgerDocument:
    """Read one night's ledger into a typed document, or refuse it by name.

    The schema check is `ledger.read`'s own, reused by identity so this tree holds one answer to
    "is this a ledger" rather than two. Everything after it is this reader's: unknown keys, then
    each field the report renders, checked and never defaulted.
    """
    location = Path(path)
    payload = _read_ledger_payload(location)

    unexpected = sorted(set(payload) - _KNOWN_FIELDS)
    if unexpected:
        raise LedgerFieldInvalid(
            f"ledger {str(location)!r} carries unknown field(s) {unexpected}. Refused rather "
            "than ignored: a key this reader does not know is a schema change nobody declared, "
            "and ignoring it is how a document and its reader stop describing the same thing"
        )

    for required in REQUIRED_FIELDS:
        _require(payload, required, location)

    model = _block(payload, "model", location)
    task_set = _block(payload, "task_set", location)
    dataset = _block(payload, "dataset", location)
    checkpoint = _block(payload, "checkpoint", location)
    contract = _block(payload, "generation_contract", location)
    versions = _block(payload, "tool_versions", location)

    heldout = task_set.get("heldout")
    if heldout is not None and not isinstance(heldout, dict):
        raise LedgerFieldInvalid(
            f"ledger {str(location)!r}: 'task_set.heldout' must be an object or null, got "
            f"{type(heldout).__name__}"
        )

    probe = task_set.get("probe")
    if probe is not None and (isinstance(probe, bool) or not isinstance(probe, int)):
        raise LedgerFieldInvalid(
            f"ledger {str(location)!r}: 'task_set.probe' must be an integer or null, got "
            f"{type(probe).__name__}"
        )

    digest = checkpoint.get("digest")
    if digest is not None and not isinstance(digest, str):
        raise LedgerFieldInvalid(
            f"ledger {str(location)!r}: 'checkpoint.digest' must be a string or null, got "
            f"{type(digest).__name__}"
        )

    return LedgerDocument(
        run_id=_text(payload, "run_id", location),
        recorded_on=_iso_date(_text(payload, "recorded_on", location), location),
        run_seed=_count(payload, "run_seed", location),
        draws=_count(payload, "draws", location),
        model=ModelRef(
            repo_id=_text(model, "repo_id", location, where="model."),
            revision=_text(model, "revision", location, where="model."),
        ),
        contract=dict(contract),
        task_set=TaskCounts(
            private=_count(task_set, "private", location, where="task_set."),
            public=_count(task_set, "public", location, where="task_set."),
            roots=_count(task_set, "roots", location, where="task_set."),
            dev_subset=tuple(task_set.get("dev_subset", ())),
            probe=probe,
            heldout_digest=(
                _text(heldout, "document_digest", location, where="task_set.heldout.")
                if heldout
                else ""
            ),
            heldout_membership=(
                _count(heldout, "membership_count", location, where="task_set.heldout.")
                if heldout
                else 0
            ),
        ),
        dataset=DatasetCounts(
            digest=_text(dataset, "digest", location, where="dataset."),
            examples=_count(dataset, "examples", location, where="dataset."),
            denominator=_count(dataset, "denominator", location, where="dataset."),
            unverified=_count(dataset, "unverified", location, where="dataset."),
            coverage=_count(dataset, "coverage", location, where="dataset."),
            valid_split=_text(dataset, "valid_split", location, where="dataset."),
        ),
        checkpoint_digest=digest,
        checkpoint_absent=_text(checkpoint, "absent", location, where="checkpoint."),
        tool_versions=dict(versions),
    )


def load_named_run(directory: Path) -> LedgerDocument:
    """Read the night the operator named, refusing one whose ledger disagrees with its home.

    The directory name and the ledger's `run_id` are both operator-declared strings, so a
    disagreement is a rename or a copy rather than corruption — and it is precisely the state in
    which a report would name one run at the top of the page and render another beneath it.
    """
    home = Path(directory)
    document = read_ledger(home / LEDGER_FILE)
    if document.run_id != home.name:
        raise RunIdentityMismatch(
            f"run directory {home.name!r} holds a ledger declaring run_id "
            f"{document.run_id!r}. Refused rather than reconciled: both are operator-declared, "
            "so this is a rename or a copy, and a report that named one and rendered the other "
            "would be wrong in the one field a reader uses to find the evidence"
        )
    return document


def _nights(runs_root: Path) -> list[Path]:
    """Every directory under the runs root that is a night, in a stable order.

    The gate's own `runs/promotions/` is excluded by its own constant. That is the single
    exclusion and it is by name: a directory this project writes on purpose, for another purpose,
    is a different fact from a night whose ledger will not parse — which is refused, below.
    """
    root = Path(runs_root)
    if not root.is_dir():
        return []
    return sorted(
        one for one in root.iterdir() if one.is_dir() and one.name != PROMOTIONS_DIR
    )


def resolve_last_night(runs_root: Path) -> LedgerDocument:
    """The night with the greatest declared `recorded_on`, or a refusal naming why there is none.

    Every night is read — not just the one that wins — because a night whose ledger will not parse
    is a fact the operator needs, and discovering it only when it happens to be the newest would
    make the check a matter of luck.
    """
    root = Path(runs_root)
    directories = _nights(root)
    if not directories:
        raise NoRuns(
            f"no night under {str(root)!r}. Refused rather than rendered: a report over no runs "
            "and a report over a night that produced nothing are opposite facts, and a blank "
            "document would make them read identically"
        )

    documents = [read_ledger(one / LEDGER_FILE) for one in directories]
    latest = max(one.recorded_on for one in documents)
    tied = sorted(one.run_id for one in documents if one.recorded_on == latest)
    if len(tied) > 1:
        raise AmbiguousNight(
            f"{len(tied)} nights declare the same latest date {latest!r}: {', '.join(tied)}. "
            "Refused rather than broken by sort order, mtime or directory order — each of those "
            "answers a question about the filesystem while appearing to answer one about the "
            "run. Name the one you meant with --run"
        )
    return next(one for one in documents if one.run_id == tied[0])


def refuse_published_out(root: Path, flag: str) -> None:
    """Refuse an output root inside a committed report directory, before anything is written.

    The night's own `_refuse_published_root` cannot be reused here, and the reason is worth
    stating rather than working around: it refuses **any** path with a `reports` component, and
    this unit's documented home is `reports/local/`. Borrowing it by identity would refuse the one
    place a morning report is supposed to go.

    So this is its narrower sibling, and the carve-out is not invented here. `.gitignore` reserves
    `/reports/local/` for the user's own nightly output — its comment names "the morning reports"
    — and the one-home guard already filters that prefix out of the published-artifact list on the
    argument that it is *"their data and never ours to assert on"*. Everything else under
    `reports/` is the one part of this tree an outside reader is expected to read, and a morning
    report holds counts and digests derived from private donor code.

    Resolved rather than compared as written, for the reason `night.py:620-622` gives:
    `reports/local/../baseline` and a symlinked scratch directory each name a published path while
    comparing unequal to one, and the check has to hold against the path that gets written.
    `strict=False` throughout — the directory does not exist before the first morning, and a check
    that required it to would refuse every honest invocation.

    Raises the bake-off's own `TranscriptNotPrivate`, imported by identity, so this repository has
    one name for "private evidence was pointed at a published path" rather than two.
    """
    parts = Path(root).resolve().parts
    if PUBLISHED not in parts:
        return
    published_at = parts.index(PUBLISHED)
    if parts[published_at + 1 : published_at + 2] == (LOCAL,):
        return
    raise TranscriptNotPrivate(
        f"{flag} points at {str(root)!r}, which is inside a {PUBLISHED}/ directory but outside "
        f"{PUBLISHED}/{LOCAL}/ — the one carve-out reserved for the user's own nightly output. A "
        "morning report holds counts and digests derived from private donor code, and every other "
        f"directory under {PUBLISHED}/ is committed and read by outsiders. Point it at "
        f"{PUBLISHED}/{LOCAL}/ or at a path outside {PUBLISHED}/ entirely"
    )
