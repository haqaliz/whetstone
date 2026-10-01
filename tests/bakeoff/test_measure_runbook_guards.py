"""Guards over the measurement runbook, so its commands cannot drift from the doors they invoke.

`docs/planning/edit-contract-finding/measurement-run/runbook.md` is the operator's sheet for
the unit's measurement: the driver (`python -m whetstone.bakeoff.measure`) spends one small
real bake-off on the pinned base under the numbered-listing prompt, the instrument
(`python -m whetstone.bakeoff.addressability`) classifies the completions by the pre-committed
rule, and the finding is written from the exits. The sheet is run verbatim, after this unit
merges, on a GPU pass that costs an hour — a sheet that disagrees with the code it runs fails
after that pass is spent, so the disagreements are refused here first.

**Extended, not parameterized, on the night guard's own argument.** The three parse helpers
that are independent of which command a sheet invokes — `_bash_blocks`, `_named_paths`,
`_worktree_name` — are imported **by identity**, asserted `is`, so a fix to the shared parse is
seen by every runbook guard in this tree. The flag and value parses are keyed on this sheet's
own two doors (`python -m` modules with their own `build_parser`s, not `whetstone`
subcommands) and are this file's own, rather than mutating a constant another guard reads: a
guard that reaches into another guard's globals can silently repoint the sheet it was watching.

Thirteen properties, and the last nine are this sheet's own:

1. the parse really reads the sheet (anti-vacuity);
2. every flag either command passes exists in the shipped parser (`measure.build_parser`,
   `addressability.build_parser` — the sheet is pinned to the code that ships, not to a memory
   of it);
3. every path either command names is absolute;
4. no worktree is named anywhere, and no stale one survives;
5. the sheet exports the anchor every path depends on;
6. the sheet cites the spec and pins the rule sentence by identity with
   `addressability.RULE` — a wrong citation or a lax variant is a failure — and the rule is
   cross-pinned into the spec document itself, so a sheet and a spec cannot disagree quietly;
7. the population is pinned by identity with `measure._PINNED_POPULATION`: every one of the 16
   ids present, and both committed documents named by path;
8. the measure command passes `--only` the pinned candidate, and nothing else;
9. the measure command uses the night door's own `--timeout 900` and a declared
   `--recorded-on` — an input, never the clock;
10. the machine-level GPU is serialized — a second process drawing on the same device perturbs
    the draws;
11. the digest-equality halt stands — a changed spec, stratum document or held-out document is
    a halt, never a rerun; a driver refusal is a halt, never a rerun with the inputs changed;
    exit 0 only when all three evidence files are on disk; the instrument's exits are 0 GO /
    1 NO-GO / 2 refused, and an exit-2 instrument refusal writes nothing and is re-run only
    with the same inputs;
12. no counts are published into `reports/` — the sentence is stated, and no command writes
    under a reports path.

**Watched failing first** (CONTRIBUTING.md): every assertion was run against a deliberately
wrong stub sheet — a missing spec citation, a lax rule sentence, a population that dropped an
id, a relative `--workspace`, a `--only` naming a second candidate, a `--timeout` other than
the night door's, a halt condition that renamed the digest response, a `--out` under
`reports/`, and a missing "counts never published" sentence — and each refused it before the
real sheet existed.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from test_runbook_guards import _bash_blocks, _named_paths, _worktree_name

from whetstone.bakeoff import addressability, measure

#: The sheet under guard. This module lives under `tests/bakeoff/`, so the repository root
#: is three parents up — one deeper than the root-level runbook guards' sheets.
RUNBOOK = (
    Path(__file__).parent.parent.parent
    / "docs/planning/edit-contract-finding/measurement-run/runbook.md"
)

#: The spec the sheet must cite — the pre-committed rule's home.
SPEC = "docs/planning/edit-contract-finding/measurement-run/spec.md"

#: The two doors this sheet drives, paired with the module whose parser defines their flags.
DOORS = (
    ("python -m whetstone.bakeoff.measure", measure.build_parser),
    ("python -m whetstone.bakeoff.addressability", addressability.build_parser),
)

#: The candidate the measurement is taken under (PREREGISTRATION.md § 10.10) — the one value
#: `--only` may name, and the one candidate the instrument's manifest may record.
CANDIDATE = "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit"

#: The timeout the night door chose, carried over unchanged (`--timeout 900`).
TIMEOUT = "900"

#: Every worktree any unit ever used. A worktree is removed the moment its unit merges, so a
#: sheet that names one sends the operator to a directory that no longer exists — including the
#: sheet's *own* unit's worktree, which is why no name here is exempt. The launch-chain sheets
#: run from the primary checkout instead, and name no worktree at all.
STALE_WORKTREES = (
    "feat-edit-contract-finding",
    "feat-gate-untrained-incumbent",
    "feat-baseline-measurement",
    "feat-honest-number-report",
    "feat-p2-format-hardening",
    "feat-format-hardening-measurement",
    "feat-measured-arm-run",
    "feat-p2-easier-stratum",
    "feat-stratum-probe-execution",
    "feat-larger-base-arm",
    "feat-p2-rollouts",
    "feat-p3-promotion-gate",
)

#: Every flag on either door whose value is a path. All of them must be absolute — the failure
#: that killed the measured arm on 2026-08-12 was a relative workspace, and this run is longer
#: than that one: the driver provisions a sandbox per task and the instrument materialises two
#: checkouts per task.
PATH_FLAGS = frozenset(
    {
        "--tasks",
        "--stratum",
        "--heldout",
        "--weights",
        "--workspace",
        "--journal",
        "--transcript",
        "--manifest",
        "--out",
    }
)

FLAG = re.compile(r"--[a-z][a-z0-9-]*")

#: A path the sheet can be run verbatim from: either literally absolute, or anchored to `$REPO`,
#: which the sheet exports to an absolute path before the first door runs. The distinction the
#: 2026-08-12 failure turns on is not the leading slash but **what the subprocess receives**: an
#: exported variable is expanded by the shell before the command starts, so the provisioner is
#: handed an absolute path either way. A bare relative path is not, and that is what produced a
#: night of `UNPROVISIONED`. The operator's own absolute path is deliberately not written into a
#: committed sheet — that publishes a home directory, and a reader re-deriving the run has a
#: different one.
_ANCHOR = "$REPO/"


def _is_anchored(value: str) -> bool:
    return value.startswith("/") or value.startswith(_ANCHOR)


def _exports_repo(text: str) -> bool:
    """The sheet must define `$REPO` as an absolute path, or the anchor anchors nothing."""
    return "export REPO=/" in text


def _flat(text: str) -> str:
    """The sheet's words with runs of whitespace collapsed to single spaces.

    A phrase pin asserts a sentence the sheet wraps freely, and the wrap point is not a
    word: "…a changed spec, stratum\\n  document…" is the same sentence as its flattened
    form.
    """
    return re.sub(r"\s+", " ", text)


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

    Values are a **list** because `--tasks` is repeatable: a last-one-wins parse would silently
    drop a donor root and leave the guard attesting to a command set nobody runs.
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


def _parser_flags(build: object) -> set[str]:
    """Every option string the shipped parser accepts."""
    parser = build()  # type: ignore[operator]
    return {option for action in parser._actions for option in action.option_strings}


def test_the_guard_shares_the_parse_helpers_it_can() -> None:
    """One parse implementation for the command-independent parts, imported by identity.

    A second, drifting copy of "which paths does this line name" would let one runbook's guard
    accept a shape another's refuses, and the divergence would look like two correct guards.
    """
    from test_runbook_guards import _bash_blocks as shared_blocks
    from test_runbook_guards import _named_paths as shared_paths
    from test_runbook_guards import _worktree_name as shared_worktree

    assert _bash_blocks is shared_blocks
    assert _named_paths is shared_paths
    assert _worktree_name is shared_worktree


def test_the_parse_really_reads_the_sheets_commands() -> None:
    """Anti-vacuity: a renamed or emptied sheet must fail loudly rather than pass.

    Every assertion below is a statement about the members of a parsed set, so an empty parse
    satisfies all of them at once — the strongest possible result from the weakest possible run.
    """
    blocks = _bash_blocks(_runbook())
    for door, _ in DOORS:
        found = _door_blocks(blocks, door)
        assert found, f"WHY THIS IS A FAILURE: no bash block invokes `{door}`"
        assert any(_flags(block, door) for block in found), (
            f"WHY THIS IS A FAILURE: every `{door}` block parsed into no flags at all"
        )
    measure_blocks = _door_blocks(blocks, DOORS[0][0])
    instrument_blocks = _door_blocks(blocks, DOORS[1][0])
    assert any("--only" in _flags(block, DOORS[0][0]) for block in measure_blocks), (
        "WHY THIS IS A FAILURE: the measure command no longer carries `--only`, the switch "
        "that names the one candidate measured"
    )
    assert any("--out" in _flags(block, DOORS[1][0]) for block in instrument_blocks), (
        "WHY THIS IS A FAILURE: the instrument command no longer carries `--out`, so the "
        "document's home is unstated"
    )


def test_every_flag_the_commands_pass_exists_in_the_shipped_parser() -> None:
    """A flag the door does not define is a usage error after the GPU pass is already spent.

    Checked against each door's own `build_parser` rather than against a copied list, so the
    sheet is pinned to the code that ships and not to a memory of it.
    """
    blocks = _bash_blocks(_runbook())
    for door, build in DOORS:
        known = _parser_flags(build)
        for block in _door_blocks(blocks, door):
            unknown = sorted(_flags(block, door) - known)
            assert not unknown, (
                f"WHY THIS IS A FAILURE: the sheet passes {unknown} to `{door}` and the parser "
                f"defines none of them. The operator runs this verbatim. Accepts: {sorted(known)}"
            )


def test_every_path_the_commands_name_is_absolute() -> None:
    """A relative path is the failure that killed the measured arm on 2026-08-12.

    It applies to every path-valued flag here, not only the written ones: the driver builds
    sandboxes under the workspace by subprocesses whose CWD is not the run's, and a relative
    workspace does not resolve there — the run's own `RelativeWorkspace` refusal would fire,
    but only after the operator believes the command is right.
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
                if not _is_anchored(value)
            )
            assert not relative, (
                f"WHY THIS IS A FAILURE: `{door}` is given relative path(s) {relative}. The "
                "sheet is run verbatim from a stated CWD, and a path that resolves against the "
                "wrong directory fails as a refusal about the run rather than about the command"
            )


