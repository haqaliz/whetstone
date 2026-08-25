"""The held-out split rule and its writer: pre-committed, deterministic, meet-or-refuse.

The held-out document is the artifact `PREREGISTRATION.md` § 7.1 names open until P3, and its
whole value is the order of events: the rule is fixed **in code before the split is computed**,
the document is committed **before the split is used to score anything**, and a split that
cannot meet the rule is the § 7.1 published finding — never a criterion tuned after the fact
(`docs/planning/p3-promotion-gate/heldout/spec.md`). This file tests the rule and the writer
half of that contract: the constants are the spec's, the banding reuses the stratum document's
per-task difficulty measurement as the ordering key (never a new axis), the per-band selection
is `sha256(split_seed, task_id)` — deterministic across processes, unlike the builtin `hash` —
and the writer refuses a degenerate split by name instead of writing one.

The difficulty source is the **committed stratum document**, consumed through its own
fail-closed loader by identity: a second implementation of "how hard is this task" would be a
second answer to the same question, with only one of them reviewed.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from whetstone.bakeoff import stratum
from whetstone.loop import heldout
from whetstone.verify.task import Task, load_task

#: A value that only exists inside a task's held test file. If it turns up anywhere in the
#: document, a file's contents did — which is the one thing the document may never carry
#: (the ledger-walk canary, `test_ledger.py:45-47`).
_CANARY = "canary-9f2c1e-the-users-own-source-line"

#: A string no legitimate field can contain: paths are the excluded class, and a committed
#: document carrying one has leaked a fact about the donor's layout.
_PATH_SHAPED = "src/calc.py"


def _task(root: Path, task_id: str) -> Task:
    """One manifest-only task: valid for `load_task`, no donor repository needed.

    The held-out writer reads exactly `task_id`; the fixture is the smallest manifest
    `whetstone.verify.task.load_task` accepts (the `fixtures/repos` shapes, minus the
    two-commit donor these tests never touch).
    """
    manifest = {
        "task_id": task_id,
        "source": "private",
        "repo_url": str(root / "donor"),
        "base_commit": "0" * 40,
        "environment": {"python": "3.12", "pins": [], "import_roots": ["."]},
        "problem_statement": "Fix the bug",
        "fail_to_pass": ["tests/test_addition.py::test_add_is_addition"],
        "pass_to_pass": ["tests/test_addition.py::test_adding_zero_is_the_identity"],
        "test_blobs": {
            "tests/test_addition.py": base64.b64encode(_CANARY.encode("utf-8")).decode("ascii")
        },
        "provenance": {"donor": "donor", "commit": "0" * 40, "parent": "0" * 40},
    }
    path = root / f"{task_id}.json"
    path.write_text(json.dumps(manifest))
    return load_task(path)


def _difficulty(files: int, hunks: int, added: int, deleted: int) -> dict[str, int]:
    """A full seven-field stratum difficulty entry, with the ordering key under test's control."""
    return {
        "files": files,
        "hunks": hunks,
        "added": added,
        "deleted": deleted,
        "f2p": 1,
        "pins": 0,
        "blobs": 1,
    }


def _stratum_document(
    root: Path, measured: Mapping[str, dict[str, int]], refused: Sequence[str] = ()
) -> Path:
    """A synthetic stratum document over `measured` (and refused) ids, parseable by its loader.

    Carries the module's current rule digest and a freshly computed document digest, so
    `stratum.read_document` accepts it and the held-out writer can consume the parsed shape
    exactly as it consumes the committed document on the machine.
    """
    raw = {
        "schema": stratum.STRATUM_SCHEMA,
        "rule_digest": stratum.rule_digest(),
        "band": {"max_non_test_files": 1, "max_hunks": 2, "max_changed_lines": 30},
        "corpus": sorted([*measured, *refused]),
        "difficulty": dict(measured),
        "refusals": {task_id: "synthetic refusal" for task_id in refused},
        "membership": list(measured)[:1],
    }
    raw["document_digest"] = stratum.document_digest_of(raw)
    path = root / "stratum.json"
    path.write_text(json.dumps(raw))
    return path


def _parse_stratum(root: Path, **kwargs: object) -> stratum.Stratum:
    """The parsed synthetic stratum document, via the stratum module's own fail-closed loader."""
    return stratum.read_document(_stratum_document(root, **kwargs))


def _corpus(
    root: Path,
    measured: Mapping[str, tuple[int, int, int, int]],
    refused: Sequence[str] = (),
) -> tuple[tuple[Task, ...], stratum.Stratum]:
    """A task corpus plus a stratum document measuring (or refusing) exactly those tasks."""
    keys = {task_id: _difficulty(*counts) for task_id, counts in measured.items()}
    tasks = tuple(_task(root, task_id) for task_id in [*measured, *refused])
    return tasks, _parse_stratum(root, measured=keys, refused=refused)


