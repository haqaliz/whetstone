"""Guards over the baseline-measurement runbook, so its commands cannot drift from the door.

`docs/planning/baseline-measurement/measurement-run/runbook.md` is the operator's sheet for
the single GPU pass that spends the `PREREGISTRATION.md` § 3 baseline — the untrained open
base scored on the held-out split, **measured once, re-measured never**. It is run verbatim,
and a sheet that disagrees with the code it runs fails after the number is gone, so the
disagreements are refused here.

**Extended, not parameterized, on the gate guard's own argument.** The three parse helpers
that are independent of which command a sheet invokes — `_bash_blocks`, `_named_paths`,
`_worktree_name` — are imported **by identity** from `test_runbook_guards.py`, and the
stale-worktree list is `test_gate_runbook_guards.STALE_WORKTREES` **by identity**, asserted
`is`: a fix to the shared parse or to the stale list is seen by every runbook guard in this
tree. The flag and value parses are keyed on this sheet's own door and are this file's own,
rather than mutating a constant another guard reads: a guard that reaches into another
guard's globals can silently repoint the sheet it was watching.

Ten properties, and the last six are this sheet's own:

1. the parse really reads the sheet (anti-vacuity);
2. every flag the chain passes exists in `baseline.build_parser` — the module door's own
   parser, never `whetstone.cli`'s;
3. every writable path the chain names is absolute;
4. exactly one worktree is named anywhere, and no stale one survives;
5. the measured-once discipline is stated as a **refusal**, and the sheet nowhere tells the
   operator to re-measure, re-render or "confirm" the number — re-measuring until it
   flatters is selecting on the outcome, and the § 3 baseline is not re-run for any reason;
6. the machinery is verified on the fixture suites before the real pass;
7. the candidate resolution names the 32B and keeps § 7.3 open — no pinned/selected base
   phrasing;
8. the zero-score and coverage outcomes are stated as publishable, never a halt;
9. the killed-run behavior (fresh `--run-id`, half-written artifacts refused by schema) and
   `--recorded-on` as an input are stated;
10. the post-run chain is present — the render door over the evidence, then the finding.

**Watched failing first** (`CONTRIBUTING.md`): every assertion was run against a deliberately
wrong stub sheet — relative writable paths, a `--retries` flag the parser does not define, a
stale worktree, a "re-measure to confirm the number" instruction, no § 7.3 sentence, no
fixture verification and no post-run chain — and all ten refused it before the real sheet
existed.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from test_gate_runbook_guards import STALE_WORKTREES
from test_runbook_guards import _bash_blocks, _named_paths, _worktree_name

from whetstone.loop import baseline

#: The sheet under guard.
RUNBOOK = (
    Path(__file__).parent.parent
    / "docs/planning/baseline-measurement/measurement-run/runbook.md"
)

#: The one door this sheet drives — the module door. Its flag surface is pinned against
#: `baseline.build_parser()` itself; `whetstone.cli` is not involved.
DOORS = (("python -m whetstone.loop.baseline", None),)

#: This unit's worktree, and every worktree an earlier unit used. A stale name in a sheet
#: sends an operator to a directory that no longer holds the code they think they are
#: running — the gate guard's own list, by identity.
WORKTREE = "feat-baseline-measurement"

#: Every flag the door accepts whose value is a path. All of them must be absolute — the
#: failure that killed the measured arm on 2026-08-12 was a relative workspace, and this
#: run scores the one input that is never measured twice.
PATH_FLAGS = frozenset(
    {
        "--weights",
        "--checkpoint",
        "--heldout",
        "--tasks",
        "--public",
        "--runs",
        "--workspace",
        "--out",
        "--pool",
    }
)

#: The runbook-resolved candidate — the base the night runbook retained on its evidence.
CANDIDATE = "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit"

FLAG = re.compile(r"--[a-z][a-z0-9-]*")

#: The instruction shapes that would route around the measured-once discipline. The sheet
#: must state the same-series case as a refusal and must contain none of these.
RERUN_PHRASES = (
    "re-measure to",
    "re-render",
    "confirm the number",
    "measure again",
    "run it again",
)


def _runbook() -> str:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert text.strip(), (
        f"{RUNBOOK} is empty, so every guard in this module would pass vacuously. A command "
        "sheet that parses into nothing proves nothing."
    )
    return text


def _door_blocks(blocks: list[str], door: str) -> list[str]:
    """Every bash block that invokes `door`."""
    return [block for block in blocks if door in block]


def _flags(block: str, door: str) -> set[str]:
    """The `--flag` tokens handed to `door`, ignoring `uv`'s own `--project`."""
    return set(FLAG.findall(block.partition(door)[2]))


