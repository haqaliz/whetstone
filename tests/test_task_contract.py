"""Pins the task contract: what a Task is, and the single provenance-safe way to obtain one.

The failure this prevents has two halves, and both end in a reward paid for nothing.

The first is a loader that swallows a malformed manifest and returns a default. An operator
whose ``test_blobs`` silently came back empty would be running STRICT with no restore source
and no rejection set — the verifier would report PASS on a patch that deleted the failing
test. So every malformed shape below raises a ``ValueError`` that names the problem, and
never a quiet empty value.

The second is a Task built from something the policy produced. ``test_blobs`` is the
operator's artifact and the whole boundary; a patch, a diff, or a rollout that could author
its own golden tests would be the policy grading its own homework.
``test_no_task_is_ever_sourced_from_policy_output`` asserts that absence structurally, by
census rather than by reading the code, so a future loader with an innocent name breaks the
build instead of quietly opening the hole.

That census carries two anti-vacuity controls, because a census that found nothing would pass
while proving nothing: it asserts it observed public callables at all, and it runs its own
selector against a synthetic ``-> Task`` function to prove the selector is live. Both were
watched failing — the first against a census filtered down to nothing, the second against a
selector keyed on a return annotation that never matches — before being trusted.
"""

import base64
import inspect
import json
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest

from whetstone.verify import task as task_module
from whetstone.verify.task import Task, load_task

#: A golden test blob that is deliberately NOT valid UTF-8. If any layer decoded it to text
#: on the way through, the round-trip below cannot survive.
NON_UTF8_BLOB = b"def test_x():\n    assert b'\xff\xfe' == payload\n"

VALID_MANIFEST: dict[str, Any] = {
    "task_id": "demo-0001",
    "source": "public",
    "repo_url": "https://example.invalid/demo.git",
    "base_commit": "0123456789abcdef0123456789abcdef01234567",
    "problem_statement": "payload comparison is inverted",
    "fail_to_pass": ["tests/test_x.py::test_x"],
    "pass_to_pass": ["tests/test_y.py::test_y"],
    "test_blobs": {"tests/test_x.py": base64.b64encode(NON_UTF8_BLOB).decode("ascii")},
    "provenance": {"obtained": "2026-07-28", "how": "hand-authored fixture"},
}


def write_manifest(tmp_path: Path, manifest: object, name: str = "task.json") -> Path:
    """An operator file on disk, which is the only shape ``load_task`` accepts."""
    path = tmp_path / name
    path.write_text(json.dumps(manifest))
    return path


def manifest_without(key: str) -> dict[str, Any]:
    return {k: v for k, v in VALID_MANIFEST.items() if k != key}


def manifest_with(**overrides: Any) -> dict[str, Any]:
    return {**VALID_MANIFEST, **overrides}


def test_load_task_round_trips_an_operator_manifest(tmp_path: Path) -> None:
    """Every declared field survives the load, with the node-id lists as tuples."""
    loaded = load_task(write_manifest(tmp_path, VALID_MANIFEST))

    assert loaded.task_id == "demo-0001"
    assert loaded.source == "public"
    assert loaded.repo_url == "https://example.invalid/demo.git"
    assert loaded.base_commit == "0123456789abcdef0123456789abcdef01234567"
    assert loaded.problem_statement == "payload comparison is inverted"
    assert loaded.fail_to_pass == ("tests/test_x.py::test_x",)
    assert loaded.pass_to_pass == ("tests/test_y.py::test_y",)
    assert loaded.provenance == {"obtained": "2026-07-28", "how": "hand-authored fixture"}


def test_test_blobs_are_raw_bytes_and_not_text(tmp_path: Path) -> None:
    """Bytes, not ``str``: text would reintroduce the unicode-normalisation trap.

    The blob here is not valid UTF-8, so a loader that decoded it would raise rather than
    return the wrong thing — which is why the identity assertion below is paired with the
    explicit ``isinstance`` check on the type the caller actually receives.
    """
    loaded = load_task(write_manifest(tmp_path, VALID_MANIFEST))

    (blob,) = loaded.test_blobs.values()
    assert isinstance(blob, bytes)
    assert blob == NON_UTF8_BLOB
    assert loaded.test_blobs["tests/test_x.py"] == NON_UTF8_BLOB


def test_a_task_is_frozen(tmp_path: Path) -> None:
    """The contract cannot be edited after loading — including by the code that runs it."""
    loaded = load_task(write_manifest(tmp_path, VALID_MANIFEST))

    with pytest.raises(FrozenInstanceError):
        loaded.base_commit = "deadbeef"
    with pytest.raises(FrozenInstanceError):
        loaded.fail_to_pass = ()


def test_a_missing_file_raises_and_names_the_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="could not read"):
        load_task(tmp_path / "absent.json")


def test_a_file_that_is_not_json_raises_and_says_so(tmp_path: Path) -> None:
    path = tmp_path / "task.json"
    path.write_text("{not json at all")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_task(path)


