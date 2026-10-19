"""The night's failure partition is a command: one complete run in, its causes out.

A finished night's ledger records counts and no cause, and the per-rollout facts that explain a
zero live only in the per-draw journals. `bakeoff.attribution` reads one transcript and never a
journal or a ledger; `bakeoff.autopsy` needs a `whetstone-attribution/1` sidecar no night writes.
This file pins the module that closes the gap: it reads one **complete** night, reconstructs the
journal `Rollout`s, and reconciles their partition against the ledger that is the completeness
authority.

The fixture is a **real** run, written only through the shipped writers — `run_ledger.write`,
`Journal`, `Transcript`, `dataset.write_document` — so the module under test reads exactly what a
night writes. Its `DrawRecord`s are built with `run_ledger.counts_of` over the same rollouts, so
the *valid* fixture reconciles by construction; the count-disagreement fixture then mutates the
ledger's own record, so the disagreement is genuine rather than a restatement of the code.

Every class of `scoring.Outcome` appears at least once, including `NO_ORACLE` and `UNPROVISIONED`,
which are recorded before generation and have a journal row and no transcript row. A partition
that treated those as incompleteness would refuse exactly the nights that most need reading.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import pytest
from fixtures.repos.mined import build_mined_task
from loop.test_run_ledger import _ledger

from whetstone.bakeoff import night_autopsy
from whetstone.bakeoff.control import Control, Origin, Probe
from whetstone.bakeoff.journal import Journal, Step
from whetstone.bakeoff.night_autopsy import main
from whetstone.bakeoff.scoring import Outcome, Rollout
from whetstone.bakeoff.transcript import Transcribed, Transcript
from whetstone.loop import dataset as training
from whetstone.loop import draws as run_draws
from whetstone.loop import ledger as run_ledger
from whetstone.loop import night as loop_night
from whetstone.loop.sampling import Applied
from whetstone.verify.verdict import Status

#: The repository root, reached from `tests/bakeoff/`. The CLI's locality rule resolves its
#: gitignored roots against the process' working directory, which is this tree under pytest.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: The one candidate the fixture night ran. A night is single-candidate; the journal and the
#: transcript are both keyed `(candidate, task_id)`.
CANDIDATE = "base-a"

#: A complete, well-formed diff. Fenced in the transcript, it parses.
GOOD_DIFF = """diff --git a/calc.py b/calc.py
--- a/calc.py
+++ b/calc.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b
+    return a + b
"""

#: The same shape aimed at a path the checkout does not have: git parses it and refuses to apply
#: it. This is the well-formed-but-misapplied diff whose cause needs the checkout layer.
MISSING_PATH_DIFF = GOOD_DIFF.replace("calc.py", "missing.py")

#: Plain prose: no diff markers at all, so the pure layer alone can name the cause.
PROSE = "The bug is that `add` subtracts instead of adding; change the operator.\n"


@dataclass(frozen=True)
class _Task:
    """One (draw, task) the fixture night ran, and the evidence it left behind."""

    task_id: str
    outcome: Outcome
    strict: Status | None
    weak: Status | None
    kinds: tuple[str, ...]
    detail: str
    #: The stored completion, or `None` for a rollout recorded before generation (`NO_ORACLE`,
    #: `UNPROVISIONED`), which has a journal row and no transcript row.
    completion: str | None


#: The fixture night: two draws, every class of `Outcome` at least once. The `NOT_APPLIED` task
#: id matches the donor manifest the `--tasks` tests materialise, so its cause can be answered.
_DRAWS: tuple[tuple[int, tuple[_Task, ...]], ...] = (
    (
        1,
        (
            _Task(
                "synthetic-mined-adder",
                Outcome.NOT_APPLIED,
                Status.FAIL,
                Status.FAIL,
                ("patch-apply",),
                "error: missing.py: No such file or directory",
                f"```diff\n{MISSING_PATH_DIFF}```\n",
            ),
            _Task(
                "t-solved",
                Outcome.SOLVED,
                Status.PASS,
                Status.PASS,
                ("fail-to-pass",),
                "",
                f"```diff\n{GOOD_DIFF}```\n",
            ),
            _Task("t-no-diff", Outcome.NO_DIFF, None, None, (), "", PROSE),
            _Task(
                "t-no-oracle",
                Outcome.NO_ORACLE,
                Status.UNVERIFIED,
                Status.UNVERIFIED,
                (),
                "no source could be shown for this task",
                None,
            ),
        ),
    ),
    (
        2,
        (
            _Task(
                "t-not-solved",
                Outcome.NOT_SOLVED,
                Status.FAIL,
                Status.FAIL,
                ("fail-to-pass",),
                "",
                f"```diff\n{GOOD_DIFF}```\n",
            ),
            _Task(
                "t-unverified",
                Outcome.UNVERIFIED,
                Status.UNVERIFIED,
                Status.UNVERIFIED,
                (),
                "the reward could not be computed",
                "",
            ),
            _Task(
                "t-unprovisioned",
                Outcome.UNPROVISIONED,
                Status.UNVERIFIED,
                Status.UNVERIFIED,
                (),
                "the environment could not be built",
                None,
            ),
        ),
    ),
)


def _probe(task_id: str) -> Probe:
    """An intact control arm on `task_id`. The partition never reads it; the journal carries it."""
    return Probe(
        candidate=CANDIDATE,
        task_id=task_id,
        control=Control.INTACT,
        without_patch=Status.FAIL,
        with_reference=Status.PASS,
        origin=Origin.DONOR,
        detail="",
        seconds=0.0,
    )


def _rollout(spec: _Task) -> Rollout:
    """The record the run wrote for one fixture task."""
    return Rollout(
        candidate=CANDIDATE,
        task_id=spec.task_id,
        outcome=spec.outcome,
        strict=spec.strict,
        weak=spec.weak,
        verdict_kinds=spec.kinds,
        executed=None,
        prompt_sha256="" if spec.completion is None else "a" * 64,
        detail=spec.detail,
        generation_seconds=0.0,
        strict_seconds=0.0,
        weak_seconds=0.0,
    )


def _transcribed(spec: _Task) -> Transcribed:
    """The transcript row for one generated fixture task."""
    assert spec.completion is not None
    return Transcribed(
        candidate=CANDIDATE,
        task_id=spec.task_id,
        prompt_sha256="a" * 64,
        prompt=f"fix {spec.task_id}\n",
        completion=spec.completion,
        attempt=1,
        decision="graded",
    )


def night(
    tmp_path: Path,
    *,
    recorded_counts: dict[int, dict[str, tuple[int, int, int]]] | None = None,
    journals: bool = True,
    transcripts: bool = True,
    ledger: bool = True,
) -> Path:
    """Build a complete fixture night through the shipped writers and return its directory.

    `recorded_counts`, when given, overrides the ledger's own per-draw counts for the named
    attempts. It is how the count-disagreement fixture makes the ledger say something the
    journals do not: the writer re-seals the (now wrong) document, so the refusal under test is
    the reconciliation's, not the seal's.
    """
    run = tmp_path / "runs" / "night-fixture"
    run.mkdir(parents=True)
    evidence = run / loop_night.EVIDENCE_DIR

    rollouts: dict[int, tuple[Rollout, ...]] = {}
    for attempt, specs in _DRAWS:
        journal_path, transcript_path = run_draws.evidence_paths(evidence, attempt)
        if journals:
            journal = Journal(journal_path)
            for spec in specs:
                journal.append(Step(probe=_probe(spec.task_id), rollout=_rollout(spec)))
        if transcripts:
            transcript = Transcript(transcript_path)
            for spec in specs:
                if spec.completion is not None:
                    transcript.append(_transcribed(spec))
        rollouts[attempt] = tuple(_rollout(spec) for spec in specs)

    every = tuple(one for attempt, _ in _DRAWS for one in rollouts[attempt])
    denominator, unverified, _ = run_ledger.counts_of(every)
    solved = [one for one in every if one.outcome is Outcome.SOLVED]
    selected = training.build(
        [
            training.TrainingText(
                example=training.example_of(
                    one,
                    source="private",
                    attempt=1,
                    seed=1234,
                    completion=f"```diff\n{GOOD_DIFF}```\n",
                    control=Status.PASS,
                ),
                prompt=f"fix {one.task_id}\n",
                completion=f"```diff\n{GOOD_DIFF}```\n",
            )
            for one in solved
        ],
        denominator=denominator,
        unverified=unverified,
    )

    counts_by_attempt = {
        attempt: {"private": run_ledger.counts_of(rollouts[attempt])}
        for attempt, _ in _DRAWS
    }
    if recorded_counts is not None:
        counts_by_attempt.update(recorded_counts)
    draws_recorded = tuple(
        run_ledger.DrawRecord(
            attempt=attempt,
            harness={"private": Status.PASS},
            counts=counts_by_attempt[attempt],
        )
        for attempt, _ in _DRAWS
    )

    if ledger:
        base = _ledger()
        run_ledger.write(
            run / run_ledger.LEDGER_FILE,
            replace(
                base,
                run_id="night-fixture",
                draws=len(_DRAWS),
                draws_recorded=draws_recorded,
                dataset=selected,
                task_set=replace(base.task_set, probe=None),
                seeds=(Applied(task_id="synthetic-mined-adder", attempt=1, seed=1234),),
            ),
        )
    training.write_document(run / loop_night.DATASET_FILE, selected)
    return run


def out_path(tmp_path: Path) -> Path:
    """A document path under the worktree's gitignored `runs/`, unique per test."""
    return REPO_ROOT / "runs" / "night-autopsy-tests" / tmp_path.name / "night-autopsy.json"


