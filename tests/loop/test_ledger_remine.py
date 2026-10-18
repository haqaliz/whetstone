"""The run ledger's re-mine delta: `task_set.remined`, its conditional bytes, and its consumers.

`night-corpus-remine` aspect 2 (`docs/planning/night-corpus-remine/record/`). The ledger already
recorded *which tasks the night drew against*; it recorded nothing about the corpus having
**grown** that night, or from which donor. The re-mine delta lands under the existing `task_set`
claim as `remined` — a list of `(task_id, donor)` pairs, ids and labels only, never contents.

Two properties carry the design:

* **no-flag byte-identity.** `remined` is emitted only when the field is not `None`, so a night
  without the re-mine flags writes the pre-change bytes exactly. An always-present
  `"remined": null` would move every ledger's `task_set` claim and break that; the deliberate
  deviation from `heldout`/`stratum`'s always-present `null` style is the safety property.
* **the seal covers it.** `remined` is nested inside `task_set`, which is one claim, so editing it
  without recomputing the document is a `LedgerUnverified` naming `task_set` — while a forger who
  recomputes `claims`/`digest` is not caught, the documented unkeyed-hash boundary.

No model, no runtime, no network. The fixtures are the shipped `_ledger()` (imported, never
edited — it is a shared fixture and the golden's subject) plus `dataclasses.replace`.
"""

from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from loop.test_run_ledger import _ledger
from whetstone.loop import ledger as run_ledger
from whetstone.loop import seal

#: The no-flag golden: `ledger.document(_ledger())` for a `TaskSet` with `remined=None`. It must
#: not move because of the re-mine feature: a no-flag night carries no `remined` key.
#: **Re-pinned 2026-10-11** when `Backend.precision` (`portability-cpu-dtype`, `PREREGISTRATION.md`
#: § 10.18) added a key to the ledger's `backend` block — an unrelated, pre-registered change to a
#: pinned document. The re-pin is dated rather than silent; the previous value was
#: `4fe1022f659fe0b98123dbbf011ace415fd1b9210a6ebee83f6f49ef9aae392d`.
GOLDEN_SHA256 = "2ef3f68baa33d09aebb142309015c2fd87f1505432f879285c4a137a2179360f"

#: A re-mine delta in minting order (unsorted): the writer, not the caller, must sort it.
_MINTED = (
    ("task-zeta", "donor-c"),
    ("task-alpha", "donor-b"),
    ("task-alpha", "donor-a"),
)

#: The same delta as the writer must serialize it: sorted by `(task_id, donor)`.
_SORTED = [
    {"task_id": "task-alpha", "donor": "donor-a"},
    {"task_id": "task-alpha", "donor": "donor-b"},
    {"task_id": "task-zeta", "donor": "donor-c"},
]


def _remined(pairs: tuple[tuple[str, str], ...] | None) -> run_ledger.Ledger:
    """The shipped fixture with its `task_set.remined` replaced. `_ledger()` is never edited."""
    base = _ledger()
    return replace(base, task_set=replace(base.task_set, remined=pairs))


def _rewrite(path: Path, document: dict[str, object]) -> None:
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_the_remine_delta_round_trips_sorted_and_ids_only(tmp_path: Path) -> None:
    """AC 1: `(task_id, donor)` pairs round-trip as sorted `{task_id, donor}` dicts.

    The pairs are fed in minting order and read back sorted, so the sort is the writer's and not
    the caller's; each entry carries exactly the two keys, never a third.
    """
    path = run_ledger.write(tmp_path / "ledger.json", _remined(_MINTED))
    recorded = run_ledger.read(path)

    assert recorded["task_set"]["remined"] == _SORTED, (
        f"WHY THIS IS A FAILURE: the re-mine delta did not round-trip sorted: "
        f"{recorded['task_set']['remined']!r}. A caller that minted in another order would "
        "produce different bytes for the same delta"
    )
    for entry in recorded["task_set"]["remined"]:
        assert set(entry) == {"task_id", "donor"}, (
            f"WHY THIS IS A FAILURE: a re-mine entry carries {sorted(entry)}. The ledger's "
            "discipline is ids and labels only, never a third field that could hold content"
        )


