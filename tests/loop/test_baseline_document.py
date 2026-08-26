"""The § 3 baseline document's fail-closed reader: `read_baseline_document`.

`PREREGISTRATION.md` § 3's baseline is measured once, re-measured never, and the loader is
the read side of that discipline: a document an outside reader hand-edited — a count
changed without the digest regenerated — is refused by name, never trusted. The loader
lives in `loop/baseline.py` beside `read_series_identity` and composes it **by identity**
(the loop→bakeoff direction: `bakeoff.report` must never import `loop.baseline`), and it
reads the writer's own schema, count-shape and digest constants from `bakeoff.report` by
identity.

Nothing here runs a model, a sandbox, a verifier, or the network; every document is the
writer's own output over the synthetic records `tests/bakeoff/test_baseline_report.py`
builds, written to `tmp_path` and read back from disk.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from bakeoff.test_baseline_report import (
    HELDOUT_DENOMINATOR,
    RECORDED_ON,
    SERIES,
    _declaration,
    _document,
)

from whetstone.bakeoff import report
from whetstone.loop import baseline as baseline_module


def _written(tmp_path: Path, document: object) -> Path:
    """Write `document` through the writer and return the sidecar's path."""
    return report.write_baseline_report(document, tmp_path / "home")[1]


def _raw(tmp_path: Path, document: object) -> Path:
    """Write a malformed document directly as `report.json` — the writer would never
    produce it, and the loader's job is to refuse documents no writer produced."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    sidecar = tmp_path / "report.json"
    sidecar.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return sidecar


def test_the_loader_accepts_a_writer_round_trip(tmp_path: Path) -> None:
    """AC 4: write via the writer, read via the loader — fields verbatim, state preserved.

    The loader is the writer's read side: every field the P4 report writer will need
    survives the round trip unchanged, and `measured` — the one field that decides whether
    a count may be read at all — is preserved in both directions: a measured document
    loads measured, a declaration loads declared, never the other way.
    """
    document = _document()
    sidecar = _written(tmp_path / "measured", document)
    loaded = baseline_module.read_baseline_document(sidecar)

    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert loaded.schema == payload["schema"]
    assert loaded.recorded_on == RECORDED_ON
    assert loaded.series == SERIES
    assert loaded.base == payload["base"]
    assert loaded.sides == payload["sides"]
    assert loaded.n == payload["n"]
    assert loaded.retries == payload["retries"]
    assert loaded.evidence == payload["evidence"]
    assert loaded.tool_versions == payload["tool_versions"]
    assert loaded.measured is True

    declared_sidecar = _written(tmp_path / "declaration", _declaration())
    declared = baseline_module.read_baseline_document(declared_sidecar)
    assert declared.measured is False
    assert declared.series is None
    assert declared.sides is None
    assert declared.n is None
    assert declared.recorded_on == RECORDED_ON


def test_the_loader_refuses_a_hand_edited_document(tmp_path: Path) -> None:
    """A count changed without the digest regenerated is refused by name.

    This is the refusal the measured-once discipline's read side exists for: a hand edit
    that moves a count and leaves the digest stale is the edit that would quietly change
    what the baseline claims, and the loader refuses it rather than trusting it. The edit
    keeps the count an integer and inside the denominator, so only the seal can refuse.
    """
    document = dict(_document())
    document["sides"]["source-b"]["solved"] += 1
    sidecar = _written(tmp_path, document)

    with pytest.raises(ValueError) as refused:
        baseline_module.read_baseline_document(sidecar)

    message = str(refused.value)
    assert "document_digest" in message, refused.value
    assert "source-b" not in message, (
        "WHY THIS IS A FAILURE: the refusal names a count field, but the count is valid — "
        "only the stale seal may refuse"
    )


def test_the_loader_refuses_unknown_fields_missing_sources_and_bad_counts(
    tmp_path: Path,
) -> None:
    """Each malformed shape is refused by name — never read past, never defaulted.

    An unknown field would be trusted by nobody and read by no one; a wrong schema is not
    this document; a missing source breaks `PREREGISTRATION.md:142-143`'s both-sources-
    always rule; and a missing, non-integer or negative count cannot be a count at all.
    Each is its own named refusal. The documents are written directly, never through the
    writer — a malformed document is exactly what the writer refuses to produce, and the
    loader must still refuse it.
    """
    wrong_schema = dict(_document())
    wrong_schema["schema"] = "whetstone-baseline/2"
    with pytest.raises(ValueError) as refused:
        baseline_module.read_baseline_document(_raw(tmp_path / "schema", wrong_schema))
    assert "whetstone-baseline/2" in str(refused.value), refused.value

    unknown = dict(_document())
    unknown["bogus_field"] = "x"
    with pytest.raises(ValueError) as refused:
        baseline_module.read_baseline_document(_raw(tmp_path / "unknown", unknown))
    assert "bogus_field" in str(refused.value), refused.value

    missing_source = dict(_document())
    del missing_source["sides"]["source-a"]
    with pytest.raises(ValueError) as refused:
        baseline_module.read_baseline_document(_raw(tmp_path / "source", missing_source))
    assert "source-a" in str(refused.value), refused.value

    missing_count = dict(_document())
    del missing_count["sides"]["source-b"]["solved"]
    with pytest.raises(ValueError) as refused:
        baseline_module.read_baseline_document(_raw(tmp_path / "count", missing_count))
    assert "solved" in str(refused.value), refused.value

    non_integer = dict(_document())
    non_integer["sides"]["source-b"]["solved"] = "2"
    with pytest.raises(ValueError) as refused:
        baseline_module.read_baseline_document(_raw(tmp_path / "float", non_integer))
    assert "solved" in str(refused.value), refused.value

    negative = dict(_document())
    negative["sides"]["source-b"]["solved"] = -1
    with pytest.raises(ValueError) as refused:
        baseline_module.read_baseline_document(_raw(tmp_path / "negative", negative))
    assert "-1" in str(refused.value), refused.value


def test_the_loader_refuses_weaker_wins_over_its_own_denominator(tmp_path: Path) -> None:
    """`weaker_wins` above its own denominator is refused — with the digest regenerated.

    The count checks must each stand alone: the digest is recomputed with the writer's own
    function, so the ONLY check that can fire is the `weaker_wins`-over-denominator one,
    and the refusal must be attributable to exactly it.
    """
    document = dict(_document())
    document["sides"]["source-b"]["weaker_wins"] = HELDOUT_DENOMINATOR + 1
    document["document_digest"] = report._baseline_document_digest(document)
    sidecar = _written(tmp_path, document)

    with pytest.raises(ValueError) as refused:
        baseline_module.read_baseline_document(sidecar)

    message = str(refused.value)
    assert "weaker_wins" in message, refused.value
    assert "document_digest" not in message, (
        "WHY THIS IS A FAILURE: the digest was regenerated, so a digest refusal means the "
        "regeneration did not seal what the loader verifies"
    )


def test_the_series_read_and_schema_are_by_identity() -> None:
    """The loader composes `read_series_identity` and the writer's constants by identity.

    The loader could have re-implemented the series read or re-declared the schema and
    the seal — the day it did, a second answer to "what is this series", "what shape is
    this document" or "what is sealed" would exist with nothing to say so. The function
    object and the constants are the module's own, asserted `is`.
    """
    assert baseline_module._baseline_series_reader is baseline_module.read_series_identity, (
        "WHY THIS IS A FAILURE: the loader's series read is not `read_series_identity` — "
        "a second implementation of the series validation now exists"
    )
    assert baseline_module._baseline_schema is report.BASELINE_REPORT_SCHEMA, (
        "WHY THIS IS A FAILURE: the loader's schema constant is not the writer's own — a "
        "drift could let the loader read a schema the writer does not write"
    )
    assert baseline_module._baseline_document_digest is report._baseline_document_digest, (
        "WHY THIS IS A FAILURE: the loader recomputes the seal with its own digest "
        "function — the loader and the writer could disagree about what is sealed"
    )