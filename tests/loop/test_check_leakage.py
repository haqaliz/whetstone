"""The leakage proof: a night's training set and the held-out membership must be disjoint.

The night already *excludes* the held-out ids at the partition seam, before the contract is
frozen. That is a behaviour, and `docs/ROADMAP.md:459-460` asks for a **proof**: `uv run
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
  not compared against it at all (identity matching applies to source B only), and the
  disclosure says "not compared" rather than printing a zero that reads as a measurement.

No model, no `mlx`, no network. The inputs are two id sets and a run directory.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loop.test_gate import _heldout_document as _gate_heldout_document
from whetstone.bakeoff.scoring import Outcome
from whetstone.loop import check_leakage, dataset, heldout, night
from whetstone.loop import ledger as run_ledger
from whetstone.verify.verdict import Status


def _id(n: int, prefix: str = "donor-a") -> str:
    """A private task id as the corpus mints it: a name, then a 12-hex identity.

    Identity is the trailing 12 hex; the prefix is the corpus's own naming and a re-mint can
    change it (`legacy-a-X` became `donor-a-X`). The tests use the prefix to say which side of
    that re-mint an id is on.
    """
    return f"{prefix}-{n:012x}"


#: A held-out membership, in the shape aspect 1's document declares it.
_HELDOUT = (_id(1), _id(2), _id(3))

#: The fixture document's membership (ten ids) and the one corpus task it leaves out.
_MEMBERS = tuple(_id(n) for n in range(1, 11))
_SURVIVOR = _id(11)


def _heldout_document(root: Path, members: tuple[str, ...]) -> Path:
    """A loader-valid held-out document over `members` plus the survivor."""
    return _gate_heldout_document(root, members, corpus_ids=(*members, _SURVIVOR))


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
    report = check_leakage.check_overlap(_training(private=(_id(7), _id(8))), _HELDOUT)

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
    report = check_leakage.check_overlap(_training(private=(_id(7), _id(2))), _HELDOUT)

    assert report.clean is False
    assert report.overlap == (_id(2),), (
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
        _training(private=(_id(3), _id(2), _id(2), _id(9))), _HELDOUT
    )

    assert report.overlap == (_id(2), _id(3))
    assert report.leaked_examples == 3
    assert report.examples == 4


def test_both_sources_are_reported_over_their_own_denominators() -> None:
    """Source A's examples are counted beside source B's, over their own denominator.

    The membership is source B's, so source A is counted but not compared against it; the
    next tests pin that the disclosure says so.
    """
    report = check_leakage.check_overlap(
        _training(private=(_id(2), _id(9)), public=("pallets__flask-4045",)), _HELDOUT
    )

    assert report.private.source == night.PRIVATE
    assert report.private.examples == 2 and report.private.overlap == (_id(2),)
    assert report.public.source == night.PUBLIC
    assert report.public.examples == 1 and report.public.overlap == ()
    assert report.examples == 3


def test_source_a_is_stated_as_not_compared_not_as_measured_clean() -> None:
    """The source A line says it was not compared, and never "0 of N ... touch a held-out task".

    The membership is source B's and public ids carry no identity, so source A's zero is a
    structural constant. Printing it as a count over its denominator would read as a
    measurement nobody made.
    """
    report = check_leakage.check_overlap(
        _training(private=(_id(9),), public=("pallets__flask-4045",)), _HELDOUT
    )
    line = next(one for one in check_leakage.disclosure(report) if "source A (public)" in one)

    assert "not compared" in line and "source B" in line, line
    assert "touch a held-out task" not in line, (
        "WHY THIS IS A FAILURE: the source A line reports a count of examples touching a "
        "held-out task, but source A is never compared against the membership"
    )
    assert "1 training example," in line, line
    assert "1 training examples" not in line, line


def test_the_same_identity_in_the_public_source_is_not_an_overlap() -> None:
    """AC5: the membership is source B's, so a public example is not compared against it.

    CHANGED from "a public collision is a finding": under identity matching the public
    source's ids (`pallets__flask-4045`) carry no 12-hex identity at all, and the membership
    says nothing about them. Comparing them would either refuse every public example or
    invent a match by accident. They are counted as examples and never matched.
    """
    report = check_leakage.check_overlap(
        _training(public=(_id(1, "pallets"),), private=(_id(9),)), _HELDOUT
    )

    assert report.clean is True
    assert report.public.examples == 1 and report.public.overlap == ()
    assert report.private.examples == 1


def test_disjoint_identities_are_clean_whatever_the_prefixes() -> None:
    """AC1: different 12-hex identities do not touch, however alike the names look."""
    report = check_leakage.check_overlap(
        _training(private=(_id(7, "legacy-a"), _id(8, "donor-a"))), _HELDOUT
    )

    assert report.clean is True
    assert report.overlap == ()


def _exact_string_rule(training: tuple[str, ...], membership: tuple[str, ...]) -> tuple[str, ...]:
    """A local copy of the rule `check_overlap` used before: exact string equality."""
    return tuple(sorted({one for one in training if one in set(membership)}))


def test_a_re_minted_id_cannot_hide_a_leak() -> None:
    """AC2, adversarial: `legacy-a-X` trained on, `donor-a-X` held out, is a leak naming both.

    The corpus re-mint renamed ids but kept the trailing identity. The old exact-string rule
    calls this fixture clean, which is pinned here so the test demonstrably fails it.
    """
    trained = _id(5, "legacy-a")
    held = _id(5, "donor-a")
    membership = (_id(1), held, _id(3))

    assert _exact_string_rule((trained,), membership) == (), (
        "the fixture no longer demonstrates the defect: the old rule must call it clean"
    )

    report = check_leakage.check_overlap(_training(private=(trained,)), membership)

    assert report.clean is False
    assert report.leaked_examples == 1
    lines = " ".join(check_leakage.disclosure(report))
    assert trained in lines and held in lines, (
        "WHY THIS IS A FAILURE: the leak did not name both the training id and the held-out "
        "id it matched, and the re-mint is exactly why the two names differ"
    )


def test_a_training_id_without_an_identity_is_refused() -> None:
    """AC3: an id with no trailing 12-hex cannot be matched, so it is refused, never passed."""
    with pytest.raises(check_leakage.UnrecognisedIdentity) as refusal:
        check_leakage.check_overlap(_training(private=("t-07",)), _HELDOUT)

    assert "t-07" in str(refusal.value)
    assert check_leakage.UnrecognisedIdentity in check_leakage.REFUSALS


def test_a_held_out_member_without_an_identity_is_refused() -> None:
    """The same refusal on the other side: a member nothing can be matched against."""
    with pytest.raises(check_leakage.UnrecognisedIdentity) as refusal:
        check_leakage.check_overlap(_training(private=(_id(7),)), (_id(1), "legacy-name"))

    assert "legacy-name" in str(refusal.value)


def test_the_unrecognised_identity_refusal_names_the_cause_and_the_fix() -> None:
    """AC3: the message says why (a re-mint renames ids) and what fixes it (an amendment)."""
    with pytest.raises(check_leakage.UnrecognisedIdentity) as refusal:
        check_leakage.check_overlap(_training(private=("t-07",)), _HELDOUT)

    text = str(refusal.value)
    assert "t-07" in text and "re-mint" in text and "amendment" in text, text


def test_a_clean_disclosure_states_what_it_does_not_rule_out() -> None:
    """The clean verdict is about shared identity only, and says so."""
    report = check_leakage.check_overlap(_training(private=(_id(7),)), _HELDOUT)
    text = " ".join(check_leakage.disclosure(report))

    assert "no shared task identity" in text, text
    assert "no contamination" not in text.lower(), text
    assert "near-duplicate" in text, text


def test_the_verdict_denominator_counts_only_compared_examples() -> None:
    """Source A examples are not compared, so they are not in the verdict's denominator."""
    report = check_leakage.check_overlap(
        _training(private=(_id(2), _id(9)), public=("a-1", "a-2", "a-3")), _HELDOUT
    )
    verdict = check_leakage.disclosure(report)[0]

    assert "1 of 2 training examples" in verdict, verdict
    assert "of 5" not in verdict, verdict