def test_no_worktree_is_named_and_no_stale_one_survives() -> None:
    """Every worktree is deleted when its unit merges, so a sheet may name none.

    This guard used to require *exactly one* — this unit's — which stopped holding the
    moment the unit merged and cleanup removed the directory. The sheet is read long
    after its branch is gone; only the primary checkout survives.
    """
    text = _runbook()
    named = {
        name
        for line in text.splitlines()
        for path in _named_paths(line)
        if (name := _worktree_name(path)) is not None
    }

    assert named == set(), (
        f"WHY THIS IS A FAILURE: the sheet names worktree(s) {sorted(named)}. Worktrees are "
        "removed when their unit merges, so an operator running this sheet verbatim hits a "
        "directory that does not exist. Run from the primary checkout, with no --project"
    )
    stale = sorted(one for one in STALE_WORKTREES if one in text)
    assert not stale, (
        f"WHY THIS IS A FAILURE: the sheet still names {stale}, from an earlier unit. That "
        "directory does not hold the measurement"
    )


def test_the_sheet_exports_the_anchor_every_path_depends_on() -> None:
    """`$REPO/...` is absolute only because the sheet makes it so.

    Every path-valued flag here is anchored to `$REPO` rather than written as one operator's
    own absolute path, which keeps a home directory out of a committed file. That trade is
    only sound while the sheet still defines the anchor: an unset `REPO` expands to nothing,
    every path silently becomes relative, and this sheet is back to the shape that killed the
    measured arm on 2026-08-12 — with no leading slash left for the other guards to catch.
    """
    assert _exports_repo(_runbook()), (
        "WHY THIS IS A FAILURE: the sheet anchors its paths to `$REPO` and never exports it. "
        "An unset variable expands to the empty string, so every anchored path resolves "
        "against whatever directory the operator happened to be in"
    )


