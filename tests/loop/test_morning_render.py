"""The morning report itself: what it says, what it refuses to say, and what seals it.

Every other file in this unit is about reading evidence correctly. This one is about the only
thing the operator actually sees, and the failure available here is not a wrong number — the
numbers are all copied from documents that already sealed them. The failure available here is a
**bad night that reads like a blank one**: a section left empty when a night produced nothing, a
`PASS` printed under an evaluation that made no comparison, a training-set size quoted without
the denominator that makes it mean anything.

So the unflattering states are each pinned by name, and the two that could flatter are watched
failing against renderers that get them wrong.

**The record belongs to this night by digest, not by name.** The brief said to compare run ids,
and integration proved that wrong: a promotion record's `run_id` is the *gate evaluation's*
operator-declared id (`gate-001`), never the night's. The link that actually exists is the
checkpoint — a record belongs to this night iff the night's checkpoint digest is one of the two
the gate compared. That is stronger than the name check would have been, because a digest is
evidence and a name is a string somebody typed.

**Sealed, and only as far as the seal reaches.** Re-rendering proves the report matches the
evidence. It does not prove the evidence matches the run: a hand-edited ledger re-renders to a
perfectly consistent report, because a ledger is not self-sealing. The report says so in its own
text, and that sentence is asserted here — a document whose claim to be sealed is larger than
what it can check is the precise failure this project names in everyone else's work.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from loop.test_promotion_record_n import _sides
from loop.test_run_ledger import _ledger
from whetstone.bakeoff import report as bakeoff_report
from whetstone.bakeoff.scoring import Outcome
from whetstone.loop import gate, morning
from whetstone.loop import ledger as run_ledger
from whetstone.loop.gate import Exit, GateDecision, Retryable, RetryOutcome

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The candidate digest the fixture ledger records, so the record and the night agree.
NIGHT_DIGEST = "c" * 64


def _night(
    root: Path,
    *,
    run_id: str = "night-001",
    checkpoint_digest: str | None = NIGHT_DIGEST,
    absent: str = "",
) -> morning.LedgerDocument:
    """A night's ledger on disk, read back through the aspect-1 reader."""
    ledger = replace(
        _ledger(), run_id=run_id, checkpoint_digest=checkpoint_digest, checkpoint_absent=absent
    )
    directory = root / run_id
    directory.mkdir(parents=True, exist_ok=True)
    return morning.read_ledger(run_ledger.write(directory / run_ledger.LEDGER_FILE, ledger))


def _record(
    root: Path,
    *,
    exit_: Exit = Exit.PROMOTED,
    candidate_digest: str = NIGHT_DIGEST,
    detail: str = "the candidate solved more with no regression",
) -> gate.PromotionRecord:
    """A promotion record as the gate's own writer emits it, read back fail-closed."""
    sides = _sides()
    path = gate.write_promotion_record(
        path=root / "promotions" / "gate-001.json",
        run_id="gate-001",
        recorded_on="2026-08-27",
        candidate_digest=candidate_digest,
        incumbent_digest="i" * 64,
        heldout_digest="h" * 64,
        candidate=sides["candidate"],
        incumbent=sides["incumbent"],
        decision=GateDecision(
            exit=exit_,
            denominator=10,
            solved_new=4,
            solved_old=3,
            regressed=0,
            unverified=1 if exit_ is Exit.UNVERIFIED else 0,
            detail=detail,
        ),
        retries=(
            RetryOutcome(
                side="candidate",
                task_id="t-05",
                before=Outcome.UNVERIFIED,
                after=Outcome.SOLVED,
                retries_used=1,
                prompt_sha256="p" * 64,
                completion_sha256="q" * 64,
            ),
        ),
        retryable=(
            Retryable(
                side="incumbent",
                task_id="t-06",
                outcome=Outcome.NO_ORACLE,
                prompt_sha256="",
                completion_sha256="",
            ),
        ),
        retry_count=gate.RETRY_COUNT,
        tool_versions={"python": "3.12"},
    )
    return gate.read_promotion_record(path)


