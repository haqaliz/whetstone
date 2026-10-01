"""The operator end of the whole-function measurement's decision: a finished run's evidence in,
a decision out.

The command's exit *is* the pre-committed go/no-go — 0 GO, 1 NO-GO, 2 a refusal — the shape
`check-probe`, `locatability` and `addressability` gave the night door, so the decision to
build the whole-function contract is a process exit rather than an operator reading a
partition by eye. The rule and the population are fixed in `docs/planning/
whole-function-edit-finding/measurement-run/spec.md` before the run; the class fixtures here
assert every class and its place in the worst-first ladder, and the decision tests run the
boundary of the strict-majority inequality.

**No model is loaded and no network is touched.** Tasks are real two-commit donors on disk,
so checkouts are materialised against real git and the shown set is re-derived the way the run
derived it, but nothing is generated.
"""

from __future__ import annotations

import ast
import base64
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from fixtures.repos import _git
from fixtures.repos.mined import (
    MINED_CALC_BUGGY,
    MINED_CALC_FIXED,
    MINED_README_AFTER,
    MINED_README_BEFORE,
    MINED_TESTS_AFTER,
    MINED_TESTS_BEFORE,
)

from whetstone.bakeoff import measure, resolvability
from whetstone.bakeoff import stratum as stratum_module
from whetstone.bakeoff.resolvability import RULE, RolloutClass, classify_rollout, decide, main
from whetstone.bakeoff.transcript import Transcribed, Transcript
from whetstone.loop import heldout as heldout_module

#: The candidate the pinned base is measured under (PREREGISTRATION.md § 10.10).
CANDIDATE = "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit"

#: The spec's pinned 16, spelled here as the committed rule names them (spec.md "Population"),
#: and cross-pinned against `measure._PINNED_POPULATION` below.
SPEC_PINNED = (
    "donor-a-128bcb99b701",
    "donor-a-16213e62eae1",
    "donor-a-2ef3383b0ce7",
    "donor-a-2f4e497580ff",
    "donor-a-34daf85182d5",
    "donor-a-5e25b106874c",
    "donor-a-6005d7ec06f5",
    "donor-a-7975de5439dc",
    "donor-a-b7c53b77453a",
    "donor-a-d601ff2d0ec0",
    "donor-a-ec3af08b913d",
    "donor-a-f100a90e47f2",
    "donor-b-0f8651175ef8",
    "donor-b-45740535725b",
    "donor-b-c57246c7841a",
    "donor-b-dbf19c8009dd",
)

#: The overlap between the stratum membership and the held-out membership — the members that
#: are subtracted and never rolled out (spec.md "Population").
OVERLAP = ("donor-a-6884ed72a9e9", "donor-a-c6e4d4c4de87", "donor-a-c7cee63e3cab")

#: Held-out members outside the stratum, so the synthetic held-out document meets the
#: pre-committed floors while subtracting exactly the overlap.
HELDOUT_ONLY = (
    "donor-a-18265334544f",
    "donor-a-192f26c402a3",
    "donor-a-74f000a772cf",
    "donor-a-b5f840cdf71d",
    "donor-a-d2c03949ecf3",
    "donor-a-dc3be3134276",
    "donor-b-353359e9ac6e",
    "donor-b-3e3051c4192a",
    "donor-b-468e343e9fb5",
)

#: The three `NO_ORACLE` members (spec.md "Population"): no prompt is rendered for them, they
#: are `UNCLASSIFIED`, and they stay in the denominator.
NO_ORACLE = ("donor-a-128bcb99b701", "donor-a-16213e62eae1", "donor-b-45740535725b")

#: The stratum document's membership: the pinned 16 plus the overlap (19 in all).
STRATUM_MEMBERS = tuple(sorted(set(SPEC_PINNED) | set(OVERLAP)))

#: The held-out document's membership: the overlap plus nine outside the stratum (12 in all).
HELDOUT_MEMBERS = tuple(sorted(set(OVERLAP) | set(HELDOUT_ONLY)))

#: A resolvable completion: one block naming the mined fixture's `add` in `calc.py` with a
#: body at the function's indentation, against the two-line `calc.py` at `base_commit`.
def _block(path: str = "calc.py", name: str = "add", body: str = "    return a + b") -> str:
    return (
        f"EDIT {path}\n"
        f"FUNCTION {name}\n"
        f"<<<<<<< REPLACE\n"
        f"{body}\n"
        f">>>>>>> END\n"
    )


RESOLVABLE = _block()

#: A completion no block can be parsed out of.
GARBAGE = "hello there\n"

#: A body at column 0 — the indentation the format requires, violated.
COL_ZERO = (
    "EDIT calc.py\n"
    "FUNCTION add\n"
    "<<<<<<< REPLACE\n"
    "return a + b\n"
    ">>>>>>> END\n"
)

#: A body at the function's indentation with a genuine syntax error.
SYNTAX_ERROR = (
    "EDIT calc.py\n"
    "FUNCTION add\n"
    "<<<<<<< REPLACE\n"
    "    return 1 +\n"
    ">>>>>>> END\n"
)

#: An empty body: the wrapped parse refuses it with `IndentationError` (expected an indented
#: block), which the class rule makes `MALFORMED`.
EMPTY_BODY = "EDIT calc.py\nFUNCTION add\n<<<<<<< REPLACE\n>>>>>>> END\n"

#: The manifest's recorded prompt digest for every task, and the transcript's by default.
DIGEST = "0" * 64

#: The mined fixture's default files: the bug at the parent, the fix at the child.
DEFAULT_BEFORE = {
    "calc.py": MINED_CALC_BUGGY,
    "tests/test_addition.py": MINED_TESTS_BEFORE,
    "README.md": MINED_README_BEFORE,
}
DEFAULT_AFTER = {
    "calc.py": MINED_CALC_FIXED,
    "tests/test_addition.py": MINED_TESTS_AFTER,
    "README.md": MINED_README_AFTER,
}

