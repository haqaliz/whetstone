"""Pins the import package's version to the installed distribution's metadata.

The failure this prevents: a hardcoded ``__version__`` literal that drifts from the version
actually built and installed, so the package reports a version it is not. The import package
(``whetstone``) and the distribution (``whetstonehq``) have different names, which makes that
drift easy to introduce and invisible without this test.
"""

from importlib.metadata import version

import whetstone


def test_version_matches_the_installed_distribution_metadata() -> None:
    assert whetstone.__version__ == version("whetstonehq")


def test_version_is_a_non_empty_string() -> None:
    assert isinstance(whetstone.__version__, str)
    assert whetstone.__version__ != ""
