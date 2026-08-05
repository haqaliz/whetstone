"""Wiring the transcript into a real run: where it is composed, and where it must not be written.

`RecordingGenerator` is correct in isolation (`test_recording_generator.py`). What is asserted here
is the part that only exists in `run.conduct` — the two decisions a wrapper cannot make about
itself.

**Where it sits in the composition.** The recorder is the *outermost* wrapper, outside `Sealed`, so
that it observes every prompt the run tries to ask. That position is what makes the refusal
interesting: a prompt whose digest the frozen contract does not carry reaches the recorder first,
and `Sealed` refuses it one layer down. A refusal is not a generation, and a row written for one
would put a completion-less record — or worse, a record filed under a task nobody asked — into a
file whose entire purpose is completions. An offline replay counting rows would then report a
rollout that never happened, in a run that was voided.

**Where the file goes.** `--out` is the published directory; `reports/baseline/` is what a committed
one looks like. A source-B completion quotes the user's own private donor code back verbatim, so a
transcript written under `--out` is private code staged for publication by a path default. That is
refused as a usage error rather than warned about, because a warning at the top of a night's run is
read by nobody at 3am and the file is already written by the time anyone reads it.

**And the run without one is the run there was before.** `--transcript` is undefaulted for the same
reason `--journal` is, only sharper: the default would not merely resume from something forgotten,
it would write the user's private code somewhere nobody chose.

No model, no `mlx`, no network. The fixtures are `test_run.py`'s own — a real two-commit git donor
per task, real provisioning, a stubbed engine behind an injected factory — imported rather than
copied, because a second fixture set is a second thing to keep in step with the driver and the point
of this file is the wiring rather than the scaffolding.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from bakeoff.test_run import REFUSAL, _run
from whetstone.bakeoff import rendering, scoring
from whetstone.bakeoff.run import ContractChanged, TranscriptNotPrivate, build_parser, main
from whetstone.bakeoff.transcript import Transcript
from whetstone.verify.task import Task

#: The candidate `test_run._run` builds its provenance around. Spelled here because the transcript
#: is keyed on it and an assertion about a key needs the key.
CANDIDATE = "mlx-community/Qwen2.5-Coder-3B-Instruct-4bit"


def test_a_refused_prompt_leaves_no_record_while_the_honest_one_before_it_stays(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The composition property: the recorder observes everything and records only generations.

    The template is moved **after the first task has been scored**, which is the real shape of the
    failure M7b guards — nobody edits a prompt before a run, they edit it once the first numbers
    disappoint. So the run reaches the recorder twice: once with a question the contract froze, and
    once with a question it did not.

    Both halves are asserted together, and that is what stops this test passing for a driver that
    records nothing at all. The first task's record must be **there** — the recorder is wired in and
    working — and the refused task's must be **absent**, because `Sealed` raised before the base was
    asked anything and there is no completion to store. A recorder that wrote the prompt on the way
    in would leave a row for a rollout that never happened, keyed to whatever it guessed.
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
    path = tmp_path / "transcripts" / "arm-a.jsonl"

    with pytest.raises(ContractChanged):
        _run(tmp_path, transcript=path)

    assert len(seen) >= 2, (
        "WHY THIS IS A FAILURE: the run never reached a second task, so the template never moved "
        "mid-run and everything below would hold for a driver that refuses every prompt"
    )
    recorded = Transcript(path=path).replay()
    assert set(recorded) == {(CANDIDATE, seen[0])}, (
        f"WHY THIS IS A FAILURE: the transcript holds {sorted(recorded)!r}. It must hold exactly "
        f"the one task that was actually generated for ({seen[0]!r}) and nothing for {seen[1]!r}, "
        "whose prompt the frozen contract refused. A row for a refused prompt is a rollout an "
        "offline replay would count and attribute a cause to, in a run M7b voided outright"
    )
    assert recorded[(CANDIDATE, seen[0])].completion == REFUSAL, (
        "WHY THIS IS A FAILURE: the surviving record does not carry the text the base produced, so "
        "the recorder is wired in but is not evidence of anything"
    )


def test_a_sound_run_records_every_rollout_under_its_own_key(tmp_path: Path) -> None:
    """The green case: one record per (candidate, task), carrying what the base actually wrote.

    The anti-vacuity control for the refusal above and for the absence below — both of those assert
    that something is *not* on disk, and neither means anything unless this one shows the recorder
    puts things there when a generation happens.
    """
    path = tmp_path / "transcripts" / "arm-a.jsonl"

    conducted = _run(tmp_path, transcript=path)

    assert conducted.report is not None
    recorded = Transcript(path=path).replay()
    assert set(recorded) == {
        (CANDIDATE, "alpha"),
        (CANDIDATE, "beta"),
        (CANDIDATE, "gamma"),
        (CANDIDATE, "pallets__flask-4045"),
    }, (
        f"WHY THIS IS A FAILURE: the transcript holds {sorted(recorded)!r} rather than one record "
        "per (candidate, task) over both sources. A transcript missing rollouts attributes the "
        "run's causes over fewer of them than it ran, and reports that partial breakdown as whole"
    )
    assert {record.completion for record in recorded.values()} == {REFUSAL}, (
        "WHY THIS IS A FAILURE: a stored completion is not the text the stubbed base returned, so "
        "the record is keyed correctly and carries something other than the evidence"
    )
    assert all(
        record.prompt_sha256 in conducted.contract.prompts for record in recorded.values()
    ), (
        "WHY THIS IS A FAILURE: a stored prompt digest is not one the frozen contract carries, so "
        "the record cannot be tied to the run that produced it — which is the one comparison the "
        "digest exists for"
    )


def test_a_run_that_names_no_transcript_writes_none(tmp_path: Path) -> None:
    """No flag, no file, no change: the run without a transcript is the run there was before.

    `--transcript` is undefaulted for the reason `--journal` is, only sharper. A default journal
    would resume from a run somebody had forgotten; a default transcript would write the user's own
    private donor code, verbatim, to a path nobody chose. So the absence is asserted over the whole
    tree the run is allowed to touch, not merely over the path this file happens to use.
    """
    conducted = _run(tmp_path)

    assert conducted.report is not None and conducted.written is not None, (
        "WHY THIS IS A FAILURE: a run naming no transcript did not complete, so adding the flag "
        "changed the behaviour of every invocation that does not use it"
    )
    stray = sorted(str(found) for found in tmp_path.rglob("*.jsonl"))
    assert stray == [], (
        f"WHY THIS IS A FAILURE: a run that asked for no transcript wrote {stray!r}. A completion "
        "quotes the user's private donor code back verbatim, and writing one to a path the "
        "operator did not name is the disclosure this flag is undefaulted to prevent"
    )


def test_a_transcript_under_the_output_directory_is_refused_before_anything_runs(
    tmp_path: Path,
) -> None:
    """`--out` is published; a transcript is private code. The two may not share a directory.

    Refused rather than warned about. `--out` is what `reports/baseline/` is: a committed directory,
    read by outside readers, and the whole reason source B's manifests live in gitignored
    `tasks/local/` while only hashes and verdicts are committed. A transcript written inside it is
    the user's own donor code staged for publication by a path default — and a warning printed at
    the top of a night's run is read by nobody, long after the file exists.

    The refusal must arrive **before** anything runs, which is why the output directory's absence is
    asserted too: a run that got as far as writing a report and then refused would have paid for the
    night and left the operator to work out what, if anything, was sound.
    """
    out = tmp_path / "out"

    with pytest.raises(TranscriptNotPrivate) as refusal:
        _run(tmp_path, out=out, transcript=out / "transcripts" / "arm-a.jsonl")

    message = str(refusal.value)
    assert str(out) in message and "arm-a.jsonl" in message, (
        f"WHY THIS IS A FAILURE: the refusal names neither the output directory nor the transcript "
        f"it was pointed inside. Got {message!r}. An operator cannot fix a path they are not shown"
    )
    assert not out.exists(), (
        "WHY THIS IS A FAILURE: the refusal arrived after the run had begun writing. The check "
        "costs nothing and must happen before the first task is loaded, let alone scored"
    )


def test_the_entry_point_reports_that_refusal_as_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """At the CLI the same refusal is a usage error: a non-zero exit and a message, not a traceback.

    The distinction matters because the operator's next action differs. A traceback reads as a
    harness defect and invites a re-run of the same command; a usage error names the flag that was
    wrong, which is the one thing they can fix.
    """
    out = tmp_path / "out"
    with pytest.raises(SystemExit) as exit_code:
        main(
            [
                "--tasks", str(tmp_path / "corpus"),
                "--public", str(tmp_path / "public"),
                "--pool", str(tmp_path / "pool.json"),
                "--funnel", str(tmp_path / "funnel.json"),
                "--weights", str(tmp_path / "weights"),
                "--out", str(out),
                "--workspace", str(tmp_path / "work"),
                "--timeout", "60",
                "--recorded-on", "2026-08-05",
                "--transcript", str(out / "arm-a.jsonl"),
            ]
        )

    assert exit_code.value.code != 0, (
        "WHY THIS IS A FAILURE: an invocation writing the transcript into the published output "
        "directory exited zero. The operator would read that as an accepted run"
    )
    assert "--transcript" in capsys.readouterr().err, (
        "WHY THIS IS A FAILURE: the usage error does not name the flag that was wrong, so it reads "
        "as a harness crash rather than as something the operator can correct"
    )


def test_the_flag_is_optional_and_undefaulted() -> None:
    """Parsed as `None` when absent — the property the two tests above depend on being true."""
    parsed = build_parser().parse_args(
        [
            "--tasks", "/corpus/donor-b",
            "--public", "/pub",
            "--pool", "/pool.json",
            "--funnel", "/funnel.json",
            "--weights", "/w",
            "--out", "/out",
            "--workspace", "/ws",
            "--timeout", "900",
            "--recorded-on", "2026-08-01",
        ]
    )
    assert parsed.transcript is None, (
        f"WHY THIS IS A FAILURE: --transcript defaulted to {parsed.transcript!r}. A default path "
        "writes the user's own private donor code, verbatim, somewhere they did not choose"
    )
