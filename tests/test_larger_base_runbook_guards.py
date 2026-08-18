"""Guards over the larger-base-arm runbook, so its commands cannot drift from the code they run.

`docs/planning/larger-base-arm/runbook.md` is the operator's command sheet for the larger-base
arm: the operator executes its probe pass and its arm command verbatim, and a later agent
executes its post-run commands verbatim (spec in-scope, plan Phase 2). A command sheet that
disagrees with the code it runs fails at night, in a run nobody can undo, so the disagreements
are refused here first.

**This module is the A1-style extension, not a parameterization.** The probe guard
(`tests/test_probe_runbook_guards.py`) is a frozen historical pin — its sheet is the executed
easier-stratum probe, superseded by this unit's sheet — so it is left byte-untouched and the
parse helpers are imported from it **by identity**: one parse implementation, shared, matching
the repo's identity discipline (`diffcheck` imports `classify_completion` by identity; the
probe guard imports the measured-arm module's helpers by identity). The helpers are
text-parameterized — every one takes the runbook text or its parsed blocks as its argument —
so only what a second sheet legitimately re-binds is re-bound here: `RUNBOOK`,
`STALE_WORKTREES`, and the A2 candidate-resolution pin that is this sheet's own.

Beyond the seven properties the measured-arm module guards — writable paths absolute, every
arm flag in `build_parser()`, worktree-shaped `uv run --project` targets, exactly one worktree
named everywhere, the arm's CWD at the primary checkout, no stale worktree names, and an
anti-vacuity parse re-pointed at this arm's shape — this module pins four things this sheet
owns: the A2 resolution rule (the 32B retained and named in the resolution block, the 7B
excluded and in no `--only` value, the zero-ceiling rule stated), the probe-pass-first rule
(D7's timing pass gates the arm and precedes it), the restored dev overlay (every declared
`--dev-subset` id is stated in the dev section and is a member of the committed stratum
document's `corpus` — non-vacuous on the full declared set), and the mandatory pre-analysis
extension over **all five** autopsy documents.

**Watched failing first** (CONTRIBUTING.md:56-60): this module was written with `RUNBOOK`
bound to the probe sheet as it exists and `feat-stratum-probe-execution` already in
`STALE_WORKTREES`, and the stale-name test refuses that sheet before the new one exists.
"""

from __future__ import annotations

import shlex
from pathlib import Path

import test_probe_runbook_guards as guards
from test_runbook_guards import PROJECT_TARGET

from whetstone.bakeoff import run
from whetstone.bakeoff.run import build_parser
from whetstone.bakeoff.stratum import read_document

RUNBOOK = Path(__file__).parent.parent / "docs/planning/larger-base-arm/runbook.md"
STRATUM_DOC = Path(__file__).parent.parent / "tasks/stratum/easier.json"
STALE_WORKTREES = (
    "feat-measured-arm-run",
    "feat-p2-format-hardening",
    "feat-format-hardening-measurement",
    "feat-p2-easier-stratum",
    "feat-stratum-probe-execution",
)
RETAINED = ("mlx-community/Qwen2.5-Coder-32B-Instruct-4bit",)
EXCLUDED = "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"
FIVE_AUTOPSY_STEMS = (
    "arm-a",
    "budget-2048",
    "format-hardening-arm-evidence",
    "easier-stratum-evidence",
    "larger-base-arm-evidence",
)

_bash_blocks = guards._bash_blocks
_arm_block = guards._arm_block
_arm_flags = guards._arm_flags
_arm_values = guards._arm_values
_named_paths = guards._named_paths
_worktree_name = guards._worktree_name
_arm_cwd_line = guards._arm_cwd_line
_arm_only_values = guards._arm_only_values
_resolution_block = guards._resolution_block
_dev_block = guards._dev_block
_dev_subset_values = guards._dev_subset_values
ARM_MODULE = guards.ARM_MODULE


def _runbook() -> str:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert text.strip(), (
        f"{RUNBOOK} is empty, so every guard in this module would pass vacuously. "
        "A command sheet that parses into nothing proves nothing."
    )
    return text


def _probe_block(blocks: list[str]) -> str:
    """The block carrying D7's timing sample: the run-door invocation with `--probe`."""
    return next((block for block in blocks if "--probe" in block), "")


def _preanalysis_block(blocks: list[str]) -> str:
    """The block invoking the pre-analysis extension, which must cover all five documents."""
    return next((block for block in blocks if "whetstone.bakeoff.preanalysis" in block), "")


