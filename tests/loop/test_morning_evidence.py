"""What the morning report is allowed to believe about a night, and how it picks one.

Two properties, and both are the kind that pass for the wrong reason if nobody looks.

**The ledger is read fail-closed, field by field.** `ledger.read` checks the schema string and
hands back the raw mapping; every field the report renders is one an optimistic parse would
default, and a defaulted count records nothing while returning successfully. That is the shape of
every silent failure this repository has already found, so the typed reader refuses each missing
or mistyped field by name rather than filling it in.

**"Last night" has no answer on disk, so the rule is written down and enforced.** The run id is
operator-declared (`cli.py:328`) and `recorded_on` is *"an input, never the clock"*
(`ledger.py:151`) — there is no timestamp anywhere in this tree. Selection therefore reads the
greatest declared `recorded_on`, and the fixtures below are built so that **directory order,
alphabetical run-id order and mtime order each disagree with the right answer.** Without that,
every test here would pass under an implementation that sorted by mtime, and the command whose
whole job is to say what happened last night would confidently name the wrong run.

A tie is refused rather than broken, and the refusal is watched failing against the credulous
resolver this would otherwise decay into. A corrupt night refuses the whole scan rather than
being skipped: skipping makes a killed night invisible to the one command that exists to notice
it.
"""

from __future__ import annotations

import ast
import json
import os
from collections.abc import Mapping
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

import pytest

from loop.test_run_ledger import _ledger
from whetstone.loop import ledger as run_ledger
from whetstone.loop import morning

#: Text that could only have come from a donor's working tree, for the locality canary.
DONOR_SOURCE = "SECRET_DONOR_MARKER"


def _written(root: Path, *, run_id: str = "night-001", recorded_on: str = "2026-08-20") -> Path:
    """A real ledger on disk, produced by the ledger's own writer.

    Through `ledger.write` rather than hand-typed JSON, deliberately: a hand-typed fixture tests
    the reader against a document the writer would never produce, and the two drift apart without
    either one looking wrong.
    """
    ledger = replace(_ledger(), run_id=run_id, recorded_on=recorded_on)
    directory = root / run_id
    directory.mkdir(parents=True, exist_ok=True)
    return run_ledger.write(directory / run_ledger.LEDGER_FILE, ledger)


def _payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rewrite(path: Path, payload: Mapping[str, Any]) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Phase 1 — the typed document and its fail-closed reader
# ---------------------------------------------------------------------------


def test_a_well_formed_ledger_reads_field_for_field(tmp_path: Path) -> None:
    """The happy path, asserted against the values the writer actually wrote."""
    path = _written(tmp_path)
    document = morning.read_ledger(path)

    assert document.run_id == "night-001"
    assert document.recorded_on == "2026-08-20"
    assert document.run_seed == 20260820
    assert document.draws == 8
    assert document.model.repo_id == "mlx-community/base-32B"
    assert document.model.revision == "d1e3b69"
    assert document.task_set.private == 61
    assert document.task_set.public == 1
    assert document.task_set.roots == 2
    assert document.task_set.dev_subset == ("dev-1",)
    assert document.task_set.probe is None
    assert document.task_set.heldout_membership == 12
    assert document.dataset.examples == 1
    assert document.dataset.denominator == 61
    assert document.dataset.unverified == 7
    assert document.dataset.coverage == 54
    assert document.dataset.valid_split.startswith("no valid split")
    assert document.checkpoint_digest == "c" * 64
    assert document.checkpoint_absent == ""
    assert document.tool_versions["python"] == "3.12.0"
    assert document.contract["sampler"] == "categorical"


def test_the_required_field_list_is_not_empty() -> None:
    """Anti-vacuity: the refusal loop below is a statement about the members of this set.

    `CONTRIBUTING.md:53-60` makes this mandatory rather than tidy. An empty tuple satisfies every
    parameterised refusal test at once, and the suite would report that every field is required at
    the moment it stopped checking any of them.
    """
    assert morning.REQUIRED_FIELDS, (
        "morning.REQUIRED_FIELDS is empty — the per-field refusal test below would iterate over "
        "nothing and pass while proving nothing"
    )


@pytest.mark.parametrize("field", morning.REQUIRED_FIELDS)
def test_every_required_field_is_refused_when_absent(tmp_path: Path, field: str) -> None:
    """No field is defaulted. A field added later without a refusal fails here, not in production.

    This is the anti-staleness half: the reader's own list drives the parameterisation, so the
    only way to add a field the reader reads without a refusal for it is to leave it out of
    `REQUIRED_FIELDS`, which the document-shape assertion below then catches.
    """
    path = _written(tmp_path)
    payload = _payload(path)
    del payload[field]
    _rewrite(path, payload)

    with pytest.raises(morning.LedgerFieldMissing) as refused:
        morning.read_ledger(path)
    assert field in str(refused.value), refused.value
    assert str(path) in str(refused.value), refused.value