# ---------------------------------------------------------------------------
# The shape of the thing
# ---------------------------------------------------------------------------


def test_a_night_and_a_gate_render_both_artifacts(tmp_path: Path) -> None:
    """The happy path: two artifacts, the declared schema, and no third file."""
    out = tmp_path / "home"
    markdown, payload = morning.write_morning_report(
        out=out, night=_night(tmp_path), record=_record(tmp_path)
    )
    assert markdown.name == "report.md"
    assert payload.name == "report.json"
    assert sorted(one.name for one in out.iterdir()) == ["report.json", "report.md"], (
        "WHY THIS IS A FAILURE: a third artifact appeared. A night produces no cost document, "
        "and an empty cost.json would be an artifact asserting a measurement nobody made"
    )
    assert json.loads(payload.read_text(encoding="utf-8"))["schema"] == "whetstone-morning/1"


def test_the_lede_names_the_night_the_yield_and_the_candidate(tmp_path: Path) -> None:
    """The one sentence a person reads first, pinned.

    Without this the whole unit is satisfied by a JSON dump with a `.md` extension — every other
    assertion here is about correctness, and correctness is not the same as being a report.
    """
    built = morning.build_morning_report(night=_night(tmp_path), record=_record(tmp_path))
    lede = next(
        line
        for line in built.markdown.splitlines()
        if line.strip() and not line.startswith("#")
    )
    assert "night-001" in lede, lede
    assert "2026-08-20" in lede, lede
    assert bakeoff_report._over(1, 61) in lede, (
        f"the lede quotes the kept count without the set it was counted on: {lede}"
    )
    assert "candidate" in lede.lower(), lede


def test_every_count_travels_with_its_denominator(tmp_path: Path) -> None:
    """`PREREGISTRATION.md:157` refuses a bare proportion; this is that rule at the local surface.

    A training-set size on its own grows with the number of draws and says nothing about how much
    of the task set was graded (`dataset.py:169-174`). The size, the coverage and the unverified
    count each appear over the same denominator.
    """
    built = morning.build_morning_report(night=_night(tmp_path), record=_record(tmp_path))
    for count in (1, 54, 7):
        assert bakeoff_report._over(count, 61) in built.markdown, (
            f"{count} is rendered without its denominator:\n{built.markdown}"
        )


def test_the_over_helper_is_reused_by_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """The count-over-denominator idiom is the bake-off's, not a second copy of it.

    Monkeypatched rather than asserted with `is`, because what matters is that the renderer
    *resolves* the helper from the module at call time — a copy taken at import would survive an
    `is` check on the name and ignore the patch.
    """
    monkeypatch.setattr(bakeoff_report, "_over", lambda count, denominator: "SENTINEL")
    rendered = morning._render_counts(examples=1, denominator=61, coverage=54, unverified=7)
    assert "SENTINEL" in rendered, (
        "WHY THIS IS A FAILURE: patching the bake-off's helper did not change what this renderer "
        f"produced, so it holds a copy rather than resolving the shared definition: {rendered!r}"
    )


# ---------------------------------------------------------------------------
# The states that could flatter, each pinned as itself
# ---------------------------------------------------------------------------


def test_a_zero_yield_night_renders_the_reason_verbatim(tmp_path: Path) -> None:
    """A night that kept nothing is a published outcome, not a blank section.

    The ledger already carries the reason (`checkpoint_absent`); the report quotes it rather than
    paraphrasing, because the night wrote the sentence that is true about itself.
    """
    absent = "no rollout reached a strict PASS, so there is nothing to train on"
    night = _night(tmp_path, checkpoint_digest=None, absent=absent)
    built = morning.build_morning_report(night=night, record=None)

    assert absent in built.markdown, built.markdown
    assert "no candidate" in built.markdown.lower(), built.markdown


def test_a_night_with_no_gate_says_so(tmp_path: Path) -> None:
    """Absence of an evaluation is a fact about the night, not an omission from the page."""
    built = morning.build_morning_report(night=_night(tmp_path), record=None)
    assert "no gated evaluation is recorded for this night" in built.markdown.lower(), (
        built.markdown
    )


