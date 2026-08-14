"""The run-side seam over aspect 1's loader: the stratum document as the run's pinned input.

The easier-stratum probe consumes the committed stratum document (`tasks/stratum/easier.json`,
schema `whetstone-stratum/1`) and never recomputes a difficulty live — a task set changed by
the stratum is a new series, which is the non-comparability ground of the later aspects. So the
document is a pinned input, and this file is the run-side seam over the loader that guards it:
aspect 1's `read_document` is consumed **by identity** (imported, never copied — the diffcheck
rule), and the four refusal classes are the module's own.

The checks of spec D4-4 are completed here where the landed loader's suite stops: an unknown
top-level field, a membership that repeats an id, and a membership naming a task the document
*refused* rather than measured are each a named refusal (spec AC 4, D4-4). The run-side half
of the membership check — every id must resolve against the **loaded private corpus**, refused
with the loaded ids — cannot live in the loader, which never sees the loaded tasks (spec Open
question 3), so `include_stratum(membership, tasks)` is this aspect's addition to aspect 1's
module: it selects the membership's tasks in the corpus's own load order (spec D5), so a run's
sequence stays a property of the corpus and the contract SHA never depends on the document's
list order.

Stdlib only. No model, no network, nothing under `verify/`, `patch.py` or `attribution.py`.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from fixtures.repos.mined import build_mined_task

from whetstone.bakeoff import stratum
from whetstone.bakeoff.stratum import (
    EmptyStratum,
    StratumDigestMismatch,
    StratumSchemaError,
    UnknownStratumId,
)

#: The repository root, for the no-inference walk below.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: A three-task corpus for the synthetic documents. The membership tests need a corpus large
#: enough that a membership can be a proper non-empty subset of it.
_CORPUS = ("alpha", "beta", "gamma")


def _counts(task_id: str) -> dict[str, int]:
    """One task's difficulty entry: generic counts, all within the pre-committed band."""
    return {"files": 1, "hunks": 1, "added": 1, "deleted": 1, "f2p": 1, "pins": 0, "blobs": 1}


def _document(
    root: Path,
    members: Sequence[str],
    *,
    corpus: Sequence[str] = _CORPUS,
    **fields: Any,
) -> Path:
    """A valid `whetstone-stratum/1` document over `corpus` with membership `members`.

    The digest is sealed through aspect 1's own `document_digest_of` **after** `fields` are
    applied, so a doctored field does not hide behind a stale digest — a test that plants an
    edit reaches the check it is about (the re-seal pattern of
    `test_stratum_document.py:269-283`). Every corpus id is measured, never refused, so the
    only field a test has to vary is the one it is about.
    """
    raw: dict[str, Any] = {
        "schema": stratum.STRATUM_SCHEMA,
        "rule_digest": stratum.rule_digest(),
        "band": {"max_non_test_files": 1, "max_hunks": 2, "max_changed_lines": 30},
        "corpus": list(corpus),
        "donor_heads": {},
        "difficulty": {task_id: _counts(task_id) for task_id in corpus},
        "refusals": {},
        "membership": list(members),
    }
    raw.update(fields)
    raw["document_digest"] = stratum.document_digest_of(raw)
    out = root / "easier.json"
    out.write_text(json.dumps(raw))
    return out


def _loaded_tasks(root: Path) -> tuple[Any, ...]:
    """Three mined tasks in load order — the shape `include_stratum` consumes."""
    return tuple(
        build_mined_task(root / f"donor-{task_id}", task_id=task_id).task
        for task_id in _CORPUS
    )


def test_a_valid_document_round_trips_with_byte_identical_fields(tmp_path: Path) -> None:
    """Read must equal write: the run consumes exactly what aspect 1's writer would produce."""
    out = _document(tmp_path, ("alpha", "gamma"))

    first = stratum.read_document(out)
    second = stratum.read_document(out)

    assert first == second, (
        "WHY THIS IS A FAILURE: the loader is not deterministic — two reads of one file gave "
        "two parsed documents, so the run's selection depends on which read happened to win"
    )
    assert first.membership == ("alpha", "gamma")
    assert first.corpus == _CORPUS
    assert first.rule_digest == stratum.rule_digest()