#: A donor whose `calc.py` carries two module-level `add` functions — the ambiguous shape.
#: `multiply` is the unique name the other fixtures resolve there.
AMBIGUOUS_BEFORE = {
    "calc.py": (
        "def add(a, b):\n    return a - b\n\n\ndef add(a, b, c):\n    return a - b - c\n\n\n"
        "def multiply(a, b):\n    return a * b\n"
    ),
    "README.md": MINED_README_BEFORE,
}
AMBIGUOUS_AFTER = {
    "calc.py": (
        "def add(a, b):\n    return a + b\n\n\ndef add(a, b, c):\n    return a - b + c\n\n\n"
        "def multiply(a, b):\n    return a * b\n"
    ),
    "README.md": MINED_README_AFTER,
}

#: A donor whose only `add`-ish function is `adder` — a looser instrument matching `add` by
#: substring would resolve it; the exact-name rule must not. `multiply` is the unique name.
ADDER_BEFORE = {
    "calc.py": "def adder(a, b):\n    return a - b\n\n\ndef multiply(a, b):\n    return a * b\n",
    "README.md": MINED_README_BEFORE,
}
ADDER_AFTER = {
    "calc.py": "def adder(a, b):\n    return a + b\n\n\ndef multiply(a, b):\n    return a * b\n",
    "README.md": MINED_README_AFTER,
}

#: A donor whose `add` is a module-level `async def` — the format's async scope (spec,
#: "Format": module-level `def`/`async def`). `multiply` is the unique sync name.
ASYNC_BEFORE = {
    "calc.py": (
        "async def add(a, b):\n    return await a\n\n\n"
        "def multiply(a, b):\n    return a * b\n"
    ),
    "README.md": MINED_README_BEFORE,
}

#: A donor whose `add` lives inside a class — a method, never a module-level function.
#: `multiply` is the unique module-level name.
METHOD_BEFORE = {
    "calc.py": (
        "class Calculator:\n    def add(self, a, b):\n        return a - b\n\n\n"
        "def multiply(a, b):\n    return a * b\n"
    ),
    "README.md": MINED_README_BEFORE,
}
METHOD_AFTER = {
    "calc.py": (
        "class Calculator:\n    def add(self, a, b):\n        return a + b\n\n\n"
        "def multiply(a, b):\n    return a * b\n"
    ),
    "README.md": MINED_README_AFTER,
}


def _reader(files: dict[str, str]):
    """An in-memory stand-in for `locatability.checkout_reader`, for classify-level tests."""

    def read(path: str) -> str | None:
        return files.get(path)

    return read


def _difficulty() -> dict[str, int]:
    """One measured-difficulty entry: all seven fields the loaders require, minimum values."""
    return {"files": 1, "hunks": 1, "added": 1, "deleted": 1, "f2p": 1, "pins": 0, "blobs": 1}


def _stratum_document(root: Path, members: tuple[str, ...], **fields: Any) -> Path:
    """A valid `whetstone-stratum/1` document whose membership is `members` — the
    `test_measure_driver` builder's shape, sealed through the module's own digest."""
    corpus = sorted({*members, "extra-stratum-1", "extra-stratum-2"})
    raw: dict[str, Any] = {
        "schema": stratum_module.STRATUM_SCHEMA,
        "rule_digest": stratum_module.rule_digest(),
        "band": {"max_non_test_files": 1, "max_hunks": 2, "max_changed_lines": 30},
        "corpus": corpus,
        "donor_heads": {},
        "difficulty": {task_id: _difficulty() for task_id in corpus},
        "refusals": {},
        "membership": list(members),
    }
    raw.update(fields)
    raw["document_digest"] = stratum_module.document_digest_of(raw)
    out = root / "easier.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(raw))
    return out


def _heldout_document(root: Path, members: tuple[str, ...], **fields: Any) -> Path:
    """A valid `whetstone-heldout/1` document whose membership is `members` — the
    `test_measure_driver` builder's shape, sealed through the module's own digest."""
    sorted_members = sorted(members)
    corpus = sorted({*members, "extra-heldout-1", "extra-heldout-2"})
    bands: dict[str, int] = {}
    for index, task_id in enumerate(sorted_members):
        bands[task_id] = index // 4
    for task_id in corpus:
        bands.setdefault(task_id, 0)
    raw: dict[str, Any] = {
        "schema": heldout_module.HELDOUT_SCHEMA,
        "rule_digest": heldout_module.rule_digest(),
        "rule": {
            "bands": heldout_module.HELDOUT_BANDS,
            "min_heldout": heldout_module.MIN_HELDOUT,
            "min_per_band": heldout_module.MIN_PER_BAND,
            "split_seed": heldout_module.SPLIT_SEED,
        },
        "corpus": corpus,
        "difficulty": {task_id: _difficulty() for task_id in corpus},
        "bands": bands,
        "refusals": {},
        "excluded": {},
        "membership": list(members),
    }
    raw.update(fields)
    raw["document_digest"] = heldout_module.document_digest_of(raw)
    out = root / "source-b.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(raw))
    return out


def _digest(path: Path) -> str:
    """The document's own `document_digest` field — what the manifest records."""
    return str(json.loads(path.read_text(encoding="utf-8"))["document_digest"])


def _manifest(
    root: Path,
    tasks: tuple[str, ...],
    *,
    stratum: Path,
    heldout: Path,
    **fields: Any,
) -> Path:
    """A valid `whetstone-measure/1` manifest whose task list is `tasks`."""
    raw: dict[str, Any] = {
        "schema": measure.MANIFEST_SCHEMA,
        "run_id": "measure-0123456789ab",
        "recorded_on": "2026-10-01",
        "candidate": {"repo_id": CANDIDATE, "revision": "a" * 64},
        "run_seed": measure.RUN_SEED,
        "tasks": list(tasks),
        "stratum_document_digest": _digest(stratum),
        "heldout_document_digest": _digest(heldout),
        "prompt_sha256": {task_id: DIGEST for task_id in tasks},
        "control": {task_id: "INTACT" for task_id in tasks},
        "tool_versions": {},
    }
    raw.update(fields)
    out = root / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(raw))
    return out