def _values(block: str, door: str) -> dict[str, list[str]]:
    """Flag → every value it was given, from the tokens after the door invocation.

    Values are a **list** because `--tasks` is repeatable: a last-one-wins parse would
    silently drop a donor root and leave the guard attesting to a command set nobody runs.
    """
    tokens = shlex.split(block.partition(door)[2], posix=True)
    values: dict[str, list[str]] = {}
    current: str | None = None
    for token in tokens:
        if token.startswith("--"):
            current = token
            values.setdefault(current, [])
        elif current is not None:
            values[current].append(token)
            current = None
    return values


def _parser_flags() -> set[str]:
    """Every option string the door's own parser accepts.

    Pinned against `baseline.build_parser()` itself rather than against `whetstone.cli`:
    this sheet drives `python -m whetstone.loop.baseline`, which parses with the module's
    own surface, and the CLI's parser is not the one that would abort this run.
    """
    parser = baseline.build_parser()
    return {name for name in parser._option_string_actions if name.startswith("--")}


def test_the_guard_shares_the_parse_helpers_and_the_stale_list_it_can() -> None:
    """One parse implementation and one stale list, imported by identity.

    A second, drifting copy of "which paths does this line name" would let one runbook's
    guard accept a shape another's refuses; a second stale list would let an earlier unit's
    worktree survive a refresh the gate's guard already retired.
    """
    from test_gate_runbook_guards import STALE_WORKTREES as shared_stale
    from test_runbook_guards import _bash_blocks as shared_blocks
    from test_runbook_guards import _named_paths as shared_paths
    from test_runbook_guards import _worktree_name as shared_worktree

    assert _bash_blocks is shared_blocks
    assert _named_paths is shared_paths
    assert _worktree_name is shared_worktree
    assert STALE_WORKTREES is shared_stale


def test_the_parse_really_reads_the_sheet() -> None:
    """Anti-vacuity: a renamed or emptied sheet must fail loudly rather than pass.

    Every assertion below is a statement about the members of a parsed set, so an empty
    parse satisfies all of them at once. The door's two signature flags — the operator's
    run identity and the operator's declared date — must come out of the parse, proving the
    blocks being guarded are the sheet's own.
    """
    blocks = _bash_blocks(_runbook())
    for door, _ in DOORS:
        found = _door_blocks(blocks, door)
        assert found, f"WHY THIS IS A FAILURE: no bash block invokes `{door}`"
        flags = {flag for block in found for flag in _flags(block, door)}
        assert "--run-id" in flags, (
            "WHY THIS IS A FAILURE: the parse never yielded `--run-id`. The run identity is "
            "this door's signature — the evidence directory's name — and a sheet whose "
            "blocks parse without it is not the sheet being guarded"
        )
        assert "--recorded-on" in flags, (
            "WHY THIS IS A FAILURE: the parse never yielded `--recorded-on`. The operator "
            "declares it in every mode, never the clock, and a sheet whose blocks parse "
            "without it is not this door's sheet"
        )


def test_every_flag_the_chain_passes_exists_in_the_door_parser() -> None:
    """A flag the door does not define is a usage error after the number is gone.

    Checked against `baseline.build_parser()` itself rather than against a copied list, so
    the sheet is pinned to the code that ships and not to a memory of it.
    """
    blocks = _bash_blocks(_runbook())
    known = _parser_flags()
    for door, _ in DOORS:
        found = _door_blocks(blocks, door)
        assert found, f"WHY THIS IS A FAILURE: no bash block invokes `{door}`"
        for block in found:
            unknown = sorted(_flags(block, door) - known)
            assert not unknown, (
                f"WHY THIS IS A FAILURE: the sheet passes {unknown} to `{door}` and the "
                "parser defines none of them. The operator runs this verbatim, and the § 3 "
                "baseline is never re-run because a command line was wrong. "
                f"Accepts: {sorted(known)}"
            )