def test_the_sheet_cites_the_spec_and_pins_the_rule_sentence() -> None:
    """The rule is fixed before the run, and the sheet must say which document fixed it.

    The pre-committed rule lives in the spec (spec.md, "The pre-committed rule"); the sheet is
    where the operator meets it, so it cites the spec by name and states the decision sentence
    **by identity** with `addressability.RULE` — the constant the instrument writes into every
    document it emits. A sheet that quotes a lax variant (`>=`, a threshold, a yield claim)
    describes a different decision than the instrument makes, and is refused here rather than
    discovered at exit time.

    **Watched failing first:** the assertions were run against a stub sheet that dropped the
    spec citation and against one that pinned the lax `count(ADDRESSABLE) * 2 >= population`;
    each failed with its message before the real sheet existed.
    """
    text = _flat(_runbook())
    assert SPEC in text, (
        "WHY THIS IS A FAILURE: the sheet never cites the spec "
        f"({SPEC}). The pre-committed rule — the population, the classes, the decision — "
        "lives there, and a sheet that does not name it cannot be checked against it"
    )
    assert addressability.RULE in text, (
        f"WHY THIS IS A FAILURE: the sheet does not state the rule sentence "
        f"{addressability.RULE!r} by identity with `addressability.RULE`. The decision the "
        "instrument makes is that strict-majority inequality, and a sheet that pins any other "
        "sentence describes a different experiment"
    )