def _commit(donor: Path, files: dict[str, str], *, subject: str) -> str:
    """Write `files` into `donor`, commit them, and return the resulting SHA."""
    for relative, contents in files.items():
        target = donor / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents)
    _git(["add", "--all"], cwd=donor)
    _git(["commit", "--quiet", "--message", subject], cwd=donor)
    return _git(["rev-parse", "HEAD"], cwd=donor).strip()


def _donor(root: Path, task_id: str, before: dict[str, str], after: dict[str, str]) -> None:
    """A two-commit donor under `root` and the task manifest mined from its second commit.

    `base_commit` is the first commit; the second commit's touched paths are the shown set —
    the shape `build_mined_task` gives, with the files parameterised so a fixture can carry
    several module-level functions, a method, or a near-miss name.
    """
    donor = root / "donor"
    donor.mkdir(parents=True)
    _git(["init", "--quiet", "--initial-branch=main"], cwd=donor)
    parent = _commit(donor, before, subject="Seed the calculator")
    commit = _commit(donor, after, subject=f"Fix addition ({task_id})")
    manifest = {
        "task_id": task_id,
        "source": "private",
        "repo_url": str(donor),
        "base_commit": parent,
        "environment": {"python": "3.12", "pins": [], "import_roots": ["."]},
        "problem_statement": f"Fix addition ({task_id})",
        "fail_to_pass": ["tests/test_addition.py::test_add_is_addition"],
        "pass_to_pass": ["tests/test_addition.py::test_adding_zero_is_the_identity"],
        "test_blobs": {
            "tests/test_addition.py": base64.b64encode(MINED_TESTS_AFTER.encode()).decode(
                "ascii"
            )
        },
        "provenance": {"donor": donor.name, "commit": commit, "parent": parent},
    }
    manifest_path = root / f"{task_id}.json"
    manifest_path.write_text(json.dumps(manifest))


def _inputs(
    root: Path, overrides: dict[str, tuple[dict[str, str], dict[str, str]]]
) -> tuple[Path, Path, Path]:
    """The pinned 16 tasks as real two-commit donors, plus valid stratum/held-out documents.

    `overrides` maps a task id to the (before, after) file maps its donor is built from;
    every other task gets the mined fixture's default shape.
    """
    corpus = root / "private"
    corpus.mkdir()
    for task_id in SPEC_PINNED:
        before, after = overrides.get(task_id, (DEFAULT_BEFORE, DEFAULT_AFTER))
        _donor(root / f"donor-{task_id}", task_id, before, after)
        shutil.copy(root / f"donor-{task_id}" / f"{task_id}.json", corpus / f"{task_id}.json")
    stratum = _stratum_document(root / "docs", STRATUM_MEMBERS)
    heldout = _heldout_document(root / "docs", HELDOUT_MEMBERS)
    return corpus, stratum, heldout


def _evidence(
    tmp_path: Path,
    inputs: tuple[Path, Path, Path],
    rows: list[tuple[str, str | None, str | None]],
    *,
    corpus: Path | None = None,
    stratum: Path | None = None,
    heldout: Path | None = None,
    manifest_tasks: tuple[str, ...] = SPEC_PINNED,
    **manifest_fields: Any,
) -> list[str]:
    """A manifest, a transcript and the command's arguments for one instrument invocation.

    A row is (task_id, completion, record digest): a `None` completion writes no transcript
    record for it — the missing-evidence case — and a record digest other than `DIGEST`
    makes the record disagree with the manifest's recorded digest.
    """
    default_corpus, default_stratum, default_heldout = inputs
    chosen_stratum = stratum or default_stratum
    chosen_heldout = heldout or default_heldout
    transcript = Transcript(tmp_path / "transcript.jsonl")
    for task_id, completion, record_digest in rows:
        if completion is not None:
            transcript.append(
                Transcribed(
                    candidate=CANDIDATE,
                    task_id=task_id,
                    prompt_sha256=record_digest or DIGEST,
                    prompt="irrelevant to resolvability",
                    completion=completion,
                    attempt=1,
                    decision="graded",
                )
            )
    manifest = _manifest(
        tmp_path, manifest_tasks, stratum=chosen_stratum, heldout=chosen_heldout,
        **manifest_fields,
    )
    return [
        "--manifest",
        str(manifest),
        "--transcript",
        str(transcript.path),
        "--tasks",
        str(corpus or default_corpus),
        "--stratum",
        str(chosen_stratum),
        "--heldout",
        str(chosen_heldout),
        "--out",
        str(tmp_path / "out" / "resolvability.json"),
    ]


def _all_sixteen(completion: str) -> list[tuple[str, str | None, str | None]]:
    """One row per pinned task, every completion the same."""
    return [(task_id, completion, None) for task_id in SPEC_PINNED]


def _one_special(completion: str) -> list[tuple[str, str | None, str | None]]:
    """The first pinned task gets `completion`; the other fifteen get the resolvable one."""
    return [(SPEC_PINNED[0], completion, None), *(
        (task_id, RESOLVABLE, None) for task_id in SPEC_PINNED[1:]
    )]


