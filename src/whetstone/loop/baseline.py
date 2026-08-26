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

The render door (`spec.md` requirement 4) is the post-run chain's committed step:
`render_artifact` reads a measurement's evidence document (`whetstone-baseline-run/1`,
fail-closed by name — never rendered from nothing), re-hashes the checkpoint and reads the
base identity from its provenance (`_checkpoint_base`, the gate's own read, by identity),
computes the evidence digest (sha256 of the evidence's bytes — a pointer, never contents),
and writes the three artifacts through the aspect-3 writer by identity. The measured-once
discipline holds on the render side too — an artifact already rendered for this series is
refused by name, never re-rendered — and `render_declaration` writes the declaration-only
state, the committed artifacts *before* any measurement, on which the refusal is
deliberately not applied (a declaration is not a measurement).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from whetstone.bakeoff import report as bakeoff_report
from whetstone.bakeoff.generator import Generator
from whetstone.bakeoff.mlx_runtime import DEFAULT_MAX_TOKENS
from whetstone.bakeoff.report import Tally
from whetstone.bakeoff.run import HF_HUB_OFFLINE, TranscriptNotPrivate, load_task_roots
from whetstone.bakeoff.scoring import Interpreters, Outcome, Rollout
from whetstone.bakeoff.stratum import OutUnderLocalCorpus
from whetstone.bakeoff.weights import (
    ProvenanceUnreadable,
    Weights,
    WeightsUnverified,
    load_weights,
)
from whetstone.loop import gate as gate_module
from whetstone.loop import heldout as heldout_module
from whetstone.loop import night as night_module
from whetstone.loop.heldout import (
    EmptyHeldout,
    HeldoutDigestMismatch,
    HeldoutSchemaError,
    UnknownHeldoutId,
)
from whetstone.loop.ledger import tool_versions
from whetstone.loop.sampling import sampler_for
from whetstone.loop.sft import Checkpoint, CheckpointUnverified, verify_checkpoint
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

#: The base a checkpoint's provenance names — the gate's own read, by identity. The render
#: door re-hashes the checkpoint first and reads the base identity from its provenance
#: with this function, exactly as `measure()` resolves the base it scores.
_checkpoint_base = gate_module._checkpoint_base

#: The held-out document's loader and digest, the private-root refusal, and the `--out`
#: refusal — each by identity.
read_document = heldout_module.read_document
document_digest_of = heldout_module.document_digest_of
refuse_committed_out = heldout_module.refuse_committed_out
_refuse_published_root = night_module._refuse_published_root

#: The single place each published count is defined — the bake-off's own tally, by identity.
tally = bakeoff_report.tally

#: The committed artifact's schema — the writer's own constant, by identity. The loader
#: reads what the writer writes; a drift between the two constants would let the loader
#: accept a schema the writer never emits, or refuse the one it does.
_baseline_schema = bakeoff_report.BASELINE_REPORT_SCHEMA

#: The six fields each source's side carries — the writer's own shape, by identity.
_baseline_count_fields = bakeoff_report._BASELINE_COUNT_FIELDS

#: Every field the committed artifact may carry — the writer's own set, by identity.
_baseline_known_fields = bakeoff_report._BASELINE_KNOWN_FIELDS

#: The seal the loader verifies — the writer's own digest function, by identity: the
#: loader recomputes what the writer computed, with the writer's own code, so the two
#: cannot disagree about what is sealed.
_baseline_document_digest = bakeoff_report._baseline_document_digest

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
    """Read a document's series identity, or refuse it by name.

    The fail-closed half of the measured-once guard (`spec.md` requirement 5): an artifact
    that half-parses could be the same series, and a measurement that read it as absent
    would be a second measurement wearing the name of a first. The refusals are named — an
    unreadable file, a non-object document, a wrong or missing `schema`, a missing or
    non-string digest — and the returned identity is exactly the two digests: `recorded_on`
    is the refusal message's input, never the identity's.

    Two spellings of the two digests are read, because the series identity exists in two
    documents: the evidence's `checkpoint.digest`/`heldout.document_digest` (the aspect-2
    shape the measured-once guard reads at `--out`) and the committed artifact's
    `series.checkpoint_digest`/`series.heldout_digest` (aspect 3's writer). The loader of
    the committed artifact composes this function by identity on the artifact's path, so
    the artifact spelling must be readable here; the evidence spelling is unchanged.
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
    heldout_raw = raw.get("heldout")
    if isinstance(checkpoint, dict) and isinstance(heldout_raw, dict):
        if not isinstance(checkpoint.get("digest"), str):
            raise ValueError(
                f"baseline artifact {str(location)!r} has a missing or non-string "
                "checkpoint.digest"
            )
        if not isinstance(heldout_raw.get("document_digest"), str):
            raise ValueError(
                f"baseline artifact {str(location)!r} has a missing or non-string "
                "heldout.document_digest"
            )
        return SeriesIdentity(
            checkpoint_digest=checkpoint["digest"],
            heldout_digest=heldout_raw["document_digest"],
        )
    series_block = raw.get("series")
    if isinstance(series_block, dict):
        if not isinstance(series_block.get("checkpoint_digest"), str):
            raise ValueError(
                f"baseline artifact {str(location)!r} has a missing or non-string "
                "series.checkpoint_digest"
            )
        if not isinstance(series_block.get("heldout_digest"), str):
            raise ValueError(
                f"baseline artifact {str(location)!r} has a missing or non-string "
                "series.heldout_digest"
            )
        return SeriesIdentity(
            checkpoint_digest=series_block["checkpoint_digest"],
            heldout_digest=series_block["heldout_digest"],
        )
    raise ValueError(
        f"baseline artifact {str(location)!r} has no readable series identity: neither "
        "checkpoint.digest/heldout.document_digest nor series.checkpoint_digest/"
        "series.heldout_digest is present"
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


# --------------------------------------------------------------------------------------------
# The committed document's loader — `read_baseline_document`, the read side of the
# measured-once discipline. The writer lives in `bakeoff.report` (which must never import
# this module — the loop imports the report), so the loader lives here beside its own
# `read_series_identity`, composing it by identity and importing the writer's schema,
# count-shape, field set and digest function by identity (the loop→bakeoff direction).
# --------------------------------------------------------------------------------------------

#: The series read — `read_series_identity`'s own function object, by identity. The loader
#: hands it the artifact's path exactly as the measured-once guard does; a second
#: implementation of the series validation would be a second answer to "what is this
#: series" with nothing to say so.
_baseline_series_reader = read_series_identity


@dataclass(frozen=True)
class BaselineDocument:
    """A parsed, validated § 3 baseline document — what the P4 report writer will read.

    The loader's checks are the gate: the document is accepted only after every check has
    passed, and the returned object carries the fields the P4 writer needs, verbatim from
    the document. A declaration (`measured=False`) carries no series, no sides, no counts —
    those fields are `None` — and the one field that decides whether a count may be read
    at all is `measured` itself.
    """

    #: The declared schema, carried rather than assumed.
    schema: str

    #: The operator-declared date — an input, never the clock.
    recorded_on: str

    #: The series identity — the two digests the measured-once guard keys on.
    series: SeriesIdentity | None

    #: The pinned base input and the § 7.3-open sentence, verbatim.
    base: Mapping[str, str] | None

    #: Both sources' six-field counts, over their own denominators.
    sides: Mapping[str, Mapping[str, int]] | None

    #: `N` with its pre-registered sentence, verbatim.
    n: Mapping[str, Any] | None

    #: The retry facts — the declared `R`, what was spent, per-task records.
    retries: Mapping[str, Any] | None

    #: The evidence pointer — schema and digest, never contents.
    evidence: Mapping[str, str] | None

    #: The tool versions, sorted by the writer.
    tool_versions: Mapping[str, str] | None

    #: Whether the document reports a measurement — False for the declaration state.
    measured: bool


def _refuse_unsealed(raw: Mapping[str, Any], location: Path) -> None:
    """The seal check, shared by both document states: the digest must match the payload.

    The writer's own digest function, recomputed over the raw document by identity. A
    missing, non-string or mismatched digest is refused by name: the hand edit that
    changes a count without regenerating the digest is exactly the edit this seals.
    """
    recorded = raw.get("document_digest")
    if not isinstance(recorded, str) or _baseline_document_digest(raw) != recorded:
        raise ValueError(
            f"baseline artifact {str(location)!r} has a document_digest that does not seal "
            "its payload; a hand edit that changes a count without regenerating the digest "
            "is refused, never trusted"
        )


def read_baseline_document(path: Path) -> BaselineDocument:
    """Read the committed § 3 baseline document, or refuse it by name.

    The fail-closed read side of the measured-once discipline: a document an outside
    reader hand-edited is refused rather than trusted, because the committed baseline is
    the "before" of every later delta and a silently moved count is the one edit nobody
    checks. The checks are, in order: the file reads and is an object; the schema is the
    writer's own (`BASELINE_REPORT_SCHEMA`, by identity); no field is unknown; the state
    is declared (`measured`); a declaration carries its sentence and is sealed; a measured
    document's series identity is validated by `read_series_identity` **by identity**, both
    sources are present, every count is an integer and non-negative, `weaker_wins` never
    exceeds its own denominator; and the document digest — recomputed with the writer's own
    function — seals the payload. Each refusal names the file and the offending field.
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
    if raw.get("schema") != _baseline_schema:
        raise ValueError(
            f"baseline artifact {str(location)!r} declares schema {raw.get('schema')!r}, "
            f"but this module reads {_baseline_schema!r}; an old-schema artifact fails "
            "decode rather than defaulting"
        )
    unexpected = sorted(set(raw) - _baseline_known_fields)
    if unexpected:
        raise ValueError(
            f"baseline artifact {str(location)!r} carries unknown field {unexpected!r}; a "
            "field this module does not read would be trusted by nobody and read by no one"
        )
    recorded_on = raw.get("recorded_on")
    if not isinstance(recorded_on, str):
        raise ValueError(
            f"baseline artifact {str(location)!r} has a missing or non-string recorded_on"
        )
    if raw.get("measured") is False:
        declaration = raw.get("declaration")
        if not isinstance(declaration, str) or not declaration:
            raise ValueError(
                f"baseline artifact {str(location)!r} has a missing or non-string "
                "declaration"
            )
        _refuse_unsealed(raw, location)
        return BaselineDocument(
            schema=raw["schema"],
            recorded_on=recorded_on,
            series=None,
            base=None,
            sides=None,
            n=None,
            retries=None,
            evidence=None,
            tool_versions=None,
            measured=False,
        )
    if raw.get("measured") is not True:
        raise ValueError(
            f"baseline artifact {str(location)!r} has a missing or non-boolean measured"
        )

    series = _baseline_series_reader(location)

    sides = raw.get("sides")
    if not isinstance(sides, dict):
        raise ValueError(
            f"baseline artifact {str(location)!r} has a missing or non-object sides"
        )
    for source in ("source-b", "source-a"):
        counts = sides.get(source)
        if not isinstance(counts, dict):
            raise ValueError(
                f"baseline artifact {str(location)!r} has a missing or non-object "
                f"{source} side"
            )
        for field in _baseline_count_fields:
            value = counts.get(field)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(
                    f"baseline artifact {str(location)!r} has a missing or non-integer "
                    f"{source}.{field}"
                )
            if value < 0:
                raise ValueError(
                    f"baseline artifact {str(location)!r} has a negative {source}.{field} "
                    f"({value})"
                )
        if counts["weaker_wins"] > counts["denominator"]:
            raise ValueError(
                f"baseline artifact {str(location)!r} counts {source}.weaker_wins "
                f"({counts['weaker_wins']}) over its own denominator "
                f"({counts['denominator']})"
            )

    _refuse_unsealed(raw, location)
    return BaselineDocument(
        schema=raw["schema"],
        recorded_on=recorded_on,
        series=series,
        base=raw["base"],
        sides=sides,
        n=raw["n"],
        retries=raw["retries"],
        evidence=raw["evidence"],
        tool_versions=raw["tool_versions"],
        measured=True,
    )


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


# --------------------------------------------------------------------------------------------
# The render door — `render_artifact` and `render_declaration`, the post-run chain's step
# that turns a measurement's evidence into the committed § 3 artifact (`spec.md` requirement
# 4, AC 6). The measured-once discipline holds here too: an artifact already rendered for
# this series is not re-rendered; the declaration is the committed state *before* any
# measurement and re-running it rewrites the same declaration, never a second measurement
# wearing the name of a first.
# --------------------------------------------------------------------------------------------


def _read_evidence(path: Path) -> dict[str, Any]:
    """Read the evidence document (`whetstone-baseline-run/1`), fail-closed by name.

    The render never produces an artifact from nothing: a missing, unreadable or
    wrong-schema evidence document is refused by name, and so is a schema-valid document
    missing a field the render reads — the series digests, both sources' six-field counts
    (integers, non-negative, `weaker_wins` within its own denominator), the per-task retry
    records, the declared `R` and the tool versions. Each refusal is one sentence naming
    the file; an evidence that half-parses is refused, never rendered past.
    """
    location = Path(path)
    try:
        raw = json.loads(location.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"baseline evidence {str(location)!r} could not be read: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise ValueError(
            f"baseline evidence {str(location)!r} must be a JSON object, "
            f"got {type(raw).__name__}"
        )
    if raw.get("schema") != EVIDENCE_SCHEMA:
        raise ValueError(
            f"baseline evidence {str(location)!r} declares schema {raw.get('schema')!r}, "
            f"but this module reads {EVIDENCE_SCHEMA!r}; an old-schema evidence fails "
            "decode rather than defaulting"
        )
    checkpoint = raw.get("checkpoint")
    heldout_block = raw.get("heldout")
    if not isinstance(checkpoint, dict) or not isinstance(checkpoint.get("digest"), str):
        raise ValueError(
            f"baseline evidence {str(location)!r} has a missing or non-string "
            "checkpoint.digest"
        )
    if not isinstance(heldout_block, dict) or not isinstance(
        heldout_block.get("document_digest"), str
    ):
        raise ValueError(
            f"baseline evidence {str(location)!r} has a missing or non-string "
            "heldout.document_digest"
        )
    counts = raw.get("counts")
    if not isinstance(counts, dict) or not all(
        isinstance(counts.get(source), dict) for source in ("heldout", "public")
    ):
        raise ValueError(
            f"baseline evidence {str(location)!r} has a missing or non-object "
            "counts.heldout/counts.public"
        )
    for source in ("heldout", "public"):
        side = counts[source]
        for field in _baseline_count_fields:
            value = side.get(field)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(
                    f"baseline evidence {str(location)!r} has a missing or non-integer "
                    f"counts.{source}.{field}"
                )
            if value < 0:
                raise ValueError(
                    f"baseline evidence {str(location)!r} has a negative "
                    f"counts.{source}.{field} ({value})"
                )
        if side["weaker_wins"] > side["denominator"]:
            raise ValueError(
                f"baseline evidence {str(location)!r} counts counts.{source}.weaker_wins "
                f"({side['weaker_wins']}) over its own denominator ({side['denominator']})"
            )
    retries = raw.get("retries")
    if not isinstance(retries, list) or not all(
        isinstance(one, dict) for one in retries
    ):
        raise ValueError(
            f"baseline evidence {str(location)!r} has a missing or non-list retries"
        )
    outcome_values = {member.value for member in Outcome}
    for one in retries:
        if not isinstance(one.get("task_id"), str):
            raise ValueError(
                f"baseline evidence {str(location)!r} has a retry record with a missing "
                "or non-string task_id"
            )
        if one.get("before") not in outcome_values or one.get("after") not in outcome_values:
            raise ValueError(
                f"baseline evidence {str(location)!r} has a retry record with an outcome "
                "that is not one of the declared outcomes"
            )
        if isinstance(one.get("retries_used"), bool) or not isinstance(
            one.get("retries_used"), int
        ):
            raise ValueError(
                f"baseline evidence {str(location)!r} has a retry record with a missing "
                "or non-integer retries_used"
            )
    retry_count = raw.get("retry_count")
    if isinstance(retry_count, bool) or not isinstance(retry_count, int):
        raise ValueError(
            f"baseline evidence {str(location)!r} has a missing or non-integer retry_count"
        )
    tool_versions = raw.get("tool_versions")
    if not isinstance(tool_versions, dict) or not all(
        isinstance(value, str) for value in tool_versions.values()
    ):
        raise ValueError(
            f"baseline evidence {str(location)!r} has a missing or non-string-valued "
            "tool_versions"
        )
    return raw


def _tally_from_counts(counts: Mapping[str, int]) -> Tally:
    """The writer-input `Tally` reconstructed from one source's six-field counts.

    The evidence schema carries six of the `Tally`'s eleven fields — the six the baseline
    document publishes (`_BASELINE_COUNT_FIELDS`, by identity) — so those are carried
    verbatim; the remaining four (`no_diff`, `not_applied`, `out_of_scope`,
    `not_solved`) are not part of the evidence schema and are never read from this
    document, and the transport carries them at zero, stated here rather than hidden.
    """
    return Tally(
        candidate="baseline",
        denominator=counts["denominator"],
        solved=counts["solved"],
        covered=counts["covered"],
        unverified=counts["unverified"],
        failed=counts["failed"],
        weaker_wins=counts["weaker_wins"],
        no_diff=0,
        not_applied=0,
        out_of_scope=0,
        not_solved=0,
    )


def _retry_outcomes(records: Sequence[Mapping[str, Any]]) -> tuple[gate_module.RetryOutcome, ...]:
    """The writer-input retry records, reconstructed as the gate's own type, by identity.

    The evidence's per-task retry facts (task id, before/after outcome, retries spent and
    the two hashes) are carried verbatim into `RetryOutcome` — the gate's own dataclass —
    so the artifact's retry block is a restatement of the evidence, never a re-derivation.
    """
    return tuple(
        gate_module.RetryOutcome(
            side="baseline",
            task_id=one["task_id"],
            before=Outcome(one["before"]),
            after=Outcome(one["after"]),
            retries_used=one["retries_used"],
            prompt_sha256=one.get("prompt_sha256", ""),
            completion_sha256=one.get("completion_sha256", ""),
        )
        for one in records
    )


def _evidence_digest(path: Path) -> str:
    """The sha256 of the evidence document's bytes — the artifact's pointer, never contents."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


#: The zero-shaped six-field counts the declaration door carries: the writer reads none of
#: its fields when `measured=False` — the declaration document carries no count in any
#: spelling — and the shape exists only to satisfy the writer's signature with its own type.
_EMPTY_COUNTS: dict[str, int] = {
    "denominator": 0,
    "solved": 0,
    "unverified": 0,
    "covered": 0,
    "failed": 0,
    "weaker_wins": 0,
}


def render_artifact(
    *, evidence: Path, out: Path, recorded_on: str, checkpoint: Path
) -> tuple[Path, Path, Path]:
    """Render the committed § 3 baseline artifact from a measurement's evidence document.

    The post-run chain's render step (`spec.md` requirement 4): the evidence
    (`whetstone-baseline-run/1`, read fail-closed by name — never rendered from nothing)
    fixes the series identity (its two digests) and the counts (its six-field sides), the
    checkpoint is re-hashed and its provenance read for the base identity, the evidence
    digest is the sha256 of the evidence's bytes, and the three artifacts are written via
    the aspect-3 writer by identity — `build_baseline_report`/`write_baseline_report`
    imported, never copied.

    The measured-once discipline holds on the render side: an artifact already at
    `out/report.json` for the same series is refused by name (`BaselineAlreadyMeasured`),
    naming the first artifact, because a rendered baseline is not re-rendered; a
    **different** series — a changed pinned input — is § 3's legitimate new series,
    allowed. `out` under a gitignored root is refused by identity
    (`refuse_committed_out`), before anything is loaded. `recorded_on` is an input, never
    the clock.
    """
    refuse_committed_out(out)
    document = _read_evidence(evidence)
    checkpoint_obj = verify_checkpoint(checkpoint)
    base = _checkpoint_base(checkpoint_obj)
    series = SeriesIdentity(
        checkpoint_digest=document["checkpoint"]["digest"],
        heldout_digest=document["heldout"]["document_digest"],
    )
    artifact_path = Path(out) / "report.json"
    existing: SeriesIdentity | None = (
        read_series_identity(artifact_path) if artifact_path.exists() else None
    )
    if existing is not None and existing == series:
        raise BaselineAlreadyMeasured(
            f"baseline series (checkpoint {existing.checkpoint_digest}, held-out document "
            f"{existing.heldout_digest}) at {str(artifact_path)!r} was already rendered on "
            f"{_artifact_recorded_on(artifact_path)}; the § 3 baseline is measured once, "
            "re-measured never, and a changed pinned input is a new series, never a second "
            "render"
        )
    return bakeoff_report.write_baseline_report(
        bakeoff_report.build_baseline_report(
            series=series,
            heldout_tally=_tally_from_counts(document["counts"]["heldout"]),
            public_tally=_tally_from_counts(document["counts"]["public"]),
            retries=_retry_outcomes(document["retries"]),
            retry_count=document["retry_count"],
            evidence_digest=_evidence_digest(evidence),
            base=base,
            recorded_on=recorded_on,
            tool_versions=document["tool_versions"],
        ),
        out,
    )


def render_declaration(*, out: Path, recorded_on: str) -> tuple[Path, Path, Path]:
    """Write the declaration-only state — the committed artifacts before any measurement.

    The state *before* the operator spends the § 3 measurement (`spec.md` requirement 4):
    `measured=False` through the writer, holding the "No count is measured here" sentence
    and no figure in any spelling. This is the pre-run state, committed once, so the
    measured-once refusal is deliberately NOT applied — the declaration is not a
    measurement, and re-running it rewrites the same declaration, never a second
    measurement wearing the name of a first. `out` under a gitignored root is refused by
    identity: the declaration is a committed artifact, and one git cannot see is one git
    cannot prove predated the measurement.
    """
    refuse_committed_out(out)
    document = bakeoff_report.build_baseline_report(
        series=None,
        heldout_tally=_tally_from_counts(_EMPTY_COUNTS),
        public_tally=_tally_from_counts(_EMPTY_COUNTS),
        retries=(),
        retry_count=0,
        evidence_digest="",
        base={},
        recorded_on=recorded_on,
        tool_versions={},
        measured=False,
    )
    return bakeoff_report.write_baseline_report(document, out)


# --------------------------------------------------------------------------------------------
# The module door — `python -m whetstone.loop.baseline` (spec.md requirement 6). A completed
# measurement exits 0 whatever the score: the baseline is the anchor, not a verdict, and
# coverage is disclosed, never a failure. Refusals exit 2 with the reason named, never a
# traceback. The parser is a single module-level `build_parser()` so the aspect-4 runbook
# guard can pin the runbook's flags against it by identity.
# --------------------------------------------------------------------------------------------

#: Every refusal this module raises that is an **operator's error** rather than a finding:
#: a runs root pointed at a published directory, an `--out` under a gitignored root, an
#: artifact already at `--out` for this series, a checkpoint that cannot be re-hashed, a
#: held-out document that cannot be read or whose membership resolves nowhere, a checkpoint
#: naming a base the weights root does not hold, weights whose provenance does not match
#: the disk, or an evidence document the render cannot read. Collected here so the door
#: maps them to the usage code without a chain of per-module excepts; `ValueError` closes
#: the tuple — the named refusals first, and a door that crashes on an unforeseen
#: `ValueError` with a traceback is worse than a named exit-2.
REFUSALS: tuple[type[Exception], ...] = (
    TranscriptNotPrivate,
    OutUnderLocalCorpus,
    CheckpointUnverified,
    HeldoutSchemaError,
    HeldoutDigestMismatch,
    EmptyHeldout,
    UnknownHeldoutId,
    NoBaseWeights,
    ProvenanceUnreadable,
    WeightsUnverified,
    BaselineAlreadyMeasured,
    ValueError,
)


def disclosure(measurement: BaselineMeasurement) -> tuple[str, ...]:
    """The lines the door prints after a completed measurement, in the gate's voice.

    Every count carries its denominator (`PREREGISTRATION.md:157`), source A is reported
    beside source B, never alone (`PREREGISTRATION.md:142-147`), and `N` is the report's
    own pre-registered sentence (`report._N_SENTENCE`, by identity) with the count over
    its denominator (`report._over`). The retry line is unconditional — the declared `R`
    by identity, and what was actually spent — because a line that appeared only on
    trouble would make a clean machine and an unmeasured one read identically. The
    measured-once line states what the guard does: a second measurement of this series is
    refused by name, because the § 3 baseline is measured once, re-measured never.
    """
    heldout_tally = measurement.heldout_tally
    public_tally = measurement.public_tally
    spent = sum(one.retries_used for one in measurement.retries)
    return (
        f"baseline checkpoint: {measurement.checkpoint_digest[:12]}",
        f"held-out document: {measurement.heldout_digest[:12]}",
        f"source B (held-out): {heldout_tally.solved} solved of {heldout_tally.denominator}, "
        f"{heldout_tally.unverified} unverified of {heldout_tally.denominator}, "
        f"coverage {heldout_tally.covered} of {heldout_tally.denominator}",
        bakeoff_report._N_SENTENCE.format(
            count=heldout_tally.weaker_wins
        )
        + f" ({bakeoff_report._over(heldout_tally.weaker_wins, heldout_tally.denominator)})",
        f"source A (public): {public_tally.solved} solved of {public_tally.denominator}, "
        f"{public_tally.unverified} unverified of {public_tally.denominator}",
        f"retries: R={RETRY_COUNT}, {spent} spent over {len(measurement.retries)} held-out "
        f"task(s); {heldout_tally.unverified} of {heldout_tally.denominator} held-out tasks "
        "still without a verdict",
        f"evidence: {measurement.evidence_path}",
        "the § 3 baseline is measured once, re-measured never: a second measurement of this "
        "series (this checkpoint and this held-out document) is refused by name",
    )


def build_parser() -> argparse.ArgumentParser:
    """The door's argument surface — the one the aspect-4 runbook guard pins by identity.

    The spec's full flag set (`spec.md` requirement 6): every writable path is a `Path`,
    `--tasks` is repeatable, `--timeout` is a float, `--recorded-on` is a required input
    in every mode — never a default from the clock, never a name the operator did not
    declare — and `--max-tokens` defaults to the bake-off's own `DEFAULT_MAX_TOKENS` **by
    identity**, never a second number written beside it. The two render modes share the
    parser with measuring: `--render EVIDENCE` and `--render-declaration OUT` are mutually
    exclusive with each other, and the door refuses them beside a measuring flag. The
    measuring flags are enforced as a group by `main` (`parser.error`, the usage code)
    rather than by `required=True`, because a render-mode command line must be able to
    name exactly the flags that mode reads. All writable paths are expected absolute; that
    is the runbook guard's property (aspect 4), not this parser's.
    """
    parser = argparse.ArgumentParser(
        prog="python -m whetstone.loop.baseline",
        description=(
            "Score the § 3 baseline checkpoint on the held-out split, exactly once: the "
            "untrained base's patches through both verifiers with the gate's retry "
            "discipline, over the declared held-out membership and source A, with the "
            "evidence written to the gitignored runs home and a same-series artifact at "
            "--out refused by name; or render the committed artifact from a measurement's "
            "evidence (--render EVIDENCE); or write the declaration-only state "
            "(--render-declaration OUT). No model is loaded by this process boundary "
            "alone: the engine seam is reached only inside the measurement."
        ),
    )
    parser.add_argument(
        "--weights", type=Path, help="the weights root holding the base"
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        help="the untrained baseline checkpoint to score, or re-hash for a render",
    )
    parser.add_argument(
        "--heldout", type=Path, help="the committed held-out document"
    )
    parser.add_argument(
        "--tasks",
        action="append",
        type=Path,
        help="a private task root (repeatable; the roots are unioned)",
    )
    parser.add_argument(
        "--public", type=Path, help="source A's task root"
    )
    parser.add_argument(
        "--runs", type=Path, help="the gitignored evidence home"
    )
    parser.add_argument(
        "--workspace", type=Path, help="the sandboxed work root"
    )
    parser.add_argument(
        "--out", type=Path, help="where a first artifact would sit, or is rendered"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        help="per-task verification timeout in seconds",
    )
    parser.add_argument(
        "--recorded-on",
        required=True,
        help="the date the operator declares — an input, never the clock",
    )
    parser.add_argument(
        "--run-id",
        help="the operator-declared run id — the evidence directory's name",
    )
    parser.add_argument("--pool", type=Path, default=None, help="the fetch pool")
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help="the generation budget",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--render",
        type=Path,
        metavar="EVIDENCE",
        help=(
            "render the committed artifact from this evidence document "
            "(`whetstone-baseline-run/1`); mutually exclusive with measuring"
        ),
    )
    mode.add_argument(
        "--render-declaration",
        dest="render_declaration",
        type=Path,
        metavar="OUT",
        help=(
            "write the declaration-only state — the committed artifacts before any "
            "measurement — to OUT; mutually exclusive with measuring"
        ),
    )
    return parser


def _measure_flags(args: argparse.Namespace) -> dict[str, object]:
    """The measuring-only flags by their command-line names — the mutual-exclusion check's
    subject. `--checkpoint`/`--out`/`--recorded-on` are shared with the render modes and
    are not here."""
    return {
        "--weights": args.weights,
        "--heldout": args.heldout,
        "--tasks": args.tasks,
        "--public": args.public,
        "--runs": args.runs,
        "--workspace": args.workspace,
        "--timeout": args.timeout,
        "--run-id": args.run_id,
    }


def _render_main(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    """One render-mode command line: refuse measuring flags, then render or declare.

    A render mode beside a measuring flag is a command nobody meant, refused with the
    usage code. `--render` renders the three artifacts from the evidence and prints the
    artifact paths plus the measured-once wording; `--render-declaration` writes the
    pre-run committed state and prints its paths. Every named refusal is exit 2 with the
    reason on stderr, never a traceback.
    """
    given = [name for name, value in _measure_flags(args).items() if value is not None]
    if given:
        parser.error(
            "--render/--render-declaration are mutually exclusive with measuring; "
            f"measuring flag {given[0]} was also given"
        )
    if args.render is not None:
        missing = [
            name
            for name, value in (("--checkpoint", args.checkpoint), ("--out", args.out))
            if value is None
        ]
        if missing:
            parser.error(f"{', '.join(missing)} is required with --render")
        try:
            rendered = render_artifact(
                evidence=args.render,
                out=args.out,
                recorded_on=args.recorded_on,
                checkpoint=args.checkpoint,
            )
        except REFUSALS as refusal:
            print(f"whetstone baseline: {refusal}", file=sys.stderr)
            return 2
        for path in rendered:
            print(path)
        print(
            "the § 3 baseline is measured once, re-measured never: a rendered baseline is "
            "not re-rendered"
        )
        return 0
    try:
        rendered = render_declaration(
            out=args.render_declaration, recorded_on=args.recorded_on
        )
    except REFUSALS as refusal:
        print(f"whetstone baseline: {refusal}", file=sys.stderr)
        return 2
    for path in rendered:
        print(path)
    return 0


def _measure_main(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    """The measuring command line: every measuring flag present, one measurement, exit 0.

    The measuring flags are enforced as a group here (`parser.error`, the usage code)
    rather than by `required=True`, so a render-mode command line may name exactly the
    flags that mode reads; a measuring command line missing any of them is refused by
    name. The engine seam is resolved at call time, so a test can substitute the stub
    engine exactly as the gate's CLI tests substitute `gate.gate_engine`.
    """
    missing = [
        name
        for name, value in (
            ("--weights", args.weights),
            ("--checkpoint", args.checkpoint),
            ("--heldout", args.heldout),
            ("--tasks", args.tasks),
            ("--public", args.public),
            ("--runs", args.runs),
            ("--workspace", args.workspace),
            ("--timeout", args.timeout),
            ("--run-id", args.run_id),
            ("--out", args.out),
        )
        if value is None
    ]
    if missing:
        parser.error(f"measuring requires {', '.join(missing)}")
    try:
        measurement = measure(
            checkpoint=args.checkpoint,
            heldout=args.heldout,
            tasks=args.tasks,
            public=args.public,
            runs=args.runs,
            workspace=args.workspace,
            timeout=args.timeout,
            recorded_on=args.recorded_on,
            run_id=args.run_id,
            pool=args.pool,
            weights=args.weights,
            out=args.out,
            max_tokens=args.max_tokens,
            engine=baseline_engine,
        )
    except REFUSALS as refusal:
        print(f"whetstone baseline: {refusal}", file=sys.stderr)
        return 2
    for line in disclosure(measurement):
        print(line)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """The runbook door: `python -m whetstone.loop.baseline` — measure, render, or declare.

    Parses and dispatches the three modes the parser admits (`spec.md` requirement 6).
    Measuring exits 0 whatever the score: the baseline is the anchor, not a verdict, and
    coverage is disclosed, never a failure. Rendering (`--render EVIDENCE`) is the
    post-run chain's render step: it prints the artifact paths and the measured-once
    wording and exits 0. Declaring (`--render-declaration OUT`) writes the committed
    pre-run state and exits 0. Every named refusal — a same-series artifact at `--out`, a
    runs root inside `reports/`, an `--out` under a gitignored root, an unreadable
    evidence, a checkpoint that cannot be re-hashed, a held-out document that cannot be
    read, a base the weights root does not hold — is exit 2 with the reason named on
    stderr, never a traceback; argparse's own error path supplies the usage code for a
    mistyped or incomplete command line, and a render mode beside a measuring flag is
    refused with the same code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.render is not None or args.render_declaration is not None:
        return _render_main(parser, args)
    return _measure_main(parser, args)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BASELINE_SCHEMA",
    "REFUSALS",
    "BaselineAlreadyMeasured",
    "BaselineDocument",
    "BaselineMeasurement",
    "SeriesIdentity",
    "baseline_engine",
    "build_parser",
    "disclosure",
    "main",
    "measure",
    "read_baseline_document",
    "read_series_identity",
    "render_artifact",
    "render_declaration",
    "write_evidence",
]