def test_an_unverified_gate_makes_no_comparison_and_prints_no_pass(tmp_path: Path) -> None:
    """`UNVERIFIED` is never rendered as a win, and never as `PASS`.

    The credulous renderer this is watched against prints the candidate's solved count as though
    it were a result. It is not: when the evaluation reached no verdict, no comparison was made,
    and the counts are evidence about an incomplete run rather than about a candidate.
    """
    built = morning.build_morning_report(
        night=_night(tmp_path),
        record=_record(tmp_path, exit_=Exit.UNVERIFIED, detail="1 of 10 reached no verdict"),
    )
    assert "no comparison was made" in built.markdown, built.markdown
    assert "UNVERIFIED" in built.markdown, built.markdown

    # Scoped to the gate's own section rather than the whole page, and the narrowing is a
    # correction rather than a loosening. The night's `valid_split` legitimately quotes the
    # ledger's own sentence, which contains the words "strict-PASS set below floor" — refusing
    # that would mean paraphrasing a sentence the night wrote about itself. What must not happen
    # is a PASS rendered as this evaluation's verdict, which is what this now asserts.
    gate_section = built.markdown.split("## The gate", 1)[1].split("## How to trust", 1)[0]
    assert "PASS" not in gate_section, (
        "WHY THIS IS A FAILURE: the word PASS appears in the section reporting an evaluation "
        f"that made no comparison. UNVERIFIED is never rendered as PASS:\n{gate_section}"
    )
    assert "promoted" not in gate_section.lower(), gate_section
    assert "rejected" not in gate_section.lower(), gate_section


def test_a_rejected_gate_says_the_incumbent_stands(tmp_path: Path) -> None:
    """Rejection is a result and reads as one — the candidate did not earn the promotion."""
    built = morning.build_morning_report(
        night=_night(tmp_path),
        record=_record(tmp_path, exit_=Exit.REJECTED, detail="no solved gain"),
    )
    assert "rejected" in built.markdown.lower(), built.markdown
    assert "no comparison was made" not in built.markdown, built.markdown


def test_the_three_gate_exits_are_the_gates_own_and_an_unknown_one_is_refused(
    tmp_path: Path,
) -> None:
    """The renderer knows exactly the exits the gate defines, and refuses a fourth.

    If a later gate grows a decision string, printing it beside a headline would be the renderer
    guessing what it means. The enumeration is asserted complete against `gate.Exit` itself, so
    the guess is impossible and the failure lands here.
    """
    assert set(morning.GATE_EXITS) == {one.value for one in Exit}

    record = _record(tmp_path)
    doctored = replace(record, decision={**record.decision, "exit": "annexed"})
    with pytest.raises(morning.UnknownGateExit) as refused:
        morning.build_morning_report(night=_night(tmp_path), record=doctored)
    assert "annexed" in str(refused.value), refused.value


# ---------------------------------------------------------------------------
# The record must belong to this night
# ---------------------------------------------------------------------------


def test_a_record_for_another_night_is_refused_and_nothing_is_written(tmp_path: Path) -> None:
    """The half-truth the previous unit spent an aspect refusing, at this surface.

    Matched on the **checkpoint digest**, not the run id: a promotion record's `run_id` is the
    gate evaluation's own operator-declared name (`gate-001`), so a name check would compare two
    unrelated strings and pass or fail for no reason. The digest is the link that exists.
    """
    out = tmp_path / "home"
    with pytest.raises(morning.RecordNotThisNight) as refused:
        morning.write_morning_report(
            out=out,
            night=_night(tmp_path),
            record=_record(tmp_path, candidate_digest="f" * 64),
        )
    assert NIGHT_DIGEST[:12] in str(refused.value), refused.value
    assert not out.exists(), (
        "WHY THIS IS A FAILURE: a refused render left artifacts behind. A half-written morning "
        "report is worse than none: it is a page an operator will read"
    )


