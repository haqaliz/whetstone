"""Whetstone — a model that trains itself overnight, and proves it didn't cheat.

The failure this module prevents: a version number the code asserts rather than knows.
``__version__`` is read from the installed distribution's metadata, never written as a
literal, so it cannot drift from what was actually built and installed. If the package is
not installed, this raises loudly at import time — a silently-wrong version is worse than a
loud failure.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("whetstonehq")
except PackageNotFoundError as exc:  # pragma: no cover - requires an uninstalled checkout
    raise RuntimeError(
        "whetstone is not installed, so its version cannot be resolved from package "
        "metadata. Run `uv sync` to install the project into the environment."
    ) from exc

__all__ = ["__version__"]
