"""Asserts the repository ships the files a distribution is obliged to ship, and that they agree.

The failure this prevents: a LICENSE that is missing or silently replaced, and a CHANGELOG
that drifts from the version actually being released — both invisible until someone
downstream depends on them.

The version compared against is the **installed distribution metadata**, not a literal parsed
out of ``pyproject.toml``. That is deliberate on two counts. It is the version the built
artifact actually carries and the one ``whetstone --version`` prints, so it is what a user
would see; and reading it this way needs no TOML parser, which keeps the suite runnable on
every interpreter the package claims to support. ``tomllib`` only entered the stdlib in 3.11
while ``requires-python`` is ``>=3.10`` (the floor `mlx` sets), so parsing the file here would
have quietly narrowed the supported range to satisfy a test.
"""

from importlib.metadata import version
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DISTRIBUTION = "whetstonehq"
"""The PyPI distribution name. The import package and the CLI are both ``whetstone``; bare
``whetstone`` was already taken on PyPI, so the three names deliberately differ."""


def released_version() -> str:
    """The version the installed distribution reports.

    Derived by the build backend from ``pyproject.toml``, so this is that value — read from
    the artifact rather than from the source file.
    """
    return version(DISTRIBUTION)


def test_license_exists_and_is_apache() -> None:
    license_path = REPO_ROOT / "LICENSE"
    assert license_path.is_file()
    first_line = license_path.read_text(encoding="utf-8").splitlines()[0]
    assert first_line.strip() == "Apache License"


def test_license_carries_the_full_apache_text() -> None:
    text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "Version 2.0, January 2004" in text
    assert "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION" in text
    assert "APPENDIX: How to apply the Apache License to your work." in text


def test_changelog_documents_the_released_version() -> None:
    """A release whose version has no changelog entry ships undocumented.

    If this fails after a version bump, the likely causes are an un-updated CHANGELOG or a
    stale virtualenv — ``uv sync`` re-reads the version from ``pyproject.toml``.
    """
    released = released_version()
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{released}]" in changelog, (
        f"CHANGELOG.md has no `## [{released}]` section, but that is the version the "
        f"installed {DISTRIBUTION} distribution reports.\n\n"
        "Either the changelog was not updated for this version, or the virtualenv is stale "
        "and predates a version bump in pyproject.toml — run `uv sync` and re-check."
    )