def test_the_counts_are_grammatical_for_one_example() -> None:
    """'1 training example', never '1 training examples', in the verdict and the source line."""
    report = check_leakage.check_overlap(_training(private=(_id(9),)), _HELDOUT)
    text = "\n".join(check_leakage.disclosure(report))

    assert "0 of 1 training example " in text, text
    assert "1 training examples" not in text, text
    many = check_leakage.check_overlap(_training(private=(_id(9), _id(8))), _HELDOUT)
    assert "0 of 2 training examples" in "\n".join(check_leakage.disclosure(many))


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
    report = check_leakage.check_overlap(_training(private=(_id(2), _id(9))), _HELDOUT)
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
        check_leakage.check_overlap({"source-c": (_id(9),)}, _HELDOUT)

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
    run = _run(
        tmp_path / "runs" / "night-1", private=(_id(11), _id(11)), public=("pallets__flask-4045",)
    )
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
    run = _run(tmp_path / "runs" / "night-1", private=(_MEMBERS[0], _id(11)))
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


def test_a_directory_with_neither_dataset_nor_ledger_is_not_a_run(tmp_path: Path) -> None:
    """AC4: nothing identifies the directory as a night's run, so it is refused by name."""
    run = tmp_path / "empty"
    run.mkdir()
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    with pytest.raises(check_leakage.NotARun) as refusal:
        check_leakage.run_check(run, document)
    assert night.DATASET_FILE in str(refusal.value)