#: The standard rule-meeting corpus: 12 measured tasks in three clear difficulty terciles
#: (4/4/4) and 3 tasks the stratum document refuses, so the writer's floors are met and the
#: refusal path is exercised at the same time.
_STANDARD_MEASURED = {
    "t-00": (1, 1, 1, 0),
    "t-01": (1, 1, 1, 0),
    "t-02": (1, 1, 1, 0),
    "t-03": (1, 1, 1, 0),
    "t-04": (2, 2, 2, 0),
    "t-05": (2, 2, 2, 0),
    "t-06": (2, 2, 2, 0),
    "t-07": (2, 2, 2, 0),
    "t-08": (3, 3, 3, 0),
    "t-09": (3, 3, 3, 0),
    "t-10": (3, 3, 3, 0),
    "t-11": (3, 3, 3, 0),
}
_STANDARD_REFUSED = ("t-12", "t-13", "t-14")


def _seed_sorted(ids: Sequence[str]) -> list[str]:
    """The rule's own per-band order, re-derived in the test from the declared seed."""
    return sorted(
        ids, key=lambda task_id: hashlib.sha256(
            f"{heldout.SPLIT_SEED}\n{task_id}".encode()
        ).hexdigest()
    )


def _manifest_dir(root: Path, ids: Sequence[str]) -> Path:
    """A directory of manifests the door's `--corpus` can load."""
    directory = root / "corpus"
    directory.mkdir()
    for task_id in ids:
        _task(directory, task_id)
    return directory


def test_the_pre_committed_rule_is_the_specs() -> None:
    """The constants are pinned to the spec's numbers, the way the stratum band was pinned.

    `docs/planning/p3-promotion-gate/heldout/spec.md` fixes `HELDOUT_BANDS = 3`,
    `MIN_HELDOUT = 10`, `MIN_PER_BAND = 2`, and the per-band take of
    `max(MIN_PER_BAND, ceil(MIN_HELDOUT / 3))`. Widening after seeing the corpus is post-hoc
    selection, and the frozen test is what makes the edit visible.
    """
    assert (heldout.HELDOUT_BANDS, heldout.MIN_HELDOUT, heldout.MIN_PER_BAND) == (3, 10, 2)
    assert max(heldout.MIN_PER_BAND, math.ceil(heldout.MIN_HELDOUT / heldout.HELDOUT_BANDS)) == 4


def test_the_writer_meets_the_pre_committed_rule(tmp_path: Path) -> None:
    """AC1: the written document's membership meets the floors, and matches a re-derivation.

    The expected membership is computed in the test from the declared seed and the band
    assignment — an independent re-derivation, not a restatement of the module's own answer —
    and asserted equal to the document's.
    """
    tasks, document = _corpus(tmp_path, _STANDARD_MEASURED, _STANDARD_REFUSED)
    out = tmp_path / "heldout" / "source-b.json"

    heldout.write_document(out, tasks, document)

    raw = json.loads(out.read_text())
    membership = raw["membership"]
    bands = raw["bands"]

    assert raw["schema"] == heldout.HELDOUT_SCHEMA
    per_band = [sum(1 for task_id in membership if bands[task_id] == band) for band in range(3)]
    assert len(membership) >= heldout.MIN_HELDOUT, (
        "the split must hold out at least MIN_HELDOUT tasks: "
        f"{len(membership)} < {heldout.MIN_HELDOUT}"
    )
    assert all(count >= heldout.MIN_PER_BAND for count in per_band), (
        f"every band must contribute at least MIN_PER_BAND: {per_band}"
    )

    expected: list[str] = []
    take = max(heldout.MIN_PER_BAND, math.ceil(heldout.MIN_HELDOUT / heldout.HELDOUT_BANDS))
    for band in range(heldout.HELDOUT_BANDS):
        members = [task_id for task_id, b in bands.items() if b == band]
        expected.extend(_seed_sorted(members)[:take])
    assert membership == expected, (
        "the document's membership is not the sha256(split_seed, task_id) selection the rule "
        "declares; the recomputation test would catch drift on the machine, and this pins it "
        "on synthetic corpora everywhere"
    )