def test_the_guard_imports_its_parse_helpers_by_identity() -> None:
    """The A1-style discipline: one parse implementation, imported, never copied.

    Each helper is the probe module's own object, so a fix that lands in the shared helpers is
    seen by both runbooks' guards — and a second, drifting copy cannot be introduced here.
    """
    assert _bash_blocks is guards._bash_blocks
    assert _arm_block is guards._arm_block
    assert _arm_flags is guards._arm_flags
    assert _arm_values is guards._arm_values
    assert _named_paths is guards._named_paths
    assert _worktree_name is guards._worktree_name
    assert _arm_cwd_line is guards._arm_cwd_line
    assert _arm_only_values is guards._arm_only_values
    assert _resolution_block is guards._resolution_block
    assert _dev_block is guards._dev_block
    assert _dev_subset_values is guards._dev_subset_values


def test_the_parse_really_reads_the_runbooks_command() -> None:
    """Anti-vacuity: an empty or silently renamed file must fail loudly, not pass.

    A guard that parsed no blocks would assert absence on nothing. The arm command's three
    signature flags must come out of the parse, and the sheet as a whole must still carry the
    D7 timing pass — proving the blocks being guarded are the runbook's own.
    """
    blocks = _bash_blocks(_runbook())
    assert blocks, (
        "no bash fenced block parsed out of the runbook, so every guard in this module would "
        "pass vacuously. Either the fence style changed or the command sections are gone."
    )
    arm = _arm_block(blocks)
    assert arm, (
        "no bash block invokes `python -m whetstone.bakeoff.run`, so the flag guard has "
        "nothing to check. A renamed module would pass every absence below."
    )
    text = _runbook()
    assert "--retries" in arm, "the arm command no longer carries the switch that defines this run"
    assert "--only" in arm, "the arm command no longer names its candidate restriction"
    assert "--dev-subset" in arm, "the arm command no longer names its dev overlay"
    assert "--probe" in text, "the runbook no longer names the D7 timing pass that gates the arm"
    assert "--stratum" not in text, (
        "the runbook names the stratum document: this arm scores the full declared source-B "
        "set, and a surviving stratum flag would restrict the run to the band"
    )


def test_the_arm_commands_writable_paths_are_absolute() -> None:
    """The arm's `--out`, `--workspace`, `--journal` and `--transcript` are absolute paths.

    The workspace is built as `workspace / digest` and provisioned by subprocesses whose CWD
    is not the run's (`run.py:546`): a relative workspace does not resolve there, every
    environment build fails, every rollout is `UNPROVISIONED`, and the control arm proves
    nothing — the measured arm died exactly this way on 2026-08-12 (`HarnessNotProven`,
    `measured-arm/finding.md:31-45`). The same class covers the run's other writable paths:
    absolute means no part of the run depends on CWD.
    """
    values = _arm_values(_arm_block(_bash_blocks(_runbook())))
    for flag in ("--out", "--workspace", "--journal", "--transcript"):
        value = values.get(flag)
        assert value, f"the arm command does not pass {flag}, so its path is unstated"
        assert value.startswith("/"), (
            f"the arm command passes {flag} a relative path {value!r}: the environment "
            "builder and its subprocesses do not share the run's CWD, so the path does not "
            "resolve there and every task is UNPROVISIONED — a night that proves nothing"
        )


def test_every_flag_the_arm_command_passes_exists_in_the_parser() -> None:
    """The permanent drift guard: the sheet and `build_parser` cannot disagree.

    Every flag the arm command hands to `python -m whetstone.bakeoff.run` must still be
    accepted by it, else the operator's night ends in a usage error. The parser side is pinned
    too: `--retries`, `--only` and `--dev-subset` must be present, proving this guard really
    saw the parser and not an empty one.
    """
    arm = _arm_block(_bash_blocks(_runbook()))
    assert arm
    parser_flags = {name for name in build_parser()._option_string_actions if name.startswith("--")}
    for flag in ("--retries", "--only", "--dev-subset"):
        assert flag in parser_flags, (
            f"the parser this guard checks does not accept `{flag}`, so either the import did "
            "not see the real `build_parser` or this arm's defining surface was removed"
        )
    unknown = _arm_flags(arm) - parser_flags
    assert not unknown, (
        f"the arm command passes flag(s) the parser does not accept: {sorted(unknown)}. "
        "A renamed or dropped flag aborts the run at parse time, after the night is committed."
    )


