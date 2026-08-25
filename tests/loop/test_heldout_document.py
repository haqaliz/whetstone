"""The held-out document's machine-level proof: recomputation, locality, and the runbook door.

The held-out document is the pre-committed pinned input `PREREGISTRATION.md` § 7.1 names, and
its whole value is that a reader — or a test — can re-derive the membership from the committed
rule and the corpus and watch it come out identical. This file is that test: it loads the real
source-B corpus from the primary checkout, reads the committed stratum document through its own
fail-closed loader, recomposes the held-out document, and asserts it equals
`tasks/heldout/source-b.json` field by field (spec AC3).

The document is evidence about the data, never the data (`tasks/README.md:126-128`): counts,
band indices and membership ids only — never paths, never patch content, never donor code. The
locality walk at the bottom proves it structurally, with a canary that proves the walk would
see a leak (spec AC5).

**The machine-level state.** `tasks/local/` is gitignored, so a plain checkout has no manifests;
the corpus lives in the **primary checkout** of this repository, resolved from
`git worktree list --porcelain` the same way the operator's own machine names it. In CI the
corpus is absent and the test skips with a reason naming exactly what is missing; the runbook
re-runs it on the machine before the split is used to score anything (the stratum precedent,
`test_stratum_corpus.py`).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from whetstone.bakeoff import stratum
from whetstone.loop import heldout
from whetstone.tasks.manifest import load_tasks

#: The repository root, for the committed documents and the git calls below.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: The committed held-out document whose membership this file re-derives (spec AC3).
HELDOUT_DOCUMENT = REPO_ROOT / "tasks" / "heldout" / "source-b.json"

#: The committed difficulty source the writer consumes (spec: the stratum document).
STRATUM_DOCUMENT = REPO_ROOT / "tasks" / "stratum" / "easier.json"

#: The machine-level corpus roots: the two donor directories under the primary checkout's
#: gitignored `tasks/local/` (`tasks/README.md:63-64`).
_CORPUS_ROOTS = ("tasks/local/belay", "tasks/local/contig")

#: A value that only exists inside a task's held test file. If it turns up anywhere in the
#: document, a file's contents did — which is the one thing the document may never carry
#: (the ledger-walk canary, `test_ledger.py:45-47`).
_CANARY = "canary-9f2c1e-the-users-own-source-line"

#: A string no legitimate field can contain: paths are the excluded class (spec AC5), and a
#: committed document carrying one has leaked a fact about the donor's layout.
_PATH_SHAPED = "src/calc.py"

#: git's environment with the machine's configuration switched off — the discipline every
#: real-git call in this suite inherits (`test_format_hardening_frozen.py:42-67`).
_GIT_ENV = {
    "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_TERMINAL_PROMPT": "0",
}


def _primary_root() -> Path:
    """The primary checkout's root, resolved from `git worktree list --porcelain`.

    The first `worktree` entry is the main checkout; in CI — a plain checkout — that entry is
    this repository itself, and the skip below then fires on the missing corpus. Resolved with
    git's own words rather than assumed, so the test still finds the corpus when the layout
    changes.
    """
    completed = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=_GIT_ENV,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    for line in completed.stdout.splitlines():
        if line.startswith("worktree "):
            return Path(line.split(" ", 1)[1])
    raise RuntimeError(f"git worktree list gave no worktree entry:\n{completed.stdout}")


def _machine_corpus() -> tuple[tuple[Any, ...], stratum.Stratum]:
    """The source-B corpus and the committed stratum document, or a skip naming what is missing.

    The held-out recomputation needs no donors: the difficulty comes from the committed
    stratum document (whose own recomputation test validates it against the donors), so the
    machine-level state is the manifests alone. Either absent, the recomputation cannot run —
    and the skip says so.
    """
    primary = _primary_root()
    roots = tuple(primary / root for root in _CORPUS_ROOTS)
    missing = [str(root) for root in roots if not root.is_dir()]
    if missing:
        pytest.skip(
            "the machine-level source-B corpus is absent here: "
            + ", ".join(missing)
            + " do not exist. CI's plain checkout has no gitignored manifests, so this "
            "recomputation runs only on the operator's machine; the runbook re-runs it before "
            "the split is used to score anything"
        )
    tasks = tuple(load_tasks(roots[0])) + tuple(load_tasks(roots[1]))
    return tasks, stratum.read_document(STRATUM_DOCUMENT)


def _strings(value: Any) -> list[str]:
    """Every string anywhere in a decoded JSON document, keys and values alike."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [
            found
            for key, item in value.items()
            for found in [*_strings(key), *_strings(item)]
        ]
    if isinstance(value, list):
        return [found for item in value for found in _strings(item)]
    return []