def _special_rows(
    special_task: str, completion: str
) -> list[tuple[str, str | None, str | None]]:
    """Rows for the special fixture: `special_task` gets `completion`; the other two special
    donors resolve their unique `multiply`; the thirteen default donors resolve `add`."""
    special = {SPEC_PINNED[2], SPEC_PINNED[3], SPEC_PINNED[4]}
    rows: list[tuple[str, str | None, str | None]] = []
    for task_id in SPEC_PINNED:
        if task_id == special_task:
            rows.append((task_id, completion, None))
        elif task_id in special:
            rows.append((task_id, _block(name="multiply", body="    return a * b"), None))
        else:
            rows.append((task_id, RESOLVABLE, None))
    return rows


@pytest.fixture(scope="module")
def inputs(tmp_path_factory: pytest.TempPathFactory):
    """The pinned 16 in the mined default shape — every donor's `calc.py` carries one `add`."""
    return _inputs(tmp_path_factory.mktemp("resolvability-inputs"), {})


@pytest.fixture(scope="module")
def special_inputs(tmp_path_factory: pytest.TempPathFactory):
    """The pinned 16 with three donors carrying the adversarial shapes: two `add` functions,
    a `adder`-only file, and a method-only file."""
    return _inputs(
        tmp_path_factory.mktemp("resolvability-special"),
        {
            SPEC_PINNED[2]: (AMBIGUOUS_BEFORE, AMBIGUOUS_AFTER),
            SPEC_PINNED[3]: (ADDER_BEFORE, ADDER_AFTER),
            SPEC_PINNED[4]: (METHOD_BEFORE, METHOD_AFTER),
        },
    )


# --- The pre-committed rule and the exit -----------------------------------------------------


def test_the_pinned_population_constant_is_the_specs_list() -> None:
    """The module's constant is the spec's 16 ids, spelled here — a drift in either is red."""
    assert measure._PINNED_POPULATION == SPEC_PINNED


def test_the_rule_constant_is_the_specs_sentence() -> None:
    """The inequality is a constant in code, cross-pinned to the committed spec's sentence."""
    assert RULE == "GO iff count(RESOLVABLE) * 2 > population"


def test_a_majority_resolvable_population_exits_go(tmp_path: Path, inputs: Any) -> None:
    arguments = _evidence(tmp_path, inputs, _all_sixteen(RESOLVABLE))
    assert main(arguments) == 0
    written = json.loads((tmp_path / "out" / "resolvability.json").read_text())
    assert written["schema"] == "whetstone-resolvability/1"
    assert written["run_id"] == "measure-0123456789ab"
    assert written["candidate"] == {"repo_id": CANDIDATE, "revision": "a" * 64}
    assert written["rule"] == RULE
    assert (written["population"], written["decision"]) == (16, "GO")
    assert written["counts"] == {"RESOLVABLE": 16}
    assert written["sub_counts"] == {"outside_shown_set": 0, "splice_in_context": 16}
    assert {row["task_id"]: row["class"] for row in written["rollouts"]} == {
        task_id: "RESOLVABLE" for task_id in SPEC_PINNED
    }
    assert all(row["splice_in_context"] for row in written["rollouts"])


def test_exactly_half_resolvable_is_no_go(tmp_path: Path, inputs: Any) -> None:
    """8 of 16 is exactly half, and the rule is strict-majority: NO-GO, exit 1."""
    rows = [(task_id, RESOLVABLE, None) for task_id in SPEC_PINNED[:8]]
    rows += [(task_id, GARBAGE, None) for task_id in SPEC_PINNED[8:]]
    assert main(_evidence(tmp_path, inputs, rows)) == 1
    written = json.loads((tmp_path / "out" / "resolvability.json").read_text())
    assert written["counts"] == {"MALFORMED": 8, "RESOLVABLE": 8}


def test_a_minority_resolvable_population_is_no_go(tmp_path: Path, inputs: Any) -> None:
    rows = [(SPEC_PINNED[0], RESOLVABLE, None), *(
        (task_id, GARBAGE, None) for task_id in SPEC_PINNED[1:]
    )]
    assert main(_evidence(tmp_path, inputs, rows)) == 1


def test_missing_evidence_is_unclassified_and_still_counted(
    tmp_path: Path, inputs: Any
) -> None:
    """No graded record for a task: the question could not be asked, and stays in the total."""
    rows = [(task_id, RESOLVABLE, None) for task_id in SPEC_PINNED[:8]]
    rows += [(SPEC_PINNED[8], None, None)]
    rows += [(task_id, GARBAGE, None) for task_id in SPEC_PINNED[9:]]
    assert main(_evidence(tmp_path, inputs, rows)) == 1
    written = json.loads((tmp_path / "out" / "resolvability.json").read_text())
    assert written["counts"] == {"MALFORMED": 7, "RESOLVABLE": 8, "UNCLASSIFIED": 1}
    unclassified = next(
        row for row in written["rollouts"] if row["class"] == "UNCLASSIFIED"
    )
    assert unclassified["task_id"] == SPEC_PINNED[8]
    assert "graded record" in unclassified["detail"]


def test_a_transcript_record_whose_prompt_digest_disagrees_is_unclassified(
    tmp_path: Path, inputs: Any
) -> None:
    """A record that does not match the manifest's recorded digest is not this run's evidence:
    `UNCLASSIFIED`, counted, never a refusal — the spec's class, `addressability`'s behaviour."""
    rows = [(task_id, RESOLVABLE, None) for task_id in SPEC_PINNED[:8]]
    rows += [(SPEC_PINNED[8], RESOLVABLE, "1" * 64)]
    rows += [(task_id, GARBAGE, None) for task_id in SPEC_PINNED[9:]]
    assert main(_evidence(tmp_path, inputs, rows)) == 1
    written = json.loads((tmp_path / "out" / "resolvability.json").read_text())
    assert written["counts"] == {"MALFORMED": 7, "RESOLVABLE": 8, "UNCLASSIFIED": 1}
    unclassified = next(
        row for row in written["rollouts"] if row["class"] == "UNCLASSIFIED"
    )
    assert "prompt digest" in unclassified["detail"]