def test_every_project_target_is_a_worktree_shaped_path() -> None:
    """A `uv run --project` must point at a `.claude/worktrees/<name>` checkout, nothing else.

    The post-run commands execute the worktree's branch code by its project; a target that is
    not a worktree path (a primary checkout, a scratch directory) would run some other tree's
    code and the run's records would not correspond to what it executed.
    """
    targets = [
        match.group(1).rstrip("\\")
        for block in _bash_blocks(_runbook())
        for match in PROJECT_TARGET.finditer(block)
    ]
    assert targets, (
        "no `uv run --project` target parsed out of the runbook, so the worktree-structure "
        "guards have nothing to check"
    )
    for target in targets:
        name = _worktree_name(Path(target))
        assert name, f"{target!r} is not a `.claude/worktrees/<name>` path"


def test_the_runbook_names_exactly_one_worktree_everywhere() -> None:
    """The arm's CWD line and every post-run `--project` target must name the same worktree.

    The stale measured-arm runbook named one branch where the arm runs and another in every
    post-run target: the arm would write its `--out`, workspace and evidence into one checkout
    while the post-run commands read another, and the before/after comparison would compare
    two different trees' records.
    """
    text = _runbook()
    names = {
        name
        for block in _bash_blocks(text)
        for match in PROJECT_TARGET.finditer(block)
        for name in [_worktree_name(Path(match.group(1).rstrip("\\")))]
        if name is not None
    }
    cwd_line = _arm_cwd_line(text)
    assert cwd_line, "no line above the arm command names a worktree, so its CWD is unstated"
    cwd_names = {
        name
        for path in _named_paths(cwd_line)
        for name in [_worktree_name(path)]
        if name is not None
    }
    assert cwd_names, "the arm command's CWD line names no `.claude/worktrees/<name>` path"
    assert len(names | cwd_names) == 1, (
        f"the runbook names {sorted(names | cwd_names)}: the arm would write into one checkout "
        "while the post-run commands read another. Every command must name the same worktree"
    )


def test_the_arm_command_runs_from_the_primary_checkout() -> None:
    """CWD at the primary repo root, never at the worktree (the 54bea44 pattern).

    The run's `--out`, workspace, journal and transcript are absolute `runs/` paths: executed
    from the worktree they land in the worktree's store, which the post-run commands (run from
    the primary) do not read. The primary is derived structurally — the checkout a
    `.claude/worktrees/<name>` path lives under is its ancestor three components up — and
    asserted by name only, never as an existing path on this machine.
    """
    cwd_line = _arm_cwd_line(_runbook())
    worktrees = [path for path in _named_paths(cwd_line) if _worktree_name(path) is not None]
    assert worktrees, "the arm command's CWD line names no `.claude/worktrees/<name>` path"
    primary = worktrees[0].parents[2]
    assert primary in set(_named_paths(cwd_line)), (
        f"the arm command's CWD line names the worktree {worktrees[0]} but not the primary "
        f"checkout it lives under ({primary}); run from the worktree, the absolute runs/ "
        "paths land in the wrong store while the post-run commands read the primary's"
    )


def test_no_stale_worktree_name_survives_anywhere() -> None:
    """The stale branch names are gone, everywhere, not just from the commands.

    The refresh moves the runbook onto the unit's worktree; a surviving mention of any old
    name is a command that runs the wrong checkout's code — or a reader pointed at a branch
    that no longer exists. Checked over the whole file, so an edit that fixed the commands
    but left the prose naming the old worktrees still fails.
    """
    text = _runbook()
    found = [name for name in STALE_WORKTREES if name in text]
    assert not found, (
        f"the runbook still names stale worktree(s): {found}. The arm runs the branch code "
        "this repository actually points at; a stale name runs a checkout that is not the one "
        "being measured"
    )


