"""The stratum document: schema `whetstone-stratum/1`, deterministic, fail-closed, committed.

The stratum is the pre-committed pinned input of the easier-stratum probe (spec D5): the run
consumes the document, never a live recomputation. So the document is deterministic — sorted
ids, sorted keys, no timestamp, byte-identical across runs — and fail-closed — unknown schema,
a rule whose digest no longer matches, a degenerate membership (empty, or the whole corpus),
an id that does not resolve, or a hand-edited payload that breaks the document digest are each
refused by name, never read optimistically.

The document is evidence about the data, never the data (`tasks/README.md:126-128`): counts
only — files/hunks/added/deleted and the manifest-structural tie-break fields — never path
names, never patch content, never donor code. The locality walk at the bottom proves it
structurally, with a canary that proves the walk would see a leak.

The four loader refusals are defined here, in `stratum.py`, because the run-side filter
(aspect 2) imports them by identity — a second definition of "what may be selected" would be
a second answer to the same question, with only one of them reviewed.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fixtures.repos.mined import build_mined_task
from fixtures.repos.variant import single_file_task

from whetstone.bakeoff import stratum
from whetstone.bakeoff.stratum import (
    EmptyStratum,
    StratumDigestMismatch,
    StratumSchemaError,
    UnknownStratumId,
)

#: The repository root, for the `python -m` entry-point test below.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: A value that only exists inside a task's held test file. If it turns up anywhere in the
#: document, a file's contents did — which is the one thing the document may never carry
#: (the ledger-walk canary, `test_ledger.py:45-47`).
_CANARY = "canary-9f2c1e-the-users-own-source-line"

#: A string no legitimate field can contain: paths are the excluded class (spec D6), and a
#: committed document carrying one has leaked a fact about the donor's layout.
_PATH_SHAPED = "src/calc.py"


def _corpus(root: Path) -> tuple[tuple[Any, ...], dict[str, Path]]:
    """A two-task corpus: one in-band (single-file) and one out-of-band (mined, 2 files).

    Membership is then exactly one of two — non-empty and not the whole corpus — so the
    document is valid and the round trip can be asserted. The tasks arrive deliberately out
    of id order, so the writer's sorting is what is being exercised, not the caller's.
    """
    in_band = single_file_task(root / "in-band", "synthetic-in-band")
    out = build_mined_task(root / "out-of-band", task_id="synthetic-out-of-band")
    tasks = (out.task, in_band.task)
    donors = {"in-band": in_band.donor, "out-of-band": out.donor}
    return tasks, donors


def _write(root: Path, tasks: tuple[Any, ...], donors: dict[str, Path]) -> Path:
    out = root / "easier.json"
    stratum.write_document(out, tasks, donors)
    return out


def _strings(value: Any) -> list[str]:
    """Every string anywhere in a decoded JSON document, keys and values alike."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [
            found
            for key, item in value.items()
            for found in [*_strings(key), *_strings(item)]
        ]
    if isinstance(value, list):
        return [found for item in value for found in _strings(item)]
    return []


def _planted(root: Path, tasks: tuple[Any, ...], donors: dict[str, Path], **edits: Any) -> Path:
    """A document with `edits` applied to its raw JSON, its digest left untouched.

    Dict-valued edits merge into the existing field, so a doctored difficulty entry does not
    silently drop the other entries the field already held. The loader must refuse the result
    whether or not the edit broke the digest — this is how a hand-edited membership, band or
    value is refused rather than trusted (spec D5).
    """
    out = _write(root, tasks, donors)
    raw = json.loads(out.read_text())
    for key, value in edits.items():
        if isinstance(value, dict) and isinstance(raw.get(key), dict):
            raw[key].update(value)
        else:
            raw[key] = value
    out.write_text(json.dumps(raw))
    return out