def test_a_task_nobody_offered_is_unclassified(tmp_path: Path, inputs: Any) -> None:
    """A corpus that does not carry one of the pinned tasks leaves it UNCLASSIFIED, counted."""
    corpus, _, _ = inputs
    reduced = tmp_path / "corpus-minus-one"
    reduced.mkdir()
    for name in sorted(Path(corpus).iterdir()):
        if name.name != f"{SPEC_PINNED[0]}.json":
            shutil.copy(name, reduced / name.name)
    assert main(_evidence(tmp_path, inputs, _all_sixteen(RESOLVABLE), corpus=reduced)) == 0
    written = json.loads((tmp_path / "out" / "resolvability.json").read_text())
    assert written["counts"] == {"RESOLVABLE": 15, "UNCLASSIFIED": 1}
    unclassified = next(
        row for row in written["rollouts"] if row["class"] == "UNCLASSIFIED"
    )
    assert unclassified["task_id"] == SPEC_PINNED[0]
    assert "not offered" in unclassified["detail"]


def test_the_no_oracle_members_are_unclassified_and_stay_in_the_denominator(
    tmp_path: Path, inputs: Any
) -> None:
    """No prompt is rendered for the `NO_ORACLE` members, so no record exists for them: they
    are `UNCLASSIFIED`, counted, and a population with them can still GO (spec R5 — the rule
    claims no scorable filter)."""
    rows = [
        (task_id, RESOLVABLE, None) for task_id in SPEC_PINNED if task_id not in NO_ORACLE
    ]
    assert main(_evidence(tmp_path, inputs, rows)) == 0
    written = json.loads((tmp_path / "out" / "resolvability.json").read_text())
    assert written["counts"] == {"RESOLVABLE": 13, "UNCLASSIFIED": 3}
    assert written["decision"] == "GO"


# --- One fixture per class, and its place in the worst-first ladder -------------------------


def test_a_completion_no_block_parses_out_of_is_malformed(
    tmp_path: Path, inputs: Any
) -> None:
    """`parse_edit_block` refused the whole completion — `MALFORMED` with the parser's reason."""
    arguments = _evidence(tmp_path, inputs, _one_special(GARBAGE))
    assert main(arguments) == 0
    written = json.loads((tmp_path / "out" / "resolvability.json").read_text())
    assert written["counts"] == {"MALFORMED": 1, "RESOLVABLE": 15}
    row = next(row for row in written["rollouts"] if row["task_id"] == SPEC_PINNED[0])
    assert row["class"] == "MALFORMED"
    assert row["detail"] == "missing EDIT header"


def test_a_body_at_column_zero_is_malformed(tmp_path: Path, inputs: Any) -> None:
    """A body at column 0 fails the wrapped parse with `IndentationError` — the format
    requires the body at the function's indentation (spec R1's class rule)."""
    arguments = _evidence(tmp_path, inputs, _one_special(COL_ZERO))
    assert main(arguments) == 0
    written = json.loads((tmp_path / "out" / "resolvability.json").read_text())
    assert written["counts"] == {"MALFORMED": 1, "RESOLVABLE": 15}
    row = next(row for row in written["rollouts"] if row["task_id"] == SPEC_PINNED[0])
    assert row["class"] == "MALFORMED"
    assert "IndentationError" in row["detail"]


def test_an_empty_body_is_malformed(tmp_path: Path, inputs: Any) -> None:
    """An empty body fails the wrapped parse with `IndentationError` (expected an indented
    block) — `MALFORMED`, never a quiet no-op (plan § 6's class edge)."""
    arguments = _evidence(tmp_path, inputs, _one_special(EMPTY_BODY))
    assert main(arguments) == 0
    written = json.loads((tmp_path / "out" / "resolvability.json").read_text())
    assert written["counts"] == {"MALFORMED": 1, "RESOLVABLE": 15}


def test_a_body_both_malformed_and_not_parseable_is_malformed() -> None:
    """A col-0 body that also carries a genuine syntax error raises `IndentationError` — a
    `SyntaxError` subclass — first; a looser instrument catching `SyntaxError` would call it
    `NOT_PARSEABLE`, the class rule calls it `MALFORMED`. The ladder is a total order."""
    classified = classify_rollout(
        "EDIT calc.py\nFUNCTION add\n<<<<<<< REPLACE\nreturn 1 +\n>>>>>>> END\n",
        _reader({"calc.py": MINED_CALC_BUGGY}),
        shown=frozenset({"calc.py"}),
    )
    assert classified.klass is RolloutClass.MALFORMED


def test_the_worst_first_ladder_places_malformed_above_no_file() -> None:
    """A completion that is both `NO_FILE` (an absent path) and `MALFORMED` (a col-0 body)
    resolves to `MALFORMED` — worst first, not first checked."""
    classified = classify_rollout(
        "EDIT absent.py\nFUNCTION add\n<<<<<<< REPLACE\nreturn a + b\n>>>>>>> END\n",
        _reader({}),
        shown=frozenset(),
    )
    assert classified.klass is RolloutClass.MALFORMED


def test_an_indentation_error_is_malformed_and_a_syntax_error_is_not_parseable() -> None:
    """The IndentationError-vs-SyntaxError pair: the same body at the function's indentation
    with a genuine syntax error is `NOT_PARSEABLE`; at column 0 it is `MALFORMED`."""
    pair = [
        (COL_ZERO, RolloutClass.MALFORMED),
        (SYNTAX_ERROR, RolloutClass.NOT_PARSEABLE),
    ]
    for completion, expected in pair:
        classified = classify_rollout(
            completion, _reader({"calc.py": MINED_CALC_BUGGY}), shown=frozenset({"calc.py"})
        )
        assert classified.klass is expected


