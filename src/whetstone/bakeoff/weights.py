"""The one download this project performs, and the proof that what it left behind is still there.

`docs/ROADMAP.md:574-576` declares exactly one network exception. The weight fetch is a second
(PRD S1): human-run, once, with its **provenance committed and its bytes never committed** —
13.4 GiB of `/weights/` is gitignored, so the only thing a reviewer ever sees is this module's
output. That asymmetry is the reason the module exists rather than a `curl` in a runbook.

**One: a mutable tag is not a snapshot.** `mlx-community` repositories are ordinary HuggingFace
repos and `main` moves. Fetching `main` and then recording `"revision": "main"` records nothing —
two operators running the same documented command a week apart get different weights and identical
provenance. So the tag is resolved to an **immutable commit sha first**, and the sha is what is
fetched *and* what is recorded, in that order. `PREREGISTRATION.md:131` makes model revision a
pinned input; a pinned input that names a moving reference is a reproducibility claim that cannot
be falsified, which is worse than none.

**Two: a recorded digest nobody reads is worse than no digest at all.** It renders in a pull
request exactly like a checked one. A gitignored directory can be re-fetched, half-downloaded,
hand-edited, or pointed at a different snapshot entirely, and every one of those produces a run
whose report cites weights it never loaded. So `load_weights` re-hashes every file the provenance
names, on every run, before a single token is generated. The cost is one linear read of the
weights — seconds against an overnight job — and it buys the difference between *these* bytes and
*some* bytes. It refuses rather than warns, and names the path, because a caveat is a thing a
caller reads past and an operator told only "the weights are wrong" has three multi-gigabyte
directories to search.

**Three: the extra must not become mandatory.** `huggingface_hub` arrives only with the `mlx`
extra (`pyproject.toml:29`, via `mlx-lm`), and CI runs the suite under a plain `uv sync`
(`.github/workflows/ci.yml:32`). So every import of it here is **function-local**, exactly as
`mlx_runtime.py` does it: this module imports, type-checks and is fully tested on a machine with
no extra installed and no network, because the half that needs the network is the half no test
enters. `load_weights` — the half every run enters — is `hashlib` and `json`.

Nothing here decides anything about a base model. It proves which weights are on the disk; what
they earn is decided by `whetstone.verify`, by re-execution, and nothing in this file participates
in that.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from whetstone.bakeoff.mlx_runtime import MODEL_CONFIG

#: The provenance document's own version, checked on read. A schema string rather than a bare
#: shape check because the fields this reader needs are exactly the fields an optimistic parse
#: would default: a `files` list read as empty verifies nothing whatsoever and returns
#: successfully, which is the shape of every silent failure this repository has already found.
PROVENANCE_SCHEMA = "whetstone-bakeoff-weights/1"

#: What the document is called, inside the weights root. A constant because both halves of this
#: module name it and a run that wrote one filename and read another would fail at the far end.
PROVENANCE_FILE = "provenance.json"

#: How much is read per digest step. Large enough that hashing is bound by the disk rather than by
#: the loop, small enough that a 7.74 GiB shard is never resident in this process — which matters
#: because the process that runs this is the same one that afterwards holds a model in memory.
_CHUNK = 1 << 20

#: The digest's encoding of choice, spelled out because it is published: a reader auditing a run
#: must be able to recompute these values with `shasum -a 256` and no knowledge of this file.
_DIGEST = "sha256"


class ProvenanceUnreadable(ValueError):
    """The provenance document is absent, malformed, or written to a schema this cannot read.

    Distinct from `WeightsUnverified` because the two send an operator to different places: this
    one means the *record* is wrong or missing, and the fix is to re-run the fetch; the other
    means the record is fine and the *disk* disagrees with it.
    """


class WeightsUnverified(ValueError):
    """The disk does not hold what the provenance says it holds.

    Raised, never returned as a flag, and raised before any model is loaded. A run that proceeded
    on unconfirmed weights would attribute every number it published to a revision it cannot
    demonstrate it ever read, and there is no later point at which that becomes detectable.
    """


@dataclass(frozen=True)
class WeightFile:
    """One file inside a candidate's directory, as the fetch recorded it."""

    #: The path relative to the candidate's `local_dir`, as HuggingFace names it.
    name: str

    #: Its size when fetched. Checked before the digest purely so a truncated download reports as
    #: a truncated download rather than as a mismatch that says nothing about what went wrong.
    bytes: int

    #: Hex-encoded SHA-256 of the file's bytes. The only field that distinguishes these weights
    #: from some other snapshot of the same repository.
    sha256: str


