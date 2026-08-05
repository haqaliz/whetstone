"""The transcript: what the model actually wrote, kept, so a zero can be diagnosed offline.

`reports/baseline/` records that most verdict-reaching rollouts never got a patch onto disk, and
nothing on disk can say why — the completion is extracted from and then dropped. The transcript is
the evidence that makes the *why* answerable a second time, without a model and without another
night of compute. Everything asserted here follows from that one purpose:

* **The completion is stored byte-for-byte.** A transcript that normalised whitespace, or dropped a
  trailing newline, or re-wrapped a fenced block would silently repair the exact defects the replay
  exists to measure — and the repaired text would then extract to a patch the live run never got.
* **An unreadable line raises rather than being skipped.** A truncated final line is what a killed
  process leaves behind, and a replay that quietly dropped it would report a cause breakdown over
  fewer rollouts than the run produced while looking complete. Silence here converts missing
  evidence into a confident wrong answer.
* **A missing file is not an error.** That is the ordinary first run, and it has to be
  distinguishable from a corrupt one, because one needs nothing and the other needs a human.

No model, no `mlx`, no network: every record here is constructed by hand.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whetstone.bakeoff.transcript import Transcribed, Transcript, TranscriptUnreadable

#: A completion shaped like the ones this instrument exists to explain: prose, a fenced block with
#: backticks, embedded newlines, and a trailing newline. Every one of those is something a
#: well-meaning writer might normalise away, and each is load-bearing for `extract_patch`.
AWKWARD = (
    "Here is the fix.\n\n"
    "```diff\n"
    "--- a/calc.py\n"
    "+++ b/calc.py\n"
    "@@ -1,2 +1,2 @@\n"
    "-def add(a, b):\n"
    "-    return a - b\n"
    "+def add(a, b):\n"
    "+    return a + b\n"
    "```\n"
)


def record(**overrides: str) -> Transcribed:
    """One plausible record, with the awkward completion by default."""
    fields = {
        "candidate": "base-a",
        "task_id": "t1",
        "prompt_sha256": "0" * 64,
        "prompt": "Fix addition.\n\nFailing: tests/test_calc.py::test_add\n",
        "completion": AWKWARD,
    }
    return Transcribed(**(fields | overrides))


def test_a_completion_survives_the_round_trip_byte_for_byte(tmp_path: Path) -> None:
    """Written and replayed, a record is the record that was written — not a tidied version of it.

    Asserted on the whole dataclass *and* separately on the completion string, because the
    dataclass comparison would still pass if some future encoder normalised both sides the same
    way. The completion is the one field whose exact bytes decide what `extract_patch` returns.
    """
    transcript = Transcript(path=tmp_path / "transcript.jsonl")
    written = record()

    transcript.append(written)
    replayed = transcript.replay()

    assert replayed == {("base-a", "t1"): written}, (
        "WHY THIS IS A FAILURE: a record written to the transcript did not come back as itself, "
        f"so the transcript is not evidence of what happened. Got {replayed!r}"
    )
    assert replayed[("base-a", "t1")].completion == AWKWARD, (
        "WHY THIS IS A FAILURE: the completion changed in storage. The whole point of keeping it "
        "is to re-derive offline what the extractor did with it live; a transcript that repairs "
        "the text repairs the defect under investigation and reports a cause that never occurred"
    )


def test_a_truncated_line_raises_rather_than_being_skipped(tmp_path: Path) -> None:
    """A killed writer leaves half a line behind. Replay must say so, not quietly drop it.

    The healthy half of this test is what gives it teeth: the same first record replays cleanly
    from a file that was not truncated, so the raise below is caused by the truncation and not by
    a replay that refuses everything.
    """
    healthy = Transcript(path=tmp_path / "healthy.jsonl")
    healthy.append(record())
    assert len(healthy.replay()) == 1, (
        "WHY THIS IS A FAILURE: an intact transcript did not replay, so the corruption assertion "
        "below would pass for the wrong reason — against a replay that raises on everything"
    )

    corrupt = Transcript(path=tmp_path / "corrupt.jsonl")
    corrupt.append(record())
    with corrupt.path.open("a", encoding="utf-8") as handle:
        handle.write('{"candidate": "base-a", "task_id": "t2", "prom')

    with pytest.raises(TranscriptUnreadable) as unreadable:
        corrupt.replay()

    assert str(corrupt.path) in str(unreadable.value), (
        "WHY THIS IS A FAILURE: the error does not name the file that cannot be read, so an "
        f"operator holding several transcripts is told only that one of them is bad. Got "
        f"{str(unreadable.value)!r}"
    )
    assert isinstance(unreadable.value, ValueError), (
        "WHY THIS IS A FAILURE: TranscriptUnreadable is not a ValueError, so a caller with an "
        "existing `except ValueError` around its replay would let a corrupt transcript through"
    )


def test_a_missing_file_replays_empty_and_is_not_a_corrupt_one(tmp_path: Path) -> None:
    """No transcript yet is the ordinary first run; it must not look like damage, or create a file.

    Distinguishability runs both ways, which is why this test lives beside the truncation one: an
    absent file that raised would make every first run look broken, and a corrupt file that
    returned empty would make lost evidence look like a run that recorded nothing.
    """
    transcript = Transcript(path=tmp_path / "absent" / "transcript.jsonl")

    assert transcript.replay() == {}, (
        "WHY THIS IS A FAILURE: a transcript that does not exist yet did not replay as empty, so "
        "the first run of the instrument is indistinguishable from a damaged one"
    )
    assert not transcript.path.exists(), (
        "WHY THIS IS A FAILURE: merely reading a transcript created it. A reader with a side "
        "effect turns 'no transcript here' into 'an empty transcript was recorded here'"
    )


def test_a_repeated_key_takes_the_later_record(tmp_path: Path) -> None:
    """Two records for one (candidate, task) means the pair ran twice; the second is what happened.

    The append-only file's own answer, and the same rule the journal follows: the later write is
    the one whose completion the run would have carried forward, so replaying the earlier one
    would attribute a cause to text that was superseded.
    """
    transcript = Transcript(path=tmp_path / "transcript.jsonl")
    first = record(completion="I have made no change.")
    second = record(completion=AWKWARD)

    transcript.append(first)
    transcript.append(second)
    replayed = transcript.replay()

    assert replayed == {("base-a", "t1"): second}, (
        "WHY THIS IS A FAILURE: a re-run (candidate, task) pair did not replay as its later "
        f"record, so the transcript reports a completion the run superseded. Got {replayed!r}"
    )
    assert transcript.path.read_text(encoding="utf-8").count("\n") == 2, (
        "WHY THIS IS A FAILURE: the transcript is not append-only — both records must survive on "
        "disk. Rewriting the file to keep one is how a process killed mid-rewrite loses the lot"
    )


def test_every_field_reaches_disk_under_its_own_name(tmp_path: Path) -> None:
    """The stored line is field-by-field JSON, so a field added later cannot ride along undecoded.

    Asserted against the raw line rather than through `replay`, because a round-trip through an
    encoder and its own inverse passes even when the two agree on something nobody else can read.
    """
    transcript = Transcript(path=tmp_path / "transcript.jsonl")
    transcript.append(record())

    stored = json.loads(transcript.path.read_text(encoding="utf-8").splitlines()[0])

    assert set(stored) == {"candidate", "task_id", "prompt_sha256", "prompt", "completion"}, (
        "WHY THIS IS A FAILURE: the line on disk does not carry exactly the five declared fields. "
        f"A field written without a decoder round-trips lossily rather than failing. Got {stored!r}"
    )
    assert stored["completion"] == AWKWARD, (
        "WHY THIS IS A FAILURE: the completion on disk is not the completion that was generated, "
        "so the evidence was altered before anything read it back"
    )