def test_the_required_fields_cover_every_field_the_document_carries() -> None:
    """The reader's required list and the document's own shape cannot drift apart.

    A `LedgerDocument` field fed from a payload key that is not required is a field the reader
    would silently default — the exact failure this file exists to prevent — so the mapping is
    asserted total rather than described in a comment.
    """
    sourced = set(morning.FIELD_SOURCES)
    carried = {one.name for one in fields(morning.LedgerDocument)}
    assert carried == sourced, (
        f"WHY THIS IS A FAILURE: LedgerDocument carries {sorted(carried - sourced)} with no "
        f"declared payload source, and declares sources for {sorted(sourced - carried)} it does "
        "not carry. A field with no source is a field the reader defaults."
    )
    assert set(morning.FIELD_SOURCES.values()) <= set(morning.REQUIRED_FIELDS)


def test_a_boolean_is_not_an_integer(tmp_path: Path) -> None:
    """`bool` is an `int` subclass, so `isinstance(x, int)` accepts `true` for a count.

    The gate's own reader refuses this by name (`gate.py:911-912`); a count that reads back as
    `True` would render as `1` and nobody would see it.
    """
    path = _written(tmp_path)
    payload = _payload(path)
    payload["draws"] = True
    _rewrite(path, payload)

    with pytest.raises(morning.LedgerFieldInvalid) as refused:
        morning.read_ledger(path)
    assert "draws" in str(refused.value), refused.value


def test_an_unknown_top_level_field_is_refused(tmp_path: Path) -> None:
    """A key the reader does not know is a schema change nobody declared."""
    path = _written(tmp_path)
    payload = _payload(path)
    payload["surprise"] = 1
    _rewrite(path, payload)

    with pytest.raises(morning.LedgerFieldInvalid) as refused:
        morning.read_ledger(path)
    assert "surprise" in str(refused.value), refused.value


def test_the_schema_check_is_the_ledgers_own(tmp_path: Path) -> None:
    """One schema check in this tree, not two — reused by identity rather than restated."""
    assert morning.LedgerUnreadable is run_ledger.LedgerUnreadable

    path = _written(tmp_path)
    payload = _payload(path)
    payload["schema"] = "whetstone-run/99"
    _rewrite(path, payload)

    with pytest.raises(run_ledger.LedgerUnreadable):
        morning.read_ledger(path)


def test_a_missing_ledger_is_refused_as_unreadable(tmp_path: Path) -> None:
    """Absent and malformed are the ledger's own refusal, not a new one."""
    with pytest.raises(run_ledger.LedgerUnreadable):
        morning.read_ledger(tmp_path / "nothing" / "ledger.json")


def test_recorded_on_must_be_an_iso_date(tmp_path: Path) -> None:
    """The resolver compares two of these lexicographically, which is correct only for ISO-8601.

    `recorded_on` is a free string on the writer's side. Comparing strings of unknown format and
    calling the greater one "last night" is an ordering that looks like a measurement, so the
    shape is refused at read time — before any comparison happens.
    """
    path = _written(tmp_path)
    payload = _payload(path)
    payload["recorded_on"] = "20 August 2026"
    _rewrite(path, payload)

    with pytest.raises(morning.LedgerFieldInvalid) as refused:
        morning.read_ledger(path)
    assert "recorded_on" in str(refused.value), refused.value


def test_the_document_carries_no_donor_source_text(tmp_path: Path) -> None:
    """The locality canary, at the reader's own surface.

    The ledger already refuses to hold donor text (`test_run_ledger.py:107`), and this asserts the
    typed document did not acquire a field that reaches for it. Counts, digests and verdicts only.
    """
    path = _written(tmp_path)
    document = morning.read_ledger(path)
    assert DONOR_SOURCE not in repr(document), (
        "WHY THIS IS A FAILURE: donor source text reached the typed ledger document. This is the "
        "object the morning report renders from, and a report is the kind of file that gets "
        "shared. Hashes and verdicts, never contents"
    )


def test_the_module_imports_no_inference_library() -> None:
    """The morning report reads documents and renders text; it must never reach a model.

    Walked over the module's own bytes rather than asserted about `sys.modules`, on the
    `preanalysis.py` precedent: an import that only fires on some path is still an import.
    """
    source = Path(morning.__file__).read_bytes()
    tree = ast.parse(source, filename=morning.__file__)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    banned = sorted(
        name
        for name in imported
        if name.split(".")[0] in {"mlx", "mlx_lm", "torch", "transformers"}
        or name.endswith((".run", ".scoring", ".mlx_runtime"))
    )
    assert not banned, (
        f"WHY THIS IS A FAILURE: {banned} reached the morning report's own module. It reads "
        "documents and renders text; nothing here needs a model, and the CLI edge that calls it "
        "is function-local precisely so `whetstone verify` never loads one"
    )