def test_a_ledger_without_a_dataset_is_refused_by_a_true_message(tmp_path: Path) -> None:
    """A ledger present and no dataset: refused, and the message may not claim the opposite.

    The refusal names the missing dataset and does not say the run is unidentified, because
    the ledger is right there.
    """
    run = _run(tmp_path / "ledgered", ledger=True, dataset_text=None)
    (run / night.DATASET_FILE).unlink()
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    with pytest.raises(check_leakage.NotARun) as refusal:
        check_leakage.run_check(run, document)
    message = str(refusal.value)
    assert night.DATASET_FILE in message
    assert "nothing identifies" not in message and "not a night-written" not in message, message


def test_a_dataset_without_a_ledger_is_checked_and_says_so(tmp_path: Path) -> None:
    """AC4 / PRD requirement 2: CHANGED from "a ledger-less directory is not a run".

    Night #1 wrote a dataset and then raised before its ledger landed, so the check must
    work on the one document that records what was trained on. It says the ledger was absent
    rather than staying silent, and claims no more than that.
    """
    run = _run(tmp_path / "loose", private=(_SURVIVOR,), ledger=False)
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    report = check_leakage.run_check(run, document)
    lines = check_leakage.disclosure(report)

    assert report.clean is True and report.examples == 1
    notice = [line for line in lines if run_ledger.LEDGER_FILE in line]
    assert len(notice) == 1 and "absent" in notice[0], lines
    assert "not" in notice[0] and "dataset" in notice[0], notice


def test_a_dataset_with_a_ledger_carries_no_notice(tmp_path: Path) -> None:
    """AC6: the existing behaviour is unchanged when the ledger is there."""
    run = _run(tmp_path / "runs" / "night-1", private=(_SURVIVOR,))
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    lines = check_leakage.disclosure(check_leakage.run_check(run, document))

    assert not any(run_ledger.LEDGER_FILE in line for line in lines), lines


def test_a_present_ledger_is_still_validated(tmp_path: Path) -> None:
    """A corrupt ledger refuses; only an absent one is tolerated."""
    run = _run(tmp_path / "runs" / "night-1", private=(_id(7),))
    (run / run_ledger.LEDGER_FILE).write_text("{not json", encoding="utf-8")
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    with pytest.raises(run_ledger.LedgerUnreadable):
        check_leakage.run_check(run, document)


def _night_001(tmp_path: Path) -> tuple[Path, Path]:
    """A night-001-shaped run with no ledger: 4+1+1 private examples under the old names."""
    ids = ("legacy-a-c6e4d4c4de87",) * 4 + ("legacy-a-34daf85182d5", "legacy-b-c3e132b7469b")
    run = _run(tmp_path / "runs" / "night-001", private=ids, ledger=False)
    members = ("donor-a-c6e4d4c4de87", *_MEMBERS[:9])
    corpus = (*members, "donor-a-34daf85182d5", "donor-b-c3e132b7469b")
    return run, _gate_heldout_document(tmp_path / "doc", members, corpus_ids=corpus)


def test_a_night_001_shaped_run_is_leaked_by_identity(tmp_path: Path) -> None:
    """AC6: the old names and the new names share an identity, and the check says so."""
    run, document = _night_001(tmp_path)

    report = check_leakage.run_check(run, document)
    text = " ".join(check_leakage.disclosure(report))

    assert report.clean is False
    assert report.examples == 6 and report.leaked_examples == 4
    assert report.overlap == ("donor-a-c6e4d4c4de87",)
    assert "legacy-a-c6e4d4c4de87" in text and "donor-a-c6e4d4c4de87" in text
    assert "donor-a-34daf85182d5" not in text and "donor-b-c3e132b7469b" not in text


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
    raw["membership"] = [_id(11) if one == _MEMBERS[0] else one for one in raw["membership"]]
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
        "examples": [{"task_id": _id(7), "source": "source-c"}],
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


def test_a_source_a_only_run_is_a_refusal_not_a_verdict() -> None:
    """Amendment 2 (gate-leakage-guard PRD): a comparison that compared nothing is a refusal.

    This test asserted exit-0 semantics ("not checked", report.clean True) until Amendment 2;
    it is updated, not deleted: the same input now raises, so no verdict can be rendered.
    """
    with pytest.raises(check_leakage.NothingCompared) as caught:
        check_leakage.check_overlap(_training(public=("a-1", "a-2")), _HELDOUT)

    assert check_leakage.NothingCompared in check_leakage.REFUSALS
    message = str(caught.value)
    assert "no source B" in message and "nothing was compared" in message, message
    assert "no verdict" in message, message
