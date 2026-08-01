"""The operator entry point, and the four ways a bake-off can publish something it did not measure.

Everything under `src/whetstone/bakeoff/` before this file is a component with a narrow claim.
This is the file that composes them into a night, and composition is where the honesty controls
either hold or quietly do not — each one of them lives in the seam between two modules that are
individually correct.

**The frozen generation contract is the assertion this file exists for.** PRD M7b: the prompt and
the extractor are fixed and hashed *before* the first scored result, and any change to either
afterwards invalidates the run. The temptation it guards against is the strongest one in P1 —
`docs/planning/p1-baseline-bakeoff/the-run/spec.md:92-94` names it: a disappointing number reads
exactly like evidence that the prompt was wrong, and the two cases are indistinguishable after the
fact unless something refused to let them mix. So the test below **moves the template while the run
is in flight** and requires the run to die rather than finish. A run that survived that would
publish a comparison between bases that were shown different questions.

The other three are the same shape:

- **the dev subset** must never reach a published count, because a contract iterated against a task
  and then scored on that task is optimising on the outcome;
- **a broken control arm** must produce no report at all, not a report with a caveat — a run whose
  harness was never shown to grade anything measures nothing about any base;
- **the MLX adapter must be handed a filesystem path**, never a repo id, because `mlx_lm.utils.load`
  treats a repo id as an instruction to download and the two are one paste apart.

**No model, no `mlx`, no network, no weights.** Every base is a stub behind an injected engine
factory; the weights are a few bytes of `tmp_path` with a real provenance over them; the tasks are
two-commit synthetic donors built with real git. Nothing here writes outside `tmp_path`, and in
particular nothing writes into `reports/`.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from fixtures.repos.mined import build_mined_task

from whetstone.bakeoff import rendering, scoring
from whetstone.bakeoff.generator import Generator
from whetstone.bakeoff.run import (
    COST_FILE,
    PROBE_FILE,
    REPORT_FILE,
    Conducted,
    ContractChanged,
    UnknownDevSubset,
    conduct,
    main,
    mlx_engine,
)
from whetstone.bakeoff.sweep import HarnessNotProven
from whetstone.bakeoff.weights import PROVENANCE_FILE, PROVENANCE_SCHEMA, Weights, load_weights
from whetstone.tasks.fetch import POOL_SCHEMA
from whetstone.verify.task import Task
from whetstone.verify.verdict import Status

#: Generous enough that a two-commit donor with one module and one pytest file can never reach it.
TIMEOUT = 120.0

#: The date the operator declares for a run. An input everywhere, never read from a clock — a
#: report that dated itself would differ from itself between two renders of the same records.
RECORDED_ON = "2026-08-01"

#: What a base says when it has nothing to offer. Prose, no fence, no diff header: the shape
#: `extract_patch` reports as no-diff, so every rollout here is a guaranteed, verifier-free zero.
#: These tests are about the harness's refusals and never about whether a base can solve anything.
REFUSAL = "I could not work out what is wrong with this repository, so I have made no change."

#: One stand-in weights file per fake candidate. Tiny: `load_weights` is under test in its own
#: file, and what is needed here is only that the driver's provenance check has something to pass.
WEIGHT_FILES = {"config.json": '{"model_type": "qwen2"}', "model.safetensors": "not a tensor"}


class _Refuses:
    """A base that answers every prompt with the same refusal, and holds no table of them.

    Deliberately not `StubGenerator`: that class refuses an unstubbed prompt, and the
    frozen-contract test below moves the template mid-run precisely so that a prompt the test
    never rendered is attempted. A table would refuse it first, and the test would pass while
    proving something about the fixture instead of about the seal.
    """

    def generate(self, prompt: str) -> str:
        return REFUSAL


def _engine(_: Weights) -> Generator:
    """An engine factory that loads nothing and never touches `mlx`."""
    return _Refuses()


def _weights(root: Path, *names: str) -> Path:
    """Write fake weight directories under `root` plus the provenance that names them."""
    root.mkdir(parents=True, exist_ok=True)
    recorded = []
    for name in names:
        local_dir = root / name.split("/")[-1]
        local_dir.mkdir()
        for filename, text in WEIGHT_FILES.items():
            (local_dir / filename).write_text(text, encoding="utf-8")
        recorded.append(
            {
                "repo_id": name,
                "revision": hashlib.sha256(name.encode()).hexdigest(),
                "local_dir": local_dir.name,
                "bytes": sum(len(text.encode()) for text in WEIGHT_FILES.values()),
                "seconds": 1.0,
                "files": [
                    {
                        "name": filename,
                        "bytes": len(text.encode()),
                        "sha256": hashlib.sha256(text.encode()).hexdigest(),
                    }
                    for filename, text in WEIGHT_FILES.items()
                ],
            }
        )
    (root / PROVENANCE_FILE).write_text(
        json.dumps({"schema": PROVENANCE_SCHEMA, "candidates": recorded}), encoding="utf-8"
    )
    return root


def _funnel(path: Path) -> Path:
    """A minimal source-A rejection ledger, in the shape `funnel_from_ledger` reads."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "counts": {
                    "input": 300,
                    "ineligible": 299,
                    "format": 192,
                    "environment": 106,
                    "collectability": 1,
                    "liveness": 0,
                    "eligible": 1,
                },
                "eligible": ["pallets__flask-4045"],
                "execution_order": ["format", "environment", "collectability", "liveness"],
            }
        ),
        encoding="utf-8",
    )
    return path