def test_banding_uses_the_stratum_difficulty_ordering(tmp_path: Path) -> None:
    """The ordering key is the stratum document's measurement, never a new difficulty axis.

    The document's per-task bands must agree with terciles over exactly (files, hunks,
    added + deleted) — the spec's own three components — re-derived in the test from the
    document's own difficulty field.
    """
    tasks, document = _corpus(tmp_path, _STANDARD_MEASURED, _STANDARD_REFUSED)
    out = tmp_path / "heldout" / "source-b.json"

    heldout.write_document(out, tasks, document)

    raw = json.loads(out.read_text())
    ordered = sorted(
        raw["difficulty"],
        key=lambda task_id: (
            (
                raw["difficulty"][task_id]["files"],
                raw["difficulty"][task_id]["hunks"],
                raw["difficulty"][task_id]["added"] + raw["difficulty"][task_id]["deleted"],
            ),
            task_id,
        ),
    )
    for band in range(heldout.HELDOUT_BANDS):
        for task_id in ordered[band * 4 : (band + 1) * 4]:
            assert raw["bands"][task_id] == band, (
                f"{task_id} landed in band {raw['bands'][task_id]}, but its difficulty key "
                f"falls in tercile {band} of the stratum ordering"
            )


def test_band_of_orders_by_files_first_never_a_weighted_sum() -> None:
    """Lexicographic (files, hunks, added+deleted): a one-file giant fix is easier than a
    two-file one-line fix, because that is the stratum measurement's own order — a derived
    scalar (a sum, a product) would be a new axis the spec forbids."""
    difficulty = {
        "a": stratum.Difficulty(
            files=1, hunks=100, added=1000, deleted=1000, f2p=1, pins=0, blobs=1
        ),
        "b": stratum.Difficulty(
            files=2, hunks=1, added=1, deleted=0, f2p=1, pins=0, blobs=1
        ),
    }

    assert heldout.band_of("a", difficulty, ["a", "b"]) == 0
    assert heldout.band_of("b", difficulty, ["a", "b"]) == 1


def test_two_writes_over_one_corpus_are_byte_identical(tmp_path: Path) -> None:
    """Determinism is the recomputation test's premise: no timestamp, no clock, no order."""
    tasks, document = _corpus(tmp_path, _STANDARD_MEASURED, _STANDARD_REFUSED)
    first, second = tmp_path / "one.json", tmp_path / "two.json"

    heldout.write_document(first, tasks, document)
    heldout.write_document(second, tasks, document)

    assert first.read_bytes() == second.read_bytes()
    assert "timestamp" not in json.loads(first.read_text()), (
        "a write-moment clock would make byte-equality impossible by construction"
    )


def test_the_writer_refuses_an_empty_corpus_by_name(tmp_path: Path) -> None:
    """No manifests, no document: an empty set is a malformed invocation, never a split."""
    document = _parse_stratum(
        tmp_path,
        measured={
            "other-a": _difficulty(1, 1, 1, 0),
            "other-b": _difficulty(2, 2, 2, 0),
        },
    )

    with pytest.raises(ValueError, match="empty"):
        heldout.write_document(tmp_path / "source-b.json", (), document)


def test_the_writer_refuses_a_split_that_cannot_meet_the_floors(tmp_path: Path) -> None:
    """A band too small to meet its floor is the § 7.1 finding, refused by name (spec AC1).

    Nine measured tasks arrange as 3/3/3 across the terciles: the selection totals nine,
    below `MIN_HELDOUT`, so the split cannot meet the rule. The refusal names the floor
    rather than tuning it.
    """
    tasks, document = _corpus(
        tmp_path,
        {f"t-{i:02d}": (1, 1, 1, 0) for i in range(9)},
        tuple(f"t-{i:02d}" for i in range(9, 15)),
    )

    with pytest.raises(heldout.EmptyHeldout) as caught:
        heldout.write_document(tmp_path / "source-b.json", tasks, document)

    assert "floor" in str(caught.value).lower(), (
        f"the refusal must name the unmet floor: {caught.value}"
    )


def test_the_writer_refuses_empty_membership_by_name(tmp_path: Path) -> None:
    """A split of nothing is a vacuous pass wearing the held-out split's name.

    The loaded corpus and the difficulty source disagree entirely: the stratum document
    measures other ids, so every loaded task is refused and nothing can be held out.
    """
    other = _parse_stratum(
        tmp_path,
        measured={
            "other-a": _difficulty(1, 1, 1, 0),
            "other-b": _difficulty(2, 2, 2, 0),
        },
    )
    tasks = tuple(_task(tmp_path, task_id) for task_id in ("t-00", "t-01", "t-02"))

    with pytest.raises(heldout.EmptyHeldout) as caught:
        heldout.write_document(tmp_path / "source-b.json", tasks, other)

    assert "empty" in str(caught.value).lower(), (
        f"the refusal must name the empty membership: {caught.value}"
    )


def test_the_writer_refuses_whole_corpus_membership_by_name(tmp_path: Path) -> None:
    """The whole declared set is not a held-out split: held out must mean held back."""
    tasks, document = _corpus(tmp_path, _STANDARD_MEASURED)

    with pytest.raises(heldout.EmptyHeldout) as caught:
        heldout.write_document(tmp_path / "source-b.json", tasks, document)

    assert "whole" in str(caught.value).lower(), (
        f"the refusal must name the whole-corpus membership: {caught.value}"
    )


