"""A fixture dependency, version 1.0.0. NOT a real package — see ``../../../README.md``.

The whole package is one function, and the only thing that matters about it is that 2.0.0
removes the ``loud`` keyword this version accepts. That removal is a miniature of flask's
``CliRunner(mix_stderr=)`` disappearing in click 8.2, which is the incident the ``environment``
contract exists to refuse.
"""

VERSION = "1.0.0"


def greet(name: str, *, loud: bool = False) -> str:
    """Greet ``name``. ``loud`` is the keyword 2.0.0 deletes."""
    text = f"hello, {name}"
    return text.upper() if loud else text