def test_a_written_document_round_trips_through_the_loader(tmp_path: Path) -> None:
    """The document is meant to be consumed, not only written: read must equal write."""
    tasks, donors = _corpus(tmp_path)
    out = _write(tmp_path, tasks, donors)

    loaded = stratum.read_document(out)

    assert loaded.schema == stratum.STRATUM_SCHEMA
    assert loaded.rule_digest == stratum.rule_digest()
    assert (
        loaded.band.max_non_test_files,
        loaded.band.max_hunks,
        loaded.band.max_changed_lines,
    ) == (1, 2, 30)
    assert loaded.corpus == ("synthetic-in-band", "synthetic-out-of-band")
    assert loaded.membership == ("synthetic-in-band",)
    assert loaded.difficulty["synthetic-out-of-band"].files == 2
    assert loaded.difficulty["synthetic-out-of-band"].added == 3
    assert loaded.difficulty["synthetic-in-band"].added == 1
    assert loaded.refusals == {}
    assert loaded.donor_heads, "the donor heads are recorded (informational, never gated)"


def test_two_writes_over_one_corpus_are_byte_identical(tmp_path: Path) -> None:
    """Determinism is the recomputation test's premise: no timestamp, no clock, no order."""
    tasks, donors = _corpus(tmp_path)
    first, second = tmp_path / "one.json", tmp_path / "two.json"
    stratum.write_document(first, tasks, donors)
    stratum.write_document(second, tasks, donors)
    assert first.read_bytes() == second.read_bytes()
    assert "timestamp" not in json.loads(first.read_text()), (
        "a write-moment clock would make byte-equality impossible by construction (spec D5)"
    )


def test_an_unknown_schema_is_refused_by_name(tmp_path: Path) -> None:
    """An old-schema document fails decode rather than defaulting (spec N1)."""
    out = _planted(tmp_path, *_corpus(tmp_path), schema="whetstone-stratum/0")

    with pytest.raises(StratumSchemaError) as caught:
        stratum.read_document(out)
    assert "whetstone-stratum/0" in str(caught.value), caught.value


def test_a_rule_digest_drift_is_refused_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Any rule-source or band edit invalidates the committed document (spec D7, AC 4).

    The drift is simulated by making the module's own digest answer differently from the
    digest the document was sealed with — which is exactly what a rule edit does to a
    document that was not regenerated in the same commit.
    """
    out = _write(tmp_path, *_corpus(tmp_path))

    monkeypatch.setattr(stratum, "rule_digest", lambda: "f" * 64)

    with pytest.raises(StratumDigestMismatch) as caught:
        stratum.read_document(out)
    assert "rule" in str(caught.value).lower(), (
        f"the refusal must name the drift, not hide behind a generic message: {caught.value}"
    )


@pytest.mark.parametrize(
    ("edit", "name"),
    [
        ({"membership": ["synthetic-out-of-band"]}, "a hand-edited membership"),
        (
            {"band": {"max_non_test_files": 1, "max_hunks": 2, "max_changed_lines": 31}},
            "a band edit",
        ),
        (
            {
                "difficulty": {
                    "synthetic-in-band": {
                        "files": 99,
                        "hunks": 1,
                        "added": 1,
                        "deleted": 1,
                        "f2p": 1,
                        "pins": 0,
                        "blobs": 1,
                    }
                }
            },
            "a doctored difficulty value",
        ),
    ],
)
def test_a_hand_edit_breaks_the_document_digest_and_is_refused(
    tmp_path: Path, edit: dict[str, Any], name: str
) -> None:
    """The `document_digest` is aspect 2's mechanically-required check: edits break it.

    A hand-edited membership, band or value is refused rather than trusted — the loader
    re-derives the digest over the canonical payload and refuses a mismatch, naming it.
    """
    out = _planted(tmp_path, *_corpus(tmp_path), **edit)

    with pytest.raises(StratumDigestMismatch) as caught:
        stratum.read_document(out)
    assert "document" in str(caught.value).lower(), (
        f"the refusal must name the document digest, not a generic message: {caught.value}"
    )


def test_the_writer_refuses_an_empty_corpus_by_name(tmp_path: Path) -> None:
    """No manifests, no document: an empty set is a malformed invocation, never a stratum."""
    with pytest.raises(ValueError, match="empty"):
        stratum.write_document(tmp_path / "easier.json", (), {"donor": tmp_path})


def test_the_writer_refuses_empty_membership_by_name(tmp_path: Path) -> None:
    """A stratum of nothing is a vacuous pass wearing the easier-stratum's name (spec D4)."""
    tasks = (
        build_mined_task(tmp_path / "a", task_id="synthetic-out-a").task,
        build_mined_task(tmp_path / "b", task_id="synthetic-out-b").task,
    )

    with pytest.raises(EmptyStratum) as caught:
        stratum.write_document(tmp_path / "easier.json", tasks, {})

    assert "empty" in str(caught.value).lower(), (
        f"the refusal must name the empty membership: {caught.value}"
    )


