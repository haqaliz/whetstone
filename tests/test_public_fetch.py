"""The human-run fetch: what it carries, what it refuses, and why no test may call it.

Source A is the **externally checkable half** of the corpus. Its whole value is that a reader
can fetch the same rows and check our manifests against them, so the fetch has two obligations
that pull in opposite directions: it must touch the network, and the test suite must never do
so. Both are settled here.

**The output is committed; the fetch is a human-run maintenance step.** `tasks/public/pool.json`
is read by everything downstream and produced by exactly one command, run by hand. A dataset
outage therefore cannot break CI, and a refetch is a reviewable diff rather than a silent change
of what the corpus is about.

**"Tests never fetch" is asserted structurally, not conventionally.** `urllib` is imported inside
`main` and nowhere else, so importing `whetstone.tasks.fetch` cannot put an HTTP client in scope.
An `ast` walk is the only thing that can assert that — an import which works in this venv leaves
no other trace — and the walk carries an anti-vacuity control, because a guard that found no
imports at all would pass for the wrong reason. Ported from the sibling project's
`tests/test_eval_pool_fetch.py:323-400`, whose own control this keeps.

**The transform is where the honesty lives.** the sibling project's committed pool carries six keys
and cannot ground a reward: no `patch`, no `test_patch`, no `FAIL_TO_PASS`, no `PASS_TO_PASS`, no
`environment_setup_commit`. Whetstone needs all five, so the projection is asserted field by field
rather than assumed. And the dataset server **truncates large cells** — a truncated `test_patch`
would be a corrupt task that looks perfectly well-formed — so a truncated row is dropped and its
instance id is recorded in the header, never silently carried.

Offline throughout: every test below builds row envelopes by hand.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from whetstone.tasks.fetch import (
    CONFIG,
    DATASET,
    POOL_SCHEMA,
    ROWS_ENDPOINT,
    SPLIT,
    PoolError,
    pool_document,
    read_pool,
    rows_to_pool,
)

#: The module under test, read as **source**. Never imported for the guard's sake: importing to
#: inspect would report on this venv rather than on the file that actually runs.
MODULE = Path(__file__).parent.parent / "src" / "whetstone" / "tasks" / "fetch.py"

# The five columns the sibling project's committed pool omits and a reward cannot be grounded
# without.
GROUNDING_COLUMNS = (
    "patch",
    "test_patch",
    "fail_to_pass",
    "pass_to_pass",
    "environment_setup_commit",
)


def _envelope(**overrides: Any) -> dict[str, Any]:
    """One `/rows` envelope, in the shape the datasets server actually returns.

    The envelope wrapper matters: the server nests the record under `row` and reports
    `truncated_cells` beside it, and a transform written against a flat dict would read `None`
    for every field while looking like it worked.
    """
    row: dict[str, Any] = {
        "instance_id": "pallets__flask-5063",
        "repo": "pallets/flask",
        "base_commit": "182ce3dd15dfa3537391c3efaf9c3ff407355071",
        "environment_setup_commit": "182ce3dd15dfa3537391c3efaf9c3ff407355071",
        "problem_statement": "Add subdomain to flask routes command",
        "patch": "diff --git a/src/flask/cli.py b/src/flask/cli.py\n",
        "test_patch": "diff --git a/tests/test_cli.py b/tests/test_cli.py\n",
        "FAIL_TO_PASS": '["tests/test_cli.py::test_subdomain"]',
        "PASS_TO_PASS": '["tests/test_cli.py::test_cli_name"]',
    }
    truncated = overrides.pop("truncated_cells", [])
    for key, value in overrides.items():
        if value is None:
            row.pop(key, None)
        else:
            row[key] = value
    return {"row_idx": 0, "row": row, "truncated_cells": list(truncated)}


# --------------------------------------------------------------------------------------
# The projection: exactly the columns a reward can be grounded on
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("column", GROUNDING_COLUMNS)
def test_the_pool_carries_every_column_the_siblings_pool_omits(column: str) -> None:
    """The five that make the difference between a pool and a corpus.

    The sibling project's committed pool has six keys — instance_id, repo, base_commit,
    problem_statement and two derived fields — and none of these. A pool without `test_patch` has no
    held tests, and one without `FAIL_TO_PASS` has nothing that must go green: it can describe an
    instance but it cannot ground a reward. Parametrised so a dropped column names itself.
    """
    records, _ = rows_to_pool([_envelope()])

    assert len(records) == 1
    assert column in records[0], f"the pool dropped {column!r}, which a reward cannot be ground on"


def test_the_declared_node_ids_are_parsed_out_of_their_json_string() -> None:
    """SWE-bench stores both lists as a JSON-encoded string, not as a list.

    Left as a string the field would still be truthy, still serialise, and still round-trip — and
    every downstream `for node_id in record.fail_to_pass` would iterate over **characters**.
    """
    records, _ = rows_to_pool([_envelope()])

    assert records[0]["fail_to_pass"] == ["tests/test_cli.py::test_subdomain"]
    assert records[0]["pass_to_pass"] == ["tests/test_cli.py::test_cli_name"]


def test_a_list_valued_declaration_is_taken_as_it_stands() -> None:
    """A server that stops JSON-encoding the column must not become a parse failure."""
    records, _ = rows_to_pool([_envelope(FAIL_TO_PASS=["a.py::b"], PASS_TO_PASS=[])])

    assert records[0]["fail_to_pass"] == ["a.py::b"]
    assert records[0]["pass_to_pass"] == []


def test_records_are_sorted_by_instance_id() -> None:
    """The committed pool must not move its bytes because the server changed page order."""
    records, _ = rows_to_pool(
        [_envelope(instance_id="z__z-2"), _envelope(instance_id="a__a-1")]
    )

    assert [record["instance_id"] for record in records] == ["a__a-1", "z__z-2"]


# --------------------------------------------------------------------------------------
# What the fetch refuses, and what it records rather than dropping
# --------------------------------------------------------------------------------------


def test_a_truncated_cell_drops_the_row_and_reports_its_instance_id() -> None:
    """The datasets server truncates large cells, and a truncated patch is a corrupt task.

    It is the worst possible shape of bad data: the record is well-formed, every field is
    present, and the diff simply stops in the middle. Committed into the pool it would produce a
    task whose gold patch does not apply, reported as an ordinary rejection with nothing anywhere
    pointing at the dataset. So the row is dropped **and its id is returned**, which is what the
    header then publishes — nothing vanishes silently.
    """
    records, truncated = rows_to_pool(
        [
            _envelope(instance_id="good__good-1"),
            _envelope(instance_id="cut__cut-2", truncated_cells=["test_patch"]),
        ]
    )

    assert [record["instance_id"] for record in records] == ["good__good-1"]
    assert truncated == ("cut__cut-2",)


def test_a_cell_truncated_outside_the_columns_we_read_is_not_a_problem() -> None:
    """Truncation only matters for the columns the projection carries.

    `hints_text` is not read, so a server that truncated it has taken nothing from us — and
    dropping the row over it would shrink the corpus for a field no task ever consults.
    """
    records, truncated = rows_to_pool([_envelope(truncated_cells=["hints_text"])])

    assert len(records) == 1
    assert truncated == ()


def test_a_missing_column_raises_rather_than_defaulting() -> None:
    """Dataset drift is loud. A silently absent `test_patch` is a corpus with no held tests."""
    with pytest.raises(PoolError, match="test_patch"):
        rows_to_pool([_envelope(test_patch=None)])


def test_a_repo_that_is_already_a_url_raises_rather_than_being_normalised() -> None:
    """`repo_url` is built as `https://github.com/{repo}.git`; a URL here double-prefixes.

    The sibling project's own note: this bit its stage 1, after a live batch had started spending.
    The transform refuses rather than repairs, because a URL in the source means our assumption
    about the dataset's shape is wrong and that is the thing a human needs to see.
    """
    with pytest.raises(PoolError, match="owner/name"):
        rows_to_pool([_envelope(repo="https://github.com/pallets/flask")])


def test_a_declaration_that_is_neither_a_list_nor_json_raises() -> None:
    with pytest.raises(PoolError, match="FAIL_TO_PASS"):
        rows_to_pool([_envelope(FAIL_TO_PASS="not json at all")])


def test_an_envelope_with_no_row_raises() -> None:
    with pytest.raises(PoolError, match="row"):
        rows_to_pool([{"row_idx": 0, "truncated_cells": []}])


# --------------------------------------------------------------------------------------
# The provenance header is a falsifiable claim, not a decoration
# --------------------------------------------------------------------------------------


def test_the_header_states_the_dataset_coordinates_it_was_fetched_from() -> None:
    """A pool whose provenance a reader cannot re-issue is a pool nobody can check."""
    records, truncated = rows_to_pool([_envelope()])
    document = pool_document(
        records, truncated, revision="abc123", fetched_at="2026-07-28T00:00:00Z", num_rows_total=300
    )

    assert document["schema"] == POOL_SCHEMA
    assert document["dataset"] == DATASET
    assert document["config"] == CONFIG
    assert document["split"] == SPLIT
    assert document["source_url"] == ROWS_ENDPOINT
    assert document["revision"] == "abc123"
    assert document["fetched_at"] == "2026-07-28T00:00:00Z"
    assert document["num_rows_total"] == 300


def test_the_header_s_counts_match_the_records_beneath_them() -> None:
    """The check that makes the published composition falsifiable rather than decorative.

    A regeneration that moved the data but not the claim would otherwise publish a count nobody
    had checked — which is the same shape as every other number this project refuses to state
    without evidence.
    """
    records, truncated = rows_to_pool(
        [
            _envelope(instance_id="a__a-1"),
            _envelope(instance_id="b__b-2"),
            _envelope(instance_id="c__c-3", truncated_cells=["patch"]),
        ]
    )
    document = pool_document(
        records, truncated, revision=None, fetched_at="2026-07-28T00:00:00Z", num_rows_total=3
    )

    assert document["counts"]["records"] == len(document["instances"]) == 2
    assert document["counts"]["truncated"] == 1
    assert document["truncated"] == ["c__c-3"]


def test_the_header_says_that_no_row_filter_is_applied_at_fetch() -> None:
    """The pool is a faithful projection; eligibility is decided by the gates, and ledgered.

    A fetch that quietly filtered would make the rejection ledger's conservation property — the
    ledger plus the eligible set equals the input — true of a denominator somebody had already
    trimmed. The header therefore states the projection rule and states that it filters no rows.
    """
    records, truncated = rows_to_pool([_envelope()])
    document = pool_document(
        records, truncated, revision=None, fetched_at="2026-07-28T00:00:00Z", num_rows_total=1
    )

    assert document["filters"]["rows_filtered"] == 0
    assert "ineligible.json" in document["filters"]["eligibility_decided_by"]


def test_a_written_pool_reads_back_as_the_instances_it_carried(tmp_path: Path) -> None:
    """`read_pool` is the one door into the pool, and it fails closed like `load_task`."""
    records, truncated = rows_to_pool([_envelope()])
    path = tmp_path / "pool.json"
    path.write_text(
        json.dumps(
            pool_document(
                records,
                truncated,
                revision=None,
                fetched_at="2026-07-28T00:00:00Z",
                num_rows_total=1,
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    instances = read_pool(path)

    assert [instance.instance_id for instance in instances] == ["pallets__flask-5063"]
    assert instances[0].repo_url == "https://github.com/pallets/flask.git"
    assert instances[0].fail_to_pass == ("tests/test_cli.py::test_subdomain",)


def test_a_pool_that_is_not_a_pool_raises_naming_the_file(tmp_path: Path) -> None:
    path = tmp_path / "pool.json"
    path.write_text('{"schema": "something-else", "instances": []}')

    with pytest.raises(ValueError, match=r"pool\.json"):
        read_pool(path)


# --------------------------------------------------------------------------------------
# The fetch is structurally incapable of running under the test suite
# --------------------------------------------------------------------------------------


def _imports(tree: ast.AST, root_name: str) -> list[ast.stmt]:
    """Every import statement in `tree` whose root module is `root_name`."""
    found: list[ast.stmt] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] == root_name for alias in node.names):
                found.append(node)
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module
            and node.module.split(".")[0] == root_name
        ):
            found.append(node)
    return found


def test_the_network_client_is_imported_only_inside_main() -> None:
    """Importing this module must not put an HTTP client in scope.

    That is what keeps the whole suite offline: the network lives in one function no test calls.
    A convention would be forgettable; this is structural, and the `ast` walk is the only thing
    that can observe it.
    """
    tree = ast.parse(MODULE.read_bytes(), filename=str(MODULE))

    main = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main"),
        None,
    )
    assert main is not None, "fetch.main is missing — the guard would be vacuous without it"

    inside_main = {id(node) for node in ast.walk(main)}
    outside = [
        f"line {node.lineno}"
        for node in _imports(tree, "urllib")
        if id(node) not in inside_main
    ]

    assert not outside, (
        "`urllib` is imported outside main() in src/whetstone/tasks/fetch.py:\n  "
        + "\n  ".join(outside)
        + "\n\nWhy this fails the build: tests import the pure transform, and the fetch itself "
        "is a human-run step whose OUTPUT is committed. Keeping urllib inside main() is what "
        "makes 'the tests never fetch' a property of the source rather than a habit."
    )


def test_the_guard_actually_observes_the_network_client() -> None:
    """Anti-vacuity control A: the walk must find the import it is policing.

    Without this, deleting the fetch — or renaming `urllib` to a third-party client — would
    leave the guard above green while asserting nothing at all.
    """
    tree = ast.parse(MODULE.read_bytes(), filename=str(MODULE))

    assert _imports(tree, "urllib"), (
        "no `urllib` import found anywhere in fetch.py — either the fetch grew a third-party "
        "HTTP dependency (runtime dependencies are zero, and that is load-bearing) or the "
        "guard above is now vacuous"
    )


def test_the_guard_would_see_an_import_planted_outside_main(tmp_path: Path) -> None:
    """Anti-vacuity control B: the walk is shown catching a planted violation.

    Control A proves the walk sees imports. This proves the *positional* half — that an import
    at module scope is reported rather than silently attributed to `main`.
    """
    planted = tmp_path / "planted.py"
    planted.write_text("import urllib.request\n\n\ndef main() -> int:\n    return 0\n")
    tree = ast.parse(planted.read_bytes(), filename=str(planted))

    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
    inside_main = {id(node) for node in ast.walk(main)}

    assert [node for node in _imports(tree, "urllib") if id(node) not in inside_main]


def test_the_module_imports_only_the_standard_library_and_whetstone_itself() -> None:
    """Zero runtime dependencies is load-bearing, and ingestion gets no exemption.

    A third-party HTTP or dataset client here would also be a client the offline guard above
    knows nothing about, so the two checks are a pair rather than a duplication.
    """
    tree = ast.parse(MODULE.read_bytes(), filename=str(MODULE))

    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])

    offenders = sorted(
        root for root in roots if root != "whetstone" and root not in sys.stdlib_module_names
    )

    assert not offenders, f"fetch.py imports non-stdlib module(s): {offenders}"