def test_a_path_outside_the_shown_set_is_no_file(tmp_path: Path, inputs: Any) -> None:
    """The held test path is real at `base_commit` but the run never showed it: `NO_FILE`
    with the outside-shown-set flag — held-test paths count beside (spec, "Sub-counts")."""
    completion = (
        "EDIT tests/test_addition.py\n"
        "FUNCTION test_adding_zero_is_the_identity\n"
        "<<<<<<< REPLACE\n"
        "    assert True\n"
        ">>>>>>> END\n"
    )
    arguments = _evidence(tmp_path, inputs, _one_special(completion))
    assert main(arguments) == 0
    written = json.loads((tmp_path / "out" / "resolvability.json").read_text())
    assert written["counts"] == {"NO_FILE": 1, "RESOLVABLE": 15}
    assert written["sub_counts"] == {"outside_shown_set": 1, "splice_in_context": 15}
    row = next(row for row in written["rollouts"] if row["task_id"] == SPEC_PINNED[0])
    assert row["class"] == "NO_FILE"
    assert row["outside_shown_set"] is True
    assert "shown" in row["detail"]


def test_a_path_absent_from_the_checkout_is_no_file(tmp_path: Path, inputs: Any) -> None:
    """A path that is not in the checkout at `base_commit` is `NO_FILE` — and not real, so it
    never counts as outside the shown set."""
    completion = (
        "EDIT no-such-file.py\n"
        "FUNCTION add\n"
        "<<<<<<< REPLACE\n"
        "    return 1\n"
        ">>>>>>> END\n"
    )
    arguments = _evidence(tmp_path, inputs, _one_special(completion))
    assert main(arguments) == 0
    written = json.loads((tmp_path / "out" / "resolvability.json").read_text())
    assert written["counts"] == {"NO_FILE": 1, "RESOLVABLE": 15}
    assert written["sub_counts"] == {"outside_shown_set": 0, "splice_in_context": 15}
    row = next(row for row in written["rollouts"] if row["task_id"] == SPEC_PINNED[0])
    assert row["class"] == "NO_FILE"
    assert "no such file" in row["detail"]


def test_an_escaping_path_is_no_file(tmp_path: Path, inputs: Any) -> None:
    """An absolute or `..`-climbing path is `NO_FILE` before anything is read — the
    `locatability` escape rule."""
    arguments = _evidence(
        tmp_path,
        inputs,
        _one_special(
            "EDIT /etc/passwd\nFUNCTION add\n<<<<<<< REPLACE\n    return 1\n>>>>>>> END\n"
        ),
    )
    assert main(arguments) == 0
    written = json.loads((tmp_path / "out" / "resolvability.json").read_text())
    assert written["counts"] == {"NO_FILE": 1, "RESOLVABLE": 15}
    row = next(row for row in written["rollouts"] if row["task_id"] == SPEC_PINNED[0])
    assert "climbs" in row["detail"]


def test_a_name_resolving_to_several_module_level_functions_is_ambiguous(
    tmp_path: Path, special_inputs: Any
) -> None:
    """The ambiguous donor's `calc.py` carries two module-level `add` functions; the name
    resolves to both — `AMBIGUOUS`, never a coin toss."""
    arguments = _evidence(tmp_path, special_inputs, _special_rows(SPEC_PINNED[2], RESOLVABLE))
    assert main(arguments) == 0
    written = json.loads((tmp_path / "out" / "resolvability.json").read_text())
    assert written["counts"] == {"AMBIGUOUS": 1, "RESOLVABLE": 15}
    row = next(row for row in written["rollouts"] if row["task_id"] == SPEC_PINNED[2])
    assert row["class"] == "AMBIGUOUS"
    assert "2" in row["detail"]


def test_a_name_matching_no_module_level_function_is_unknown(
    tmp_path: Path, inputs: Any
) -> None:
    """The mined `calc.py` carries `add` and nothing else; any other name is
    `UNKNOWN_FUNCTION` — the name is looked up by exact identity, never by guesswork."""
    completion = (
        "EDIT calc.py\n"
        "FUNCTION multiply\n"
        "<<<<<<< REPLACE\n"
        "    return a * b\n"
        ">>>>>>> END\n"
    )
    arguments = _evidence(tmp_path, inputs, _one_special(completion))
    assert main(arguments) == 0
    written = json.loads((tmp_path / "out" / "resolvability.json").read_text())
    assert written["counts"] == {"RESOLVABLE": 15, "UNKNOWN_FUNCTION": 1}
    row = next(row for row in written["rollouts"] if row["task_id"] == SPEC_PINNED[0])
    assert row["class"] == "UNKNOWN_FUNCTION"
    assert "not a module-level function" in row["detail"]


def test_a_loose_substring_match_is_unknown_function(
    tmp_path: Path, special_inputs: Any
) -> None:
    """The weaker-check differential, name half: a looser instrument matching `add` inside
    `adder` would resolve this; the exact-name rule scores it `UNKNOWN_FUNCTION`."""
    arguments = _evidence(tmp_path, special_inputs, _special_rows(SPEC_PINNED[3], RESOLVABLE))
    assert main(arguments) == 0
    written = json.loads((tmp_path / "out" / "resolvability.json").read_text())
    assert written["counts"] == {"RESOLVABLE": 15, "UNKNOWN_FUNCTION": 1}
    row = next(row for row in written["rollouts"] if row["task_id"] == SPEC_PINNED[3])
    assert row["class"] == "UNKNOWN_FUNCTION"


def test_a_method_name_is_unknown_function(tmp_path: Path, special_inputs: Any) -> None:
    """The weaker-check differential, method half: `add` inside the class is a method, never
    a module-level function — a looser instrument would resolve it, the spec's rule does not."""
    arguments = _evidence(tmp_path, special_inputs, _special_rows(SPEC_PINNED[4], RESOLVABLE))
    assert main(arguments) == 0
    written = json.loads((tmp_path / "out" / "resolvability.json").read_text())
    assert written["counts"] == {"RESOLVABLE": 15, "UNKNOWN_FUNCTION": 1}
    row = next(row for row in written["rollouts"] if row["task_id"] == SPEC_PINNED[4])
    assert row["class"] == "UNKNOWN_FUNCTION"