def test_an_unknown_schema_is_refused_by_name(tmp_path: Path) -> None:
    """An old-schema document fails decode rather than defaulting (spec N1)."""
    out = _document(tmp_path, ("alpha",), schema="whetstone-stratum/0")

    with pytest.raises(StratumSchemaError) as caught:
        stratum.read_document(out)
    assert "whetstone-stratum/0" in str(caught.value), caught.value


@pytest.mark.parametrize(
    ("field", "name"),
    [
        ({"band": "not-a-dict"}, "a wrong-typed band"),
        ({"membership": "alpha"}, "a non-list membership"),
        ({"difficulty": "not-a-dict"}, "a wrong-typed difficulty"),
    ],
)
def test_a_missing_or_wrong_typed_field_is_refused_by_name(
    tmp_path: Path, field: dict[str, Any], name: str
) -> None:
    """One field, one type: a missing or wrong-typed field is a schema error, never a default."""
    out = _document(tmp_path, ("alpha",), **field)

    with pytest.raises(StratumSchemaError) as caught:
        stratum.read_document(out)
    assert str(caught.value), name


def test_an_unknown_field_is_refused_by_name(tmp_path: Path) -> None:
    """A field this module does not read is refused, never silently trusted by nobody.

    A later schema that added a field would be refused by the schema check; an unknown field
    under schema 1 is a hand-edited or miswritten document, and a loader that ignored it would
    read a membership nobody can see (spec AC 4).
    """
    out = _document(tmp_path, ("alpha",), mystery_field="zzz")

    with pytest.raises(StratumSchemaError) as caught:
        stratum.read_document(out)
    assert "mystery_field" in str(caught.value), (
        f"WHY THIS IS A FAILURE: the refusal does not name the unknown field. Got "
        f"{str(caught.value)!r}"
    )