def test_a_record_naming_this_night_as_the_incumbent_is_accepted(tmp_path: Path) -> None:
    """A night's checkpoint is the incumbent in every gate after the one that promoted it.

    The control that stops the digest check being read as "candidate only" — which would refuse
    every morning report written after the second night.
    """
    record = _record(tmp_path, candidate_digest="f" * 64)
    as_incumbent = replace(record, incumbent_digest=NIGHT_DIGEST)
    built = morning.build_morning_report(night=_night(tmp_path), record=as_incumbent)
    assert "incumbent" in built.markdown.lower()


def test_a_night_with_no_checkpoint_cannot_have_a_gate_record(tmp_path: Path) -> None:
    """Nothing was produced, so nothing could have been compared."""
    night = _night(tmp_path, checkpoint_digest=None, absent="no strict PASS")
    with pytest.raises(morning.RecordNotThisNight):
        morning.build_morning_report(night=night, record=_record(tmp_path))


# ---------------------------------------------------------------------------
# Sealed to its evidence — and only that far
# ---------------------------------------------------------------------------


def test_the_report_states_the_boundary_of_its_own_seal(tmp_path: Path) -> None:
    """The sentence that keeps the claim the size of what the code can check.

    `VISION.md:12` promises "a signed proof". There is no signing key in this project and
    `pyproject.toml` declares zero runtime dependencies, so the honest claim is narrower: the
    report is sealed to its evidence, and re-rendering proves it matches that evidence — not that
    the evidence matches the run. A hand-edited ledger re-renders consistently.
    """
    built = morning.build_morning_report(night=_night(tmp_path), record=_record(tmp_path))
    assert "sealed to its evidence" in built.markdown, built.markdown
    assert "not cryptographically signed" in built.markdown, built.markdown
    assert "does not prove the evidence matches the run" in built.markdown, built.markdown


def test_the_word_signed_never_stands_unqualified(tmp_path: Path) -> None:
    """This is the claim most likely to be quoted out of the artifact, so it is pinned.

    Every occurrence of "sign" in the rendered page must sit in the sentence that denies a
    cryptographic signature. A stray "signed morning report" heading would be quoted on its own.
    """
    built = morning.build_morning_report(night=_night(tmp_path), record=_record(tmp_path))
    for line in built.markdown.splitlines():
        if "sign" in line.lower():
            assert "not cryptographically signed" in line, (
                f"WHY THIS IS A FAILURE: a line uses 'signed' outside the sentence that denies a "
                f"cryptographic signature, where it can be quoted alone: {line!r}"
            )


def test_every_figure_names_the_document_it_came_from(tmp_path: Path) -> None:
    """Sealed means each number is traceable to a sealed document, by digest."""
    built = morning.build_morning_report(night=_night(tmp_path), record=_record(tmp_path))
    payload = built.payload
    assert payload["evidence"]["dataset_digest"], payload
    assert payload["evidence"]["checkpoint_digest"] == NIGHT_DIGEST
    assert payload["evidence"]["heldout_digest"] == "h" * 64
    assert payload["evidence"]["ledger_run_id"] == "night-001"