def test_the_writer_sorts_at_the_document_boundary() -> None:
    """AC 5: the pure writer emits the sorted list, so the sort is not the read path's doing."""
    document = json.loads(run_ledger.document(_remined(tuple(reversed(_MINTED)))))

    assert document["task_set"]["remined"] == _SORTED, (
        f"WHY THIS IS A FAILURE: `document()` emitted "
        f"{document['task_set']['remined']!r}, not the sorted delta. The serialization boundary "
        "is where the order is fixed, so the same delta is the same bytes whatever order it "
        "was minted in"
    )


def test_none_means_no_remine_block_and_emits_no_key() -> None:
    """AC 3, the no-block half: `None` omits the key entirely — the byte-identity path."""
    document = json.loads(run_ledger.document(_remined(None)))

    assert "remined" not in document["task_set"], (
        f"WHY THIS IS A FAILURE: a ledger with no re-mine block carries a 'remined' key "
        f"({document['task_set'].get('remined')!r}). An always-present key would move every "
        "ledger's bytes, so an unflagged night would not be the pre-change night byte for byte"
    )


def test_an_empty_tuple_means_a_remine_that_minted_nothing() -> None:
    """AC 3, the empty half: `()` is a *recorded* empty delta, distinct from `None`.

    M4's distinction cannot ride on a single boolean: `None` is "no re-mine block ran" and `()`
    is "a re-mine ran and minted nothing", and a reader must be able to tell them apart.
    """
    document = json.loads(run_ledger.document(_remined(())))

    assert document["task_set"].get("remined") == [], (
        f"WHY THIS IS A FAILURE: an empty re-mine delta serialized as "
        f"{document['task_set'].get('remined')!r}, not `[]`. An empty delta that read as an "
        "absent block would conflate 'minted nothing' with 'no re-mine ran'"
    )


def test_the_no_remine_document_is_the_prechange_golden() -> None:
    """AC 2: the re-mine feature adds no bytes when no re-mine runs.

    The shipped `_ledger()` defaults `remined` to `None`, so the document carries no `remined`
    key. Its job is to fail if the conditional ever becomes an always-present key. The absolute
    golden is not frozen against the whole tree — an unrelated pinned-document change re-pins it
    (dated above; `Backend.precision`, § 10.18) — but the structural assertion below is the
    invariant, and the hash catches any further unintended move of the fixture's bytes.
    """
    document = run_ledger.document(_ledger())

    assert "remined" not in json.loads(document)["task_set"], (
        "WHY THIS IS A FAILURE: the unmodified fixture carries a 'remined' key, so the "
        "byte-identity claim is broken at the source"
    )
    assert hashlib.sha256(document.encode()).hexdigest() == GOLDEN_SHA256, (
        "WHY THIS IS A FAILURE: the no-flag ledger's bytes moved. A night without the re-mine "
        "flags must write the same document as the fixture, and a move means either the re-mine "
        "conditional fired or an unrelated pinned-document change landed without re-pinning"
    )


def test_the_schema_constant_did_not_move() -> None:
    """AC 9: the field is nested under an existing claim, so no `/4` bump is needed or allowed."""
    assert run_ledger.LEDGER_SCHEMA == run_ledger.LEDGER_SCHEMA_V3


# ---------------------------------------------------------------------------
# Phase 2: the no-flag night is byte-identical and carries no key (tests only)
# ---------------------------------------------------------------------------


def test_a_night_without_the_flags_carries_no_remine_key(tmp_path: Path) -> None:
    """AC 4: a real night with no re-mine arguments writes a `task_set` with no `remined` key.

    Green on arrival after Phase 1 (the field defaults to `None`); its job is to stay green and to
    prove the default is the byte-identity path. The night is a real one written through the
    shipped `_night` helper, not a hand-built `Ledger`.
    """
    from loop.test_night import _night

    night = _night(tmp_path)
    recorded = run_ledger.read(night.ledger)

    assert "remined" not in recorded["task_set"], (
        f"WHY THIS IS A FAILURE: an unflagged night wrote a 'remined' key "
        f"({recorded['task_set'].get('remined')!r}). The no-flag path must be the pre-change "
        "document exactly"
    )


