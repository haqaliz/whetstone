"""Guards over the re-mint apply runbook, so its commands cannot drift from the machinery.

`docs/planning/heldout-scorable/rederivation/runbook.md` is the operator's sheet for the
**#62 re-mint** — the one-time swap of the machine corpus (`tasks/local/`) to the staged
re-mint, with the ledger, stratum and held-out documents re-derived and committed together.
It is executed exactly once, on the machine that holds the real donors, and a sheet that
disagrees with the machinery it runs would move the corpus behind the evidence
(`gate-001`, every portability figure) with no guard having said anything — so the
disagreements are refused here first, in the launch-chain shape: `REPO` exported,
every path absolute or anchored to a declared anchor, snapshot before any file moves, the
double-apply halt stated, and no worktree named (worktrees are removed when their unit
merges, so a sheet that names one sends the operator to a directory that no longer exists).

The command-independent parse helpers — `_bash_blocks`, `_named_paths`, `_worktree_name` —
are imported **by identity** from `test_runbook_guards`, and the stale-worktree list from
`test_gate_runbook_guards`, so a fix to the shared parse or a name added to the retirement
list is seen by every runbook guard in this tree.

The apply blocks run the branch's machinery (`whetstone.loop.remint_apply`), which exists
only on the branch until merge — so the sheet runs with CWD at the branch's worktree and
derives the worktree's own path from `git worktree list --porcelain` (the
`test_heldout_document.py` pattern: resolved with git's own words rather than assumed),
never spelling `.claude/worktrees/<name>`. `$REPO` always names the primary checkout,
whose gitignored `tasks/local/` and `_sandbox/` are the machine state the sheet touches.

**Watched failing first** (`CONTRIBUTING.md`): every assertion was run against a
deliberately wrong stub sheet — no `REPO` export, relative paths, swap before any
snapshot, no double-apply halt, a stale worktree named — and each refused it with its
intended message before the real sheet was written.
"""

from __future__ import annotations

import shlex
from pathlib import Path

from test_gate_runbook_guards import STALE_WORKTREES
from test_runbook_guards import _bash_blocks, _is_anchored, _named_paths, _worktree_name

#: The sheet under guard.
RUNBOOK = Path(__file__).parent.parent / "docs/planning/heldout-scorable/rederivation/runbook.md"

#: The apply machinery the sheet drives, and the two derivation doors it invokes directly.
APPLY_MODULE = "whetstone.loop.remint_apply"
DOORS = ("whetstone.bakeoff.stratum", "whetstone.loop.heldout")

#: The apply step's functions, in the order the sheet must perform them.
STEPS = (
    "snapshot_corpus",
    "verify_staged",
    "swap_manifests",
    "rewrite_repo_url",
    "regenerate_ledger",
)

#: The tracked documents the derivation doors must write — the phase-4 commit's files.
TRACKED_DOCUMENTS = (
    ("whetstone.bakeoff.stratum", "tasks/stratum/easier.json"),
    ("whetstone.loop.heldout", "tasks/heldout/source-b.json"),
)

#: The second anchor every derivation path depends on: the branch's worktree, derived from
#: git's own words so the sheet never spells a `.claude/worktrees/<name>` path.
WORKTREE_EXPORT = "export WORKTREE="
WORKTREE_DERIVATION = "worktree list --porcelain"


def _anchored(value: str) -> bool:
    """Anchored: absolute, `$REPO/`-anchored, or `$WORKTREE/`-anchored.

    The shared `_is_anchored` knows `$REPO`; this sheet adds a second declared anchor —
    `$WORKTREE`, exported from git's own words before the first door runs — and a path
    under it is as absolute as one under `$REPO` by the same argument: an exported
    variable expands before the command starts.
    """
    return _is_anchored(value) or value.startswith("$WORKTREE/")


def _runbook() -> str:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert text.strip(), (
        f"{RUNBOOK} is empty, so every guard in this module would pass vacuously. A command "
        "sheet that parses into nothing proves nothing."
    )
    return text


def _apply_blocks(blocks: list[str]) -> list[str]:
    """Every bash block that invokes the apply machinery or a derivation door."""
    return [
        block
        for block in blocks
        if APPLY_MODULE in block or any(door in block for door in DOORS)
    ]


