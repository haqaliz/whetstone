"""Two guards on the night-autopsy: it stays offline, and the reward path did not move.

`night_autopsy` reads a finished night's stored evidence and reports its failure partition. Its
whole claim is that the numbers it produces are the numbers the night's own run produced, and that
claim survives only if (a) the analysis needs no model — the entire reason a night's journals and
transcripts are kept is that every later question costs a file read rather than another night of
generation — and (b) the reward the rollouts were graded against did not change underneath the
measurement. `src/whetstone/verify/` is the reward path; a file modified on this branch would make
every count describe a verifier that no longer exists, and nothing in the output would look wrong
while it happened.

**Reuse is by identity, and this file is where that is asserted.** `night_autopsy` imports the
coarse vocabulary, the cause taxonomy, the fine shape, the solved predicate, the reconciliation
definition and the evidence paths from the modules that define them. A re-export that was secretly
a re-implementation would satisfy a behavioural test and drift the first time the original moved;
an `is` assertion cannot.

Both honesty properties are exercised on inputs that are *meant* to trip them (`CONTRIBUTING.md`:
a guard nobody has seen fail may be passing vacuously) — the AST walk against a planted `mlx_lm`
import and a `json` anti-vacuity control, the determinism claim against a real subprocess at two
hash seeds, and the reward-path guard against a command that reports a staged change.

No model, no network. The AST walk reads source, the determinism test runs the door offline, and
the reward-path guard runs `git`.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from bakeoff.test_night_autopsy import night
from whetstone.bakeoff import attribution, autopsy, night_autopsy, scoring
from whetstone.loop import dataset
from whetstone.loop import draws as run_draws
from whetstone.loop import ledger as run_ledger
from whetstone.loop import night as loop_night

#: The repository root, reached from `tests/bakeoff/`. The `git` guard measures this tree, and the
#: determinism test's outputs live under its gitignored `runs/`.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: The module under test and this slice's two test files, the no-inference walk's scope.
AUTOPSY_PATHS = (
    "src/whetstone/bakeoff/night_autopsy.py",
    "tests/bakeoff/test_night_autopsy.py",
    "tests/bakeoff/test_night_autopsy_guards.py",
)

#: Import roots that would mean a model was consulted. Deliberately wider than `mlx`: the claim is
#: that the autopsy costs no inference at all, and `torch` or `openai` would break it exactly as
#: `mlx_lm` would. The same list the replay's and autopsy's own walks carry.
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {"mlx", "mlx_lm", "torch", "transformers", "openai", "anthropic", "huggingface_hub"}
)


def _imported_roots(source: bytes) -> set[str]:
    """The top-level package of every import in `source`, function-local ones included.

    `ast.walk` rather than a top-of-file read: an import moved inside a function would otherwise
    be invisible — which is exactly where a "just this once" model call would go.
    """
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source, filename="<source>")):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


# --------------------------------------------------------------------------------------------
# Guard one: the walk sees real imports, and it flags a planted inference import.
# --------------------------------------------------------------------------------------------


def test_the_walk_reports_an_import_it_is_given() -> None:
    """Anti-vacuity control: the walk must actually observe imports.

    The guard below asserts an absence, which a parser that saw nothing would satisfy. Fed a
    source that imports `json`, the walk must report `json` — only a walk that reads real imports
    can then be trusted when it reports none on the autopsy's path.
    """
    assert "json" in _imported_roots(b"import json\n"), (
        "the AST walk did not see the stdlib import it was handed, so the no-inference assertion "
        "below would pass by seeing nothing at all"
    )


def test_a_planted_inference_import_is_seen_and_flagged() -> None:
    """The guard's predicate, watched failing: a planted inference import must be flagged."""
    roots = _imported_roots(b"import json\n\nfrom mlx_lm import load\n")
    assert roots & FORBIDDEN_IMPORT_ROOTS == {"mlx_lm"}, roots


@pytest.mark.parametrize("relative", AUTOPSY_PATHS)
def test_the_night_autopsy_path_imports_no_inference_library(relative: str) -> None:
    """The autopsy's whole value is that it costs no compute; an import here would spend some.

    `bakeoff/` is exempt from the reward-path guard, and legitimately so — `mlx_runtime.py` must
    import `mlx_lm`. This is a narrower claim about this slice's own files: the module re-runs
    `patch.py`'s extractor over stored completions, and a module or test that reached for the
    model again would be a re-run charging a replay's price.
    """
    path = REPO_ROOT / relative
    assert path.is_file(), f"{relative} does not exist, so the walk proves nothing about it"

    roots = _imported_roots(path.read_bytes())

    assert not roots & FORBIDDEN_IMPORT_ROOTS, (
        f"{relative} imports {sorted(roots & FORBIDDEN_IMPORT_ROOTS)}.\n\n"
        "WHY THIS IS A FAILURE: the night's journals and transcripts exist so one night of "
        "compute can be re-analysed indefinitely without another. An inference import here means "
        "the analysis needs the model back, and every question asked of the data costs a "
        "generation pass again."
    )
    # Anti-vacuity per file: an empty module would satisfy the absence above.
    assert roots, (
        f"{relative} contains no import at all, so the assertion above holds for a file nothing "
        "was checked against"
    )


