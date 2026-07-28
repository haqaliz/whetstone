"""Gate 3: install-exit-0 is not evidence. Demonstrated against a real interpreter.

This is the gate whose obvious implementation is wrong, and wrong in the direction that looks
like success. **Measured, not anticipated:** `sphinx==3.5.4`, `pytest==4.6.9`, `pylint==2.13.9`
and `requests==2.4.0` all install cleanly on arm64 CPython 3.12 — and `pytest==4.6.9` cannot be
imported there, because it needs the `imp` module 3.12 removed, and `requests==2.4.0` cannot be
imported on anything from 3.10. A gate that stopped at the installer's exit code would admit all
four and hand the corpus tasks that die at collection time, reported as ordinary rejections with
nothing anywhere pointing at the interpreter. It is the same false green the CI `mlx` step
guards against, for the same reason.

**So the gate imports.** Every installed distribution's top-level modules are derived from its
own metadata — not from a name table, which would be a guess about the mapping from `Jinja2` to
`jinja2` — and imported inside the nominated interpreter.

**The false-green arm is fixtured, and its installer trivially succeeds.** The broken
distribution below is planted directly into a real venv and the `install` callable does nothing
at all, which is the strongest possible statement of "exit 0". The gate must still reject.

**With an anti-vacuity control**, because a probe that imported nothing would pass every arm:
the healthy arm asserts the probe actually checked a module it can name.

Offline throughout. The healthy arm resolves from the committed local index at
`tests/fixtures/pkgindex`, with `--no-index --find-links`; nothing here reaches a registry.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fixtures.repos import FIXTURE_DEP, FIXTURE_DEP_PIN

from whetstone.tasks.gates import (
    GATE_ENVIRONMENT,
    Ineligible,
    check_environment,
    era_pins,
    probe_imports,
    read_era_pins,
)

pytestmark = pytest.mark.skipif(
    shutil.which("uv") is None, reason="gate 3 provisions with uv, which is not installed"
)

#: The recorded index the healthy arm resolves from — the same two wheels
#: `tests/test_environment_pins.py` uses, and for the same reason: a test that reached PyPI to
#: prove something about pinning would be self-refuting.
INDEX = Path(__file__).parent / "fixtures" / "pkgindex"

#: The false green, in the exact shape the measurement found it. A module that imports `imp` is
#: importable on 3.10 and gone on 3.12, which is precisely `pytest==4.6.9`'s failure.
_BROKEN_MODULE = "import imp  # removed in 3.12\n\nVALUE = 1\n"

#: The distribution name and version planted, chosen to read as what it stands in for.
_BROKEN_NAME = "erapin-broken"
_BROKEN_TOP_LEVEL = "erapin_broken"
_BROKEN_VERSION = "4.6.9"


def _venv(root: Path) -> Path:
    """A real venv on this interpreter, and the path to its python.

    Built from `sys.executable` rather than from a version string so nothing can be downloaded:
    the interpreter is already here.
    """
    location = root / "venv"
    subprocess.run(
        ["uv", "venv", "--python", sys.executable, str(location)],
        check=True,
        capture_output=True,
    )
    return location


def _site_packages(interpreter: Path) -> Path:
    """Where the venv's own interpreter says its packages live. Asked, never constructed."""
    completed = subprocess.run(
        [str(interpreter), "-c", "import site; print(site.getsitepackages()[0])"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(completed.stdout.strip())


def _plant_broken(interpreter: Path) -> None:
    """Install a distribution the way an installer that exited 0 would have left it.

    Written by hand rather than built into a wheel because the point of the arm is that nothing
    ran an installer: the metadata is on disk, `uv pip freeze` reports it, and the module cannot
    be imported. That is the state a successful install of `pytest==4.6.9` leaves behind on 3.12.
    """
    site = _site_packages(interpreter)
    (site / f"{_BROKEN_TOP_LEVEL}.py").write_text(_BROKEN_MODULE)
    info = site / f"{_BROKEN_TOP_LEVEL}-{_BROKEN_VERSION}.dist-info"
    info.mkdir(parents=True, exist_ok=True)
    (info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {_BROKEN_NAME}\nVersion: {_BROKEN_VERSION}\n"
    )
    (info / "top_level.txt").write_text(f"{_BROKEN_TOP_LEVEL}\n")
    (info / "INSTALLER").write_text("uv\n")
    (info / "RECORD").write_text(f"{_BROKEN_TOP_LEVEL}.py,,\n")


def _nothing_installed(requirements: list[str], interpreter: Path) -> None:
    """An installer that succeeds and does nothing. The strongest possible 'exit 0'."""


# --------------------------------------------------------------------------------------
# The false green
# --------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def broken(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A venv holding a distribution that installed cleanly and cannot be imported."""
    venv = _venv(tmp_path_factory.mktemp("gate3-broken"))
    _plant_broken(venv / "bin" / "python")
    return venv


def test_a_pin_that_installs_but_cannot_be_imported_is_rejected(broken: Path) -> None:
    """The gate's whole reason to exist, asserted against a real interpreter.

    The installer here does nothing and reports success, so the only thing that can reject this
    environment is the import probe. If this test ever passes with the probe removed, gate 3 has
    silently become an exit-code check.
    """
    with pytest.raises(Ineligible) as raised:
        check_environment(
            [f"{_BROKEN_NAME}=={_BROKEN_VERSION}"],
            venv=broken,
            install=_nothing_installed,
        )

    assert raised.value.gate == GATE_ENVIRONMENT
    assert _BROKEN_TOP_LEVEL in str(raised.value)


def test_the_rejection_names_what_could_not_be_imported_and_why(broken: Path) -> None:
    """A refusal that said only 'environment' would be one nobody could act on.

    The message carries the interpreter's own ImportError, so a reader sees `No module named
    'imp'` — the fact that identifies this as an interpreter-era problem rather than a missing
    dependency — instead of inferring it.
    """
    with pytest.raises(Ineligible) as raised:
        check_environment(
            [f"{_BROKEN_NAME}=={_BROKEN_VERSION}"],
            venv=broken,
            install=_nothing_installed,
        )

    assert "imp" in str(raised.value)


def test_the_probe_reports_the_failure_rather_than_raising(broken: Path) -> None:
    """`probe_imports` is a measurement; the gate is what turns it into a refusal.

    Kept apart so the measurement can be asserted directly. A probe that raised would make
    "which modules did you check" unanswerable in the failing case, which is the case that
    matters.
    """
    result = probe_imports(broken / "bin" / "python")

    assert _BROKEN_TOP_LEVEL in {failure.module for failure in result.failures}


# --------------------------------------------------------------------------------------
# The healthy arm, and the control that makes the probe non-vacuous
# --------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def healthy(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A venv holding one genuinely importable distribution, resolved from the local index."""
    return _venv(tmp_path_factory.mktemp("gate3-healthy"))


def test_an_environment_that_resolves_and_imports_passes_and_reports_exact_pins(
    healthy: Path,
) -> None:
    """The positive case, and the pins it hands the manifest are read from the freeze.

    Read rather than echoed back: what the manifest must carry is the environment the tests will
    actually run in, including whatever the requirement pulled in transitively. Echoing the
    requested list would describe a smaller environment than the one that was measured.
    """
    provisioned = check_environment([FIXTURE_DEP_PIN], venv=healthy, index=INDEX)

    assert FIXTURE_DEP_PIN in provisioned.pins
    assert provisioned.interpreter.is_file()
    assert provisioned.python.startswith("3.")


def test_the_probe_actually_imported_something_it_can_name(healthy: Path) -> None:
    """Anti-vacuity: a probe that checked nothing would pass every arm above.

    Without this, deleting the import loop would leave the healthy arm green and the broken arm
    green, and gate 3 would be an exit-code check wearing a longer docstring.
    """
    result = probe_imports(healthy / "bin" / "python")

    assert not result.failures
    assert FIXTURE_DEP.replace("-", "_") in result.checked


def test_a_requirement_absent_from_the_index_cannot_be_installed(healthy: Path) -> None:
    """The control that proves the index is genuinely the only source.

    Without it, "offline" would be a flag nobody had checked, and the healthy arm might be
    resolving from a warm cache or from PyPI.
    """
    with pytest.raises(Ineligible) as raised:
        check_environment(
            ["whetstone-not-in-the-index==9.9.9"], venv=healthy / ".." / "other", index=INDEX
        )

    assert raised.value.gate == GATE_ENVIRONMENT


# --------------------------------------------------------------------------------------
# Era-pins are hand-determined, and an instance without them is rejected rather than guessed
# --------------------------------------------------------------------------------------


def test_an_instance_with_no_recorded_era_pins_is_rejected_at_this_gate(tmp_path: Path) -> None:
    """The refusal that keeps the corpus honest about what it does not know.

    A repository declares ranges — flask says `click>=8.0` at every commit it has ever had — so
    `environment_setup_commit` cannot answer which versions the era used. Resolving anyway would
    hand the verdict to whatever the index served that morning, which is the exact incident
    `environment` exists to close. Source B escapes this because a donor's `uv.lock` is its
    owner's own recorded resolution; source A has no such artifact, so the answer is a hand-made
    table and an honest refusal when it has no entry.
    """
    table = tmp_path / "era-pins.json"
    table.write_text(
        '{"schema": "whetstone-source-a-era-pins/1", "note": "x", "instances": {}}'
    )

    with pytest.raises(Ineligible) as raised:
        era_pins(read_era_pins(table), "sphinx-doc__sphinx-8721")

    assert raised.value.gate == GATE_ENVIRONMENT
    assert "sphinx-doc__sphinx-8721" in str(raised.value)


def test_a_recorded_instance_yields_its_interpreter_and_its_requirements(
    tmp_path: Path,
) -> None:
    table = tmp_path / "era-pins.json"
    table.write_text(
        '{"schema": "whetstone-source-a-era-pins/1", "note": "x", "instances": '
        '{"pallets__flask-5063": {"python": "3.12", '
        '"requirements": ["click==8.1.3"], "determined_by": "by hand"}}}'
    )

    pins = era_pins(read_era_pins(table), "pallets__flask-5063")

    assert pins.python == "3.12"
    assert pins.requirements == ("click==8.1.3",)


def test_a_recorded_requirement_that_is_not_an_exact_pin_is_refused(tmp_path: Path) -> None:
    """A range in the table would reopen the hole the table exists to close.

    Validated against the loader's own predicate, so the table cannot record something
    `load_task` would later refuse — a manifest that fails to load one instance at a time, a
    whole filter run later.
    """
    table = tmp_path / "era-pins.json"
    table.write_text(
        '{"schema": "whetstone-source-a-era-pins/1", "note": "x", "instances": '
        '{"a__b-1": {"python": "3.12", "requirements": ["click>=8.0"], '
        '"determined_by": "by hand"}}}'
    )

    with pytest.raises(ValueError, match="exact"):
        read_era_pins(table)


def test_the_committed_era_pin_table_records_how_each_entry_was_determined() -> None:
    """The table ships with the repository, and every entry says where its versions came from.

    `determined_by` is required rather than optional because the difference between "found by
    hand, one incident at a time" and "whatever resolved" is the difference between a pinned
    corpus and a pinned-looking one, and only the first is worth committing.
    """
    table = read_era_pins(Path(__file__).parent.parent / "tasks" / "public" / "era-pins.json")

    assert table, "the committed era-pin table is empty, so gate 3 rejects every instance"
    for instance_id, pins in table.items():
        assert pins.determined_by, f"{instance_id} records no provenance for its pins"
        assert pins.requirements, f"{instance_id} records no requirements"
