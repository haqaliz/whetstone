"""The held-out split rule and its writer: pre-committed, deterministic, meet-or-refuse.

The held-out document is the artifact `PREREGISTRATION.md` § 7.1 names open until P3, and its
whole value is the order of events: the rule is fixed **in code before the split is computed**,
the document is committed **before the split is used to score anything**, and a split that
cannot meet the rule is the § 7.1 published finding — never a criterion tuned after the fact
(`docs/planning/p3-promotion-gate/heldout/spec.md`). This file tests the rule and the writer
half of that contract: the constants are the spec's, the banding reuses the stratum document's
per-task difficulty measurement as the ordering key (never a new axis), the per-band selection
is `sha256(split_seed, task_id)` — deterministic across processes, unlike the builtin `hash` —
and the writer refuses a degenerate split by name instead of writing one. Since the
oracle-predicate aspect, the draw runs over the scorable members only — the rule's own filter,
reached by identity — and the document records every task it excluded (`excluded`, digested)
while `corpus`/`difficulty`/`bands` keep covering the measured corpus entire.

The difficulty source is the **committed stratum document**, consumed through its own
fail-closed loader by identity: a second implementation of "how hard is this task" would be a
second answer to the same question, with only one of them reviewed.
"""

from __future__ import annotations

import base64
import hashlib
import inspect
import json
import math
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from fixtures.repos.mined import MINED_TESTS_AFTER, Mined, build_mined_task

from whetstone.bakeoff import sources as sources_module
from whetstone.bakeoff import stratum
from whetstone.loop import heldout
from whetstone.verify.task import Task, load_task

#: A string no legitimate field can contain: paths are the excluded class, and a committed
#: document carrying one has leaked a fact about the donor's layout.
_PATH_SHAPED = "src/calc.py"


def _mined(root: Path, *, task_id: str = "synthetic-mined-adder", bulk_chars: int = 0) -> Mined:
    """One materialised mined fixture under `root`: a two-commit donor and its task.

    The aspect-1 pattern (`test_oracle_fittable.py`): a donor with a parent and a child,
    and a manifest naming both — the smallest repository `oracle_fittable` can read.
    `bulk_chars` puts a non-test source file of roughly that many characters into the donor,
    so the task's oracle exceeds any budget smaller than it.
    """
    return build_mined_task(root, task_id=task_id, bulk_chars=bulk_chars)


def _manifest_for(root: Path, task_id: str, donor: Mined) -> Task:
    """A manifest naming `donor`'s repository, at `root/{task_id}.json`, loaded like `mine` would.

    The mined manifest shape (`fixtures/repos/mined.py`), with the task id and the donor's
    paths substituted. Several manifests can name one donor: the fixture's commits are
    deterministic, so a shared repository reads identically behind every manifest.
    """
    manifest = {
        "task_id": task_id,
        "source": "private",
        "repo_url": str(donor.donor),
        "base_commit": donor.parent,
        "environment": {"python": "3.12", "pins": [], "import_roots": ["."]},
        "problem_statement": "Fix addition",
        "fail_to_pass": ["tests/test_addition.py::test_add_is_addition"],
        "pass_to_pass": ["tests/test_addition.py::test_adding_zero_is_the_identity"],
        "test_blobs": {
            "tests/test_addition.py": base64.b64encode(MINED_TESTS_AFTER.encode("utf-8")).decode(
                "ascii"
            )
        },
        "provenance": {"donor": donor.donor.name, "commit": donor.commit, "parent": donor.parent},
    }
    path = root / f"{task_id}.json"
    path.write_text(json.dumps(manifest))
    return load_task(path)