def _corpus(root: Path, name: str, ids: tuple[str, ...], *, vacuous: str = "") -> Path:
    """Build one donor per id and collect their manifests into a directory of their own.

    `load_task_directory` refuses any entry that is not a manifest, so the donors are built
    elsewhere and only the JSON is copied in — which is also the shape of the real corpus, where
    `tasks/local/` holds manifests and the donors are the user's own checkouts.
    """
    corpus = root / name
    corpus.mkdir(parents=True)
    for task_id in ids:
        build_mined_task(
            root / f"donor-{task_id}",
            task_id=task_id,
            subject=f"Fix addition ({task_id})",
            vacuous=task_id == vacuous,
        )
        shutil.copy(root / f"donor-{task_id}" / f"{task_id}.json", corpus / f"{task_id}.json")
    return corpus


def _pool(path: Path) -> Path:
    """A valid but empty source-A pool.

    Empty because the "public" corpus below is a *mined* fixture — it carries a donor commit, so
    its control arm re-derives its reference and never opens this file. The path is still passed,
    and passed as a real pool rather than a name, because `conduct` requires it: a run that reached
    a genuine SWE-bench instance without one would skip every public probe and be refused a ranking
    after paying for the generation, which is how the first scored run ended.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema": POOL_SCHEMA, "instances": []}), encoding="utf-8")
    return path


def _run(tmp_path: Path, **overrides: Any) -> Conducted:
    """A whole bake-off over three private tasks and one public one, with a stubbed engine."""
    private = overrides.pop("private", ("alpha", "beta", "gamma"))
    vacuous = overrides.pop("vacuous", "")
    arguments: dict[str, Any] = {
        # `--tasks` is repeatable, because the real corpus is one directory per donor; a single
        # root is still the common case and is passed as a one-element sequence.
        "tasks": (_corpus(tmp_path, "private", private, vacuous=vacuous),),
        "public": _corpus(tmp_path, "public", ("pallets__flask-4045",)),
        "pool": _pool(tmp_path / "pool" / "pool.json"),
        "funnel": _funnel(tmp_path / "ledger" / "ineligible.json"),
        "weights": _weights(tmp_path / "weights", "mlx-community/Qwen2.5-Coder-3B-Instruct-4bit"),
        "out": tmp_path / "out",
        "workspace": tmp_path / "work",
        "timeout": TIMEOUT,
        "recorded_on": RECORDED_ON,
        "engine": _engine,
    }
    arguments.update(overrides)
    return conduct(**arguments)


def test_the_probe_runs_exactly_the_declared_sample_and_publishes_what_it_cost(
    tmp_path: Path,
) -> None:
    """D7: time a declared sample, publish the measured cost, and score nothing.

    Two properties, and the second is the one that is easy to leave out. The sample must be
    **exactly** N — a probe that ran the whole set would answer the scope question by doing the
    thing the question was whether to do. And the probe must publish **cost and nothing else**: if
    it emitted counts, the operator would be choosing the scored set's size while looking at
    partial results from it, which is the same act M7b forbids one layer up.
    """
    conducted = _run(tmp_path, probe=2)

    assert [cost.tasks for cost in conducted.costs] == [2], (
        "WHY THIS IS A FAILURE: `--probe 2` was asked for a two-task sample and the run did not "
        f"produce one ({[cost.tasks for cost in conducted.costs]}). A probe that runs the whole "
        "set has answered the scope question by performing the work the question was about"
    )
    assert conducted.report is None and conducted.written is None, (
        "WHY THIS IS A FAILURE: a probe emitted a report. Its counts are over a sample the "
        "operator chose, and publishing them would let the scored set's size be decided while "
        "looking at partial results from it"
    )
    assert not (tmp_path / "out" / REPORT_FILE).exists(), (
        "WHY THIS IS A FAILURE: a probe wrote the scored run's document, so the next reader "
        "cannot tell a measurement from a timing sample"
    )

    published = json.loads((tmp_path / "out" / PROBE_FILE).read_text(encoding="utf-8"))
    assert published["candidates"][0]["seconds_per_task"] > 0.0, (
        "WHY THIS IS A FAILURE: the probe published no measured per-task cost, which is the one "
        f"number it exists to produce. Got {published!r}"
    )
    assert "solved" not in json.dumps(published), (
        "WHY THIS IS A FAILURE: the probe's payload carries a count of solved tasks. The probe "
        "measures time; a count from it is a partial score over a self-chosen sample"
    )


def test_a_contract_that_moves_mid_run_aborts_the_run_and_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The honesty control of this whole slice, fired for real rather than asserted about.

    The template is replaced **after the first task has already been scored**, which is exactly the
    shape of the failure it guards: nobody edits a prompt before a run, they edit it once the first
    numbers look disappointing, and a resumed or continued run then mixes results from two
    different questions under one heading. `PREREGISTRATION.md:133-135` applies that discipline to
    pinned inputs; M7b applies it here, to the input that is not pinned and that moves the number
    most.

    The mechanism under test is deliberately not a flag anybody sets. The contract is frozen as the
    set of prompt digests the declared template produces over the scored set, computed before any
    engine exists; the generator is sealed behind that set; and a prompt whose digest is not in it
    cannot be sent to a base at all. So this test changes the template and never touches the
    driver, and the abort has to come from the seal.
    """
    real = rendering.render_prompt
    seen: list[str] = []

    def _drifting(task: Task, sources: Mapping[str, str]) -> str:
        """The declared template for the first task, and a quietly edited one thereafter."""
        seen.append(task.task_id)
        if len(seen) == 1:
            return real(task, sources)
        return real(task, sources) + "\n\nThink step by step before writing the diff.\n"

    monkeypatch.setattr(scoring, "render_prompt", _drifting)

    with pytest.raises(ContractChanged) as refusal:
        _run(tmp_path)

    message = str(refusal.value)
    assert len(seen) >= 2, (
        "WHY THIS IS A FAILURE: the run never reached a second task, so the template never moved "
        "mid-run and this test would pass for a driver that refuses everything"
    )
    assert "M7b" in message, (
        "WHY THIS IS A FAILURE: the abort does not cite the rule it is enforcing, so an operator "
        f"reads it as a harness crash and re-runs. Got {message!r}"
    )
    assert not (tmp_path / "out" / REPORT_FILE).exists(), (
        "WHY THIS IS A FAILURE: a run whose contract changed mid-flight still wrote a report. "
        "Half its rollouts answered a different question from the other half, and nothing in the "
        "document would say so"
    )


