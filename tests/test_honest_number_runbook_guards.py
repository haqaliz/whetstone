"""Guards over the honest-number report runbook, so its commands cannot drift from the door.

`docs/planning/honest-number-report/report-runbook/runbook.md` is the operator's sheet for the
report render — the last step of the operator chain (`docs/ROADMAP.md:652-656`: § 7.3
amendment → baseline spend → night #1 → night #2 → first gated evaluation → the P4 report →
the finding). It is run verbatim, and a sheet that disagrees with the code it runs fails after
a night has already been spent producing the candidate, so the disagreements are refused here.

**Extended, not parameterized, on the baseline guard's own argument.** The three parse helpers
that are independent of which command a sheet invokes — `_bash_blocks`, `_named_paths`,
`_worktree_name` — are imported **by identity** from `test_runbook_guards.py`, and the
stale-worktree list is `test_gate_runbook_guards.STALE_WORKTREES` **by identity**, asserted
`is`: a fix to the shared parse or to the stale list is seen by every runbook guard in this
tree. The flag and value parses are keyed on this sheet's own door and are this file's own,
rather than mutating a constant another guard reads: a guard that reaches into another guard's
globals can silently repoint the sheet it was watching.

Ten properties, all of them this sheet's own:

1. the parse really reads the sheet (anti-vacuity — the render command and `--recorded-on`);
2. every flag the chain passes exists in `honest_report.build_parser` — the module door's own
   parser, never a copied list;
3. every writable path the chain names is absolute;
4. exactly one worktree is named anywhere, and no stale one survives;
5. the refusal discipline is present — "refused by name", series disagreement, an unmeasured
   baseline — and the sheet nowhere tells the operator to re-render, run it again, or confirm
   the number;
6. the machinery is verified on the fixture suites before the real render (`text.index`
   ordering);
7. the § 4 shape sentence is present — both sources, delta, both N's, coverage;
8. the decision-semantics statement is present — promoted / rejected / UNVERIFIED each render
   a defined document, UNVERIFIED as "no comparison was made";
9. the post-render chain names the finding as the number's home;
10. the sheet contains no `\\d+ of \\d+` figure in any spelling.

**Watched failing first** (`CONTRIBUTING.md`): every assertion was run against a deliberately
wrong stub sheet — relative writable paths, a `--retries` flag the parser does not define, a
stale worktree, a "re-render to confirm" instruction, no refusal sentences, no fixture
verification, no § 4 sentence, no decision-semantics statement, no post-render chain and a
`12 of 66` figure — and all ten refused it before the real sheet existed.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from test_gate_runbook_guards import STALE_WORKTREES
from test_runbook_guards import _bash_blocks, _named_paths, _worktree_name

from whetstone.loop import honest_report

#: The sheet under guard.
RUNBOOK = (
    Path(__file__).parent.parent
    / "docs/planning/honest-number-report/report-runbook/runbook.md"
)

#: The one door this sheet drives — the module door. Its flag surface is pinned against
#: `honest_report.build_parser()` itself; `whetstone.cli` is not involved.
DOORS = (("python -m whetstone.loop.honest_report", None),)

#: This unit's worktree, and every worktree an earlier unit used. A stale name in a sheet
#: sends an operator to a directory that no longer holds the code they think they are
#: running — the gate guard's own list, by identity.
WORKTREE = "feat-honest-number-report"

#: Every flag the door accepts whose value is a path. All of them must be absolute — the
#: failure that killed the measured arm on 2026-08-12 was a relative workspace, and this
#: render consumes the evidence a baseline spend and two nights produced.
PATH_FLAGS = frozenset(
    {
        "--baseline",
        "--record",
        "--checkpoint-candidate",
        "--checkpoint-incumbent",
        "--heldout",
        "--out",
        "--render-declaration",
    }
)

FLAG = re.compile(r"--[a-z][a-z0-9-]*")

#: The figure shape the pre-registration forbids the sheet from carrying. The sheet is
#: committed before the render, so any `N of M` in it is invented, not measured.
N_OF_M = re.compile(r"\d+\s+of\s+\d+")

#: The instruction shapes that would route around the render-once discipline. The sheet must
#: state the refusals and must contain none of these: re-rendering until the number flatters
#: is selecting on the outcome, and it would turn the report into a re-runnable figure.
RERUN_PHRASES = (
    "re-render to confirm",
    "run it again",
    "confirm the number",
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

    Values are a **list** so a repeatable flag cannot be silently dropped by a last-one-wins
    parse.
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

    Pinned against `honest_report.build_parser()` itself rather than against `whetstone.cli`:
    this sheet drives `python -m whetstone.loop.honest_report`, which parses with the
    module's own surface.
    """
    parser = honest_report.build_parser()
    return {name for name in parser._option_string_actions if name.startswith("--")}


