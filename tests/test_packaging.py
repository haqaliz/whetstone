"""Asserts the repository ships the files a distribution is obliged to ship, and that they agree.

The failure this prevents: a LICENSE that is missing or silently replaced, and a CHANGELOG
that drifts from the version actually being released — both invisible until someone
downstream depends on them.

Uses ``tomllib`` (Python 3.11+). The runtime package declares ``requires-python = ">=3.10"``
because that is what `mlx` supports; the *development* environment is pinned to 3.12 by
`.python-version`, and nothing under ``src/`` imports ``tomllib``.
"""

from pathlib import Path

# Sorted below the stdlib block on purpose: `requires-python = ">=3.10"` sets ruff's target
# version, and `tomllib` only entered the stdlib in 3.11, so ruff classifies it third-party.
import tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent


def pyproject_version() -> str:
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        project: dict[str, str] = tomllib.load(handle)["project"]
    return project["version"]


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


def test_changelog_documents_the_current_version() -> None:
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{pyproject_version()}]" in changelog


def test_changelog_version_matches_the_installed_distribution() -> None:
    from importlib.metadata import version

    assert pyproject_version() == version("whetstonehq")
