"""The leakage proof: a night's training set and the held-out membership must be disjoint.

The night already *excludes* the held-out ids at the partition seam, before the contract is
frozen. That is a behaviour, and `docs/ROADMAP.md:449-450` asks for a **proof**: `uv run
whetstone check-leakage` exits 0 iff the two sets do not touch. The distinction is the whole
point of this aspect — an exclusion nobody checks is a claim, and the one claim this project
cannot afford to make on trust is that its headline was not measured on its training data.

Two properties carry the honesty here, and both are asserted rather than described:

- **An overlap is named, never counted.** A leak reported as "1 task overlaps" tells an
  operator that something is wrong and nothing about what; a leak reported by id tells them
  which task to look at and which night produced it. The assertions below are on the ids, so
  a report that counted without naming would fail them.
- **Both sources are reported together** (`PREREGISTRATION.md:142-147`), each over its own
  denominator (`:157`). The held-out membership is source B's, so source A's overlap is
  expected to be empty — and it is *measured* empty rather than assumed, because "it cannot
  happen" is the kind of assumption that stops being true quietly.

No model, no `mlx`, no network. The inputs are two id sets and a run directory.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loop.test_gate import _MEMBERS, _heldout_document
from whetstone.bakeoff.scoring import Outcome
from whetstone.loop import check_leakage, dataset, heldout, night
from whetstone.loop import ledger as run_ledger
from whetstone.verify.verdict import Status

#: A held-out membership, in the shape aspect 1's document declares it.
_HELDOUT = ("t-01", "t-02", "t-03")


def _training(
    private: tuple[str, ...] = (), public: tuple[str, ...] = ()
) -> dict[str, tuple[str, ...]]:
    """One training set as the check reads it: task ids per source, duplicates kept.

    Duplicates are kept because they are real: a night draws `K` attempts per task and every
    verified win becomes its own example, so the same task can appear several times. The
    denominator is examples, not tasks, and collapsing them here would make the reported
    count disagree with the dataset document it came from.
    """
    return {night.PRIVATE: private, night.PUBLIC: public}


def test_a_disjoint_training_set_is_clean() -> None:
    """The ordinary case: nothing the night trained on is held out."""
    report = check_leakage.check_overlap(_training(private=("t-07", "t-08")), _HELDOUT)

    assert report.clean is True
    assert report.overlap == ()
    assert report.leaked_examples == 0
    assert report.examples == 2
    assert report.heldout_count == len(_HELDOUT)


def test_an_overlap_names_the_id_it_found() -> None:
    """A leak is a named violation, and the assertion is on the id rather than on a count.

    The credulity this guards against is not carelessness but convenience: a boolean or a
    count is easier to render and reads as a finding, and it is the shape a later
    "just tell me if it's clean" would reach for. An operator holding a nonzero exit needs to
    know *which* task leaked, because the fix is in the night that produced it.
    """
    report = check_leakage.check_overlap(_training(private=("t-07", "t-02")), _HELDOUT)

    assert report.clean is False
    assert report.overlap == ("t-02",), (
        "WHY THIS IS A FAILURE: the check did not name the leaked id. A leak reported as a "
        "count tells an operator that something is wrong and nothing about what — and the "
        "fix for a leak is in the night that produced it, which the id is how you find"
    )
    assert report.leaked_examples == 1
    assert report.examples == 2


def test_every_leaked_id_is_named_and_the_examples_are_counted_separately() -> None:
    """Ids are distinct and sorted; the example count is the denominator's own unit.

    A task drawn `K` times contributes several examples and one id. Reporting the two as one
    number would either understate the leak (one id, three examples trained on) or invent a
    task that is not there.
    """
    report = check_leakage.check_overlap(
        _training(private=("t-03", "t-02", "t-02", "t-09")), _HELDOUT
    )

    assert report.overlap == ("t-02", "t-03")
    assert report.leaked_examples == 3
    assert report.examples == 4


def test_both_sources_are_reported_over_their_own_denominators() -> None:
    """Source A is measured beside source B, never assumed away.

    The membership is source B's, so source A's overlap should be empty — and it is checked
    rather than asserted, because a public task id colliding with a held-out one would be a
    finding about the corpus, and "that cannot happen" is how a finding goes unnoticed.
    """
    report = check_leakage.check_overlap(
        _training(private=("t-02", "t-09"), public=("pallets__flask-4045",)), _HELDOUT
    )

    assert report.private.source == night.PRIVATE
    assert report.private.examples == 2 and report.private.overlap == ("t-02",)
    assert report.public.source == night.PUBLIC
    assert report.public.examples == 1 and report.public.overlap == ()
    assert report.examples == 3


def test_a_public_collision_is_a_finding_not_an_impossibility() -> None:
    """If a public training example ever names a held-out id, the check says so."""
    report = check_leakage.check_overlap(_training(public=("t-01",)), _HELDOUT)

    assert report.clean is False
    assert report.public.overlap == ("t-01",)
    assert report.overlap == ("t-01",)


def test_an_empty_training_set_is_disjoint_by_truth() -> None:
    """A zero-strict-PASS night trained on nothing, which is not a leak and not a refusal.

    It is worth its own test because the two ways of getting `clean` — nothing overlapped and
    nothing existed — are different facts about the night, and the disclosure must not let
    them read identically.
    """
    report = check_leakage.check_overlap(_training(), _HELDOUT)

    assert report.clean is True
    assert report.examples == 0
    assert any("no training examples" in line for line in check_leakage.disclosure(report)), (
        "WHY THIS IS A FAILURE: an empty training set discloses as an ordinary clean result. "
        "A night that trained on nothing is trivially disjoint, and a reader must be able to "
        "tell that from a night whose training set was checked and found clean"
    )


def test_the_disclosure_carries_the_count_over_its_denominator() -> None:
    """Every rate carries its denominator (`PREREGISTRATION.md:157`) — here, examples."""
    report = check_leakage.check_overlap(_training(private=("t-02", "t-09")), _HELDOUT)
    lines = check_leakage.disclosure(report)

    assert any("1 of 2 training examples" in line for line in lines), lines
    assert not any("%" in line or "percent" in line for line in lines), (
        "WHY THIS IS A FAILURE: the disclosure states a proportion. This repository reports "
        "counts over their denominators and never a rate on its own"
    )


def test_an_unrecognised_source_is_refused_by_name() -> None:
    """A training set the check cannot split by source is refused, never half-read.

    Both sources are always published together, so a document carrying a third source name is
    one this check cannot report honestly: it would either drop those examples from the
    denominator or file them under a source they are not.
    """
    import pytest

    with pytest.raises(check_leakage.UnknownSource) as refusal:
        check_leakage.check_overlap({"source-c": ("t-09",)}, _HELDOUT)

    assert "source-c" in str(refusal.value)
    assert night.PRIVATE in str(refusal.value) and night.PUBLIC in str(refusal.value)


# --------------------------------------------------------------------------------------------
# The run reader: what it identifies, what it refuses, and what it refuses to guess.
# --------------------------------------------------------------------------------------------


def _run(
    root: Path,
    *,
    private: tuple[str, ...] = (),
    public: tuple[str, ...] = (),
    ledger: bool = True,
    dataset_text: str | None = None,
) -> Path:
    """A night-shaped run directory: a ledger to identify it and a dataset to read.

    The ledger is written as the minimum `ledger.read` accepts, deliberately. This check
    **identifies** a run by its ledger and reads its training set from the dataset document;
    it never reads the ledger's contents, and a fixture that built a whole `Ledger` would
    suggest otherwise. The dataset goes through the real `write_document`, because that half
    *is* read field by field and a hand-written fixture could drift from the writer.
    """
    root.mkdir(parents=True, exist_ok=True)
    if ledger:
        (root / run_ledger.LEDGER_FILE).write_text(
            json.dumps({"schema": run_ledger.LEDGER_SCHEMA}), encoding="utf-8"
        )
    if dataset_text is not None:
        (root / night.DATASET_FILE).write_text(dataset_text, encoding="utf-8")
        return root
    examples = tuple(
        _example(task_id, source)
        for source, ids in ((night.PRIVATE, private), (night.PUBLIC, public))
        for task_id in ids
    )
    document = dataset.Dataset(
        examples=examples, digest="d" * 64, denominator=len(examples), unverified=0
    )
    dataset.write_document(root / night.DATASET_FILE, document)
    return root


def _example(task_id: str, source: str) -> dataset.Example:
    """One training record in the shape the night writes it — hashes and verdicts only."""
    return dataset.Example(
        task_id=task_id,
        source=source,
        attempt=1,
        seed=1,
        prompt_sha256="a" * 64,
        completion_sha256="b" * 64,
        strict=Status.PASS,
        outcome=Outcome.SOLVED,
        control=Status.PASS,
    )


def test_a_disjoint_run_reads_clean_end_to_end(tmp_path: Path) -> None:
    """AC1: a real dataset document and a real held-out document, compared.

    `t-11` is the fixture corpus's survivor — the one private id the membership does not hold
    out — and it appears twice, because a night draws `K` attempts per task and two verified
    wins on one task are two examples. The denominator counts them both.
    """
    run = _run(tmp_path / "runs" / "night-1", private=("t-11", "t-11"), public=("pub-1",))
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    report = check_leakage.run_check(run, document)

    assert report.clean is True
    assert report.examples == 3
    assert report.heldout_count == len(_MEMBERS)


def test_a_leaked_run_names_the_task_and_the_regression_it_is_evidence_of(
    tmp_path: Path,
) -> None:
    """AC2: the id is named, and the disclosure says what the operator should fix.

    A nonzero exit here is not a fact about the gate; it is evidence that the night's
    partition seam regressed. The disclosure says so, because the wrong response — dropping
    the leaked examples after the fact and re-running the check — would leave the defect in
    place and produce a clean result.
    """
    run = _run(tmp_path / "runs" / "night-1", private=(_MEMBERS[0], "t-11"))
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    report = check_leakage.run_check(run, document)
    lines = check_leakage.disclosure(report)

    assert report.clean is False
    assert report.overlap == (_MEMBERS[0],)
    assert any(_MEMBERS[0] in line for line in lines), lines
    assert any("partition seam" in line for line in lines), (
        "WHY THIS IS A FAILURE: the disclosure reports a leak without naming what it is "
        "evidence of. The fix is in the night that produced this run — excluding these "
        "examples after the fact would leave the defect in place and print a clean result"
    )


def test_a_directory_without_a_ledger_is_not_a_run(tmp_path: Path) -> None:
    """AC3: refused by name — a leakage proof over an unidentified training set proves nothing."""
    run = _run(tmp_path / "loose", private=("t-07",), ledger=False)
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    with pytest.raises(check_leakage.NotARun) as refusal:
        check_leakage.run_check(run, document)
    assert run_ledger.LEDGER_FILE in str(refusal.value)


def test_a_dataset_that_does_not_declare_the_schema_is_refused(tmp_path: Path) -> None:
    """AC3: an unreadable training set is refused, never treated as empty.

    The two would exit identically — an empty training set is clean — and they are opposite
    facts: one night trained on nothing, the other cannot be checked at all.
    """
    run = _run(tmp_path / "runs" / "night-1", dataset_text=json.dumps({"examples": []}))
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    with pytest.raises(check_leakage.DatasetUnreadable) as refusal:
        check_leakage.run_check(run, document)
    assert dataset.DATASET_SCHEMA in str(refusal.value)


def test_a_dataset_missing_its_examples_list_is_refused(tmp_path: Path) -> None:
    """A document declaring the schema and carrying no examples list is refused, not defaulted."""
    run = _run(
        tmp_path / "runs" / "night-1",
        dataset_text=json.dumps({"schema": dataset.DATASET_SCHEMA}),
    )
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    with pytest.raises(check_leakage.DatasetUnreadable):
        check_leakage.run_check(run, document)


def test_a_doctored_held_out_document_refuses_before_any_comparison(tmp_path: Path) -> None:
    """AC3: aspect 1's loader by identity — a hand-edited membership never reaches the check.

    The doctored document swaps the leaked id out of the membership and does not regenerate
    the digest — the edit someone would make to turn a failing check green. The count is kept
    at the floor deliberately, so the refusal that fires is the digest's and not the floor's:
    a check that read this document and reported "clean" would be worse than no check,
    because it would attest to the disjointness of a set nobody wrote down.
    """
    run = _run(tmp_path / "runs" / "night-1", private=(_MEMBERS[0],))
    document = _heldout_document(tmp_path / "doc", _MEMBERS)
    raw = json.loads(document.read_text(encoding="utf-8"))
    raw["membership"] = ["t-11" if one == _MEMBERS[0] else one for one in raw["membership"]]
    document.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(heldout.HeldoutDigestMismatch):
        check_leakage.run_check(run, document)


def test_a_night_that_trained_on_nothing_is_clean_and_says_so(tmp_path: Path) -> None:
    """AC4: a zero-strict-PASS night is disjoint by truth, and the disclosure distinguishes it."""
    run = _run(tmp_path / "runs" / "night-1")
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    report = check_leakage.run_check(run, document)

    assert report.clean is True and report.examples == 0
    assert any("disjoint by truth" in line for line in check_leakage.disclosure(report))


def test_a_dataset_naming_a_third_source_is_refused(tmp_path: Path) -> None:
    """A source this check cannot report over is refused, never filed under one of the two."""
    payload = {
        "schema": dataset.DATASET_SCHEMA,
        "digest": "d" * 64,
        "denominator": 1,
        "unverified": 0,
        "coverage": 1,
        "examples": [{"task_id": "t-07", "source": "source-c"}],
    }
    run = _run(tmp_path / "runs" / "night-1", dataset_text=json.dumps(payload))
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    with pytest.raises(check_leakage.UnknownSource) as refusal:
        check_leakage.run_check(run, document)
    assert "source-c" in str(refusal.value)


@pytest.mark.parametrize(
    "relative",
    ["src/whetstone/loop/check_leakage.py", "tests/loop/test_check_leakage.py"],
)
def test_the_leakage_path_imports_no_inference_library(relative: str) -> None:
    """The proof compares two id sets. It must cost nothing and load no weights.

    The test file is walked too: a fixture that generated its own training set would make the
    module's guarantee untestable, since the guard would pass while the path that exercises
    it did the very thing the guard forbids.
    """
    from bakeoff.test_comparison import FORBIDDEN_IMPORT_ROOTS, _imported_roots

    path = Path(__file__).resolve().parents[2] / relative
    roots = _imported_roots(path.read_bytes())

    assert not roots & FORBIDDEN_IMPORT_ROOTS, (
        f"{relative} imports {sorted(roots & FORBIDDEN_IMPORT_ROOTS)}.\n\n"
        "WHY THIS IS A FAILURE: the leakage proof reads two JSON documents and compares two "
        "id sets. An inference import here means the exit criterion needs a GPU to check."
    )
    assert roots, (
        f"{relative} contains no import at all, so the assertion above holds for a file "
        "nothing was checked against (`CONTRIBUTING.md:60`)."
    )