def _corpus(tmp_path: Path) -> Path:
    """A corpus root holding the `synthetic-mined-adder` manifest, whose donor can materialise."""
    scratch = tmp_path / "donor-src"
    built = build_mined_task(
        scratch, task_id="synthetic-mined-adder", subject="Fix addition"
    )
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / f"{built.task.task_id}.json").write_bytes(
        (scratch / f"{built.task.task_id}.json").read_bytes()
    )
    return corpus


# --------------------------------------------------------------------------------------------
# The partition and the reconciliation.
# --------------------------------------------------------------------------------------------


def test_the_partition_counts_every_class(tmp_path: Path) -> None:
    """Every `Outcome` member appears, each with its hand-written count, and it reconciles.

    The partition is the whole product: a class missing from it is a failure mode the operator
    cannot see, and a count that does not match the fixture's own construction is the instrument
    inventing a night.
    """
    run = night(tmp_path)
    out = out_path(tmp_path)
    try:
        assert main(["--run", str(run), "--out", str(out)]) == 0
        document = json.loads(out.read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(out.parent, ignore_errors=True)

    assert document["schema"] == "whetstone-night-autopsy/1", document
    assert document["run_id"] == "night-fixture"
    assert document["draws"] == 2, document
    assert document["rollouts"] == 7, document
    assert document["outcomes"] == {
        "NOT_APPLIED": 1,
        "NO_DIFF": 1,
        "NO_ORACLE": 1,
        "NOT_SOLVED": 1,
        "SOLVED": 1,
        "UNPROVISIONED": 1,
        "UNVERIFIED": 1,
    }, document

    # With no `--tasks`, the well-formed diff is UNATTRIBUTED and the prose has a pure cause.
    assert document["causes"] == {"NO_DIFF_HEADER": 1, "UNATTRIBUTED": 1}, document
    assert document["unattributed"] == 1, document

    global_check = document["reconciliation"]["global"]
    assert global_check["recomputed"] == {"denominator": 7, "unverified": 3, "solved": 1}, document
    assert global_check["recorded"] == {"denominator": 7, "unverified": 3, "solved": 1}, document
    assert document["reconciliation"]["dataset"] == {
        "denominator": 7,
        "unverified": 3,
        "examples": 1,
    }, document

    rows = [task for draw in document["per_draw"] for task in draw["tasks"]]
    assert {row["task_id"] for row in rows} == {
        "synthetic-mined-adder",
        "t-solved",
        "t-no-diff",
        "t-no-oracle",
        "t-not-solved",
        "t-unverified",
        "t-unprovisioned",
    }, rows
    assert {row["task_id"]: row["trainable"] for row in rows}["t-solved"] is True
    assert not any(row["trainable"] for row in rows if row["outcome"] != "SOLVED"), rows


def test_a_count_disagreement_is_refused_naming_the_draw_and_both_triples(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The ledger is the completeness authority; a partition that does not reproduce it is refused.

    The disagreement is genuine, not circular: the journals are the valid fixture's, and only the
    ledger's own `DrawRecord` is mutated and re-sealed. The refusal must name the draw and both
    triples, because "they disagree" without the numbers is not something an operator can act on.
    """
    run = night(tmp_path, recorded_counts={1: {"private": (4, 1, 2)}})
    out = out_path(tmp_path)

    code = main(["--run", str(run), "--out", str(out)])

    assert code == 2, code
    message = capsys.readouterr().err
    assert "draw 1" in message, message
    assert "(denominator=4, unverified=1, solved=1)" in message, message
    assert "(denominator=4, unverified=1, solved=2)" in message, message
    assert not out.exists(), "a refused run must not leave a partial partition behind"


# --------------------------------------------------------------------------------------------
# Refusals, each by name, before a partial partition is rendered.
# --------------------------------------------------------------------------------------------


def test_a_run_without_a_ledger_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A ledgerless run is refused, not rendered as a partial partition."""
    run = night(tmp_path, ledger=False)
    out = out_path(tmp_path)

    code = main(["--run", str(run), "--out", str(out)])

    assert code == 2, code
    message = capsys.readouterr().err
    assert str(run) in message and run_ledger.LEDGER_FILE in message, message
    assert not out.exists()


def test_a_declared_draw_without_a_journal_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A declared draw whose journal is absent is refused, naming the draw and the file."""
    run = night(tmp_path)
    journal, _ = run_draws.evidence_paths(run / loop_night.EVIDENCE_DIR, 2)
    journal.unlink()
    out = out_path(tmp_path)

    code = main(["--run", str(run), "--out", str(out)])

    assert code == 2, code
    message = capsys.readouterr().err
    assert "draw 2" in message and journal.name in message, message
    assert not out.exists()


def test_a_declared_draw_without_a_transcript_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A declared draw whose transcript is absent is refused, naming the draw and the file."""
    run = night(tmp_path)
    _, transcript = run_draws.evidence_paths(run / loop_night.EVIDENCE_DIR, 1)
    transcript.unlink()
    out = out_path(tmp_path)

    code = main(["--run", str(run), "--out", str(out)])

    assert code == 2, code
    message = capsys.readouterr().err
    assert "draw 1" in message and transcript.name in message, message
    assert not out.exists()


def test_an_unparsable_journal_line_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A journal line that cannot be read is an error, never a skipped record."""
    run = night(tmp_path)
    journal, _ = run_draws.evidence_paths(run / loop_night.EVIDENCE_DIR, 1)
    with journal.open("a", encoding="utf-8") as handle:
        handle.write("{not a json line\n")
    out = out_path(tmp_path)

    code = main(["--run", str(run), "--out", str(out)])

    assert code == 2, code
    message = capsys.readouterr().err
    assert "draw 1" in message and journal.name in message, message
    assert not out.exists()


def test_no_oracle_rows_are_counted_not_treated_as_incomplete(tmp_path: Path) -> None:
    """`NO_ORACLE` is recorded before generation: a journal row and no transcript row is valid.

    Treating the missing transcript row as incompleteness would refuse exactly the nights — a
    corpus whose tasks could not be posed — whose failure partition most needs reading.
    """
    run = night(tmp_path)
    out = out_path(tmp_path)
    try:
        assert main(["--run", str(run), "--out", str(out)]) == 0
        document = json.loads(out.read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(out.parent, ignore_errors=True)

    assert document["outcomes"]["NO_ORACLE"] == 1, document
    assert document["outcomes"]["UNPROVISIONED"] == 1, document


def test_out_outside_the_gitignored_roots_is_refused_before_reading(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The locality refusal comes first: a git-committable `--out` is refused before the ledger.

    `--run` names a directory that does not exist, so if the module had read it first this
    invocation would fail with a different error and the locality promise would be unenforced.
    """
    out = tmp_path / "out.json"

    code = main(["--run", str(tmp_path / "no-such-run"), "--out", str(out)])

    assert code == 2, code
    message = capsys.readouterr().err
    assert str(out) in message and "runs/" in message, message
    assert not out.exists()


# --------------------------------------------------------------------------------------------
# The attribution join: the coarse cause, the checkout layer, and `UNATTRIBUTED` by name.
# --------------------------------------------------------------------------------------------


def test_a_not_applied_patch_gets_its_attribution_cause(tmp_path: Path) -> None:
    """A completion the pure layer can explain gets its `Cause` from that layer, offline.

    The prose `NO_DIFF` row is the cheapest question in the partition and must not depend on the
    checkout machinery: `NO_DIFF_HEADER` is one of `patch.py`'s own reasons, reused by identity.
    """
    run = night(tmp_path)
    out = out_path(tmp_path)
    try:
        assert main(["--run", str(run), "--out", str(out)]) == 0
        document = json.loads(out.read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(out.parent, ignore_errors=True)

    rows = {row["task_id"]: row for draw in document["per_draw"] for row in draw["tasks"]}
    assert rows["t-no-diff"]["cause"] == "NO_DIFF_HEADER", rows["t-no-diff"]
    assert rows["t-no-diff"]["cause_detail"], "a cause must carry the extractor's own sentence"


def test_without_tasks_a_checkout_layer_cause_is_unattributed(tmp_path: Path) -> None:
    """A located diff with no checkout to test it against is `UNATTRIBUTED`, never guessed.

    "We could not measure this" and "we measured this and it failed" are different claims; the
    well-formed-but-misapplied patch cannot be told from a would-not-parse one by text alone.
    """
    run = night(tmp_path)
    out = out_path(tmp_path)
    try:
        assert main(["--run", str(run), "--out", str(out)]) == 0
        document = json.loads(out.read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(out.parent, ignore_errors=True)

    rows = {row["task_id"]: row for draw in document["per_draw"] for row in draw["tasks"]}
    assert rows["synthetic-mined-adder"]["cause"] == "UNATTRIBUTED", rows["synthetic-mined-adder"]
    assert document["unattributed"] == 1, document


def test_a_named_task_root_materialises_a_checkout_for_the_cause(tmp_path: Path) -> None:
    """With `--tasks`, the located diff is put to git and the two refusals are separated.

    A throwaway checkout of the task's own tree answers what text cannot: git parsed this patch
    and refused to apply it, which is a model-was-wrong finding, not a format one.
    """
    run = night(tmp_path)
    corpus = _corpus(tmp_path)
    out = out_path(tmp_path)
    try:
        assert main(["--run", str(run), "--out", str(out), "--tasks", str(corpus)]) == 0
        document = json.loads(out.read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(out.parent, ignore_errors=True)

    rows = {row["task_id"]: row for draw in document["per_draw"] for row in draw["tasks"]}
    assert rows["synthetic-mined-adder"]["cause"] == "PARSED_BUT_DID_NOT_APPLY", rows[
        "synthetic-mined-adder"
    ]
    assert document["causes"].get("UNATTRIBUTED", 0) == 0, document["causes"]


def test_the_default_out_sits_beside_the_run(tmp_path: Path) -> None:
    """With no `--out`, the document is written to `<run>/night-autopsy.json`.

    The run has to live under a gitignored root for the default to be a legal home, which is
    exactly the operator's shape: a real night is always `runs/nights/<id>`.
    """
    root = REPO_ROOT / "runs" / "night-autopsy-tests" / tmp_path.name
    run = night(root)
    try:
        assert main(["--run", str(run)]) == 0
        written = run / "night-autopsy.json"
        assert written.is_file()
        assert json.loads(written.read_text(encoding="utf-8"))["run_id"] == "night-fixture"
    finally:
        shutil.rmtree(root, ignore_errors=True)


# --------------------------------------------------------------------------------------------
# The render: a page the operator reads at the morning, a pure function of the document.
# --------------------------------------------------------------------------------------------


def _document(run: Path) -> dict[str, object]:
    """The `whetstone-night-autopsy/1` document for a fixture night, built offline."""
    return night_autopsy.document(night_autopsy.autopsy(run))


def test_the_render_is_a_pure_function_of_the_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`render_markdown` reads no file: it is a function of the document and nothing else.

    The page is a view of one partition, not a second reading of the run. If it opened the
    journals or the ledger itself, two reads of the same run could disagree — the JSON and the
    markdown would describe two nights — and a document on its own would not be renderable.
    Pinned by forbidding every file read: the render below must complete with `open` and
    `Path.read_text`/`read_bytes` unable to be called.
    """
    document = _document(night(tmp_path))

    def _no_read(*args: object, **kwargs: object) -> object:
        raise AssertionError("render_markdown performed a file read")

    monkeypatch.setattr("builtins.open", _no_read)
    monkeypatch.setattr(Path, "read_text", _no_read)
    monkeypatch.setattr(Path, "read_bytes", _no_read)
    monkeypatch.setattr(Path, "open", _no_read)

    first = night_autopsy.render_markdown(document)
    second = night_autopsy.render_markdown(document)

    assert isinstance(first, str) and first, "the render produced no page"
    assert first == second, "the render is not a function of its argument alone"
    assert first.endswith("\n"), (
        "a page should end in a newline, like every file this module writes"
    )


def test_the_render_carries_every_class_and_the_disclosures(tmp_path: Path) -> None:
    """The page carries the header, every class per draw, the worst-first tasks and the disclosures.

    Every unflattering state renders as itself: the two freedoms the module does not have are
    dropping a class that came out zero (an invisible failure mode) and hiding the two limits the
    document discloses. The per-task table is worst-first so the operator reads the failures that
    matter first, and a tie is broken by task id so the order is the same on every machine.
    """
    document = _document(night(tmp_path))
    page = night_autopsy.render_markdown(document)

    # 1. the run id, the declared draw budget, the task count.
    assert "- Run: night-fixture" in page, page
    assert "- Draws: 2" in page, page
    assert "- Tasks: 7" in page, page

    # 2. the per-draw table carries every class, zero-filled where the draw recorded none.
    for outcome in (
        "SOLVED",
        "NOT_APPLIED",
        "NOT_SOLVED",
        "NO_DIFF",
        "NO_ORACLE",
        "UNVERIFIED",
        "UNPROVISIONED",
        "OUT_OF_SCOPE",
    ):
        assert outcome in page, f"the per-draw table dropped the class {outcome}"
    assert "| draw | control | SOLVED | NOT_APPLIED | NOT_SOLVED | NO_DIFF | NO_ORACLE | " \
        "UNVERIFIED | UNPROVISIONED | OUT_OF_SCOPE |" in page, page
    assert "| 1 | private=PASS | 1 | 1 | 0 | 1 | 1 | 0 | 0 | 0 |" in page, page
    assert "| 2 | private=PASS | 0 | 0 | 1 | 0 | 0 | 1 | 1 | 0 |" in page, page

    # 3. the per-task table, worst-first by non-solved count, with the dominant cause.
    assert "| task | draws | solved | dominant cause |" in page, page
    for row in (
        "| synthetic-mined-adder | 1 | 0 | UNATTRIBUTED |",
        "| t-no-diff | 1 | 0 | NO_DIFF_HEADER |",
        "| t-solved | 1 | 1 | - |",
    ):
        assert row in page, f"the per-task table dropped the row {row!r}\n\n{page}"
    assert page.index("| synthetic-mined-adder |") < page.index("| t-solved |"), (
        "a non-solved task must sort before the solved one (worst-first)"
    )

    # 4. the disclosures, verbatim from the document, and the UNATTRIBUTED count.
    for disclosure in document["disclosures"]:
        assert disclosure in page, f"the render dropped the disclosure {disclosure!r}"
    assert "UNATTRIBUTED: 1 rollout(s) the taxonomy could not name." in page, page


def test_the_render_is_byte_identical_across_processes(tmp_path: Path) -> None:
    """Two door invocations at `PYTHONHASHSEED` 0 and 1 write the same `.json` and `.md` bytes.

    The partition and its page are evidence: someone re-running the door on the same night must
    get the same bytes, or the finding is not re-derivable. Asserted across processes because an
    in-process repeat shares one hash seed and would miss exactly the set-iteration dependence
    this guards; both artefacts are compared because the markdown is a view of the same document
    and a seed-dependent render would diverge from it.
    """
    run = night(tmp_path)
    root = REPO_ROOT / "runs" / "night-autopsy-render" / tmp_path.name
    first = root / "seed0.json"
    second = root / "seed1.json"
    try:
        for seed, out in (("0", first), ("1", second)):
            environment = dict(os.environ)
            environment["PYTHONHASHSEED"] = seed
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "whetstone.bakeoff.night_autopsy",
                    "--run",
                    str(run),
                    "--out",
                    str(out),
                ],
                cwd=str(REPO_ROOT),
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            assert completed.returncode == 0, completed.stderr

        assert first.read_bytes() == second.read_bytes(), (
            "two invocations at PYTHONHASHSEED 0 and 1 wrote different .json bytes"
        )
        first_md = first.with_suffix(".md")
        second_md = second.with_suffix(".md")
        assert first_md.is_file() and second_md.is_file(), (
            f"the door wrote no markdown beside the document: {first_md.parent}"
        )
        assert first_md.read_bytes() == second_md.read_bytes(), (
            "two invocations at PYTHONHASHSEED 0 and 1 wrote different .md bytes"
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)
