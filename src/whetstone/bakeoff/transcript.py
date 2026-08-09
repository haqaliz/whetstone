"""The transcript: keep what the model actually wrote, so a zero can be diagnosed without a model.

`reports/baseline/` records that most verdict-reaching rollouts never got a patch onto disk, and
**nothing on disk can say why**. The scoring path generates a completion, extracts a patch from it,
and drops the text; `NOT_APPLIED` then means only *"git refused it"*, which conflates several
distinct causes — no fenced block, a header with no hunk, truncation, a diff git would not parse, a
diff git parsed and would not apply. Choosing a patch format to fix that on evidence rather than on
taste needs the completions themselves, and re-running the night to get them costs another night of
compute per question asked. So the completion is kept.

**This module stores; it does not interpret.** No extraction, no classification, no counting. The
cause breakdown is derived downstream from one place, so there is exactly one definition of each
bucket, and it is derived from `patch.py`'s own reasons rather than from a taxonomy invented beside
the storage.

**And it stores without widening the model seam.** `RecordingGenerator` is a `Generator` wrapping a
`Generator`, so the recording is installed by composition at the driver and nothing between the
driver and the model — `sweep`, `score` — learns that a transcript exists. The alternative, a second
method on `generator.Generator`, would cost the project the one property that makes every test in
this package model-free: a one-method seam is one thing the MLX adapter has to reproduce faithfully,
and each addition is another chance for the substitution to become a fiction.

Three properties, and none of them are style:

* **The completion is stored byte-for-byte.** Stripping whitespace, dropping a trailing newline, or
  re-wrapping a fenced block would silently repair the exact defects the replay exists to measure —
  and the repaired text would extract to a patch the live run never had. The evidence has to be
  worth less than the original in no respect at all.
* **A line that cannot be read is an error, never a skipped record.** A truncated final line is what
  a killed process leaves behind. A replay that dropped it quietly would report a breakdown over
  fewer rollouts than the run produced while looking complete — missing evidence rendered as a
  confident answer.
* **A missing file is the ordinary first run.** It must stay distinguishable from a corrupt one:
  the first needs nothing, the second needs a human.

**Locality.** A completion here quotes the user's own private donor code back verbatim. The
transcript's home is a gitignored root and it is never written under a committed output directory;
that is a privacy guarantee, and it is enforced where the path is chosen rather than here, because
this module is handed a path and is not the thing that picks it.

The shape deliberately mirrors `journal.py` — same JSON Lines, same field-by-field codec, same
raise-don't-skip rule. A second serialisation style in one package would be a second set of failure
modes to learn for no gain.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from whetstone.bakeoff.generator import Generator
from whetstone.bakeoff.rendering import prompt_hash

#: What a record is filed and looked up under. Both halves are needed for the same reason the
#: journal needs both (`journal.py:41-44`): one candidate's completion on a task says nothing about
#: another's. Spelled out here rather than imported from `journal.py`, because the transcript is
#: readable — deliberately — without loading the checkpoint's record types, and through them the
#: control and scoring modules, none of which an offline replay has any use for.
Key = tuple[str, str]


class TranscriptUnreadable(ValueError):
    """A transcript line could not be read back. Raised rather than skipped — see the docstring.

    Its own type so a caller can tell a corrupt transcript from a missing one: the second is the
    ordinary first run, and the first means evidence was lost and a human has to decide whether
    what remains can be reasoned from.
    """


@dataclass(frozen=True)
class Transcribed:
    """One generation, whole: what the model was asked, and what it wrote back.

    The prompt travels with the completion because a completion alone cannot be re-extracted
    *against anything* — the diagnosis asks what this text was a response to. `prompt_sha256`
    travels alongside the prompt rather than instead of it: the digest is what ties a record to the
    frozen generation contract the run was sealed against, and the text is what makes the record
    readable by a person trying to understand a failure. Storing only the digest would make the
    transcript verifiable and useless; only the text would make it readable and unattributable.

    With retries a (candidate, task) is generated more than once, so a record is one *attempt*:
    `attempt` numbers it within the run, and `decision` says whether a later record followed it
    ("retry") or whether it is the record the run carried forward and scored ("graded"). The
    decided record is always the last one for its key — that is what `replay` selects, unchanged
    (`replay()` below).
    """

    #: The base that produced this completion.
    candidate: str

    #: The task it was working on.
    task_id: str

    #: The digest of `prompt`, as the run computed it, so a record can be tied to the contract.
    prompt_sha256: str

    #: The prompt as sent, verbatim.
    prompt: str

    #: The completion as returned, verbatim — never normalised. See the module docstring.
    completion: str

    #: Which attempt within the (candidate, task) run this record is. One-based; the first
    #: generation of a pair is attempt 1, its retry is attempt 2.
    attempt: int

    #: What became of this attempt: "retry" when a later record follows it, "graded" when it
    #: is the decided record for its key.
    decision: str

    @property
    def key(self) -> Key:
        """The (candidate, task) pair this record is filed under."""
        return (self.candidate, self.task_id)


@dataclass(frozen=True)
class Transcript:
    """An append-only transcript file. One JSON object per line, one record per attempt.

    JSON Lines rather than a single JSON document because the file is written *during* a run that
    may be killed at any moment: a document would have to be rewritten whole on every generation,
    and a process killed mid-rewrite loses everything already recorded rather than the one line it
    was adding. Append-only for the same reason — nothing already on disk is ever touched again.

    A (candidate, task) now holds **several** records when a run retried: each attempt is a line,
    and the decided one is the last. `replay` selects it (`replay()` below), so the frozen
    consumers (`attribution.py`, `autopsy.py`) read the same transcript as ever — multi-record
    keys were already safe by the keyed last-record-wins rule.

    Frozen: a transcript names a file and nothing else. There is no in-memory index to go stale,
    which is why `replay` reads the file each time it is asked rather than caching.
    """

    #: The transcript file. Created, with its parents, on the first append.
    path: Path

    def append(self, record: Transcribed) -> None:
        """Record `record`, durably enough that a killed process keeps it.

        Flushed on every call. A buffered transcript is one whose last few generations exist only
        in the memory of the process that is about to be killed — and those are the expensive ones,
        each costing a model generation that cannot be re-derived from anything on disk.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_encode(record), sort_keys=True) + "\n")
            handle.flush()

    def replay(self) -> dict[Key, Transcribed]:
        """Every record on disk, keyed by (candidate, task). An absent file is an empty run.

        A missing file is not an error: nothing has been recorded yet. A file that exists and
        cannot be parsed *is* one — see the module docstring on why a dropped line is worse than a
        raise. Reading never creates the file, so "no transcript here" cannot become "an empty
        transcript was recorded here".

        A repeated key takes the **last** record, which is the append-only file's own answer: with
        retries, a pair recorded more than once is a run that tried again, and the later completion
        is the decided one — the record the run would have carried forward and scored. `decision`
        says so per record: every record but the last for a key is `"retry"`, and the last is
        `"graded"`. A last record declaring `"retry"` is refused as corruption: in the live run a
        retry always has a following record, so a trailing one is a run killed between the retry
        and its completion — missing evidence, raised rather than repaired.
        """
        if not self.path.exists():
            return {}

        records: dict[Key, Transcribed] = {}
        last_line: dict[Key, int] = {}
        for number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                record = _decode(json.loads(line))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                raise TranscriptUnreadable(
                    f"line {number} of the transcript at {str(self.path)!r} could not be read "
                    f"({type(exc).__name__}: {exc}). It is not skipped: a replay that quietly "
                    f"dropped a recorded generation would attribute the run's failures over fewer "
                    f"rollouts than it produced, and report that partial breakdown as a complete "
                    f"one"
                ) from exc
            records[record.key] = record
            last_line[record.key] = number

        for key, record in records.items():
            if record.decision == "retry":
                raise TranscriptUnreadable(
                    f"line {last_line[key]} of the transcript at {str(self.path)!r} is the last "
                    f"record for {key!r} and declares decision 'retry'. In the live run a retry "
                    f"always has a following record — the decided one — so a trailing 'retry' is "
                    f"a run killed between the retry and its completion. It is not skipped or "
                    f"repaired: replaying it would report a decision the run never made"
                )
        return records


