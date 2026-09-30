"""The operator end of the measurement's decision: a finished run's evidence in, a decision out.

The command's exit *is* the pre-committed go/no-go — 0 GO, 1 NO-GO, 2 a refusal — the shape
`check-probe` and `locatability` gave the night door, so the decision to build the
numbered-listing contract is a process exit rather than an operator reading a partition by
eye. The rule and the population are fixed in `docs/planning/edit-contract-finding/
measurement-run/spec.md` before the run; the exit tests here run the boundary of the
strict-majority inequality at the pinned 16-task population (8 of 16 is exactly half and is
NO-GO; 9 is GO).

**No model is loaded and no network is touched.** Tasks are real two-commit donors on disk,
so checkouts are materialised against real git and the oracle listing is re-derived the way
the run derived it, but nothing is generated.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from fixtures.repos.mined import build_mined_task

from whetstone.bakeoff import measure
from whetstone.bakeoff import stratum as stratum_module
from whetstone.bakeoff.addressability import RULE, main
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

#: The stratum document's membership: the pinned 16 plus the overlap (19 in all).
STRATUM_MEMBERS = tuple(sorted(set(SPEC_PINNED) | set(OVERLAP)))

#: The held-out document's membership: the overlap plus nine outside the stratum (12 in all).
HELDOUT_MEMBERS = tuple(sorted(set(OVERLAP) | set(HELDOUT_ONLY)))

#: An addressable completion: one in-range EDIT block whose replacement parses, against the
#: mined fixture's two-line `calc.py` at `base_commit`.
ADDRESSABLE = (
    "EDIT calc.py:1-2\n"
    "<<<<<<< REPLACE\n"
    "def add(a, b):\n"
    "    return a + b\n"
    ">>>>>>> END\n"
)

#: A completion no EDIT block can be parsed out of.
GARBAGE = "hello there\n"

#: The manifest's recorded prompt digest for every task, and the transcript's by default.
DIGEST = "0" * 64


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
        "recorded_on": "2026-09-30",
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
                    prompt="irrelevant to addressability",
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
        str(tmp_path / "out" / "addressability.json"),
    ]


def _all_sixteen(completion: str) -> list[tuple[str, str | None, str | None]]:
    """One row per pinned task, every completion the same."""
    return [(task_id, completion, None) for task_id in SPEC_PINNED]


@pytest.fixture(scope="module")
def inputs(tmp_path_factory: pytest.TempPathFactory):
    """The pinned 16 tasks as real two-commit donors, plus valid stratum/held-out documents."""
    root = tmp_path_factory.mktemp("addressability-inputs")
    corpus = root / "private"
    corpus.mkdir()
    for task_id in SPEC_PINNED:
        build_mined_task(
            root / f"donor-{task_id}",
            task_id=task_id,
            subject=f"Fix addition ({task_id})",
        )
        shutil.copy(root / f"donor-{task_id}" / f"{task_id}.json", corpus / f"{task_id}.json")
    stratum = _stratum_document(root / "docs", STRATUM_MEMBERS)
    heldout = _heldout_document(root / "docs", HELDOUT_MEMBERS)
    return corpus, stratum, heldout


# --- The pre-committed rule and the exit -----------------------------------------------------


def test_the_pinned_population_constant_is_the_specs_list() -> None:
    """The module's constant is the spec's 16 ids, spelled here — a drift in either is red."""
    assert measure._PINNED_POPULATION == SPEC_PINNED


def test_the_rule_constant_is_the_specs_sentence() -> None:
    """The inequality is a constant in code, cross-pinned to the committed spec's sentence."""
    assert RULE == "GO iff count(ADDRESSABLE) * 2 > population"


def test_a_majority_addressable_population_exits_go(tmp_path: Path, inputs: Any) -> None:
    arguments = _evidence(tmp_path, inputs, _all_sixteen(ADDRESSABLE))
    assert main(arguments) == 0
    written = json.loads((tmp_path / "out" / "addressability.json").read_text())
    assert written["schema"] == "whetstone-addressability/1"
    assert written["run_id"] == "measure-0123456789ab"
    assert written["candidate"] == {"repo_id": CANDIDATE, "revision": "a" * 64}
    assert written["rule"] == RULE
    assert (written["population"], written["decision"]) == (16, "GO")
    assert written["counts"] == {"ADDRESSABLE": 16}
    assert written["sub_counts"] == {"outside_listing": 0, "syntax_fragile_in_context": 0}
    assert {row["task_id"]: row["class"] for row in written["rollouts"]} == {
        task_id: "ADDRESSABLE" for task_id in SPEC_PINNED
    }


def test_exactly_half_addressable_is_no_go(tmp_path: Path, inputs: Any) -> None:
    """8 of 16 is exactly half, and the rule is strict-majority: NO-GO, exit 1."""
    rows = [(task_id, ADDRESSABLE, None) for task_id in SPEC_PINNED[:8]]
    rows += [(task_id, GARBAGE, None) for task_id in SPEC_PINNED[8:]]
    assert main(_evidence(tmp_path, inputs, rows)) == 1
    written = json.loads((tmp_path / "out" / "addressability.json").read_text())
    assert written["counts"] == {"ADDRESSABLE": 8, "MALFORMED": 8}


def test_a_minority_addressable_population_is_no_go(tmp_path: Path, inputs: Any) -> None:
    rows = [(SPEC_PINNED[0], ADDRESSABLE, None), *(
        (task_id, GARBAGE, None) for task_id in SPEC_PINNED[1:]
    )]
    assert main(_evidence(tmp_path, inputs, rows)) == 1


