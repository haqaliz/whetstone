"""The held-out source-B split: rule pre-committed, document deterministic, both fail-closed.

`PREREGISTRATION.md` § 7.1 leaves the held-out split open until P3 and names its closure rule:
a dated amendment committed **before the split is used to score anything**, with a corpus too
small for a non-degenerate split being the published finding rather than a worked-around number
(`PREREGISTRATION.md:242-247`). This module is the split's machinery, and its whole value is
the order of events: the rule lives here in code — `HELDOUT_BANDS`, `MIN_HELDOUT`,
`MIN_PER_BAND`, and the `SPLIT_SEED` — so it is fixed before any split is computed, and the
document it writes is committed before any scoring touches it.

**The difficulty axis is the stratum document's, never a new one.** The 66 source-B tasks are
ordered into terciles by the per-task difficulty the committed stratum document already
measures (`tasks/stratum/easier.json`: files / hunks / added+deleted), and that measurement is
reused as the ordering key by identity: `band_of` reads a `whetstone.bakeoff.stratum.Difficulty`
through the stratum module's own fail-closed loader, so "how hard is this task" has exactly one
definition in this repository — the stratum rule's (`stratum.py:29-32`). The held-out document
carries the same per-task difficulty beside its per-task band, so a reader sees the axis under
the split it produced.

**Selection is `sha256(split_seed, task_id)`, never the builtin `hash`.** The builtin is salted
per process, so a derivation built on it would make the split's determinism a claim about
`PYTHONHASHSEED` (the `sampling.attempt_seed` discipline, `sampling.py:100-119`). Per band, the
members sort by the digest and the first `max(MIN_PER_BAND, ceil(MIN_HELDOUT / HELDOUT_BANDS))`
are held out; the seed is a declared constant the document carries, and the rule digest hashes
the rule's source **and** the constants, so any edit to either invalidates every committed
document by design.

**A split that cannot meet the rule is refused by name, in the writer and the loader.** Empty,
whole-corpus, and floors-unmet memberships are `EmptyHeldout` — the § 7.1 finding is the
response, never a loosened floor (`spec.md` AC1). The loader is fail-closed like the stratum
loader's: unknown schema, an unknown field, a rule whose digest moved on, a hand-edited payload
that breaks the `document_digest`, a duplicated membership, a membership naming a task the
document refused rather than measured, and the two degenerate memberships are each a named
refusal. A fully regenerated doctored document passes by construction — the layered defence is
git history plus ordering plus the recomputation test (`test_heldout_document.py`), stated,
never reconciled.

The document is evidence about the data, never the data (`tasks/README.md:126-128`): counts,
band indices and membership ids only — never paths, never patch content, never donor code. The
locality walk in `test_heldout_document.py` asserts that structurally, with a canary that
proves the walk would see a leak. No model, no network, nothing under `verify/`, `patch.py` or
`attribution.py` is touched; the bake-off imports here run one way (loop -> bakeoff -> verify),
the declared direction.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from whetstone.bakeoff.stratum import (
    _LOCAL_OUT_ROOTS,
    Difficulty,
    OutUnderLocalCorpus,
    Stratum,
)
from whetstone.bakeoff.stratum import (
    read_document as read_stratum_document,
)
from whetstone.tasks.manifest import load_tasks
from whetstone.verify.task import Task

#: The pre-committed rule, fixed before any split is computed (spec AC1): three difficulty
#: terciles over the source-B corpus, a floor of ten held-out tasks and two per band, and the
#: per-band take of `max(MIN_PER_BAND, ceil(MIN_HELDOUT / HELDOUT_BANDS))`. Widening after
#: seeing the corpus is post-hoc selection; the frozen test pins these numbers to the spec's.
HELDOUT_BANDS = 3
MIN_HELDOUT = 10
MIN_PER_BAND = 2

#: The split seed — a declared constant, never a flag: the per-band order is
#: `sha256(SPLIT_SEED, task_id)`, so any reader holding the document and the seed can
#: re-derive the membership from the corpus (the stratum determinism precedent).
SPLIT_SEED = "whetstone-heldout-source-b-v1"

#: The per-band take, derived from the floors: `max(MIN_PER_BAND, ceil(MIN_HELDOUT / BANDS))`.
_PER_BAND_TAKE = max(MIN_PER_BAND, math.ceil(MIN_HELDOUT / HELDOUT_BANDS))

#: The committed difficulty source the door reads: the stratum document over the same
#: source-B corpus. Consumed through the stratum module's own fail-closed loader.
STRATUM_DOCUMENT = Path("tasks/stratum/easier.json")

#: The rule's declared parameters, as the document carries them and the `rule_digest` hashes
#: them — any edit to a constant invalidates every committed document by design (spec AC1).
_RULE_PARAMETERS = {
    "bands": HELDOUT_BANDS,
    "min_heldout": MIN_HELDOUT,
    "min_per_band": MIN_PER_BAND,
    "split_seed": SPLIT_SEED,
}


# --------------------------------------------------------------------------------------------
# The rule: the ordering key, the tercile band, and the per-band selection.
# --------------------------------------------------------------------------------------------


def difficulty_key(difficulty: Difficulty) -> tuple[int, int, int]:
    """The ordering key: the stratum measurement, in the spec's own order — files, hunks,
    added+deleted — never a derived scalar.

    A weighted sum would be a new difficulty axis invented beside the one the stratum rule
    measures; this is the same three components, in the order the spec names them
    (`spec.md`: "files / hunks / added+deleted"), so the banding is the measurement, not a
    reading of it.
    """
    return (difficulty.files, difficulty.hunks, difficulty.added + difficulty.deleted)


def band_of(task_id: str, difficulty: Mapping[str, Difficulty], corpus: Sequence[str]) -> int:
    """The tercile band of one measured task: its position in `corpus` ordered by the stratum
    difficulty key, cut into `HELDOUT_BANDS` contiguous terciles.

    The corpus is ordered by `(difficulty_key, task_id)` — the id breaks ties deterministically
    — and the cut is the standard chunking: `base` per band, the first `extra` bands taking one
    more. For the 66-task corpus that is three terciles of 22.
    """
    if task_id not in difficulty:
        raise ValueError(
            f"task {task_id!r} has no measured difficulty, so it cannot be banded"
        )
    ordered = sorted(corpus, key=lambda one: (difficulty_key(difficulty[one]), one))
    try:
        index = ordered.index(task_id)
    except ValueError as exc:
        raise ValueError(
            f"task {task_id!r} is not among the {len(ordered)} tasks being banded"
        ) from exc
    size = len(ordered)
    base, extra = divmod(size, HELDOUT_BANDS)
    for band in range(HELDOUT_BANDS):
        band_size = base + (1 if band < extra else 0)
        if index < band_size:
            return band
        index -= band_size
    raise AssertionError("unreachable: the tercile cut must cover every index")


def select_band(ids: Sequence[str]) -> tuple[str, ...]:
    """The held-out draw from one band: `_PER_BAND_TAKE` ids in `sha256(SPLIT_SEED, id)` order.

    **sha256, not `hash`.** The builtin is salted per process, so a derivation built on it
    would make the split's determinism a claim about `PYTHONHASHSEED` — recomputable by
    anyone holding the document and the seed, like `sampling.attempt_seed`
    (`sampling.py:100-119`). The fields are joined with a separator that cannot occur in a
    task id.
    """
    ordered = sorted(
        ids,
        key=lambda task_id: hashlib.sha256(
            f"{SPLIT_SEED}\n{task_id}".encode()
        ).hexdigest(),
    )
    return tuple(ordered[:_PER_BAND_TAKE])


#: The functions whose source IS the rule, for the drift guard. Scoped to the rule rather
#: than the module's I/O: a loader-only edit (an error-message change) must not refuse the
#: committed document, while any edit to the ordering, the banding or the selection must.
_RULE_FUNCTIONS = (difficulty_key, band_of, select_band)


def rule_digest() -> str:
    """The digest of the rule as it stands: the rule functions' source plus the parameters.

    Hashes `inspect.getsource` of the rule functions and a canonical JSON rendering of the
    declared parameters (the stratum shape, `stratum.py:269-283`). The held-out document
    records it, and the loader refuses a document whose digest no longer matches the
    module's — any rule-source or constant edit breaks the pairing, which is the rule-drift
    guard.
    """
    hasher = hashlib.sha256()
    for function in _RULE_FUNCTIONS:
        hasher.update(inspect.getsource(function).encode("utf-8"))
    hasher.update(
        json.dumps(_RULE_PARAMETERS, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return hasher.hexdigest()


# --------------------------------------------------------------------------------------------
# The held-out document: schema `whetstone-heldout/1`, deterministic writer, fail-closed
# loader. The three loader refusals are defined here because the run-side consumers (aspects 2
# and 3) import them by identity.
# --------------------------------------------------------------------------------------------

#: Names the shape of the file so a later format change is a visible one rather than a silent
#: reinterpretation of an old file by new code (the stratum schema discipline).
HELDOUT_SCHEMA = "whetstone-heldout/1"

#: The fields the `document_digest` covers — the canonical payload of everything except the
#: digest itself.
_DIGESTED_FIELDS = (
    "schema",
    "rule_digest",
    "rule",
    "corpus",
    "difficulty",
    "bands",
    "refusals",
    "membership",
)

#: Every field schema `whetstone-heldout/1` may carry. Anything else is an unknown field: a
#: hand-edited or miswritten document, refused by name rather than silently read past.
_KNOWN_FIELDS = frozenset({*_DIGESTED_FIELDS, "document_digest"})


class HeldoutSchemaError(ValueError):
    """The document is not schema `whetstone-heldout/1` — unknown schema, field or shape."""


class EmptyHeldout(ValueError):
    """The split is degenerate: empty, whole-corpus, or below the pre-committed floors."""


class HeldoutDigestMismatch(ValueError):
    """The document's digest does not match its payload, or the rule's has moved on."""


@dataclass(frozen=True)
class Rule:
    """The rule's declared parameters as the document carries them. The module constants are
    the source; the digest over them is what makes an edit invalidate the document."""

    bands: int
    min_heldout: int
    min_per_band: int
    split_seed: str


@dataclass(frozen=True)
class Heldout:
    """A parsed, validated held-out document — the shape the gate and the night consume.

    `schema` is carried rather than assumed, `document_digest` is not carried at all: the
    loader's checks are the gate, and a consumer that re-checked the digest would be a second
    answer to "is this document trustworthy" with only one of them reviewed. `difficulty`
    reuses the stratum module's `Difficulty` by identity — one definition of the axis.
    """

    schema: str
    rule_digest: str
    rule: Rule
    corpus: tuple[str, ...]
    difficulty: Mapping[str, Difficulty]
    bands: Mapping[str, int]
    refusals: Mapping[str, str]
    membership: tuple[str, ...]


def document_digest_of(document: Mapping[str, Any]) -> str:
    """The digest over the canonical payload of the other fields — the stratum shape.

    Canonical JSON — sorted keys, no whitespace — so the digest is a pure function of the
    payload. The loader's mechanically-required check: a hand-edited membership, band or
    value breaks it, and the loader refuses rather than trusts.
    """
    payload = {key: document[key] for key in _DIGESTED_FIELDS}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _refuse_unmet_floors(
    membership: Sequence[str], bands: Mapping[str, int], *, where: str
) -> None:
    """The pre-committed floors, shared by writer and loader: total and per-band minima.

    One definition of "can this split be used at all": the writer refuses before writing and
    the loader refuses before consuming, so a degenerate document can never become a pinned
    input. The refusal names the unmet floor — the response is the § 7.1 finding, never a
    loosened constant.
    """
    total = len(membership)
    if total < MIN_HELDOUT:
        raise EmptyHeldout(
            f"{where} holds out {total} tasks, below the pre-committed floor of "
            f"{MIN_HELDOUT} (MIN_HELDOUT). The split cannot meet the rule, so the response is "
            "the § 7.1 finding, never a looser floor"
        )
    for band in range(HELDOUT_BANDS):
        count = sum(1 for task_id in membership if bands.get(task_id) == band)
        if count < MIN_PER_BAND:
            raise EmptyHeldout(
                f"{where} holds out {count} tasks from band {band}, below the pre-committed "
                f"per-band floor of {MIN_PER_BAND} (MIN_PER_BAND). The split cannot meet the "
                "rule, so the response is the § 7.1 finding, never a looser floor"
            )


def compose_document(tasks: Sequence[Task], stratum_document: Stratum) -> dict[str, Any]:
    """The document for `tasks` under the stratum document's difficulty: every field except
    nothing, digest included.

    Sorted ids, sorted keys, no timestamp: two calls over one corpus are byte-identical,
    which is the recomputation test's premise. A task the stratum document refused carries a
    refusal here — never a guessed band — and an empty corpus, an empty membership, a
    whole-corpus membership or an unmet floor is refused by name: the vacuous-pass lie
    (`manifest.py:70-75`), each wearing its own spelling.
    """
    ids = [task.task_id for task in tasks]
    if not ids:
        raise ValueError(
            "the held-out corpus is empty: no task manifests were loaded, and a split over "
            "nothing would be a split nobody chose"
        )
    duplicates = sorted({task_id for task_id in ids if ids.count(task_id) > 1})
    if duplicates:
        raise ValueError(
            f"the held-out corpus repeats task id {duplicates!r}; two manifests naming one "
            f"task would make the membership ambiguous"
        )

    measured: dict[str, Difficulty] = {}
    refusals: dict[str, str] = {}
    for task_id in ids:
        difficulty = stratum_document.difficulty.get(task_id)
        if difficulty is None:
            refusals[task_id] = (
                "the stratum document carries no difficulty for this task, so it cannot be "
                "banded; a task that cannot be banded cannot be held out"
            )
        else:
            measured[task_id] = difficulty

    bands = {task_id: band_of(task_id, measured, list(measured)) for task_id in measured}

    membership: list[str] = []
    for band in range(HELDOUT_BANDS):
        members = sorted(task_id for task_id, b in bands.items() if b == band)
        membership.extend(select_band(members))

    if not membership:
        raise EmptyHeldout(
            "the rule produced an empty membership: no loaded task has a measured difficulty, "
            "so nothing can be held out. A split of nothing is a usage error, never a vacuous "
            "pass — record it as a finding; do not loosen the rule after seeing the corpus"
        )
    if set(membership) == set(ids):
        raise EmptyHeldout(
            "the rule selected the whole declared corpus: every measured task falls inside the "
            "per-band take, so \"held out\" is not a split but the corpus itself. A degenerate "
            "membership is a usage error, never a silent widening"
        )
    _refuse_unmet_floors(
        membership, bands, where="the rule's membership"
    )

    document: dict[str, Any] = {
        "schema": HELDOUT_SCHEMA,
        "rule_digest": rule_digest(),
        "rule": dict(_RULE_PARAMETERS),
        "corpus": sorted(ids),
        "difficulty": {
            task_id: {
                "files": d.files,
                "hunks": d.hunks,
                "added": d.added,
                "deleted": d.deleted,
                "f2p": d.f2p,
                "pins": d.pins,
                "blobs": d.blobs,
            }
            for task_id, d in sorted(measured.items())
        },
        "bands": dict(sorted(bands.items())),
        "refusals": dict(sorted(refusals.items())),
        "membership": membership,
    }
    document["document_digest"] = document_digest_of(document)
    return document


def write_document(
    out: Path, tasks: Sequence[Task], stratum_document: Stratum
) -> None:
    """Write the held-out document for `tasks`, deterministically, with a trailing newline.

    The committed file diffs line by line: indented, sorted keys, no timestamp — the same
    reviewable shape as the ledger (`ledger.py:155-165`).
    """
    document = compose_document(tasks, stratum_document)
    location = Path(out)
    location.parent.mkdir(parents=True, exist_ok=True)
    location.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")


def read_document(path: Path) -> Heldout:
    """Read and validate a held-out document, or refuse it by name.

    Fail-closed like the stratum loader (`stratum.py:478-649`): a document that half-parsed
    would let the gate score a membership the document's own fields do not support. The
    checks are the named refusals — unknown schema, an unknown field, digest mismatches (the
    rule's, then the document's), a duplicated membership, a membership naming a refused
    task, an id the document neither measured nor refused, and a degenerate membership —
    plus `ValueError` for a file that cannot be read at all.
    """
    location = Path(path)
    try:
        raw = json.loads(location.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"held-out document {str(location)!r} could not be read: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise HeldoutSchemaError(
            f"held-out document {str(location)!r} must be a JSON object, "
            f"got {type(raw).__name__}"
        )

    if raw.get("schema") != HELDOUT_SCHEMA:
        raise HeldoutSchemaError(
            f"held-out document {str(location)!r} declares schema {raw.get('schema')!r}, "
            f"but this module reads {HELDOUT_SCHEMA!r}; an old-schema document fails decode "
            "rather than defaulting"
        )

    unexpected = sorted(set(raw) - _KNOWN_FIELDS)
    if unexpected:
        raise HeldoutSchemaError(
            f"held-out document {str(location)!r} carries unknown field {unexpected!r}; a "
            "field this module does not read would be trusted by nobody and read by no one, "
            "and a document that cannot be read as the shape it claims is not a document the "
            "gate trusts"
        )

    if raw.get("rule_digest") != rule_digest():
        raise HeldoutDigestMismatch(
            f"held-out document {str(location)!r} was sealed under a different rule: its "
            f"rule digest {raw.get('rule_digest')!r} does not match the module's current "
            f"{rule_digest()!r}. Any rule-source or constant edit invalidates the committed "
            "document by design; regenerate it in the same commit as the edit"
        )

    _require(raw, "rule", dict, location)
    _require(raw, "corpus", list, location)
    _require(raw, "difficulty", dict, location)
    _require(raw, "bands", dict, location)
    _require(raw, "refusals", dict, location)
    _require(raw, "membership", list, location)
    _require(raw, "document_digest", str, location)

    rule_raw = raw["rule"]
    rule = Rule(
        bands=_int_field(rule_raw, "bands", location),
        min_heldout=_int_field(rule_raw, "min_heldout", location),
        min_per_band=_int_field(rule_raw, "min_per_band", location),
        split_seed=_str_field(rule_raw, "split_seed", location),
    )

    corpus = tuple(_str_list(raw["corpus"], "corpus", location))
    membership = tuple(_str_list(raw["membership"], "membership", location))

    difficulty: dict[str, Difficulty] = {}
    for task_id, counts in raw["difficulty"].items():
        if not isinstance(task_id, str) or not isinstance(counts, dict):
            raise HeldoutSchemaError(
                f"held-out document {str(location)!r} has a malformed difficulty entry; "
                "each entry must be a task id mapping to its counts"
            )
        difficulty[task_id] = Difficulty(
            files=_int_field(counts, "files", location),
            hunks=_int_field(counts, "hunks", location),
            added=_int_field(counts, "added", location),
            deleted=_int_field(counts, "deleted", location),
            f2p=_int_field(counts, "f2p", location),
            pins=_int_field(counts, "pins", location),
            blobs=_int_field(counts, "blobs", location),
        )

    bands: dict[str, int] = {}
    for task_id, band in raw["bands"].items():
        if not isinstance(task_id, str):
            raise HeldoutSchemaError(
                f"held-out document {str(location)!r} has a non-string band key "
                f"({task_id!r})"
            )
        if not isinstance(band, int):
            raise HeldoutSchemaError(
                f"held-out document {str(location)!r} has a non-int band value "
                f"({band!r}) for {task_id!r}"
            )
        bands[task_id] = band

    refusals: dict[str, str] = {}
    for task_id, reason in raw["refusals"].items():
        if not isinstance(task_id, str) or not isinstance(reason, str):
            raise HeldoutSchemaError(
                f"held-out document {str(location)!r} has a malformed refusal; each entry "
                "must be a task id mapping to a reason string"
            )
        refusals[task_id] = reason

    ids = set(corpus)
    measured_ids = set(difficulty)
    for task_id in membership:
        if task_id not in ids:
            raise HeldoutSchemaError(
                f"held-out document {str(location)!r} lists {task_id!r} in its membership, "
                "but the corpus never names that task; an unknown id is refused rather than "
                "silently scored by the gate"
            )
    for task_id in measured_ids | set(refusals):
        if task_id not in ids:
            raise HeldoutSchemaError(
                f"held-out document {str(location)!r} records difficulty or a refusal for "
                f"{task_id!r}, which is not in its corpus"
            )
    overlap = measured_ids & set(refusals)
    if overlap:
        raise HeldoutSchemaError(
            f"held-out document {str(location)!r} both measures and refuses "
            f"{sorted(overlap)!r}; a task cannot carry both"
        )
    uncovered = ids - measured_ids - set(refusals)
    if uncovered:
        raise HeldoutSchemaError(
            f"held-out document {str(location)!r} leaves {sorted(uncovered)!r} of its own "
            "corpus neither measured nor refused; a silently dropped task is a missing "
            "denominator"
        )
    if set(bands) != measured_ids:
        raise HeldoutSchemaError(
            f"held-out document {str(location)!r} bands {sorted(set(bands) ^ measured_ids)!r}, "
            "which do not match its measured tasks exactly; every measured task needs a band "
            "and every banded task must be measured"
        )

    duplicated = sorted({one for one in membership if membership.count(one) > 1})
    if duplicated:
        raise HeldoutSchemaError(
            f"held-out document {str(location)!r} repeats {duplicated!r} in its membership; "
            "a membership that cannot be read as a set is not the set the rule selected, and "
            "a gate that read it twice would score every member twice"
        )
    unmeasured = sorted(set(membership) - measured_ids)
    if unmeasured:
        raise HeldoutSchemaError(
            f"held-out document {str(location)!r} lists {unmeasured!r} in its membership, but "
            f"records a refusal for {unmeasured!r} rather than a difficulty; the membership "
            "must name exactly tasks the rule measured, and a refused task is not held out"
        )

    if not membership:
        raise EmptyHeldout(
            f"held-out document {str(location)!r} has an empty membership; a split of "
            "nothing is a usage error, never a vacuous pass"
        )
    if set(membership) == ids:
        raise EmptyHeldout(
            f"held-out document {str(location)!r} selects the whole declared corpus; "
            "\"held out\" must be a proper subset, or the split measures nothing new"
        )
    _refuse_unmet_floors(
        membership, bands, where=f"held-out document {str(location)!r}"
    )

    if raw.get("document_digest") != document_digest_of(raw):
        raise HeldoutDigestMismatch(
            f"held-out document {str(location)!r} carries a document_digest that does not "
            f"match its own payload: expected {document_digest_of(raw)}, got "
            f"{raw.get('document_digest')!r}. A hand-edited membership, band or value breaks "
            "the digest, and the loader refuses rather than trusts"
        )

    return Heldout(
        schema=raw["schema"],
        rule_digest=raw["rule_digest"],
        rule=rule,
        corpus=corpus,
        difficulty=difficulty,
        bands=bands,
        refusals=refusals,
        membership=membership,
    )


def _require(raw: dict[str, Any], key: str, kind: type[Any], location: Path) -> None:
    """One field, one type: a missing or wrong-typed field is a schema error, never a default."""
    if key not in raw:
        raise HeldoutSchemaError(
            f"held-out document {str(location)!r} is missing required field {key!r}"
        )
    if not isinstance(raw[key], kind):
        raise HeldoutSchemaError(
            f"held-out document {str(location)!r} has a non-{kind.__name__} {key} "
            f"({type(raw[key]).__name__})"
        )


def _int_field(raw: dict[str, Any], key: str, location: Path) -> int:
    """One int in a nested object: a missing or non-int value is a schema error."""
    value = raw.get(key)
    if not isinstance(value, int):
        raise HeldoutSchemaError(
            f"held-out document {str(location)!r} has a missing or non-int {key!r}"
        )
    return value


def _str_field(raw: dict[str, Any], key: str, location: Path) -> str:
    """One str in a nested object: a missing or non-str value is a schema error."""
    value = raw.get(key)
    if not isinstance(value, str):
        raise HeldoutSchemaError(
            f"held-out document {str(location)!r} has a missing or non-str {key!r}"
        )
    return value


def _str_list(values: list[Any], key: str, location: Path) -> tuple[str, ...]:
    """A list of task ids: one non-string entry is a schema error, never a silent drop."""
    for value in values:
        if not isinstance(value, str):
            raise HeldoutSchemaError(
                f"held-out document {str(location)!r} has a non-string entry in {key} "
                f"({type(value).__name__})"
            )
    return tuple(values)


def refuse_committed_out(out: Path) -> None:
    """Refuse an `--out` that passes through a gitignored data root.

    The document is the pre-committed pinned input: a split written under a gitignored data
    root is a split git history cannot prove predated the scoring. The root list is the
    stratum module's own (`stratum._LOCAL_OUT_ROOTS`, imported by identity — one definition
    of "what git cannot see"), and the refusal names the committable home. It is a refusal,
    never a rewrite: the operator's spelling is heard as given.
    """
    parts = out.resolve().parts
    for root in _LOCAL_OUT_ROOTS:
        root_parts = Path(root).parts
        if any(
            parts[i : i + len(root_parts)] == root_parts
            for i in range(len(parts) - len(root_parts) + 1)
        ):
            raise OutUnderLocalCorpus(
                f"the held-out document at {str(out)!r} sits under the gitignored root "
                f"{root!r}. The held-out split is the pre-committed pinned input the gate "
                "scores over, and a document git cannot see is a document git history cannot "
                "prove predated the run. Point --out at a committable path such as "
                "tasks/heldout/source-b.json"
            )


def main(argv: Sequence[str] | None = None) -> int:
    """The runbook door: `python -m whetstone.loop.heldout --corpus A [--corpus B ...] --out P`.

    Loads one directory of manifests per `--corpus` (the two-donor union shape), reads the
    committed stratum document at `STRATUM_DOCUMENT` through its own fail-closed loader, and
    writes the held-out document. `--out` is checked **before** anything is loaded — the
    refusal is about the artifact's home, and it must fire even against a corpus that would
    itself refuse. A degenerate split is exit 2 with the reason named; the committed document
    can never be degenerate.
    """
    parser = argparse.ArgumentParser(
        prog="python -m whetstone.loop.heldout",
        description=(
            "Compute the held-out source-B split over a corpus and write the committed "
            "document: schema whetstone-heldout/1, the rule digest, the declared constants, "
            "per-task difficulty and band, refusals, the membership, and the document digest. "
            "Offline: no model is loaded and no network is touched; the stratum document's "
            "difficulty is read, never recomputed."
        ),
    )
    parser.add_argument(
        "--corpus",
        action="append",
        required=True,
        type=Path,
        help="a directory of task manifests (repeatable; the roots are unioned)",
    )
    parser.add_argument(
        "--out", required=True, type=Path, help="where the document is written"
    )
    namespace = parser.parse_args(argv)

    out = namespace.out
    try:
        refuse_committed_out(out)
    except OutUnderLocalCorpus as exc:
        print(f"whetstone heldout: {exc}", file=sys.stderr)
        return 2

    tasks: list[Task] = []
    for root in namespace.corpus:
        try:
            tasks.extend(load_tasks(Path(root)))
        except ValueError as exc:
            print(f"whetstone heldout: {exc}", file=sys.stderr)
            return 2

    try:
        stratum_document = read_stratum_document(STRATUM_DOCUMENT)
    except ValueError as exc:
        print(
            f"whetstone heldout: the stratum document at {str(STRATUM_DOCUMENT)!r} could not "
            f"be read: {exc}",
            file=sys.stderr,
        )
        return 2

    try:
        write_document(out, tasks, stratum_document)
    except (EmptyHeldout, ValueError) as exc:
        print(f"whetstone heldout: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "HELDOUT_BANDS",
    "HELDOUT_SCHEMA",
    "MIN_HELDOUT",
    "MIN_PER_BAND",
    "SPLIT_SEED",
    "STRATUM_DOCUMENT",
    "EmptyHeldout",
    "Heldout",
    "HeldoutDigestMismatch",
    "HeldoutSchemaError",
    "Rule",
    "band_of",
    "compose_document",
    "difficulty_key",
    "document_digest_of",
    "main",
    "read_document",
    "read_stratum_document",
    "refuse_committed_out",
    "rule_digest",
    "select_band",
    "write_document",
]