def test_the_writer_refuses_whole_corpus_membership_by_name(tmp_path: Path) -> None:
    """The whole declared set is not a stratum: "easier" must be a proper subset (spec D4)."""
    tasks = (
        single_file_task(tmp_path / "a", "synthetic-in-a").task,
        single_file_task(tmp_path / "b", "synthetic-in-b").task,
    )

    with pytest.raises(EmptyStratum) as caught:
        stratum.write_document(tmp_path / "easier.json", tasks, {})

    assert "whole" in str(caught.value).lower(), (
        f"the refusal must name the whole-corpus membership: {caught.value}"
    )


def test_the_loader_refuses_empty_membership_by_name(tmp_path: Path) -> None:
    """The loader refuses too: a degenerate document can never be the run's pinned input."""
    out = _planted(tmp_path, *_corpus(tmp_path), membership=[])

    with pytest.raises(EmptyStratum) as caught:
        stratum.read_document(out)
    assert "empty" in str(caught.value).lower(), caught.value


def test_the_loader_refuses_whole_corpus_membership_by_name(tmp_path: Path) -> None:
    """Both degenerate shapes, and in the loader as well as the writer (spec AC 3)."""
    out = _planted(
        tmp_path, *_corpus(tmp_path), membership=["synthetic-in-band", "synthetic-out-of-band"]
    )

    with pytest.raises(EmptyStratum) as caught:
        stratum.read_document(out)
    assert "whole" in str(caught.value).lower(), caught.value


def test_the_loader_refuses_a_membership_id_unknown_to_the_corpus(tmp_path: Path) -> None:
    """A membership naming a task the document never measured is refused by name.

    The edit is re-sealed with the module's own `document_digest_of`, so the refusal that
    fires is about the id, not about the tampering — each check must be reachable on its own.
    """
    out = _write(tmp_path, *_corpus(tmp_path))
    raw = json.loads(out.read_text())
    raw["membership"] = ["synthetic-in-band", "synthetic-ghost"]
    raw["document_digest"] = stratum.document_digest_of(raw)
    out.write_text(json.dumps(raw))

    with pytest.raises(UnknownStratumId) as caught:
        stratum.read_document(out)
    assert "synthetic-ghost" in str(caught.value), caught.value


def test_the_loader_refuses_a_corpus_id_with_neither_difficulty_nor_refusal(
    tmp_path: Path,
) -> None:
    """Every corpus id must be measured or refused; a silent hole is an unknown id (spec AC 2)."""
    out = _write(tmp_path, *_corpus(tmp_path))
    raw = json.loads(out.read_text())
    raw["corpus"] = ["synthetic-in-band", "synthetic-out-of-band", "synthetic-ghost"]
    raw["document_digest"] = stratum.document_digest_of(raw)
    out.write_text(json.dumps(raw))

    with pytest.raises(UnknownStratumId) as caught:
        stratum.read_document(out)
    assert "synthetic-ghost" in str(caught.value), caught.value


def test_the_document_carries_counts_only(tmp_path: Path) -> None:
    """No path-shaped, no content-shaped, no line-spanning value anywhere (spec D6, AC 8).

    Task ids are already committed in the ledger (`tasks/README.md:24-27`); file paths are
    not, and the walk below is the assertion that they never start being.
    """
    out = _write(tmp_path, *_corpus(tmp_path))
    raw = json.loads(out.read_text())

    found = _strings(raw)
    assert found, "the walk found no strings at all, so it is asserting over nothing"
    for value in found:
        if value == stratum.STRATUM_SCHEMA:
            # The schema is a versioned format name (`whetstone-stratum/1`), not a path: it
            # is the one slash that names the file's shape, and it is pinned by the loader.
            continue
        assert "\n" not in value, f"{value!r} spans lines, so it is not a count or a digest"
        assert "/" not in value, (
            f"{value!r} is path-shaped; the document carries counts, never paths"
        )
        assert len(value) <= 200, (
            f"{value[:80]!r}… is {len(value)} characters, too long to be evidence rather than data"
        )

    for task_id, counts in raw["difficulty"].items():
        assert isinstance(task_id, str)
        assert set(counts) == {"files", "hunks", "added", "deleted", "f2p", "pins", "blobs"}
        assert all(isinstance(value, int) for value in counts.values()), (
            f"difficulty values must be ints only, got {counts!r}"
        )


