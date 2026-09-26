"""The operator end of the locatability finding: a finished arm's evidence in, a decision out.

The command's exit *is* the pre-committed go/no-go — 0 GO, 1 NO-GO, 2 a refusal — the shape
`check-probe` gave the night door, so the decision to build a representation is a process exit
rather than an operator reading a breakdown by eye.

**No model is loaded and no network is touched.** Tasks are real two-commit donors on disk,
so the checkout reader is exercised against real git, but nothing is generated.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fixtures.repos.mined import build_mined_task

from whetstone.bakeoff.control import Control, Origin, Probe
from whetstone.bakeoff.journal import Journal, Step
from whetstone.bakeoff.locatability import main
from whetstone.bakeoff.scoring import Outcome, Rollout
from whetstone.bakeoff.transcript import Transcribed, Transcript
from whetstone.verify.verdict import Status

CANDIDATE = "big"

#: Quotes the mined fixture's buggy `calc.py` exactly: locatable.
QUOTES_THE_FILE = """```diff
--- a/calc.py
+++ b/calc.py
@@ -1,9 +1,9 @@
 def add(a, b):
-    return a - b
+    return a + b
```
"""

#: Quotes a function the fixture never had: invented.
QUOTES_NOTHING_REAL = """```diff
--- a/calc.py
+++ b/calc.py
@@ -1,2 +1,2 @@
-def multiply(a, b):
-    return a * b
+def add(a, b):
+    return a + b
```
"""


def _rollout(task_id: str, outcome: Outcome, *, candidate: str = CANDIDATE) -> Rollout:
    return Rollout(
        candidate=candidate,
        task_id=task_id,
        outcome=outcome,
        strict=Status.FAIL,
        weak=Status.FAIL,
        verdict_kinds=("patch-apply",) if outcome is Outcome.NOT_APPLIED else ("tests",),
        executed=None,
        prompt_sha256="0" * 64,
        detail="",
        generation_seconds=0.0,
        strict_seconds=0.0,
        weak_seconds=0.0,
    )


def _evidence(tmp_path: Path, rows: list[tuple[str, Outcome, str | None]]) -> list[str]:
    """Build one real task per row, a journal and a transcript; return the command's arguments.

    A row's completion of `None` writes no transcript record for it — the missing-evidence case.
    """
    journal = Journal(tmp_path / "journal.jsonl")
    transcript = Transcript(tmp_path / "transcript.jsonl")
    arguments = []
    for index, (task_id, outcome, completion) in enumerate(rows):
        root = tmp_path / "corpus" / task_id
        build_mined_task(root, task_id=task_id, subject=f"Fix addition {index}")
        # The manifest file, not its directory: the fixture keeps its donor beside the manifest,
        # and a corpus directory holding anything but manifests is refused whole.
        arguments += ["--tasks", str(root / f"{task_id}.json")]
        rollout = _rollout(task_id, outcome)
        probe = Probe(
            candidate=CANDIDATE,
            task_id=task_id,
            control=Control.INTACT,
            without_patch=Status.FAIL,
            with_reference=Status.PASS,
            origin=Origin.DONOR,
            detail="",
            seconds=0.0,
        )
        journal.append(Step(probe=probe, rollout=rollout))
        if completion is not None:
            transcript.append(
                Transcribed(
                    candidate=CANDIDATE,
                    task_id=task_id,
                    prompt_sha256="0" * 64,
                    prompt="irrelevant to locatability",
                    completion=completion,
                    attempt=1,
                    decision="graded",
                )
            )
    return [
        "--transcript",
        str(transcript.path),
        "--journal",
        str(journal.path),
        "--candidate",
        CANDIDATE,
        *arguments,
        "--out",
        str(tmp_path / "out" / "locatability.json"),
    ]


def test_a_majority_locatable_population_exits_go(tmp_path: Path) -> None:
    arguments = _evidence(
        tmp_path,
        [
            ("t-one", Outcome.NOT_APPLIED, QUOTES_THE_FILE),
            ("t-two", Outcome.NOT_APPLIED, QUOTES_THE_FILE),
            ("t-three", Outcome.NOT_APPLIED, QUOTES_NOTHING_REAL),
        ],
    )
    assert main(arguments) == 0
    written = json.loads((tmp_path / "out" / "locatability.json").read_text())
    assert written["schema"] == "whetstone-locatability/1"
    assert (written["population"], written["decision"]) == (3, "GO")
    assert written["counts"] == {"INVENTED": 1, "LOCATABLE": 2}
    assert {row["task_id"]: row["class"] for row in written["rollouts"]} == {
        "t-one": "LOCATABLE",
        "t-two": "LOCATABLE",
        "t-three": "INVENTED",
    }


def test_a_rollout_that_was_not_refused_is_not_in_the_population(tmp_path: Path) -> None:
    arguments = _evidence(
        tmp_path,
        [
            ("t-one", Outcome.NOT_APPLIED, QUOTES_THE_FILE),
            ("t-two", Outcome.NOT_APPLIED, QUOTES_NOTHING_REAL),
            ("t-solved", Outcome.NOT_SOLVED, QUOTES_THE_FILE),
        ],
    )
    assert main(arguments) == 1, "one locatable of two is exactly half, which is NO-GO"
    written = json.loads((tmp_path / "out" / "locatability.json").read_text())
    assert written["population"] == 2
    assert "t-solved" not in {row["task_id"] for row in written["rollouts"]}


def test_missing_evidence_is_unclassified_and_still_counted(tmp_path: Path) -> None:
    """No graded record for a refused key: the question could not be asked, and says so."""
    arguments = _evidence(
        tmp_path,
        [
            ("t-one", Outcome.NOT_APPLIED, QUOTES_THE_FILE),
            ("t-gone", Outcome.NOT_APPLIED, None),
        ],
    )
    assert main(arguments) == 1
    written = json.loads((tmp_path / "out" / "locatability.json").read_text())
    assert written["counts"] == {"LOCATABLE": 1, "UNCLASSIFIED": 1}


def test_a_task_nobody_offered_is_unclassified(tmp_path: Path) -> None:
    arguments = _evidence(tmp_path, [("t-one", Outcome.NOT_APPLIED, QUOTES_THE_FILE)])
    without_tasks = [a for a in arguments if a != "--tasks" and "corpus" not in a]
    assert main(without_tasks) == 1
    written = json.loads((tmp_path / "out" / "locatability.json").read_text())
    assert written["counts"] == {"UNCLASSIFIED": 1}


@pytest.mark.parametrize("missing", ["--transcript", "--journal"])
def test_missing_evidence_files_are_refused_and_nothing_is_written(
    tmp_path: Path, missing: str, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = _evidence(tmp_path, [("t-one", Outcome.NOT_APPLIED, QUOTES_THE_FILE)])
    arguments[arguments.index(missing) + 1] = str(tmp_path / "absent.jsonl")
    assert main(arguments) == 2
    assert "absent.jsonl" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_a_candidate_the_journal_never_saw_is_refused(tmp_path: Path) -> None:
    arguments = _evidence(tmp_path, [("t-one", Outcome.NOT_APPLIED, QUOTES_THE_FILE)])
    arguments[arguments.index("--candidate") + 1] = "nobody"
    assert main(arguments) == 2
    assert not (tmp_path / "out").exists()


def test_a_candidate_with_no_refusals_is_refused_not_decided(tmp_path: Path) -> None:
    arguments = _evidence(tmp_path, [("t-one", Outcome.NOT_SOLVED, QUOTES_THE_FILE)])
    assert main(arguments) == 2
    assert not (tmp_path / "out").exists()


def test_the_document_is_byte_identical_across_hash_seeds(tmp_path: Path) -> None:
    arguments = _evidence(
        tmp_path,
        [
            ("t-one", Outcome.NOT_APPLIED, QUOTES_THE_FILE),
            ("t-two", Outcome.NOT_APPLIED, QUOTES_NOTHING_REAL),
        ],
    )
    out = Path(arguments[-1])
    written = []
    for seed in ("0", "12345"):
        # Removed before each run, so a second run that wrote nothing cannot pass by re-reading
        # the first run's file.
        out.unlink(missing_ok=True)
        environment = {**os.environ, "PYTHONHASHSEED": seed}
        subprocess.run(
            [sys.executable, "-m", "whetstone.bakeoff.locatability", *arguments],
            env=environment,
            check=False,
        )
        written.append(out.read_bytes())
    assert written[0] == written[1]


def test_the_module_loads_no_model_and_no_driver() -> None:
    source = Path(__file__).parents[2] / "src" / "whetstone" / "bakeoff" / "locatability.py"
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
        if "locatability" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, f"the reward path reaches the classifier: {offenders}"
