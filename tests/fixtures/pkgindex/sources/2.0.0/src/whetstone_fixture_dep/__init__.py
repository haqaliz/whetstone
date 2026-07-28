"""A fixture dependency, version 2.0.0. NOT a real package — see ``../../../README.md``.

Identical to 1.0.0 except that ``greet`` no longer accepts ``loud``, so every 1.0.0-era call
site raises ``TypeError`` at call time. Deliberately a *call-time* break rather than an import
or attribute error: the point being demonstrated is a task's declared tests FAILING under the
wrong resolution, and a package that could not be imported at all would fail collection
instead, which is a different — and much more obvious — outcome.
"""

VERSION = "2.0.0"


def greet(name: str) -> str:
    """Greet ``name``. The ``loud`` keyword 1.0.0 accepted is gone."""
    return f"hello, {name}"
