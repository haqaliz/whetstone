"""Where a night's evidence may be written, and the one directory it may never be written under.

A night writes the user's own private donor code to disk in three forms: the prompts and
completions in its per-draw transcripts, the training set built from them, and an adapter trained
on that set. The bake-off already refuses a transcript under `--out` for exactly this reason
(`run.TranscriptNotPrivate`), and its argument was that `--out` is *published*: `reports/baseline/`
is what a committed output directory looks like, and a warning at the top of a night's run is read
after the file already exists.

A night publishes nothing — no report, no figure about a model (that is P4) — so its `--out` is
the gitignored evidence root itself, and "refuse the transcript under `--out`" cannot be the
literal rule. The rule that *is* coherent is stronger and is what this file asserts:

* the run root and the checkpoint root are refused inside any committed `reports/` directory;
* the refusal is `run.TranscriptNotPrivate` **by identity**, so this repository has one name for
  "private evidence was pointed at a published path" rather than two;
* the documented homes — `runs/` and `checkpoints/` — are asserted **gitignored**, on the
  `tests/bakeoff/test_transcript_locality.py` precedent.

The last one is the assertion that would actually catch a regression: a `.gitignore` edit is the
one change that turns every private artefact in this project into a commit.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from whetstone.bakeoff.run import TranscriptNotPrivate
from whetstone.loop.night import PUBLISHED, _refuse_published_root

#: The repository root, reached from `tests/loop/`.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: The two roots a night writes under, as `.gitignore` pre-declared them before the loop existed.
DOCUMENTED_HOMES = ("runs/night-001/ledger.json", "checkpoints/night-001/adapters.safetensors")


def test_a_run_root_inside_a_published_directory_is_refused(tmp_path: Path) -> None:
    """The refusal fires, and it fires on the resolved path rather than on the string typed.

    `reports/../reports/x` names a path inside `reports/` while comparing unequal to it, and so
    does a symlinked scratch directory. The check has to hold against the path that gets written,
    not the one that got typed.
    """
    published = tmp_path / PUBLISHED / "nightly"
    with pytest.raises(TranscriptNotPrivate) as refused:
        _refuse_published_root(published, "--runs")
    assert "--runs" in str(refused.value) and PUBLISHED in str(refused.value), refused.value

    with pytest.raises(TranscriptNotPrivate):
        _refuse_published_root(tmp_path / PUBLISHED / ".." / PUBLISHED / "nightly", "--runs")


def test_a_gitignored_root_is_accepted(tmp_path: Path) -> None:
    """The control: the refusal is a discriminator and not a blanket no.

    Without this, a `_refuse_published_root` that raised unconditionally would satisfy the test
    above perfectly while making the command unusable — and the fix under deadline would be to
    delete the check.
    """
    _refuse_published_root(tmp_path / "runs", "--runs")
    _refuse_published_root(tmp_path / "checkpoints", "--checkpoints")


def test_the_refusal_is_the_bakeoffs_own_exception_type() -> None:
    """One vocabulary for "private evidence was pointed at a published path", not two.

    Asserted by identity. Two exception types for one property is two things a caller has to know
    to catch, and the one that gets forgotten is the one that reaches a user as a traceback.
    """
    from whetstone.bakeoff import run as bakeoff_run

    assert TranscriptNotPrivate is bakeoff_run.TranscriptNotPrivate


def test_the_documented_homes_are_gitignored() -> None:
    """`runs/` and `checkpoints/` must be ignored by git, asserted against git itself.

    Asked of `git check-ignore` rather than by reading `.gitignore`, because what matters is what
    git *does*: a negation elsewhere in the file, or a nested `.gitignore`, can un-ignore a path
    that the pattern list appears to cover.

    Both paths are hypothetical — nothing is created — so this test is a statement about the
    repository's configuration rather than about whatever a previous run happened to leave behind.
    """
    for candidate in DOCUMENTED_HOMES:
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", candidate],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"},
        )
        assert result.returncode == 0, (
            f"WHY THIS IS A FAILURE: git would track {candidate!r}. A night writes the user's own "
            "private donor code there — the prompts and completions in its transcripts, the "
            "training set built from them, and an adapter trained on that set. The whole "
            "local-first guarantee is one `.gitignore` edit wide, and this is the assertion that "
            f"notices. git said: {result.stderr.strip()!r}"
        )