def _task(root: Path, task_id: str, *, bulk_chars: int = 0) -> Task:
    """One mined task with a dedicated two-commit donor, under `root`.

    The draw's filter reads each task's donor, so a fixture task needs a real repository
    (the aspect-1 pattern, `test_oracle_fittable.py`). `bulk_chars` makes its oracle exceed
    the sealed budget — the unfittable class.
    """
    return _manifest_for(
        root,
        task_id,
        _mined(root / "donors" / task_id, task_id=task_id, bulk_chars=bulk_chars),
    )


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
    *,
    unfittable: Sequence[str] = (),
    dedicated: Sequence[str] = (),
) -> tuple[tuple[Task, ...], stratum.Stratum]:
    """A task corpus plus a stratum document measuring (or refusing) exactly those tasks.

    The scorable tasks share one fit donor — the fixture's two-commit repository is
    deterministic, so a shared repository reads identically behind every manifest —
    `unfittable` ids get the bulk donor whose oracle exceeds the sealed budget, and
    `dedicated` ids get donors of their own (the shapes a test must remove or replace).
    """
    keys = {task_id: _difficulty(*counts) for task_id, counts in measured.items()}
    fit = _mined(root / "donors" / "fit")
    bulk = None
    if unfittable:
        bulk = _mined(
            root / "donors" / "bulk", bulk_chars=sources_module.ORACLE_BUDGET_CHARS + 1_000
        )
    tasks = []
    for task_id in [*measured, *refused]:
        if task_id in dedicated:
            donor = _mined(root / "donors" / task_id, task_id=task_id)
        elif task_id in unfittable:
            assert bulk is not None
            donor = bulk
        else:
            donor = fit
        tasks.append(_manifest_for(root, task_id, donor))
    return tuple(tasks), _parse_stratum(root, measured=keys, refused=refused)


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
    """A directory of manifests the door's `--corpus` can load — one shared donor behind them.

    The donor lives outside the directory: `load_task_directory` refuses a non-manifest
    entry, and the fixture's commits are deterministic, so every manifest in the directory
    can name the same repository.
    """
    directory = root / "corpus"
    directory.mkdir()
    donor = _mined(root / "donors" / "fit")
    for task_id in ids:
        _manifest_for(directory, task_id, donor)
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
        "excluded": {},
        "refusals": {},
        "membership": ["a"],
    }
    payload = {key: raw[key] for key in heldout._DIGESTED_FIELDS}
    expected = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    assert heldout.document_digest_of(raw) == expected