def test_missing_evidence_is_unclassified_and_still_counted(tmp_path: Path, inputs: Any) -> None:
    """No graded record for a task: the question could not be asked, and stays in the total."""
    rows = [(task_id, ADDRESSABLE, None) for task_id in SPEC_PINNED[:8]]
    rows += [(SPEC_PINNED[8], None, None)]
    rows += [(task_id, GARBAGE, None) for task_id in SPEC_PINNED[9:]]
    assert main(_evidence(tmp_path, inputs, rows)) == 1
    written = json.loads((tmp_path / "out" / "addressability.json").read_text())
    assert written["counts"] == {"ADDRESSABLE": 8, "MALFORMED": 7, "UNCLASSIFIED": 1}
    unclassified = next(
        row for row in written["rollouts"] if row["class"] == "UNCLASSIFIED"
    )
    assert unclassified["task_id"] == SPEC_PINNED[8]
    assert "graded record" in unclassified["detail"]


def test_a_transcript_record_whose_prompt_digest_disagrees_is_unclassified(
    tmp_path: Path, inputs: Any
) -> None:
    """A record that does not match the manifest's recorded digest is not this run's evidence."""
    rows = [(task_id, ADDRESSABLE, None) for task_id in SPEC_PINNED[:8]]
    rows += [(SPEC_PINNED[8], ADDRESSABLE, "1" * 64)]
    rows += [(task_id, GARBAGE, None) for task_id in SPEC_PINNED[9:]]
    assert main(_evidence(tmp_path, inputs, rows)) == 1
    written = json.loads((tmp_path / "out" / "addressability.json").read_text())
    assert written["counts"] == {"ADDRESSABLE": 8, "MALFORMED": 7, "UNCLASSIFIED": 1}
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
    assert main(_evidence(tmp_path, inputs, _all_sixteen(ADDRESSABLE), corpus=reduced)) == 0
    written = json.loads((tmp_path / "out" / "addressability.json").read_text())
    assert written["counts"] == {"ADDRESSABLE": 15, "UNCLASSIFIED": 1}
    unclassified = next(
        row for row in written["rollouts"] if row["class"] == "UNCLASSIFIED"
    )
    assert unclassified["task_id"] == SPEC_PINNED[0]
    assert "not offered" in unclassified["detail"]


# --- The refusals: exit 2, a named reason, nothing written ------------------------------------


def test_missing_manifest_is_refused_and_nothing_is_written(
    tmp_path: Path, inputs: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = _evidence(tmp_path, inputs, _all_sixteen(ADDRESSABLE))
    arguments[arguments.index("--manifest") + 1] = str(tmp_path / "absent.json")
    assert main(arguments) == 2
    assert "absent.json" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_missing_transcript_is_refused_and_nothing_is_written(
    tmp_path: Path, inputs: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = _evidence(tmp_path, inputs, _all_sixteen(ADDRESSABLE))
    arguments[arguments.index("--transcript") + 1] = str(tmp_path / "absent.jsonl")
    assert main(arguments) == 2
    assert "absent.jsonl" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_a_manifest_with_an_unknown_schema_is_refused(
    tmp_path: Path, inputs: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = _evidence(
        tmp_path, inputs, _all_sixteen(ADDRESSABLE), schema="whetstone-measure/2"
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
        _all_sixteen(ADDRESSABLE),
        manifest_tasks=intruder,
        prompt_sha256={task_id: DIGEST for task_id in intruder},
    )
    assert main(arguments) == 2
    assert "pinned" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_documents_that_subtract_to_a_different_set_are_refused(
    tmp_path: Path, inputs: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    _, _, heldout = inputs
    smaller = tuple(sorted(set(STRATUM_MEMBERS) - {SPEC_PINNED[0]}))
    drifted = _stratum_document(tmp_path / "drifted-docs", smaller)
    arguments = _evidence(
        tmp_path,
        inputs,
        _all_sixteen(ADDRESSABLE),
        stratum=drifted,
        heldout=heldout,
    )
    assert main(arguments) == 2
    assert "subtract" in capsys.readouterr().err
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
        _all_sixteen(ADDRESSABLE),
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
        tmp_path, inputs, _all_sixteen(ADDRESSABLE), corpus=tmp_path / "no-such-corpus"
    )
    assert main(arguments) == 2
    assert "corpus" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


# --- Determinism -----------------------------------------------------------------------------


def test_the_document_is_byte_identical_across_hash_seeds(tmp_path: Path, inputs: Any) -> None:
    arguments = _evidence(tmp_path, inputs, _all_sixteen(ADDRESSABLE))
    out = Path(arguments[-1])
    written = []
    for seed in ("0", "12345"):
        # Removed before each run, so a second run that wrote nothing cannot pass by re-reading
        # the first run's file.
        out.unlink(missing_ok=True)
        environment = {**os.environ, "PYTHONHASHSEED": seed}
        subprocess.run(
            [sys.executable, "-m", "whetstone.bakeoff.addressability", *arguments],
            env=environment,
            check=False,
        )
        written.append(out.read_bytes())
    assert written[0] == written[1]


# --- The guards ------------------------------------------------------------------------------


def test_the_module_loads_no_model_and_no_driver() -> None:
    source = Path(__file__).parents[2] / "src" / "whetstone" / "bakeoff" / "addressability.py"
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


def test_nothing_on_the_reward_path_imports_the_classifier() -> None:
    src = Path(__file__).parents[2] / "src" / "whetstone"
    offenders = [
        str(path.relative_to(src))
        for root in ("verify", "tasks")
        for path in sorted((src / root).rglob("*.py"))
        if "addressability" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, f"the reward path reaches the classifier: {offenders}"