def test_a_body_with_a_genuine_syntax_error_is_not_parseable(
    tmp_path: Path, inputs: Any
) -> None:
    """A body at the function's indentation that does not parse is `NOT_PARSEABLE` — any
    wrapped-parse failure that is not an `IndentationError`."""
    arguments = _evidence(tmp_path, inputs, _one_special(SYNTAX_ERROR))
    assert main(arguments) == 0
    written = json.loads((tmp_path / "out" / "resolvability.json").read_text())
    assert written["counts"] == {"NOT_PARSEABLE": 1, "RESOLVABLE": 15}
    row = next(row for row in written["rollouts"] if row["task_id"] == SPEC_PINNED[0])
    assert row["class"] == "NOT_PARSEABLE"
    assert "wrapped parse" in row["detail"]


def test_a_resolvable_completion_splices_in_context() -> None:
    """The resolvable fixture: unique module-level function, body at the function's
    indentation, wrapped parse passing — and the file with the body spliced over the extent
    still parses, so the splice-in-context flag is set."""
    classified = classify_rollout(
        RESOLVABLE, _reader({"calc.py": MINED_CALC_BUGGY}), shown=frozenset({"calc.py"})
    )
    assert classified.klass is RolloutClass.RESOLVABLE
    assert classified.splice_in_context is True
    assert classified.outside_shown_set is False


def test_an_async_targets_body_with_await_is_resolvable() -> None:
    """An `await`-carrying body for an async target resolves — the format's async scope
    (spec, "Format": module-level `async def`) is in the format, and the body the base
    wrote for it is the body the harness would splice; the file with the splice still
    parses, so the splice-in-context flag is set."""
    classified = classify_rollout(
        _block(name="add", body="    return await a"),
        _reader({"calc.py": ASYNC_BEFORE["calc.py"]}),
        shown=frozenset({"calc.py"}),
    )
    assert classified.klass is RolloutClass.RESOLVABLE
    assert classified.splice_in_context is True


def test_a_sync_targets_body_with_yield_is_resolvable() -> None:
    """A `yield`-carrying body for a sync target stays resolvable — the sync wrapper keeps
    its kind; the sync path must not regress when the wrapper follows the target's kind."""
    classified = classify_rollout(
        _block(body="    yield a + b"),
        _reader({"calc.py": MINED_CALC_BUGGY}),
        shown=frozenset({"calc.py"}),
    )
    assert classified.klass is RolloutClass.RESOLVABLE
    assert classified.splice_in_context is True


def test_the_wrapped_parse_follows_the_resolved_targets_kind() -> None:
    """The synthetic wrapper's kind follows the resolved target's kind: an async target's
    body is parsed inside an `async def`, a sync target's inside a `def` (spec, "Format":
    module-level `def`/`async def` are in scope). `ast.parse` does not itself enforce the
    async context — `'await' outside async function` is a compile-time error, never a
    parse-time one — so the wrapper's kind is the gate's own contract: it must wrap the
    body in the kind the instrument resolved for the function the harness would splice."""
    body = "    return await a"
    async_wrapped = ast.parse(resolvability._WRAP_ASYNC + body)
    sync_wrapped = ast.parse(resolvability._WRAP + body)
    assert isinstance(async_wrapped.body[0], ast.AsyncFunctionDef)
    assert isinstance(sync_wrapped.body[0], ast.FunctionDef)


# --- The decision inequality (the pure function, at the exact-half boundary) -----------------


def test_one_of_three_resolvable_is_no_go() -> None:
    """1 of 3 is a minority: 1 * 2 = 2 is not > 3 — NO-GO."""
    classes = [RolloutClass.RESOLVABLE, RolloutClass.NOT_PARSEABLE, RolloutClass.NOT_PARSEABLE]
    assert decide(classes).value == "NO-GO"


def test_two_of_three_resolvable_is_go() -> None:
    """2 of 3 is a strict majority: 2 * 2 = 4 > 3 — GO. The exact-half boundary."""
    classes = [RolloutClass.RESOLVABLE, RolloutClass.RESOLVABLE, RolloutClass.NOT_PARSEABLE]
    assert decide(classes).value == "GO"


def test_an_empty_population_is_refused_not_decided() -> None:
    """'Nothing to classify' is a join bug or the wrong manifest, never a result."""
    with pytest.raises(ValueError, match="empty"):
        decide([])


def test_the_decision_is_blind_to_the_sub_counts() -> None:
    """A population of 2 RESOLVABLE and 1 other is GO (2 * 2 > 3) whatever the sub-counts say
    — the decision is a pure function of the classes (spec, "Sub-counts": beside, never
    decisive)."""
    classes = [RolloutClass.RESOLVABLE, RolloutClass.RESOLVABLE, RolloutClass.NOT_PARSEABLE]
    assert decide(classes).value == "GO"


def test_an_unclassified_member_stays_in_the_denominator_and_can_still_go() -> None:
    """`UNCLASSIFIED` counts in the population: 2 RESOLVABLE of 3 is still GO with one
    unclassifiable member (spec, "Classes": stays in the denominator; never a refusal)."""
    classes = [RolloutClass.RESOLVABLE, RolloutClass.RESOLVABLE, RolloutClass.UNCLASSIFIED]
    assert decide(classes).value == "GO"


# --- The refusals: exit 2, a named reason, nothing written ------------------------------------


