"""Stored completions in; the reason each one never became an applied patch. No model consulted.

`reports/baseline/` records that most verdict-reaching rollouts never got a patch onto disk, and
nothing on disk can say why: `NOT_APPLIED` means only *"git refused it"*
(`verify/strict.py:171-183` → `verify/repo.py:100,118`), which is where a malformed diff, a
mis-anchored one, a correct diff with a wrong path prefix, CRLF endings and a budget-truncated
patch all end up wearing the same tag. The next slice has to choose a response format on that
evidence. This module is what turns the tag back into causes, from the transcript, offline —
so every later question costs a file read rather than another night of generation.

**The taxonomy is read out of `patch.py`, never invented here.** `patch.py` has four `NoDiff`
construction sites and their reason strings *are* the partition; `NO_DIFF_MARKERS` names each by a
verbatim fragment of the sentence written at that site. The PRD flags an invented taxonomy as its
one red risk (`prd.md` § 8): a bucket set that merely resembles the extractor's reasons keeps
producing confident counts after the extractor gains a fifth reason, with the new reason drifting
into whichever bucket happens to match. `tests/bakeoff/test_attribution.py` walks `patch.py` with
`ast` and requires a bijection between sites and buckets, so a fifth reason fails the suite instead
of being absorbed — and until someone adds its bucket, this module answers `UNATTRIBUTED` rather
than guessing a neighbour.

**Two layers, because they cost differently and fail differently.** The pure layer re-runs the
run's own `extract_patch` over the stored text and needs nothing else. The checkout layer answers
the one question that cannot be answered from text alone — *did git refuse to read this patch, or
read it and refuse to apply it* — and needs the task's tree. Those two are the pair the current
report cannot separate, and their fixes are opposite: the first is an output-format problem the
next slice can address, the second is the base being wrong about the code, which no format
changes.

**A rollout the checkout layer could not reach is `UNATTRIBUTED`, by name.** Not folded into the
adjacent bucket, not dropped from the denominator. A missing measurement rendered as a measurement
is how a partial breakdown reads as a complete one, and this module's entire output is a set of
counts somebody will act on.

**The caller's checkout is never written to.** Deciding whether a patch applies means applying it,
and one tree is shared by every candidate's rollout on that task. So the apply happens against a
throwaway copy: otherwise attributing the second rollout would depend on what the first one wrote,
and the breakdown would change with the order the transcript was read in.

**Read-only towards the reward path.** `declared_paths` and `apply_patch` are imported from
`verify/repo.py` and called; nothing under `verify/` is modified, and nothing here is on the reward
path — this module grades no rollout and returns no verdict. It only explains one that already
happened. Stdlib, git, and the extractor the run itself used.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from whetstone.bakeoff.patch import Extracted, extract_patch
from whetstone.bakeoff.transcript import Transcribed
from whetstone.verify.repo import PatchError, apply_patch, declared_paths

#: The fragment of `verify/repo.py:100`'s message that means git would not read the patch — the
#: `--numstat` parse failed. Matched as a substring rather than reconstructed, because the two
#: `PatchError` messages are the only signal separating a parse refusal from an apply refusal
#: (`repo.py:100` vs `:118`), and both are raised as the same type. If either sentence is
#: reworded, the two checkout tests fail against real git rather than this module silently
#: attributing everything to whichever branch it fell through to.
_PARSE_REFUSAL = "could not be parsed"

#: The same, for `verify/repo.py:118` — git read the patch and would not apply it.
_APPLY_REFUSAL = "did not apply"


class Cause(str, Enum):
    """Why one rollout never reached a graded patch. A cause, deliberately not a verdict.

    `str` mixin so a cause serialises as its name, matching `Outcome` and `Status`. These are
    **not** ordered and must never be reduced against one another: they name distinct causes with
    distinct fixes, and the only thing anything downstream may do with them is count them.

    The first four are `patch.py`'s own `NoDiff` reasons and exist one-per-construction-site (see
    `NO_DIFF_MARKERS`). The rest are what a located diff met when it reached git.
    """

    #: The base returned nothing but whitespace. A fact about the model or the runtime, and the
    #: only one of these that no prompt or format change can address.
    NO_OUTPUT = "NO_OUTPUT"

    #: Fenced blocks came back, none of them a diff — a code sample or an explanation. The
    #: response-format bucket: the base answered the question and not the request.
    FENCED_WITHOUT_DIFF = "FENCED_WITHOUT_DIFF"

    #: A diff header with no hunk after it. The patch would change nothing, and the shape says
    #: the generation budget ran out before the first `@@`.
    HEADER_WITHOUT_HUNK = "HEADER_WITHOUT_HUNK"

    #: No diff header anywhere: the output is prose. A prompt problem, not a budget one.
    NO_DIFF_HEADER = "NO_DIFF_HEADER"

    #: A diff was located and git would not parse it — a corrupt or truncated patch. Truncation
    #: is *inferred* from this shape rather than measured: `mlx_runtime.generate` returns text
    #: with no finish reason, so nothing on disk records that the token cap was hit. Any report
    #: quoting this bucket has to say so rather than implying a measurement.
    WOULD_NOT_PARSE = "WOULD_NOT_PARSE"

    #: git read the patch, named the paths it touches, and refused to apply it — a wrong path, a
    #: context that does not match, a line-number anchor that is off. The base wrote a real patch
    #: about code it was wrong about, which is a different finding from every bucket above.
    PARSED_BUT_DID_NOT_APPLY = "PARSED_BUT_DID_NOT_APPLY"

    #: The patch applied cleanly, so this rollout is not one of the ones being explained here:
    #: whatever happened next, the held tests got to judge a real edit. Present so the breakdown
    #: totals over every rollout rather than over a filtered subset chosen by this module.
    APPLIED = "APPLIED"

    #: The question could not be asked — no checkout for this task, or an extractor reason with
    #: no bucket. Its own name, always, because "we could not measure this" and "we measured this
    #: and it failed" are different claims and only one of them is evidence.
    UNATTRIBUTED = "UNATTRIBUTED"


#: Bucket → a verbatim fragment of the sentence `patch.py` writes at that `NoDiff` site.
#:
#: A fragment rather than the whole sentence because two of the four reasons are f-strings
#: (`patch.py:180,184`), so the full runtime text depends on a count nobody can predict. Each
#: marker is chosen to sit **inside one literal run**, never spanning a `{...}`, which is what
#: lets the mapping test match it against the source and this module match it against the real
#: string a run produced.
#:
#: Adding a reason to `patch.py` and not adding it here fails the bijection test in
#: `tests/bakeoff/test_attribution.py`, which is the whole point: the alternative is an "other"
#: bin that grows quietly and reports a cause nobody has read.
NO_DIFF_MARKERS: Mapping[Cause, str] = {
    Cause.NO_OUTPUT: "no output at all beyond whitespace",
    Cause.HEADER_WITHOUT_HUNK: "a diff header was found but no hunk",
    Cause.FENCED_WITHOUT_DIFF: "fenced code block(s) but none of them contained a",
    Cause.NO_DIFF_HEADER: "line(s) the model produced; the output is prose",
}


@dataclass(frozen=True)
class Attribution:
    """One rollout, and why it came out the way it did. A reading of evidence, never a verdict.

    Carries the candidate and task rather than being keyed by them so a list of these can be
    filtered, sorted and counted without the caller reassembling the pair — and so a breakdown
    is always per candidate, which is what makes it readable: P1's finding was that the failure
    modes *differ* between bases, and a pooled count is exactly what would have hidden it.
    """

    #: The base whose rollout this was.
    candidate: str

    #: The task it was working on.
    task_id: str

    #: The bucket, and the only field anything counts.
    cause: Cause

    #: The sentence behind the bucket: `patch.py`'s own reason, or git's own refusal, verbatim.
    #: The bucket is for counting and this is for reading — whoever opens the breakdown to
    #: understand a single rollout needs what the tool actually said about it, not a paraphrase
    #: written here. Empty only when there is nothing to add (`APPLIED`).
    detail: str


def cause_of_reason(reason: str) -> Cause | None:
    """Which bucket `reason` belongs to, or `None` if `patch.py` has grown one nobody has bucketed.

    `None` rather than a fallback bucket, and rather than raising. A fallback would put an
    unexamined cause into a count someone acts on; raising would make one new extractor reason
    abort a replay over an entire night's transcript, losing the attribution of every rollout that
    *was* attributable. The caller renders `None` as `UNATTRIBUTED`, which is both true and
    countable.
    """
    for cause, marker in NO_DIFF_MARKERS.items():
        if marker in reason:
            return cause
    return None


def attribute(record: Transcribed, checkout: Path | None = None) -> Attribution:
    """Replay one stored rollout and say why it never became an applied patch.

    `checkout` is the task's tree at its base commit. Without it — or with a path that has since
    gone — the parse/apply question cannot be asked at all, and a located diff is attributed
    `UNATTRIBUTED` rather than to either answer. Guessing would manufacture the one distinction
    this module exists to draw.
    """
    extraction = extract_patch(record.completion)
    if not isinstance(extraction, Extracted):
        cause = cause_of_reason(extraction.reason)
        if cause is None:
            return _attributed(
                record,
                Cause.UNATTRIBUTED,
                f"the extractor gave a reason no bucket covers, so it is left unattributed "
                f"rather than counted as a cause it was never measured into: {extraction.reason}",
            )
        return _attributed(record, cause, extraction.reason)

    if checkout is None or not checkout.is_dir():
        return _attributed(
            record,
            Cause.UNATTRIBUTED,
            f"a diff was produced but no checkout was available at {str(checkout)!r}, so whether "
            f"git would parse or apply it could not be asked",
        )
    return _attributed(record, *_against_checkout(extraction.diff, checkout))


def attribute_all(
    records: Iterable[Transcribed],
    checkouts: Mapping[str, Path] | None = None,
) -> tuple[Attribution, ...]:
    """Attribute every stored rollout, in the order given.

    `checkouts` maps a task id to that task's tree. A task missing from it is `UNATTRIBUTED` — a
    fallback to "whichever checkout is available" would apply one task's patch to another task's
    code and answer a question nobody asked, confidently.
    """
    available = checkouts or {}
    return tuple(attribute(record, available.get(record.task_id)) for record in records)


def breakdown(attributions: Iterable[Attribution]) -> dict[str, dict[Cause, int]]:
    """Counts per candidate, per cause. Causes that did not occur are absent, never zero-filled.

    Per candidate because that is the finding: `reports/baseline/` reports the failure modes
    differing between bases — unapplicable patches at the small and large ends, empty diffs in the
    middle — and a pooled total is precisely what would have hidden it.

    Absent rather than zero because a zero here would be indistinguishable from a bucket that has
    stopped matching anything, and the difference between "this never happened" and "this stopped
    being observed" is the difference between a finding and a broken instrument.
    """
    counts: dict[str, dict[Cause, int]] = {}
    for attribution in attributions:
        per_candidate = counts.setdefault(attribution.candidate, {})
        per_candidate[attribution.cause] = per_candidate.get(attribution.cause, 0) + 1
    return counts


def _against_checkout(diff: str, checkout: Path) -> tuple[Cause, str]:
    """Ask git the one question text cannot answer: would it parse this, and would it apply it?

    `declared_paths` first, because it parses and reports without writing (`repo.py:87-96`), so a
    corrupt patch is separated for the price of one git invocation and never reaches the copy
    below. The apply then runs against a **throwaway copy** of the tree: `apply_patch` writes, one
    checkout is shared by every candidate's rollout on that task, and an attributor that dirtied it
    would make each rollout's answer depend on the ones read before it.

    A `PatchError` whose message matches neither known refusal is `UNATTRIBUTED` rather than
    assigned to the nearer of the two. `declared_paths` has a third raise site — git's report of
    what the patch touches being unreadable (`repo.py:108`) — which is a statement about the
    harness, not about the patch, and it must not be counted as either kind of model failure.
    """
    try:
        declared_paths(diff, checkout)
    except PatchError as exc:
        return _refusal(exc, _PARSE_REFUSAL, Cause.WOULD_NOT_PARSE)

    with tempfile.TemporaryDirectory(prefix="whetstone-attribution-") as scratch:
        replica = Path(scratch) / "checkout"
        shutil.copytree(checkout, replica, symlinks=True)
        try:
            apply_patch(diff, replica)
        except PatchError as exc:
            return _refusal(exc, _APPLY_REFUSAL, Cause.PARSED_BUT_DID_NOT_APPLY)
    return Cause.APPLIED, ""


def _refusal(exc: PatchError, expected: str, cause: Cause) -> tuple[Cause, str]:
    """`cause` if git refused for the reason this step tests for, `UNATTRIBUTED` if not."""
    message = str(exc)
    if expected in message:
        return cause, message
    return (
        Cause.UNATTRIBUTED,
        f"git refused the patch in a way this module does not recognise, so it is named rather "
        f"than counted as {cause.value}: {message}",
    )


def _attributed(record: Transcribed, cause: Cause, detail: str) -> Attribution:
    """Bind a cause to the rollout it explains. One construction site, so the key cannot drift."""
    return Attribution(
        candidate=record.candidate,
        task_id=record.task_id,
        cause=cause,
        detail=detail,
    )


__all__ = [
    "NO_DIFF_MARKERS",
    "Attribution",
    "Cause",
    "attribute",
    "attribute_all",
    "breakdown",
    "cause_of_reason",
    "extract_patch",
]