def test_the_rule_sentence_is_cross_pinned_into_the_spec_document() -> None:
    """The spec's own sentence and the instrument's constant cannot drift apart.

    The locatability output-schema pattern: the rule is a constant in code, cross-pinned to
    the committed spec's sentence. This guard closes the triangle — sheet, spec, instrument —
    by asserting the spec document itself carries the instrument's constant, so an amendment
    that rewrote one side without the other fails here rather than on the operator.
    """
    spec = (RUNBOOK.parent / "spec.md").read_text(encoding="utf-8")
    plain = _flat(spec).replace("`", "")
    assert addressability.RULE in plain, (
        f"WHY THIS IS A FAILURE: the spec no longer carries the rule sentence "
        f"{addressability.RULE!r}. The spec is the pre-committed rule's home, and the "
        "instrument's constant is cross-pinned to it; a spec that disagrees with the code "
        "leaves the sheet pinning a rule nobody implements"
    )


def test_the_sheet_pins_the_population_by_identity() -> None:
    """All 16 pre-committed ids, and the two documents they are derived from.

    The population is the stratum document's membership minus the held-out document's
    membership, by identity — the subtraction the driver re-derives and refuses to deviate
    from. The sheet must name every member and both documents, or an operator reading it
    cannot tell which run the instrument's decision is about.

    **Watched failing first:** the assertion was run against a stub sheet that dropped one id
    and against one that named the stratum document but not the held-out document; each
    failed with its message before the real sheet existed.
    """
    text = _runbook()
    for task_id in measure._PINNED_POPULATION:
        assert task_id in text, (
            f"WHY THIS IS A FAILURE: the sheet does not name {task_id}, a member of the spec's "
            "pinned population. The population is pinned by identity — every id — and a sheet "
            "that lists a subset describes a different run"
        )
    assert len(measure._PINNED_POPULATION) == 16, (
        "WHY THIS IS A FAILURE: the driver's pinned population is no longer 16 tasks. The "
        "spec pins 16 (19 easier-band members minus 3 held-out members), and the guard "
        "asserts the identity pin actually covers 16 ids"
    )
    assert "tasks/stratum/easier.json" in text, (
        "WHY THIS IS A FAILURE: the sheet never names the stratum document "
        "(tasks/stratum/easier.json). The population is its membership, and the operator "
        "needs the document named to know which membership was subtracted"
    )
    assert "tasks/heldout/source-b.json" in text, (
        "WHY THIS IS A FAILURE: the sheet never names the held-out document "
        "(tasks/heldout/source-b.json). Its members are subtracted from the population and "
        "are never rollout targets — the subtraction the sheet must show"
    )