# --------------------------------------------------------------------------------------------
# Guard two: every reused fact is the object the run itself used, by identity.
# --------------------------------------------------------------------------------------------


def test_every_reused_fact_is_imported_by_identity() -> None:
    """A re-spelled taxonomy would drift from the run's own; `is` cannot be a copy.

    Each assertion names one fact the module must not own: the coarse vocabulary, the cause
    taxonomy and its markers, the replay's own `attribute`/`extract_patch`, the fine shape, the
    solved predicate, the reconciliation definition, the evidence paths and the ledger reader.
    """
    assert night_autopsy.Cause is attribution.Cause
    assert night_autopsy.NO_DIFF_MARKERS is attribution.NO_DIFF_MARKERS
    assert night_autopsy.attribute is attribution.attribute
    assert night_autopsy.extract_patch is attribution.extract_patch
    assert night_autopsy.classify_completion is autopsy.classify_completion
    assert night_autopsy.ledger_read is run_ledger.read
    assert night_autopsy.LEDGER_FILE is run_ledger.LEDGER_FILE
    assert night_autopsy.evidence_paths is run_draws.evidence_paths
    assert night_autopsy.EVIDENCE_DIR is loop_night.EVIDENCE_DIR
    assert night_autopsy.Outcome is scoring.Outcome
    assert night_autopsy.trainable is dataset.trainable
    assert night_autopsy.counts_of is run_ledger.counts_of
    assert night_autopsy.refuse_published_out is autopsy.refuse_published_out
    assert night_autopsy.OutNotPrivate is autopsy.OutNotPrivate


# --------------------------------------------------------------------------------------------
# Guard three: the document is byte-deterministic across invocations and hash seeds.
# --------------------------------------------------------------------------------------------


def test_the_document_is_byte_identical_under_pythonhashseed(tmp_path: Path) -> None:
    """Two door invocations at `PYTHONHASHSEED` 0 and 1 write the same bytes.

    Determinism is an acceptance criterion: a partition that changed between reads of the same run
    would be evidence nobody can re-derive. Asserted across processes, because an in-process
    repeat shares one hash seed and would miss exactly the set-iteration dependence this guards.
    """
    run = night(tmp_path)
    root = REPO_ROOT / "runs" / "night-autopsy-guards" / tmp_path.name
    first = root / "seed0.json"
    second = root / "seed1.json"
    try:
        for seed, out in (("0", first), ("1", second)):
            environment = dict(os.environ)
            environment["PYTHONHASHSEED"] = seed
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "whetstone.bakeoff.night_autopsy",
                    "--run",
                    str(run),
                    "--out",
                    str(out),
                ],
                cwd=str(REPO_ROOT),
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            assert completed.returncode == 0, completed.stderr

        assert first.read_bytes() == second.read_bytes(), (
            "two invocations at PYTHONHASHSEED 0 and 1 wrote different bytes.\n\n"
            "WHY THIS IS A FAILURE: a partition that changes between reads of the same run is "
            "evidence nobody can re-derive, and the difference is a hash-seed-dependent iteration "
            "order nothing in a single process would ever surface."
        )
        assert json.loads(first.read_bytes())["schema"] == "whetstone-night-autopsy/1"
    finally:
        shutil.rmtree(root, ignore_errors=True)


# --------------------------------------------------------------------------------------------
# Guard four: the reward path and the corpus did not move on this branch.
# --------------------------------------------------------------------------------------------


def _git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Real git, with the developer's own configuration switched off.

    The same environment scrubbing `test_attribution.py` and `test_autopsy_guards.py` use: a
    machine-local `hooksPath` or a `diff` alias would change what the guard measures.
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
            "HOME": str(cwd),
        },
        check=False,
    )


def test_the_reward_path_and_corpus_did_not_move() -> None:
    """The slice's central promise: `verify/` and `tasks/` are byte-identical to `origin/master`.

    The partition describes rollouts graded against this reward and drawn from this corpus. A
    modified `verify/` file means the measurement and the thing it measures drift apart, and the
    counts describe a verifier that no longer exists; a modified `tasks/` file means the corpus the
    partition is keyed by changed under it. Either would be invisible in the output.
    """
    result = _git(
        ["diff", "--stat", "origin/master", "--", "src/whetstone/verify", "tasks"], cwd=REPO_ROOT
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "", (
        f"the reward path or the corpus moved on this branch:\n{result.stdout}\n"
        "WHY THIS IS A FAILURE: a branch that publishes a partition must not also change the "
        "reward the rollouts were graded against or the corpus they were drawn from — the "
        "measurement and the measured drift apart and nothing in the output looks wrong while it "
        "happens."
    )