# ---------------------------------------------------------------------------
# Phase 2 — resolving "last night"
# ---------------------------------------------------------------------------


def _three_nights(root: Path) -> None:
    """Three nights whose every incidental ordering disagrees with the declared one.

    The answer is `alpha-run`, declared 2026-08-27. Built so that:

    * **alphabetical run-id order** puts `alpha-run` FIRST, not last;
    * **mtime order** makes `zulu-run` the most recently touched;
    * **directory creation order** puts `zulu-run` last.

    Every one of those is an ordering a plausible implementation might reach for, and each gives a
    different answer than the declared date does. A fixture where they agree would let an mtime
    resolver pass this file end to end.
    """
    _written(root, run_id="mike-run", recorded_on="2026-08-25")
    _written(root, run_id="alpha-run", recorded_on="2026-08-27")
    _written(root, run_id="zulu-run", recorded_on="2026-08-26")

    for name, when in (("mike-run", 1_600_000_000), ("alpha-run", 1_700_000_000)):
        target = root / name / run_ledger.LEDGER_FILE
        os.utime(target, (when, when))
        os.utime(target.parent, (when, when))


def test_the_greatest_declared_recorded_on_wins(tmp_path: Path) -> None:
    """The stated rule, against a fixture where three other orderings each say something else."""
    _three_nights(tmp_path)
    document = morning.resolve_last_night(tmp_path)
    assert document.run_id == "alpha-run", (
        "WHY THIS IS A FAILURE: the resolver did not read the declared date. This fixture is "
        "built so alphabetical order, mtime order and creation order each name a different run"
    )
    assert document.recorded_on == "2026-08-27"


def test_a_tie_on_the_greatest_date_is_refused_and_names_the_escape(tmp_path: Path) -> None:
    """Two nights declared on one date is an ordinary operator action, so this will fire.

    The refusal names both run ids and `--run`, because a correct refusal with no next step leaves
    the operator holding an accurate message and no way forward.
    """
    _written(tmp_path, run_id="night-a", recorded_on="2026-08-27")
    _written(tmp_path, run_id="night-b", recorded_on="2026-08-27")
    _written(tmp_path, run_id="night-c", recorded_on="2026-08-01")

    with pytest.raises(morning.AmbiguousNight) as refused:
        morning.resolve_last_night(tmp_path)
    message = str(refused.value)
    assert "night-a" in message and "night-b" in message, message
    assert "night-c" not in message, f"an untied night was named in the tie: {message}"
    assert "--run" in message, f"the refusal names no way forward: {message}"


def test_the_tie_refusal_is_a_differential_against_a_credulous_resolver(tmp_path: Path) -> None:
    """Watched failing against the implementation this would decay into.

    A resolver that breaks the tie by sort order returns an answer here, confidently, and every
    other test in this file still passes. The difference between that and the shipped one is the
    whole point of the refusal, so it is asserted rather than trusted.
    """
    _written(tmp_path, run_id="night-a", recorded_on="2026-08-27")
    _written(tmp_path, run_id="night-b", recorded_on="2026-08-27")

    def credulous(root: Path) -> morning.LedgerDocument:
        documents = [
            morning.read_ledger(one / run_ledger.LEDGER_FILE) for one in sorted(root.iterdir())
        ]
        return sorted(documents, key=lambda one: (one.recorded_on, one.run_id))[-1]

    assert credulous(tmp_path).run_id == "night-b"
    with pytest.raises(morning.AmbiguousNight):
        morning.resolve_last_night(tmp_path)


def test_an_empty_runs_root_is_refused(tmp_path: Path) -> None:
    """Never an empty morning: nothing to report on is a refusal, not a blank report."""
    (tmp_path / "empty").mkdir()
    with pytest.raises(morning.NoRuns):
        morning.resolve_last_night(tmp_path / "empty")


def test_a_runs_root_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    with pytest.raises(morning.NoRuns):
        morning.resolve_last_night(tmp_path / "absent")


