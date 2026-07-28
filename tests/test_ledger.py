"""The committed evidence for a corpus that is not committed — and the no-egress line it holds.

`/tasks/local/` is gitignored, because source B is mined from the user's own repositories and
their code never belongs in this one. Left there, that makes the **pre-registered headline
source** the one source whose liveness no reader can check: "trust us, the other half was fine" —
the exact shape of hole this project exists to refuse (`tasks/README.md`, PRD § 3.1).

The ledger closes it by committing the *evidence* and not the data: per task, a hash of the
manifest, the two liveness verdicts, whether the executed set equalled the declared one, the skip
count, and the versions and date behind those runs. A reader with none of the user's code can
still check that every claimed task was proven live, count them, and re-derive the corpus from
the committed recipe against their own copy of the donor.

That guarantee is only worth what it is *tested* to be worth, so the central test here is
structural: **no value anywhere in the ledger carries file contents**. Walked, not eyeballed —
a blob that crept into a provenance field would be invisible to a reviewer and permanent in the
history.

No sandbox and no reward run: a `Liveness` is a record, so this file constructs one and asserts
about what is written down. What produces a real one is `tests/test_liveness.py`.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from whetstone.tasks.ledger import (
    LedgerEntry,
    Recipe,
    read_ledger,
    record,
    tool_versions,
    write_ledger,
    write_recipe,
)
from whetstone.tasks.liveness import Liveness
from whetstone.verify.verdict import Status

#: A string that exists only inside the task's held test file. If it turns up anywhere in the
#: ledger, a file's contents did — which is the one thing the ledger may never carry.
CANARY = "canary-9f2c1e-the-users-own-source-line"

#: A pinned clock. The ledger is committed, so two mints of the same corpus differing only in a
#: timestamp would produce a diff nobody can read; and a test that called the real clock would
#: assert about the minute it ran in.
_MINTED_AT = "2026-07-28T00:00:00Z"

#: What a mint records about the tools behind the runs. Pinned here for the same reason.
_TOOLS = {"git": "git version 2.39.5", "uv": "uv 0.11.23", "whetstone": "0.0.0"}


@pytest.fixture
def manifest(tmp_path: Path) -> Path:
    """A manifest whose held test blob carries the canary, written as a real file."""
    blob = base64.b64encode(f"def test_x():\n    assert '{CANARY}'\n".encode()).decode("ascii")
    path = tmp_path / "task.json"
    path.write_text(
        json.dumps(
            {
                "task_id": "donor-abc123def456",
                "source": "private",
                "repo_url": "/donor",
                "base_commit": "a" * 40,
                "environment": {"python": "3.12.13", "pins": ["pytest==9.1.1"]},
                # The canary sits in two places a leak could plausibly come from: base64 inside
                # the held blob, and verbatim in the problem statement — which for a mined task
                # is the user's own commit subject, and is exactly the field a ledger might copy
                # across without thinking.
                "problem_statement": f"add() subtracts. {CANARY}",
                "fail_to_pass": ["tests/test_x.py::test_x"],
                "pass_to_pass": [],
                "test_blobs": {"tests/test_x.py": blob},
                "provenance": {"pass_to_pass_scope": "held-files"},
            }
        )
    )
    return path


@pytest.fixture
def proven() -> Liveness:
    """One task's proof, as `prove_live` would return it."""
    return Liveness(
        task_id="donor-abc123def456",
        without_patch=Status.FAIL,
        with_patch=Status.PASS,
        executed_without_patch=1,
        executed_matches_declared=True,
        skipped=0,
    )


def _entry(manifest: Path, proven: Liveness) -> LedgerEntry:
    return record(manifest, proven, python="3.12.13", tools=_TOOLS, clock=lambda: _MINTED_AT)


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


def test_the_ledger_carries_no_file_contents(
    manifest: Path, proven: Liveness, tmp_path: Path
) -> None:
    """THE structural guarantee, walked rather than eyeballed.

    A source line, a diff hunk or a blob is many characters long and contains newlines; nothing
    the ledger legitimately records is either. Both halves are asserted because either alone is
    weak: a base64 blob has no newline, and a single stolen source line can be short.
    """
    ledger = tmp_path / "local-ledger.json"
    write_ledger(ledger, (_entry(manifest, proven),))

    found = _strings(json.loads(ledger.read_text()))
    assert found, "the walk found no strings at all, so it is asserting over nothing"
    for value in found:
        assert "\n" not in value, f"{value!r} spans lines, so it is not a hash or a verdict"
        assert len(value) <= 200, (
            f"{value[:80]!r}… is {len(value)} characters, too long to be evidence rather than data"
        )