def test_the_parse_really_reads_the_sheet() -> None:
    """Anti-vacuity: a renamed or emptied sheet must fail loudly rather than pass.

    Every assertion below is a statement about the members of a parsed set, so an empty
    parse satisfies all of them at once. The door's two signature flags — the render switch
    and the operator's declared date — must come out of the parse, proving the blocks being
    guarded are the sheet's own.
    """
    blocks = _bash_blocks(_runbook())
    for door, _ in DOORS:
        found = _door_blocks(blocks, door)
        assert found, f"WHY THIS IS A FAILURE: no bash block invokes `{door}`"
        flags = {flag for block in found for flag in _flags(block, door)}
        assert "--render" in flags, (
            "WHY THIS IS A FAILURE: the parse never yielded `--render`. The render switch "
            "is this door's signature mode, and a sheet whose blocks parse without it is "
            "not the sheet being guarded"
        )
        assert "--recorded-on" in flags, (
            "WHY THIS IS A FAILURE: the parse never yielded `--recorded-on`. The operator "
            "declares it in every mode, never the clock, and a sheet whose blocks parse "
            "without it is not this door's sheet"
        )


def test_every_flag_the_chain_passes_exists_in_the_door_parser() -> None:
    """A flag the door does not define is a usage error after a night is already spent.

    Checked against `honest_report.build_parser()` itself rather than against a copied list,
    so the sheet is pinned to the code that ships and not to a memory of it.
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
                "parser defines none of them. The operator runs this verbatim, and the "
                "report is never re-rendered because a command line was wrong. "
                f"Accepts: {sorted(known)}"
            )


def test_every_writable_path_the_chain_names_is_absolute() -> None:
    """A relative path is the failure that killed the measured arm on 2026-08-12.

    It applies to every path-valued flag here: the render reads the sealed evidence and
    writes the committed home, and a relative path resolved against the wrong CWD either
    reads the wrong evidence or writes where git cannot see it.
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
                "against the wrong directory fails as a refusal about the evidence rather "
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
        "directory does not hold the report door"
    )


def test_the_refusal_discipline_is_a_refusal_not_a_rerun() -> None:
    """The half-truth render is a refusal by name; the sheet never tells the operator to re-render.

    The failure this refuses is the obvious one to write into an operator's sheet: *"if the
    render looks off, re-render to confirm the number."* Re-rendering until the number
    flatters is selecting on the outcome, and the report is a pure function of its sealed
    evidence — a second render would be the first render wearing a second date.
    """
    text = _runbook()
    lowered = text.lower()

    assert "refused by name" in lowered, (
        "WHY THIS IS A FAILURE: the sheet nowhere states a half-truth render as a refusal "
        "by name. A warning to proceed would make the wrong render the operator's honest "
        "option"
    )
    assert "series disagreement" in lowered, (
        "WHY THIS IS A FAILURE: the sheet does not state the series-disagreement refusal. A "
        "delta across a changed pinned input is not a delta, and it is refused by name"
    )
    assert "unmeasured baseline" in lowered, (
        "WHY THIS IS A FAILURE: the sheet does not state the unmeasured-baseline refusal. A "
        "declaration has no counts to delta against, and a render against it is refused by "
        "name"
    )
    for phrase in RERUN_PHRASES:
        assert phrase not in lowered, (
            f"WHY THIS IS A FAILURE: the sheet says {phrase!r}. Re-rendering until the "
            "number flatters is selecting on the outcome, and the report is never re-run "
            "to be checked"
        )