def _apply_paths(blocks: list[str]) -> list[str]:
    """Every slash-bearing token in the apply blocks, quotes stripped.

    The sheet writes paths inside `Path('$REPO/...')` and `--corpus "$REPO/..."`, so the
    quote characters are removed before tokenising. The shared `_named_paths` only
    collects anchored tokens — which is right for the prose lines it was written for, but
    a guard whose job is to *refuse* relative paths must see them first — so this
    collector takes every slash-bearing token and lets the anchored assertion decide.
    """
    found: list[str] = []
    for block in blocks:
        for line in block.splitlines():
            for token in line.replace("'", " ").replace('"', " ").replace("`", " ").split():
                token = token.strip("()`*,.:;")
                if "/" in token and not token.startswith("--"):
                    found.append(token)
    return found


def _flag_values(block: str, module: str) -> dict[str, list[str]]:
    """Flag → every value it was given, from the tokens after the module invocation."""
    tokens = shlex.split(block.partition(module)[2], posix=True)
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


def test_the_guard_shares_the_parse_helpers_it_can() -> None:
    """One parse implementation for the command-independent parts, imported by identity."""
    from test_gate_runbook_guards import STALE_WORKTREES as shared_stale
    from test_runbook_guards import _bash_blocks as shared_blocks
    from test_runbook_guards import _named_paths as shared_paths
    from test_runbook_guards import _worktree_name as shared_worktree

    assert _bash_blocks is shared_blocks
    assert _named_paths is shared_paths
    assert _worktree_name is shared_worktree
    assert STALE_WORKTREES is shared_stale


def test_the_parse_really_reads_the_sheets_commands() -> None:
    """Anti-vacuity: a renamed or emptied sheet must fail loudly rather than pass."""
    blocks = _bash_blocks(_runbook())
    apply_blocks = _apply_blocks(blocks)
    assert apply_blocks, (
        "WHY THIS IS A FAILURE: no bash block invokes the apply machinery. The sheet "
        "executes `whetstone.loop.remint_apply`'s functions and the two derivation doors; "
        "a sheet that names none of them guards nothing."
    )
    for step in STEPS:
        assert any(step in block for block in apply_blocks), (
            f"WHY THIS IS A FAILURE: no bash block names `{step}`. The apply step is "
            f"machinery, and a sheet that never invokes `{step}` cannot be the sheet the "
            "runbook describes."
        )
    for door in DOORS:
        assert any(door in block for block in blocks), (
            f"WHY THIS IS A FAILURE: no bash block invokes `{door}`. The re-derivations "
            "run through their established doors."
        )


def test_the_sheet_exports_the_anchor_every_path_depends_on() -> None:
    """`$REPO/...` is absolute only because the sheet makes it so."""
    assert "export REPO=/" in _runbook(), (
        "WHY THIS IS A FAILURE: the sheet anchors its paths to `$REPO` and never exports "
        "it. An unset variable expands to the empty string, so every anchored path "
        "resolves against whatever directory the operator happened to be in"
    )


def test_the_sheet_exports_the_worktree_anchor_from_gits_own_words() -> None:
    """`$WORKTREE` is the second anchor, derived from git — never a spelled worktree path.

    The apply machinery and the tracked documents live on the branch, so the sheet runs
    from the branch's worktree — but a sheet that spells `.claude/worktrees/<name>` sends
    the operator to a directory that is gone the moment the unit merges. The anchor is
    exported from `git worktree list --porcelain` instead (the `test_heldout_document.py`
    pattern), so the checkout is found with git's own words, and the no-worktree-named
    guard below still holds.
    """
    text = _runbook()
    assert WORKTREE_EXPORT in text, (
        "WHY THIS IS A FAILURE: the sheet anchors its derivation paths to `$WORKTREE` and "
        "never exports it. An unset variable expands to the empty string, so every "
        "worktree-anchored path resolves against the primary checkout"
    )
    assert WORKTREE_DERIVATION in text, (
        "WHY THIS IS A FAILURE: the sheet spells the worktree anchor rather than deriving "
        "it from `git worktree list --porcelain`. A spelled `.claude/worktrees/<name>` "
        "path is a directory that no longer exists after the unit merges"
    )
    assert "export WORKTREE=" in text.split(WORKTREE_DERIVATION)[0], (
        "WHY THIS IS A FAILURE: the worktree anchor is exported after it is first used, "
        "so the first anchored path expands to nothing"
    )


