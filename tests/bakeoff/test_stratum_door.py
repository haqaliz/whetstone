"""The stratum-report mode of the report door: one arm, one contract, one render.

`--render-stratum-report` is the door's second mode: exactly one `--arm NAME --journal
PATH --contract PATH` group — the probe is one run under one contract — rendered into the
`--out` directory by the shipped writer, by identity. The mode reuses
`build_contract_arms` unchanged, so its refusals (a missing journal, an empty journal, a
run with no `INTACT` control probe) hold by identity; zero or two groups are refused by
name; `--stratum-doc` is required as a pointer, never parsed; and every refusal happens
before anything is written. `--render-report` itself is untouched.

All fixtures are synthetic: toy candidates and task ids, tiny — never donor content.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whetstone.bakeoff import comparison, report
from whetstone.bakeoff.control import Control, Origin, Probe
from whetstone.bakeoff.journal import Journal, Step
from whetstone.bakeoff.scoring import Outcome, Rollout
from whetstone.verify.verdict import Status

#: The committed stratum document the render points at — a pointer, never parsed.
STRATUM_DOC = "tasks/stratum/easier.json"

#: The gitignored breakdown home the render points at (the probe-run runbook's declared home).
BREAKDOWN_HOME = "runs/easier-stratum-arm/"

#: A declared date for the door's render — an input, never the clock.
RECORDED_ON = "2026-08-14"

#: The candidate the larger-base arm scores, named by the runbook's resolution block —
#: a pointer string, never parsed.
LARGER_BASE_CANDIDATE = "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit"

#: The gitignored breakdown home the larger-base render points at.
LARGER_BASE_BREAKDOWN_HOME = "runs/larger-base-arm/"

#: A declared date for the larger-base door's render — an input, never the clock.
LARGER_BASE_RECORDED_ON = "2026-08-15"

#: The hardened contract block: every field explicit, the retry trio carried (`retry_budget` 2).
HARDENED_CONTRACT_BLOCK: dict[str, object] = {
    "pinned": False,
    "prompt_sha256": "b" * 64,
    "sampler": "greedy: argmax over the final logprob axis",
    "max_tokens": 600,
    "extractor_version": "2",
    "dev_subset": ["dev-x"],
    "retry_budget": 2,
    "retry_template_sha256": "d" * 64,
    "diagnosis_vocabulary_version": "e" * 64,
    "retrieval": "oracle",
}


def _step(
    candidate: str,
    task_id: str,
    *,
    outcome: Outcome,
    generation_seconds: float,
    strict: Status | None = None,
    weak: Status | None = None,
    control: Control = Control.INTACT,
) -> Step:
    """One journal step, built through the real `Probe`/`Rollout` constructors."""
    if control is Control.INTACT:
        without_patch: Status | None = Status.FAIL
        with_reference: Status | None = Status.PASS
        detail = ""
    else:
        without_patch, with_reference, detail = Status.PASS, None, "the inert patch did not fail"
    return Step(
        probe=Probe(
            candidate=candidate,
            task_id=task_id,
            control=control,
            without_patch=without_patch,
            with_reference=with_reference,
            origin=Origin.DONOR,
            detail=detail,
            seconds=1.0,
        ),
        rollout=Rollout(
            candidate=candidate,
            task_id=task_id,
            outcome=outcome,
            strict=strict,
            weak=weak,
            verdict_kinds=(),
            executed=None,
            prompt_sha256="0" * 64,
            detail="",
            generation_seconds=generation_seconds,
            strict_seconds=0.0,
            weak_seconds=0.0,
        ),
    )


#: The arm's synthetic journal: 37 rollouts for the larger-base candidate (5 solved) at a
#: named spend. Denominators 37/41 collide with nothing in the six existing artifacts
#: (their own are 1, 62, 63, 64, 189, 299, 300), so the render is disjoint from every
#: committed home by construction. The candidate is the arm's real name — the runbook's
#: resolution block names it and the run's own records carry it.
PROBE_ARM_STEPS: list[Step] = [
    _step(
        "one", f"t-{i:02d}", outcome=Outcome.SOLVED, generation_seconds=9.0,
        strict=Status.PASS, weak=Status.PASS,
    )
    for i in range(5)
] + [
    _step(
        "one", f"t-{i:02d}", outcome=Outcome.NOT_SOLVED, generation_seconds=9.0,
        strict=Status.FAIL, weak=Status.FAIL,
    )
    for i in range(5, 37)
]

#: The larger-base arm's journal: the same shape as the probe's, under the arm's own
#: candidate — the door names the candidate from the arm's tallies, never from a flag.
LARGER_BASE_ARM_STEPS: list[Step] = [
    _step(
        LARGER_BASE_CANDIDATE, f"t-{i:02d}", outcome=Outcome.SOLVED, generation_seconds=9.0,
        strict=Status.PASS, weak=Status.PASS,
    )
    for i in range(5)
] + [
    _step(
        LARGER_BASE_CANDIDATE, f"t-{i:02d}", outcome=Outcome.NOT_SOLVED, generation_seconds=9.0,
        strict=Status.FAIL, weak=Status.FAIL,
    )
    for i in range(5, 37)
]


def _write_journal(tmp_path: Path, stem: str, steps: list[Step]) -> Path:
    """A journal under `tmp/{stem}/journal.jsonl`."""
    path = tmp_path / stem / "journal.jsonl"
    journal = Journal(path)
    for step in steps:
        journal.append(step)
    return path


def _write_sidecar(tmp_path: Path, name: str, block: dict[str, object]) -> Path:
    """A contract sidecar on disk: the report sidecar shape, with a `generation_contract` block."""
    path = tmp_path / f"{name}-sidecar.json"
    path.write_text(
        json.dumps(
            {"measurement": "synthetic", "generation_contract": block},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _stratum_argv(fixture: dict[str, Path], out: Path) -> list[str]:
    """The render-stratum-report invocation over the single synthetic arm."""
    return [
        "--render-stratum-report",
        "--arm", "probe",
        "--journal", str(fixture["probe_journal"]),
        "--contract", str(fixture["probe_sidecar"]),
        "--stratum-doc", STRATUM_DOC,
        "--breakdown-home", BREAKDOWN_HOME,
        "--recorded-on", RECORDED_ON,
        "--out", str(out),
    ]


def _written(out: Path, name: str) -> str:
    """One artifact of a door render, as text."""
    return (out / name).read_text(encoding="utf-8")


def test_the_stratum_report_door_writes_the_three_artifacts_and_nothing_else(
    tmp_path: Path,
) -> None:
    """report.md, report.json and cost.json into `--out`, and nothing anywhere else."""
    fixture = {
        "probe_journal": _write_journal(tmp_path, "probe", PROBE_ARM_STEPS),
        "probe_sidecar": _write_sidecar(tmp_path, "probe", HARDENED_CONTRACT_BLOCK),
    }
    out = tmp_path / "render"
    exit_code = comparison.main(_stratum_argv(fixture, out))

    assert exit_code == 0, exit_code
    assert {path.name for path in out.rglob("*")} == {"report.md", "report.json", "cost.json"}, (
        [str(path) for path in out.rglob("*")]
    )
    assert {path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")} == {
        "probe",
        "probe/journal.jsonl",
        "probe-sidecar.json",
        "render",
        "render/cost.json",
        "render/report.json",
        "render/report.md",
    }, "WHY THIS IS A FAILURE: the door touched a path outside the destination it was given"


def test_the_stratum_report_door_render_carries_the_changed_task_set_ground(
    tmp_path: Path,
) -> None:
    """The render is the probe's report: changed task set, pointers, rows — never the comparison's.

    The door must render the stratum document, not a copy of the two-contract report: the
    changed-task-set ground is stated, the stratum document and breakdown home are named,
    the contract fields sit beside the per-candidate table, and the comparison's own
    header is absent.
    """
    fixture = {
        "probe_journal": _write_journal(tmp_path, "probe", PROBE_ARM_STEPS),
        "probe_sidecar": _write_sidecar(tmp_path, "probe", HARDENED_CONTRACT_BLOCK),
    }
    out = tmp_path / "render"
    exit_code = comparison.main(_stratum_argv(fixture, out))

    assert exit_code == 0, exit_code
    markdown = _written(out, "report.md")
    payload = json.loads(_written(out, "report.json"))

    assert "different task set" in markdown, markdown
    assert STRATUM_DOC in markdown, markdown
    assert BREAKDOWN_HOME in markdown, markdown
    assert "5 of 37" in markdown, markdown
    assert "Format-hardening arm" not in markdown, markdown
    assert payload["schema"] == "whetstone-stratum-report/1", payload
    assert payload["non_comparable"] is True, payload
    assert payload["stratum_doc"] == STRATUM_DOC, payload
    assert payload["generation_contract"]["retry_budget"] == 2, payload
    assert payload["per_candidate"][0]["denominator"] == 37, payload
    cost = json.loads(_written(out, "cost.json"))
    assert cost["kind"] == "stratum-report", cost


def test_the_stratum_report_door_is_byte_deterministic(tmp_path: Path) -> None:
    """Two invocations over the same inputs write byte-identical artifacts."""
    fixture = {
        "probe_journal": _write_journal(tmp_path, "probe", PROBE_ARM_STEPS),
        "probe_sidecar": _write_sidecar(tmp_path, "probe", HARDENED_CONTRACT_BLOCK),
    }
    out = tmp_path / "render"
    argv = _stratum_argv(fixture, out)
    first = comparison.main(argv)
    first_bytes = {
        name: (out / name).read_bytes() for name in ("report.md", "report.json", "cost.json")
    }
    second = comparison.main(argv)
    second_bytes = {
        name: (out / name).read_bytes() for name in ("report.md", "report.json", "cost.json")
    }

    assert first == 0 and second == 0
    assert first_bytes == second_bytes, (
        "WHY THIS IS A FAILURE: two invocations over the same inputs wrote different bytes. "
        "A render that changes between reads of the same runs is evidence nobody can "
        "re-derive"
    )


# --------------------------------------------------------------------------------------------
# The stratum mode's refusals: each exit 2 with the reason named, and nothing written.
# --------------------------------------------------------------------------------------------


def _assert_refused(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    expected: str,
) -> None:
    """One refusal: exit 2, the reason named on stderr, nothing written under `--out`."""
    out = tmp_path / "render"
    exit_code = comparison.main([*argv, "--out", str(out)])
    message = capsys.readouterr().err
    assert exit_code == 2, exit_code
    assert expected in message, message
    assert not out.exists(), (
        "WHY THIS IS A FAILURE: a refused invocation wrote something under --out. A "
        "refusal must happen before anything touches the destination"
    )


def test_stratum_report_with_no_arms_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The committed declaration is not re-rendered by the door: zero groups is exit 2."""
    _assert_refused(tmp_path, capsys, ["--render-stratum-report"], "no arms")


