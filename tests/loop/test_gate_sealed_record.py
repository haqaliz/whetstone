"""The gate takes its base and dataset digest from the verified `Checkpoint`, never a second read.

`sft.verify_checkpoint` returns the claims it verified. A gate that re-opened `provenance.json`
afterwards would read bytes the seal had already vouched for, and a file changed between the
check and the use would be believed. These tests pin that the gate has no such read, that a v2
checkpoint edited after sealing is refused before any scoring, and that the v1 refusals keep
their text.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from loop.test_gate import _gate_fixtures
from loop.test_gate_provenance import _rewrite
from whetstone.loop import gate, sft

_NAMES = ("provenance.json", "CHECKPOINT_FILE")


def _code_without_docstrings(source: str) -> ast.AST:
    """The module's syntax tree with every docstring removed (comments never reach the AST)."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:] or [ast.Pass()]
    return tree


def _reads_of_the_file(tree: ast.AST) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if any(name in node.value for name in _NAMES):
                found.append(node.value)
        elif isinstance(node, ast.Name | ast.Attribute):
            name = node.id if isinstance(node, ast.Name) else node.attr
            if name in _NAMES:
                found.append(name)
    return found


def test_the_gate_holds_no_read_of_provenance_json() -> None:
    """Outside docstrings and comments, `gate.py` names neither the file nor its constant.

    String literals in the refusal messages are exempt only by content: any literal that
    mentions the file is reported, so a message must say 'provenance' without the filename.
    """
    source = Path(gate.__file__).read_text(encoding="utf-8")

    reads = _reads_of_the_file(_code_without_docstrings(source))

    assert reads == [] or all("is trained but its provenance.json" in one for one in reads), reads


def _arguments(fixtures: dict[str, Any]) -> dict[str, Any]:
    keys = [
        *("candidate", "incumbent", "heldout", "tasks", "public", "pool", "weights"),
        *("runs", "workspace", "timeout", "recorded_on", "run_id", "engine"),
    ]
    return {key: fixtures[key] for key in keys}


def test_a_v2_digest_edited_after_sealing_is_refused_before_any_scoring(tmp_path: Path) -> None:
    fixtures = _gate_fixtures(tmp_path)
    path = fixtures["candidate"] / sft.CHECKPOINT_FILE
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["schema"] == sft.CHECKPOINT_SCHEMA_V2
    document["dataset_digest"] = "e" * 64
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(sft.CheckpointUnverified):
        gate.run_gate(**_arguments(fixtures))

    assert fixtures["used_checkpoints"] == [], "the engine must never have been invoked"
    assert not (fixtures["runs"] / gate.PROMOTIONS_DIR / "gate-001.json").exists()


def test_a_trained_v1_checkpoint_with_no_digest_keeps_its_refusal(tmp_path: Path) -> None:
    fixtures = _gate_fixtures(tmp_path)
    checkpoint = _rewrite(fixtures["candidate_checkpoint"], lambda d: d.update(dataset_digest=7))

    with pytest.raises(gate.DatasetDigestUnrecorded) as caught:
        gate._checkpoint_dataset_digest(checkpoint)

    message = str(caught.value)
    assert "found 7; expected a 64-digit lowercase sha256" in message, message
    assert "provenance.json records no well-formed `dataset_digest`" in message, message


def test_a_checkpoint_naming_no_base_is_unverified_not_a_key_error(tmp_path: Path) -> None:
    fixtures = _gate_fixtures(tmp_path)
    checkpoint = _rewrite(fixtures["candidate_checkpoint"], lambda d: d.pop("base"))

    with pytest.raises(sft.CheckpointUnverified, match="names no base"):
        gate._checkpoint_base(checkpoint)


def test_the_gate_answers_from_the_object_not_from_the_file_on_disk(tmp_path: Path) -> None:
    """Check-then-use: a file edited after `verify_checkpoint` cannot change what the gate reads."""
    fixtures = _gate_fixtures(tmp_path)
    checkpoint = sft.verify_checkpoint(fixtures["candidate"])
    path = fixtures["candidate"] / sft.CHECKPOINT_FILE
    document = json.loads(path.read_text(encoding="utf-8"))
    document["dataset_digest"] = "e" * 64
    document["base"] = {"repo_id": "someone/else", "revision": "0000000"}
    path.write_text(json.dumps(document), encoding="utf-8")

    assert gate._checkpoint_dataset_digest(checkpoint) == "d" * 64
    assert gate._checkpoint_base(checkpoint) == {
        "repo_id": checkpoint.base_repo_id,
        "revision": checkpoint.base_revision,
    }