def test_a_document_predating_excluded_still_seals_its_own_digest() -> None:
    """A pre-amendment document (no `excluded`) re-seals: a digest of what it carries, not a crash.

    `_DIGESTED_FIELDS` gained `excluded`, and documents written before the field existed — the
    synthetic fixtures other consumers build, and the committed document until it is
    regenerated — carry no such key. The digest covers the fields the document has, so such a
    document is still a document; a written document stripped of `excluded` still moves the
    digest, which is the fail-closed half.
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
    predating = heldout.document_digest_of(raw)

    raw["excluded"] = {}
    assert heldout.document_digest_of(raw) != predating, (
        "the presence of a digested field does not move the digest, so stripping `excluded` "
        "from a written document would be invisible"
    )


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


def test_the_scorable_filter_reaches_the_predicate_by_identity() -> None:
    """The filter is the bakeoff's own predicate, reached by identity, never a second rule.

    A copied budget check inside `heldout.py` would be a second rule with a different digest:
    the module's digest covers this wrapper's source, so the one thing that must be the
    bakeoff's own object is the predicate the wrapper calls. `__globals__` is where the
    wrapper's body resolves the name, so the pin is that resolution — the very object the
    bakeoff enforces (the aspect-1 pin pattern, `test_oracle_sources.py`).
    """
    assert heldout.scorable.__globals__["oracle_fittable"] is sources_module.oracle_fittable, (
        "the scorable filter resolves a predicate that is not `bakeoff.sources.oracle_fittable`"
        " itself, so a second implementation of the budget rule exists and the held-out rule "
        "could classify on a boundary the bakeoff does not enforce"
    )


def test_the_rule_digest_covers_the_scorable_filter_and_the_budget_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: the filter's source and the budget value are digest input, so an edit refuses.

    Two halves of one pin. First, the digest is not the same rule without the filter: a
    re-derivation over `_RULE_FUNCTIONS` minus `scorable` and `_RULE_PARAMETERS` minus
    `oracle_budget_chars` must differ from the module's, so each is covered. Second, moving
    the parameter's value moves the digest — the budget is input, not a bystander.
    """
    assert heldout.scorable in heldout._RULE_FUNCTIONS, (
        "the scorable filter is not in `_RULE_FUNCTIONS`, so its source is not digest-covered"
    )
    assert "oracle_budget_chars" in heldout._RULE_PARAMETERS, (
        "the oracle budget is not in `_RULE_PARAMETERS`, so the sealed budget is not "
        "digest-covered"
    )
    digest_before = heldout.rule_digest()

    hasher = hashlib.sha256()
    for function in heldout._RULE_FUNCTIONS:
        if function is not heldout.scorable:
            hasher.update(inspect.getsource(function).encode("utf-8"))
    hasher.update(
        json.dumps(
            {k: v for k, v in heldout._RULE_PARAMETERS.items() if k != "oracle_budget_chars"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    assert hasher.hexdigest() != digest_before, (
        "the digest is identical to the rule without the scorable filter and its budget, so an "
        "edit to either would not invalidate the committed document"
    )

    monkeypatch.setitem(heldout._RULE_PARAMETERS, "oracle_budget_chars", 1)
    assert heldout.rule_digest() != digest_before, (
        "the digest does not move when the sealed budget parameter moves, so the budget value "
        "is not part of the rule"
    )


def test_the_writer_refuses_when_the_bakeoff_budget_drifts_from_the_seal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3: a budget the bakeoff enforces but the rule does not seal is refused by name.

    The bakeoff side is the one the module's own digest cannot see: `rule_digest()` covers
    `_RULE_PARAMETERS`, not `bakeoff.sources.ORACLE_BUDGET_CHARS`, so a budget change there
    would leave every committed document loadable while the draw classifies under a seal the
    bakeoff no longer enforces. `compose_document` refuses that shape by name.
    """
    tasks, document = _corpus(tmp_path, _STANDARD_MEASURED, _STANDARD_REFUSED)

    monkeypatch.setattr(sources_module, "ORACLE_BUDGET_CHARS", 1)

    with pytest.raises(heldout.HeldoutRuleDrift) as caught:
        heldout.compose_document(tasks, document)

    assert "oracle_budget_chars" in str(caught.value), (
        f"the refusal must name the drifting budget parameter: {caught.value}"
    )
    assert str(sources_module.ORACLE_BUDGET_CHARS) in str(caught.value), (
        f"the refusal must name the bakeoff budget that no longer matches: {caught.value}"
    )


def test_the_writer_refuses_when_the_sealed_budget_drifts_from_the_bakeoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3 (mirror): a budget the rule seals but the bakeoff does not enforce is refused.

    The seal side is already digest-covered — moving the parameter refuses every committed
    document at load — and `compose_document` refuses it at write time too, by name, so the
    operator hears the contradiction before any document is produced.
    """
    tasks, document = _corpus(tmp_path, _STANDARD_MEASURED, _STANDARD_REFUSED)

    monkeypatch.setitem(heldout._RULE_PARAMETERS, "oracle_budget_chars", 1)

    with pytest.raises(heldout.HeldoutRuleDrift) as caught:
        heldout.compose_document(tasks, document)

    assert "oracle_budget_chars" in str(caught.value), (
        f"the refusal must name the drifting budget parameter: {caught.value}"
    )


# --------------------------------------------------------------------------------------------
# The draw excludes the class: membership over scorable members, `excluded` on the record.
# --------------------------------------------------------------------------------------------


def test_the_draw_never_contains_an_excluded_id_and_the_document_records_it(
    tmp_path: Path,
) -> None:
    """AC1/AC5: a task the predicate refuses is never drawn, and the document says so.

    One synthetic corpus task has a donor whose oracle exceeds the sealed budget — the class
    `oracle_fittable` refuses with the bakeoff's sentence. The derived membership must not
    contain it, `excluded` must record it with the predicate's own reason, and the
    corpus-wide fields must still cover it: only the draw changes.
    """
    measured = {**_STANDARD_MEASURED, "t-15": (1, 1, 1, 0)}
    tasks, document = _corpus(tmp_path, measured, _STANDARD_REFUSED, unfittable=("t-15",))
    out = tmp_path / "heldout" / "source-b.json"

    heldout.write_document(out, tasks, document)

    raw = json.loads(out.read_text())
    assert "t-15" not in raw["membership"], (
        f"the draw included t-15, whose oracle the predicate refused: {raw['membership']}"
    )
    assert set(raw["membership"]) & set(raw["excluded"]) == set(), (
        "the membership and the exclusion overlap: an excluded task was drawn"
    )
    reason = raw["excluded"]["t-15"]
    assert "bulk.py" in reason and str(sources_module.ORACLE_BUDGET_CHARS) in reason, (
        f"the exclusion must carry the predicate's own reason, naming the file and the "
        f"budget: {reason!r}"
    )
    for key in ("corpus", "difficulty", "bands"):
        assert "t-15" in raw[key], (
            f"{key} no longer covers the excluded task: only the draw is allowed to change"
        )
    assert set(raw["refusals"]) == set(_STANDARD_REFUSED), (
        "refusals kept its stratum meaning; an exclusion is not a refusal"
    )


def test_a_band_with_fewer_scorable_members_than_the_take_draws_fewer(
    tmp_path: Path,
) -> None:
    """AC4: a band of three scorable members draws three — the take is a cap, never a quota.

    The standard twelve arrange as 4/4/4; making one band-0 member unfittable leaves three
    scorable members, and the draw takes the three without error while the floors still bind
    (11 >= MIN_HELDOUT, 3/4/4 >= MIN_PER_BAND).
    """
    tasks, document = _corpus(
        tmp_path, _STANDARD_MEASURED, _STANDARD_REFUSED, unfittable=("t-03",)
    )
    out = tmp_path / "heldout" / "source-b.json"

    heldout.write_document(out, tasks, document)

    raw = json.loads(out.read_text())
    membership = raw["membership"]
    per_band = [
        sum(1 for task_id in membership if raw["bands"][task_id] == band)
        for band in range(heldout.HELDOUT_BANDS)
    ]
    assert per_band == [3, 4, 4], (
        f"band 0 drew {per_band[0]} with three scorable members: {per_band}"
    )
    assert set(raw["excluded"]) == {"t-03"}, raw["excluded"]
    assert len(membership) >= heldout.MIN_HELDOUT
    assert all(count >= heldout.MIN_PER_BAND for count in per_band)


def test_the_draw_refuses_when_the_scorable_population_cannot_meet_a_band_floor(
    tmp_path: Path,
) -> None:
    """AC4: floors over the filtered population — one scorable member in a band is the finding.

    Fourteen measured tasks arrange as 5/5/4 across the terciles; four of band 0's five
    members are unfittable, leaving one scorable member. The draw can then hold out at most
    1+4+4 = 9 tasks — below `MIN_HELDOUT`, with band 0 also below `MIN_PER_BAND` — and the
    response is the published § 7.1 finding, never a loosened floor. Unfiltered, the same
    corpus draws twelve; the refusal is the filter's doing.
    """
    measured = {
        **{f"t-{i:02d}": (1, 1, 1, 0) for i in range(5)},
        **{f"t-{i:02d}": (2, 2, 2, 0) for i in range(5, 10)},
        **{f"t-{i:02d}": (3, 3, 3, 0) for i in range(10, 14)},
    }
    tasks, document = _corpus(
        tmp_path, measured, unfittable=tuple(f"t-{i:02d}" for i in range(4))
    )

    with pytest.raises(heldout.EmptyHeldout) as caught:
        heldout.compose_document(tasks, document)

    assert "floor" in str(caught.value).lower(), (
        f"the refusal must name the unmet floor: {caught.value}"
    )


def test_the_draw_refuses_by_name_when_a_donor_cannot_be_read(tmp_path: Path) -> None:
    """AC7: machine state is a named refusal of the derivation, never an exclusion.

    One measured task's donor is removed after the corpus is built — the shape
    `oracle_fittable` raises on, not classifies. The derivation must refuse by name, and
    because it refuses, no document exists for the task to be excluded from.
    """
    measured = {**_STANDARD_MEASURED, "t-15": (1, 1, 1, 0)}
    tasks, document = _corpus(tmp_path, measured, _STANDARD_REFUSED, dedicated=("t-15",))
    shutil.rmtree(tmp_path / "donors" / "t-15" / "donor")

    with pytest.raises(heldout.HeldoutUnscorable) as caught:
        heldout.compose_document(tasks, document)

    assert "t-15" in str(caught.value), (
        f"the refusal must name the task whose oracle could not be decided: {caught.value}"
    )


def test_a_corpus_with_an_exclusion_derives_byte_identically_twice(tmp_path: Path) -> None:
    """AC9: the exclusion is part of the derivation, so it is byte-identical too.

    Two derivations over one corpus — including the excluded task's reason, which must come
    back byte for byte — produce one document. The predicate is a pure function of the
    manifest and git objects, so the reason cannot depend on when the draw ran.
    """
    measured = {**_STANDARD_MEASURED, "t-15": (1, 1, 1, 0)}
    tasks, document = _corpus(tmp_path, measured, _STANDARD_REFUSED, unfittable=("t-15",))
    first, second = tmp_path / "one.json", tmp_path / "two.json"

    heldout.write_document(first, tasks, document)
    heldout.write_document(second, tasks, document)

    assert first.read_bytes() == second.read_bytes()


def test_the_document_records_the_exclusion_in_a_digested_field(tmp_path: Path) -> None:
    """The `excluded` field is required, sorted, and inside the digest.

    A change to an excluded entry must move `document_digest` — the exclusion is part of the
    rule's output, so a hand-edit to it is exactly the tampering the digest exists to catch.
    """
    assert "excluded" in heldout._DIGESTED_FIELDS, (
        "the exclusion is not digest-covered, so an edit to it would not invalidate the "
        "committed document"
    )
    assert "excluded" in heldout._KNOWN_FIELDS, (
        "a document carrying `excluded` would be refused as carrying an unknown field"
    )
    measured = {**_STANDARD_MEASURED, "t-15": (1, 1, 1, 0)}
    tasks, document = _corpus(tmp_path, measured, _STANDARD_REFUSED, unfittable=("t-15",))
    out = tmp_path / "heldout" / "source-b.json"

    heldout.write_document(out, tasks, document)

    raw = json.loads(out.read_text())
    assert list(raw["excluded"]) == sorted(raw["excluded"]), "excluded ids must be sorted"

    doctored = json.loads(out.read_text())
    doctored["excluded"]["t-15"] = "a hand-edited reason"
    assert heldout.document_digest_of(doctored) != raw["document_digest"], (
        "the digest does not move when an excluded entry changes, so the exclusion is not "
        "part of the sealed rule output"
    )


# --------------------------------------------------------------------------------------------
# The loader: fail-closed by name, so the gate and the night can consume the document.
# --------------------------------------------------------------------------------------------


def _written(tmp_path: Path) -> Path:
    """A written held-out document over the standard corpus, for the loader tests.

    Each call builds its own corpus root: the loader tests re-derive a written document
    several times over one `tmp_path`, and the donors are real repositories that cannot be
    built twice in one place.
    """
    root = Path(tempfile.mkdtemp(dir=tmp_path))
    tasks, document = _corpus(root, _STANDARD_MEASURED, _STANDARD_REFUSED)
    out = root / "heldout" / "source-b.json"
    heldout.write_document(out, tasks, document)
    return out


def _resealed(path: Path, **edits: object) -> Path:
    """The document with `edits` applied and its digest re-sealed with the module's own
    `document_digest_of`, so the refusal that fires is about the edit, not the tampering —
    each loader check must be reachable on its own (the stratum precedent)."""
    raw = json.loads(path.read_text())
    raw.update(edits)
    raw["document_digest"] = heldout.document_digest_of(raw)
    path.write_text(json.dumps(raw))
    return path


def test_a_written_document_round_trips_through_the_loader(tmp_path: Path) -> None:
    """The document is meant to be consumed, not only written: read must equal write."""
    out = _written(tmp_path)

    loaded = heldout.read_document(out)

    assert loaded.schema == heldout.HELDOUT_SCHEMA
    assert loaded.rule_digest == heldout.rule_digest()
    assert (loaded.rule.bands, loaded.rule.min_heldout, loaded.rule.min_per_band) == (3, 10, 2)
    assert loaded.rule.split_seed == heldout.SPLIT_SEED
    assert loaded.corpus == tuple(sorted([*_STANDARD_MEASURED, *_STANDARD_REFUSED]))
    assert loaded.membership == tuple(json.loads(out.read_text())["membership"])
    assert set(loaded.difficulty) == set(_STANDARD_MEASURED)
    assert set(loaded.bands) == set(_STANDARD_MEASURED)
    assert set(loaded.refusals) == set(_STANDARD_REFUSED)
    assert all(
        loaded.bands[task_id] == band
        for task_id, band in json.loads(out.read_text())["bands"].items()
    )


def test_an_unknown_schema_is_refused_by_name(tmp_path: Path) -> None:
    """An old-schema document fails decode rather than defaulting."""
    out = _written(tmp_path)
    raw = json.loads(out.read_text())
    raw["schema"] = "whetstone-heldout/0"
    out.write_text(json.dumps(raw))

    with pytest.raises(heldout.HeldoutSchemaError) as caught:
        heldout.read_document(out)
    assert "whetstone-heldout/0" in str(caught.value), caught.value


def test_a_rule_digest_drift_is_refused_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Any rule-source or constant edit invalidates the committed document.

    The drift is simulated by making the module's own digest answer differently from the
    digest the document was sealed with — exactly what a rule edit does to a document that
    was not regenerated in the same commit.
    """
    out = _written(tmp_path)

    monkeypatch.setattr(heldout, "rule_digest", lambda: "f" * 64)

    with pytest.raises(heldout.HeldoutDigestMismatch) as caught:
        heldout.read_document(out)
    assert "rule" in str(caught.value).lower(), (
        f"the refusal must name the drift, not hide behind a generic message: {caught.value}"
    )


@pytest.mark.parametrize(
    ("edit", "name"),
    [
        (
            {"bands": {"t-00": 2}},
            "a hand-edited band",
        ),
        (
            {"difficulty": {"t-00": _difficulty(99, 1, 1, 0)}},
            "a doctored difficulty value",
        ),
    ],
)
def test_a_hand_edit_breaks_the_document_digest_and_is_refused(
    tmp_path: Path, edit: dict[str, object], name: str
) -> None:
    """The `document_digest` is the mechanically-required check: edits break it.

    A hand-edited band or value is refused rather than trusted — the loader re-derives the
    digest over the canonical payload and refuses a mismatch, naming it. (A membership edit
    is its own test below: it must stay floors-valid for the digest check to be the one that
    fires, and that shape is clearer spelled out than parametrized.)
    """
    out = _written(tmp_path)
    raw = json.loads(out.read_text())
    for key, value in edit.items():
        if isinstance(value, dict) and isinstance(raw.get(key), dict):
            raw[key].update(value)
        else:
            raw[key] = value
    out.write_text(json.dumps(raw))

    with pytest.raises(heldout.HeldoutDigestMismatch) as caught:
        heldout.read_document(out)
    assert "document" in str(caught.value).lower(), (
        f"the refusal must name the document digest, not a generic message: {caught.value}"
    )


def test_a_hand_edited_membership_breaks_the_document_digest_and_is_refused(
    tmp_path: Path,
) -> None:
    """A floors-valid but doctored membership is refused by the digest, not by the floors.

    Every member of the standard corpus's bands is selected (band size equals the take), so
    the only doctored membership that keeps every check green but the digest is a
    reordering — the digest covers order, and the reorder is exactly the hand-edit the
    `document_digest` exists to catch.
    """
    out = _written(tmp_path)
    raw = json.loads(out.read_text())
    raw["membership"] = list(reversed(raw["membership"]))
    out.write_text(json.dumps(raw))

    with pytest.raises(heldout.HeldoutDigestMismatch) as caught:
        heldout.read_document(out)
    assert "document" in str(caught.value).lower(), (
        f"the refusal must name the document digest, not a generic message: {caught.value}"
    )


def test_the_loader_refuses_an_unknown_field_by_name(tmp_path: Path) -> None:
    """A field this module does not read would be trusted by nobody and read by no one."""
    out = _resealed(_written(tmp_path), donor_heads={"donor-b": "0" * 40})

    with pytest.raises(heldout.HeldoutSchemaError) as caught:
        heldout.read_document(out)
    assert "donor_heads" in str(caught.value), caught.value


def test_the_loader_refuses_a_duplicated_membership_by_name(tmp_path: Path) -> None:
    """A membership that cannot be read as a set is not the set the rule selected."""
    raw = json.loads(_written(tmp_path).read_text())
    membership = raw["membership"]
    out = _resealed(_written(tmp_path), membership=[*membership, membership[0]])

    with pytest.raises(heldout.HeldoutSchemaError) as caught:
        heldout.read_document(out)
    assert "repeat" in str(caught.value).lower() or "duplicate" in str(caught.value).lower(), (
        caught.value
    )


def test_the_loader_refuses_a_membership_id_unknown_to_the_corpus(tmp_path: Path) -> None:
    """A membership naming a task the document never measured is refused by name."""
    raw = json.loads(_written(tmp_path).read_text())
    out = _resealed(_written(tmp_path), membership=[*raw["membership"], "synthetic-ghost"])

    with pytest.raises(heldout.HeldoutSchemaError) as caught:
        heldout.read_document(out)
    assert "synthetic-ghost" in str(caught.value), caught.value


def test_the_loader_refuses_a_member_the_document_refused_rather_than_measured(
    tmp_path: Path,
) -> None:
    """A refused task is not held out: the membership must name measured tasks exactly."""
    out = _resealed(_written(tmp_path), membership=[*_STANDARD_MEASURED, "t-12"])

    with pytest.raises(heldout.HeldoutSchemaError) as caught:
        heldout.read_document(out)
    assert "t-12" in str(caught.value), caught.value
    assert "refusal" in str(caught.value).lower(), (
        f"the refusal must say the member was refused rather than measured: {caught.value}"
    )


def test_the_loader_refuses_empty_membership_by_name(tmp_path: Path) -> None:
    """The loader refuses too: a degenerate document can never be the gate's pinned input."""
    out = _written(tmp_path)
    raw = json.loads(out.read_text())
    raw["membership"] = []
    out.write_text(json.dumps(raw))

    with pytest.raises(heldout.EmptyHeldout) as caught:
        heldout.read_document(out)
    assert "empty" in str(caught.value).lower(), caught.value


def test_the_loader_refuses_whole_corpus_membership_by_name(tmp_path: Path) -> None:
    """Both degenerate shapes, and in the loader as well as the writer.

    The written document's corpus carries refused tasks, so the degenerate shape is built by
    hand: a corpus that is exactly the measured set, refused by nothing, all of it selected.
    """
    out = _written(tmp_path)
    raw = json.loads(out.read_text())
    raw["corpus"] = sorted(_STANDARD_MEASURED)
    raw["refusals"] = {}
    raw["membership"] = raw["corpus"]
    out.write_text(json.dumps(raw))

    with pytest.raises(heldout.EmptyHeldout) as caught:
        heldout.read_document(out)
    assert "whole" in str(caught.value).lower(), caught.value


def test_the_loader_refuses_unmet_floors_by_name(tmp_path: Path) -> None:
    """A membership below the pre-committed floors is refused, even re-sealed: the gate must
    never consume a split the rule would not have written."""
    raw = json.loads(_written(tmp_path).read_text())
    out = _resealed(_written(tmp_path), membership=raw["membership"][:6])

    with pytest.raises(heldout.EmptyHeldout) as caught:
        heldout.read_document(out)
    assert "floor" in str(caught.value).lower(), (
        f"the refusal must name the unmet floor: {caught.value}"
    )


def test_the_loader_refuses_a_membership_naming_an_excluded_id_by_name(tmp_path: Path) -> None:
    """AC6: a doctored membership that smuggles an excluded id back into the draw refuses.

    The document over the standard corpus plus one unfittable task records the exclusion;
    adding that id to the membership is exactly the edit a hand would make to put a task the
    scorable filter refused back into the draw, and the loader names the task.
    """
    measured = {**_STANDARD_MEASURED, "t-15": (1, 1, 1, 0)}
    root = Path(tempfile.mkdtemp(dir=tmp_path))
    tasks, document = _corpus(root, measured, _STANDARD_REFUSED, unfittable=("t-15",))
    out = root / "heldout" / "source-b.json"
    heldout.write_document(out, tasks, document)
    raw = json.loads(out.read_text())
    assert "t-15" in raw["excluded"]

    doctored = _resealed(out, membership=[*raw["membership"], "t-15"])

    with pytest.raises(heldout.HeldoutSchemaError) as caught:
        heldout.read_document(doctored)
    assert "t-15" in str(caught.value), caught.value


def test_the_loader_refuses_an_excluded_id_unknown_to_the_corpus(tmp_path: Path) -> None:
    """AC6: an exclusion of a task the corpus never names is a classification of nothing.

    `excluded` is the record of what the scorable filter refused *here*; an id that matches
    no corpus task excludes nothing and would be trusted by nobody — refused by name.
    """
    out = _resealed(_written(tmp_path), excluded={"synthetic-ghost": "a hand-written reason"})

    with pytest.raises(heldout.HeldoutSchemaError) as caught:
        heldout.read_document(out)
    assert "synthetic-ghost" in str(caught.value), caught.value


def test_the_loader_refuses_an_exclusion_that_blurs_into_refusals(tmp_path: Path) -> None:
    """AC6: `excluded` and `refusals` are two meanings, and a task cannot carry both.

    `refusals` records the stratum's verdict (no difficulty measured); `excluded` records
    the scorable filter's. A document that puts one task in both has blurred the record the
    rule sealed, and the loader names the task.
    """
    out = _resealed(_written(tmp_path), excluded={"t-12": "a hand-written reason"})

    with pytest.raises(heldout.HeldoutSchemaError) as caught:
        heldout.read_document(out)
    assert "t-12" in str(caught.value), caught.value
    assert "refusal" in str(caught.value).lower(), (
        f"the refusal must name the blur with `refusals`: {caught.value}"
    )


def test_the_loader_refuses_unmet_per_band_floors_by_name(tmp_path: Path) -> None:
    """A loaded membership that meets the total floor but starves a band refuses by name.

    The degenerate shapes hit the total-floor refusal first; this is the shape that reaches
    the per-band sentence — a doctored membership of ten drawn entirely from two of three
    bands leaves the third with none, and the loader names the starved band.
    """
    root = Path(tempfile.mkdtemp(dir=tmp_path))
    measured = {f"t-{i:02d}": (1, 1, 1, 0) for i in range(20, 35)}
    tasks, document = _corpus(root, measured, _STANDARD_REFUSED)
    out = root / "heldout" / "source-b.json"
    heldout.write_document(out, tasks, document)
    raw = json.loads(out.read_text())
    assert raw["excluded"] == {}
    starved = [task_id for task_id, band in raw["bands"].items() if band in (0, 1)]

    doctored = _resealed(out, membership=starved)

    with pytest.raises(heldout.EmptyHeldout) as caught:
        heldout.read_document(doctored)
    assert "floor" in str(caught.value).lower(), caught.value
    assert "band 2" in str(caught.value), caught.value