def test_two_unflagged_nights_write_byte_identical_ledgers(tmp_path: Path) -> None:
    """AC 4: two identical unflagged nights write byte-identical `ledger.json`.

    The no-remine determinism half of M8/AC3 as it touches the ledger (the
    `test_night_integration.py:358-383` precedent): the default `None` adds no key and no bytes,
    so the same inputs render the same file.
    """
    from loop.test_night import _night

    first = _night(tmp_path / "first")
    second = _night(tmp_path / "second")

    assert first.ledger.read_bytes() == second.ledger.read_bytes(), (
        "WHY THIS IS A FAILURE: two unflagged nights over identical fixtures wrote different "
        "ledger bytes. The default path is not deterministic, so no reader can recompute what "
        "an unflagged night recorded"
    )


def test_a_mutated_remine_delta_is_refused_by_name(tmp_path: Path) -> None:
    """AC 6: the `task_set` claim covers the nested delta, so an edit is a refusal by name."""
    path = run_ledger.write(tmp_path / "ledger.json", _remined(_MINTED))
    document = json.loads(path.read_text(encoding="utf-8"))
    document["task_set"]["remined"] = []
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnverified, match="task_set"):
        run_ledger.read(path)


def test_a_forger_who_recomputes_the_remine_claims_is_not_caught(tmp_path: Path) -> None:
    """AC 6, the documented limit: the digest is an unkeyed hash, never authentication.

    Recomputing `claims` and `digest` consistently after editing the nested delta produces a
    document this reader accepts and reports `sealed`. That is the boundary the vocabulary states
    (`ledger.py:79-88`), not a defect: the seal catches accident-shaped edits, and anyone who can
    edit the file can recompute both.
    """
    path = run_ledger.write(tmp_path / "ledger.json", _remined(_MINTED))
    document = json.loads(path.read_text(encoding="utf-8"))
    document["task_set"]["remined"] = [{"task_id": "task-forged", "donor": "donor-forged"}]
    body = {key: value for key, value in document.items() if key not in seal.UNSEALED_KEYS}
    document["claims"] = seal.claim_hashes(
        body, subject="ledger", refuse=run_ledger.LedgerUnverified
    )
    document["digest"] = seal.claims_digest(document["claims"], schema=run_ledger.LEDGER_SCHEMA_V3)
    _rewrite(path, document)

    forged = run_ledger.verify_document(path)

    assert forged.sealed is True
    assert forged.document["task_set"]["remined"] == [
        {"task_id": "task-forged", "donor": "donor-forged"}
    ]


# ---------------------------------------------------------------------------
# Phase 3: every consumer tolerates the nested key; the tripwire
# ---------------------------------------------------------------------------


def test_a_remined_ledger_reads_through_morning(tmp_path: Path) -> None:
    """AC 7: the morning reader accepts a genuine v3 ledger carrying `task_set.remined`.

    `_KNOWN_FIELDS` (`morning.py:207`) is compared only against `set(payload)`
    (`morning.py:301`) — top-level keys — so a nested addition is invisible to the unknown-key
    refusal, and the known subfields are extracted as before.
    """
    from whetstone.loop import morning

    path = run_ledger.write(tmp_path / "ledger.json", _remined(_MINTED))
    document = morning.read_ledger(path)

    assert document.task_set.private == 61, (
        "WHY THIS IS A FAILURE: the morning reader did not read the known subfields of a "
        "remined ledger. A nested key the reader rejects would make every future night's "
        "report refuse as an unknown-key change"
    )


