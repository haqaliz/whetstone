"""The night, end to end — and the three ways it could quietly produce a dataset nobody verified.

Every other file in this package tests a component with a narrow claim. This one composes them
into a night, and composition is where the honesty controls either hold or silently do not.

The P2 exit criteria (`docs/ROADMAP.md:399-403`) are the assertions here, in their own words:

* the door produces `runs/<id>/` with a ledger, and `checkpoints/<id>/` with a candidate;
* **every** example in the training set carries a recorded strict-PASS verdict;
* same seed → byte-identical training set;
* the ledger records pinned seeds, model revision, task set and tool versions.

And the three failures they are worth asserting against, none hypothetical:

* **a zero-yield night that still writes a candidate.** An adapter trained on nothing is
  indistinguishable, to P3's gate, from one that learned something — so a night that selected no
  verified rollout must write no checkpoint and say so.
* **a dataset assembled from an unproven harness.** `sweep.rankable` refuses those records; if
  the night reached around it, a broken verifier's zeroes would become training data.
* **a training set that varies between two identical invocations.** The determinism criterion is
  the whole basis for calling a night reproducible, and it is asserted by running two of them.

No model, no `mlx`, no network, no weights: the base is a stub behind an injected engine factory
and the trainer is a stub behind the injected `Trainer` seam.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from loop.harness import (
    RECORDED_ON,
    TIMEOUT,
    Answers,
    corpus,
    engine_of,
    pool,
    solving_answers,
    weights,
)
from whetstone.bakeoff.scoring import Outcome
from whetstone.loop import dataset as training
from whetstone.loop import ledger as run_ledger
from whetstone.loop import sft
from whetstone.loop.night import DATA_DIR, DATASET_FILE, EVIDENCE_DIR, Night, run_night
from whetstone.verify.verdict import Status

#: Two draws rather than the declared `K`. The property under test is "k draws per task, each
#: seeded and selected independently", which two exercise exactly as eight do — and eight would
#: put sixteen sandboxed pytest pairs into every test in this file. `K` itself is asserted where
#: it is declared (`test_sampling.py`), which is the place a silent change to it would show.
DRAWS = 2

#: The night's declared seed. An input everywhere, like every other pinned input.
SEED = 20260820


def _trainer(request: sft.TrainingRequest) -> sft.TrainingResult:
    """A trainer that writes an adapter-shaped file and measures nothing.

    Substituted for `sft.mlx_trainer` through the seam that exists for exactly this: the
    checkpoint's identity, its provenance and its re-hash are properties of this repository's
    code, and asserting them must not require 18 GiB of weights and a GPU.
    """
    request.adapters.mkdir(parents=True, exist_ok=True)
    (request.adapters / request.args.adapter_file).write_bytes(b"not a tensor, deliberately")
    return sft.TrainingResult(peak_bytes=8 * 1024**3, seconds=0.5)


def _night(tmp_path: Path, **overrides: Any) -> Night:
    """One night over one private task and one public task, with a stubbed engine and trainer."""
    private, private_built = corpus(tmp_path / "corpus", "private", ("alpha",))
    public, public_built = corpus(tmp_path / "corpus", "public", ("pallets__flask-4045",))
    answers = overrides.pop("answers", None)
    if answers is None:
        answers = solving_answers(*private_built, *public_built)
    arguments: dict[str, Any] = {
        "tasks": (private,),
        "public": public,
        "pool": pool(tmp_path / "pool" / "pool.json"),
        "weights": weights(tmp_path / "weights", "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit"),
        "runs": tmp_path / "runs",
        "checkpoints": tmp_path / "checkpoints",
        "workspace": tmp_path / "work",
        "timeout": TIMEOUT,
        "recorded_on": RECORDED_ON,
        "run_id": "night-001",
        "run_seed": SEED,
        "draws": DRAWS,
        "engine": engine_of(Answers(answers)),
        "trainer": _trainer,
        "seeder": lambda _: None,
    }
    arguments.update(overrides)
    return run_night(**arguments)


def test_a_night_produces_a_run_directory_with_a_ledger_and_a_candidate(tmp_path: Path) -> None:
    """P2 exit criterion 1, asserted as the operator would check it: the files are there.

    The two directories are separate on purpose and both are gitignored roots: `runs/<id>/` is
    the evidence — the ledger, the dataset, the per-draw journals and transcripts — and
    `checkpoints/<id>/` is the artefact P3's gate will later compare. A night that wrote one and
    not the other would look complete from whichever half its reader opened.
    """
    night = _night(tmp_path)

    assert night.directory == tmp_path / "runs" / "night-001", night.directory
    for expected in (run_ledger.LEDGER_FILE, DATASET_FILE):
        assert (night.directory / expected).is_file(), (
            f"WHY THIS IS A FAILURE: the run directory holds no {expected}. The roadmap's exit "
            "criterion is that `run --night` produces a run directory WITH a ledger; a directory "
            "of scratch with no record of what was pinned is not that"
        )
    assert (night.directory / DATA_DIR / training.TRAIN_FILE).is_file(), (
        "WHY THIS IS A FAILURE: no train.jsonl. The dataset document records what was selected; "
        "this file is what a trainer actually reads, and a night that wrote the record and not "
        "the data would report a training set nothing was trained on"
    )
    assert night.checkpoint is not None and night.checkpoint.directory.is_dir(), (
        "WHY THIS IS A FAILURE: the night solved tasks and produced no candidate. A checkpoint "
        f"under checkpoints/<id>/ is the exit criterion. Reason recorded: "
        f"{night.checkpoint_absent!r}"
    )
    assert (night.directory / EVIDENCE_DIR).is_dir(), (
        "WHY THIS IS A FAILURE: the per-draw journals and transcripts are missing, so a killed "
        "night could not resume and no completion could be re-read offline"
    )


def test_every_training_example_carries_a_recorded_strict_pass_verdict(tmp_path: Path) -> None:
    """P2 exit criterion 2 — the one this whole project rests on.

    Asserted over the **written document** rather than over the in-memory objects, because the
    document is what a later step reads and what a reviewer would open. Every record must carry
    both `SOLVED` and a strict `PASS`: the tag and the verifier's own verdict are produced by
    different steps, and a record whose halves disagree is a defect, not a win.

    The denominator assertion is the anti-vacuity half. A selection that returned nothing would
    satisfy "every example is a strict PASS" perfectly, and this fixture's base writes the task's
    own reference patch, so there must be examples to check.
    """
    night = _night(tmp_path)
    document = json.loads((night.directory / DATASET_FILE).read_text(encoding="utf-8"))

    assert document["examples"], (
        "WHY THIS IS A FAILURE: the night selected nothing, so the assertion below holds "
        "vacuously. The stub base answers with each task's own reference patch, which reaches "
        "STRICT PASS — a selection of nothing means the pipeline dropped a verified win"
    )
    offenders = [
        one
        for one in document["examples"]
        if one["strict"] != Status.PASS.value or one["outcome"] != Outcome.SOLVED.value
    ]
    assert not offenders, (
        f"WHY THIS IS A FAILURE: {len(offenders)} training example(s) do not carry a recorded "
        f"strict-PASS verdict: {offenders!r}. UNVERIFIED is never a win and never training data; "
        "an example without the verifier's own PASS is a rollout nobody verified, being trained "
        "on"
    )


def test_the_same_seed_produces_a_byte_identical_training_set(tmp_path: Path) -> None:
    """P2 exit criterion 3, run rather than argued: two nights, one seed, the same bytes.

    Two whole nights into two run roots, compared on the **written** dataset document and on
    `train.jsonl`. Comparing in-memory objects would prove the selection is deterministic and
    say nothing about the ordering, the digest or the serialisation — and the criterion is about
    a *training set*, which is a file.
    """
    first = _night(tmp_path / "one")
    second = _night(tmp_path / "two")

    for name in (DATASET_FILE, f"{DATA_DIR}/{training.TRAIN_FILE}"):
        left = (first.directory / name).read_bytes()
        right = (second.directory / name).read_bytes()
        assert left == right, (
            f"WHY THIS IS A FAILURE: two nights at seed {SEED} over the same task set and the "
            f"same frozen contract produced different {name}. The determinism criterion is the "
            "entire basis for calling a night reproducible: without it, a dataset cannot be "
            "re-derived, a checkpoint cannot be explained by its inputs, and the pinned seed in "
            "the ledger records nothing"
        )
    assert first.dataset.digest == second.dataset.digest, (
        "WHY THIS IS A FAILURE: the datasets are byte-identical and their digests differ, which "
        "means the digest is over something other than the document — a provenance value nobody "
        "can recompute"
    )


def test_a_night_that_selected_nothing_writes_no_checkpoint_and_says_so(tmp_path: Path) -> None:
    """The zero-yield night: a published outcome, never an empty candidate.

    A low strict-PASS yield is a legitimate result — the roadmap's own response is to raise the
    number of draws, never to loosen what counts as a win — so the night must complete, record
    what it drew, and refuse to emit a candidate. An adapter trained on nothing would be
    indistinguishable, to the promotion gate, from one that learned something.
    """
    night = _night(tmp_path, answers={})

    assert night.dataset.examples == (), (
        "WHY THIS IS A FAILURE: a base that answered every prompt with prose produced training "
        f"examples: {night.dataset.examples!r}. Nothing it wrote contained a diff, so nothing "
        "reached the verifier, so nothing is trainable"
    )
    assert night.checkpoint is None, (
        "WHY THIS IS A FAILURE: a night that selected no verified rollout emitted a candidate"
    )
    assert "nothing to train on" in night.checkpoint_absent, (
        "WHY THIS IS A FAILURE: the night wrote no candidate and does not say why. A silent "
        f"absence reads as an oversight rather than a result. Got {night.checkpoint_absent!r}"
    )
    recorded = run_ledger.read(night.ledger)
    assert recorded["checkpoint"]["digest"] is None and recorded["checkpoint"]["absent"], (
        "WHY THIS IS A FAILURE: the ledger does not record the empty outcome, so a reader of the "
        f"evidence alone cannot tell a zero-yield night from an interrupted one. Got "
        f"{recorded['checkpoint']!r}"
    )
    assert night.status is not Status.PASS, (
        "WHY THIS IS A FAILURE: a night that solved nothing reduced to PASS. UNVERIFIED is never "
        "a win and neither is a night with no candidate"
    )


def test_the_ledger_records_every_pinned_input(tmp_path: Path) -> None:
    """P2 exit criterion 4: seeds, model revision, task set, tool versions — all four, present.

    Read back through the ledger's own reader, so the schema check is exercised on the way in.
    The seeds assertion checks the **derivation** rather than merely the presence of a list: a
    seed map that recorded the same value for every draw would satisfy "the ledger records
    seeds" and would make the determinism criterion meaningless.
    """
    night = _night(tmp_path)
    recorded = run_ledger.read(night.ledger)

    assert recorded["run_seed"] == SEED and recorded["draws"] == DRAWS, recorded
    assert recorded["model"]["revision"], (
        "WHY THIS IS A FAILURE: the ledger names no model revision. It is one of the five pinned "
        "inputs, and a checkpoint whose base cannot be identified cannot be compared to anything"
    )
    assert recorded["task_set"]["private"] == 1 and recorded["task_set"]["public"] == 1, recorded
    assert set(recorded["tool_versions"]) >= {"python", "whetstonehq", "mlx-lm", "platform"}, (
        "WHY THIS IS A FAILURE: the ledger omits a tool version. A figure is only interpretable "
        f"against the versions that produced it. Got {recorded['tool_versions']!r}"
    )

    seeds = recorded["seeds"]
    assert seeds, "WHY THIS IS A FAILURE: no seed was recorded, so the seed map is vacuous"
    assert len({one["seed"] for one in seeds}) == len(seeds), (
        "WHY THIS IS A FAILURE: two draws recorded the same seed. Then k draws of a task are k "
        f"copies of one answer and rejection sampling selects nothing. Got {seeds!r}"
    )
    assert {one["attempt"] for one in seeds} == set(range(1, DRAWS + 1)), (
        f"WHY THIS IS A FAILURE: the recorded attempts are not 1..{DRAWS}. The draw index IS the "
        f"attempt index, and a reader recomputes a seed from it. Got {seeds!r}"
    )


def test_a_probe_night_draws_a_declared_sample_and_writes_no_candidate(tmp_path: Path) -> None:
    """`--probe N` validates the chain cheaply and must not produce a candidate from a sample.

    The same argument the bake-off's D7 probe makes one layer down: a probe that emitted the
    thing the operator is deciding whether to commit to has answered the question by doing the
    work the question was about — here, by training a checkpoint on a self-chosen subset.
    """
    night = _night(tmp_path, probe=1)

    assert night.checkpoint is None and "--probe" in night.checkpoint_absent, (
        "WHY THIS IS A FAILURE: a probe night emitted a candidate. Its dataset is drawn from the "
        f"first N tasks of the private source, chosen by the operator. Got "
        f"{night.checkpoint_absent!r}"
    )
    assert run_ledger.read(night.ledger)["task_set"]["probe"] == 1, (
        "WHY THIS IS A FAILURE: the ledger does not record that this was a probe, so its counts "
        "read as a full night's"
    )


def test_the_disclosure_never_prints_a_training_set_size_alone(tmp_path: Path) -> None:
    """`docs/ROADMAP.md:430-435`: coverage and the unverified rate, from the first run onward.

    The training-set size is the flattering half of the measurement — it grows with the number of
    draws and says nothing about how much of the task set was actually graded. So the line that
    carries it must carry the denominator and the unverified count too, and this asserts that
    they travel together rather than being available somewhere else in the file.
    """
    from whetstone.loop.night import disclosure

    night = _night(tmp_path)
    headline = disclosure(night)[0]

    assert "unverified" in headline and "coverage" in headline, (
        "WHY THIS IS A FAILURE: the night's headline reports a training-set size without the "
        f"unverified count and coverage beside it. Got {headline!r}"
    )
    assert str(night.dataset.denominator) in headline, (
        f"WHY THIS IS A FAILURE: the headline quotes no denominator. Got {headline!r}"
    )


def test_a_second_candidate_is_refused_rather_than_resolved(tmp_path: Path) -> None:
    """A night trains one candidate; two would produce a checkpoint whose base nobody can name."""
    from whetstone.loop.night import ManyCandidates

    with pytest.raises(ManyCandidates) as refused:
        _night(
            tmp_path,
            weights=weights(
                tmp_path / "two-candidates",
                "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit",
                "mlx-community/Qwen2.5-Coder-3B-Instruct-4bit",
            ),
        )
    assert "--only" in str(refused.value), refused.value