def test_every_path_the_apply_names_is_absolute_or_anchored() -> None:
    """A relative path is the failure that killed the measured arm on 2026-08-12.

    It applies to every path the apply blocks name, not only the written ones: the
    snapshot, the staged re-mint and the corpus are machine-level state addressed by
    absolute path, and a relative read resolved against the wrong CWD produces a refusal
    that looks like a missing file rather than a mistyped command.
    """
    paths = _apply_paths(_apply_blocks(_bash_blocks(_runbook())))
    assert paths, (
        "WHY THIS IS A FAILURE: no path parsed out of the apply blocks, so this guard "
        "would pass vacuously. Either the blocks are gone or the path spelling changed."
    )
    relative = sorted(path for path in paths if not _anchored(path))
    assert not relative, (
        f"WHY THIS IS A FAILURE: the apply blocks name relative path(s) {relative}. The "
        "sheet is run from a stated CWD, and a path that resolves against the wrong "
        "directory fails as a refusal about the machine state rather than the command"
    )


def test_the_sheet_snapshots_before_it_touches_the_corpus() -> None:
    """The snapshot is the reversibility guarantee, and it must land before the swap."""
    text = _runbook()
    blocks = _bash_blocks(text)
    snapshot = [block for block in blocks if "snapshot_corpus" in block]
    verify = [block for block in blocks if "verify_staged" in block]
    swap = [block for block in blocks if "swap_manifests" in block]

    assert snapshot and verify and swap, (
        "WHY THIS IS A FAILURE: the sheet is missing the snapshot, verification or swap "
        "step. The apply is snapshot → verify → swap → rewrite → regenerate, and a sheet "
        "that skips one of them is not the machinery's sheet"
    )
    assert text.index(snapshot[0]) < text.index(verify[0]) < text.index(swap[0]), (
        "WHY THIS IS A FAILURE: the swap appears before the snapshot or its verification. "
        "The pre-swap corpus is the evidence behind gate-001 and every portability "
        "figure; a sheet that moves files before the snapshot is taken cannot restore "
        "them (spec AC2, AC10)"
    )


def test_the_sheet_names_the_double_apply_halt() -> None:
    """A corpus root that already holds donor-a-* files is a named halt, never a re-run."""
    text = _runbook()
    assert "double-apply" in text, (
        "WHY THIS IS A FAILURE: the sheet never names the double-apply refusal. A second "
        "apply over an already re-minted corpus would replace verified bytes with the "
        "same bytes while pretending to move something — the operator must be told to "
        "stop and use the snapshot (spec AC10)"
    )
    assert "already holds donor-a" in text, (
        "WHY THIS IS A FAILURE: the sheet never states the refusal's trigger. The "
        "double-apply halt must name what the swap checks — donor-a-* manifests already "
        "present in the target root"
    )


def test_no_worktree_is_named_and_no_stale_one_survives() -> None:
    """Every worktree is deleted when its unit merges, so the sheet may name none."""
    text = _runbook()
    named = {
        name
        for line in text.splitlines()
        for path in _named_paths(line)
        if (name := _worktree_name(path)) is not None
    }

    assert named == set(), (
        f"WHY THIS IS A FAILURE: the sheet names worktree(s) {sorted(named)}. Worktrees "
        "are removed when their unit merges, so an operator running this sheet verbatim "
        "hits a directory that does not exist. The worktree anchor is derived from git "
        "instead"
    )
    stale = sorted(one for one in STALE_WORKTREES if one in text)
    assert not stale, (
        f"WHY THIS IS A FAILURE: the sheet still names {stale}, from an earlier unit. "
        "That directory does not hold the re-mint"
    )


def test_the_derivations_write_to_the_tracked_documents() -> None:
    """The doors' `--out` must land on the tracked paths the phase-4 commit carries.

    The stratum and held-out documents are the pre-committed pinned inputs; a door pointed
    at a gitignored or foreign destination would derive a document nobody commits, and the
    sheet's own final `git add` would then name files that do not exist. The out must be
    anchored (never relative) and must end at the tracked document.
    """
    blocks = _bash_blocks(_runbook())
    for module, tracked in TRACKED_DOCUMENTS:
        door_blocks = [block for block in blocks if module in block]
        assert door_blocks, f"WHY THIS IS A FAILURE: no bash block invokes `{module}`"
        outs = [
            value
            for block in door_blocks
            for flag, values in _flag_values(block, module).items()
            if flag == "--out"
            for value in values
        ]
        assert outs, f"WHY THIS IS A FAILURE: the `{module}` block passes no --out"
        for out in outs:
            assert _anchored(out), (
                f"WHY THIS IS A FAILURE: `{module}` is handed the relative --out {out!r}. "
                "A document written against the wrong CWD lands where the sheet never "
                "reads it"
            )
            assert out.endswith(tracked), (
                f"WHY THIS IS A FAILURE: `{module}` writes to {out!r}, not the tracked "
                f"document {tracked!r}. The phase-4 commit carries the tracked documents "
                "only"
            )