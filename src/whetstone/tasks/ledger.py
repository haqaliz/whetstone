"""The committed evidence for a corpus that is deliberately not committed.

**Why this file exists.** `/tasks/local/` is gitignored: source B is mined from the user's own
repositories, and their code never belongs in this one (CLAUDE.md's no-egress guardrail,
`tasks/README.md`). Left there, that would make the **pre-registered headline source** the one
source whose liveness no reader can check — "trust us, the other half was fine", which is the
same shape of hole this project exists to refuse (PRD § 3.1).

**How it closes.** Two artifacts, both committed, neither carrying any of the user's code:

- **the ledger** (`tasks/local-ledger.json`) — per proven task: a **hash** of the manifest, the
  two liveness verdicts, whether the executed set equalled the declared one, the skip count, the
  interpreter version, the tool versions, and the date;
- **the recipe** (`tasks/recipes/<donor>.json`) — how the corpus was derived: the donor, the
  commit its history was read at, the selection filters, the tool versions, the mining date, and
  the `pass_to_pass_scope` decision (D-A) that says what the corpus is *about*.

What that buys a reader who has none of the data: they can check that **every** claimed task was
proven live rather than assumed, count them, and re-derive the corpus themselves from the recipe
against their own copy of the donor. What it does not buy them is reproducing our instances
byte-for-byte, which is the honest cost of locality.

**Hashes and verdicts only — never contents.** No blob, no diff, no source line, in any field
including the free-text ones. `tests/test_ledger.py` walks the written JSON and asserts it
structurally, with a canary that proves the walk would see a leak if there were one. A record
that quietly carried a fragment of the user's code would be invisible in review and permanent in
the history, so it is asserted rather than intended.

**The clock is injected.** Every writer here takes a `clock`, because a committed file whose
bytes move for no reason produces a diff nobody can read — and because a test that called the
real clock would be asserting about the minute it ran in.

Zero runtime dependencies: `hashlib`, `json`, and `subprocess` for two `--version` calls. No
model, no network.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from whetstone import __version__
from whetstone.tasks.liveness import Liveness

#: Names the shape of the file so a later format change is a visible one rather than a silent
#: reinterpretation of an old file by new code.
LEDGER_SCHEMA = "whetstone-source-b-liveness/1"
RECIPE_SCHEMA = "whetstone-source-b-recipe/1"

#: A timestamp source. `str` rather than `datetime` so there is exactly one place a format is
#: decided, and so a caller pinning it in a test writes the same kind of value the real one does.
Clock = Callable[[], str]

#: How long git and uv are given to say their own version. Short: a `--version` that hangs is a
#: broken tool, not a slow one.
_VERSION_TIMEOUT = 30.0


def utc_now() -> str:
    """The current time, UTC, to the second. The default `Clock`.

    UTC and second precision because the field is evidence about when a mint ran, not a
    measurement: a local offset would make two operators' ledgers incomparable, and a microsecond
    would be a byte that differs between mints for no reason a reader cares about.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class LedgerEntry:
    """One proven task, as the ledger commits it. Evidence about a manifest, never the manifest.

    `manifest_sha256` is what stands in for the file. A reader who re-derives the corpus can
    compare their own manifest's hash against this one and know whether they reproduced it, and
    a reader who cannot re-derive it still knows the mint had *something* fixed in hand when it
    made these claims.

    The verdicts are stored as their string values rather than as `Status`, because this is a
    file format: a serialised enum member is a name that means whatever the code says it means
    today, and the ledger has to still read correctly when the code has moved on.
    """

    task_id: str
    manifest_sha256: str
    without_patch: str
    with_patch: str
    executed_matches_declared: bool
    skipped: int
    python: str
    tools: Mapping[str, str]
    proven_at: str