def test_a_rule_digest_drift_is_refused_naming_the_rule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Any rule-source or band edit invalidates the committed document (spec D7)."""
    out = _document(tmp_path, ("alpha",))
    monkeypatch.setattr(stratum, "rule_digest", lambda: "f" * 64)

    with pytest.raises(StratumDigestMismatch) as caught:
        stratum.read_document(out)
    assert "rule" in str(caught.value).lower(), (
        f"WHY THIS IS A FAILURE: the refusal does not name the rule digest. Got {caught.value!r}"
    )


def test_a_hand_edited_membership_is_refused_by_the_document_digest(tmp_path: Path) -> None:
    """A hand-edited membership is refused rather than trusted (spec D5, AC 9).

    The edit is applied without re-sealing, so the refusal that fires is about the tampering,
    not about any other check.
    """
    out = _document(tmp_path, ("alpha",))
    raw = json.loads(out.read_text())
    raw["membership"] = ["gamma"]
    out.write_text(json.dumps(raw))

    with pytest.raises(StratumDigestMismatch) as caught:
        stratum.read_document(out)
    assert "document" in str(caught.value).lower(), (
        f"WHY THIS IS A FAILURE: the refusal does not name the document digest. Got "
        f"{caught.value!r}"
    )


def test_an_empty_membership_is_refused_by_name(tmp_path: Path) -> None:
    """A stratum of nothing is a usage error, never a vacuous pass (spec AC 3)."""
    out = _document(tmp_path, ())

    with pytest.raises(EmptyStratum) as caught:
        stratum.read_document(out)
    assert "empty" in str(caught.value).lower(), caught.value


def test_duplicate_membership_ids_are_refused_by_name(tmp_path: Path) -> None:
    """A membership that cannot be read as a set is not the set the rule selected (spec D4-4).

    The duplicate is re-sealed, so the refusal that fires is about the shape of the
    membership, not about the tampering.
    """
    out = _document(tmp_path, ("alpha", "alpha"))

    with pytest.raises(StratumSchemaError) as caught:
        stratum.read_document(out)
    assert "alpha" in str(caught.value), (
        f"WHY THIS IS A FAILURE: the refusal does not name the duplicated id. Got "
        f"{str(caught.value)!r}"
    )


def test_a_refused_membership_id_is_refused_by_name(tmp_path: Path) -> None:
    """The membership must name tasks the rule *measured* — a refused task is never selectable.

    The `values` (difficulty) key set must cover the membership (spec D4-4): a membership
    naming a task the document refused would select for scoring a task the rule said has no
    difficulty — the "easier" set wearing a name the document does not support.
    """
    out = _document(
        tmp_path,
        ("alpha",),
        difficulty={task_id: _counts(task_id) for task_id in ("beta", "gamma")},
        refusals={"alpha": "no donor commit, so there is no fix shape to measure"},
    )

    with pytest.raises(UnknownStratumId) as caught:
        stratum.read_document(out)
    assert "alpha" in str(caught.value), (
        f"WHY THIS IS A FAILURE: the refusal does not name the refused member. Got "
        f"{str(caught.value)!r}"
    )


def test_a_membership_id_unknown_to_the_document_corpus_is_refused_by_name(
    tmp_path: Path,
) -> None:
    """A membership naming a task the document never measured is refused by name."""
    out = _document(tmp_path, ("ghost",))

    with pytest.raises(UnknownStratumId) as caught:
        stratum.read_document(out)
    assert "ghost" in str(caught.value), caught.value


def test_include_stratum_refuses_an_id_that_matches_no_loaded_task_naming_the_loaded_ids(
    tmp_path: Path,
) -> None:
    """A membership id that resolves nowhere in the loaded private corpus is refused.

    The scope is the loaded private corpus only (spec Open question 3): a public id, or a
    mistyped id, would select nothing while the run reported a stratum — the exact
    `UnknownDevSubset` failure shape (`run.py:963-982`). The refusal names the id and the
    loaded ids, mirroring that check.
    """
    tasks = _loaded_tasks(tmp_path)
    membership = ("alpha", "ghost")

    with pytest.raises(UnknownStratumId) as caught:
        stratum.include_stratum(membership, tasks)
    message = str(caught.value)
    assert "ghost" in message, (
        f"WHY THIS IS A FAILURE: the refusal does not name the id that matched nothing: "
        f"{message!r}"
    )
    assert "alpha" in message and "beta" in message and "gamma" in message, (
        f"WHY THIS IS A FAILURE: the refusal does not list the loaded ids, so the operator "
        f"cannot see the typo: {message!r}"
    )


def test_include_stratum_returns_the_included_tasks_in_load_order(tmp_path: Path) -> None:
    """Load order, never membership order: a run's sequence is a property of the corpus (D5).

    Two runs must agree on sequence even if the document's list order changed — the contract
    SHA is a digest over sorted posed prompts, but the sweep order is the load order, and a
    sequence that depended on the document's spelling would make runs disagree for no reason.
    """
    tasks = _loaded_tasks(tmp_path)

    included = stratum.include_stratum(("gamma", "alpha"), tasks)

    assert [task.task_id for task in included] == ["alpha", "gamma"], (
        f"WHY THIS IS A FAILURE: the filter returned the membership's order "
        f"({[task.task_id for task in included]!r}) rather than the corpus's load order. Two "
        "runs over one corpus with differently-sorted documents would then disagree on "
        "sequence"
    )


def test_include_stratum_selects_every_loaded_task_when_the_membership_covers_them(
    tmp_path: Path,
) -> None:
    """The filter is intersection, not mutation: loaded tasks outside the membership are gone,
    and every member that IS loaded survives, in order."""
    tasks = _loaded_tasks(tmp_path)

    included = stratum.include_stratum(("alpha", "beta", "gamma"), tasks)

    assert [task.task_id for task in included] == ["alpha", "beta", "gamma"]


def test_the_refusal_classes_are_the_modules_own_by_identity() -> None:
    """The seam imports the module's classes, never copies of them (the diffcheck rule).

    The run-side filter answers "what may be selected" with the same four refusals aspect 1
    defines — a second definition of any of them would be a second answer to the same
    question, with only one of them reviewed.
    """
    assert stratum.EmptyStratum is EmptyStratum
    assert stratum.StratumSchemaError is StratumSchemaError
    assert stratum.StratumDigestMismatch is StratumDigestMismatch
    assert stratum.UnknownStratumId is UnknownStratumId


# --------------------------------------------------------------------------------------------
# The offline guard: the stratum path imports no inference library, and no run/scoring.
# --------------------------------------------------------------------------------------------

#: Import roots that would mean a model was consulted on the stratum's path, plus the two
#: modules whose byte-identity the run depends on being unscoped. The diffcheck root set,
#: with `scoring` added (the plan's list: mlx, mlx_lm, torch, transformers, run, scoring).
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {"mlx", "mlx_lm", "torch", "transformers", "run", "scoring"}
)

#: The paths the no-inference walk covers: aspect 1's module and this aspect's two test
#: files. The filter file lands in Phase 2; the walk skips it until it exists, then covers
#: it forever after.
STRATUM_FILTER_PATHS = (
    "src/whetstone/bakeoff/stratum.py",
    "tests/bakeoff/test_stratum_loader.py",
    "tests/bakeoff/test_stratum_filter.py",
)


def _imported_roots(source: bytes) -> set[str]:
    """The top-level package of every import in `source`, function-local ones included.

    `ast.walk` rather than a top-of-file read: an import moved inside a function would
    otherwise be invisible — which is exactly where a "just this once" model call would go.
    Relative imports are invisible too, by `node.level == 0`: the documented porting-trap
    shape, and this path is first-party code that imports by absolute name.
    """
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source, filename="<source>")):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_the_walk_reports_an_import_it_is_given() -> None:
    """Anti-vacuity control: the walk must actually observe imports."""
    assert "json" in _imported_roots(b"import json\n"), (
        "the AST walk did not see the stdlib import it was handed, so the no-inference "
        "assertions below would pass by seeing nothing at all."
    )


def test_a_planted_inference_import_is_seen_and_flagged() -> None:
    """The guard's predicate, watched failing: a planted inference import must be flagged."""
    roots = _imported_roots(b"import json\n\nfrom mlx_lm import load\n")
    assert roots & FORBIDDEN_IMPORT_ROOTS == {"mlx_lm"}, roots


