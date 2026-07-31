"""The weights a run loaded must be the weights its provenance names — proven, not asserted.

`weights/provenance.json` is the committed half of a 13.4 GiB fetch whose other half is
gitignored and can therefore never be reviewed. That asymmetry is the whole risk: the document
that gets read in a pull request describes bytes nobody in the review can see, and a directory
that was re-fetched, half-downloaded, hand-edited or pointed at a different snapshot produces a
run whose numbers are attributed to weights it never loaded. Recording a sha256 per file and then
not checking it would be worse than recording nothing, because the unchecked digest reads to a
reviewer exactly like a checked one.

So the two adversarial cases below are synthesised rather than waited for: a candidate whose
directory is gone, and a file whose recorded digest no longer matches the bytes beside it. Both
must refuse, and both must name the path, because an operator told only that "the weights are
wrong" has 13.4 GiB and three directories to search.

**No network, no download, no `huggingface_hub`, no real weights.** Every fixture here is a few
bytes in `tmp_path`; the fetch half of the module imports its dependency function-locally and is
never entered by this file.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from whetstone.bakeoff.weights import (
    PROVENANCE_FILE,
    PROVENANCE_SCHEMA,
    ProvenanceUnreadable,
    WeightsUnverified,
    load_weights,
)

#: Stand-ins for the three candidates' files. Tiny, because what is under test is the digest
#: check and not the reader's throughput.
CONTENTS = {
    "config.json": '{"model_type": "qwen2"}',
    "model.safetensors": "not really a tensor",
    "tokenizer.json": '{"version": "1.0"}',
}


def _build(root: Path, *, candidates: int = 1, omit: str | None = None) -> Path:
    """Write `candidates` weight directories under `root`, plus the provenance naming them.

    `omit` names a candidate whose provenance entry is written but whose directory is not — the
    "somebody moved the weights" case, synthesised rather than waited for.
    """
    recorded = []
    for index in range(candidates):
        name = f"Qwen2.5-Coder-{index}B-Instruct-4bit"
        local_dir = root / name
        if name != omit:
            local_dir.mkdir(parents=True)
            for filename, text in CONTENTS.items():
                (local_dir / filename).write_text(text, encoding="utf-8")
        recorded.append(
            {
                "repo_id": f"mlx-community/{name}",
                "revision": f"{index}" * 40,
                "local_dir": name,
                "bytes": sum(len(text.encode("utf-8")) for text in CONTENTS.values()),
                "seconds": 12.5,
                "files": [
                    {
                        "name": filename,
                        "bytes": len(text.encode("utf-8")),
                        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    }
                    for filename, text in CONTENTS.items()
                ],
            }
        )

    root.mkdir(parents=True, exist_ok=True)
    (root / PROVENANCE_FILE).write_text(
        json.dumps({"schema": PROVENANCE_SCHEMA, "candidates": recorded}, indent=2),
        encoding="utf-8",
    )
    return root


def test_a_sound_provenance_loads_every_candidate_it_names(tmp_path: Path) -> None:
    """The green case, asserted first so the refusals below cannot pass by refusing everything.

    A checker that raised unconditionally would satisfy both adversarial tests and be worthless,
    and it would look exactly like a strict one in the diff.
    """
    root = _build(tmp_path / "weights", candidates=3)

    loaded = load_weights(root)

    assert len(loaded) == 3, (
        "WHY THIS IS A FAILURE: the provenance names three candidates and the loader returned "
        f"{len(loaded)}. A bake-off that silently drops a candidate publishes a two-way "
        "comparison under a three-way heading"
    )
    assert [one.local_dir for one in loaded] == [
        root / f"Qwen2.5-Coder-{index}B-Instruct-4bit" for index in range(3)
    ], (
        "WHY THIS IS A FAILURE: a relative `local_dir` was not resolved against the provenance "
        "file's own directory, so the path handed to the MLX adapter depends on the working "
        f"directory the run was started from. Got {[str(one.local_dir) for one in loaded]!r}"
    )


def test_a_candidate_whose_directory_is_gone_is_refused_by_name(tmp_path: Path) -> None:
    """Weights the provenance names and the disk does not hold must stop the run.

    The failure this prevents is not exotic: the directory is gitignored, so a fresh clone, a
    moved cache or an interrupted fetch all produce exactly this state, and every one of them
    produces a run whose report cites a revision that was never loaded.
    """
    root = _build(tmp_path / "weights", candidates=2, omit="Qwen2.5-Coder-1B-Instruct-4bit")

    with pytest.raises(WeightsUnverified) as refusal:
        load_weights(root)

    assert "Qwen2.5-Coder-1B-Instruct-4bit" in str(refusal.value), (
        "WHY THIS IS A FAILURE: the refusal does not name the directory that is missing, so an "
        "operator holding three multi-gigabyte candidates is told only that something is absent. "
        f"Got {str(refusal.value)!r}"
    )


def test_a_file_that_no_longer_matches_its_recorded_digest_is_refused(tmp_path: Path) -> None:
    """The case the sha256 column exists for, and the only one that proves it is read.

    Everything else about a weights directory — that it exists, that it holds a `config.json` —
    is satisfied by a directory somebody rebuilt from a different snapshot. Only the digest
    distinguishes *these* bytes from *some* bytes, which is the difference between a run that is
    reproducible and a run that says it is.

    **The replacement is the same length as what it replaces, and that is the whole test.** Written
    the obvious way — any old string — the cheaper size check catches it first, whose message
    mentions the digest it did not compute, and the assertions below pass against an
    implementation that never hashes anything. Watched: with the digest comparison removed, this
    test failed only once the lengths matched.
    """
    root = _build(tmp_path / "weights", candidates=1)
    tampered = root / "Qwen2.5-Coder-0B-Instruct-4bit" / "model.safetensors"
    tampered.write_text("x" * len(CONTENTS["model.safetensors"]), encoding="utf-8")

    with pytest.raises(WeightsUnverified) as refusal:
        load_weights(root)

    message = str(refusal.value)
    assert str(tampered) in message, (
        "WHY THIS IS A FAILURE: the refusal does not name the file whose bytes moved, so the "
        f"operator cannot tell a truncated download from a swapped snapshot. Got {message!r}"
    )
    assert "sha256" in message, (
        "WHY THIS IS A FAILURE: the refusal does not say what was compared, so it reads as a "
        f"missing file rather than as an identity check that failed. Got {message!r}"
    )


def test_a_directory_holding_no_config_is_refused_before_the_adapter_sees_it(
    tmp_path: Path,
) -> None:
    """A directory that is not a model is caught here, naming the path the operator chose.

    `MlxGenerator` refuses the same thing, and that is not duplication: it refuses one path at
    construction, after the run has started and after some candidates may already have been
    scored. Refusing at load time refuses the whole set before a single token is generated.
    """
    root = _build(tmp_path / "weights", candidates=1)
    (root / "Qwen2.5-Coder-0B-Instruct-4bit" / "config.json").unlink()

    with pytest.raises(WeightsUnverified) as refusal:
        load_weights(root)

    assert "config.json" in str(refusal.value), (
        "WHY THIS IS A FAILURE: a directory with no config.json was refused without saying what "
        f"was missing from it. Got {str(refusal.value)!r}"
    )


def test_an_unrecognised_schema_is_refused_rather_than_read_optimistically(
    tmp_path: Path,
) -> None:
    """A provenance written by some other tool must not be read as if it were this one's.

    Refused rather than best-effort parsed, because the fields this reader needs are exactly the
    fields a partial read would default: a `files` list read as empty verifies nothing at all and
    returns successfully, which is the shape of every silent failure in this repository.
    """
    root = tmp_path / "weights"
    root.mkdir()
    (root / PROVENANCE_FILE).write_text(
        json.dumps({"schema": "something-else/9", "candidates": []}), encoding="utf-8"
    )

    with pytest.raises(ProvenanceUnreadable) as refusal:
        load_weights(root)

    assert PROVENANCE_SCHEMA in str(refusal.value), (
        "WHY THIS IS A FAILURE: the refusal does not say which schema was expected, so nobody "
        f"can tell whether the file or the reader is out of date. Got {str(refusal.value)!r}"
    )


def test_an_empty_candidate_list_is_refused_rather_than_run_as_a_bake_off_of_nothing(
    tmp_path: Path,
) -> None:
    """Zero candidates is a usage error, exactly as an empty task directory is.

    `whetstone.tasks.manifest` refuses an empty corpus because a set with nothing in it that
    reduces to success is the cheapest possible fake. The same argument applies one level up: a
    bake-off with no candidates would sweep nothing, tally nothing and select nothing, and
    `selection.NoContenders` would be reached far downstream of the file that was actually wrong.
    """
    root = tmp_path / "weights"
    root.mkdir()
    (root / PROVENANCE_FILE).write_text(
        json.dumps({"schema": PROVENANCE_SCHEMA, "candidates": []}), encoding="utf-8"
    )

    with pytest.raises(ProvenanceUnreadable):
        load_weights(root)


def test_a_missing_provenance_file_names_the_path_it_looked_for(tmp_path: Path) -> None:
    """The first thing an operator hits if they skipped the fetch, so it must say where to look."""
    with pytest.raises(ProvenanceUnreadable) as refusal:
        load_weights(tmp_path / "weights")

    assert PROVENANCE_FILE in str(refusal.value), (
        "WHY THIS IS A FAILURE: the loader could not find its provenance and did not say what it "
        f"was looking for. Got {str(refusal.value)!r}"
    )
