"""A transcript holds the user's own code back verbatim, so it must not be committable.

A source-B completion is a patch against one of the author's private repositories, quoted out of
the prompt it answered. That is the same data `.gitignore:16-24` keeps out of this repository and
the reason `tasks/local/` is ignored while only hashes and verdicts are committed. A transcript is
therefore private code, and the guarantee it cannot be committed belongs in a test rather than in
the docstring that asks an operator to choose a good path.

Two halves, deliberately opposite in sign, each the other's anti-vacuity control:

* the documented transcript roots **are** ignored — a broken `git check-ignore` invocation that
  answered "ignored" to everything would satisfy this half alone;
* `reports/` is **not**, and still holds exactly the bake-off's three artifacts — which the same
  broken invocation would fail.

The second half also discharges the aspect's AC9: instrumentation publishes nothing. This suite
passing is the statement that no figure moved.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

#: The roots `.gitignore:20-24` reserves for the loop's own artifacts, which is where a transcript
#: belongs. Written with the **trailing slash** every time: these are directory-only patterns, and
#: `git check-ignore tasks/local` — no slash, directory absent — answers "not ignored".
#: `tests/test_tasks_layout.py::test_the_trailing_slash_form_is_load_bearing` pins that trap; this
#: file inherits it rather than rediscovering it.
TRANSCRIPT_ROOTS = ("runs/", "checkpoints/", "reports/local/")


def _check_ignore(path: str) -> subprocess.CompletedProcess[str]:
    """Ask git whether it would ignore `path`. rc 0 means ignored, rc 1 means it would not."""
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), "check-ignore", "-v", path],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("root", TRANSCRIPT_ROOTS)
def test_every_documented_transcript_root_is_ignored(root: str) -> None:
    """The private half. A completion written here can never reach a commit."""
    result = _check_ignore(root)
    assert result.returncode == 0, (
        f"git would NOT ignore {root!r}, which is a documented home for a transcript. A "
        "transcript quotes the user's own private repository back verbatim, so a plain "
        f"`git add -A` would commit their code: {result.stdout}{result.stderr}"
    )
    assert ".gitignore" in result.stdout, result.stdout


@pytest.mark.parametrize("root", TRANSCRIPT_ROOTS)
def test_a_file_underneath_is_ignored_and_not_only_the_directory(root: str) -> None:
    """The guarantee the guard above only implies.

    A directory-only pattern answers about the directory; what actually gets committed is a file
    inside it. This asserts the thing that matters, and it holds whether or not the directory
    exists on this machine — which the bare-directory form does not.
    """
    result = _check_ignore(f"{root}some-run/transcript.jsonl")
    assert result.returncode == 0, (
        f"a transcript file under {root!r} is committable: {result.stdout}{result.stderr}"
    )


def test_the_published_tree_is_not_ignored_and_this_aspect_added_nothing_to_it() -> None:
    """The opposite-sign control, and the aspect's AC9 in one assertion.

    `reports/` must stay committable — a report nobody can read supports no published number — and
    it must still hold exactly each report directory's three artifacts. Instrumentation produces
    local evidence only; a fourth file here would mean this aspect published a figure, which it
    has no contract to do and no non-comparability disclosure to do it under.

    **The guard moved again when the format-hardening arm's home landed, and only on the D6
    argument** — the same amendment, in lock-step with `test_report.py:961`'s copy. The two
    directories measure **different generation contracts** and are declared non-comparable
    (`PREREGISTRATION.md` § 10.4), so neither is a competing home for the same figure: the
    baseline's figures live in `reports/baseline/` and the hardened contract's in
    `reports/format-hardening/`. A silent list extension remains refused — the permission is
    the argument, in this docstring.

    **The guard moved a third time when the easier-stratum probe's home landed, and only on
    the changed-task-set argument.** The task set is one of the five pinned inputs
    (`PREREGISTRATION.md:131-132`), and a change to any pinned input invalidates the series
    and starts a new one (`PREREGISTRATION.md:133-135`). The probe scores a **different task
    set** — a pre-committed difficulty stratum of the declared source-B set — under the same
    hardened contract, so its figures are a new series, declared non-comparable to both
    existing homes (`PREREGISTRATION.md` § 10.5): the baseline's figures live in
    `reports/baseline/`, the hardened arm's in `reports/format-hardening/`, and the probe's
    in `reports/easier-stratum/` — each the only home of its own. A silent list extension
    remains refused: the permission is the argument, in this docstring.

    **The guard moved a fourth time when the larger-base arm's home landed, and only on the
    changed-candidate-set argument.** Model revision is one of the five pinned inputs
    (`PREREGISTRATION.md:131-132`), and the arm scores the **same declared task set** under
    the same hardened contract with a **new candidate** — a change to a pinned input, which
    invalidates the series and starts a new one (`PREREGISTRATION.md:133-135`). So its
    figures are a new series, declared non-comparable to all three existing homes
    (`PREREGISTRATION.md` § 10.6): the baseline's figures live in `reports/baseline/`, the
    hardened arm's in `reports/format-hardening/`, the probe's in `reports/easier-stratum/`,
    and the arm's in `reports/larger-base/` — each the only home of its own. A silent list
    extension remains refused: the permission is the argument, in this docstring.
    """
    published = _check_ignore("reports/")
    assert published.returncode == 1, (
        f"git ignores reports/, so the committed half of the evidence would not be committed: "
        f"{published.stdout}{published.stderr}"
    )

    reports = REPO_ROOT / "reports"
    relative = (
        path.relative_to(REPO_ROOT).as_posix() for path in reports.rglob("*") if path.is_file()
    )
    held = sorted(name for name in relative if not name.startswith("reports/local/"))
    assert held == [
        "reports/baseline/cost.json",
        "reports/baseline/report.json",
        "reports/baseline/report.md",
        "reports/easier-stratum/cost.json",
        "reports/easier-stratum/report.json",
        "reports/easier-stratum/report.md",
        "reports/format-hardening/cost.json",
        "reports/format-hardening/report.json",
        "reports/format-hardening/report.md",
        "reports/larger-base/cost.json",
        "reports/larger-base/report.json",
        "reports/larger-base/report.md",
    ], (
        f"reports/ holds {held}. The instrumentation aspect publishes nothing: it produces "
        "transcripts and a breakdown, both local. Each report directory holds exactly its own "
        "three artifacts — the bake-off's in reports/baseline/, the format-hardening arm's in "
        "reports/format-hardening/, the easier-stratum probe's in "
        "reports/easier-stratum/ and the larger-base arm's in reports/larger-base/, "
        "non-comparable by the D6, changed-task-set and changed-candidate-set arguments — "
        "and a file appearing elsewhere means a figure about a model was published without "
        "the disclosure PREREGISTRATION.md:356-361 requires beside one"
    )