def test_a_declared_dev_subset_task_never_reaches_a_published_count(tmp_path: Path) -> None:
    """M7b: the tasks the contract was developed against are excluded, and said out loud.

    Both halves are asserted, because either alone is a lie of a different kind. Excluded but
    unnamed is an undisclosed denominator — the reader sees `n of 2` and has no way to learn which
    task left. Named but scored is the optimisation the exclusion exists to prevent, and
    `report.build_report` refuses it outright, which is the wiring this test proves is connected.
    """
    conducted = _run(tmp_path, dev_subset=["beta"])

    assert conducted.report is not None
    assert "beta" not in conducted.scored, (
        f"WHY THIS IS A FAILURE: the declared dev-subset task was scored anyway "
        f"({conducted.scored}). The prompt and the extractor were developed against it, so its "
        "outcome is not a measurement of anything"
    )
    assert conducted.report.private[0].denominator == 2, (
        "WHY THIS IS A FAILURE: three private tasks were loaded, one was declared as the dev "
        "subset, and the published denominator is "
        f"{conducted.report.private[0].denominator} rather than 2. A denominator that still "
        "counts an excluded task makes every figure over it wrong by one"
    )
    assert "beta" in conducted.report.markdown, (
        "WHY THIS IS A FAILURE: the excluded task is not named in the report, so the exclusion is "
        "asserted rather than auditable and a reader cannot check what left the denominator"
    )


