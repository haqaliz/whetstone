"""The retry-aware transcript: every attempt is a record, and replay decides among them.

With retries a (candidate, task) is generated more than once. Each attempt is a record:
`attempt` numbers it within the run, and `decision` says whether a later record followed it
("retry") or whether it is the record the run carried forward and scored ("graded"). The two
frozen consumers (`attribution.py`, `autopsy.py`) read through `Transcript.replay()`, which
is keyed and last-record-wins (`transcript.py:134-144`) — so multi-record keys are safe by
construction, and the decided record is the last one for its key.

Everything asserted here follows from that contract:

* **The decided record is the last one for its key.** Replaying a retry-shaped transcript —
  three records, one key — returns the third, byte-for-byte, carrying `decision == "graded"`:
  the record the run would have scored. The earlier attempts survive on disk (append-only)
  and are the evidence that the retry happened.
* **A missing `attempt` or `decision` key fails decode.** No defaults
  (`transcript.py:244-258`): a field this writer never wrote is a schema the reader cannot
  trust, and the plausible default — a fake first attempt, a fake "graded" — is exactly the
  invention that would make a pre-retry transcript read as a clean single-attempt run with
  no evidence it was one.
* **A trailing `"retry"` record is corruption, raised rather than repaired.** In the live
  run a retry always has a following record; one that does not is a run killed between the
  retry and its completion — the same missing-evidence family as a truncated line, and it
  raises rather than silently reporting a decision the run never made.

No model, no `mlx`, no network: every record here is constructed by hand.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whetstone.bakeoff.transcript import Transcribed, Transcript, TranscriptUnreadable

#: A completion shaped like the ones this instrument exists to explain: prose, a fenced block
#: with backticks, embedded newlines, and a trailing newline. Every one of those is something a
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


def record(attempt: int, decision: str, **overrides: str) -> Transcribed:
    """One attempt under the retry schema: numbered and decided, awkward completion by default."""
    fields = {
        "candidate": "base-a",
        "task_id": "t1",
        "prompt_sha256": "0" * 64,
        "prompt": "Fix addition.\n\nFailing: tests/test_calc.py::test_add\n",
        "completion": AWKWARD,
    }
    return Transcribed(attempt=attempt, decision=decision, **(fields | overrides))


def test_a_retry_shaped_transcript_replays_the_decided_record(tmp_path: Path) -> None:
    """Three attempts, one key: replay returns the last — the graded one — byte-for-byte.

    A retry means the earlier attempts were superseded; the record the run would have carried
    forward and scored is the last one written, and it is the one that says "graded". Both
    facts must hold together: a replay that picked the last record but reported an earlier
    attempt or decision would describe a run that never happened.
    """
    transcript = Transcript(path=tmp_path / "transcript.jsonl")
    first = record(1, "retry", completion="attempt one, incomplete")
    second = record(2, "retry", completion="attempt two, still incomplete")
    decided = record(3, "graded")

    for attempt in (first, second, decided):
        transcript.append(attempt)

    replayed = transcript.replay()

    assert replayed == {("base-a", "t1"): decided}, (
        "WHY THIS IS A FAILURE: a retry-shaped transcript did not replay to its decided "
        f"record. Got {replayed!r}. The decided completion is the one the run would have "
        "scored; replaying an earlier attempt would attribute a cause to text that was "
        "superseded"
    )
    assert replayed[("base-a", "t1")].attempt == 3, (
        "WHY THIS IS A FAILURE: the decided record does not carry its attempt number, so "
        "downstream cannot tell which draw of the run was graded"
    )
    assert replayed[("base-a", "t1")].decision == "graded", (
        "WHY THIS IS A FAILURE: the decided record does not declare decision 'graded', so "
        "the transcript cannot say which attempt the run carried forward"
    )
    assert transcript.path.read_text(encoding="utf-8").count("\n") == 3, (
        "WHY THIS IS A FAILURE: the transcript is not append-only — all three attempts must "
        "survive on disk. Rewriting the file to keep one is how a process killed mid-rewrite "
        "loses the lot"
    )


@pytest.mark.parametrize("missing", ["attempt", "decision"])
def test_a_missing_retry_field_fails_decode(tmp_path: Path, missing: str) -> None:
    """An old-schema line is unreadable, never defaulted — for either new field.

    `_decode` is strict about everything (`transcript.py:244-258`): a field this writer
    never wrote is refused, and the plausible default — attempt 1, "graded" — is exactly
    the invention that would make a pre-retry transcript read as a clean single-attempt
    run when the reader has no evidence it was one.
    """
    transcript = Transcript(path=tmp_path / "transcript.jsonl")
    transcript.append(record(1, "graded"))

    old_schema = {
        "candidate": "base-b",
        "task_id": "t2",
        "prompt_sha256": "0" * 64,
        "prompt": "fix the bug",
        "completion": "prose, no diff",
        "attempt": 1,
        "decision": "graded",
    }
    del old_schema[missing]
    with transcript.path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(old_schema) + "\n")

    with pytest.raises(TranscriptUnreadable) as unreadable:
        transcript.replay()

    assert missing in str(unreadable.value), (
        "WHY THIS IS A FAILURE: the unreadable line's error does not name the missing "
        f"{missing!r} field, so an operator cannot tell an old-schema transcript from a "
        f"truncated one. Got {str(unreadable.value)!r}"
    )
    assert str(transcript.path) in str(unreadable.value), (
        "WHY THIS IS A FAILURE: the error does not name the file that cannot be read, so an "
        "operator holding several transcripts is told only that one of them is bad"
    )


def test_round_trip_is_deterministic_and_lossless(tmp_path: Path) -> None:
    """The same records, written to two files, replay identically — and as they were written.

    The retry fields are part of the record's identity: a transcript that lost the attempt
    number or the decision would report a run that was never decided. Two files written from
    the same records must replay to the same dict, and each key's record must be the last
    attempt written for it.
    """
    attempts = (
        record(1, "retry", completion="stub one"),
        record(2, "graded", completion=AWKWARD),
    )
    first = Transcript(path=tmp_path / "a.jsonl")
    second = Transcript(path=tmp_path / "b.jsonl")
    for attempt in attempts:
        first.append(attempt)
        second.append(attempt)

    assert first.replay() == second.replay(), (
        "WHY THIS IS A FAILURE: identical writes replayed differently, so the transcript is "
        "not a deterministic function of what was written — an offline replay could then "
        "disagree with the live run for no recorded reason"
    )
    assert first.replay() == {("base-a", "t1"): attempts[1]}, (
        "WHY THIS IS A FAILURE: the round trip did not return the records as written, so the "
        "transcript is not evidence of the run that produced it"
    )


def test_a_trailing_retry_record_is_refused_as_corruption(tmp_path: Path) -> None:
    """A last record declaring "retry" is a run killed mid-retry, raised not repaired.

    In the live run a retry always has a following record — the decision "retry" means a
    later attempt exists. A transcript whose last record for a key says "retry" is therefore
    a run that was killed between the retry and its completion: the same missing-evidence
    family as a truncated line, and the same answer — `TranscriptUnreadable`, never a
    silently reported decision the run never made.
    """
    transcript = Transcript(path=tmp_path / "transcript.jsonl")
    transcript.append(record(1, "retry"))

    with pytest.raises(TranscriptUnreadable) as unreadable:
        transcript.replay()

    message = str(unreadable.value)
    assert "retry" in message and ("base-a" in message or "t1" in message), (
        "WHY THIS IS A FAILURE: the refusal does not name the impossible shape — a trailing "
        f"record declaring a retry — or the key it is filed under. Got {message!r}"
    )
