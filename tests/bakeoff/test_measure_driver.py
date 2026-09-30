"""The measurement driver: population-pinned, verifier never entered, control arm required.

`docs/planning/edit-contract-finding/measurement-run/spec.md` acceptance criteria 3-4 are
the tests written here: the `scoring.score` renderer seam is byte-identical under the
default and an injected renderer reaches the generator; and the driver — with a stub
generator, never a model — writes manifest + journal + transcript over exactly the pinned
16-task population, refuses a task set that is not the pinned list, refuses a run whose
control arm is not intact on every draw, and never enters the verifier for any rollout.

The refusal shape is the `check-probe`/`locatability` one: exit 2, a named reason on
stderr, and **no evidence written** — a journal, transcript or manifest on disk is a
document somebody quotes, and it must not exist for a run that was void.

The control arm is the real thing, through the real verifier, on real two-commit donors:
`control.probe` by identity, exactly as the night builds it. What is stubbed is the base —
a generator that answers every prompt with one fixture completion, recording what it was
asked. The seam-spy assertion on `scoring.verify_strict`/`verify_weak` stays clean while
the control arm genuinely verifies, because the control reaches the verifier through
`whetstone.verify.strict` directly and the rollout path never does.

No model, no `mlx`, no network. Nothing writes outside `tmp_path` (the default-paths test
chdirs into `tmp_path` first). The pinned population is spelled here as the spec's list and
cross-pinned against the module's constant, so a drift in either is a red test.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from fixtures.repos.mined import build_mined_task

from whetstone.bakeoff import measure
from whetstone.bakeoff import stratum as stratum_module
from whetstone.bakeoff.control import Control
from whetstone.bakeoff.generator import Generator
from whetstone.bakeoff.journal import Journal
from whetstone.bakeoff.line_range import render_line_range_prompt
from whetstone.bakeoff.rendering import prompt_hash, render_prompt
from whetstone.bakeoff.scoring import Interpreters, Outcome, score
from whetstone.bakeoff.sources import oracle_sources
from whetstone.bakeoff.transcript import Transcript
from whetstone.bakeoff.weights import PROVENANCE_FILE, PROVENANCE_SCHEMA, Weights
from whetstone.loop import heldout as heldout_module
from whetstone.tasks.manifest import load_tasks

#: The candidate the pinned base is measured under (PREREGISTRATION.md § 10.10).
CANDIDATE = "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit"

#: The date the operator declares. An input everywhere, never a clock.
RECORDED_ON = "2026-09-30"

#: Generous enough that a two-commit donor with one module and one pytest file can never reach it.
TIMEOUT = 120.0

#: The spec's pinned 16, spelled here as the committed rule names them (spec.md "Population"),
#: and cross-pinned against the module's own constant below.
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
#: pre-committed floors (10 total, 2 per band) while subtracting exactly the overlap.
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

#: One fixture completion: a well-formed EDIT block in the measurement format. What the stub
#: base answers with; the driver never parses it (the instrument does, in phase 3).
COMPLETION = (
    "EDIT calc.py:1-2\n"
    "<<<<<<< REPLACE\n"
    "def add(a, b):\n"
    "    return a + b\n"
    ">>>>>>> END\n"
)

#: The measurement detail every rollout row carries. Spelled here and asserted, so the
#: journal's rows can never silently stop saying the run never grades.
MEASUREMENT_DETAIL = "measurement run — no grading performed by design"

#: One stand-in weights file per fake candidate, the test_run shape.
WEIGHT_FILES = {"config.json": '{"model_type": "qwen2"}', "model.safetensors": "not a tensor"}


class _AnswersEveryPrompt:
    """A base that answers every prompt with one completion, recording what it was asked.

    The driver poses the numbered-listing prompt and nothing else, so a table of exact
    prompts is unnecessary: the stub's own record is what the transcript is asserted
    against.
    """

    def __init__(self, completion: str = COMPLETION) -> None:
        self.completion = completion
        self.asked: list[str] = []

    def generate(self, prompt: str) -> str:
        self.asked.append(prompt)
        return self.completion


def _engine_of(generator: Generator) -> Any:
    """An `Engine` returning `generator`, ignoring the weights and the budget it is handed."""

    def factory(_: Weights, max_tokens: int) -> Generator:
        assert max_tokens >= 1, max_tokens
        return generator

    return factory


def _difficulty() -> dict[str, int]:
    """One measured-difficulty entry: all seven fields the loaders require, minimum values."""
    return {"files": 1, "hunks": 1, "added": 1, "deleted": 1, "f2p": 1, "pins": 0, "blobs": 1}


def _stratum_document(root: Path, members: Sequence[str], **fields: Any) -> Path:
    """A valid `whetstone-stratum/1` document whose membership is `members`.

    Sealed through the module's own `document_digest_of` **after** `fields` are applied, so
    a doctored field does not hide behind a stale digest — the `test_stratum_filter`
    pattern. Two extra corpus ids keep the membership a proper subset of the corpus, which
    the loader demands.
    """
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


def _heldout_document(root: Path, members: Sequence[str], **fields: Any) -> Path:
    """A valid `whetstone-heldout/1` document whose membership is `members`.

    Bands are assigned so the pre-committed floors hold for any 12-member membership:
    four members per band, two corpus extras keep the membership a proper subset.
    """
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


@pytest.fixture(scope="module")
def inputs(tmp_path_factory: pytest.TempPathFactory):
    """The pinned 16 tasks as real two-commit donors, fake weights, and their exact prompts.

    `expected` maps each pinned id to the numbered-listing prompt the driver must pose for
    it — derived once here through the same oracle derivation the driver uses, so every
    assertion on what the base was asked compares against the contract's own rendering.
    """
    root = tmp_path_factory.mktemp("measure-inputs")
    corpus = root / "private"
    corpus.mkdir()
    for task_id in SPEC_PINNED:
        build_mined_task(
            root / f"donor-{task_id}",
            task_id=task_id,
            subject=f"Fix addition ({task_id})",
        )
        shutil.copy(root / f"donor-{task_id}" / f"{task_id}.json", corpus / f"{task_id}.json")

    by_id = {task.task_id: task for task in load_tasks(corpus)}
    expected: dict[str, str] = {}
    for task_id in SPEC_PINNED:
        sources = oracle_sources(by_id[task_id], pool=None)
        assert sources.files is not None, sources.reason
        expected[task_id] = render_line_range_prompt(by_id[task_id], sources.files)
    return corpus, _weights(root / "weights", CANDIDATE), expected


def _run(
    tmp_path: Path,
    inputs: tuple[Path, Path, dict[str, str]],
    engine: Any,
    **overrides: Any,
) -> measure.Measured:
    """One measurement run over the pinned 16, with stubbed generation."""
    corpus, weights_root, _ = inputs
    arguments: dict[str, Any] = {
        "tasks": (corpus,),
        "stratum": _stratum_document(tmp_path / "docs", STRATUM_MEMBERS),
        "heldout": _heldout_document(tmp_path / "docs", HELDOUT_MEMBERS),
        "weights": weights_root,
        "workspace": tmp_path / "workspace",
        "recorded_on": RECORDED_ON,
        "timeout": TIMEOUT,
        "journal": tmp_path / "journal.jsonl",
        "transcript": tmp_path / "transcript.jsonl",
        "manifest": tmp_path / "manifest.json",
        "engine": engine,
    }
    arguments.update(overrides)
    return measure.run_measurement(**arguments)


def _cli(
    tmp_path: Path,
    inputs: tuple[Path, Path, dict[str, str]],
    *,
    stratum: Path | None = None,
    heldout: Path | None = None,
    weights: Path | None = None,
    workspace: str | None = None,
    **extra: Any,
) -> list[str]:
    """The command-line spelling of one run, for the refusal paths main() is asked about."""
    corpus, weights_root, _ = inputs
    args = [
        "--tasks", str(corpus),
        "--stratum", str(stratum or _stratum_document(tmp_path / "docs", STRATUM_MEMBERS)),
        "--heldout", str(heldout or _heldout_document(tmp_path / "docs", HELDOUT_MEMBERS)),
        "--weights", str(weights_root if weights is None else weights),
        "--workspace", str(tmp_path / "workspace" if workspace is None else workspace),
        "--recorded-on", RECORDED_ON,
        "--timeout", str(TIMEOUT),
        "--journal", str(tmp_path / "journal.jsonl"),
        "--transcript", str(tmp_path / "transcript.jsonl"),
        "--manifest", str(tmp_path / "manifest.json"),
    ]
    for flag, value in extra.items():
        args += [flag, str(value)]
    return args


def _evidence_paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    """The journal, transcript and manifest paths `_cli` writes to, for refusal assertions."""
    return tmp_path / "journal.jsonl", tmp_path / "transcript.jsonl", tmp_path / "manifest.json"


# --- The scoring seam (spec criterion 3) -----------------------------------------------------


def test_the_default_renderer_reaches_the_generator_byte_identical_to_master(
    tmp_path: Path,
) -> None:
    """`score(renderer=None)` poses exactly `render_prompt`'s bytes — master behaviour.

    The assertion is on the string the generator actually receives, not on an outcome: a
    harness could produce the right outcome while rendering something else. The expected
    prompt is derived the way master derives it, so a seam that drifted by a single byte
    fails here.
    """
    fixture = build_mined_task(tmp_path / "task")
    sources = oracle_sources(fixture.task, pool=None)
    assert sources.files is not None, sources.reason
    expected = render_prompt(fixture.task, sources.files)
    seen: list[str] = []

    class _Sees:
        def generate(self, prompt: str) -> str:
            seen.append(prompt)
            return "no diff here"

    score(
        candidate="default-renderer",
        task=fixture.task,
        generator=_Sees(),
        sandbox_root=tmp_path / "runs",
        timeout=TIMEOUT,
        interpreters=Interpreters(workspace=tmp_path / "envs"),
    )

    assert seen == [expected], (
        "WHY THIS IS A FAILURE: the default renderer reached the generator with different "
        f"bytes than render_prompt produces ({seen!r}). Every existing caller's prompt "
        "must be byte-identical — the existing suite green is the guard, and this test is "
        "the explicit statement of it"
    )


def test_an_injected_renderer_reaches_the_generator(tmp_path: Path) -> None:
    """The seam is live: a caller-supplied renderer replaces `render_prompt` for that call.

    The measurement run's numbered-listing prompt is supplied this way at the seam, so a
    seam that parsed the argument and ignored it would render the diff prompt for a run
    that believes it asked for EDIT blocks.
    """
    fixture = build_mined_task(tmp_path / "task")
    seen: list[str] = []

    class _Sees:
        def generate(self, prompt: str) -> str:
            seen.append(prompt)
            return "no diff here"

    score(
        candidate="injected-renderer",
        task=fixture.task,
        generator=_Sees(),
        sandbox_root=tmp_path / "runs",
        timeout=TIMEOUT,
        interpreters=Interpreters(workspace=tmp_path / "envs"),
        renderer=lambda task, sources: "the numbered-listing prompt",
    )

    assert seen == ["the numbered-listing prompt"], (
        f"WHY THIS IS A FAILURE: the injected renderer's text did not reach the generator "
        f"({seen!r}). The seam is a dead argument"
    )


# --- The pinned population (spec criterion 4) ------------------------------------------------


def test_the_pinned_population_constant_is_the_specs_list() -> None:
    """The module's constant is the spec's 16 ids, spelled here — a drift in either is red."""
    assert measure._PINNED_POPULATION == SPEC_PINNED


def test_the_driver_runs_exactly_the_pinned_population_in_order(
    tmp_path: Path, inputs: Any
) -> None:
    """One greedy attempt per pinned task, in pinned (sorted) order — nothing else is asked."""
    stub = _AnswersEveryPrompt()
    measured = _run(tmp_path, inputs, engine=_engine_of(stub))

    assert measured.tasks == SPEC_PINNED
    assert stub.asked == [inputs[2][task_id] for task_id in SPEC_PINNED], (
        "WHY THIS IS A FAILURE: the base was asked prompts other than the pinned tasks' "
        "numbered-listing prompts, or in a different order"
    )


def test_a_task_set_that_is_not_the_pinned_population_is_refused(
    tmp_path: Path, inputs: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """A stratum/held-out pair whose difference is not the pinned 16 is refused, exit 2.

    A run whose task set differs from the committed list is a run over a different
    experiment (spec: "A run whose task set differs from this list is refused"), and a
    refusal must leave no evidence: no journal, no transcript, no manifest.
    """
    corpus, weights_root, _ = inputs
    smaller = tuple(sorted(set(STRATUM_MEMBERS) - {SPEC_PINNED[0]}))
    stratum_path = _stratum_document(tmp_path / "docs", smaller)
    heldout_path = _heldout_document(tmp_path / "docs", HELDOUT_MEMBERS)
    journal, transcript, manifest = _evidence_paths(tmp_path)

    assert measure.main(_cli(tmp_path, inputs, stratum=stratum_path, heldout=heldout_path)) == 2
    assert "pinned" in capsys.readouterr().err, (
        "the refusal must name the pinned population, not crash like a harness defect"
    )
    assert not journal.exists() and not transcript.exists() and not manifest.exists(), (
        "WHY THIS IS A FAILURE: a refused run left evidence on disk. A journal, transcript "
        "or manifest outlives the exception that should have stopped it, and reads as a "
        "measurement"
    )
    assert corpus.exists() and weights_root.exists()

    # And the driver function itself names the refusal, so a caller reaching it another way
    # is refused just the same.
    with pytest.raises(measure.PopulationMismatch):
        measure.run_measurement(
            tasks=(corpus,),
            stratum=stratum_path,
            heldout=heldout_path,
            weights=weights_root,
            workspace=tmp_path / "workspace",
            recorded_on=RECORDED_ON,
            timeout=TIMEOUT,
            journal=journal,
            transcript=transcript,
            manifest=manifest,
            engine=_engine_of(_AnswersEveryPrompt()),
        )
    assert not journal.exists()


def test_an_empty_population_is_refused_by_name(tmp_path: Path, inputs: Any) -> None:
    """A stratum wholly inside the held-out membership leaves nothing to roll out."""
    corpus, weights_root, _ = inputs
    stratum_path = _stratum_document(tmp_path / "docs", OVERLAP)
    heldout_path = _heldout_document(tmp_path / "docs", HELDOUT_MEMBERS)

    with pytest.raises(measure.EmptyPopulation):
        measure.run_measurement(
            tasks=(corpus,),
            stratum=stratum_path,
            heldout=heldout_path,
            weights=weights_root,
            workspace=tmp_path / "workspace",
            recorded_on=RECORDED_ON,
            timeout=TIMEOUT,
            journal=tmp_path / "journal.jsonl",
            transcript=tmp_path / "transcript.jsonl",
            manifest=tmp_path / "manifest.json",
            engine=_engine_of(_AnswersEveryPrompt()),
        )


def test_a_hand_edited_document_is_refused_by_the_document_digest(
    tmp_path: Path, inputs: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """A document whose `document_digest` no longer matches its payload is refused by name.

    The stratum and held-out documents are pre-committed pinned inputs; a hand-edited
    membership or value breaks the digest, and the loader refuses rather than trusts — the
    same fail-closed posture the night's held-out loader takes.
    """
    stratum_path = _stratum_document(tmp_path / "docs", STRATUM_MEMBERS)
    raw = json.loads(stratum_path.read_text())
    raw["difficulty"][SPEC_PINNED[0]]["files"] = 2
    stratum_path.write_text(json.dumps(raw))

    assert measure.main(_cli(tmp_path, inputs, stratum=stratum_path)) == 2
    assert "digest" in capsys.readouterr().err

    heldout_path = _heldout_document(tmp_path / "docs", HELDOUT_MEMBERS)
    raw = json.loads(heldout_path.read_text())
    raw["difficulty"][HELDOUT_MEMBERS[0]]["files"] = 2
    heldout_path.write_text(json.dumps(raw))
    args = _cli(tmp_path, inputs, heldout=heldout_path)
    args[args.index("--stratum") + 1] = str(_stratum_document(tmp_path / "docs", STRATUM_MEMBERS))
    assert measure.main(args) == 2
    assert "digest" in capsys.readouterr().err


def test_a_missing_document_is_refused(tmp_path: Path, inputs: Any) -> None:
    """A stratum or held-out document that cannot be read is a refusal, not a default."""
    corpus, weights_root, _ = inputs
    absent = tmp_path / "absent" / "easier.json"

    with pytest.raises(ValueError):
        measure.run_measurement(
            tasks=(corpus,),
            stratum=absent,
            heldout=_heldout_document(tmp_path / "docs", HELDOUT_MEMBERS),
            weights=weights_root,
            workspace=tmp_path / "workspace",
            recorded_on=RECORDED_ON,
            timeout=TIMEOUT,
            journal=tmp_path / "journal.jsonl",
            transcript=tmp_path / "transcript.jsonl",
            manifest=tmp_path / "manifest.json",
            engine=_engine_of(_AnswersEveryPrompt()),
        )


# --- The control arm and the verifier (spec criterion 4) -------------------------------------


def test_the_control_arm_runs_through_the_verifier_and_must_be_intact_on_every_draw(
    tmp_path: Path, inputs: Any
) -> None:
    """A successful run's journal carries an INTACT probe per task, taken by the real probe.

    The probes are the real `control.probe` records — inert patch FAIL, re-derived
    reference PASS — which is the whole claim behind any later use of this run's evidence:
    a verdict about a verifier that graded nothing is no verdict.
    """
    stub = _AnswersEveryPrompt()
    measured = _run(tmp_path, inputs, engine=_engine_of(stub))

    steps = Journal(Path(measured.journal)).replay()
    assert len(steps) == len(SPEC_PINNED)
    assert [step.probe.control for step in steps.values()] == [Control.INTACT] * len(SPEC_PINNED), (
        "WHY THIS IS A FAILURE: a probe that is not INTACT means the harness was not shown "
        "to discriminate on that task, so nothing measured on it is evidence about any base"
    )


def test_a_control_arm_that_is_not_intact_refuses_and_writes_nothing(
    tmp_path: Path, inputs: Any
) -> None:
    """A run whose control fold is not PASS produces no evidence and no verdict.

    One pinned task is built `vacuous` — its declared failing test already passes at
    `base_commit` — so its probe is genuinely BROKEN through the real verifier, and the
    fold is UNVERIFIED. The run refuses with the named reason and writes nothing.
    """
    root = tmp_path / "corpus"
    vacuous = SPEC_PINNED[0]
    vacuous_corpus = root / "private"
    vacuous_corpus.mkdir(parents=True)
    for task_id in SPEC_PINNED:
        build_mined_task(
            root / f"donor-{task_id}",
            task_id=task_id,
            subject=f"Fix addition ({task_id})",
            vacuous=task_id == vacuous,
        )
        shutil.copy(
            root / f"donor-{task_id}" / f"{task_id}.json", vacuous_corpus / f"{task_id}.json"
        )
    weights_root = _weights(root / "weights", CANDIDATE)
    journal, transcript, manifest = _evidence_paths(tmp_path)

    with pytest.raises(measure.ControlNotIntact) as refusal:
        measure.run_measurement(
            tasks=(vacuous_corpus,),
            stratum=_stratum_document(tmp_path / "docs", STRATUM_MEMBERS),
            heldout=_heldout_document(tmp_path / "docs", HELDOUT_MEMBERS),
            weights=weights_root,
            workspace=tmp_path / "workspace",
            recorded_on=RECORDED_ON,
            timeout=TIMEOUT,
            journal=journal,
            transcript=transcript,
            manifest=manifest,
            engine=_engine_of(_AnswersEveryPrompt()),
        )
    assert vacuous in str(refusal.value), (
        "the refusal must name the task whose control arm failed, so the operator can see "
        "which draw voided the run"
    )
    assert not journal.exists() and not transcript.exists() and not manifest.exists(), (
        "WHY THIS IS A FAILURE: a run whose harness was never shown to grade anything left "
        "evidence on disk — a journal or manifest that reads as a measurement of nothing"
    )


def test_the_verifier_is_never_entered_for_any_rollout(
    tmp_path: Path, inputs: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Completions are recorded, journal rows written, and no rollout calls either verifier.

    The seam spy sits on `scoring.verify_strict`/`verify_weak` — the rollout path's own
    entry points. The control arm reaches the verifier through `whetstone.verify.strict`
    directly and stays untouched, which is the point of the assertion: the *rollouts* are
    never graded, by design, while the harness is still proven.
    """
    calls: list[str] = []
    monkeypatch.setattr(
        "whetstone.bakeoff.scoring.verify_strict", lambda *a, **k: calls.append("strict")
    )
    monkeypatch.setattr(
        "whetstone.bakeoff.scoring.verify_weak", lambda *a, **k: calls.append("weak")
    )
    stub = _AnswersEveryPrompt()
    measured = _run(tmp_path, inputs, engine=_engine_of(stub))

    assert calls == [], (
        f"WHY THIS IS A FAILURE: a rollout reached a verifier ({calls}). The measurement "
        "run never grades by design — its rows record UNVERIFIED with a detail saying so, "
        "and a verifier entry would make those rows a lie"
    )
    steps = Journal(Path(measured.journal)).replay()
    assert len(steps) == len(SPEC_PINNED)
    for step in steps.values():
        assert step.rollout.outcome is Outcome.UNVERIFIED
        assert step.rollout.detail == MEASUREMENT_DETAIL
        assert step.rollout.strict is None and step.rollout.weak is None, (
            "WHY THIS IS A FAILURE: a rollout that was never graded carries a verdict "
            "status. `None` means no verifier ran; UNVERIFIED means the harness tried and "
            "could not tell — the measurement is the first, never the second"
        )
        assert step.probe.control is Control.INTACT, (
            "the spy must not have disabled the control arm: its probes are still the "
            "real, verifier-grounded ones"
        )