def test_a_dev_subset_id_that_matches_no_task_is_refused(tmp_path: Path) -> None:
    """A mistyped exclusion excludes nothing while the report says it excluded something.

    The failure is silent by construction: the driver filters on an id that matches nothing, every
    task is scored, and the report still prints the declared subset. Refusing costs one comparison
    and closes the only route by which the dev-subset disclosure could be false.
    """
    with pytest.raises(UnknownDevSubset) as refusal:
        _run(tmp_path, dev_subset=["betta"])

    assert "betta" in str(refusal.value), (
        "WHY THIS IS A FAILURE: the refusal does not name the id that matched nothing, so the "
        f"operator cannot see the typo. Got {str(refusal.value)!r}"
    )


def test_a_broken_control_arm_writes_no_report_at_all(tmp_path: Path) -> None:
    """A run whose harness was never shown to grade anything must publish nothing whatever.

    The vacuous task's declared failing test already passes at `base_commit`, so the inert patch
    reaches PASS and the harness has graded nothing. `rankable` refuses such a run, and the
    property under test here is that the refusal arrives **before** anything is written — a report
    on disk is a report somebody quotes, and a caveat inside it is a thing a reader reads past.
    """
    with pytest.raises(HarnessNotProven):
        _run(tmp_path, private=("alpha", "vacant"), vacuous="vacant")

    assert not (tmp_path / "out" / REPORT_FILE).exists(), (
        "WHY THIS IS A FAILURE: the control arm proved the harness broken and a report was "
        "written anyway. Its zeroes are not attributable to any base, and a document on disk "
        "outlives the exception that should have stopped it"
    )
    assert not (tmp_path / "out" / COST_FILE).exists(), (
        "WHY THIS IS A FAILURE: the cost sidecar survived a refused run, so the output directory "
        "holds partial evidence of a measurement that was never allowed to exist"
    )