def test_missing_manifest_is_refused_and_nothing_is_written(
    tmp_path: Path, inputs: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = _evidence(tmp_path, inputs, _all_sixteen(RESOLVABLE))
    arguments[arguments.index("--manifest") + 1] = str(tmp_path / "absent.json")
    assert main(arguments) == 2
    assert "absent.json" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_missing_transcript_is_refused_and_nothing_is_written(
    tmp_path: Path, inputs: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = _evidence(tmp_path, inputs, _all_sixteen(RESOLVABLE))
    arguments[arguments.index("--transcript") + 1] = str(tmp_path / "absent.jsonl")
    assert main(arguments) == 2
    assert "absent.jsonl" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_a_manifest_with_an_unknown_schema_is_refused(
    tmp_path: Path, inputs: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = _evidence(
        tmp_path, inputs, _all_sixteen(RESOLVABLE), schema="whetstone-measure/2"
    )
    assert main(arguments) == 2
    assert "schema" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_an_empty_population_manifest_is_refused(
    tmp_path: Path, inputs: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = _evidence(
        tmp_path, inputs, [], manifest_tasks=(), prompt_sha256={}
    )
    assert main(arguments) == 2
    assert "empty" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_a_task_set_that_is_not_the_pinned_population_is_refused(
    tmp_path: Path, inputs: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    intruder = (*sorted(set(SPEC_PINNED) - {SPEC_PINNED[0]}), "intruder-task")
    arguments = _evidence(
        tmp_path,
        inputs,
        _all_sixteen(RESOLVABLE),
        manifest_tasks=intruder,
        prompt_sha256={task_id: DIGEST for task_id in intruder},
    )
    assert main(arguments) == 2
    assert "pinned" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_a_manifest_that_records_a_different_document_digest_is_refused(
    tmp_path: Path, inputs: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """The manifest records a stratum digest the committed document does not carry — the
    instrument was pointed at documents the run did not consume."""
    arguments = _evidence(tmp_path, inputs, _all_sixteen(RESOLVABLE))
    manifest = Path(arguments[arguments.index("--manifest") + 1])
    raw = json.loads(manifest.read_text())
    raw["stratum_document_digest"] = "1" * 64
    manifest.write_text(json.dumps(raw))
    assert main(arguments) == 2
    assert "digest" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_a_hand_edited_document_is_refused_by_the_document_digest(
    tmp_path: Path, inputs: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """A document whose `document_digest` no longer matches its payload is refused by name."""
    _, _, heldout = inputs
    tampered = _stratum_document(tmp_path / "tampered-docs", STRATUM_MEMBERS)
    raw = json.loads(tampered.read_text())
    raw["difficulty"][SPEC_PINNED[0]]["files"] = 2
    tampered.write_text(json.dumps(raw))
    arguments = _evidence(
        tmp_path,
        inputs,
        _all_sixteen(RESOLVABLE),
        stratum=tampered,
        heldout=heldout,
    )
    assert main(arguments) == 2
    assert "digest" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_an_unreadable_corpus_is_refused(
    tmp_path: Path, inputs: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = _evidence(
        tmp_path, inputs, _all_sixteen(RESOLVABLE), corpus=tmp_path / "no-such-corpus"
    )
    assert main(arguments) == 2
    assert "corpus" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_a_relative_output_path_is_refused(
    tmp_path: Path, inputs: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """A relative `--out` resolves against wherever the process was started — the runbook's
    known pitfall, refused here rather than recorded."""
    arguments = _evidence(tmp_path, inputs, _all_sixteen(RESOLVABLE))
    arguments[arguments.index("--out") + 1] = "relative.json"
    assert main(arguments) == 2
    assert "absolute" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


# --- Determinism -----------------------------------------------------------------------------


def test_the_document_is_byte_identical_across_hash_seeds(tmp_path: Path, inputs: Any) -> None:
    arguments = _evidence(tmp_path, inputs, _all_sixteen(RESOLVABLE))
    out = Path(arguments[-1])
    written = []
    for seed in ("0", "12345"):
        # Removed before each run, so a second run that wrote nothing cannot pass by re-reading
        # the first run's file.
        out.unlink(missing_ok=True)
        environment = {**os.environ, "PYTHONHASHSEED": seed}
        subprocess.run(
            [sys.executable, "-m", "whetstone.bakeoff.resolvability", *arguments],
            env=environment,
            check=False,
        )
        written.append(out.read_bytes())
    assert written[0] == written[1]


# --- The guards ------------------------------------------------------------------------------


def test_the_module_loads_no_model_and_no_driver() -> None:
    source = Path(__file__).parents[2] / "src" / "whetstone" / "bakeoff" / "resolvability.py"
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = {
        name
        for name in imported
        if name.split(".")[0] in {"mlx", "mlx_lm", "torch", "transformers"}
        or name == "whetstone.bakeoff.run"
    }
    assert not forbidden, f"the offline classifier imports inference or the driver: {forbidden}"
    assert "whetstone.bakeoff.whole_function" in imported, (
        "the walk does not see the module's real imports — the guard would pass vacuously"
    )


def test_the_module_imports_nothing_under_verify_or_tasks() -> None:
    """The instrument is stdlib-only by its own import list: nothing under `verify/` or
    `tasks/` is imported anywhere in the module — not even under `TYPE_CHECKING` — so
    importing it never executes a reward-path import (the whole_function.py hygiene shape)."""
    source = Path(__file__).parents[2] / "src" / "whetstone" / "bakeoff" / "resolvability.py"
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    reward_path = {
        name
        for name in imported
        if name.startswith("whetstone.verify.") or name.startswith("whetstone.tasks.")
    }
    assert not reward_path, (
        "the offline classifier imports the reward path: " + ", ".join(sorted(reward_path))
    )


def test_nothing_on_the_reward_path_imports_the_classifier() -> None:
    src = Path(__file__).parents[2] / "src" / "whetstone"
    offenders = [
        str(path.relative_to(src))
        for root in ("verify", "tasks")
        for path in sorted((src / root).rglob("*.py"))
        if "resolvability" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, f"the reward path reaches the classifier: {offenders}"