def test_the_measure_command_uses_the_pinned_candidate() -> None:
    """`--only` names the pinned base and nothing else.

    The measurement is one candidate — the pinned 32B (PREREGISTRATION.md § 10.10) — and the
    driver refuses a provenance that names several after selection rather than picking. The
    sheet must pass `--only` exactly the pinned id: a second value would select a different
    base, and a sheet that names none leaves the selection to the weights provenance's
    content.
    """
    blocks = _bash_blocks(_runbook())
    door = DOORS[0][0]
    measure_blocks = _door_blocks(blocks, door)
    assert measure_blocks, f"WHY THIS IS A FAILURE: no bash block invokes `{door}`"
    only = _values(measure_blocks[0], door).get("--only", [])
    assert only == [CANDIDATE], (
        f"WHY THIS IS A FAILURE: the measure command passes `--only` {only}, and the pinned "
        f"candidate is {CANDIDATE!r}. The measurement is one base — measuring several in one "
        "run is refused by the driver, and naming a different base measures a different question"
    )


def test_the_measure_command_uses_the_night_doors_timeout_and_a_declared_date() -> None:
    """`--timeout 900` — the night door's own value — and `--recorded-on` an input, never the clock.

    The driver has no timeout default, so the sheet must state one; the night door's 900 is
    carried over unchanged — headroom against a genuinely hung verification without letting
    one eat the run, and a timeout is `UNVERIFIED`, never a verdict. `--recorded-on` must be
    present and is typed by the operator: a generated date would make two renders of the same
    documented command produce two run ids nobody chose.
    """
    blocks = _bash_blocks(_runbook())
    door = DOORS[0][0]
    measure_blocks = _door_blocks(blocks, door)
    assert measure_blocks, f"WHY THIS IS A FAILURE: no bash block invokes `{door}`"
    values = _values(measure_blocks[0], door)
    assert values.get("--timeout") == [TIMEOUT], (
        f"WHY THIS IS A FAILURE: the measure command's `--timeout` is {values.get('--timeout')}, "
        f"not the night door's {TIMEOUT}. A different timeout spends a different budget and "
        "produces figures comparable to nothing else"
    )
    assert "--recorded-on" in values, (
        "WHY THIS IS A FAILURE: the measure command passes no `--recorded-on`. The run's id "
        "descends from the declared date, and a sheet that omits it leaves the operator to "
        "invent the input the manifest records"
    )


def test_the_sheet_serializes_the_machine_level_gpu() -> None:
    """A second process drawing on the same device perturbs this run's draws.

    `mlx-lm` samples from process-global `mx.random` state; that is a machine-level
    constraint and deliberately not a code fix. The sheet must command the serialization
    before anything runs, or the operator's own machine is the uncontrolled variable.
    """
    text = _flat(_runbook())
    assert "machine-level GPU is serialized" in text, (
        "WHY THIS IS A FAILURE: the sheet never states the machine-level GPU serialization. "
        "Run nothing else on the device beside the measurement, or the draws are perturbed "
        "by whatever else happened to be running"
    )