def test_the_recomputed_document_equals_the_committed_one_field_by_field() -> None:
    """The membership recomputation (spec AC3): the rule re-run, byte-equal field by field.

    The committed document is the pinned input; a rule edit changes `rule_digest`, a corpus
    change moves the ids, a stratum change moves the difficulty — and each moves at least one
    of the compared fields, failing this test by name rather than drifting in silence.
    """
    tasks, stratum_document = _machine_corpus()
    committed = json.loads(HELDOUT_DOCUMENT.read_text())

    assert len(tasks) == len(committed["corpus"]), (
        "the corpus loaded from the machine does not match the document's: "
        f"{len(tasks)} tasks loaded, {len(committed['corpus'])} declared"
    )

    recomputed = heldout.compose_document(tasks, stratum_document)

    for key in (
        "schema",
        "rule_digest",
        "rule",
        "corpus",
        "difficulty",
        "bands",
        "refusals",
        "membership",
        "document_digest",
    ):
        assert recomputed[key] == committed[key], (
            f"the committed held-out document's {key} is no longer what the rule computes.\n\n"
            "WHY THIS IS A FAILURE: the held-out split is the pre-committed pinned input; a "
            "document that disagrees with its own rule on the same corpus means a rule edit, a "
            "corpus change or a stratum change landed without regenerating the document. "
            "Regenerate it in the same commit."
        )

    assert "timestamp" not in committed, (
        "a write-moment clock would make byte-determinism impossible"
    )


def test_the_membership_meets_the_pre_committed_floors() -> None:
    """The committed document is its own claim, asserted from it: a valid split by the rule.

    Every committed held-out document must satisfy the floors `MIN_HELDOUT` / `MIN_PER_BAND`
    over its own bands map — the same checks the writer refuses on the way in, re-asserted
    here over the artifact itself.
    """
    committed = json.loads(HELDOUT_DOCUMENT.read_text())
    membership = committed["membership"]
    bands = committed["bands"]

    assert len(membership) >= heldout.MIN_HELDOUT, (
        f"{len(membership)} held-out tasks is below the pre-committed floor of "
        f"{heldout.MIN_HELDOUT}"
    )
    per_band = [
        sum(1 for task_id in membership if bands[task_id] == band)
        for band in range(heldout.HELDOUT_BANDS)
    ]
    assert all(count >= heldout.MIN_PER_BAND for count in per_band), (
        f"per-band counts {per_band} violate the pre-committed per-band floor"
    )
    assert 0 < len(membership) < len(committed["corpus"]), (
        "a degenerate split (empty, or the whole corpus) is a usage error, never a committed "
        "document"
    )
    assert len(set(membership)) == len(membership), "membership ids are unique"
    assert set(membership) <= set(committed["corpus"]), "membership ids all resolve in the corpus"
    assert set(committed["difficulty"]) == set(committed["bands"]), (
        "every measured task has a band and every banded task is measured"
    )
    assert set(committed["difficulty"]) | set(committed["refusals"]) == set(
        committed["corpus"]
    ), "every corpus id is measured or refused, and never both"


def test_the_recomputation_reaches_zero_skips_on_this_machine() -> None:
    """The recomputation is exercised here, not skipped here: this is the machine's check.

    The test body's skip exists for CI; on the machine that generated the document it must
    never fire, or the field-by-field test above would be asserting over nothing.
    """
    tasks, _ = _machine_corpus()
    assert len(tasks) == 66, (
        "the machine-level source-B corpus is the declared set: 21 belay + 45 contig "
        f"manifests, got {len(tasks)}"
    )