def test_the_adapter_is_handed_a_filesystem_path_and_never_a_repo_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC1, asserted on the constructed arguments rather than by loading anything.

    `mlx_lm.utils.load` decides what it was handed with a plain `Path.exists()`: an existing
    directory is read from disk, and **anything else is a repo id and a download**, resolved
    against whatever `main` points at that morning. The adapter already refuses a non-directory;
    what this test covers is the layer above it, which is where the repo id is actually in scope
    and where handing over `weights.repo_id` instead of `weights.local_dir` is a one-word slip
    that nothing downstream could detect.
    """
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    recorded: dict[str, Any] = {}

    class _Records:
        def __init__(self, path: Path | str, *, revision: str, **rest: Any) -> None:
            recorded["path"] = path
            recorded["revision"] = revision
            recorded["offline"] = os.environ.get("HF_HUB_OFFLINE")

        def generate(self, prompt: str) -> str:  # pragma: no cover - never reached here
            return ""

    monkeypatch.setattr("whetstone.bakeoff.run.MlxGenerator", _Records)
    weights = load_weights(_weights(tmp_path / "weights", "mlx-community/Qwen2.5-Coder-3B-4bit"))

    mlx_engine(weights[0])

    assert recorded["path"] == weights[0].local_dir, (
        "WHY THIS IS A FAILURE: the adapter was constructed with "
        f"{recorded['path']!r} rather than the verified local directory "
        f"{str(weights[0].local_dir)!r}. If that value is a repo id, mlx_lm downloads it at call "
        "time and the run's weights become whatever the Hub served this morning"
    )
    assert isinstance(recorded["path"], Path), (
        "WHY THIS IS A FAILURE: the adapter was handed a string. A string that happens to name a "
        f"directory works and a string that does not is a repo id. Got {type(recorded['path'])}"
    )
    assert recorded["revision"] == weights[0].revision, (
        "WHY THIS IS A FAILURE: the adapter was not pinned to the immutable commit sha the "
        f"provenance records. Got {recorded['revision']!r}"
    )
    assert recorded["offline"] == "1", (
        "WHY THIS IS A FAILURE: HF_HUB_OFFLINE was not set when the adapter was constructed, so "
        "a mistyped path would reach the network instead of raising. The environment variable is "
        "the only thing standing between a typo and a download"
    )


def test_a_sound_run_publishes_both_sources_its_contract_and_its_cost(tmp_path: Path) -> None:
    """The green case, so every refusal above is known not to be a driver that refuses everything.

    Asserts the four things a reader of `reports/baseline/` needs to exist at all: both sources
    published together (`PREREGISTRATION.md:142-143`), the frozen contract hash recorded beside
    the counts, the harness proven, and the measured cost written down (AC5, AC8).
    """
    conducted = _run(tmp_path)

    assert conducted.report is not None and conducted.written is not None
    document = (tmp_path / "out" / REPORT_FILE).read_text(encoding="utf-8")
    assert conducted.contract.sha256 in document, (
        "WHY THIS IS A FAILURE: the report does not carry the frozen contract's digest, so M7b's "
        "invalidation rule has nothing to compare a later run against"
    )
    assert conducted.report.private[0].denominator == 3, (
        "WHY THIS IS A FAILURE: the private source's denominator is "
        f"{conducted.report.private[0].denominator} rather than the three tasks in the corpus"
    )
    assert conducted.report.public[0].denominator == 1, (
        "WHY THIS IS A FAILURE: source A was not published beside source B. "
        "PREREGISTRATION.md:142-143 fixes that both are always published together"
    )
    assert [cost.harness for cost in conducted.costs] == [Status.PASS], (
        "WHY THIS IS A FAILURE: the control arm did not prove this harness graded anything, so "
        "the green case is green for a reason nobody established"
    )

    cost = json.loads((tmp_path / "out" / COST_FILE).read_text(encoding="utf-8"))
    assert cost["candidates"][0]["wall_seconds"] > 0.0, (
        f"WHY THIS IS A FAILURE: no wall-clock was recorded per candidate (AC8). Got {cost!r}"
    )


def test_the_entry_point_refuses_an_invocation_that_names_no_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`python -m whetstone.bakeoff.run` with a missing required argument exits non-zero.

    A thin assertion on purpose: what is worth holding is that every input the run depends on is
    *required* rather than defaulted. A default output directory, a default workspace or a default
    timeout would each put a night's work somewhere the operator did not choose — the same
    argument `sweep` makes for refusing to default its journal.
    """
    with pytest.raises(SystemExit) as exit_code:
        main(["--tasks", str(tmp_path), "--weights", str(tmp_path)])

    assert exit_code.value.code != 0, (
        "WHY THIS IS A FAILURE: an invocation naming no output directory, no workspace and no "
        "timeout was accepted. Each of those has to be chosen, because each decides where a "
        "night's work lands or how long it is allowed to take"
    )
    assert "required" in capsys.readouterr().err.lower()