def test_every_writable_path_the_chain_names_is_absolute() -> None:
    """A relative path is the failure that killed the measured arm on 2026-08-12.

    It applies to every path-valued flag here: the workspace is built as `workspace /
    digest` and provisioned by subprocesses whose CWD is not the run's, so a relative
    workspace does not resolve there, every environment build fails and every rollout is
    `UNPROVISIONED` — a measurement that measures nothing.
    """
    blocks = _bash_blocks(_runbook())
    for door, _ in DOORS:
        for block in _door_blocks(blocks, door):
            values = _values(block, door)
            relative = sorted(
                f"{flag} {value}"
                for flag, given in values.items()
                if flag in PATH_FLAGS
                for value in given
                if not value.startswith("/")
            )
            assert not relative, (
                f"WHY THIS IS A FAILURE: `{door}` is given relative path(s) {relative}. "
                "The sheet is run verbatim from a stated CWD, and a path that resolves "
                "against the wrong directory fails as a refusal about the checkpoint rather "
                "than about the command"
            )


def test_exactly_one_worktree_is_named_and_no_stale_one_survives() -> None:
    """A stale worktree sends the operator to a directory that no longer holds this code."""
    text = _runbook()
    named = {
        name
        for line in text.splitlines()
        for path in _named_paths(line)
        if (name := _worktree_name(path)) is not None
    }

    assert named == {WORKTREE}, (
        f"WHY THIS IS A FAILURE: the sheet names worktree(s) {sorted(named)} and this unit's "
        f"is {WORKTREE!r}. A sheet naming two sends the operator to whichever they read first"
    )
    stale = sorted(one for one in STALE_WORKTREES if one in text)
    assert not stale, (
        f"WHY THIS IS A FAILURE: the sheet still names {stale}, from an earlier unit. That "
        "directory does not hold the measurement door"
    )


def test_the_measured_once_discipline_is_a_refusal_not_a_rerun() -> None:
    """The same-series case is a refusal; the sheet never tells the operator to re-measure.

    The failure this refuses is the obvious one to write into an operator's sheet: *"if the
    number looks off, re-measure to confirm it."* Re-measuring until the number flatters is
    selecting on the outcome, and it would turn the once-spent § 3 baseline into a
    re-runnable figure.
    """
    text = _runbook()
    lowered = text.lower()

    assert "refus" in lowered, (
        "WHY THIS IS A FAILURE: the sheet nowhere states the same-series case as a refusal. "
        "A same-series artifact at `--out` is refused by name — a warning to proceed would "
        "make the second measurement the operator's honest option"
    )
    for phrase in RERUN_PHRASES:
        assert phrase not in lowered, (
            f"WHY THIS IS A FAILURE: the sheet says {phrase!r}. The § 3 baseline is "
            "measured once, re-measured never (`PREREGISTRATION.md:129-135`), and re-running "
            "it is selecting on the outcome"
        )


def test_the_machinery_is_verified_before_the_real_pass() -> None:
    """The first real measurement must not also be the first test of the machinery.

    The door's own fixture suites run the whole path — the held-out loader, the checkpoint
    re-hash, the scoring harness, the retry discipline, the evidence writer and the render
    door — under the stub engine. Running them first catches a machinery regression before
    the single spend is committed to it: the D7 probe-pass discipline every arm in this
    repository has used, applied to the one input that is never measured twice.
    """
    text = _runbook()
    blocks = _bash_blocks(text)

    fixture = [
        block
        for block in blocks
        if "pytest" in block and "tests/loop/test_baseline" in block
    ]
    assert fixture, (
        "WHY THIS IS A FAILURE: the sheet has no fixture verification step. The door's "
        "fixture suites are what prove the machinery before the single spend is committed "
        "to it"
    )
    assert "tests/bakeoff/test_baseline_report.py" in fixture[0], (
        "WHY THIS IS A FAILURE: the fixture verification omits the report suite. The render "
        "chain's writer is part of the machinery the first real measurement exercises"
    )
    real = _door_blocks(blocks, "python -m whetstone.loop.baseline")
    assert real, "the sheet invokes `python -m whetstone.loop.baseline` nowhere"
    assert text.index(fixture[0]) < text.index(real[0]), (
        "WHY THIS IS A FAILURE: the measurement is run before the machinery is verified. "
        "That makes the single spend the machinery's own smoke test, on the one input that "
        "is never measured twice"
    )