def test_a_remined_probe_ledger_decides_through_check_probe(tmp_path: Path) -> None:
    """AC 7: `check_probe.run_check` decides a probe run whose ledger carries `remined`.

    The check reads `task_set.probe` and the declared budget through `ledger.read` by identity,
    so the nested delta changes nothing it decides. The probe is a genuine one under the declared
    `sampling.K`, because the budget pin now compares the ledger to that constant.
    """
    from loop.test_check_probe import _COUNTS, _HARNESS, _PROBE_SEEDS
    from whetstone.loop import check_probe, night, sampling
    from whetstone.loop import draws as run_draws

    run = tmp_path / "runs" / "probe-001"
    run.mkdir(parents=True)
    base = _ledger()
    candidate = replace(
        base,
        task_set=replace(base.task_set, probe=1, remined=(("task-remined", "donor-a"),)),
        checkpoint_digest=None,
        checkpoint_absent="a probe writes no checkpoint",
        draws=sampling.K,
        seeds=_PROBE_SEEDS,
        draws_recorded=tuple(
            run_ledger.DrawRecord(attempt=index, harness=dict(_HARNESS), counts=_COUNTS)
            for index in range(1, sampling.K + 1)
        ),
    )
    run_ledger.write(run / run_ledger.LEDGER_FILE, candidate)
    for attempt in range(1, sampling.K + 1):
        journal, _ = run_draws.evidence_paths(run / night.EVIDENCE_DIR, attempt)
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.touch()

    report = check_probe.run_check(run)

    assert report.proceed is True, (
        "WHY THIS IS A FAILURE: a genuine probe run carrying `task_set.remined` did not decide "
        "as it does without the key. The gate's reader must tolerate the nested delta"
    )


def test_check_probe_and_honest_report_read_through_the_ledger_reader() -> None:
    """AC 7: the two remaining readers are the ledger's own, by identity, not a second parse."""
    from whetstone.loop import check_probe, honest_report

    assert check_probe.read_ledger is run_ledger.read
    assert honest_report.read_ledger is run_ledger.read


def test_a_remined_document_is_still_whetstone_run_3_and_sealed(tmp_path: Path) -> None:
    """AC 9: the nested field needs no schema bump — the document stays v3 and verifies sealed."""
    path = run_ledger.write(tmp_path / "ledger.json", _remined(_MINTED))
    document = json.loads(path.read_text(encoding="utf-8"))

    assert run_ledger.LEDGER_SCHEMA == run_ledger.LEDGER_SCHEMA_V3
    assert document["schema"] == run_ledger.LEDGER_SCHEMA_V3
    assert run_ledger.verify_document(path).sealed is True


def test_the_remine_ledger_holds_no_donor_source_text(tmp_path: Path) -> None:
    """AC 8: the re-mine delta carries ids and labels, never content — the canary extended.

    A ledger whose `remined` donor label looks like a donor's is written with the shipped
    fixture's donor source and prompt still in the dataset; the bytes must carry the label (so
    the field really rendered) and neither the source text nor the prompt.
    """
    path = run_ledger.write(
        tmp_path / "ledger.json", _remined((("task-alpha", "donor-from-elsewhere"),))
    )
    text = path.read_text(encoding="utf-8")

    assert "donor-from-elsewhere" in text, (
        "WHY THIS IS A FAILURE: the re-mine donor label did not reach the ledger, so this "
        "canary would pass on a document that recorded nothing"
    )
    assert "SECRET_DONOR_MARKER" not in text, (
        "WHY THIS IS A FAILURE: donor source text reached the run ledger through the re-mine "
        "delta. The ledger's discipline is hashes and verdicts, never contents"
    )
    assert "fix it" not in text, (
        "WHY THIS IS A FAILURE: a prompt reached the run ledger. The re-mine delta is ids and "
        "labels only"
    )


# ---------------------------------------------------------------------------
# The tripwire: no module validates a nested `task_set` key set
# ---------------------------------------------------------------------------


