"""The bake-off's model weights: multi-GiB files that must never enter this repository.

The baseline bake-off loads local MLX checkpoints. `docs/planning/p1-baseline-bakeoff/prd.md:75`
measures the three candidates at 1.62 / 3.99 / 7.74 GiB — **13.4 GiB** for one sweep — and each is
a directory of `.safetensors` blobs plus a HuggingFace-shaped cache around it. Nothing in this
tree stops a plain `git add -A` from taking all of it: `.gitignore` carries no weights pattern, no
model-cache pattern, no `*.safetensors`. That is the failure this file prevents, and it is a
one-way one — a multi-GiB blob committed once is in the history for good, and the honest fixes
(a rewrite, a force-push) are worse than the mistake for anyone who has already cloned.

The rule is `/weights/`, anchored to the repository root the way `/runs/`, `/checkpoints/` and
`/reports/local/` are, and **pre-declared before the directory exists** — the same house pattern
`.gitignore:16-24` already uses for loop artifacts that are not built yet. The protection has to
be in place before the first fetch, not after it, because after it is too late by definition.

Two deliberate choices are worth stating rather than leaving to be re-derived:

*Why `weights/` and not `models/`.* `tests/test_no_inference_on_reward_path.py:134-136` treats
`model` and `models` as reserved first-party name components — a `whetstone.models` on the reward
path is banned by the same guard that bans `openai`. A top-level `models/` would be legal but it
puts a banned word at the root of a repository whose central guard is about that word. `weights/`
names the artifact, not the abstraction, and cannot be confused with a module the guard hunts for.

*Why an in-repo location at all*, when the fetch could point anywhere on the machine: because an
ignore rule only protects paths inside the repository. Pointing at an external directory protects
nothing here and leaves the next person free to fetch into the tree; pre-declaring the in-repo
location makes the safe choice the default one and the unsafe one impossible.

As in `tests/test_tasks_layout.py`, the assertions ask **git** — `git check-ignore` — rather than
reading `.gitignore` and believing our own parse, and the trailing-slash trap documented at
`tests/test_tasks_layout.py:15-19` is handled here the same way: asserted, in a scratch
repository, rather than tripped over.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _check_ignore(path: str) -> subprocess.CompletedProcess[str]:
    """Ask git whether it would ignore `path`. rc 0 means ignored, rc 1 means it would not."""
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), "check-ignore", "-v", path],
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_model_weights_cannot_be_committed() -> None:
    """The directory, and — the part that actually matters — the blobs underneath it.

    A rule that covered only the directory name would still be satisfied by a `.gitignore` that
    let a stray `.safetensors` through, so every shape the fetch can plausibly produce is asked
    about individually: the flat local directory the MLX adapter loads from, and the
    HuggingFace-style `models--org--repo/snapshots/<revision>/` cache layout that
    `huggingface_hub` writes when it is pointed at a local root.
    """
    directory = _check_ignore("weights/")
    assert directory.returncode == 0, (
        "WHY THIS IS A FAILURE: git would NOT ignore weights/, so the bake-off's model "
        "checkpoints are committable. `docs/planning/p1-baseline-bakeoff/prd.md:75` measures the "
        "three candidates at 13.4 GiB together; a single `git add -A` after a fetch puts them in "
        "the history permanently, and no later commit can take them back out. "
        f"git said: {directory.stdout}{directory.stderr}"
    )
    assert ".gitignore" in directory.stdout, (
        "WHY THIS IS A FAILURE: weights/ is ignored, but not by this repository's `.gitignore` — "
        "the match came from somewhere else (a global excludes file, `.git/info/exclude`) that no "
        "clone of this repository inherits. The protection would exist on this machine only. "
        f"git said: {directory.stdout}"
    )

    for blob in (
        "weights/Qwen2.5-Coder-3B-Instruct-4bit/model.safetensors",
        "weights/Qwen2.5-Coder-7B-Instruct-4bit/model-00001-of-00002.safetensors",
        "weights/models--mlx-community--Qwen2.5-Coder-14B-Instruct-4bit/snapshots/abc123/"
        "model.safetensors",
    ):
        result = _check_ignore(blob)
        assert result.returncode == 0, (
            f"WHY THIS IS A FAILURE: the weights FILE {blob!r} is committable. Ignoring the "
            "directory name is not the guarantee this rule exists for — the guarantee is that "
            "`git add -A` cannot pick up a multi-GiB blob. This spelling escapes it. "
            f"git said: {result.stdout}{result.stderr}"
        )


def test_the_rule_is_anchored_and_swallows_nothing_else() -> None:
    """The opposite-sign control: without it, a broken invocation would pass the test above.

    `_check_ignore` reporting "ignored" for everything would satisfy every assertion in this file
    except these, so they are the anti-vacuity control — the same role
    `test_the_committed_half_of_the_corpus_is_not_ignored` plays in `tests/test_tasks_layout.py`.
    They also pin the leading slash: an unanchored `weights/` would match at any depth and could
    silently swallow source or planning material that happens to carry the word.
    """
    for path in (
        "src/whetstone/bakeoff/weights.py",
        "src/whetstone/bakeoff/weights/",
        "docs/planning/p1-baseline-bakeoff/weights/provenance.md",
        "reports/baseline/",
    ):
        result = _check_ignore(path)
        assert result.returncode == 1, (
            f"WHY THIS IS A FAILURE: git ignores {path!r}. The weights rule has been widened past "
            "the repository-root directory it is meant to cover and is now hiding committable "
            "work — and if this fires for every path, the guards above are passing vacuously "
            f"rather than proving anything. git said: {result.stdout}{result.stderr}"
        )


def test_the_trailing_slash_form_is_load_bearing(tmp_path: Path) -> None:
    """Both spellings, asserted with the expectation each actually earns.

    `/weights/` is a **directory-only** pattern. Asked about `weights` — no trailing slash, and
    the directory not present on disk — git answers **not ignored**, because it has been handed
    something it can only read as a file path and the pattern says directories. That is not a
    hole in the rule: the moment `weights/` exists, or the moment the path names a file
    underneath, git answers "ignored". A guard that asserted only the convenient spelling would
    either report a protected tree as unprotected, or — worse — invite someone to "fix" it by
    dropping the slash and widening the pattern to every file called `weights` in the tree.

    **Asserted in a scratch repository rather than this one, deliberately.** The no-slash answer
    depends on the directory being absent, which is true here only until the first fetch runs.
    `tests/test_tasks_layout.py:85-128` records that exact lesson: an earlier version of the
    equivalent guard asked this repository directly and went red the first time the corpus was
    built. A scratch repository fixes the condition the reasoning is about instead of inheriting
    whatever the working tree happens to hold today.
    """
    scratch = tmp_path / "repo"
    scratch.mkdir()
    subprocess.run(["git", "-C", str(scratch), "init", "--quiet"], check=True)
    (scratch / ".gitignore").write_text("/weights/\n")

    def ask(path: str) -> int:
        return subprocess.run(
            ["git", "-C", str(scratch), "check-ignore", path],
            capture_output=True,
            text=True,
            check=False,
        ).returncode

    assert ask("weights/") == 0, (
        "WHY THIS IS A FAILURE: the directory-only pattern did not ignore the trailing-slash "
        "spelling, which is the form every guard in this file is written in. If this answer is "
        "wrong then those guards are not testing what their names claim."
    )
    assert ask("weights") == 1, (
        "WHY THIS IS A FAILURE: git answered 'ignored' to the no-slash spelling against an absent "
        "directory, so the reasoning in this docstring is stale — either git's behaviour changed "
        "or the pattern in `.gitignore` is no longer directory-only. Re-read the other guards "
        "here before trusting them, because they were written around this asymmetry."
    )

    # The guarantee the rule actually rests on, and the reason the test above asks about blobs as
    # well as the directory: a FILE underneath is ignored in either spelling, whether or not
    # anything has been fetched yet.
    assert ask("weights/Qwen2.5-Coder-3B-Instruct-4bit/model.safetensors") == 0, (
        "WHY THIS IS A FAILURE: a directory-only pattern is supposed to ignore everything beneath "
        "the directory unconditionally. If it does not, `/weights/` protects nothing that matters "
        "and the bake-off needs a file-level pattern instead."
    )
