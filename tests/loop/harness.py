"""The night's fixtures: two synthetic donors, fake weights, an empty pool, and a stub base.

Deliberately the same shapes `tests/bakeoff/test_run.py` builds, because a night composes the
bake-off's own machinery and a second kind of fixture would be a second thing to keep true. What
is *not* shared is the engine: a night draws several attempts per task, so the stub here answers
from a table **with a fallback**, where the bake-off's `StubGenerator` refuses an unstubbed
prompt. The fallback is a refusal string that extracts to no diff, so an unanticipated prompt
produces a recorded zero rather than an exception that would be indistinguishable from a defect
in the code under test.

No model, no `mlx`, no network, no weights. Nothing here writes outside `tmp_path`.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping
from pathlib import Path

from fixtures.repos import make_patch
from fixtures.repos.mined import MINED_CALC_FIXED, build_mined_task

from whetstone.bakeoff.generator import Generator
from whetstone.bakeoff.rendering import render_prompt
from whetstone.bakeoff.sources import oracle_sources
from whetstone.bakeoff.weights import PROVENANCE_FILE, PROVENANCE_SCHEMA, Weights
from whetstone.tasks.fetch import POOL_SCHEMA
from whetstone.verify.task import Task

#: Generous enough that a two-commit donor with one module and one pytest file can never reach it.
TIMEOUT = 120.0

#: The date the operator declares. An input everywhere, never a clock.
RECORDED_ON = "2026-08-20"

#: What a base says when it has nothing to offer. Prose, no fence, no diff header: the shape
#: `extract_patch` reports as no-diff, so the rollout is a guaranteed verifier-free zero.
REFUSAL = "I could not work out what is wrong with this repository, so I have made no change."

#: One stand-in weights file per fake candidate. Tiny: `load_weights` is under test in its own
#: file, and all that is needed here is that the provenance check has something to pass.
WEIGHT_FILES = {"config.json": '{"model_type": "qwen2"}', "model.safetensors": "not a tensor"}


class Answers:
    """A base that answers from a table and refuses everything else in the model's own voice.

    Not `StubGenerator`: that raises on an unstubbed prompt, which is right for the bake-off's
    one-attempt-per-task runs and wrong here. A night poses retry prompts too, and a raise from
    the fixture in the middle of draw six would be indistinguishable, in the traceback, from a
    defect in the wrapper chain under test. The fallback is the refusal shape, so an unexpected
    prompt is recorded as a rollout that produced no diff — a finding a test can assert on.
    """

    def __init__(self, answers: Mapping[str, str]) -> None:
        self.answers = dict(answers)
        self.asked: list[str] = []

    def generate(self, prompt: str) -> str:
        self.asked.append(prompt)
        return self.answers.get(prompt, REFUSAL)


def engine_of(generator: Generator) -> object:
    """An `Engine` returning `generator`, ignoring the weights and the budget it is handed.

    Asserts the budget it was given is usable, because a real engine must: the token budget is a
    published contract field, so a factory that dropped it would let the ledger disclose a budget
    nothing was held to.
    """

    def factory(_: Weights, max_tokens: int) -> Generator:
        assert max_tokens >= 1, max_tokens
        return generator

    return factory


def posed(task: Task, *, pool: Path | None = None) -> str:
    """The exact prompt a night will pose for `task`, rendered the way the run renders it."""
    sources = oracle_sources(task, pool=pool)
    assert sources.files is not None, sources.reason
    return render_prompt(task, sources.files)


def solving_answers(*fixtures: object) -> dict[str, str]:
    """Prompt -> the fixture's own reference patch, for every fixture given.

    The patch is produced by git against the task's `base_commit`, so it is known-good by
    construction: a test asserting that a verified win reaches the dataset must not be able to
    fail because the fixture's diff was hand-written wrong.
    """
    answers: dict[str, str] = {}
    for fixture in fixtures:
        task = fixture.task  # type: ignore[attr-defined]
        answers[posed(task)] = make_patch(
            fixture.donor,  # type: ignore[attr-defined]
            {"calc.py": MINED_CALC_FIXED},
            at=fixture.parent,  # type: ignore[attr-defined]
        )
    return answers


def corpus(root: Path, name: str, ids: tuple[str, ...]) -> tuple[Path, list[object]]:
    """Build one donor per id and collect their manifests into a directory of their own.

    `load_tasks` refuses any entry that is not a manifest, so the donors are built elsewhere and
    only the JSON is copied in — which is also the shape of the real corpus, where `tasks/local/`
    holds manifests and the donors are the user's own checkouts.
    """
    directory = root / name
    directory.mkdir(parents=True)
    built: list[object] = []
    for task_id in ids:
        fixture = build_mined_task(
            root / f"donor-{task_id}", task_id=task_id, subject=f"Fix addition ({task_id})"
        )
        shutil.copy(root / f"donor-{task_id}" / f"{task_id}.json", directory / f"{task_id}.json")
        built.append(fixture)
    return directory, built


def pool(path: Path) -> Path:
    """A valid but empty source-A pool.

    Empty because the "public" corpus here is a *mined* fixture — it carries a donor commit, so
    its control arm re-derives its reference and never opens this file. The path is still passed,
    and passed as a real pool rather than a name, because a night requires it: a run reaching a
    genuine public instance without one would skip every public probe and be refused a ranking
    after the generation was paid for.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema": POOL_SCHEMA, "instances": []}), encoding="utf-8")
    return path


def weights(root: Path, *names: str) -> Path:
    """Write fake weight directories under `root` plus the provenance that names them."""
    root.mkdir(parents=True, exist_ok=True)
    recorded = []
    for name in names:
        local_dir = root / name.split("/")[-1]
        local_dir.mkdir()
        for filename, text in WEIGHT_FILES.items():
            (local_dir / filename).write_text(text, encoding="utf-8")
        recorded.append(
            {
                "repo_id": name,
                "revision": hashlib.sha256(name.encode()).hexdigest(),
                "local_dir": local_dir.name,
                "bytes": sum(len(text.encode()) for text in WEIGHT_FILES.values()),
                "seconds": 1.0,
                "files": [
                    {
                        "name": filename,
                        "bytes": len(text.encode()),
                        "sha256": hashlib.sha256(text.encode()).hexdigest(),
                    }
                    for filename, text in WEIGHT_FILES.items()
                ],
            }
        )
    (root / PROVENANCE_FILE).write_text(
        json.dumps({"schema": PROVENANCE_SCHEMA, "candidates": recorded}), encoding="utf-8"
    )
    return root


__all__ = [
    "RECORDED_ON",
    "REFUSAL",
    "TIMEOUT",
    "WEIGHT_FILES",
    "Answers",
    "corpus",
    "engine_of",
    "pool",
    "posed",
    "solving_answers",
    "weights",
]