def test_the_resolution_block_names_and_excludes_the_candidates() -> None:
    """The A2 rule: the sheet and the resolution it was decided on cannot disagree.

    The arm's `--only` values must equal the retained candidate, and it must be a name the
    resolution block records; the excluded candidate must be named in the resolution block and
    in no `--only` value; and the block must state the pre-committed exclusion rule (a
    measured zero retry-eligible ceiling excludes by name, `prd.md:93-103`) and that the
    retained candidate has no measured ceiling for it to apply to — so a sheet that starts
    scoring the excluded candidate, or drops the retained one, is refused here, before the
    night.
    """
    resolution = _resolution_block(_runbook())
    assert resolution, (
        "the runbook has no resolution block, so the candidate set is unpinned: the arm's "
        "--only flags could name anything and this guard would not know"
    )
    only_values = _arm_only_values(_arm_block(_bash_blocks(_runbook())))
    assert only_values, (
        "the arm command passes no --only flag, so the candidate set is unstated: a run "
        "that sweeps every candidate spends the excluded one's share and this guard cannot "
        "tell"
    )
    assert only_values == set(RETAINED), (
        f"the arm command's --only values {sorted(only_values)} are not the retained candidate "
        f"{list(RETAINED)} recorded in the resolution block"
    )
    for name in RETAINED:
        assert name in resolution, (
            f"the retained candidate {name!r} is scored by --only but never named in the "
            "resolution block, so the sheet's candidate set is not the resolved one"
        )
    assert EXCLUDED in resolution, (
        f"the excluded candidate {EXCLUDED!r} is not named in the resolution block, so the "
        "exclusion this run was decided on is unstated"
    )
    assert EXCLUDED not in only_values, (
        f"the arm command scores {EXCLUDED!r}, the candidate whose measured zero ceiling "
        "excluded it by name (prd.md:93-103)"
    )
    assert "ceiling 0" in resolution, (
        "the resolution block no longer states the zero-ceiling rule the exclusion was "
        "decided on"
    )
    assert "no measured ceiling" in resolution, (
        "the resolution block no longer states that the retained candidate has no measured "
        "ceiling, so the rule's non-application to it is unstated"
    )


def test_the_probe_pass_precedes_the_arm_command() -> None:
    """D7's timing pass gates the night and must come before the arm command.

    The arm proceeds only if the probe completes on all N sampled tasks within the stated
    headroom; a sheet that lost the pass, or fused it into the arm, spends a night before the
    capacity verdict exists — or derives not one verdict if the fused run carries `--probe`.
    """
    blocks = _bash_blocks(_runbook())
    probe = _probe_block(blocks)
    assert probe, (
        "no bash block carries --probe, so the D7 timing pass is unpinned: the arm can no "
        "longer be gated on a measured capacity verdict"
    )
    arm = _arm_block(blocks)
    assert arm, "no bash block invokes the arm"
    assert "--probe" not in arm, (
        "the arm command itself carries --probe: a probe publishes cost and no counts, so a "
        "night run with the flag would derive not one verdict — the two modes must not fuse"
    )
    assert blocks.index(probe) < blocks.index(arm), (
        "the probe pass does not precede the arm command: the capacity verdict must gate the "
        "night before it is committed"
    )


def test_the_stratum_loader_is_run_imports_by_identity() -> None:
    """The guard reads the corpus with the loader the run consumes, never a copy.

    `conduct` excludes the declared dev ids from both sources before anything runs
    (`run.py:540-542`), and `_partition` refuses a declared dev id that matches nothing in the
    resulting universe (`UnknownDevSubset`). The guard must therefore read the committed
    document with the very loader the run uses — one parse implementation, by identity,
    matching the repo's discipline (`run.read_document is read_document`).
    """
    assert run.read_document is read_document


def test_every_declared_dev_id_is_a_corpus_member() -> None:
    """A `--dev-subset` id that matches no loaded task dies at launch, never excludes.

    The dev overlay is declared against the full declared source-B set — the stratum
    document's 66-id `corpus` — so membership is the non-vacuous test: an id outside the
    corpus matches nothing in the loaded universe, and the harness refuses the declaration by
    name (`UnknownDevSubset`). The probe sheet's vacuous declaration died exactly this way on
    2026-08-15, against the stratum-filtered universe; on the full set the restored overlay
    must resolve the same way, against the corpus.
    """
    arm = _arm_block(_bash_blocks(_runbook()))
    declared = _dev_subset_values(arm)
    assert declared, (
        "the arm command declares no --dev-subset id, so the dev overlay is unstated: the "
        "five declared ids must exclude their tasks from both sources, or the counts they "
        "would have moved are published as scored"
    )
    corpus = set(read_document(STRATUM_DOC).corpus)
    outside = declared - corpus
    assert not outside, (
        f"the arm command declares dev id(s) {sorted(outside)} that are not members of the "
        "committed stratum document's corpus: they match no loaded task and the run dies at "
        "launch with UnknownDevSubset. Drop them or move them into the corpus"
    )