@dataclass(frozen=True)
class Weights:
    """One candidate's weights on this machine, and the fetch that put them there.

    `local_dir` is resolved against the provenance file's own directory when the document records
    it relatively, so the path handed to the MLX adapter does not depend on the working directory
    the run was started from — a run started from two different shells must load the same bytes.
    """

    #: The HuggingFace repository these came from, verbatim. Never passed to a loader: it is a
    #: repo id, and `mlx_lm.utils.load` treats a repo id as an instruction to download.
    repo_id: str

    #: The **immutable commit sha** that was fetched, resolved from whatever tag was asked for.
    revision: str

    #: The directory on this machine holding the files. Absolute after loading.
    local_dir: Path

    #: Total bytes fetched, as recorded. Published so the run can state its own footprint.
    bytes: int

    #: Wall-clock seconds the fetch took. A fact about a network on one morning, recorded because
    #: the second network exception should be as measurable as the first.
    seconds: float

    #: Every file, with its digest. Non-empty by construction — see `_candidate`.
    files: tuple[WeightFile, ...]


def load_weights(root: Path | str) -> tuple[Weights, ...]:
    """Read `root/provenance.json` and prove every byte it names is still on this disk.

    The gate every scored run passes through before it constructs anything. It performs four
    checks per candidate and each one refuses rather than degrades: the directory exists, it holds
    a `MODEL_CONFIG` (so it is a model rather than a directory), every recorded file is present at
    its recorded size, and every recorded digest matches the bytes beside it.

    The `MODEL_CONFIG` check duplicates one `MlxGenerator` already performs, and the duplication is
    the point: the adapter refuses one path at construction, after the run has started and after
    earlier candidates may already have been scored, whereas this refuses the whole set before a
    single token is generated. A bake-off that dies two hours in on candidate three has spent two
    hours discovering something that was true when it started.
    """
    location = Path(root)
    document = location / PROVENANCE_FILE
    if not document.is_file():
        raise ProvenanceUnreadable(
            f"no {PROVENANCE_FILE} at {str(document)!r}, so there is no record of which weights "
            "this machine holds. The weights themselves are gitignored and the provenance is the "
            "only committed evidence of what was fetched — run the fetch rather than pointing the "
            "run at a directory of files nobody recorded"
        )

    try:
        raw: Any = json.loads(document.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ProvenanceUnreadable(
            f"{str(document)!r} could not be read as JSON: {error}"
        ) from error

    if not isinstance(raw, dict) or raw.get("schema") != PROVENANCE_SCHEMA:
        raise ProvenanceUnreadable(
            f"{str(document)!r} does not declare schema {PROVENANCE_SCHEMA!r}; it declares "
            f"{raw.get('schema')!r} if it is an object at all. Refused rather than parsed "
            "optimistically: every field this reader needs is one a partial read would default, "
            "and a defaulted `files` list verifies nothing and returns successfully"
        )

    recorded = raw.get("candidates")
    if not isinstance(recorded, list) or not recorded:
        raise ProvenanceUnreadable(
            f"{str(document)!r} names no candidates, so this would be a bake-off of nothing. An "
            "empty set is a usage error and not a result — the same refusal "
            "`whetstone.tasks.manifest` makes for an empty task directory, one level up"
        )

    return tuple(_candidate(entry, location, document) for entry in recorded)


def verify(weights: Weights) -> None:
    """Re-hash every file `weights` names, or raise `WeightsUnverified` naming the first that moved.

    Separated from `load_weights` so the reading of a document and the checking of a disk are two
    operations with two names, and so a caller wanting to re-check mid-run — after an overnight
    resume, say — has something to call that does not re-parse anything.
    """
    if not weights.local_dir.is_dir():
        raise WeightsUnverified(
            f"{str(weights.local_dir)!r} is not a directory on this machine, so the weights "
            f"recorded for {weights.repo_id!r} at revision {weights.revision!r} are not here. "
            "The directory is gitignored, so a fresh clone, a moved cache and an interrupted "
            "fetch all produce this state — and every one of them produces a run whose report "
            "cites a revision it never loaded"
        )
    if not (weights.local_dir / MODEL_CONFIG).is_file():
        raise WeightsUnverified(
            f"{str(weights.local_dir)!r} holds no {MODEL_CONFIG}, so it is a directory rather "
            f"than a model. Refused here, before anything is generated, rather than from inside "
            "the loader after earlier candidates have already been scored"
        )

    for one in weights.files:
        path = weights.local_dir / one.name
        if not path.is_file():
            raise WeightsUnverified(
                f"{str(path)!r} is recorded in {PROVENANCE_FILE} and is not on this disk, so "
                f"{weights.repo_id!r} is incomplete. A partially-present model may still load and "
                "still generate, which is how this becomes a published number rather than an error"
            )
        size = path.stat().st_size
        if size != one.bytes:
            raise WeightsUnverified(
                f"{str(path)!r} is {size} bytes and {PROVENANCE_FILE} records {one.bytes}. "
                "Checked before the digest so that a truncated download reports as a truncated "
                f"download; the {_DIGEST} would also have failed and would have said less"
            )
        seen = _digest(path)
        if seen != one.sha256:
            raise WeightsUnverified(
                f"{str(path)!r} has {_DIGEST} {seen} and {PROVENANCE_FILE} records "
                f"{one.sha256}. The bytes on this disk are not the bytes that were fetched for "
                f"{weights.repo_id!r} at revision {weights.revision!r}. Everything else about "
                "this directory — that it exists, that it holds a config — is satisfied by a "
                "rebuild from some other snapshot, and only this check tells these weights apart "
                "from those"
            )


def fetch(repo_id: str, *, into: Path | str, revision: str = "main") -> Weights:
    """Resolve `revision` to a commit sha, download **that sha**, and record what landed.

    Human-run, and the order of the two network calls is the guarantee rather than an
    implementation detail. Asking the Hub what `main` currently points at and then downloading the
    resolved sha means the bytes on disk are the bytes the returned provenance names. Downloading
    `main` and recording the sha afterwards would be the same two calls in the order that admits a
    push between them — rare, undetectable, and fatal to a pinned input.

    `huggingface_hub` is imported inside this function, for the reason the module docstring gives:
    it ships with the `mlx` extra alone, and this module must import, type-check and test on a
    machine that has neither the extra nor a network.
    """
    from huggingface_hub import HfApi, snapshot_download

    root = Path(into)
    local_dir = root / repo_id.split("/")[-1]

    resolved = HfApi().repo_info(repo_id=repo_id, revision=revision).sha
    if not resolved:
        raise ProvenanceUnreadable(
            f"the Hub did not report a commit sha for {repo_id!r} at {revision!r}, so there is "
            "nothing immutable to pin this fetch to and nothing worth recording"
        )

    started = time.perf_counter()
    snapshot_download(repo_id=repo_id, revision=resolved, local_dir=str(local_dir))
    seconds = time.perf_counter() - started

    files = tuple(
        WeightFile(
            name=str(path.relative_to(local_dir)),
            bytes=path.stat().st_size,
            sha256=_digest(path),
        )
        for path in sorted(local_dir.rglob("*"))
        if path.is_file() and ".cache" not in path.parts
    )
    return Weights(
        repo_id=repo_id,
        revision=resolved,
        local_dir=local_dir.resolve(),
        bytes=sum(one.bytes for one in files),
        seconds=seconds,
        files=files,
    )


def write_provenance(fetched: Sequence[Weights], *, into: Path | str) -> Path:
    """Write the committed half of the fetch, and return the path it went to.

    `local_dir` is written **relative** to the weights root, because the absolute path on the
    machine that ran the fetch is a fact about that machine and this file is the part that gets
    committed. `load_weights` resolves it back against the document's own directory.
    """
    root = Path(into)
    root.mkdir(parents=True, exist_ok=True)
    document = root / PROVENANCE_FILE
    document.write_text(
        json.dumps(
            {
                "schema": PROVENANCE_SCHEMA,
                "candidates": [
                    {
                        "repo_id": one.repo_id,
                        "revision": one.revision,
                        "local_dir": _relative(one.local_dir, root),
                        "bytes": one.bytes,
                        "seconds": one.seconds,
                        "files": [
                            {"name": each.name, "bytes": each.bytes, "sha256": each.sha256}
                            for each in one.files
                        ],
                    }
                    for one in fetched
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return document


def _candidate(entry: Any, root: Path, document: Path) -> Weights:
    """One provenance entry, read strictly and then checked against the disk."""
    if not isinstance(entry, dict):
        raise ProvenanceUnreadable(
            f"{str(document)!r} holds a candidate entry that is not an object: {entry!r}"
        )
    try:
        declared = Path(str(entry["local_dir"]))
        files = tuple(
            WeightFile(name=str(one["name"]), bytes=int(one["bytes"]), sha256=str(one["sha256"]))
            for one in entry["files"]
        )
        weights = Weights(
            repo_id=str(entry["repo_id"]),
            revision=str(entry["revision"]),
            local_dir=(declared if declared.is_absolute() else root / declared).resolve(),
            bytes=int(entry["bytes"]),
            seconds=float(entry["seconds"]),
            files=files,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ProvenanceUnreadable(
            f"{str(document)!r} holds a candidate entry this reader cannot use: {error!r}. Every "
            f"field of schema {PROVENANCE_SCHEMA!r} is required, because each one is a field an "
            "optimistic parse would have defaulted to something that checks nothing"
        ) from error

    if not files:
        raise ProvenanceUnreadable(
            f"{str(document)!r} records no files for {weights.repo_id!r}, so verifying it would "
            "check nothing and succeed — which reads in a review exactly like a check that passed"
        )

    verify(weights)
    return weights


def _digest(path: Path) -> str:
    """Hex SHA-256 of `path`, read in chunks so a multi-gigabyte shard is never resident."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    """`path` relative to `root` when it is underneath it, else the absolute path unchanged.

    Falls back rather than raising: an operator who fetched to a directory outside the weights
    root has done something unusual but not wrong, and a provenance that refused to record it
    would leave them with no record at all.
    """
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


__all__ = [
    "PROVENANCE_FILE",
    "PROVENANCE_SCHEMA",
    "ProvenanceUnreadable",
    "WeightFile",
    "Weights",
    "WeightsUnverified",
    "fetch",
    "load_weights",
    "verify",
    "write_provenance",
]