def test_stratum_report_with_two_arm_groups_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The probe is one run under one contract: a second group is a second measurement shape."""
    fixture = {
        "probe_journal": _write_journal(tmp_path, "probe", PROBE_ARM_STEPS),
        "probe_sidecar": _write_sidecar(tmp_path, "probe", HARDENED_CONTRACT_BLOCK),
    }
    argv = _stratum_argv(fixture, tmp_path / "unused")
    argv += ["--arm", "second", "--journal", str(fixture["probe_journal"]),
             "--contract", str(fixture["probe_sidecar"])]
    _assert_refused(tmp_path, capsys, argv, "exactly one")


def test_stratum_report_refuses_an_arm_whose_journal_has_not_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing journal means the probe has not run — a refusal, never zero rollouts."""
    fixture = {
        "probe_journal": _write_journal(tmp_path, "probe", PROBE_ARM_STEPS),
        "probe_sidecar": _write_sidecar(tmp_path, "probe", HARDENED_CONTRACT_BLOCK),
    }
    argv = _stratum_argv(fixture, tmp_path / "unused")
    argv[argv.index(str(fixture["probe_journal"]))] = str(tmp_path / "never-ran" / "journal.jsonl")
    _assert_refused(tmp_path, capsys, argv, "has not run")


def test_stratum_report_refuses_an_arm_without_an_intact_probe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A run that never proved the harness yields no counts (`control.py:492` discipline)."""
    unproven = _write_journal(
        tmp_path,
        "unproven",
        [
            _step(
                "one", "t-01", outcome=Outcome.NOT_SOLVED, generation_seconds=1.0,
                strict=Status.FAIL, weak=Status.FAIL, control=Control.BROKEN,
            )
        ],
    )
    argv = [
        "--render-stratum-report",
        "--arm", "unproven",
        "--journal", str(unproven),
        "--contract", str(_write_sidecar(tmp_path, "unproven", HARDENED_CONTRACT_BLOCK)),
        "--stratum-doc", STRATUM_DOC,
        "--breakdown-home", BREAKDOWN_HOME,
        "--recorded-on", RECORDED_ON,
    ]
    _assert_refused(tmp_path, capsys, argv, "INTACT")


def test_stratum_report_refuses_a_missing_stratum_doc(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--stratum-doc` is required: the changed-task-set claim must be checkable."""
    fixture = {
        "probe_journal": _write_journal(tmp_path, "probe", PROBE_ARM_STEPS),
        "probe_sidecar": _write_sidecar(tmp_path, "probe", HARDENED_CONTRACT_BLOCK),
    }
    argv = _stratum_argv(fixture, tmp_path / "unused")
    index = argv.index("--stratum-doc")
    del argv[index : index + 2]
    _assert_refused(tmp_path, capsys, argv, "--stratum-doc")


