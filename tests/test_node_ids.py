"""Pins the node-id seam that ingestion and the reward must share.

A task's ``fail_to_pass``/``pass_to_pass`` are pytest node ids, and STRICT's executed-set check
(``_executed_set_verdict``) is a *set comparison* against them. That comparison only means
something if the ids in the manifest were minted the same way the ids in pytest's report are
reconstructed. Two code paths that both "build a node id" will agree on
``tests/test_a.py::test_plain`` and then disagree on exactly the shapes ``node_id`` exists to
get right — a class-qualified id, or a parametrised one whose ``[1-2]`` suffix belongs to the
name rather than to the path. That disagreement does not look like a bug: it looks like every
ingested task failing the executed-set check for no visible reason.

So ``read_report`` and ``node_id`` are public, ingestion mints through them, and this file
pins the three shapes at the seam itself rather than only where the verifier happens to use
it. ``tests/test_strict.py`` asserts the same shapes through the parser; the duplication is
deliberate — that file is about the reward, this one is about the contract ingestion depends
on, and the second must not disappear if the first is ever rewritten.
"""

from __future__ import annotations

from pathlib import Path

from whetstone.verify.strict import Case, node_id, read_report


def test_node_id_reconstructs_a_plain_function() -> None:
    """The easy shape, and the one two independent implementations would always agree on."""
    assert node_id("tests/test_a.py", "tests.test_a", "test_plain") == "tests/test_a.py::test_plain"


def test_node_id_reconstructs_a_class_qualified_id() -> None:
    """Where a second implementation drifts first: the class is in ``classname``, not the name."""
    assert (
        node_id("tests/test_a.py", "tests.test_a.TestC", "test_method")
        == "tests/test_a.py::TestC::test_method"
    )


def test_node_id_keeps_a_parametrised_id_fully_parametrised() -> None:
    """The ``[1-2]`` suffix is part of the id.

    An ingester that stripped or normalised it would declare ``test_param`` and watch pytest
    report ``test_param[1-2]`` — a mismatch the executed-set check is right to call a failure
    and that nothing about the task would explain.
    """
    assert (
        node_id("tests/test_a.py", "tests.test_a", "test_param[1-2]")
        == "tests/test_a.py::test_param[1-2]"
    )


def test_read_report_mints_the_same_three_shapes(tmp_path: Path) -> None:
    """The seam end to end: ingestion reads a report, and gets ids the verifier will match."""
    report = tmp_path / "report.xml"
    report.write_text(
        '<testsuite>'
        '<testcase file="tests/test_a.py" classname="tests.test_a" name="test_plain"/>'
        '<testcase file="tests/test_a.py" classname="tests.test_a.TestC" name="test_method"/>'
        '<testcase file="tests/test_a.py" classname="tests.test_a" name="test_param[1-2]"/>'
        '</testsuite>'
    )

    cases = read_report(report)

    assert all(isinstance(case, Case) for case in cases)
    assert [case.node_id for case in cases] == [
        "tests/test_a.py::test_plain",
        "tests/test_a.py::TestC::test_method",
        "tests/test_a.py::test_param[1-2]",
    ]
    assert [case.outcome for case in cases] == ["passed", "passed", "passed"]
