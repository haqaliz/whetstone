"""Two guards pin the slice's promise: the reward path did not move, and the autopsy stays offline.

The autopsy reads stored completions and says *which zero each was*; it is measurement-only. Its
whole claim is that the numbers it produces are the numbers the live runs produced, and that claim
survives only if the reward itself did not change underneath the measurement. `src/whetstone/
verify/` is the reward path — the verifier every recorded verdict was graded against — and
`dig-code.md` § 5 trap 5 records that nothing anywhere in the suite asserts it is untouched. This
file is the missing test, and it is the slice's central promise (`prd.md` D8, R6): a `verify/`
file modified on this branch would make every autopsy count describe a reward that no longer
exists, and nothing in the autopsy's output would look wrong while it happened.

The second guard is the offline half of the same promise. The fine pass re-derives `patch.py`'s own
span logic from the stored completions; the whole value of that is that one night of compute buys
unlimited re-analysis, and an analysis that reached for the model again would be a re-run charging
a replay's price. So nothing on the autopsy's own path may import an inference library — the same
walk, the same root list, the same shape `tests/bakeoff/test_attribution.py:538-559` uses for the
replay.

Both are honesty properties, so both are watched failing before they are trusted
(`CONTRIBUTING.md:56-60`): the `verify/` guard is exercised against a synthetic repository where a
`verify/` file has a staged change, and the AST walk is exercised against a planted inference
import, both inside this file. A guard nobody has seen fail may be passing vacuously, and a vacuous
guard on the reward path is worse than none, because it buys false confidence.

Track A owns `src/whetstone/bakeoff/autopsy.py` and four of the `test_autopsy*.py` files; the
no-inference walk walks their paths the moment they land and skips them with a note naming their
owner until then. This file is the only file this track owns.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

#: The repository root, reached from `tests/bakeoff/`. It is the git working tree the `verify/`
#: guard measures, and the base for resolving the autopsy's paths.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: The one directory this slice promises to leave untouched. The autopsy measures the stored
#: rollouts of runs scored against this reward; a reward that moved under the measurement would
#: make every count describe a verifier that no longer exists.
REWARD_PATH = "src/whetstone/verify/"

#: The autopsy's own path: the module and the files that test it, as the no-inference walk's
#: scope. `autopsy.py` and four of the test files land with Track A and are skipped (with a note
#: naming their owner) until they do; this file is walked from the day it is written.
AUTOPSY_PATHS = (
    "src/whetstone/bakeoff/autopsy.py",
    "tests/bakeoff/test_autopsy.py",
    "tests/bakeoff/test_autopsy_markers.py",
    "tests/bakeoff/test_autopsy_partition.py",
    "tests/bakeoff/test_autopsy_mapping.py",
    "tests/bakeoff/test_autopsy_cli.py",
    "tests/bakeoff/test_autopsy_guards.py",
)

#: Import roots that would mean a model was consulted on the autopsy's own path. Deliberately
#: wider than `mlx`, and identical to the list the replay's guard carries
#: (`test_attribution.py:113-115`): the autopsy must cost no compute, and `torch` or `openai`
#: would break that exactly as `mlx_lm` would.
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {"mlx", "mlx_lm", "torch", "transformers", "openai", "anthropic", "huggingface_hub"}
)


def _git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Real git, with the developer's own configuration switched off.

    The same environment scrubbing `whetstone.verify.repo._git` does, in the shape
    `test_attribution.py:118-141` uses: a machine-local `hooksPath` or identity would change
    which diff the guard measures. The author variables are pinned too, so a commit made in the
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


def _synthetic_reward_tree(tmp_path: Path) -> Path:
    """A tiny repository with an `origin/master` ref and one committed `verify/` file.

    The shape the guard's own invocation needs: a base the diff is measured against (pinned as
    `refs/remotes/origin/master`, the ref the `origin/master` shorthand resolves to) and the
    reward path with content. `_git`'s env scrubs identity and config, so none of the
    developer's settings leak into the measurement.
    """
    tree = tmp_path / "tree"
    tree.mkdir()
    verify = tree / REWARD_PATH
    verify.mkdir(parents=True)
    (verify / "planted.py").write_text("value = 1\n", encoding="utf-8")

    assert _git(["init", "--quiet", "-b", "master"], cwd=tree).returncode == 0
    assert _git(["add", "."], cwd=tree).returncode == 0
    committed = _git(["commit", "-qm", "base"], cwd=tree)
    assert committed.returncode == 0, committed.stderr
    assert (
        _git(["update-ref", "refs/remotes/origin/master", "HEAD"], cwd=tree).returncode == 0
    )
    return tree


# --------------------------------------------------------------------------------------------
# Guard one: the reward path did not move on this branch.
# --------------------------------------------------------------------------------------------


def test_the_reward_path_did_not_move() -> None:
    """The slice's central promise: the `verify/` diff against `origin/master` is empty.

    The autopsy's counts describe runs graded against this reward, so the reward itself must not
    change on the same branch — a modified `verify/` file means the measurement and the thing it
    measures drift apart, and the counts describe a verifier that no longer exists. `dig-code.md`
    § 5 trap 5 records that no test anywhere asserted this before; this is that test, and the
    planted-violation exercise below is what proves it can fail.
    """
    result = _git(["diff", "--stat", "origin/master", "--", REWARD_PATH], cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "", (
        f"the reward path moved on this branch:\n{result.stdout}\n\n"
        "WHY THIS IS A FAILURE: the autopsy's whole claim is that it measures the runs the "
        "bake-off actually graded. A change under src/whetstone/verify/ on the same branch "
        "means the counts describe a reward that no longer exists, and nothing in the "
        "autopsy's output would look wrong while it happened."
    )


def test_a_staged_change_under_verify_is_reported_by_the_guard(tmp_path: Path) -> None:
    """The guard above, proven able to fail: a staged `verify/` change must be reported.

    `CONTRIBUTING.md:56-60`: a guard nobody has seen fail may be passing vacuously, and this one
    would be trivially vacuous — it passes on the real tree today because nothing touched
    `verify/` yet, which proves nothing about the command it runs. So the exact command the guard
    runs is exercised against a synthetic repository with an `origin/master` ref and a committed
    `verify/` file: clean, the command reports nothing; with a staged change under `verify/`, it
    must report the file. Only a command that actually looks fails the second half.
    """
    tree = _synthetic_reward_tree(tmp_path)

    clean = _git(["diff", "--stat", "origin/master", "--", REWARD_PATH], cwd=tree)
    assert clean.returncode == 0, clean.stderr
    assert clean.stdout == "", (
        "the guard's own command reports a diff against a tree where verify/ is untouched, so "
        "the real-tree assertion above would be passing for the wrong reason."
    )

    planted = tree / REWARD_PATH / "planted.py"
    planted.write_text("value = 2\n", encoding="utf-8")
    assert _git(["add", str(planted)], cwd=tree).returncode == 0

    dirty = _git(["diff", "--stat", "origin/master", "--", REWARD_PATH], cwd=tree)
    assert dirty.returncode == 0, dirty.stderr
    assert dirty.stdout and "planted.py" in dirty.stdout, (
        "a staged change under src/whetstone/verify/ produced no diff output, so the guard "
        "above cannot detect the violation it exists to refuse."
    )


# --------------------------------------------------------------------------------------------
# Guard two: the autopsy's own path imports no inference library.
# --------------------------------------------------------------------------------------------


def _imported_roots(source: bytes) -> set[str]:
    """The top-level package of every import in `source`, function-local ones included.

    `ast.walk` rather than a top-of-file read: an import moved inside a function would otherwise
    be invisible — which is exactly where a "just this once" model call would go. Relative imports
    (`from .x import y`) are invisible too, by `node.level == 0`: the documented porting-trap
    shape (`docs/ROADMAP.md` § 7), and the autopsy's path is first-party code that imports by
    absolute name.
    """
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source, filename="<source>")):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_the_walk_reports_an_import_it_is_given() -> None:
    """Anti-vacuity control: the walk must actually observe imports.

    The guard below asserts an absence, which a parser that saw nothing would satisfy. Fed a
    source that imports `json`, the walk must report `json` — only a walk that reads real imports
    can then be trusted when it reports none on the autopsy's path.
    """
    assert "json" in _imported_roots(b"import json\n"), (
        "the AST walk did not see the stdlib import it was handed, so the no-inference "
        "assertions below would pass by seeing nothing at all."
    )


def test_a_planted_inference_import_is_seen_and_flagged() -> None:
    """The guard's predicate, watched failing: a planted inference import must be flagged.

    `CONTRIBUTING.md:56-60` — an honesty guard must be proven able to fail. None of the autopsy
    paths may import a forbidden root today, so the parametrized guard below would pass without
    ever having refused anything; this pins the detection half by feeding the walk a source that
    does exactly what the guard forbids and asserting the forbidden intersection is reported.
    """
    roots = _imported_roots(b"import json\n\nfrom mlx_lm import load\n")
    assert roots & FORBIDDEN_IMPORT_ROOTS == {"mlx_lm"}, roots


@pytest.mark.parametrize("relative", AUTOPSY_PATHS)
def test_the_autopsy_path_imports_no_inference_library(relative: str) -> None:
    """The autopsy's whole value is that it costs no compute; an import here would spend some.

    `bakeoff/` is exempt from the reward-path guard, and legitimately so — `mlx_runtime.py` must
    import `mlx_lm`. This is a narrower claim about the autopsy's own path: the fine pass
    re-derives `patch.py`'s span logic from the stored completions, and a module or test that
    reached for the model again would be a re-run charging a replay's price. The test files are
    covered too, because a fixture that generated its own completions would make the module's own
    guarantee untestable.

    Files that have not landed yet are skipped, not silently dropped: Track A owns the module and
    four of the test files, and each is walked the moment it exists.
    """
    path = REPO_ROOT / relative
    if not path.is_file():
        pytest.skip(f"{relative} does not exist yet — Track A owns it; walked when it lands")

    roots = _imported_roots(path.read_bytes())

    assert not roots & FORBIDDEN_IMPORT_ROOTS, (
        f"{relative} imports {sorted(roots & FORBIDDEN_IMPORT_ROOTS)}.\n\n"
        "WHY THIS IS A FAILURE: the autopsy exists so one night of compute can be re-analysed "
        "indefinitely without another. An inference import here means the analysis needs the "
        "model back, and every question asked of the data costs a generation pass again."
    )
    # Anti-vacuity per file: an empty module would satisfy the absence above.
    assert roots, (
        f"{relative} contains no import at all, so the assertion above holds for a file nothing "
        "was checked against. A guard that walks a set of files must find imports in them "
        "(`CONTRIBUTING.md:60`)."
    )
