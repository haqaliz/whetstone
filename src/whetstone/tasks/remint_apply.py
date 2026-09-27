"""The #62 re-mint as an apply step: snapshot, verify, swap, rewrite, regenerate — as code.

The machine corpus (`tasks/local/`) is the evidence behind `gate-001` and every portability
figure, and the #62 pairing requires it to be swapped to the staged re-mint — ids
`donor-a-*` / `donor-b-*`, a provably identical commit set (same sha12s, same heads,
differing only in `task_id`, `provenance.donor`, `repo_url`) — so the donor's arbitrary
label stops deciding the split. The staged re-mint is the reference; applying it is an
operator step that must be scripted, guarded, snapshot-protected, and reversible
(`docs/planning/heldout-scorable/rederivation/spec.md` AC1-AC6, AC10). This module is the
step as five functions, each of which returns the state it changed:

1. **`snapshot_corpus`** copies the pre-swap manifests and the committed ledger into a
   declared, gitignored location and writes a verification manifest (`snapshot.json`) — the
   old ids, their sha12s (the first twelve hex of each `base_commit`), each manifest's own
   sha256, and the ledger's digest. Nothing is touched before it.
2. **`verify_staged`** checks the staged re-mint against the snapshot: the count, the
   `donor-a-*` / `donor-b-*` label-form ids (each id must embed its manifest's own sha12),
   the commit set (identical, not merely overlapping), and the staged ledger's count and
   id set. Any mismatch is a named refusal **before any file moves**.
3. **`swap_manifests`** replaces each corpus root's manifests with the staged ones and
   removes the old-id files, so each root ends holding exactly the re-minted set — the
   loader reads a whole directory and nothing is skipped. A target that already holds
   `donor-a-*` files is a named refusal to double-apply.
4. **`rewrite_repo_url`** rewrites exactly one field in each applied manifest — `repo_url`
   to the declared real donor path the pre-swap corpus used (the staging donors are copies
   at the same heads; the corpus's convention is the real path). The rewrite is read back
   and asserted to have changed nothing else; a declared donor path that does not exist is
   a named refusal.
5. **`regenerate_ledger`** re-hashes the applied manifests into the staged ledger's evidence
   through `tasks.ledger`'s own `read_ledger`/`write_ledger` by identity — a hand-rolled
   JSON emit would be a second ledger contract. The regenerated entries differ from the
   staged ledger's only in `manifest_sha256`.

The staged re-mint mirrors the machine corpus home: the staged manifests live under
`<staged>/local/donor-{a,b}` and the staged ledger at `<staged>/local-ledger.json` — the
same shape `tasks/local/` and `tasks/local-ledger.json` have in the primary checkout. All
paths are absolute (the runbook's discipline); the phase-4 runbook invokes these functions
verbatim after the guard suite passes.

The re-derivations run through the same doors the originals used — `bakeoff.stratum.main`
and `loop.heldout.main`, imported by identity, invoked with absolute corpus paths and
`--out` at the tracked destination. A door that exits nonzero is a named refusal carrying
the door's own words; an unreadable donor is refused by name by the door's own fail-closed
loader, never worked around. The heldout door reads the committed stratum document at
`tasks/stratum/easier.json` relative to its CWD, which is why the sheet runs it from the
worktree root after the stratum re-derivation has written the new document there.

Zero runtime dependencies beyond the repo's own modules and stdlib: no model, no network.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import re
import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from whetstone.bakeoff import stratum
from whetstone.loop import heldout
from whetstone.tasks.ledger import Clock, read_ledger, utc_now, write_ledger
from whetstone.tasks.manifest import load_tasks
from whetstone.verify.task import Task

#: Names the snapshot's verification manifest, so a later shape change is a visible one
#: rather than a silent reinterpretation of an old snapshot by new code.
SNAPSHOT_SCHEMA = "whetstone-pre-remint-snapshot/1"

#: The two donor labels the staged re-mint carries. A manifest id must be
#: `<label>-<sha12 of its base_commit>` or the re-mint is not the provably-identical set.
DONOR_LABELS = ("donor-a", "donor-b")

#: The staged re-mint's layout, mirroring the machine corpus home: manifests under
#: `<staged>/local/`, the staged ledger at `<staged>/local-ledger.json`.
_STAGED_MANIFESTS = "local"
_STAGED_LEDGER = "local-ledger.json"

#: A staged label-form manifest filename: `donor-a-<12 hex>.json` (or donor-b).
_DONOR_FILE = re.compile(r"^(donor-[ab])-[0-9a-f]{12}\.json$")


class RemintRefusal(ValueError):
    """The apply step refused by name: a mismatch, a missing path, a double-apply.

    Raised before anything moves when a check fails, so a refused step has changed no
    machine state. The message names the offending id, path or count.
    """


@dataclass(frozen=True)
class VerifyRecord:
    """What the verification established: the total and the per-label counts."""

    total: int
    by_label: Mapping[str, int]


@dataclass(frozen=True)
class SwapRecord:
    """What the swap moved: the manifests added and the old-id files removed, per file."""

    added: tuple[Path, ...]
    removed: tuple[Path, ...]


@dataclass(frozen=True)
class _SnapshotTask:
    """One manifest's record in the snapshot's verification manifest."""

    id: str
    sha12: str
    commit: str
    sha256: str


def snapshot_corpus(
    corpus: Sequence[Path],
    ledger_path: Path,
    out: Path,
    *,
    clock: Clock = utc_now,
) -> Path:
    """Copy the pre-swap corpus and the committed ledger into `out`, and write the
    verification manifest.

    Every manifest is loaded through `tasks.manifest.load_task` before it is copied — the
    snapshot is fail-closed like the corpus loader, nothing skipped — and each is recorded
    with its task id, its sha12 (the first twelve hex of `base_commit`), its full commit,
    and its own sha256, so a reader can verify the snapshot against the copies by rehashing.
    The ledger's bytes are copied beside the manifests and digested. An `out` that already
    holds anything is refused: a second snapshot would silently overwrite the first, and the
    first is the reversibility guarantee (spec AC10).
    """
    location = Path(out)
    if location.exists() and any(location.iterdir()):
        names = sorted(entry.name for entry in location.iterdir())
        raise RemintRefusal(
            f"the snapshot destination {str(location)!r} already holds state "
            f"({names!r}); a second snapshot would overwrite the first, and the first "
            "snapshot is the reversibility guarantee for the pre-swap corpus. Point the "
            "snapshot at a fresh location"
        )
    manifests_dir = location / "manifests"
    recorded: list[_SnapshotTask] = []
    for root in corpus:
        root_dir = Path(root)
        if not root_dir.is_dir():
            raise RemintRefusal(
                f"the pre-swap corpus root {str(root_dir)!r} does not exist; a snapshot of "
                "nothing would verify nothing"
            )
        target_dir = manifests_dir / root_dir.name
        target_dir.mkdir(parents=True, exist_ok=True)
        for entry in sorted(root_dir.iterdir()):
            if not entry.is_file():
                raise RemintRefusal(
                    f"the pre-swap corpus root {str(root_dir)!r} contains {entry.name!r}, "
                    "which is not a manifest file; nothing is skipped, because a skipped "
                    "manifest is a missing denominator"
                )
            try:
                task = load_tasks(entry)[0]
            except ValueError as exc:
                raise RemintRefusal(
                    f"the pre-swap corpus refused to load {entry.name!r}: {exc}"
                ) from exc
            shutil.copy2(entry, target_dir / entry.name)
            recorded.append(
                _SnapshotTask(
                    id=task.task_id,
                    sha12=task.base_commit[:12],
                    commit=task.base_commit,
                    sha256=hashlib.sha256(entry.read_bytes()).hexdigest(),
                )
            )
    try:
        ledger_bytes = Path(ledger_path).read_bytes()
    except OSError as exc:
        raise RemintRefusal(
            f"the committed ledger {str(ledger_path)!r} could not be read: {exc}"
        ) from exc
    try:
        count = len(read_ledger(ledger_path))
    except ValueError as exc:
        raise RemintRefusal(
            f"the committed ledger {str(ledger_path)!r} could not be read: {exc}"
        ) from exc
    (location / _STAGED_LEDGER).write_bytes(ledger_bytes)
    document = {
        "schema": SNAPSHOT_SCHEMA,
        "captured_at": clock(),
        "ledger": {"sha256": hashlib.sha256(ledger_bytes).hexdigest(), "tasks": count},
        "tasks": [asdict(task) for task in sorted(recorded, key=lambda task: task.id)],
    }
    (location / "snapshot.json").write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n"
    )
    return location


def _read_snapshot(snapshot: Path) -> tuple[_SnapshotTask, ...]:
    """The snapshot's verification manifest, or a named refusal."""
    location = Path(snapshot)
    try:
        raw = json.loads((location / "snapshot.json").read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RemintRefusal(
            f"the snapshot at {str(location)!r} could not be read: {exc}"
        ) from exc
    if not isinstance(raw, dict) or raw.get("schema") != SNAPSHOT_SCHEMA:
        raise RemintRefusal(
            f"the snapshot at {str(location)!r} does not declare schema "
            f"{SNAPSHOT_SCHEMA!r}; a snapshot of another shape verifies nothing"
        )
    tasks = raw.get("tasks")
    if not isinstance(tasks, list) or not all(
        isinstance(task, dict) and {"id", "sha12", "commit", "sha256"} <= task.keys()
        for task in tasks
    ):
        raise RemintRefusal(
            f"the snapshot at {str(location)!r} carries a malformed tasks list; a snapshot "
            "whose manifest record cannot be read verifies nothing"
        )
    return tuple(_SnapshotTask(**task) for task in tasks)


def verify_staged(snapshot: Path, staged: Path) -> VerifyRecord:
    """Verify the staged re-mint against the snapshot, or refuse by name — before any move.

    The checks are each asserted: the staged manifest count equals the snapshot's; every
    staged id is `donor-a-*` / `donor-b-*` **and** embeds its own manifest's sha12 (the
    label-form id is the re-mint's claim about which commit it carries); the staged commit
    set is *identical* to the snapshot's, not merely overlapping — a single changed commit
    breaks the "provably identical commit set" claim; and the staged ledger carries the same
    count and the same id set as the staged manifests, read through `tasks.ledger`'s own
    loader by identity. Any mismatch is a `RemintRefusal` naming the offending id or count,
    raised before any file moves.
    """
    raw = _read_snapshot(snapshot)
    old_tasks = raw
    old_commits = {task.commit for task in old_tasks}

    staged_tasks: list[tuple[Task, Path]] = []
    for label in DONOR_LABELS:
        root = Path(staged) / _STAGED_MANIFESTS / label
        if not root.is_dir():
            raise RemintRefusal(
                f"the staged re-mint has no {label!r} root at {str(root)!r}; the staged "
                "re-mint must mirror the machine corpus home"
            )
        for entry in sorted(root.iterdir()):
            if not entry.is_file():
                raise RemintRefusal(
                    f"the staged root {str(root)!r} contains {entry.name!r}, which is not a "
                    "manifest file; nothing is skipped"
                )
            try:
                task = load_tasks(entry)[0]
            except ValueError as exc:
                raise RemintRefusal(
                    f"the staged re-mint refused to load {entry.name!r}: {exc}"
                ) from exc
            staged_tasks.append((task, entry))

    if len(staged_tasks) != len(old_tasks):
        raise RemintRefusal(
            f"the staged re-mint holds {len(staged_tasks)} manifests but the snapshot "
            f"records {len(old_tasks)}; a re-mint of a different size is not the #62 "
            "commit set"
        )

    staged_ids: set[str] = set()
    staged_commits: set[str] = set()
    by_label: dict[str, int] = {}
    for task, _ in staged_tasks:
        match = re.fullmatch(r"(donor-[ab])-([0-9a-f]{12})", task.task_id)
        if match is None:
            raise RemintRefusal(
                f"the staged re-mint carries {task.task_id!r}, which is not a donor-a-* / "
                "donor-b-* label-form id; the re-mint's ids must name the label and the "
                "commit it was mined from"
            )
        if match.group(2) != task.base_commit[:12]:
            raise RemintRefusal(
                f"the staged id {task.task_id!r} does not embed its own manifest's sha12 "
                f"({task.base_commit[:12]}); a label-form id that names the wrong commit "
                "breaks the provably-identical claim"
            )
        staged_ids.add(task.task_id)
        staged_commits.add(task.base_commit)
        by_label[match.group(1)] = by_label.get(match.group(1), 0) + 1

    if staged_commits != old_commits:
        missing = sorted(old_commits - staged_commits)
        foreign = sorted(staged_commits - old_commits)
        raise RemintRefusal(
            "the staged re-mint's commit set is not the snapshot's: "
            + (f"missing {missing!r}" if missing else "no missing commits")
            + ", "
            + (f"foreign {foreign!r}" if foreign else "no foreign commits")
            + ". The #62 pairing requires a provably identical commit set, so any changed "
            "commit refuses the apply before any file moves"
        )

    staged_ledger = Path(staged) / _STAGED_LEDGER
    try:
        ledger_entries = read_ledger(staged_ledger)
    except ValueError as exc:
        raise RemintRefusal(
            f"the staged ledger {str(staged_ledger)!r} could not be read: {exc}"
        ) from exc
    if len(ledger_entries) != len(old_tasks):
        raise RemintRefusal(
            f"the staged ledger carries {len(ledger_entries)} entries but the snapshot "
            f"records {len(old_tasks)} manifests; the ledger is the re-mint's evidence and "
            "must cover the same set"
        )
    ledger_ids = {entry.task_id for entry in ledger_entries}
    if ledger_ids != staged_ids:
        unledgered = sorted(staged_ids - ledger_ids)
        unmanifested = sorted(ledger_ids - staged_ids)
        raise RemintRefusal(
            "the staged ledger and the staged manifests name different sets: "
            + (f"unledgered {unledgered!r}" if unledgered else "no unledgered ids")
            + ", "
            + (f"unmanifested {unmanifested!r}" if unmanifested else "no unmanifested ids")
        )

    return VerifyRecord(total=len(staged_tasks), by_label=by_label)


def swap_manifests(corpus: Sequence[Path], staged: Path) -> SwapRecord:
    """Replace each corpus root's manifests with the staged re-mint's, removing the old ids.

    Each corpus root is matched to the staged label root of the same name. The double-apply
    refusal fires **before any file moves**: a target that already holds `donor-a-*` /
    `donor-b-*` manifests has been re-minted already, and a second swap would replace
    verified bytes with the same bytes while pretending to move something. The swap then
    copies every staged manifest in (nothing skipped) and removes every file whose name is
    not in the staged set, so each root ends holding exactly the re-minted set — the loader
    reads a whole directory, and a stray file would be a missing denominator.
    """
    record_added: list[Path] = []
    record_removed: list[Path] = []
    for root in corpus:
        root_dir = Path(root)
        if not root_dir.is_dir():
            raise RemintRefusal(
                f"the corpus root {str(root_dir)!r} does not exist; a swap into nothing "
                "would move nothing"
            )
        staged_root = Path(staged) / _STAGED_MANIFESTS / root_dir.name
        if not staged_root.is_dir():
            raise RemintRefusal(
                f"the staged re-mint has no root for {root_dir.name!r} at "
                f"{str(staged_root)!r}; a corpus root with no staged twin cannot be swapped"
            )
        existing = [entry for entry in root_dir.iterdir() if entry.is_file()]
        already = sorted(entry.name for entry in existing if _DONOR_FILE.match(entry.name))
        if already:
            raise RemintRefusal(
                f"the corpus root {str(root_dir)!r} already holds donor-a-* / donor-b-* "
                f"manifests ({already!r}); the re-mint has been applied here already, and a "
                "second apply is a double-apply. Refuse it by name rather than re-verify "
                "the same bytes"
            )
        staged_files = sorted(staged_root.iterdir())
        staged_names = {entry.name for entry in staged_files if entry.is_file()}
        for entry in staged_files:
            if not entry.is_file():
                raise RemintRefusal(
                    f"the staged root {str(staged_root)!r} contains {entry.name!r}, which "
                    "is not a manifest file; nothing is skipped"
                )
            target = root_dir / entry.name
            shutil.copy2(entry, target)
            record_added.append(target)
        for entry in sorted(root_dir.iterdir()):
            if entry.name not in staged_names:
                entry.unlink()
                record_removed.append(entry)
    return SwapRecord(added=tuple(record_added), removed=tuple(record_removed))


def rewrite_repo_url(corpus: Sequence[Path], donors: Mapping[str, Path]) -> int:
    """Rewrite exactly one field in every applied manifest: `repo_url` to its real donor.

    The staged re-mint's `repo_url` values point at the staging donors (`_sandbox/donors/`),
    copies at the same heads; the corpus's convention — the one the pre-swap manifests
    carried and the bakeoff resolves — is the real donor path. Each applied manifest is
    rewritten by its `provenance.donor` label; a label with no declared path, or a declared
    path that does not exist on this machine, is a named refusal (a written pointer to
    nowhere would fail the bakeoff's own donor resolution at run time). The rewrite is read
    back and asserted field-for-field equal to what was written, so nothing else in the
    manifest bytes changes. Returns the number of manifests rewritten.
    """
    rewritten = 0
    for root in corpus:
        root_dir = Path(root)
        for entry in sorted(root_dir.iterdir()):
            if not entry.is_file():
                raise RemintRefusal(
                    f"the corpus root {str(root_dir)!r} contains {entry.name!r}, which is "
                    "not a manifest file; nothing is skipped"
                )
            try:
                raw = json.loads(entry.read_text())
            except (OSError, json.JSONDecodeError) as exc:
                raise RemintRefusal(
                    f"the applied manifest {str(entry)!r} could not be read: {exc}"
                ) from exc
            label = raw.get("provenance", {}).get("donor")
            if label not in donors:
                raise RemintRefusal(
                    f"the applied manifest {entry.name!r} carries donor label {label!r}, "
                    "which has no declared real donor path; the rewrite must name exactly "
                    "the declared donor paths"
                )
            target = Path(donors[label])
            if not target.is_dir():
                raise RemintRefusal(
                    f"the declared real donor path {str(target)!r} for {label!r} does not "
                    "exist on this machine; a rewritten repo_url must point at a donor the "
                    "bakeoff can read"
                )
            rewritten_raw = dict(raw)
            rewritten_raw["repo_url"] = str(target)
            entry.write_text(json.dumps(rewritten_raw, indent=2, sort_keys=True) + "\n")
            read_back = json.loads(entry.read_text())
            if read_back != rewritten_raw:
                raise RemintRefusal(
                    f"rewriting {entry.name!r} changed more than repo_url; the read-back "
                    "differs from what the staged re-mint carried, field for field"
                )
            rewritten += 1
    return rewritten


def regenerate_ledger(corpus: Sequence[Path], staged: Path, out: Path) -> Path:
    """Regenerate the committed ledger from the staged ledger's evidence and the applied manifests.

    The liveness evidence (`without_patch` / `with_patch` / `executed_matches_declared` /
    `skipped` / `python` / `tools` / `proven_at`) was derived over the same commit set — the
    verification (AC3) pinned that — so only the manifest hash must follow the rewritten
    bytes. The staged ledger is read and the regenerated one written through
    `tasks.ledger`'s own `read_ledger` / `write_ledger` by identity, and each entry's
    `manifest_sha256` is recomputed from the applied manifest's bytes; every other field is
    the staged entry's, unchanged. A staged entry with no applied manifest, or an applied
    manifest the staged ledger never named, is a named refusal.
    """
    staged_ledger = Path(staged) / _STAGED_LEDGER
    try:
        staged_entries = read_ledger(staged_ledger)
    except ValueError as exc:
        raise RemintRefusal(
            f"the staged ledger {str(staged_ledger)!r} could not be read: {exc}"
        ) from exc

    applied: dict[str, Path] = {}
    for root in corpus:
        root_dir = Path(root)
        for entry in sorted(root_dir.iterdir()):
            if not entry.is_file():
                raise RemintRefusal(
                    f"the corpus root {str(root_dir)!r} contains {entry.name!r}, which is "
                    "not a manifest file; nothing is skipped"
                )
            try:
                task_id = json.loads(entry.read_text())["task_id"]
            except (OSError, json.JSONDecodeError, KeyError) as exc:
                raise RemintRefusal(
                    f"the applied manifest {str(entry)!r} could not be read: {exc}"
                ) from exc
            applied[task_id] = entry

    if len(staged_entries) != len(applied):
        raise RemintRefusal(
            f"the staged ledger carries {len(staged_entries)} entries but the applied "
            f"corpus holds {len(applied)} manifests; the regenerated ledger must cover "
            "the same set"
        )
    unapplied = sorted(entry.task_id for entry in staged_entries if entry.task_id not in applied)
    if unapplied:
        raise RemintRefusal(
            f"the staged ledger names {unapplied!r}, which no applied manifest carries; a "
            "ledger entry with no manifest hashes nothing"
        )
    unnamed = sorted(set(applied) - {entry.task_id for entry in staged_entries})
    if unnamed:
        raise RemintRefusal(
            f"the applied corpus carries {unnamed!r}, which the staged ledger never names; "
            "an applied manifest with no evidence would be a task no liveness proof stands "
            "behind"
        )

    regenerated = [
        replace(
            entry,
            manifest_sha256=hashlib.sha256(applied[entry.task_id].read_bytes()).hexdigest(),
        )
        for entry in staged_entries
    ]
    write_ledger(out, regenerated)
    return Path(out)


def _invoke_door(
    name: str, door: Callable[[Sequence[str] | None], int], corpus: Sequence[Path], out: Path
) -> Path:
    """One derivation door, invoked with absolute paths; its refusal carried by name.

    The door's own parser and fail-closed loaders are the authority — this function only
    wires them: absolute corpus paths and an absolute `--out` (the 2026-08-12 failure class
    is a relative path resolving against the wrong CWD), and a nonzero exit becomes a
    `RemintRefusal` carrying the door's own words on stderr, never a bare exit code. The
    door's stderr is captured so the operator (or the phase-4 sheet) hears exactly what the
    door refused and why.
    """
    roots = [Path(root) for root in corpus]
    relative_roots = [str(root) for root in roots if not root.is_absolute()]
    if relative_roots:
        raise RemintRefusal(
            f"{name} was handed relative corpus path(s) {relative_roots!r}; a relative "
            "path resolves against whatever directory the sheet happened to be in, which "
            "is the 2026-08-12 failure class. Pass absolute paths"
        )
    destination = Path(out)
    if not destination.is_absolute():
        raise RemintRefusal(
            f"{name} was handed a relative --out {str(destination)!r}; a document written "
            "against the wrong CWD lands where the sheet never reads it. Pass an absolute "
            "path"
        )
    argv = [*[f"--corpus={root}" for root in roots], f"--out={destination}"]
    captured = io.StringIO()
    with contextlib.redirect_stderr(captured):
        code = door(argv)
    if code != 0:
        words = captured.getvalue().strip() or f"exit {code}"
        raise RemintRefusal(f"{name} refused (exit {code}): {words}")
    return destination


def re_derive_stratum(corpus: Sequence[Path], out: Path) -> Path:
    """Re-derive the stratum document over `corpus` through the stratum module's own door.

    The door is `bakeoff.stratum.main` by identity — the same `python -m
    whetstone.bakeoff.stratum` the original document was derived through — so the re-minted
    document is produced by the identical rule and loader. The door resolves each task's
    donor from its rewritten `repo_url`; an unreadable donor is a recorded refusal inside
    the document, never a guess. Returns `out`.
    """
    return _invoke_door("the stratum re-derivation", stratum.main, corpus, out)


def re_derive_heldout(corpus: Sequence[Path], out: Path) -> Path:
    """Re-derive the held-out document over `corpus` through the heldout module's own door.

    The door is `loop.heldout.main` by identity, and it reads the stratum document at
    `tasks/stratum/easier.json` relative to its CWD — so the sheet runs it from the worktree
    root, after `re_derive_stratum` has written the re-minted stratum document to that
    tracked path. A task whose oracle cannot be decided — an unreadable donor, machine
    state — is `HeldoutUnscorable` from the door's own derivation, a refusal naming the
    task, never a classification. Returns `out`.
    """
    return _invoke_door("the heldout re-derivation", heldout.main, corpus, out)


__all__ = [
    "DONOR_LABELS",
    "RemintRefusal",
    "SNAPSHOT_SCHEMA",
    "SwapRecord",
    "VerifyRecord",
    "re_derive_heldout",
    "re_derive_stratum",
    "regenerate_ledger",
    "rewrite_repo_url",
    "snapshot_corpus",
    "swap_manifests",
    "verify_staged",
]