def test_a_json_list_is_rejected_because_a_manifest_is_an_object(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must contain a JSON object"):
        load_task(write_manifest(tmp_path, [VALID_MANIFEST]))


def test_a_missing_field_names_the_field(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing required field 'fail_to_pass'"):
        load_task(write_manifest(tmp_path, manifest_without("fail_to_pass")))


def test_an_unknown_field_is_rejected_rather_than_ignored(tmp_path: Path) -> None:
    """A typo'd key must not leave the operator verifying against less than they declared."""
    with pytest.raises(ValueError, match="unknown field"):
        load_task(write_manifest(tmp_path, manifest_with(fail_to_pas=["x"])))


def test_a_wrongly_typed_field_names_the_field_and_the_type(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="fail_to_pass"):
        load_task(write_manifest(tmp_path, manifest_with(fail_to_pass="tests/test_x.py::test_x")))


def test_an_unknown_source_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="source"):
        load_task(write_manifest(tmp_path, manifest_with(source="synthetic")))


def test_an_empty_fail_to_pass_is_rejected(tmp_path: Path) -> None:
    """A task with nothing that must go green rewards a patch that changed nothing."""
    with pytest.raises(ValueError, match="fail_to_pass"):
        load_task(write_manifest(tmp_path, manifest_with(fail_to_pass=[])))


def test_empty_test_blobs_are_rejected(tmp_path: Path) -> None:
    """``test_blobs`` is both the restore source and the rejection set; empty defeats both."""
    with pytest.raises(ValueError, match="test_blobs"):
        load_task(write_manifest(tmp_path, manifest_with(test_blobs={})))


def test_a_blob_that_is_not_base64_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="base64"):
        load_task(
            write_manifest(tmp_path, manifest_with(test_blobs={"tests/test_x.py": "not base64!"}))
        )


def test_a_node_id_in_both_lists_is_rejected(tmp_path: Path) -> None:
    """Phase 3 compares the executed set against these lists; a duplicate makes that ambiguous."""
    shared = "tests/test_x.py::test_x"
    with pytest.raises(ValueError, match="both fail_to_pass and pass_to_pass"):
        load_task(write_manifest(tmp_path, manifest_with(pass_to_pass=[shared])))


def test_an_absolute_blob_path_is_rejected(tmp_path: Path) -> None:
    """Blob paths are restored into a checkout; an absolute one would write outside it."""
    blob = base64.b64encode(NON_UTF8_BLOB).decode("ascii")
    with pytest.raises(ValueError, match="relative"):
        load_task(write_manifest(tmp_path, manifest_with(test_blobs={"/etc/passwd": blob})))


def test_a_blob_path_escaping_the_checkout_is_rejected(tmp_path: Path) -> None:
    blob = base64.b64encode(NON_UTF8_BLOB).decode("ascii")
    with pytest.raises(ValueError, match="escape"):
        load_task(write_manifest(tmp_path, manifest_with(test_blobs={"../tests/x.py": blob})))


def test_a_non_string_provenance_value_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="provenance"):
        load_task(write_manifest(tmp_path, manifest_with(provenance={"obtained": 2026})))


def test_no_task_is_ever_sourced_from_policy_output(tmp_path: Path) -> None:
    """The provenance boundary: a Task comes ONLY from an operator file, never policy output.

    A patch, a diff, or a rollout that looks like a task manifest is POLICY OUTPUT, not
    OPERATOR POLICY. This module must expose no way to turn one into a Task — a task that
    could carry its own ``test_blobs`` would let a rollout hand the verifier the golden tests
    it is graded against. The assertion is structural, keyed on the RETURN TYPE rather than
    the name, so a future ``task_from_patch`` still trips it however innocently it is named.

    The dataclass constructor is deliberately outside this boundary: ``Task(...)`` requires
    the caller to already hold every field literally, so it is not a path FROM policy output
    TO a Task. What this forbids is a second *loader*.
    """
    # A manifest-shaped record riding inside policy output. If any code path honoured this,
    # a rollout could hand itself a task whose golden tests are whatever it wants.
    policy_output = {"kind": "task", **VALID_MANIFEST}

    public: dict[str, Callable[..., Any]] = {
        name: obj
        for name, obj in vars(task_module).items()
        if not name.startswith("_")
        and callable(obj)
        and getattr(obj, "__module__", None) == task_module.__name__
    }
    assert public, "the census observed no public callables at all, so it proves nothing"

    def produces(obj: Callable[..., Any]) -> bool:
        """A provenance surface is a callable that RETURNS a Task."""
        return "Task" in str(inspect.signature(obj).return_annotation)

    # Anti-vacuity for the selector itself: Belay's version of this census asserts only that
    # it saw callables, so a predicate that never matched would leave the whole test green
    # while checking nothing. This proves the selector really does select.
    def _synthetic_loader(patch: str) -> Task:  # pragma: no cover - never called
        raise NotImplementedError

    assert produces(_synthetic_loader), (
        "the return-annotation selector did not match a function annotated `-> Task`, so the "
        "census below cannot detect a new producer and proves nothing"
    )

    producers = {name for name, obj in public.items() if produces(obj)}
    assert producers == {"load_task"}, (
        f"an unexpected Task-producing callable appeared: {producers - {'load_task'}}. A Task "
        "must be sourced only from load_task(operator_file)."
    )

    # It takes a file path, not records. A loader that accepted a patch/diff/rollout argument
    # would be exactly the policy-output-to-Task path this boundary forbids.
    params = list(inspect.signature(load_task).parameters)
    assert params == ["path"], (
        f"load_task parameters are {params}; it must take only a file path. A patch, diff, or "
        "rollout parameter would open a policy-output-to-Task path."
    )

    # No public callable is named for, or takes, policy output.
    forbidden = ("patch", "diff", "rollout", "trace", "record", "prediction")
    for name, obj in public.items():
        lowered = name.lower()
        assert not any(word in lowered for word in forbidden), (
            f"public callable {name!r} names policy output — the module must expose no "
            "policy-output-to-Task path."
        )
        for param in inspect.signature(obj).parameters:
            assert not any(word in param.lower() for word in forbidden), (
                f"public callable {name!r} takes parameter {param!r}, which names policy "
                "output; a Task must be sourced only from an operator file."
            )

    # And there is no way to hand policy output to the loader in place of a file: passing the
    # records where a path is expected is an error, not a silently honoured task.
    with pytest.raises((TypeError, ValueError, OSError)):
        load_task(policy_output)  # type: ignore[arg-type]