# --- The evidence (spec criterion 4) ---------------------------------------------------------


def test_the_driver_writes_manifest_journal_and_transcript(tmp_path: Path, inputs: Any) -> None:
    """A successful run writes all three, in the exact shapes phase 3 will read.

    The journal rows carry `outcome = UNVERIFIED` and the measurement detail; the
    transcript round-trips the completion byte-for-byte beside the exact prompt; the
    manifest carries the run identity, the pinned task list, the document digests, the
    per-task `prompt_sha256`, the per-draw control status and the tool versions.
    """
    stub = _AnswersEveryPrompt()
    measured = _run(tmp_path, inputs, engine=_engine_of(stub))

    manifest = json.loads(Path(measured.manifest).read_text())
    assert manifest["schema"] == "whetstone-measure/1"
    assert manifest["run_id"] == measured.run_id
    assert manifest["recorded_on"] == RECORDED_ON
    assert manifest["run_seed"] == measure.RUN_SEED
    assert manifest["tasks"] == list(SPEC_PINNED)
    assert manifest["candidate"] == {"repo_id": CANDIDATE, "revision": measured.revision}
    assert len(manifest["candidate"]["revision"]) == 64, (
        "the revision must be the immutable sha the weights provenance names, never a tag"
    )

    expected = inputs[2]
    assert manifest["prompt_sha256"] == {
        task_id: prompt_hash(expected[task_id]) for task_id in SPEC_PINNED
    }, (
        "WHY THIS IS A FAILURE: the manifest's per-task prompt digests do not match the "
        "numbered-listing prompts the run poses, so the manifest could not be the source "
        "of truth for what each rollout was asked"
    )
    assert manifest["control"] == {task_id: "INTACT" for task_id in SPEC_PINNED}
    assert set(manifest["tool_versions"]) >= {"python", "whetstonehq", "mlx-lm", "platform"}

    steps = Journal(Path(measured.journal)).replay()
    assert len(steps) == len(SPEC_PINNED)
    for (key_candidate, task_id), step in steps.items():
        assert key_candidate == CANDIDATE
        assert step.rollout.candidate == CANDIDATE
        assert step.rollout.task_id == task_id
        assert step.rollout.outcome is Outcome.UNVERIFIED
        assert step.rollout.detail == MEASUREMENT_DETAIL
        assert step.rollout.strict is None and step.rollout.weak is None
        assert step.rollout.verdict_kinds == ()
        assert step.rollout.prompt_sha256 == manifest["prompt_sha256"][task_id]
        assert step.rollout.generation_seconds >= 0.0

    records = Transcript(Path(measured.transcript)).replay()
    assert len(records) == len(SPEC_PINNED)
    for (key_candidate, task_id), record in records.items():
        assert key_candidate == CANDIDATE
        assert record.prompt == expected[task_id], (
            "WHY THIS IS A FAILURE: the transcript does not carry the exact prompt the "
            "contract renders for the task, so a replay could not re-derive what the base "
            "was shown"
        )
        assert record.prompt_sha256 == prompt_hash(expected[task_id])
        assert record.completion == stub.completion, (
            "WHY THIS IS A FAILURE: the completion did not round-trip byte-for-byte. The "
            "transcript is the evidence the instrument reads; an edited completion would "
            "classify a rollout that never happened"
        )
        assert record.attempt == 1 and record.decision == "graded"


