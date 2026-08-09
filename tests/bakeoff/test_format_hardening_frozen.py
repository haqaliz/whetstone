"""The AC2 pins: the reward path did not move, and now attribution.py is pinned with it.

The format-hardening slice builds a validator and a retry wrapper *beside* the reward path,
and the two must never touch. `src/whetstone/verify/` is the reward every recorded verdict
was graded against, `patch.py` is the extractor whose never-repair rule the validator restates
and whose span logic the autopsy re-derives, and `attribution.py` is the replay that reads the
transcript's coarse causes. A change to any of them on this branch would make the retry
decision, the autopsy's counts, or the caught-hack count describe a harness that no longer
exists — with nothing in the outputs looking wrong while it happened.

`test_autopsy_guards.py:126-143` pins `verify/` alone; this file extends the same command to
all three paths — `attribution.py` is the missing guard, and the diff-stat pin is the AC2
promise (`docs/planning/p2-format-hardening/card.md:38-39`, PRD R7).

Two halves, and each is the other's anti-vacuity control (`CONTRIBUTING.md:56-60`):

* the real-tree assertion — the three paths are byte-identical to `origin/master`;
* the synthetic exercise — the exact command the assertion runs is executed against a
  repository where a planted change exists, and must report it. A guard nobody has seen fail
  may be passing vacuously, and a vacuous guard on the reward path is worse than none.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

#: The repository root, reached from `tests/bakeoff/`. It is the git working tree the pins
#: measure, and the base for the synthetic exercise below.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: The three paths this slice promises to leave byte-identical to `origin/master`: the reward,
#: the extractor whose never-repair rule the validator restates, and the attributor the
#: autopsy reads through (`prd.md` R7).
FROZEN_PATHS = (
    "src/whetstone/verify/",
    "src/whetstone/bakeoff/patch.py",
    "src/whetstone/bakeoff/attribution.py",
)


def _git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Real git, with the developer's own configuration switched off.

    The same environment scrubbing `whetstone.verify.repo._git` does, in the shape
    `test_autopsy_guards.py:69-94` uses: a machine-local `hooksPath` or identity would change
    which diff the pin measures. The author variables are pinned too, so a commit made in the
    synthetic exercise cannot inherit the developer's identity.
    """
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_AUTHOR_NAME": "guard",
            "GIT_AUTHOR_EMAIL": "guard@example.invalid",
            "GIT_COMMITTER_NAME": "guard",
            "GIT_COMMITTER_EMAIL": "guard@example.invalid",
            "HOME": str(cwd),
        },
        check=False,
    )


def _synthetic_tree(tmp_path: Path) -> Path:
    """A tiny repository with an `origin/master` ref and one committed file per frozen path.

    The shape the pin's own invocation needs: a base the diff is measured against (pinned as
    `refs/remotes/origin/master`, the ref the `origin/master` shorthand resolves to) and the
    three frozen paths with content. `_git`'s env scrubs identity and config, so none of the
    developer's settings leak into the measurement.
    """
    tree = tmp_path / "tree"
    for relative in FROZEN_PATHS:
        if relative.endswith("/"):
            directory = tree / relative
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "planted.py").write_text("value = 1\n", encoding="utf-8")
        else:
            target = tree / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("value = 1\n", encoding="utf-8")

    assert _git(["init", "--quiet", "-b", "master"], cwd=tree).returncode == 0
    assert _git(["add", "."], cwd=tree).returncode == 0
    committed = _git(["commit", "-qm", "base"], cwd=tree)
    assert committed.returncode == 0, committed.stderr
    assert (
        _git(["update-ref", "refs/remotes/origin/master", "HEAD"], cwd=tree).returncode == 0
    )
    return tree


def test_the_frozen_paths_are_byte_identical_to_origin_master() -> None:
    """The AC2 pin: `verify/`, `patch.py` and `attribution.py` moved nowhere on this branch.

    The validator decides retries on the autopsy's taxonomy; the autopsy reads
    `attribution.py`'s coarse causes; both restate `patch.py`'s never-repair rule. A change to
    any of the three on the same branch means the decision, the counts and the caught-hack
    floor all describe a harness that no longer exists — and nothing in their outputs would
    look wrong while it happened.
    """
    result = _git(["diff", "--stat", "origin/master", "--", *FROZEN_PATHS], cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "", (
        f"a frozen path moved on this branch:\n{result.stdout}\n\n"
        "WHY THIS IS A FAILURE: the format-hardening slice builds beside the reward path and "
        "depends on it being exactly what every recorded verdict was graded against. A change "
        "under src/whetstone/verify/, patch.py or attribution.py on the same branch means the "
        "retry decision and the autopsy describe a harness that no longer exists."
    )


def test_a_planted_change_is_reported_by_the_pin(tmp_path: Path) -> None:
    """The pin above, proven able to fail: a planted change in any frozen path is reported.

    `CONTRIBUTING.md:56-60`: a guard nobody has seen fail may be passing vacuously, and this
    one would be trivially vacuous — it passes on the real tree today because nothing touched
    the frozen paths yet, which proves nothing about the command it runs. So the exact command
    the pin runs is exercised against a synthetic repository with an `origin/master` ref and
    one committed file per frozen path: clean, the command reports nothing; with a planted
    change in **each** of the three paths, it must report all three. Only a command that
    actually looks fails the second half.
    """
    tree = _synthetic_tree(tmp_path)

    clean = _git(["diff", "--stat", "origin/master", "--", *FROZEN_PATHS], cwd=tree)
    assert clean.returncode == 0, clean.stderr
    assert clean.stdout == "", (
        "the pin's own command reports a diff against a tree where the frozen paths are "
        "untouched, so the real-tree assertion above would be passing for the wrong reason."
    )

    planted: list[Path] = []
    for relative in FROZEN_PATHS:
        target = tree / relative / "planted.py" if relative.endswith("/") else tree / relative
        target.write_text("value = 2\n", encoding="utf-8")
        planted.append(target)
    for target in planted:
        assert _git(["add", str(target)], cwd=tree).returncode == 0

    dirty = _git(["diff", "--stat", "origin/master", "--", *FROZEN_PATHS], cwd=tree)
    assert dirty.returncode == 0, dirty.stderr
    assert dirty.stdout, (
        "a change planted in the frozen paths produced no diff output, so the pin above "
        "cannot detect the violation it exists to refuse."
    )
    for relative in FROZEN_PATHS:
        name = relative.rstrip("/").split("/")[-1]
        assert name in dirty.stdout, (
            f"a planted change under {relative!r} is missing from the pin's report:\n"
            f"{dirty.stdout}"
        )
