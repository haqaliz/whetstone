"""The stratum's membership recomputation: the committed document, re-derived, equals itself.

The stratum document is the pre-committed pinned input (spec D5), and its whole value is that
a reader — or a test — can re-derive the membership from the committed rule and the corpus
and watch it come out identical. This file is that test: it loads the real source-B corpus,
re-runs `difficulty_of` over every task against the donors the manifests name, recomposes the
document, and asserts it equals `tasks/stratum/easier.json` field by field (spec AC 2).

Two measurements back the rule, and both are asserted here rather than argued:

* the walk's added/deleted agree with git's own `--numstat` on all 66 tasks, lines only —
  `--numstat` reports a rename by destination and a binary file as dashes, so the file count
  is deliberately never compared (`repo.py:87-95`), and a contradiction is a named failure,
  never reconciled (spec D3);
* the rule's composed gold diff is byte-identical to `control.reference_patch(task).diff` —
  the control arm's own re-derivation — on every corpus task, so no second definition of
  "the commit's own fix" exists to disagree with the one the control arm trusts (spec D2, AC 6).

**The machine-level state.** `tasks/local/` is gitignored, so this worktree has no manifests;
the corpus lives in the **primary checkout** of this repository, and the donors live where the
manifests' `repo_url` fields say they do. The test resolves the primary worktree from `git
worktree list --porcelain`, the same way the operator's own machine names it. In CI — a plain
checkout, no donors — `tasks/local/` is absent and the test skips with a reason naming exactly
what is missing (the `requires_sandbox` posture, `test_verify_cli.py:32`); the runbook re-runs
it on the machine before the probe (spec AC 2).
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from whetstone.bakeoff import stratum
from whetstone.bakeoff.control import reference_patch
from whetstone.tasks.manifest import load_tasks
from whetstone.verify.task import Task

#: The repository root, for the committed document and the git calls below.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: The committed document whose membership this file re-derives (spec D5).
STRATUM_DOCUMENT = REPO_ROOT / "tasks" / "stratum" / "easier.json"

#: The machine-level corpus roots: the two donor directories under the primary checkout's
#: gitignored `tasks/local/` (`tasks/README.md:63-64`).
_CORPUS_ROOTS = ("tasks/local/belay", "tasks/local/contig")

#: The frozen reward path, byte-identical to `origin/master` (spec AC 7). The pin lives in
#: `test_format_hardening_frozen.py` too; it is restated here because this aspect's claim is
#: the same one — the rule is offline tooling beside an unmoved reward.
FROZEN_PATHS = (
    "src/whetstone/verify/",
    "src/whetstone/bakeoff/patch.py",
    "src/whetstone/bakeoff/attribution.py",
)

#: git's environment with the machine's configuration switched off — the discipline every
#: real-git call in this suite inherits (`test_format_hardening_frozen.py:42-67`).
_GIT_ENV = {
    "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_TERMINAL_PROMPT": "0",
}


def _primary_root() -> Path:
    """The primary checkout's root, resolved from `git worktree list --porcelain`.

    The first `worktree` entry is the main checkout; in CI — a plain checkout — that entry is
    this repository itself, and the skip below then fires on the missing corpus. Resolved with
    git's own words rather than assumed, so the test still finds the corpus when the layout
    changes.
    """
    completed = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=_GIT_ENV,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    for line in completed.stdout.splitlines():
        if line.startswith("worktree "):
            return Path(line.split(" ", 1)[1])
    raise RuntimeError(f"git worktree list gave no worktree entry:\n{completed.stdout}")


def _machine_corpus() -> tuple[tuple[Task, ...], dict[str, Path]]:
    """The source-B corpus and its donors, or a skip naming exactly what is missing.

    Both halves of the machine-level state are checked and named: the manifests under the
    primary's `tasks/local/`, and every donor the manifests' `repo_url` fields point at.
    Either absent, the recomputation cannot run — and the skip says so.
    """
    primary = _primary_root()
    roots = tuple(primary / root for root in _CORPUS_ROOTS)
    missing = [str(root) for root in roots if not root.is_dir()]
    if missing:
        pytest.skip(
            "the machine-level source-B corpus is absent here: "
            + ", ".join(missing)
            + " do not exist. CI's plain checkout has no donors and no gitignored manifests, "
            "so this recomputation runs only on the operator's machine; the runbook re-runs "
            "it before the probe (spec AC 2)"
        )

    tasks = tuple(load_tasks(roots[0])) + tuple(load_tasks(roots[1]))
    donors: dict[str, Path] = {}
    for task in tasks:
        label = task.provenance.get("donor") or Path(task.repo_url).name
        donors[label] = Path(task.repo_url)
    missing_donors = [str(donor) for donor in donors.values() if not donor.is_dir()]
    if missing_donors:
        pytest.skip(
            "the donor repositories the corpus names are absent here: "
            + ", ".join(missing_donors)
            + " do not exist. The rule reads only the donors' pinned commits, and a donor "
            "that is not on this machine cannot be read"
        )
    return tasks, donors


def _numstat_lines(diff: str, scratch: Path) -> tuple[int, int]:
    """`(added, deleted)` as git's own `--numstat` counts them, binary records excluded.

    `git apply --numstat -z -` parses the patch without writing anything (the
    `repo.py:87-110` posture). A binary record reports dashes rather than numbers — the walk
    counts nothing for it, so it is excluded from the sum, and the comparison is lines only
    by construction (`repo.py:93-95`).
    """
    completed = subprocess.run(
        ["git", "apply", "--numstat", "-z", "-"],
        cwd=str(scratch),
        input=diff,
        capture_output=True,
        text=True,
        env=_GIT_ENV,
        check=False,
    )
    assert completed.returncode == 0, (
        f"git refused to parse the gold patch this test derived from the corpus:\n"
        f"{completed.stderr.strip()}\n---\n{diff[:400]}"
    )
    added = 0
    deleted = 0
    for record in completed.stdout.split("\0"):
        if not record:
            continue
        fields = record.split("\t", 2)
        assert len(fields) == 3, f"could not read git's numstat record: {record!r}"
        if fields[0] == "-" or fields[1] == "-":
            continue
        added += int(fields[0])
        deleted += int(fields[1])
    return added, deleted


def test_the_recomputed_document_equals_the_committed_one_field_by_field() -> None:
    """The membership recomputation (spec AC 2): the rule re-run, byte-equal field by field.

    The committed document is the pinned input; a rule edit changes `rule_digest`, a corpus
    change moves the ids, a donor change moves the counts — and each moves at least one of
    the compared fields, failing this test by name rather than drifting in silence.
    """
    tasks, donors = _machine_corpus()
    committed = json.loads(STRATUM_DOCUMENT.read_text())

    assert len(tasks) == len(committed["corpus"]), (
        "the corpus loaded from the machine does not match the document's: "
        f"{len(tasks)} tasks loaded, {len(committed['corpus'])} declared"
    )

    recomputed = stratum.compose_document(tasks, donors)

    for key in (
        "schema",
        "rule_digest",
        "band",
        "corpus",
        "difficulty",
        "refusals",
        "membership",
        "document_digest",
    ):
        assert recomputed[key] == committed[key], (
            f"the committed document's {key} is no longer what the rule computes.\n\n"
            "WHY THIS IS A FAILURE: the stratum is the pre-committed pinned input; a "
            "document that disagrees with its own rule on the same corpus means a rule edit "
            "or a corpus change landed without regenerating the document. Regenerate it in "
            "the same commit (spec: open risk)."
        )

    assert "timestamp" not in committed, (
        "a write-moment clock would make byte-determinism impossible (spec D5)"
    )
    assert committed["donor_heads"], "the committed document records its donor heads"
    for label, head in committed["donor_heads"].items():
        assert head, f"donor {label!r} has an empty recorded head"


def test_the_walks_added_deleted_agree_with_git_numstat_on_every_corpus_task() -> None:
    """The walk is a measurement, and git's own parse is the referee (spec D3, AC 5).

    Lines only, by construction: `--numstat` reports a rename by its destination and a
    binary file as dashes, neither of which is a line count. A contradiction is a named
    failure — the walk is corrected, never reconciled.
    """
    tasks, _ = _machine_corpus()
    recomputed = stratum.compose_document(tasks, {})

    with tempfile.TemporaryDirectory(prefix="whetstone-stratum-numstat-") as scratch:
        for task in tasks:
            difficulty = recomputed["difficulty"][task.task_id]
            diff = stratum._gold_diff(task)
            assert isinstance(diff, str), f"{task.task_id} refused: {diff}"

            added, deleted = _numstat_lines(diff, Path(scratch))

            assert difficulty["added"] == added and difficulty["deleted"] == deleted, (
                f"task {task.task_id}: the rule's walk reports "
                f"{difficulty['added']}/{difficulty['deleted']} added/deleted lines, git's "
                f"--numstat reports {added}/{deleted} on the same bytes. A contradiction "
                "between the walk and git's own parse is a named failure, never reconciled"
            )


def test_the_rules_composed_diff_equals_the_control_arms_on_every_task() -> None:
    """One definition of "the commit's own fix": the rule's and the control arm's agree (AC 6).

    `control.reference_patch` re-derives the reference through the same `changed_paths` +
    `gold_patch` composition the rule uses; byte-identity on all 66 tasks means no second
    definition exists to disagree with the one the control arm trusts (`control.py:24-29`).
    """
    tasks, _ = _machine_corpus()

    for task in tasks:
        composed = stratum._gold_diff(task)
        assert isinstance(composed, str), f"{task.task_id} refused: {composed}"

        reference = reference_patch(task)
        assert reference.diff is not None, (
            f"{task.task_id}: the control arm could not derive the reference: "
            f"{reference.reason}"
        )

        assert composed == reference.diff, (
            f"task {task.task_id}: the rule's composed gold diff differs from the control "
            "arm's reference patch, byte for byte. A second composition is a second "
            "definition of the commit's own fix, and the one that disagreed would be the "
            "one nobody looked at"
        )


def test_every_recorded_refusal_carries_a_reason() -> None:
    """Refusals are evidence with a name, never a bare id (spec AC 2, `control.py:242-252`)."""
    tasks, donors = _machine_corpus()
    recomputed = stratum.compose_document(tasks, donors)

    for task_id, reason in recomputed["refusals"].items():
        assert reason.strip(), f"task {task_id} is refused with an empty reason"
    assert set(recomputed["difficulty"]) | set(recomputed["refusals"]) == set(
        recomputed["corpus"]
    ), "every corpus id is measured or refused, and never both"


def test_the_membership_is_a_proper_nonempty_subset_of_the_declared_corpus() -> None:
    """The committed membership is the document's own claim, asserted from it (spec D4)."""
    committed = json.loads(STRATUM_DOCUMENT.read_text())

    membership = committed["membership"]
    corpus = committed["corpus"]

    assert 0 < len(membership) < len(corpus), (
        "a degenerate stratum (empty, or the whole corpus) is a usage error, never a "
        "committed document; the writer refuses it by name"
    )
    assert len(set(membership)) == len(membership), "membership ids are unique"
    assert set(membership) <= set(corpus), "membership ids all resolve in the corpus"


def test_the_frozen_reward_paths_are_byte_identical_to_origin_master() -> None:
    """AC 7: the reward path did not move while the selection machinery was built beside it."""
    result = subprocess.run(
        ["git", "diff", "--stat", "origin/master", "--", *FROZEN_PATHS],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=_GIT_ENV,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "", (
        f"a frozen path moved on this branch:\n{result.stdout}\n\n"
        "WHY THIS IS A FAILURE: the stratum rule and the filter it feeds build beside the "
        "reward path and depend on it being exactly what every recorded verdict was graded "
        "against (spec AC 7, `prd.md:151-154`)."
    )
    for relative in FROZEN_PATHS:
        assert (REPO_ROOT / relative).exists(), f"frozen path {relative!r} is missing"


def test_the_recomputation_reaches_zero_skips_on_this_machine() -> None:
    """The recomputation is exercised here, not skipped here: this is the machine's check.

    The test body's skips exist for CI; on the machine that generated the document they must
    never fire, or the field-by-field test above would be asserting over nothing.
    """
    tasks, _ = _machine_corpus()
    assert len(tasks) == 66, (
        "the machine-level source-B corpus is the declared set: 21 belay + 45 contig "
        f"manifests, got {len(tasks)}"
    )