@dataclass(frozen=True)
class Recipe:
    """How a donor's corpus was derived — the procedure, never the output.

    `pass_to_pass_scope` is here because decision D-A narrowed what a mined task is *about*: each
    mint runs the held test files only, so `pass_to_pass` means "the other tests in these same
    files" rather than "the donor's suite". A reader who assumed the broader reading would
    overstate the corpus, and would have no way to discover the mistake. It is a field rather
    than a footnote for exactly that reason.

    `donor_head` records the commit the history was read at, so a re-derivation runs against the
    same history rather than against whatever the donor has grown since.

    `donor` is an **operator-chosen label, never a path and never the donor's own name.** This
    document is committed; the donor is one of the user's private repositories. An absolute path
    from the author's machine is of no use to a reader re-deriving the corpus against their own
    donor, and the repository's name is theirs rather than this project's to publish. The label
    only has to be stable, so that two mints of the same donor are recognisably the same donor.
    """

    donor: str
    donor_head: str
    selection: Mapping[str, str]
    pass_to_pass_scope: str
    tools: Mapping[str, str]
    python: str
    mined_at: str


def record(
    manifest: Path,
    liveness: Liveness,
    *,
    python: str,
    tools: Mapping[str, str],
    clock: Clock = utc_now,
) -> LedgerEntry:
    """One ledger entry for a task that has been proven live.

    Takes the manifest **path** and hashes its bytes rather than taking a `Task`: what a reader
    re-derives and compares is a file, and a hash of a reconstructed object would attest to this
    process's serialisation rather than to what is on disk.
    """
    return LedgerEntry(
        task_id=liveness.task_id,
        manifest_sha256=hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
        without_patch=liveness.without_patch.value,
        with_patch=liveness.with_patch.value,
        executed_matches_declared=liveness.executed_matches_declared,
        skipped=liveness.skipped,
        python=python,
        tools=dict(tools),
        proven_at=clock(),
    )


def write_ledger(path: Path, entries: Sequence[LedgerEntry]) -> None:
    """Write the ledger, sorted by task id, with a trailing newline.

    Sorted and indented so the committed file diffs line by line: the ledger's whole value is
    that a reader can check it, and a single-line JSON blob is a file nobody reviews.
    """
    document = {
        "schema": LEDGER_SCHEMA,
        "tasks": [asdict(entry) for entry in sorted(entries, key=lambda entry: entry.task_id)],
    }
    Path(path).write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")


def read_ledger(path: Path) -> tuple[LedgerEntry, ...]:
    """Read a ledger back, or raise `ValueError` naming the file.

    Fail-closed like `load_task`: a ledger that half-parsed would let a mint append to a record
    it had already lost part of, and the lost part would be evidence.
    """
    location = Path(path)
    try:
        raw = json.loads(location.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"ledger {str(location)!r} could not be read: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("tasks"), list):
        raise ValueError(
            f"ledger {str(location)!r} is not a liveness ledger: expected an object with a "
            f"'tasks' list"
        )
    try:
        return tuple(LedgerEntry(**entry) for entry in raw["tasks"])
    except TypeError as exc:
        raise ValueError(f"ledger {str(location)!r} carries a malformed entry: {exc}") from exc


def write_recipe(path: Path, recipe: Recipe) -> None:
    """Write one donor's recipe, in the same reviewable shape as the ledger."""
    document = {"schema": RECIPE_SCHEMA, **asdict(recipe)}
    location = Path(path)
    location.parent.mkdir(parents=True, exist_ok=True)
    location.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")


def tool_versions() -> Mapping[str, str]:
    """The versions behind a mint: git, uv, and whetstone itself.

    Read from the tools rather than declared, because a declared version is a claim about the
    machine that nobody checked. A tool that cannot report its version records that fact rather
    than raising: a missing version is a gap in the evidence, and a mint that already produced
    proven tasks should not be thrown away over one of them.
    """
    return {
        "git": _version(["git", "--version"]),
        "uv": _version(["uv", "--version"]),
        "whetstone": __version__,
    }


def _version(argv: list[str]) -> str:
    """One tool's `--version`, first line only, or a recorded absence."""
    try:
        completed = subprocess.run(
            argv, capture_output=True, text=True, timeout=_VERSION_TIMEOUT, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"unavailable: {exc}"
    if completed.returncode != 0:
        return f"unavailable: {argv[0]} exited {completed.returncode}"
    return completed.stdout.strip().splitlines()[0] if completed.stdout.strip() else "unavailable"


__all__ = [
    "LEDGER_SCHEMA",
    "RECIPE_SCHEMA",
    "Clock",
    "LedgerEntry",
    "Recipe",
    "read_ledger",
    "record",
    "tool_versions",
    "utc_now",
    "write_ledger",
    "write_recipe",
]
