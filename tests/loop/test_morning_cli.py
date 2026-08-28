"""The door: `whetstone report --last-night`, its flag surface, and its exits.

`docs/ROADMAP.md:663` names the command, and naming it is what makes this file necessary: adding
it turns the partition guard's three documented edges into four. That guard is the reason
`whetstone verify` — the reward's own entry point — never loads an inference library, so the
edge is asserted rather than described, and the constant it lives in is checked in a file of its
own (`tests/test_reward_path_scope_is_partitioned.py`).

The codes are the CLI's existing four-code contract (`cli.py:64-84`), no fifth: rendered → 0, a
`--verify` mismatch → 1 (a report that does not match its evidence is a failure, not a mistyped
command), and a refusal an operator can fix by retyping → 2. There is no `UNVERIFIED` exit — the
command reads documents and renders, so it either answers or refuses. That is `check-leakage`'s
own argument (`cli.py:828-832`) and it applies here for the same reason.

No model, no `mlx`, no network: the fixtures are JSON documents on disk.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loop.test_morning_render import NIGHT_DIGEST, _night, _record
from whetstone import cli
from whetstone.loop import morning


def _tree(root: Path) -> tuple[Path, Path]:
    """A runs root holding one night and the gate's own promotions directory beside it.

    The real layout: `runs/<id>/` for nights and `runs/promotions/<id>.json` for records. The
    report is written **outside** the runs root, because every directory in there that is not
    `promotions/` must be a night — a scan that shrugged at a stray directory would be the same
    scan that shrugs at a night whose ledger went missing.
    """
    runs = root / "runs"
    runs.mkdir(exist_ok=True)
    _night(runs, run_id="night-001")
    record = _record(runs)
    assert record.candidate_digest == NIGHT_DIGEST
    return (runs, runs / "promotions" / "gate-001.json")


def test_last_night_renders_and_exits_zero(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    runs, record = _tree(tmp_path)
    out = tmp_path / "home"
    code = cli.main(
        ["report", "--last-night", "--runs", str(runs), "--record", str(record), "--out", str(out)]
    )
    assert code == 0
    assert (out / "report.md").is_file() and (out / "report.json").is_file()
    printed = capsys.readouterr().out
    assert "report.md" in printed, printed


def test_a_named_run_renders(tmp_path: Path) -> None:
    runs, _ = _tree(tmp_path)
    out = tmp_path / "home"
    assert cli.main(["report", "--run", str(runs / "night-001"), "--out", str(out)]) == 0
    assert (out / "report.md").is_file()


def test_a_night_without_a_gate_renders(tmp_path: Path) -> None:
    """`--record` is optional: not every night is followed by a gated evaluation."""
    runs, _ = _tree(tmp_path)
    out = tmp_path / "home"
    assert cli.main(["report", "--last-night", "--runs", str(runs), "--out", str(out)]) == 0
    assert "no gated evaluation" in (out / "report.md").read_text(encoding="utf-8").lower()


def test_naming_both_selectors_is_a_usage_error(tmp_path: Path) -> None:
    runs, _ = _tree(tmp_path)
    code = cli.main(
        [
            "report",
            "--last-night",
            "--run",
            str(runs / "night-001"),
            "--out",
            str(tmp_path / "home"),
        ]
    )
    assert code == cli.USAGE_ERROR


def test_naming_neither_selector_is_a_usage_error(tmp_path: Path) -> None:
    assert cli.main(["report", "--out", str(tmp_path / "home")]) == cli.USAGE_ERROR


@pytest.mark.parametrize(
    "case",
    ["no-runs", "ambiguous", "corrupt", "wrong-record", "published-out"],
)
def test_every_refusal_exits_two_and_names_itself(
    tmp_path: Path, capsys: pytest.CaptureFixture, case: str
) -> None:
    """Each named refusal reaches the operator as a message, never as a traceback.

    Parameterised over the refusal classes rather than spot-checked, so a refusal added later that
    escapes the handler fails here instead of printing a stack trace at somebody at 7am.
    """
    runs = tmp_path / "runs"
    runs.mkdir()
    out = tmp_path / "home"
    argv = ["report", "--last-night", "--runs", str(runs), "--out", str(out)]

    if case == "ambiguous":
        _night(runs, run_id="night-a")
        _night(runs, run_id="night-b")
    elif case == "corrupt":
        _night(runs, run_id="night-a")
        (runs / "night-b").mkdir()
    elif case == "wrong-record":
        _night(runs, run_id="night-a")
        record = _record(tmp_path, candidate_digest="f" * 64)
        argv += ["--record", str(tmp_path / "promotions" / "gate-001.json")]
        assert record.candidate_digest != NIGHT_DIGEST
    elif case == "published-out":
        _night(runs, run_id="night-a")
        argv[-1] = str(tmp_path / "reports" / "nightly")

    assert cli.main(argv) == cli.USAGE_ERROR, case
    printed = capsys.readouterr().err
    assert "whetstone report:" in printed, printed
    assert "Traceback" not in printed, printed


def test_verify_exits_zero_on_an_untouched_report(tmp_path: Path) -> None:
    runs, record = _tree(tmp_path)
    out = tmp_path / "home"
    cli.main(
        ["report", "--last-night", "--runs", str(runs), "--record", str(record), "--out", str(out)]
    )
    assert (
        cli.main(
            [
                "report",
                "--verify",
                str(out),
                "--last-night",
                "--runs",
                str(runs),
                "--record",
                str(record),
            ]
        )
        == 0
    )


def test_verify_exits_one_on_an_edited_report(tmp_path: Path) -> None:
    """A report that does not match its evidence is a **failure**, not a usage error.

    The distinction is the four-code contract's whole point: exit 2 means "you typed something
    wrong and can retype it", and this is not that. Something on disk disagrees with the evidence,
    and the operator needs to know which of the two moved.
    """
    runs, record = _tree(tmp_path)
    out = tmp_path / "home"
    cli.main(
        ["report", "--last-night", "--runs", str(runs), "--record", str(record), "--out", str(out)]
    )
    edited = out / "report.md"
    edited.write_text(edited.read_text(encoding="utf-8") + "\n<!-- tampered -->\n")

    assert (
        cli.main(
            [
                "report",
                "--verify",
                str(out),
                "--last-night",
                "--runs",
                str(runs),
                "--record",
                str(record),
            ]
        )
        == cli.FAIL_EXIT
    )


def test_the_door_offers_no_flag_that_narrows_the_evidence() -> None:
    """There is no way to make a morning report say something nicer from the command line.

    The night's counts come from its ledger and the gate's from its record. A flag that dropped a
    source, filtered a task set or suppressed the unverified count would let the page be tuned
    after the fact, which is the one thing a report meant as proof must not allow.
    """
    parser = cli.build_parser()
    report = next(
        action
        for action in parser._subparsers._group_actions[0].choices.items()  # type: ignore[union-attr]
        if action[0] == "report"
    )[1]
    flags = {
        option for action in report._actions for option in action.option_strings
    }
    assert flags == {
        "-h",
        "--help",
        "--last-night",
        "--run",
        "--runs",
        "--record",
        "--out",
        "--verify",
    }, f"the door's flag surface changed: {sorted(flags)}"


def test_the_command_is_listed_in_help() -> None:
    parser = cli.build_parser()
    assert "report" in parser.format_help()


def test_the_module_docstring_names_every_subcommand_that_exists() -> None:
    """The docstring cannot go stale again the way it just did.

    Before this unit, `cli.py`'s module docstring said *"four now do"*, enumerated four commands,
    omitted `check-leakage` entirely, and closed with *"There is still no report, so there is
    still no stub for it"* — three claims, all false, in the file's own first paragraph. Asserted
    against the parser rather than proof-read, because proof-reading is what produced that.
    """
    parser = cli.build_parser()
    names = set(parser._subparsers._group_actions[0].choices)  # type: ignore[union-attr]
    docstring = cli.__doc__ or ""
    # `f"``{name}"` rather than a closed span: the night's subcommand is spelled ``run --night``
    # in the prose, which is how an operator actually types it.
    missing = sorted(name for name in names if f"``{name}" not in docstring)
    assert not missing, (
        f"WHY THIS IS A FAILURE: cli.py's module docstring does not mention {missing}, which the "
        "parser defines. A front-door docstring that under-reports the commands is how a reader "
        "learns the wrong thing first"
    )
    assert "there is still no report" not in docstring.lower(), (
        "WHY THIS IS A FAILURE: the docstring still says there is no report command. There is: "
        "this unit added it"
    )


def test_the_refusal_names_are_the_loops_own(tmp_path: Path) -> None:
    """The handler catches the module's own refusals by identity, never a bare `ValueError`."""
    assert morning.NoRuns in morning.REFUSALS
    assert morning.AmbiguousNight in morning.REFUSALS
    assert morning.RecordNotThisNight in morning.REFUSALS
    assert morning.LedgerUnreadable in morning.REFUSALS
    assert morning.TranscriptNotPrivate in morning.REFUSALS