@dataclass(frozen=True)
class RecordingGenerator:
    """A base with a transcript behind it: it answers exactly as it would have, and is written down.

    A `Generator` by structure, wrapping another, so `sweep` and `score` learn nothing about the
    transcript's existence. That is the whole reason this is a wrapper rather than a second method
    on the seam: `generator.Generator` has one method deliberately, and every addition to it is
    another thing the MLX adapter must reproduce faithfully before the substitution every test in
    this package relies on stops being a fiction.

    **Constructed per (candidate, task).** The key is what the record is filed under, and deriving
    it from anything the prompt carries would be inferring, at write time, a fact the caller already
    knows. A recorder that guessed would file one base's failure under another's run.

    **The observation must not change what is observed**, in either direction. The completion is
    returned as it arrived and stored as it arrived: the returned text is what `extract_patch` runs
    on live, so editing it would make the instrument affect the run's own verdicts, and the stored
    text is what an offline replay runs on, so editing that would make the replay disagree with the
    live run and report a cause that never occurred. Whitespace is the whole example — the extractor
    reads a fenced block, and a stripped trailing newline is the difference between two extractions.

    **The record follows the generation and never anticipates one.** The inner generator is called
    first and the row is written only once it has returned. A prompt refused by the frozen contract
    (`run.Sealed` raises before delegating) and a model process that dies mid-run are the same
    shape, and in both a row written up front leaves a completion-less record in a file whose entire
    purpose is completions — which an offline replay counting rows would report as a rollout that
    happened. Exceptions propagate untouched for the reason `sweep` gives for not catching them: an
    interrupted run must stop rather than produce a full-looking record set with holes in it.

    **The row is the decided attempt.** The recorder observes exactly one generation per
    (candidate, task) — the one the run carried forward — so the row it writes is attempt 1 of
    that run, decided and graded. The retry wrapper that makes the ordinary case multi-attempt
    (aspect `retry-loop`) writes its own intermediate rows; nothing in this wrapper guesses an
    attempt that was not observed.
    """

    #: What actually generates. Called exactly once per `generate`, with the prompt unaltered.
    inner: Generator

    #: Where the record goes. Not created until there is something to write.
    transcript: Transcript

    #: The base being recorded — half the key, and the caller's to know.
    candidate: str

    #: The task being recorded — the other half.
    task_id: str

    def generate(self, prompt: str) -> str:
        """Delegate, record what came back, and return it unchanged. In that order, deliberately."""
        completion = self.inner.generate(prompt)
        self.transcript.append(
            Transcribed(
                candidate=self.candidate,
                task_id=self.task_id,
                # Taken with the run's own function rather than recomputed here: the digest's one
                # purpose is to tie this completion to the generation contract frozen in the
                # provenance block, and a second construction of it is a second thing that can
                # disagree with the first while both look correct on disk.
                prompt_sha256=prompt_hash(prompt),
                prompt=prompt,
                completion=completion,
                # The recorder observes one generation per (candidate, task) — the decided one —
                # so the row is attempt 1 of the run, graded. See the class docstring.
                attempt=1,
                decision="graded",
            )
        )
        return completion