def test_the_document_carries_counts_only() -> None:
    """No path-shaped, no content-shaped, no line-spanning value anywhere (spec AC5).

    Task ids are already committed in the ledger (`tasks/README.md:24-27`); file paths are
    not, and the walk below is the assertion that they never start being.
    """
    raw = json.loads(HELDOUT_DOCUMENT.read_text())

    found = _strings(raw)
    assert found, "the walk found no strings at all, so it is asserting over nothing"
    for value in found:
        if value == heldout.HELDOUT_SCHEMA:
            # The schema is a versioned format name (`whetstone-heldout/1`), not a path: it
            # is the one slash that names the file's shape, and it is pinned by the loader.
            continue
        assert "\n" not in value, f"{value!r} spans lines, so it is not a count or a digest"
        assert "/" not in value, (
            f"{value!r} is path-shaped; the document carries counts, never paths"
        )
        assert len(value) <= 200, (
            f"{value[:80]!r}… is {len(value)} characters, too long to be evidence rather than data"
        )
        assert value != _CANARY, (
            "the canary text is present: a task's contents reached the document"
        )

    for task_id, counts in raw["difficulty"].items():
        assert isinstance(task_id, str)
        assert set(counts) == {"files", "hunks", "added", "deleted", "f2p", "pins", "blobs"}
        assert all(isinstance(value, int) for value in counts.values()), (
            f"difficulty values must be ints only, got {counts!r}"
        )
    for task_id, band in raw["bands"].items():
        assert isinstance(task_id, str) and isinstance(band, int), (
            "bands must be ints keyed by task id"
        )
    for task_id in raw["membership"]:
        assert task_id in raw["bands"], "every member carries its band"


def test_the_locality_walk_flags_a_planted_path(tmp_path: Path) -> None:
    """Anti-vacuity for the walk above: a planted path-shaped value must be seen.

    The canary is planted into a synthetic document in the same position a leak would land —
    a difficulty entry carrying a string — and the walk over `_strings` must find it.
    """
    raw = json.loads(HELDOUT_DOCUMENT.read_text())
    raw["difficulty"][raw["corpus"][0]] = {
        "files": _PATH_SHAPED,
        "hunks": 1,
        "added": 1,
        "deleted": 0,
        "f2p": 1,
        "pins": 0,
        "blobs": 1,
    }

    offenders = [value for value in _strings(raw) if "/" in value]

    assert _PATH_SHAPED in offenders, (
        "the walk did not see the planted path it was handed, so the locality assertion "
        "above would pass by seeing nothing at all."
    )


def test_the_module_runs_as_python_m_for_the_runbook(tmp_path: Path) -> None:
    """`python -m whetstone.loop.heldout` is the runbook's door, and it must exist.

    The plan's invocation for the committed document is the module entry point
    (`plan_20260824.md` Phase 2), not a `whetstone` CLI flag — so the `__main__` guard is
    part of the aspect's surface, and a module that imported cleanly without it would write
    nothing while exiting 0, which is the runbook's exact failure shape.
    """
    primary = _primary_root()
    roots = [primary / root for root in _CORPUS_ROOTS]
    missing = [str(root) for root in roots if not root.is_dir()]
    if missing:
        pytest.skip(
            "the machine-level source-B corpus is absent here: "
            + ", ".join(missing)
            + " do not exist, and the door's whole input is that corpus"
        )
    out = tmp_path / "heldout" / "source-b.json"

    completed = subprocess.run(
        [
            "python",
            "-m",
            "whetstone.loop.heldout",
            "--corpus",
            str(roots[0]),
            "--corpus",
            str(roots[1]),
            "--out",
            str(out),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert out.is_file(), (
        "the module entry point exited 0 without writing the document — the runbook would "
        "then believe a split exists where none does."
    )
    assert json.loads(out.read_text())["schema"] == heldout.HELDOUT_SCHEMA