@pytest.mark.parametrize("relative", STRATUM_FILTER_PATHS)
def test_the_stratum_path_imports_no_inference_library(relative: str) -> None:
    """The stratum is the pre-committed selection the probe runs over — it never costs compute.

    The document is a pure selection over the corpus the project already holds; a module on
    this path that consulted a model would make the membership a function of the model it is
    supposed to select for (`PREREGISTRATION.md:171-177`). The test files are covered too,
    because a fixture that generated its own selection would make the module's own guarantee
    untestable.

    Files that have not landed yet are skipped, not silently dropped — walked the moment they
    exist.
    """
    path = REPO_ROOT / relative
    if not path.is_file():
        pytest.skip(f"{relative} does not exist yet — walked when it lands")

    roots = _imported_roots(path.read_bytes())

    assert not roots & FORBIDDEN_IMPORT_ROOTS, (
        f"{relative} imports {sorted(roots & FORBIDDEN_IMPORT_ROOTS)}.\n\n"
        "WHY THIS IS A FAILURE: the stratum is the pre-committed pinned input of the probe. "
        "An inference import here means the membership depends on the model it is supposed "
        "to select for, and an import of run or scoring drags the run's byte-identity "
        "precedent into the selection"
    )
    assert roots, (
        f"{relative} contains no import at all, so the assertion above holds for a file "
        "nothing was checked against. A guard that walks a set of files must find imports in "
        "them (`CONTRIBUTING.md:60`)."
    )