def _encode(record: Transcribed) -> dict[str, Any]:
    """`record` as plain JSON types. Written out field by field, deliberately.

    `dataclasses.asdict` would be shorter and would silently carry any field added later into the
    file without a decoder for it — so a schema change would round-trip lossily rather than
    failing. Naming every field means a new one breaks this function first.
    """
    return {
        "candidate": record.candidate,
        "task_id": record.task_id,
        "prompt_sha256": record.prompt_sha256,
        "prompt": record.prompt,
        "completion": record.completion,
        "attempt": record.attempt,
        "decision": record.decision,
    }


def _decode(raw: Any) -> Transcribed:
    """The inverse of `_encode`, strict about everything. A missing key raises; nothing defaults.

    No `.get(..., default)` anywhere: a default would turn a field this writer never wrote into a
    plausible value, and the most plausible value here — `""` for a completion — is the one that
    would invent an empty generation, which is itself one of the failure causes being counted. The
    retry fields follow the same rule: a line missing `attempt` or `decision` is an old-schema
    transcript, and defaulting it — to attempt 1, "graded" — would invent a decided single-attempt
    run with no evidence it was one. A `KeyError` is caught by `replay` and reported as a corrupt
    line.
    """
    return Transcribed(
        candidate=raw["candidate"],
        task_id=raw["task_id"],
        prompt_sha256=raw["prompt_sha256"],
        prompt=raw["prompt"],
        completion=raw["completion"],
        attempt=raw["attempt"],
        decision=raw["decision"],
    )


__all__ = [
    "Key",
    "RecordingGenerator",
    "Transcribed",
    "Transcript",
    "TranscriptUnreadable",
]