def test_the_manifest_is_byte_identical_across_two_runs(tmp_path: Path, inputs: Any) -> None:
    """Same inputs, fixed seed, same stub answers: byte-identical manifests.

    The run id descends from declared inputs, not from the clock; `recorded_on` is an
    input; nothing in the manifest is measured. Two runs over the same inputs are the same
    experiment, and their manifests have to be the same bytes.
    """
    stub = _AnswersEveryPrompt()
    first = _run(tmp_path, inputs, engine=_engine_of(stub), run_seed=42)
    second = _run(tmp_path, inputs, engine=_engine_of(stub), run_seed=42)

    assert first.run_id == second.run_id
    first_bytes = Path(first.manifest).read_bytes()
    second_bytes = Path(second.manifest).read_bytes()
    assert first_bytes == second_bytes, (
        "WHY THIS IS A FAILURE: two runs over one stub table and one seed wrote different "
        "manifests, so the manifest is not a pure function of the run's declared inputs"
    )
    assert json.loads(first_bytes)["run_seed"] == 42


def test_journal_and_transcript_default_to_runs_edit_contract_finding(
    tmp_path: Path, inputs: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without explicit paths, the evidence lands in the gitignored runs home.

    `runs/` is gitignored — the evidence of a private measurement run never enters the
    tree — and the defaults are resolved from the working directory, so this test chdirs
    into `tmp_path` to keep everything off the worktree.
    """
    monkeypatch.chdir(tmp_path)
    stub = _AnswersEveryPrompt()
    measured = _run(
        tmp_path,
        inputs,
        engine=_engine_of(stub),
        journal=None,
        transcript=None,
        manifest=None,
    )

    assert measured.journal == Path("runs/edit-contract-finding/journal.jsonl")
    assert measured.transcript == Path("runs/edit-contract-finding/transcript.jsonl")
    assert measured.manifest == Path("runs/edit-contract-finding/manifest.json")
    assert measured.journal.is_file() and measured.transcript.is_file()
    assert measured.manifest.is_file()


# --- The CLI refusals ------------------------------------------------------------------------


def test_a_relative_workspace_is_refused(tmp_path: Path, inputs: Any) -> None:
    """`--workspace` must be an absolute path — the runbook's known pitfall, refused here.

    A relative workspace resolves against wherever the operator happened to start the
    process, so the same command from two shells builds its sandboxes in two places; the
    refusal names the pitfall rather than letting the run quietly depend on the CWD.
    """
    corpus, weights_root, _ = inputs
    with pytest.raises(measure.RelativeWorkspace):
        measure.run_measurement(
            tasks=(corpus,),
            stratum=_stratum_document(tmp_path / "docs", STRATUM_MEMBERS),
            heldout=_heldout_document(tmp_path / "docs", HELDOUT_MEMBERS),
            weights=weights_root,
            workspace="relative/workspace",
            recorded_on=RECORDED_ON,
            timeout=TIMEOUT,
            journal=tmp_path / "journal.jsonl",
            transcript=tmp_path / "transcript.jsonl",
            manifest=tmp_path / "manifest.json",
            engine=_engine_of(_AnswersEveryPrompt()),
        )

    assert measure.main(_cli(tmp_path, inputs, workspace="relative/workspace")) == 2


def test_a_missing_weights_root_is_refused(
    tmp_path: Path, inputs: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--weights` naming a root with no provenance is refused before anything is generated."""
    empty = tmp_path / "no-weights"
    empty.mkdir()
    assert measure.main(_cli(tmp_path, inputs, weights=empty)) == 2
    assert "provenance" in capsys.readouterr().err


def test_a_candidate_not_in_the_weights_provenance_is_refused(
    tmp_path: Path, inputs: Any
) -> None:
    """`--only` naming a candidate the provenance does not carry is refused, never resolved."""
    assert measure.main(_cli(tmp_path, inputs, **{"--only": "nobody"})) == 2


def test_a_weights_root_holding_more_than_one_candidate_is_refused(
    tmp_path: Path, inputs: Any
) -> None:
    """The measurement is one candidate; a provenance naming several is refused, not picked.

    Selecting one by position would be a coin toss the manifest has no way to disclose —
    the `select_candidates` refusal shape, applied to the measurement's one-candidate
    requirement.
    """
    corpus, _, _ = inputs
    both = _weights(
        tmp_path / "two-weights", CANDIDATE, "mlx-community/Qwen2.5-Coder-3B-Instruct-4bit"
    )
    with pytest.raises(measure.NotOneCandidate):
        measure.run_measurement(
            tasks=(corpus,),
            stratum=_stratum_document(tmp_path / "docs", STRATUM_MEMBERS),
            heldout=_heldout_document(tmp_path / "docs", HELDOUT_MEMBERS),
            weights=both,
            workspace=tmp_path / "workspace",
            recorded_on=RECORDED_ON,
            timeout=TIMEOUT,
            journal=tmp_path / "journal.jsonl",
            transcript=tmp_path / "transcript.jsonl",
            manifest=tmp_path / "manifest.json",
            engine=_engine_of(_AnswersEveryPrompt()),
        )