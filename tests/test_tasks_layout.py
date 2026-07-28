"""The `tasks/` layout: what of the corpus is committed, and what can never be.

Half of this project's planned corpus is mined from the user's own repositories, and that half
must never enter this repository — `.gitignore:16-24` says so, and CLAUDE.md's "no data egress"
guardrail is why. The other half is public and must be committed, because a corpus nobody can
inspect cannot support a published number. `tasks/` therefore has two halves with opposite
rules, and a rule that lives only in prose is one an ordinary `git add -A` breaks silently.

So the split is asserted here against **git's own answer** — `git check-ignore` — rather than
against a reading of `.gitignore`. The two guards are deliberately opposite in sign, and each
is the other's anti-vacuity control: a broken invocation that answered "not ignored" to
everything would satisfy the committed-half test while failing the private-half test, and a
pattern widened to `/tasks/` would do the reverse.

One trap is worth naming, because falling into it produces a green test that checks nothing:
`/tasks/local/` is a **directory-only** pattern, and `git check-ignore tasks/local` — no
trailing slash, directory not present — reports **not ignored**. Every path below is therefore
written in the trailing-slash form, and `test_the_trailing_slash_form_is_load_bearing` pins
that reasoning so a future tidy-up cannot quietly delete the slashes and the guarantee with it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS = REPO_ROOT / "tasks"


def _flat(text: str) -> str:
    """Collapse whitespace so a prose guard survives a re-wrap — same helper as `test_docs.py`."""
    return " ".join(text.split())


def _check_ignore(path: str) -> subprocess.CompletedProcess[str]:
    """Ask git whether it would ignore `path`. rc 0 means ignored, rc 1 means it would not."""
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), "check-ignore", "-v", path],
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_users_own_mined_tasks_cannot_be_committed() -> None:
    """The private half. A source-B manifest under `tasks/local/` is the user's own code."""
    directory = _check_ignore("tasks/local/")
    assert directory.returncode == 0, (
        "git would NOT ignore tasks/local/. The user's mined tasks are their own data and a "
        f"plain `git add -A` would commit them: {directory.stdout}{directory.stderr}"
    )
    assert ".gitignore" in directory.stdout, directory.stdout

    # The file, not only the directory: this is the thing that must never be committable, and
    # it answers independently of whether `tasks/local/` happens to exist on this machine.
    manifest = _check_ignore("tasks/local/contig/some-mined-task.json")
    assert manifest.returncode == 0, (
        f"a mined source-B manifest is committable: {manifest.stdout}{manifest.stderr}"
    )


def test_the_committed_half_of_the_corpus_is_not_ignored() -> None:
    """`tasks/` itself, and both committed halves, must stay committable.

    Widening the ignore to `/tasks/` would make the public corpus and the source-B recipes
    invisible too — and then *no* half of the corpus is checkable by a reader, which is the
    failure the split exists to avoid.
    """
    for path in (
        "tasks/",
        "tasks/README.md",
        "tasks/public/",
        "tasks/public/instances/some-public-task.json",
        "tasks/recipes/",
        "tasks/recipes/contig.json",
    ):
        result = _check_ignore(path)
        assert result.returncode == 1, (
            f"git ignores {path!r}, so the committed half of the corpus would not be committed: "
            f"{result.stdout}{result.stderr}"
        )


def test_the_trailing_slash_form_is_load_bearing(tmp_path: Path) -> None:
    """Why every path above ends in `/`, asserted rather than left as a comment.

    `/tasks/local/` is directory-only. Asked about `tasks/local` — no slash, **and the directory
    absent** — git answers "not ignored". A guard written that way would report the private half
    as committable while it is in fact protected, and the obvious "fix" would be to widen the
    pattern. Both spellings are asserted here so the difference is documented by a failing test
    rather than by a comment nobody reads.

    **Asserted in a scratch repository, not this one, and that is the point of the test rather
    than an inconvenience.** The no-slash spelling answers "not ignored" only while the directory
    does not exist; once a mint has actually run, `tasks/local/` is on disk and git answers
    "ignored" to both spellings. An earlier version of this test asked this repository directly
    and passed for exactly as long as nobody had minted anything — it went red the first time the
    corpus was built, which is the wrong moment to learn that a guard depended on absence. The
    scratch repository fixes the condition the reasoning is about instead of inheriting whatever
    the working tree happens to hold.
    """
    scratch = tmp_path / "repo"
    scratch.mkdir()
    subprocess.run(["git", "-C", str(scratch), "init", "--quiet"], check=True)
    (scratch / ".gitignore").write_text("/tasks/local/\n")

    def ask(path: str) -> int:
        return subprocess.run(
            ["git", "-C", str(scratch), "check-ignore", path],
            capture_output=True,
            text=True,
            check=False,
        ).returncode

    assert ask("tasks/local/") == 0, (
        "the directory-only pattern did not ignore the trailing-slash spelling, so the form "
        "every guard above is written in does not do what they rely on"
    )
    assert ask("tasks/local") == 1, (
        "git answered the same for both spellings against an absent directory; the "
        "trailing-slash reasoning above is stale and the other guards need re-reading"
    )

    # And the guarantee the guards actually depend on: a FILE underneath is ignored either way,
    # which is why `test_the_users_own_mined_tasks_cannot_be_committed` asks about a manifest
    # path as well as the directory. That one holds whether or not anything has been minted.
    assert ask("tasks/local/contig/some-mined-task.json") == 0


def test_the_layout_exists_and_the_private_half_is_untracked() -> None:
    """The directories are real, and nothing under `tasks/local/` has ever been tracked."""
    assert (TASKS / "README.md").is_file(), "tasks/ has no README, so its rules exist nowhere"
    assert (TASKS / "public" / ".gitkeep").is_file()
    assert (TASKS / "recipes" / ".gitkeep").is_file()

    tracked = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "tasks/local"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert tracked.stdout.strip() == "", (
        f"the user's own tasks are tracked in this repository: {tracked.stdout}"
    )


def test_the_readme_states_the_recipe_and_ledger_rule() -> None:
    """The resolution of a conflict the roadmap did not notice, stated where a stranger finds it.

    `docs/ROADMAP.md:244` asks `tasks/` to hold instances from both sources with committed
    provenance; `.gitignore` says the user's own tasks are never committed. Both cannot be true
    of source B. The resolution — commit the recipe and the liveness ledger, never the mined
    instances — is what makes the absence of half the corpus auditable instead of merely
    convenient, and a reader who does not find it stated assumes the corpus was cherry-picked.
    """
    readme = _flat((TASKS / "README.md").read_text())
    for claim in (
        "the recipe and the liveness ledger, never the mined instances",
        "docs/ROADMAP.md",
        ".gitignore",
        "re-derive",
    ):
        assert claim in readme, f"tasks/README.md no longer says {claim!r}"