def test_stratum_report_refuses_a_missing_breakdown_home(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--breakdown-home` is required: the render points at the counts' home, never restates one."""
    fixture = {
        "probe_journal": _write_journal(tmp_path, "probe", PROBE_ARM_STEPS),
        "probe_sidecar": _write_sidecar(tmp_path, "probe", HARDENED_CONTRACT_BLOCK),
    }
    argv = _stratum_argv(fixture, tmp_path / "unused")
    index = argv.index("--breakdown-home")
    del argv[index : index + 2]
    _assert_refused(tmp_path, capsys, argv, "--breakdown-home")


def test_stratum_report_refuses_a_missing_recorded_on(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--recorded-on` is an input, never the clock — the door refuses to invent one."""
    fixture = {
        "probe_journal": _write_journal(tmp_path, "probe", PROBE_ARM_STEPS),
        "probe_sidecar": _write_sidecar(tmp_path, "probe", HARDENED_CONTRACT_BLOCK),
    }
    argv = _stratum_argv(fixture, tmp_path / "unused")
    index = argv.index("--recorded-on")
    del argv[index : index + 2]
    _assert_refused(tmp_path, capsys, argv, "--recorded-on")


def test_stratum_report_refuses_a_missing_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--out` is required: the directory the three artifacts are written into."""
    fixture = {
        "probe_journal": _write_journal(tmp_path, "probe", PROBE_ARM_STEPS),
        "probe_sidecar": _write_sidecar(tmp_path, "probe", HARDENED_CONTRACT_BLOCK),
    }
    argv = _stratum_argv(fixture, tmp_path / "unused")
    index = argv.index("--out")
    del argv[index : index + 2]
    exit_code = comparison.main(argv)
    message = capsys.readouterr().err
    assert exit_code == 2, exit_code
    assert "--out" in message, message


def test_render_report_and_render_stratum_report_are_mutually_exclusive(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exactly one door mode runs; both flags together is a refused invocation."""
    exit_code = comparison.main(["--render-report", "--render-stratum-report"])
    message = capsys.readouterr().err
    assert exit_code == 2, exit_code
    assert "mutually exclusive" in message, message


def test_the_render_report_mode_is_untouched(tmp_path: Path) -> None:
    """`--render-report` with the same journal/contract still renders the comparison shape.

    The format-hardening mode and its refusals are untouched by the new mode; the same
    inputs render the two-contract document, not the stratum document.
    """
    fixture = {
        "probe_journal": _write_journal(tmp_path, "probe", PROBE_ARM_STEPS),
        "probe_sidecar": _write_sidecar(tmp_path, "probe", HARDENED_CONTRACT_BLOCK),
    }
    out = tmp_path / "comparison-render"
    exit_code = comparison.main(
        [
            "--render-report",
            "--arm", "arm-a",
            "--journal", str(fixture["probe_journal"]),
            "--contract", str(fixture["probe_sidecar"]),
            "--breakdown-home", BREAKDOWN_HOME,
            "--recorded-on", RECORDED_ON,
            "--out", str(out),
        ]
    )

    assert exit_code == 0, exit_code
    markdown = _written(out, "report.md")
    assert "Format-hardening arm" in markdown, markdown
    assert "different task set" not in markdown, markdown
    assert {path.name for path in out.rglob("*")} == {"report.md", "report.json", "cost.json"}


def test_the_stratum_report_door_uses_the_writer_by_identity() -> None:
    """The door's seams are `report`'s own — imported by identity, never reimplemented.

    `build_contract_arms` is reused unchanged so its refusals hold by identity; the
    render is the shipped writer's own. A second spelling of any of these would be a
    second opinion about the same number.
    """
    assert comparison.build_stratum_report is report.build_stratum_report, (
        "WHY THIS IS A FAILURE: the door does not call report.build_stratum_report by "
        "identity"
    )
    assert comparison.write_stratum_report is report.write_stratum_report, (
        "WHY THIS IS A FAILURE: the door does not call report.write_stratum_report by "
        "identity"
    )


# --------------------------------------------------------------------------------------------
# The larger-base-report mode: the door's third mode, in the stratum mode's shape.
# --------------------------------------------------------------------------------------------


def _larger_base_argv(fixture: dict[str, Path], out: Path) -> list[str]:
    """The render-larger-base-report invocation over the single synthetic arm."""
    return [
        "--render-larger-base-report",
        "--arm", "larger-base",
        "--journal", str(fixture["larger_base_journal"]),
        "--contract", str(fixture["larger_base_sidecar"]),
        "--breakdown-home", LARGER_BASE_BREAKDOWN_HOME,
        "--recorded-on", LARGER_BASE_RECORDED_ON,
        "--out", str(out),
    ]


def test_the_larger_base_report_door_writes_the_three_artifacts_and_nothing_else(
    tmp_path: Path,
) -> None:
    """report.md, report.json and cost.json into `--out`, and nothing anywhere else."""
    fixture = {
        "larger_base_journal": _write_journal(tmp_path, "larger-base", LARGER_BASE_ARM_STEPS),
        "larger_base_sidecar": _write_sidecar(tmp_path, "larger-base", HARDENED_CONTRACT_BLOCK),
    }
    out = tmp_path / "larger-base-render"
    exit_code = comparison.main(_larger_base_argv(fixture, out))

    assert exit_code == 0, exit_code
    assert {path.name for path in out.rglob("*")} == {"report.md", "report.json", "cost.json"}, (
        [str(path) for path in out.rglob("*")]
    )
    assert {path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")} == {
        "larger-base",
        "larger-base/journal.jsonl",
        "larger-base-sidecar.json",
        "larger-base-render",
        "larger-base-render/cost.json",
        "larger-base-render/report.json",
        "larger-base-render/report.md",
    }, "WHY THIS IS A FAILURE: the door touched a path outside the destination it was given"


def test_the_larger_base_report_door_render_carries_the_changed_candidate_ground(
    tmp_path: Path,
) -> None:
    """The render is the arm's report: changed candidate, pointers, rows — never the comparison's.

    The door must render the larger-base document, not a copy of the two-contract report:
    the changed-candidate-set ground is stated, the candidate and breakdown home are
    named, the contract fields sit beside the per-candidate table, and the comparison's
    own header is absent.
    """
    fixture = {
        "larger_base_journal": _write_journal(tmp_path, "larger-base", LARGER_BASE_ARM_STEPS),
        "larger_base_sidecar": _write_sidecar(tmp_path, "larger-base", HARDENED_CONTRACT_BLOCK),
    }
    out = tmp_path / "larger-base-render"
    exit_code = comparison.main(_larger_base_argv(fixture, out))

    assert exit_code == 0, exit_code
    markdown = _written(out, "report.md")
    payload = json.loads(_written(out, "report.json"))

    assert "new candidate" in markdown, markdown
    assert LARGER_BASE_CANDIDATE in markdown, markdown
    assert LARGER_BASE_BREAKDOWN_HOME in markdown, markdown
    assert "5 of 37" in markdown, markdown
    assert "Format-hardening arm" not in markdown, markdown
    assert payload["schema"] == "whetstone-larger-base-report/1", payload
    assert payload["non_comparable"] is True, payload
    assert payload["candidate"] == LARGER_BASE_CANDIDATE, payload
    assert payload["generation_contract"]["retry_budget"] == 2, payload
    assert payload["per_candidate"][0]["denominator"] == 37, payload
    cost = json.loads(_written(out, "cost.json"))
    assert cost["kind"] == "larger-base-report", cost


def test_the_larger_base_report_door_is_byte_deterministic(tmp_path: Path) -> None:
    """Two invocations over the same inputs write byte-identical artifacts."""
    fixture = {
        "larger_base_journal": _write_journal(tmp_path, "larger-base", LARGER_BASE_ARM_STEPS),
        "larger_base_sidecar": _write_sidecar(tmp_path, "larger-base", HARDENED_CONTRACT_BLOCK),
    }
    out = tmp_path / "larger-base-render"
    argv = _larger_base_argv(fixture, out)
    first = comparison.main(argv)
    first_bytes = {
        name: (out / name).read_bytes() for name in ("report.md", "report.json", "cost.json")
    }
    second = comparison.main(argv)
    second_bytes = {
        name: (out / name).read_bytes() for name in ("report.md", "report.json", "cost.json")
    }

    assert first == 0 and second == 0
    assert first_bytes == second_bytes, (
        "WHY THIS IS A FAILURE: two invocations over the same inputs wrote different bytes. "
        "A render that changes between reads of the same runs is evidence nobody can "
        "re-derive"
    )


def test_the_larger_base_report_door_mode_appears_in_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The parser accepts the mode and its help names it (the runbook quotes the flag)."""
    with pytest.raises(SystemExit) as exc:
        comparison.main(["--help"])
    assert exc.value.code == 0
    assert "--render-larger-base-report" in capsys.readouterr().out, (
        "WHY THIS IS A FAILURE: the mode is missing from --help, so the runbook's post-run "
        "chain names a flag the CLI does not accept"
    )


def test_larger_base_report_with_no_arms_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The committed declaration is not re-rendered by the door: zero groups is exit 2."""
    _assert_refused(tmp_path, capsys, ["--render-larger-base-report"], "no arms")


def test_larger_base_report_with_two_arm_groups_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The arm is one run under one contract: a second group is a second measurement shape."""
    fixture = {
        "larger_base_journal": _write_journal(tmp_path, "larger-base", LARGER_BASE_ARM_STEPS),
        "larger_base_sidecar": _write_sidecar(tmp_path, "larger-base", HARDENED_CONTRACT_BLOCK),
    }
    argv = _larger_base_argv(fixture, tmp_path / "unused")
    argv += ["--arm", "second", "--journal", str(fixture["larger_base_journal"]),
             "--contract", str(fixture["larger_base_sidecar"])]
    _assert_refused(tmp_path, capsys, argv, "exactly one")


def test_larger_base_report_refuses_a_misaligned_arm_group(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two arm names with one journal is a shape the door refuses, never guesses at."""
    fixture = {
        "larger_base_journal": _write_journal(tmp_path, "larger-base", LARGER_BASE_ARM_STEPS),
        "larger_base_sidecar": _write_sidecar(tmp_path, "larger-base", HARDENED_CONTRACT_BLOCK),
    }
    argv = _larger_base_argv(fixture, tmp_path / "unused")
    argv += ["--arm", "second"]
    _assert_refused(tmp_path, capsys, argv, "do not line up")


def test_larger_base_report_refuses_an_arm_whose_journal_has_not_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing journal means the arm has not run — a refusal via build_contract_arms."""
    fixture = {
        "larger_base_journal": _write_journal(tmp_path, "larger-base", LARGER_BASE_ARM_STEPS),
        "larger_base_sidecar": _write_sidecar(tmp_path, "larger-base", HARDENED_CONTRACT_BLOCK),
    }
    argv = _larger_base_argv(fixture, tmp_path / "unused")
    argv[argv.index(str(fixture["larger_base_journal"]))] = str(
        tmp_path / "never-ran" / "journal.jsonl"
    )
    _assert_refused(tmp_path, capsys, argv, "has not run")


def test_larger_base_report_refuses_an_arm_without_an_intact_probe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A run that never proved the harness yields no counts (`control.py:492` discipline)."""
    unproven = _write_journal(
        tmp_path,
        "unproven",
        [
            _step(
                "one", "t-01", outcome=Outcome.NOT_SOLVED, generation_seconds=1.0,
                strict=Status.FAIL, weak=Status.FAIL, control=Control.BROKEN,
            )
        ],
    )
    argv = [
        "--render-larger-base-report",
        "--arm", "unproven",
        "--journal", str(unproven),
        "--contract", str(_write_sidecar(tmp_path, "unproven", HARDENED_CONTRACT_BLOCK)),
        "--breakdown-home", LARGER_BASE_BREAKDOWN_HOME,
        "--recorded-on", LARGER_BASE_RECORDED_ON,
    ]
    _assert_refused(tmp_path, capsys, argv, "INTACT")


def test_larger_base_report_refuses_a_missing_breakdown_home(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--breakdown-home` is required: the render points at the counts' home, never restates one."""
    fixture = {
        "larger_base_journal": _write_journal(tmp_path, "larger-base", LARGER_BASE_ARM_STEPS),
        "larger_base_sidecar": _write_sidecar(tmp_path, "larger-base", HARDENED_CONTRACT_BLOCK),
    }
    argv = _larger_base_argv(fixture, tmp_path / "unused")
    index = argv.index("--breakdown-home")
    del argv[index : index + 2]
    _assert_refused(tmp_path, capsys, argv, "--breakdown-home")


def test_larger_base_report_refuses_a_missing_recorded_on(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--recorded-on` is an input, never the clock — the door refuses to invent one."""
    fixture = {
        "larger_base_journal": _write_journal(tmp_path, "larger-base", LARGER_BASE_ARM_STEPS),
        "larger_base_sidecar": _write_sidecar(tmp_path, "larger-base", HARDENED_CONTRACT_BLOCK),
    }
    argv = _larger_base_argv(fixture, tmp_path / "unused")
    index = argv.index("--recorded-on")
    del argv[index : index + 2]
    _assert_refused(tmp_path, capsys, argv, "--recorded-on")


def test_larger_base_report_refuses_a_missing_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--out` is required: the directory the three artifacts are written into."""
    fixture = {
        "larger_base_journal": _write_journal(tmp_path, "larger-base", LARGER_BASE_ARM_STEPS),
        "larger_base_sidecar": _write_sidecar(tmp_path, "larger-base", HARDENED_CONTRACT_BLOCK),
    }
    argv = _larger_base_argv(fixture, tmp_path / "unused")
    index = argv.index("--out")
    del argv[index : index + 2]
    exit_code = comparison.main(argv)
    message = capsys.readouterr().err
    assert exit_code == 2, exit_code
    assert "--out" in message, message


def test_the_three_report_door_modes_are_mutually_exclusive(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exactly one door mode runs; any pair, or all three, is a refused invocation."""
    for flags in (
        ["--render-report", "--render-larger-base-report"],
        ["--render-stratum-report", "--render-larger-base-report"],
        ["--render-report", "--render-stratum-report", "--render-larger-base-report"],
    ):
        exit_code = comparison.main(flags)
        message = capsys.readouterr().err
        assert exit_code == 2, (flags, exit_code)
        assert "mutually exclusive" in message, (flags, message)
        assert "--render-larger-base-report" in message, (flags, message)


def test_the_larger_base_report_door_uses_the_writer_by_identity() -> None:
    """The door's larger-base seams are `report`'s own — imported by identity.

    A second spelling of the writer would be a second opinion about the same number; the
    arm's refusals come from `build_contract_arms` unchanged.
    """
    assert comparison.build_larger_base_report is report.build_larger_base_report, (
        "WHY THIS IS A FAILURE: the door does not call report.build_larger_base_report by "
        "identity"
    )
    assert comparison.write_larger_base_report is report.write_larger_base_report, (
        "WHY THIS IS A FAILURE: the door does not call report.write_larger_base_report by "
        "identity"
    )