def _task_set_mapping_binding(expr: ast.expr) -> bool:
    """Whether `expr` produces a `task_set` mapping: a `["task_set"]` lookup or a call naming it.

    Covers `payload["task_set"]`, `ledger_document["task_set"]`, `_block(payload, "task_set",
    ...)` and `payload.get("task_set")` — the ways a module in this package reaches the block.
    """
    if isinstance(expr, ast.Subscript):
        key = expr.slice
        return isinstance(key, ast.Constant) and key.value == "task_set"
    if isinstance(expr, ast.Call):
        return any(isinstance(arg, ast.Constant) and arg.value == "task_set" for arg in expr.args)
    return False


def _nested_task_set_keysets(source: str) -> list[int]:
    """The lines where `source` builds a set of a `task_set` mapping's keys — a nested validator.

    A module that did `set(task_set) - KNOWN`, `set(payload["task_set"])` or `task_set.keys()`
    would refuse the nested `remined` key and is exactly what AC 7's source guard exists to catch.
    Set operations over top-level payloads (`morning.py:301`) are not flagged: their operand is
    not a `task_set` mapping.
    """
    tree = ast.parse(source)
    mappings: set[str] = set()
    for node in ast.walk(tree):
        value: ast.expr | None = None
        targets: tuple[ast.expr, ...] = ()
        if isinstance(node, ast.Assign):
            value, targets = node.value, tuple(node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            value, targets = node.value, (node.target,)
        if value is None or not _task_set_mapping_binding(value):
            continue
        mappings.update(name.id for name in targets if isinstance(name, ast.Name))

    def names_the_mapping(expr: ast.expr) -> bool:
        if isinstance(expr, ast.Name):
            return expr.id in mappings
        return _task_set_mapping_binding(expr)

    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in ("set", "frozenset"):
            if node.args and names_the_mapping(node.args[0]):
                lines.append(node.lineno)
        elif (
            isinstance(func, ast.Attribute)
            and func.attr == "keys"
            and names_the_mapping(func.value)
        ):
            lines.append(node.lineno)
    return sorted(lines)


def test_the_nested_keyset_scanner_flags_a_validator_and_passes_a_reader() -> None:
    """The scanner has teeth before it is trusted: it flags nested validators, not readers."""
    validators = [
        "task_set = payload['task_set']\nunexpected = sorted(set(task_set) - KNOWN)",
        "task_set = _block(payload, 'task_set', location)\nif set(task_set) - KNOWN:\n    pass",
        "unexpected = set(payload['task_set']) - KNOWN",
        "task_set = payload.get('task_set')\nrefuse = set(task_set.keys()) - KNOWN",
    ]
    for source in validators:
        assert _nested_task_set_keysets(source), source

    clean = [
        "unexpected = sorted(set(payload) - _KNOWN_FIELDS)",
        "task_set = _block(payload, 'task_set', location)\nheldout = task_set.get('heldout')",
        "task_set = ledger_document['task_set']\nprivate = task_set['private']",
        "raw = json.loads(path.read_text())\nunexpected = sorted(set(raw) - _KNOWN_FIELDS)",
        "keys = {'private', 'public'}\nvalue = frozenset(keys)",
    ]
    for source in clean:
        assert _nested_task_set_keysets(source) == [], source


def test_no_module_validates_a_nested_task_set_key_set() -> None:
    """AC 7, the tripwire: no source under `src/whetstone/loop/` refuses a nested `task_set` key.

    If a consumer validated the nested key set, the `remined` delta would be refused and the
    tolerance tests above would be wrong to pass. Scanned rather than assumed — the failure of
    this test names the module and line, and the fix is to widen that consumer, never to hide the
    key.
    """
    root = Path(run_ledger.__file__).resolve().parent  # src/whetstone/loop
    offenders = {
        str(path.relative_to(root)): lines
        for path in sorted(root.rglob("*.py"))
        if (lines := _nested_task_set_keysets(path.read_text(encoding="utf-8")))
    }

    assert offenders == {}, (
        f"WHY THIS IS A FAILURE: {sorted(offenders)} build a key set from a `task_set` mapping, "
        "so they would refuse the nested `remined` delta. The fix is to widen that consumer to "
        "ignore unknown nested subfields, not to hide the key"
    )