def test_the_machinery_is_verified_before_the_real_render() -> None:
    """The first real render must not also be the first test of the machinery.

    The door's own fixture suites run the whole path — the promotion-record reader, the
    writer's § 4 shape, the decision semantics — on fixtures. Running them first catches a
    machinery regression before the evidence a baseline spend and two nights produced is
    spent on it: the D7 probe-pass discipline every arm in this repository has used.
    """
    text = _runbook()
    blocks = _bash_blocks(text)

    fixture = [
        block
        for block in blocks
        if "pytest" in block
        and "tests/loop/test_honest_report_door.py" in block
        and "tests/bakeoff/test_honest_number_report.py" in block
        and "tests/loop/test_promotion_record_n.py" in block
    ]
    assert fixture, (
        "WHY THIS IS A FAILURE: the sheet has no fixture verification step covering the "
        "aspect 1-3 suites. The door's fixture suites are what prove the machinery before "
        "the real render"
    )
    real = _door_blocks(blocks, "python -m whetstone.loop.honest_report")
    assert real, "the sheet invokes `python -m whetstone.loop.honest_report` nowhere"
    assert text.index(fixture[0]) < text.index(real[0]), (
        "WHY THIS IS A FAILURE: the render is run before the machinery is verified. That "
        "makes the first real render the machinery's own smoke test, on the evidence that "
        "cost a baseline spend and two nights to produce"
    )


def test_the_section_4_shape_sentence_is_present() -> None:
    """The sheet states the § 4 shape the report instantiates — the pre-registered one.

    `PREREGISTRATION.md` § 4 fixes the report's shape; a sheet that describes a different
    shape would send the operator to check a document the pre-registration does not bind.
    """
    text = _runbook()
    lowered = text.lower()

    assert "§ 4" in text, (
        "WHY THIS IS A FAILURE: the sheet never names § 4. The report's shape is the "
        "pre-registered one, and the sheet is where the operator reads that it is"
    )
    for token in ("both sources", "delta", "n_baseline", "n_final", "coverage"):
        assert token in lowered, (
            f"WHY THIS IS A FAILURE: the sheet does not state the § 4 shape element "
            f"{token!r}. The report renders baseline score, final score, delta, both N's "
            "and coverage, for both sources"
        )


def test_the_decision_semantics_statement_is_present() -> None:
    """Promoted / rejected / UNVERIFIED each render a defined document.

    The decision semantics are the gate's and the writer's, passed through verbatim; the
    sheet is where the operator reads, before the number exists, that an UNVERIFIED eval
    renders no headline and no delta — "no comparison was made", never a delta that reads
    as a win.
    """
    text = _runbook()
    lowered = text.lower()

    assert "promoted" in lowered, (
        "WHY THIS IS A FAILURE: the sheet does not state the promoted decision's document. "
        "Promoted renders the candidate as final"
    )
    assert "rejected" in lowered, (
        "WHY THIS IS A FAILURE: the sheet does not state the rejected decision's document. "
        "Rejected renders the incumbent as final with the candidate disclosed"
    )
    assert "unverified" in lowered, (
        "WHY THIS IS A FAILURE: the sheet does not state the UNVERIFIED decision's "
        "document. An UNVERIFIED eval is a published outcome, not a halt"
    )
    assert "no comparison was made" in lowered, (
        "WHY THIS IS A FAILURE: the sheet does not state the UNVERIFIED case as 'no "
        "comparison was made'. An UNVERIFIED eval renders no headline and no delta"
    )


def test_the_post_render_chain_names_the_finding_as_the_numbers_home() -> None:
    """The finding commits the artifacts and states the number — the narrative home.

    The committed artifact exists only when the render step has run over the sealed
    evidence, and the number itself is stated by the finding, never invented in this sheet —
    which, committed before the render, holds no figure in any spelling.
    """
    text = _runbook()
    lowered = text.lower()

    assert "finding" in lowered, (
        "WHY THIS IS A FAILURE: the post-render chain never names the finding. The "
        "rendered artifacts are committed by the finding, and the number is stated there, "
        "never in this sheet"
    )
    assert "states the number" in lowered, (
        "WHY THIS IS A FAILURE: the sheet does not say the finding states the number. The "
        "number's narrative home is the finding, on the baseline runbook's precedent"
    )
    assert "nothing in this sheet is a figure about a model" in lowered, (
        "WHY THIS IS A FAILURE: the sheet does not carry the no-figure sentence. Committed "
        "before the render, it can only hold a number it invented"
    )


def test_the_sheet_contains_no_n_of_m_figure() -> None:
    """No `\\d+ of \\d+` in any spelling — a committed-before-render sheet invents nothing.

    The sheet is committed before the render, so any `N of M` in it is invented, not
    measured. Checked over the whole file, prose and blocks alike.
    """
    text = _runbook()
    matches = sorted(N_OF_M.findall(text))
    assert not matches, (
        f"WHY THIS IS A FAILURE: the sheet carries the figure(s) {matches}. The sheet is "
        "committed before the render, and a number in it would be invented, not measured"
    )