@pytest.mark.parametrize("damage", ["missing", "truncated", "foreign"])
def test_one_corrupt_night_refuses_the_whole_scan(tmp_path: Path, damage: str) -> None:
    """A killed night is refused, never skipped — planted beside two healthy ones.

    Skipping is the tempting behaviour and the wrong one: it makes a corrupt or interrupted night
    invisible to the single command whose job is to say what happened last night, and the operator
    reads a clean report about a different run without ever learning the newest one was unreadable.
    """
    _written(tmp_path, run_id="night-a", recorded_on="2026-08-25")
    _written(tmp_path, run_id="night-b", recorded_on="2026-08-26")
    broken = tmp_path / "night-c"
    broken.mkdir()
    if damage == "truncated":
        (broken / run_ledger.LEDGER_FILE).write_text("{\"schema\":", encoding="utf-8")
    elif damage == "foreign":
        (broken / run_ledger.LEDGER_FILE).write_text(
            json.dumps({"schema": "whetstone-run/99"}), encoding="utf-8"
        )

    with pytest.raises(run_ledger.LedgerUnreadable) as refused:
        morning.resolve_last_night(tmp_path)
    assert "night-c" in str(refused.value), refused.value


def test_a_named_run_whose_ledger_disagrees_with_its_directory_is_refused(tmp_path: Path) -> None:
    """The directory says one run, the ledger declares another. Refused, naming both."""
    _written(tmp_path, run_id="night-a", recorded_on="2026-08-25")
    renamed = tmp_path / "night-b"
    (tmp_path / "night-a").rename(renamed)

    with pytest.raises(morning.RunIdentityMismatch) as refused:
        morning.load_named_run(renamed)
    message = str(refused.value)
    assert "night-a" in message and "night-b" in message, message


def test_a_named_run_that_agrees_is_loaded(tmp_path: Path) -> None:
    """The control: the identity check is a discriminator, not a blanket refusal."""
    _written(tmp_path, run_id="night-a", recorded_on="2026-08-25")
    assert morning.load_named_run(tmp_path / "night-a").run_id == "night-a"


def test_the_gates_promotions_directory_is_not_read_as_a_night(tmp_path: Path) -> None:
    """`runs/promotions/` is the gate's own home under the same root, not a corrupt night.

    The gate writes `runs/promotions/<id>.json` (`gate.py:37`, `PROMOTIONS_DIR`), so on any real
    machine the runs root holds a sibling directory that is not a night and has no ledger. A scan
    that refused it would refuse every healthy tree the moment a gate had ever run — the refusal
    would be correct about the bytes and wrong about the world.

    This is the one exclusion, it is by name, and it borrows the gate's own constant by identity so
    the two cannot drift apart. It is emphatically **not** the "skip what you cannot read" rule the
    test above forbids: a directory this project writes on purpose, for another purpose, is a
    different fact from a night whose ledger will not parse.
    """
    from whetstone.loop.gate import PROMOTIONS_DIR

    assert morning.PROMOTIONS_DIR is PROMOTIONS_DIR

    _written(tmp_path, run_id="night-a", recorded_on="2026-08-25")
    promotions = tmp_path / PROMOTIONS_DIR
    promotions.mkdir()
    (promotions / "gate-001.json").write_text("{}", encoding="utf-8")

    assert morning.resolve_last_night(tmp_path).run_id == "night-a"


def test_a_runs_root_holding_only_promotions_is_no_runs(tmp_path: Path) -> None:
    """The exclusion cannot manufacture an empty morning: no night is still `NoRuns`."""
    (tmp_path / "promotions").mkdir()
    with pytest.raises(morning.NoRuns):
        morning.resolve_last_night(tmp_path)


def test_the_ordering_fixture_defeats_an_mtime_resolver(tmp_path: Path) -> None:
    """The fixture's teeth, proven rather than described in a docstring.

    `test_the_greatest_declared_recorded_on_wins` is only worth its line if the fixture would
    *catch* the wrong implementation, and the wrong implementation here is the obvious one: sort
    the run directories by modification time and take the newest. So it is written out and its
    answer asserted to differ.

    mtime is a property of the filesystem rather than of the run — a copied, rsynced or restored
    directory re-dates itself, and every night in a tree restored from backup shares one timestamp.
    An implementation that used it would be right on the machine it was written on and wrong on the
    first machine that mattered.
    """
    _three_nights(tmp_path)

    def by_mtime(root: Path) -> str:
        newest = max(
            (one for one in root.iterdir() if one.is_dir()),
            key=lambda one: (one / run_ledger.LEDGER_FILE).stat().st_mtime,
        )
        return newest.name

    def by_name(root: Path) -> str:
        return sorted(one.name for one in root.iterdir() if one.is_dir())[-1]

    assert by_mtime(tmp_path) == "zulu-run"
    assert by_name(tmp_path) == "zulu-run"
    assert morning.resolve_last_night(tmp_path).run_id == "alpha-run", (
        "WHY THIS IS A FAILURE: the shipped resolver agreed with mtime and alphabetical order, "
        "which this fixture is built to make impossible for a correct implementation. Either the "
        "resolver stopped reading the declared date, or the fixture stopped disagreeing with the "
        "orderings it exists to disagree with — and the second is the worse one, because every "
        "other test in this file would still pass"
    )