def test_the_digest_equality_halt_stands() -> None:
    """A changed pre-committed input is a halt, never a rerun — on either door.

    The driver and the instrument both refuse a changed document by name: a changed spec,
    stratum document or held-out document means the run's population is no longer the pinned
    one, and re-running until a refusal goes away would select on the outcome. The sheet must
    state the halt, state that a driver refusal is a halt (never a rerun with the inputs
    changed), state the exit-0 condition (all three evidence files on disk), and state the
    instrument's three exits — where an exit-2 refusal writes nothing and is re-run only with
    the same inputs, because the instrument is offline, deterministic and never a verdict.

    **Watched failing first:** the assertions were run against a stub sheet whose halt
    condition lost the digest-mismatch response and against one that told the operator to
    rerun a driver refusal until it passed; each failed with its message before the sheet
    moved.
    """
    text = _flat(_runbook())
    lowered = text.lower()
    halt = "a changed spec, stratum document or held-out document is a halt, never a rerun"
    assert halt in text, (
        "WHY THIS IS A FAILURE: the sheet no longer names the digest-equality halt — a "
        "changed spec, stratum document or held-out document is a halt, never a rerun. The "
        "measurement's population is pinned by identity, and a run over changed documents is "
        "a different experiment"
    )
    assert "a refusal is a halt, never a rerun with the inputs changed" in lowered, (
        "WHY THIS IS A FAILURE: the sheet no longer names the driver-refusal rule — a refusal "
        "is a halt, never a rerun with the inputs changed. Re-running a refused driver until "
        "it produces evidence selects on the outcome"
    )
    assert "exit 0 only when all three are on disk" in lowered, (
        "WHY THIS IS A FAILURE: the sheet no longer states the exit-0 condition — exit 0 only "
        "when journal, transcript and manifest are all on disk. The manifest is written last, "
        "and its existence is what the operator may read as success"
    )
    assert "0 GO / 1 NO-GO / 2 refused" in text, (
        "WHY THIS IS A FAILURE: the sheet no longer states the instrument's exits — 0 GO / "
        "1 NO-GO / 2 refused. The decision is the process exit, and the sheet must say which "
        "exit is which"
    )
    assert "re-run only with the same inputs" in lowered, (
        "WHY THIS IS A FAILURE: the sheet no longer states the instrument-refusal response — "
        "investigate and re-run only with the same inputs. The instrument is offline and "
        "deterministic, so an exit 2 is a fixable refusal about the inputs' state, never a "
        "verdict — and never a reason to change the inputs"
    )


def test_no_counts_are_published_into_reports() -> None:
    """The counts' only home is the gitignored run directory.

    The measurement's completions quote the user's own donor code back verbatim, and the
    counts are comparable to nothing prior; `reports/` gains nothing from this unit. The sheet
    must state the rule, and no command may write under a reports path — a structural check
    that would catch an `--out $REPO/reports/...` even if the sentence survived.

    **Watched failing first:** the assertions were run against a stub sheet that deleted the
    sentence and against one whose instrument `--out` pointed under `$REPO/reports/`; each
    failed with its message before the real sheet existed.
    """
    text = _flat(_runbook())
    assert "counts never published into `reports/`" in text, (
        "WHY THIS IS A FAILURE: the sheet never states the no-reports rule — counts never "
        "published into `reports/`. The counts live only in gitignored "
        "`runs/edit-contract-finding/`, and a sheet that does not say so leaves their home "
        "to the operator's memory"
    )
    blocks = _bash_blocks(_runbook())
    for door, _ in DOORS:
        for block in _door_blocks(blocks, door):
            values = _values(block, door)
            published = sorted(
                f"{flag} {value}"
                for flag, given in values.items()
                if flag in PATH_FLAGS
                for value in given
                if value.startswith("$REPO/reports/") or value.startswith("/reports/")
            )
            assert not published, (
                f"WHY THIS IS A FAILURE: `{door}` writes path(s) {published} under reports/. "
                "Counts never published into `reports/` — the gitignored run directory is "
                "their only home"
            )