def test_verify_accepts_an_untouched_pair_and_refuses_an_edited_one(tmp_path: Path) -> None:
    """The re-derivation: the artifacts are what this evidence renders to, byte for byte."""
    out = tmp_path / "home"
    night, record = _night(tmp_path), _record(tmp_path)
    markdown, _ = morning.write_morning_report(out=out, night=night, record=record)

    morning.verify_morning_report(out, night=night, record=record)

    markdown.write_text(markdown.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(morning.MorningReportAltered) as refused:
        morning.verify_morning_report(out, night=night, record=record)
    assert "report.md" in str(refused.value), refused.value


def test_verify_names_the_json_when_it_is_the_edited_one(tmp_path: Path) -> None:
    """Which artifact drifted is the whole content of the refusal."""
    out = tmp_path / "home"
    night, record = _night(tmp_path), _record(tmp_path)
    _, payload = morning.write_morning_report(out=out, night=night, record=record)
    payload.write_text(payload.read_text(encoding="utf-8").replace("night-001", "night-002"))
    with pytest.raises(morning.MorningReportAltered) as refused:
        morning.verify_morning_report(out, night=night, record=record)
    assert "report.json" in str(refused.value), refused.value


# ---------------------------------------------------------------------------
# Determinism, purity, locality
# ---------------------------------------------------------------------------


def test_two_renders_are_byte_identical(tmp_path: Path) -> None:
    night, record = _night(tmp_path), _record(tmp_path)
    first = morning.build_morning_report(night=night, record=record)
    second = morning.build_morning_report(night=night, record=record)
    assert first.markdown == second.markdown
    assert json.dumps(first.payload, sort_keys=True) == json.dumps(second.payload, sort_keys=True)


@pytest.mark.parametrize("seed", ["0", "1"])
def test_the_render_is_byte_identical_across_processes(tmp_path: Path, seed: str) -> None:
    """Set iteration over strings is seed-dependent, so this is asserted, not assumed."""
    out = tmp_path / "home"
    night, record = _night(tmp_path), _record(tmp_path)
    markdown, _ = morning.write_morning_report(out=out, night=night, record=record)
    expected = markdown.read_text(encoding="utf-8")

    record_path = tmp_path / "promotions" / "gate-001.json"
    probe = (
        "import sys; from pathlib import Path;"
        "from whetstone.loop import morning, gate;"
        f"night = morning.load_named_run(Path({str(tmp_path / 'night-001')!r}));"
        f"record = gate.read_promotion_record(Path({str(record_path)!r}));"
        "sys.stdout.write(morning.build_morning_report(night=night, record=record).markdown)"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=True,
        env={"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": seed, "HOME": str(tmp_path)},
    )
    assert result.stdout == expected, (
        f"the render differs under PYTHONHASHSEED={seed}; a figure that moves with the hash seed "
        "is not a figure the harness reproduces"
    )


def test_building_a_report_reads_no_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The render is a pure function of two documents — it cannot reach a published home.

    Asserted by making every read fail. A renderer that opened `reports/baseline/report.json` to
    "add context" would restate a figure whose only home is elsewhere, and the one-home discipline
    would be broken by a page nobody thought of as a report.
    """
    night, record = _night(tmp_path), _record(tmp_path)

    def refuse(*args: Any, **kwargs: Any) -> str:
        raise AssertionError("the renderer read a file")

    monkeypatch.setattr(Path, "read_text", refuse)
    monkeypatch.setattr(Path, "read_bytes", refuse)
    morning.build_morning_report(night=night, record=record)


def test_the_report_carries_no_donor_source_text(tmp_path: Path) -> None:
    """The locality canary: counts, digests and verdicts, never contents."""
    out = tmp_path / "home"
    markdown, payload = morning.write_morning_report(
        out=out, night=_night(tmp_path), record=_record(tmp_path)
    )
    for artifact in (markdown, payload):
        text = artifact.read_text(encoding="utf-8")
        assert "SECRET_DONOR_MARKER" not in text, (
            f"WHY THIS IS A FAILURE: donor source text reached {artifact.name}. A morning report "
            "is the artifact most likely to be shared — it exists to be read by a person"
        )
        assert "fix it" not in text, (
            f"WHY THIS IS A FAILURE: a prompt reached {artifact.name}. The prompt quotes the "
            "donor's own files back; that is what the oracle retrieval setting means"
        )


def test_the_report_restates_no_published_figure(tmp_path: Path) -> None:
    """The morning report is not a competing home for any published series' figures.

    It renders one local run's own counts, whose only home is that run's gitignored directory.
    This asserts the rendered page shares no figure-bearing line with a committed report.
    """
    built = morning.build_morning_report(night=_night(tmp_path), record=_record(tmp_path))
    rendered = set(built.markdown.splitlines())
    for published in sorted((REPO_ROOT / "reports").rglob("report.md")):
        if "local" in published.parts:
            continue
        overlap = {
            line
            for line in published.read_text(encoding="utf-8").splitlines()
            if line in rendered and any(char.isdigit() for char in line) and "|" in line
        }
        assert not overlap, (
            f"WHY THIS IS A FAILURE: the morning report shares figure-bearing lines with "
            f"{published.relative_to(REPO_ROOT)}: {sorted(overlap)}"
        )