def test_the_users_own_source_never_reaches_the_ledger(
    manifest: Path, proven: Liveness, tmp_path: Path
) -> None:
    """The same guarantee stated as a fact about one specific byte string.

    The control matters as much as the assertion: the canary really is in the manifest, so its
    absence from the ledger is a property of the ledger rather than of a marker that was never
    anywhere.
    """
    raw = json.loads(manifest.read_text())
    assert CANARY in raw["problem_statement"], "the canary is not in the manifest's prose"
    assert CANARY in base64.b64decode(raw["test_blobs"]["tests/test_x.py"]).decode(), (
        "the canary is not in the manifest's held blob, so half this control is asserting "
        "nothing"
    )

    ledger = tmp_path / "local-ledger.json"
    write_ledger(ledger, (_entry(manifest, proven),))
    assert CANARY not in ledger.read_text()


def test_the_ledger_records_the_evidence_for_the_task(manifest: Path, proven: Liveness) -> None:
    """Every field PRD § 3.1 names, present and correct."""
    entry = _entry(manifest, proven)
    assert entry.task_id == "donor-abc123def456"
    assert entry.without_patch == Status.FAIL.value
    assert entry.with_patch == Status.PASS.value
    assert entry.executed_matches_declared is True
    assert entry.skipped == 0
    assert entry.python == "3.12.13"
    assert entry.tools == _TOOLS
    assert entry.proven_at == _MINTED_AT


def test_the_recorded_hash_is_of_the_manifest_bytes(manifest: Path, proven: Liveness) -> None:
    """The hash is what stands in for the manifest, so it must be a hash OF the manifest."""
    expected = hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert _entry(manifest, proven).manifest_sha256 == expected


def test_an_edited_manifest_no_longer_matches_its_ledger_entry(
    manifest: Path, proven: Liveness
) -> None:
    """Anti-vacuity for the hash: it has to move when the manifest does.

    Without this, a constant would satisfy the test above and the ledger would attest to nothing
    — a reader could not tell a re-derived manifest from a different one.
    """
    before = _entry(manifest, proven).manifest_sha256
    manifest.write_text(manifest.read_text().replace("add() subtracts.", "add() subtracts!"))
    assert _entry(manifest, proven).manifest_sha256 != before


def test_the_ledger_round_trips(manifest: Path, proven: Liveness, tmp_path: Path) -> None:
    """Written and read back identically — the ledger is meant to be re-read, not only written."""
    ledger = tmp_path / "local-ledger.json"
    entries = (_entry(manifest, proven),)
    write_ledger(ledger, entries)
    assert read_ledger(ledger) == entries


def test_two_mints_of_the_same_corpus_write_the_same_bytes(
    manifest: Path, proven: Liveness, tmp_path: Path
) -> None:
    """Byte-identical under a pinned clock, and in whichever order the tasks arrived.

    A committed file whose bytes move for no reason produces a diff nobody can read, and a
    reviewer who cannot read the diff cannot audit the evidence.
    """
    first, second = tmp_path / "one.json", tmp_path / "two.json"
    entry = _entry(manifest, proven)
    other = LedgerEntry(**{**vars(entry), "task_id": "donor-000000000000"})

    write_ledger(first, (entry, other))
    write_ledger(second, (other, entry))
    assert first.read_bytes() == second.read_bytes()


def test_the_recipe_records_how_the_corpus_was_derived_and_not_what_it_contains(
    tmp_path: Path,
) -> None:
    """The recipe is a procedure, so a reader can re-derive against their own copy of the donor.

    `pass_to_pass_scope` is in it because decision D-A narrowed what the corpus is *about* — each
    mint runs the held test files only — and a reader who assumed whole-suite scope would
    overstate the corpus in exactly the direction nobody would notice.
    """
    path = tmp_path / "donor.json"
    write_recipe(
        path,
        Recipe(
            donor="/donor",
            donor_head="b" * 40,
            selection={"limit": "2", "seed": "7"},
            pass_to_pass_scope="held-files",
            tools=_TOOLS,
            python="3.12.13",
            mined_at=_MINTED_AT,
        ),
    )

    written = json.loads(path.read_text())
    assert written["donor"] == "/donor"
    assert written["donor_head"] == "b" * 40
    assert written["pass_to_pass_scope"] == "held-files"
    assert written["selection"] == {"limit": "2", "seed": "7"}
    assert written["tools"] == _TOOLS
    assert written["mined_at"] == _MINTED_AT


def test_the_recorded_tool_versions_are_the_ones_actually_installed() -> None:
    """A version nobody read is a version nobody can reproduce against."""
    tools = tool_versions()
    assert tools.get("git"), tools
    assert tools.get("uv"), tools
    assert tools.get("whetstone"), tools
    for value in tools.values():
        assert "\n" not in value, f"{value!r} spans lines and would break the ledger's shape"