def test_every_declared_dev_id_is_stated_in_the_dev_section() -> None:
    """The restored overlay must be the sheet's declared overlay, stated in the sheet.

    An arm that declares ids the dev section never names is an overlay the operator cannot
    have checked; a section that names ids the arm never declares is a history that reads as a
    decision. The two must agree, over the whole dev section's prose.
    """
    arm = _arm_block(_bash_blocks(_runbook()))
    declared = _dev_subset_values(arm)
    dev = _dev_block(_runbook())
    assert dev, (
        "the arm command declares a dev subset and the runbook has no dev-subset section, so "
        "the overlay is unexplained: a sheet that declares ids must name them and their "
        "resolution"
    )
    missing = sorted(task_id for task_id in declared if task_id not in dev)
    assert not missing, (
        f"the dev-subset section does not state declared id(s) {missing}: the arm's overlay "
        "is not the sheet's declared overlay"
    )


def test_the_autopsy_document_stem_matches_the_journal_run_name() -> None:
    """The comparison matches the journal and autopsy by run name, and refuses a mismatch.

    Observed in the field on 2026-08-18: the arm's post-run chain wrote the autopsy to
    `runs/diff-autopsy/larger-base-evidence.json` while the journal lived in
    `runs/larger-base-arm-evidence/`, and the comparison refused by name — "the journal and
    autopsy runs do not match". The run name is the autopsy document's own: its `--out`
    filename stem, which must equal the arm journal's parent directory name.
    """
    arm = _arm_block(_bash_blocks(_runbook()))
    journal = _arm_values(arm, "--journal")
    assert len(journal) == 1, (
        f"the arm block names {len(journal)} journal path(s), not one: the run name the "
        "comparison matches against is the journal's parent directory"
    )
    run_name = Path(journal[0]).parent.name
    blocks = _bash_blocks(_runbook())
    autopsy = next((b for b in blocks if "whetstone.bakeoff.autopsy" in b), None)
    assert autopsy, (
        "no bash block invokes whetstone.bakeoff.autopsy, so the arm's autopsy document is "
        "unpinned: the comparison matches the journal and autopsy by run name"
    )
    tokens = shlex.split(autopsy.partition("whetstone.bakeoff.autopsy")[2], posix=True)
    outs = [
        tokens[index + 1]
        for index, token in enumerate(tokens)
        if token == "--out" and index + 1 < len(tokens)
    ]
    assert len(outs) == 1, f"the autopsy block names {len(outs)} --out path(s), not one"
    stem = Path(outs[0]).stem
    assert stem == run_name, (
        f"the autopsy document's stem {stem!r} does not match the journal's run name "
        f"{run_name!r}: the comparison refuses the mismatch by name, and the run's own "
        "evidence cannot be read"
    )


def test_the_preanalysis_extension_covers_all_five_autopsy_documents() -> None:
    """The mandatory extension must name all five documents, and exactly those five.

    The comparison asserts the trigger mapping against the pre-analysis document's per-run
    decisions, and a run without declared decisions is refused by name (`comparison.py:548-557`).
    The stored ceiling covers only the two stored runs, so the arm's post-run chain requires
    the extended document over the two stored runs' documents, the format-hardening arm's, the
    easier-stratum probe's and this arm's — nothing fewer, nothing more.
    """
    block = _preanalysis_block(_bash_blocks(_runbook()))
    assert block, (
        "no bash block invokes whetstone.bakeoff.preanalysis, so the mandatory extension is "
        "unpinned: the comparison's per-run decisions assertion would refuse the run"
    )
    tokens = shlex.split(block.partition("whetstone.bakeoff.preanalysis")[2], posix=True)
    documents = {
        tokens[index + 1]
        for index, token in enumerate(tokens)
        if token == "--autopsy" and index + 1 < len(tokens)
    }
    assert len(documents) == len(FIVE_AUTOPSY_STEMS), (
        f"the pre-analysis extension passes {len(documents)} autopsy document(s), not the "
        f"five the comparison's per-run decisions assertion requires"
    )
    for stem in FIVE_AUTOPSY_STEMS:
        assert any(Path(document).name == f"{stem}.json" for document in documents), (
            f"the pre-analysis extension does not name {stem}.json: the comparison's per-run "
            "decisions assertion needs every stored run's document plus this arm's"
        )
