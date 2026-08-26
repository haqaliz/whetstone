"""The § 3 baseline measurement's door: score the untrained base, exactly once.

Aspect 2 of `baseline-measurement` (`docs/planning/baseline-measurement/`). The one new
machine seam is `baseline_engine` — gate's `gate_engine` with exactly one difference, no
`adapter_path` — and everything else this door composes is the gate's own, imported
**by identity**, never copied: `_CheckpointGenerator`, `_CompletionRecorder`, `_score_side`,
`_retry_side`, `RETRY_COUNT`, `report.tally`, exactly as `gate.py` composes the bake-off's.
A baseline draw and a gate eval are one experiment, because the greedy sampler is
`sampler_for(1)` **by identity** in both.

`measure()` is `run_gate` for one side: private roots refused first (`--runs` under a
published directory, `--out` under a gitignored root — both by identity, before anything
loads), `HF_HUB_OFFLINE` pinned, the held-out document through its fail-closed loader with
its digest recomputed, the task roots loaded, the checkpoint re-hashed, the base resolved
from its own provenance (`NoBaseWeights` for a base the weights root does not hold), the
side scored over held-out plus source A, and the retry discipline applied over the
held-out membership alone — `RETRY_COUNT` by identity, source A scored in full, unretried
and stated. The counts are `report.tally`'s over the post-retry rollouts — the single
place each published figure is defined, and the only place the baseline `N`
(`weaker_wins`) exists — and the evidence document under the gitignored `runs/<run-id>/`
home carries hashes and verdicts only, never prompts, completions or patch text.

Every `mlx` import is function-local, on the loop package's own rule: this module imports,
type-checks and tests on a machine with no extra, and merely importing it loads no inference
library.

The measured-once guard (`spec.md` requirement 5) is the write side of this door's reason to
exist. `read_series_identity` reads the committed artifact's series identity — its schema
(`BASELINE_SCHEMA`), the checkpoint digest and the held-out document digest, nothing else —
fail-closed: an artifact that cannot be read is refused by name, never treated as absent.
`measure()` refuses a second measurement of the same series (`BaselineAlreadyMeasured`),
keyed on the two digests, never on the clock; a **different** series — a changed pinned
input, e.g. a new base revision or a new held-out split — is § 3's legitimate new series
(`PREREGISTRATION.md:133-135`), allowed, with the change recorded in the new evidence.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from whetstone.bakeoff import report as bakeoff_report
from whetstone.bakeoff.generator import Generator
from whetstone.bakeoff.mlx_runtime import DEFAULT_MAX_TOKENS
from whetstone.bakeoff.report import Tally
from whetstone.bakeoff.run import HF_HUB_OFFLINE, load_task_roots
from whetstone.bakeoff.scoring import Interpreters, Rollout
from whetstone.bakeoff.weights import Weights, load_weights
from whetstone.loop import gate as gate_module
from whetstone.loop import heldout as heldout_module
from whetstone.loop import night as night_module
from whetstone.loop.ledger import tool_versions
from whetstone.loop.sampling import sampler_for
from whetstone.loop.sft import Checkpoint, verify_checkpoint
from whetstone.tasks.manifest import load_tasks

# --------------------------------------------------------------------------------------------
# The gate's own pieces, imported by identity — never copied. A second copy of any of these
# is a second answer to "how is a side scored", "what is the retry budget" or "what counts as
# solved", and the day it drifted no document would say so.
# --------------------------------------------------------------------------------------------

#: The one definition of a side's scoring, retry and no-verdict handling — the gate's own.
_CheckpointGenerator = gate_module._CheckpointGenerator
_CompletionRecorder = gate_module._CompletionRecorder
_heldout_tasks = gate_module._heldout_tasks
_base_for = gate_module._base_for
_score_side = gate_module._score_side
_retry_side = gate_module._retry_side

#: The declared retry budget `R`, by identity — revisable only by a dated amendment to
#: `PREREGISTRATION.md` § 7.2, never by a number written beside it.
RETRY_COUNT = gate_module.RETRY_COUNT

#: The refusal for a checkpoint naming a base the weights root does not hold, by identity.
NoBaseWeights = gate_module.NoBaseWeights

#: The held-out document's loader and digest, the private-root refusal, and the `--out`
#: refusal — each by identity.
read_document = heldout_module.read_document
document_digest_of = heldout_module.document_digest_of
refuse_committed_out = heldout_module.refuse_committed_out
_refuse_published_root = night_module._refuse_published_root

#: The single place each published count is defined — the bake-off's own tally, by identity.
tally = bakeoff_report.tally

#: The evidence document's own schema string, named so a later reader has one answer to
#: "what shape is this file".
EVIDENCE_SCHEMA = "whetstone-baseline-run/1"

#: The committed artifact's schema — aspect 3's `report.json`. One answer to "what shape is
#: the file that fixes a series", so the measured-once guard and the artifact's writer agree
#: on it by name rather than by coincidence.
BASELINE_SCHEMA = "whetstone-baseline/1"


@dataclass(frozen=True)
class SeriesIdentity:
    """The series a baseline measurement belongs to: exactly the two digests.

    `PREREGISTRATION.md` § 3's baseline is measured once, re-measured never, and the series
    is what "once" keys on — the checkpoint's re-hashed digest and the held-out document's
    digest, nothing else. The environment pins and tool versions are part of § 3's pinned
    inputs and are recorded in the artifact's provenance; they are provenance, never the
    refusal's key. `recorded_on` is an input to the refusal's message, never part of the
    identity — the clock is not the series.
    """

    #: The re-hashed checkpoint's digest.
    checkpoint_digest: str

    #: The held-out document's digest, recomputed from the payload the loader accepted.
    heldout_digest: str


class BaselineAlreadyMeasured(ValueError):
    """A second measurement of the same baseline series, refused by name.

    The § 3 baseline is measured once, re-measured never (`PREREGISTRATION.md:129-135`): the
    same checkpoint and the same held-out split produce the same measurement by
    construction, so a second one would be the first measurement wearing a second date. A
    **changed** pinned input is the only legitimate second measurement, and it is a new
    series, never an extension of the old one. The key is the series — the two digests —
    never the clock: this refusal fires on what was measured and over what, not on how much
    time passed.
    """


def read_series_identity(path: Path) -> SeriesIdentity:
    """Read the committed artifact's series identity, or refuse it by name.

    The fail-closed half of the measured-once guard (`spec.md` requirement 5): an artifact
    that half-parses could be the same series, and a measurement that read it as absent
    would be a second measurement wearing the name of a first. The refusals are named — an
    unreadable file, a non-object document, a wrong or missing `schema`, a missing or
    non-string `checkpoint.digest` or `heldout.document_digest` — and the returned identity
    is exactly the two digests: `recorded_on` is the refusal message's input, never the
    identity's.
    """
    location = Path(path)
    try:
        raw = json.loads(location.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"baseline artifact {str(location)!r} could not be read: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise ValueError(
            f"baseline artifact {str(location)!r} must be a JSON object, "
            f"got {type(raw).__name__}"
        )
    if raw.get("schema") != BASELINE_SCHEMA:
        raise ValueError(
            f"baseline artifact {str(location)!r} declares schema {raw.get('schema')!r}, "
            f"but this module reads {BASELINE_SCHEMA!r}; an old-schema artifact fails decode "
            "rather than defaulting"
        )
    checkpoint = raw.get("checkpoint")
    if not isinstance(checkpoint, dict) or not isinstance(checkpoint.get("digest"), str):
        raise ValueError(
            f"baseline artifact {str(location)!r} has a missing or non-string "
            "checkpoint.digest"
        )
    heldout_raw = raw.get("heldout")
    if not isinstance(heldout_raw, dict) or not isinstance(
        heldout_raw.get("document_digest"), str
    ):
        raise ValueError(
            f"baseline artifact {str(location)!r} has a missing or non-string "
            "heldout.document_digest"
        )
    return SeriesIdentity(
        checkpoint_digest=checkpoint["digest"],
        heldout_digest=heldout_raw["document_digest"],
    )


def _artifact_recorded_on(path: Path) -> str:
    """The first artifact's declared date, for the same-series refusal's message.

    An input to the message, never part of the identity: absent or non-string reads as
    "unknown date". Only ever consulted for an artifact `read_series_identity` has already
    validated, so the try/except is a guard against a file that vanished between the two
    reads, not a second validation.
    """
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unknown date"
    recorded = raw.get("recorded_on") if isinstance(raw, dict) else None
    return recorded if isinstance(recorded, str) else "unknown date"


def baseline_engine(
    weights: Weights, checkpoint: Checkpoint, max_tokens: int = DEFAULT_MAX_TOKENS
) -> Generator:
    """Load the untrained base `checkpoint` names and return a greedy `Generator`.

    The § 3 baseline's one machine seam — `gate_engine`'s sibling, differing in exactly
    one line. The checkpoint's provenance declares `untrained: true` (the aspect-1 writer),
    so there is no adapter to stack: the base is loaded from `weights.local_dir` (never a
    repo id) at the revision the checkpoint's own provenance names, and decoding is greedy —
    `sampler_for(1)` is `greedy_sampler` **by identity**, so a baseline draw and a gate
    eval are one experiment. The night's trained checkpoints never reach this seam: their
    provenance does not declare `untrained`, and the gate's own engine loads them with
    their adapter.

    Every `mlx` import is function-local, on the loop package's own rule. The factory is
    never *invoked* by the test suite — `mlx` is an optional extra, and every test injects a
    stub engine — so its behaviour is pinned by the smoke test and by the operator's runbook.
    """
    from mlx_lm.generate import generate
    from mlx_lm.utils import load as load_model

    # Indexed rather than unpacked, for the reason `gate_engine` records at its own call
    # site: `load` is typed as returning EITHER `(model, tokenizer)` OR `(model, tokenizer,
    # config)`, selected by a `return_config` argument that defaults to `False`. mypy cannot
    # narrow that union from a default, so `model, tokenizer = load(...)` is an error even
    # though the two-tuple is what arrives here; indexing is total over both arms.
    loaded = load_model(
        str(weights.local_dir),
        revision=weights.revision,
    )
    model, tokenizer = loaded[0], loaded[1]
    return _CheckpointGenerator(
        model,
        tokenizer,
        generate=generate,
        max_tokens=max_tokens,
        sampler=sampler_for(1),
    )


@dataclass(frozen=True)
class BaselineMeasurement:
    """What one baseline measurement scored, and the evidence it wrote.

    The counts are `report.tally`'s over the post-retry rollouts — `heldout_tally` carries
    the baseline `N` (`weaker_wins`) over the held-out membership, `public_tally` carries
    source A's over its own denominator, both sources always present. The run identity is
    the evidence path's directory name (`runs/<run-id>/`), never a field of the document:
    two renders of the same documented command must produce byte-identical evidence.
    """

    #: The re-hashed checkpoint's digest.
    checkpoint_digest: str

    #: The held-out document's digest, recomputed from the payload the loader accepted.
    heldout_digest: str

    #: Counts over the held-out rollouts, post-retry — `weaker_wins` is the baseline `N`.
    heldout_tally: Tally

    #: Counts over source A's rollouts, scored in full and unretried.
    public_tally: Tally

    #: Every scored rollout, post-retry: held-out first, then source A, in score order.
    rollouts: tuple[Rollout, ...]

    #: What the retry discipline did, per held-out task it fired on. Empty when nothing
    #: wobbled — which is the common case, and is itself worth being able to read.
    retries: tuple[gate_module.RetryOutcome, ...]

    #: The written evidence document.
    evidence_path: Path

    #: The operator-declared date — an input, never the clock.
    recorded_on: str

    #: The operator-declared run id — the evidence directory's name.
    run_id: str


def measure(
    *,
    checkpoint: Path,
    heldout: Path,
    tasks: Sequence[Path],
    public: Path,
    runs: Path,
    workspace: Path,
    timeout: float,
    recorded_on: str,
    run_id: str,
    pool: Path | None,
    weights: Path,
    out: Path,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    engine: Callable[..., Generator] = baseline_engine,
) -> BaselineMeasurement:
    """Score the single baseline checkpoint on the held-out split, exactly once.

    The order below is the design, and it is the gate's order for one side: private roots
    are refused first, before anything is loaded; the pinned input (the held-out document)
    is validated before the bytes it decides over; the checkpoint is re-hashed before
    anything compares; the base weights are verified and resolved from the checkpoint's own
    provenance; and only then is a token generated.

    `engine` is the machine seam — `baseline_engine` for a real run, a stub in every test.
    It receives the **verified** checkpoint, so scoring always runs under the re-hashed
    bytes. `recorded_on` is an input, never the clock, and `run_id` names the evidence
    directory — both for the arms' rule: evidence that dated or named itself would differ
    between two renders of the same documented command.

    The evidence document is written only at the end of a successful measurement: a killed
    run leaves the gitignored runs home and no artifact, and a re-run uses a fresh
    `--run-id`. `out` is not written here — the committed artifact is aspect 3's — but the
    gitignored-root refusal is this door's. The measured-once guard reads an artifact
    already at `--out` fail-closed — an unreadable artifact is refused by name, never
    treated as absent — and refuses a second measurement of this run's series
    (`BaselineAlreadyMeasured`) before any token is generated; a **different** series is §
    3's legitimate new series, allowed, its change recorded in the new evidence.
    """
    _refuse_published_root(runs, "--runs")
    refuse_committed_out(out)
    artifact_path = Path(out) / "report.json"
    existing: SeriesIdentity | None = (
        read_series_identity(artifact_path) if artifact_path.exists() else None
    )
    os.environ[HF_HUB_OFFLINE] = "1"

    heldout_document = read_document(heldout)
    heldout_digest = document_digest_of(json.loads(Path(heldout).read_text(encoding="utf-8")))

    private_tasks = load_task_roots(tasks)
    public_tasks = load_tasks(public)
    heldout_tasks = _heldout_tasks(heldout_document.membership, private_tasks)

    checkpoint_obj = verify_checkpoint(checkpoint)
    fetched = load_weights(weights)
    base = _base_for(checkpoint_obj, fetched, "baseline")

    if existing is not None and existing == SeriesIdentity(
        checkpoint_digest=checkpoint_obj.digest, heldout_digest=heldout_digest
    ):
        raise BaselineAlreadyMeasured(
            f"baseline series (checkpoint {existing.checkpoint_digest}, held-out document "
            f"{existing.heldout_digest}) at {str(artifact_path)!r} was already measured on "
            f"{_artifact_recorded_on(artifact_path)}; the § 3 baseline is measured once, "
            "re-measured never, and a changed pinned input is a new series, never a second "
            "measurement"
        )

    recorder = _CompletionRecorder(engine(base, checkpoint_obj, max_tokens))
    interpreters = Interpreters(workspace=workspace / "environments")
    sandbox_root = workspace / "sandbox"
    label = f"baseline:{checkpoint_obj.digest[:12]}"

    scored = _score_side(
        label=label,
        tasks=(*heldout_tasks, *public_tasks),
        generator=recorder,
        sandbox_root=sandbox_root,
        timeout=timeout,
        interpreters=interpreters,
        pool=pool,
    )
    post_retry, retries = _retry_side(
        side="baseline",
        label=label,
        rollouts=scored,
        tasks=heldout_tasks,
        recorder=recorder,
        sandbox_root=sandbox_root,
        timeout=timeout,
        interpreters=interpreters,
        pool=pool,
    )

    heldout_ids = {task.task_id for task in heldout_tasks}
    heldout_post_retry = tuple(record for record in post_retry if record.task_id in heldout_ids)
    public_post_retry = tuple(record for record in post_retry if record.task_id not in heldout_ids)
    heldout_tally = tally("baseline", heldout_post_retry)
    public_tally = tally("baseline", public_post_retry)

    evidence = write_evidence(
        path=runs / run_id / "evidence.json",
        recorded_on=recorded_on,
        checkpoint_digest=checkpoint_obj.digest,
        heldout_digest=heldout_digest,
        rollouts=post_retry,
        retries=retries,
        recorder=recorder,
        heldout_tally=heldout_tally,
        public_tally=public_tally,
    )
    return BaselineMeasurement(
        checkpoint_digest=checkpoint_obj.digest,
        heldout_digest=heldout_digest,
        heldout_tally=heldout_tally,
        public_tally=public_tally,
        rollouts=post_retry,
        retries=retries,
        evidence_path=evidence,
        recorded_on=recorded_on,
        run_id=run_id,
    )


def write_evidence(
    *,
    path: Path,
    recorded_on: str,
    checkpoint_digest: str,
    heldout_digest: str,
    rollouts: Sequence[Rollout],
    retries: Sequence[gate_module.RetryOutcome],
    recorder: _CompletionRecorder,
    heldout_tally: Tally,
    public_tally: Tally,
) -> Path:
    """Write the evidence document — schema `whetstone-baseline-run/1` — deterministically.

    Local evidence, never published: hashes and verdicts only. Each rollout carries the
    task id, the outcome, both verifiers' statuses, the prompt's hash, the first attempt's
    completion hash (the recorder's own, by identity) and the three wall-clock fields — a
    prompt, a completion or a patch text is never stored, so a source-B task's contents
    cannot leak through it. The retry is recorded as all three of what governed it
    (`retry_count`, the declared `R` by identity), what it spent (per-task
    `before`/`after`/`retries_used`), and the counts each source's post-retry rollouts
    reduce to — `weaker_wins` over the held-out set is the baseline `N`.

    The run identity is the path (`runs/<run-id>/`), never a field: the document must be
    byte-identical across two renders of the same documented command, and the durations are
    the one machine property inside it.
    """
    document = {
        "schema": EVIDENCE_SCHEMA,
        "recorded_on": recorded_on,
        "checkpoint": {"digest": checkpoint_digest},
        "heldout": {"document_digest": heldout_digest},
        "rollouts": [
            {
                "task_id": record.task_id,
                "outcome": record.outcome.value,
                "strict": record.strict.value if record.strict is not None else None,
                "weak": record.weak.value if record.weak is not None else None,
                "prompt_sha256": record.prompt_sha256,
                "completion_sha256": recorder.completion_sha256(record.prompt_sha256),
                "generation_seconds": record.generation_seconds,
                "strict_seconds": record.strict_seconds,
                "weak_seconds": record.weak_seconds,
            }
            for record in rollouts
        ],
        "retries": [
            {
                "task_id": one.task_id,
                "before": one.before.value,
                "after": one.after.value,
                "retries_used": one.retries_used,
                "prompt_sha256": one.prompt_sha256,
                "completion_sha256": one.completion_sha256,
            }
            for one in sorted(retries, key=lambda one: one.task_id)
        ],
        "retry_count": RETRY_COUNT,
        "counts": {
            "heldout": _counts_payload(heldout_tally),
            "public": _counts_payload(public_tally),
        },
        "tool_versions": dict(sorted(tool_versions().items())),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _counts_payload(tally_obj: Tally) -> dict[str, int]:
    """One source's counts as plain JSON types — the six fields every published figure reads."""
    return {
        "denominator": tally_obj.denominator,
        "solved": tally_obj.solved,
        "unverified": tally_obj.unverified,
        "covered": tally_obj.covered,
        "failed": tally_obj.failed,
        "weaker_wins": tally_obj.weaker_wins,
    }


__all__ = [
    "BASELINE_SCHEMA",
    "BaselineAlreadyMeasured",
    "BaselineMeasurement",
    "SeriesIdentity",
    "baseline_engine",
    "measure",
    "read_series_identity",
    "write_evidence",
]

