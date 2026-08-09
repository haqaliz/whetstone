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

import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from fixtures.repos.mined import build_mined_task

from bakeoff.test_diffcheck import COUNT_MISMATCH
from bakeoff.test_run import REFUSAL, _run
from whetstone.bakeoff import rendering, scoring
from whetstone.bakeoff import run as run_module
from whetstone.bakeoff.diffcheck import Trigger
from whetstone.bakeoff.generator import Generator, StubGenerator
from whetstone.bakeoff.rendering import render_prompt
from whetstone.bakeoff.retry import retry_prompt
from whetstone.bakeoff.run import (
    ContractChanged,
    Engine,
    TranscriptNotPrivate,
    build_parser,
    main,
)
from whetstone.bakeoff.sources import oracle_sources
from whetstone.bakeoff.transcript import Transcript
from whetstone.bakeoff.weights import Weights
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
    parsed = build_parser().parse_args(_minimum_cli())
    assert parsed.transcript is None, (
        f"WHY THIS IS A FAILURE: --transcript defaulted to {parsed.transcript!r}. A default path "
        "writes the user's own private donor code, verbatim, somewhere they did not choose"
    )


# --------------------------------------------------------------------------------------------
# The retries switch: the format-hardening arm's flag, off by default, wired through the door.
# --------------------------------------------------------------------------------------------


def _minimum_cli() -> list[str]:
    """The flags the parser requires, so a test about one option is not a test about the others."""
    return [
        "--tasks", "/corpus/donor-a",
        "--public", "/corpus/public",
        "--pool", "/corpus/pool.json",
        "--funnel", "/corpus/funnel.json",
        "--weights", "/weights",
        "--out", "/out",
        "--workspace", "/scratch",
        "--timeout", "900",
        "--recorded-on", "2026-08-05",
    ]


def test_retries_are_off_by_default_so_an_unflagged_rerun_is_the_baseline_contract() -> None:
    """Omitting the flag reproduces the recorded contract rather than inventing a new one.

    `conduct` composes the retry wrapper only when `retries` is on (`run.py:531-535`); the CLI's
    default must be the same off, or a re-run of the baseline arm would silently become the
    hardened one — a contract change nobody flagged.
    """
    parsed = build_parser().parse_args(_minimum_cli())

    assert parsed.retries is False, (
        f"WHY THIS IS A FAILURE: --retries defaulted to {parsed.retries!r}. An unflagged re-run "
        "must be the baseline contract, byte for byte — a retry-capable default would turn "
        "every baseline re-run into the hardened arm without anyone opting in"
    )


def test_the_retries_flag_opt_the_format_hardening_arm_in() -> None:
    """The flag exists and reads as on, so the arm has a door to be run through."""
    parsed = build_parser().parse_args([*_minimum_cli(), "--retries"])

    assert parsed.retries is True, (
        f"WHY THIS IS A FAILURE: --retries parsed as {parsed.retries!r}. The flag is the arm's "
        "switch, and a switch that cannot be switched on leaves the measured arm unrunnable"
    )


class _FakeConducted:
    """What `main` reads off a run: the cost lines and the written report paths."""

    costs: tuple[object, ...] = ()
    written: tuple[str, str] | None = None


