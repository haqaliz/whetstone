"""The task contract and its operator-file loader.

A `Task` is what the verifier is pointed at: a known-broken commit, the tests that must go
green, the tests that must stay green, and — the part that makes the reward mean anything —
the **operator-held golden test blobs**.

**`test_blobs` is the whole boundary.** It is both the restore source (STRICT rewrites every
operator-held test from golden after applying the patch) and the rejection set (a patch that
touches one of those paths is refused before anything runs). A policy that could author its
own `test_blobs` would be handing the verifier the exam it is graded against, so the only way
to obtain a Task is `load_task(operator_file)`. Nothing here reads a patch, a diff, or a
rollout, and `test_no_task_is_ever_sourced_from_policy_output` asserts that absence
structurally — by census of what returns a `Task` — so a future policy-output loader breaks
the build rather than silently opening the hole.

**Blob contents are raw bytes, never `str`.** A path or a file decoded to text reintroduces
the unicode-normalisation trap: two genuinely different byte sequences can compare equal once
decoded, and the comparisons downstream (does this patch touch a held path, does the restored
file match golden) must run on the same bytes throughout. The manifest therefore carries each
blob base64-encoded, and it is decoded to bytes here and left that way.

**Fail-closed.** A malformed file, a missing field, an unknown field, an empty `test_blobs` —
each is a named `ValueError`, never a silent default. The failure mode this refuses is
specific and severe: a Task that silently loaded with no `test_blobs` has no restore source
and an empty rejection set, so STRICT would report PASS on a patch that deleted the failing
test. A quiet default here is a false reward downstream.

Zero runtime dependencies: stdlib `json` and `base64` only. No model is consulted — this is a
parse and a set of type checks — and the reward-path import guard covers this package.
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

#: The provenance labels the contract understands. `source` is a record, not a check: the
#: contract a public task is verified against is identical to a private one's. An unknown
#: value is still rejected, because a manifest that says `synthetic` means something the
#: loader was never told how to treat, and guessing is how a silent default gets in.
_SOURCES = frozenset({"public", "private"})

#: Exactly the fields a manifest may carry. Both halves matter: a MISSING field is rejected
#: so nothing loads as a default, and an UNKNOWN field is rejected so a typo'd `fail_to_pas`
#: cannot leave the operator verifying against less than they wrote.
_FIELDS = frozenset(
    {
        "task_id",
        "source",
        "repo_url",
        "base_commit",
        "problem_statement",
        "fail_to_pass",
        "pass_to_pass",
        "test_blobs",
        "provenance",
    }
)


@dataclass(frozen=True)
class Task:
    """One verifiable task. Frozen, and obtainable only from `load_task`.

    `fail_to_pass` must go green and `pass_to_pass` must stay green; together they are the
    exact set of node ids the verifier expects to see executed, which is why neither may
    contain a duplicate. `test_blobs` maps a repository-relative path to that file's golden
    contents **as bytes** — the operator's artifact, and the one thing the policy must never
    supply. `source` and `provenance` are records of how the task was obtained; they do not
    change how it is verified.
    """

    task_id: str
    source: str
    repo_url: str
    base_commit: str
    problem_statement: str
    fail_to_pass: tuple[str, ...]
    pass_to_pass: tuple[str, ...]
    test_blobs: Mapping[str, bytes]
    provenance: Mapping[str, str]


def load_task(path: Path) -> Task:
    """Load a task from an operator-controlled JSON manifest. The ONLY way to obtain a Task.

    The manifest is a JSON object carrying exactly `_FIELDS`, with `test_blobs` as a mapping
    from a repository-relative path to that file's golden contents, base64-encoded. Anything
    malformed — unreadable, not JSON, not an object, a missing or unknown field, a wrongly
    typed value, an unusable blob — raises `ValueError` naming the problem. Never a silent
    default, never a raw traceback.

    It takes a filesystem `path`, never a patch, a diff, or a rollout. That signature IS the
    provenance boundary: the task is sourced from a file the operator controls, not from
    anything the policy produced.
    """
    file_path = Path(path)
    try:
        text = file_path.read_text()
    except OSError as exc:
        raise ValueError(f"could not read task manifest {str(file_path)!r}: {exc}") from exc

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"task manifest {str(file_path)!r} is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(
            f"task manifest {str(file_path)!r} must contain a JSON object, "
            f"got {type(raw).__name__}"
        )

    where = f"task manifest {str(file_path)!r}"
    _check_fields(raw, where=where)

    source = _string(raw, "source", where=where)
    if source not in _SOURCES:
        known = ", ".join(sorted(_SOURCES))
        raise ValueError(f"{where} declares unknown source {source!r}; known sources are: {known}")

    fail_to_pass = _node_ids(raw, "fail_to_pass", where=where)
    if not fail_to_pass:
        raise ValueError(
            f"{where} has an empty fail_to_pass; a task with no test that must go green "
            "would reward a patch that changed nothing"
        )
    pass_to_pass = _node_ids(raw, "pass_to_pass", where=where)

    shared = set(fail_to_pass) & set(pass_to_pass)
    if shared:
        raise ValueError(
            f"{where} lists {sorted(shared)!r} in both fail_to_pass and pass_to_pass; the "
            "verifier compares the executed node ids against these lists, and a node id in "
            "both makes that comparison ambiguous"
        )

    return Task(
        task_id=_string(raw, "task_id", where=where),
        source=source,
        repo_url=_string(raw, "repo_url", where=where),
        base_commit=_string(raw, "base_commit", where=where),
        problem_statement=_string(raw, "problem_statement", where=where),
        fail_to_pass=fail_to_pass,
        pass_to_pass=pass_to_pass,
        test_blobs=_test_blobs(raw, where=where),
        provenance=_provenance(raw, where=where),
    )


def _check_fields(raw: dict[str, Any], *, where: str) -> None:
    """Exactly `_FIELDS`, no more and no less — missing and unknown are both errors."""
    missing = sorted(_FIELDS - raw.keys())
    if missing:
        named = ", ".join(repr(name) for name in missing)
        raise ValueError(f"{where} is missing required field {named}")

    unknown = sorted(raw.keys() - _FIELDS)
    if unknown:
        named = ", ".join(repr(name) for name in unknown)
        raise ValueError(
            f"{where} carries unknown field {named}; an unknown field is rejected rather "
            "than ignored, because a typo'd key would otherwise verify the task against "
            "less than the operator declared"
        )


def _string(raw: dict[str, Any], key: str, *, where: str) -> str:
    value = raw[key]
    if not isinstance(value, str):
        raise ValueError(f"{where} has a non-string {key} ({type(value).__name__}); expected str")
    return value


def _node_ids(raw: dict[str, Any], key: str, *, where: str) -> tuple[str, ...]:
    """A list of pytest node ids, with duplicates rejected rather than collapsed."""
    value = raw[key]
    if not isinstance(value, list):
        raise ValueError(
            f"{where} has a non-list {key} ({type(value).__name__}); expected a list of "
            "pytest node ids"
        )
    for item in value:
        if not isinstance(item, str):
            raise ValueError(
                f"{where} has a non-string entry in {key} ({type(item).__name__}); every "
                "node id must be a string"
            )
    duplicates = sorted({item for item in value if value.count(item) > 1})
    if duplicates:
        raise ValueError(
            f"{where} repeats {duplicates!r} in {key}; the verifier compares the executed "
            "node ids against this list, and a duplicate makes that comparison ambiguous"
        )
    return tuple(value)


def _test_blobs(raw: dict[str, Any], *, where: str) -> Mapping[str, bytes]:
    """The operator-held golden tests: repository-relative path -> raw bytes.

    Decoded from base64 to `bytes` and left there. The paths are checked to be relative and
    non-escaping because STRICT restores each one into a checkout, and a path that resolved
    outside it would write wherever the manifest said.
    """
    value = raw["test_blobs"]
    if not isinstance(value, dict):
        raise ValueError(
            f"{where} has a non-object test_blobs ({type(value).__name__}); expected a "
            "mapping from path to base64-encoded contents"
        )
    if not value:
        raise ValueError(
            f"{where} has an empty test_blobs; it is both the restore source and the "
            "rejection set, so an empty one leaves the verifier with nothing to restore and "
            "nothing to refuse"
        )

    blobs: dict[str, bytes] = {}
    for path, encoded in value.items():
        if not isinstance(path, str):
            raise ValueError(f"{where} has a non-string test_blobs path ({path!r})")
        _check_blob_path(path, where=where)
        if not isinstance(encoded, str):
            raise ValueError(
                f"{where} has non-string contents for test_blobs path {path!r} "
                f"({type(encoded).__name__}); expected a base64-encoded string"
            )
        try:
            blobs[path] = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(
                f"{where} has contents for test_blobs path {path!r} that are not valid "
                f"base64: {exc}"
            ) from exc
    return blobs


def _check_blob_path(path: str, *, where: str) -> None:
    """Repository-relative, and staying inside the repository."""
    pure = PurePosixPath(path)
    if pure.is_absolute() or path.startswith("/"):
        raise ValueError(
            f"{where} has an absolute test_blobs path {path!r}; blob paths must be relative "
            "to the repository under test"
        )
    if ".." in pure.parts:
        raise ValueError(
            f"{where} has a test_blobs path {path!r} that would escape the repository under "
            "test; blob paths must stay inside the checkout"
        )


def _provenance(raw: dict[str, Any], *, where: str) -> Mapping[str, str]:
    """How the task was obtained, and when. A record — it does not gate the reward.

    Empty is allowed: an operator who recorded nothing has recorded nothing, and inventing a
    provenance would be worse than an absent one. Non-string values are still rejected, so
    the record cannot quietly become a structure nothing downstream knows how to render.
    """
    value = raw["provenance"]
    if not isinstance(value, dict):
        raise ValueError(
            f"{where} has a non-object provenance ({type(value).__name__}); expected a "
            "mapping of strings"
        )
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ValueError(
                f"{where} has a non-string provenance entry ({key!r}: {item!r}); every "
                "provenance key and value must be a string"
            )
    return dict(value)


__all__ = ["Task", "load_task"]