def test_the_locality_walk_flags_a_planted_path(tmp_path: Path) -> None:
    """Anti-vacuity for the walk above: a planted path-shaped value must be seen (AC 8)."""
    out = _write(tmp_path, *_corpus(tmp_path))
    raw = json.loads(out.read_text())
    raw["difficulty"]["synthetic-in-band"]["files"] = _PATH_SHAPED
    out.write_text(json.dumps(raw))

    offenders = [value for value in _strings(json.loads(out.read_text())) if "/" in value]

    assert _PATH_SHAPED in offenders, (
        "the walk did not see the planted path it was handed, so the locality assertion "
        "above would pass by seeing nothing at all."
    )


def test_main_accepts_two_corpus_roots_and_writes(tmp_path: Path) -> None:
    """`--corpus a --corpus b --out f` unions the two donors and writes one document."""
    _ = _corpus(tmp_path / "scratch")

    first = tmp_path / "corpus-a"
    second = tmp_path / "corpus-b"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (first / "synthetic-out-of-band.json").write_bytes(
        (tmp_path / "scratch" / "out-of-band" / "synthetic-out-of-band.json").read_bytes()
    )
    (second / "synthetic-in-band.json").write_bytes(
        (tmp_path / "scratch" / "in-band" / "synthetic-in-band.json").read_bytes()
    )

    out = tmp_path / "stratum" / "easier.json"
    rc = stratum.main(["--corpus", str(first), "--corpus", str(second), "--out", str(out)])

    assert rc == 0
    raw = json.loads(out.read_text())
    assert raw["schema"] == stratum.STRATUM_SCHEMA
    assert raw["corpus"] == ["synthetic-in-band", "synthetic-out-of-band"]
    assert raw["membership"] == ["synthetic-in-band"]


def test_the_module_runs_as_python_m_for_the_runbook(tmp_path: Path) -> None:
    """`python -m whetstone.bakeoff.stratum` is the runbook's door, and it must exist.

    The plan's invocation for the committed document is the module entry point
    (`plan_20260814.md` Phase 3), not a `whetstone` CLI flag — so the `__main__` guard is
    part of the aspect's surface, and a module that imported cleanly without it would write
    nothing while exiting 0, which is the runbook's exact failure shape.
    """
    _ = _corpus(tmp_path / "scratch")
    manifest_dir = tmp_path / "corpus-a"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "synthetic-out-of-band.json").write_bytes(
        (
            tmp_path / "scratch" / "out-of-band" / "synthetic-out-of-band.json"
        ).read_bytes()
    )
    (manifest_dir / "synthetic-in-band.json").write_bytes(
        (
            tmp_path / "scratch" / "in-band" / "synthetic-in-band.json"
        ).read_bytes()
    )
    out = tmp_path / "stratum" / "easier.json"

    completed = subprocess.run(
        [
            "python",
            "-m",
            "whetstone.bakeoff.stratum",
            "--corpus",
            str(manifest_dir),
            "--out",
            str(out),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert out.is_file(), (
        "the module entry point exited 0 without writing the document — the runbook would "
        "then believe a stratum exists where none does."
    )


def test_main_refuses_an_out_under_the_local_corpus(tmp_path: Path) -> None:
    """The document is a committed pinned input; `tasks/local/` is where git never sees it."""
    _ = _corpus(tmp_path / "scratch")
    root = tmp_path / "scratch" / "out-of-band"
    manifest_dir = tmp_path / "corpus-a"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "synthetic-out-of-band.json").write_bytes(
        (root / "synthetic-out-of-band.json").read_bytes()
    )

    rc = stratum.main(
        [
            "--corpus",
            str(manifest_dir),
            "--out",
            str(tmp_path / "tasks" / "local" / "easier.json"),
        ]
    )

    assert rc == 2
    assert not (tmp_path / "tasks" / "local" / "easier.json").exists()