def test_main_forwards_the_retries_flag_to_conduct(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--retries` at the door reaches `conduct(retries=True)`, not a dead flag.

    The flag is the arm's switch; a flag the parser accepts but `main` never forwards would
    parse cleanly, run the baseline composition, and print a report that looks like the hardened
    arm's. The forwarding is asserted by recording what `conduct` actually receives.
    """
    seen: dict[str, object] = {}

    def _recording_conduct(**kwargs: object) -> _FakeConducted:
        seen.update(kwargs)
        return _FakeConducted()

    monkeypatch.setattr(run_module, "conduct", _recording_conduct)

    code = main(
        [
            *_minimum_cli(),
            "--retries",
            "--transcript", str(tmp_path / "transcripts" / "arm-a.jsonl"),
        ]
    )

    assert code == 0, code
    assert seen["retries"] is True, (
        f"WHY THIS IS A FAILURE: conduct received retries={seen.get('retries')!r}. A flag the "
        "door swallows is a report that claims the hardened contract while running the baseline "
        "composition"
    )


def test_retries_without_a_transcript_is_forwarded_and_conduct_s_guard_holds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The CLI matches conduct's composition guard: no transcript, no retry wrapper.

    `conduct` refuses nothing for this combination — a retry is never composed without a
    transcript, so `retries=True, transcript=None` is still today's run with the same
    composition (`run.py:531-535`; the run-level shape is pinned by
    `test_retries_are_off_by_default_and_require_a_transcript` below). The CLI must forward
    exactly that pair rather than inventing a transcript or refusing the flag: the guard is
    `conduct`'s, and this test asserts the door does not move it.
    """
    seen: dict[str, object] = {}

    def _recording_conduct(**kwargs: object) -> _FakeConducted:
        seen.update(kwargs)
        return _FakeConducted()

    monkeypatch.setattr(run_module, "conduct", _recording_conduct)

    code = main([*_minimum_cli(), "--retries"])

    assert code == 0, code
    assert seen["retries"] is True, (
        f"WHY THIS IS A FAILURE: conduct received retries={seen.get('retries')!r} for an "
        "invocation that named the flag"
    )
    assert seen["transcript"] is None, (
        f"WHY THIS IS A FAILURE: conduct received transcript={seen.get('transcript')!r} for an "
        "invocation that named none. A transcript the CLI invented would write the user's own "
        "private donor code to a path nobody chose"
    )


def _posed(task: Task) -> str:
    """The exact prompt `score` renders for `task`, oracle sources included."""
    sources = oracle_sources(task, pool=None)
    assert sources.files is not None, sources.reason
    return render_prompt(task, sources.files)


def _triggering_answers(tmp_path: Path) -> dict[str, str]:
    """One stub table answering every posed prompt with a trigger-shaped completion.

    The answers are keyed on the exact prompts the run renders, so they are computed from
    identically-built tasks — built under a private root so they cannot collide with the
    donors `_run` builds in the same `tmp_path` (`_corpus` uses `donor-{task_id}`). The
    prompts match because `render_prompt` is a pure function of the problem statement, the
    failing node ids and the oracle sources' contents, all deterministic from the subject.
    Every first-attempt prompt answers with the count-mismatch shape — a trigger — and the
    retry prompt for that trigger answers the same way, so every task is generated exactly
    `1 + budget` times and the decided record is the last attempt's.
    """
    answers: dict[str, str] = {}
    root = tmp_path / "answer-donors"
    for task_id in ("alpha", "beta", "gamma"):
        task = build_mined_task(
            root / f"donor-{task_id}", task_id=task_id, subject=f"Fix addition ({task_id})"
        ).task
        first = _posed(task)
        answers[first] = COUNT_MISMATCH
        answers[retry_prompt(first, Trigger.HUNK_COUNT_MISMATCH)] = COUNT_MISMATCH
    task = build_mined_task(
        root / "donor-public",
        task_id="pallets__flask-4045",
        subject="Fix addition (pallets__flask-4045)",
    ).task
    first = _posed(task)
    answers[first] = COUNT_MISMATCH
    answers[retry_prompt(first, Trigger.HUNK_COUNT_MISMATCH)] = COUNT_MISMATCH
    return answers


def _engine_from(answers: dict[str, str]) -> Engine:
    """An engine factory serving one stub table, loading nothing and touching no `mlx`."""

    def engine(_: Weights, max_tokens: int = 0) -> Generator:
        assert max_tokens >= 1, max_tokens
        return StubGenerator(answers)

    return engine


def test_a_retry_run_writes_one_record_per_attempt_under_the_same_key(
    tmp_path: Path,
) -> None:
    """Retries wired into the run: three records per key, decided one last and graded.

    With retries enabled, every attempt is a record under the same (candidate, task) key —
    attempts 1..3, decisions retry/retry/graded, each with its own `prompt_sha256` — and
    `replay()` returns the decided one. The prompts frozen by the run cover the retries: a
    retry prompt asked at runtime maps to the task it was posed for, and its digest is in
    the contract.
    """
    answers = _triggering_answers(tmp_path)
    path = tmp_path / "transcripts" / "arm-a.jsonl"

    conducted = _run(tmp_path, retries=True, engine=_engine_from(answers), transcript=path)

    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    per_key: dict[tuple[str, str], list[dict[str, object]]] = {}
    for line in lines:
        per_key.setdefault((line["candidate"], line["task_id"]), []).append(line)
    assert set(per_key) == {
        (CANDIDATE, "alpha"),
        (CANDIDATE, "beta"),
        (CANDIDATE, "gamma"),
        (CANDIDATE, "pallets__flask-4045"),
    }, (
        f"WHY THIS IS A FAILURE: the transcript holds keys {sorted(per_key)!r} rather than "
        "the four (candidate, task) pairs of the run"
    )
    for key, attempts in per_key.items():
        assert len(attempts) == 3, (
            f"WHY THIS IS A FAILURE: {key!r} holds {len(attempts)} records rather than the "
            "3 attempts a budget-2 run over an always-triggering base produces"
        )
        assert [attempt["attempt"] for attempt in attempts] == [1, 2, 3], (
            f"WHY THIS IS A FAILURE: {key!r} numbers its attempts "
            f"{[a['attempt'] for a in attempts]!r} rather than 1, 2, 3"
        )
        assert [attempt["decision"] for attempt in attempts] == ["retry", "retry", "graded"], (
            f"WHY THIS IS A FAILURE: {key!r} declares decisions "
            f"{[a['decision'] for a in attempts]!r} rather than retry/retry/graded"
        )
        assert attempts[-1]["prompt_sha256"] in conducted.contract.prompts, (
            f"WHY THIS IS A FAILURE: {key!r}'s decided record's prompt digest is not one "
            "the frozen contract carries, so the decided attempt cannot be tied to the run"
        )
        assert conducted.contract.posed[attempts[-1]["prompt_sha256"]] == key[1], (
            "WHY THIS IS A FAILURE: the retry prompt maps to a different task than the one "
            "its record is filed under, so one task's attempts are filed under another's key"
        )
    replayed = Transcript(path=path).replay()
    assert all(record.decision == "graded" for record in replayed.values()), (
        "WHY THIS IS A FAILURE: replay does not return exactly the decided records"
    )


def test_retries_are_off_by_default_and_require_a_transcript(tmp_path: Path) -> None:
    """The composition guard: retries only when the driver opts in and a recorder exists.

    `retries` is off until the measured arm opts in, and the wrapper is composed only when
    `--transcript` names a file — the transcript is an operator choice, and a wrapper with
    nothing to write to would silently record nothing. A run with retries on but no
    transcript is therefore still today's run, and writes nothing anywhere.
    """
    conducted = _run(tmp_path, retries=True)

    assert conducted.report is not None and conducted.written is not None, (
        "WHY THIS IS A FAILURE: enabling the retries flag without a transcript changed the "
        "run's outcome, so the flag is not a composition switch"
    )
    stray = sorted(str(found) for found in tmp_path.rglob("*.jsonl"))
    assert stray == [], (
        f"WHY THIS IS A FAILURE: a run that asked for no transcript wrote {stray!r}. A "
        "completion quotes the user's private donor code back verbatim, and writing one to "
        "a path the operator did not name is the disclosure the flag is undefaulted to prevent"
    )