def test_the_door_consumes_the_stratum_document_through_its_own_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One definition of "how hard is this task": the stratum module's own fail-closed loader.

    The door must never re-read a raw stratum file: it consumes the parsed `Stratum`, which
    only `stratum.read_document` produces. Asserted by replacing the stratum loader with a
    recorder — a door that bypassed it would never call it.
    """
    assert heldout.read_stratum_document is stratum.read_document, (
        "the identity import was replaced by a copy, and the two could drift apart"
    )
    corpus_dir = _manifest_dir(tmp_path, [*_STANDARD_MEASURED, *_STANDARD_REFUSED])
    measured = {task_id: _difficulty(*counts) for task_id, counts in _STANDARD_MEASURED.items()}
    monkeypatch.setattr(
        heldout, "STRATUM_DOCUMENT", _stratum_document(tmp_path, measured, _STANDARD_REFUSED)
    )
    calls: list[object] = []
    real = stratum.read_document

    def recording(path: Path) -> stratum.Stratum:
        calls.append(path)
        return real(path)

    monkeypatch.setattr(heldout, "read_stratum_document", recording)

    rc = heldout.main(
        [
            "--corpus",
            str(corpus_dir),
            "--out",
            str(tmp_path / "heldout" / "source-b.json"),
        ]
    )

    assert rc == 0
    assert calls, "the door never read the stratum document through its fail-closed loader"


def test_the_digest_algorithm_is_the_stratum_shape() -> None:
    """`document_digest_of` is the stratum shape: canonical JSON, sha256, sorted keys.

    A second digest algorithm would be a second answer to "is this document trustworthy"
    with only one of them reviewed; the pinned equivalence is what keeps them one.
    """
    raw = {
        "schema": heldout.HELDOUT_SCHEMA,
        "rule_digest": "f" * 64,
        "rule": {"bands": 3, "min_heldout": 10, "min_per_band": 2, "split_seed": "seed"},
        "corpus": ["a"],
        "difficulty": {"a": _difficulty(1, 1, 1, 0)},
        "bands": {"a": 0},
        "refusals": {},
        "membership": ["a"],
    }
    payload = {key: raw[key] for key in heldout._DIGESTED_FIELDS}
    expected = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    assert heldout.document_digest_of(raw) == expected


def test_main_writes_the_document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The door `python -m whetstone.loop.heldout --corpus ... --out ...` writes the document."""
    corpus_dir = _manifest_dir(tmp_path, [*_STANDARD_MEASURED, *_STANDARD_REFUSED])
    measured = {task_id: _difficulty(*counts) for task_id, counts in _STANDARD_MEASURED.items()}
    monkeypatch.setattr(
        heldout, "STRATUM_DOCUMENT", _stratum_document(tmp_path, measured, _STANDARD_REFUSED)
    )
    out = tmp_path / "heldout" / "source-b.json"

    rc = heldout.main(["--corpus", str(corpus_dir), "--out", str(out)])

    assert rc == 0
    raw = json.loads(out.read_text())
    assert raw["schema"] == heldout.HELDOUT_SCHEMA
    assert len(raw["membership"]) >= heldout.MIN_HELDOUT


def test_main_refuses_an_out_under_the_local_corpus(tmp_path: Path) -> None:
    """The document is a committed pinned input; `tasks/local/` is where git never sees it."""
    corpus_dir = _manifest_dir(tmp_path, ("t-00", "t-01"))

    rc = heldout.main(
        [
            "--corpus",
            str(corpus_dir),
            "--out",
            str(tmp_path / "tasks" / "local" / "source-b.json"),
        ]
    )

    assert rc == 2
    assert not (tmp_path / "tasks" / "local" / "source-b.json").exists()


def test_main_refuses_a_degenerate_split_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A split that cannot meet the rule exits 2 and writes nothing — the finding is next."""
    measured = {f"t-{i:02d}": (1, 1, 1, 0) for i in range(9)}
    corpus_dir = _manifest_dir(tmp_path, [*measured, *[f"t-{i:02d}" for i in range(9, 15)]])
    monkeypatch.setattr(
        heldout,
        "STRATUM_DOCUMENT",
        _stratum_document(
            tmp_path,
            {task_id: _difficulty(*counts) for task_id, counts in measured.items()},
            tuple(f"t-{i:02d}" for i in range(9, 15)),
        ),
    )
    out = tmp_path / "heldout" / "source-b.json"

    rc = heldout.main(["--corpus", str(corpus_dir), "--out", str(out)])

    assert rc == 2
    assert not out.exists()