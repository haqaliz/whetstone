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


def test_the_mlx_extra_pins_an_upper_bound() -> None:
    """AC8: the runtime this project trains against is pinned at both ends, not just the floor.

    ``sft.mlx_trainer``'s own docstring says it calls the trainer *"at the pinned version, with
    the declared arguments and nothing else"*. The requirement was ``mlx-lm>=0.31`` — a floor and
    nothing above it — so "the pinned version" named whatever the index served that morning. That
    is the same failure the task format's ``==`` environment pins exist to prevent, on the one
    dependency that decides what a night produces.

    It is not hypothetical. ``mlx-lm`` 0.31.3 made ``config["dropout"]`` an unconditional read in
    ``linear_to_lora_layers``; night #1 resolved to it and died there after 26.6 hours of
    verified rollouts. An upper bound turns that class of change into a resolution failure at
    ``uv sync`` — visible before a night starts, rather than at the end of one.

    Read as text rather than parsed: ``tomllib`` landed in 3.11 and ``requires-python`` is
    ``>=3.10``, so parsing here would narrow the supported range to satisfy a test.
    """
    pyproject = (REPO_ROOT / "pyproject.toml").read_text()
    requirements = [
        line
        for line in pyproject.splitlines()
        if "mlx-lm" in line and not line.lstrip().startswith("#")
    ]

    assert requirements, (
        "WHY THIS IS A FAILURE: no `mlx-lm` requirement was found in pyproject.toml, so this "
        "guard is asserting nothing about a dependency that decides what every night produces"
    )
    for line in requirements:
        assert "<" in line, (
            f"WHY THIS IS A FAILURE: the mlx-lm requirement {line.strip()!r} has no upper bound, "
            "so `the pinned version` means whatever the index served that morning. A library that "
            "changes its LoRA config contract then breaks a night at its last step, after every "
            "rollout has been paid for — which is exactly how night #1 was lost"
        )