def test_the_candidate_resolution_names_the_32b_and_keeps_section_7_3_open() -> None:
    """The 32B is the runbook-resolved candidate; § 7.3 is not closed by this measurement.

    The baseline fixes the series it is measured over; it is not a base selection, and the
    pre-registration's "which open base" question closes only by a Type 1 amendment. A sheet
    that called the base "pinned" or "selected" would be closing § 7.3 in prose.
    """
    text = _runbook()

    assert CANDIDATE in text, (
        "WHY THIS IS A FAILURE: the sheet never names the runbook-resolved candidate. The "
        "32B is the base this measurement scores, and a sheet silent on it measures nobody"
    )
    assert "§ 7.3" in text and "open" in text, (
        "WHY THIS IS A FAILURE: the sheet does not state that § 7.3 stays open. The "
        "measurement fixes the series; it does not pick the base"
    )
    for phrase in ("pinned base", "selected base"):
        assert phrase not in text, (
            f"WHY THIS IS A FAILURE: the sheet calls the candidate a {phrase!r}. § 7.3 "
            "closes only by a Type 1 amendment before the measurement it governs runs"
        )


def test_the_outcomes_are_publishable_never_a_halt() -> None:
    """A zero solved count and a coverage below 12 of 12 are publishable baselines.

    `docs/ROADMAP.md:470-471` fixes the pivot signal as none — the engine working and the
    empirical claim being established are different milestones — and a held-out task still
    unverified after `R` lowers coverage, it never leaves the denominator
    (`PREREGISTRATION.md:111-114`). The sheet is where the operator reads that before the
    number exists.
    """
    text = _runbook()
    lowered = text.lower()

    assert "publishable" in lowered, (
        "WHY THIS IS A FAILURE: the sheet never states the outcomes as publishable. A zero "
        "solved count is a valid, publishable baseline, and the sheet is where the operator "
        "reads that before the number exists"
    )
    assert "zero" in lowered and "coverage" in lowered, (
        "WHY THIS IS A FAILURE: the sheet does not state the zero-score and coverage "
        "outcomes. Both are publishable; a coverage below 12 of 12 is disclosed with the "
        "count over its denominator, never a halt"
    )
    assert "12 of 12" in text, (
        "WHY THIS IS A FAILURE: the sheet never names the coverage denominator. The "
        "held-out membership is 12 of 66, and the operator needs the denominator the "
        "published count will be read over"
    )


def test_the_killed_run_behavior_and_recorded_on_are_stated() -> None:
    """A killed run uses a fresh `--run-id`; a half-written artifact is refused, never repaired.

    The measurement resumes nothing, and the evidence writer overwrites the file at its
    `runs/<run-id>/` home — so a re-run wearing the old id destroys the killed run's partial
    evidence. `--recorded-on` is an input, never the clock: the date the artifact declares
    is the date the operator typed, in the operator's own log.
    """
    text = _runbook()
    normalized = re.sub(r"\s+", " ", text.replace("`", ""))
    lowered = normalized.lower()

    assert "fresh --run-id" in normalized, (
        "WHY THIS IS A FAILURE: the sheet does not say a killed run restarts with a fresh "
        "`--run-id`. The measurement resumes nothing, and a re-run wearing the old id would "
        "overwrite the killed run's evidence"
    )
    assert "refused by schema" in lowered, (
        "WHY THIS IS A FAILURE: the sheet does not state that a half-written artifact is "
        "refused by schema. A half-written artifact is refused, never repaired"
    )
    assert "--recorded-on" in text and "an input, never the clock" in lowered, (
        "WHY THIS IS A FAILURE: the sheet does not state that `--recorded-on` is an input, "
        "never the clock. The date is typed by the operator, never generated"
    )


def test_the_post_run_chain_is_present() -> None:
    """The render door over the evidence, then the finding — the chain is in the sheet.

    The committed artifact exists only when the render step has run over the measurement's
    evidence, and the operator's single spend is committed by the finding, never by the
    machinery.
    """
    text = _runbook()
    lowered = text.lower()
    blocks = _bash_blocks(text)

    renders = [block for block in blocks if "--render" in block]
    assert renders, (
        "WHY THIS IS A FAILURE: the post-run chain never invokes the render door "
        "(`--render <evidence>`). The committed artifact exists only when the render step "
        "has run over the evidence"
    )
    values = _values(renders[0], "python -m whetstone.loop.baseline")
    out = values.get("--out")
    assert out and out[0].endswith("reports/baseline-measurement"), (
        "WHY THIS IS A FAILURE: the render step does not write the committed home "
        "`reports/baseline-measurement`. The artifact's home is where the measured-once "
        "guard reads the series"
    )
    assert "finding" in lowered, (
        "WHY THIS IS A FAILURE: the post-run chain never names the finding. The operator's "
        "single spend is committed by the finding, never by the machinery"
    )