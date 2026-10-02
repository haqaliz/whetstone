"""Guards over the gate-leakage finding, so its quoted output cannot drift from the tool.

`docs/planning/gate-leakage-guard/finding.md` records what `whetstone check-leakage` said
about night-001's training set against the committed held-out document. The finding is a
quotation, and a quotation is only honest while it still equals what the tool prints, so:

- **Unconditionally**, the finding exists and carries its seven sections.
- **When the primary checkout's gitignored artefacts exist** (night-001's `dataset.json`, the
  held-out document, the adapter's `provenance.json`), a fresh `check-leakage` run through
  `cli.main` must reproduce the finding's exit code and every line of output — after the one
  redaction the finding states — and the counts it prints; the adapter's recorded
  `dataset_digest` must equal night-001's dataset digest, and the finding must quote it.
  When any artefact is absent the test **skips loudly**, naming it: it never passes silently.
- **Unconditionally**, the finding carries no gate verdict word, no percentage, no home path,
  and no sibling-project name. The names are checked by digest so they are not written here.

The primary checkout is found from git (`--git-common-dir`), never from a literal path, because
a worktree holds none of the gitignored data.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

import pytest

from whetstone import cli

ROOT = Path(__file__).resolve().parents[1]
FINDING = ROOT / "docs" / "planning" / "gate-leakage-guard" / "finding.md"

SECTIONS = (
    "## 1. What was run",
    "## 2. What it printed",
    "## 3. The conclusion",
    "## 4. Why this is not a seam regression",
    "## 5. The provenance link",
    "## 6. Limits",
    "## 7. The next unit",
)

REDACTION = "<pre-re-mint label>"
# The one redaction: the label in front of the trailing sha12 on the identity line.
_TRAINED_ON = re.compile(r"(trained on )\S+?-([0-9a-f]{12})\b")

# sha256 of each lower-cased sibling-project name that must never reach a committed file.
FORBIDDEN_NAME_DIGESTS = frozenset(
    {
        "3e3721d14da8539340b5737c461b2d3a5556518d85e60a03a8dcfb60f29bffff",
        "7f72937a338ece153c4ad8c39b1b81ed80eb0f709804bda546046396a975329a",
    }
)


def _finding() -> str:
    return FINDING.read_text(encoding="utf-8")


def _primary() -> Path:
    common = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return Path(common).parent


def _redact(line: str) -> str:
    return _TRAINED_ON.sub(rf"\g<1>{REDACTION}-\g<2>", line)


def test_the_finding_exists_with_its_seven_sections() -> None:
    assert FINDING.is_file(), f"the finding is absent: {FINDING.relative_to(ROOT)}"
    text = _finding()
    positions = []
    for heading in SECTIONS:
        assert heading in text, f"the finding lacks the section {heading!r}"
        positions.append(text.index(heading))
    assert positions == sorted(positions), "the seven sections are out of order"


def test_the_finding_carries_no_verdict_word_percentage_home_path_or_sibling_name() -> None:
    text = _finding()
    for word in ("promoted", "rejected"):
        assert not re.search(rf"\b{word}\b", text, re.IGNORECASE), (
            f"the finding uses {word!r}; no gate ran, so it has no gate verdict"
        )
    assert "%" not in text, "the finding states a percentage; it states counts only"
    assert not re.search(r"/Users/|/home/|~/", text), "the finding names a home path"
    tokens = {token.lower() for token in re.findall(r"[A-Za-z]+", text)}
    leaked = {t for t in tokens if hashlib.sha256(t.encode()).hexdigest() in FORBIDDEN_NAME_DIGESTS}
    assert not leaked, "the finding names a sibling project"
    assert REDACTION in text, "the finding does not carry its stated redaction"


def test_the_finding_equals_a_fresh_check_leakage_run(
    capsys: pytest.CaptureFixture[str],
) -> None:
    primary = _primary()
    night = primary / "runs" / "nights" / "night-001"
    dataset = night / "dataset.json"
    heldout = primary / "tasks" / "heldout" / "source-b.json"
    provenance = primary / "checkpoints" / "portability-arm" / "provenance.json"
    for artefact in (dataset, heldout, provenance):
        if not artefact.is_file():
            pytest.skip(
                "SKIPPED LOUDLY: the finding cannot be re-checked without the primary "
                f"checkout's gitignored artefact {artefact.relative_to(primary)}"
            )

    code = cli.main(["check-leakage", "--run", str(night), "--heldout", str(heldout)])
    lines = capsys.readouterr().out.splitlines()
    text = _finding()

    assert re.search(rf"\*\*Exit code: {code}\.\*\*", text), (
        f"the finding does not record the tool's exit code {code}"
    )
    assert lines, "check-leakage printed nothing"
    for line in lines:
        redacted = _redact(line)
        assert redacted in text, f"the finding does not quote the line {redacted!r}"
        raw_label = _TRAINED_ON.search(line)
        if raw_label is not None:
            label = raw_label.group(0)[len("trained on ") :]
            assert label not in text, "the finding quotes the label it says it redacted"

    counts = re.search(r"(\d+) of (\d+) training examples touch a held-out task", lines[0])
    assert counts is not None, f"the first line carries no counts: {lines[0]!r}"
    leaked, total = int(counts.group(1)), int(counts.group(2))
    assert f"{leaked} of its {total} training examples" in text
    assert f"{total - leaked} of the {total}" in text

    recorded = json.loads(provenance.read_text(encoding="utf-8"))["dataset_digest"]
    digest = json.loads(dataset.read_text(encoding="utf-8"))["digest"]
    assert recorded == digest, "the adapter's recorded dataset digest is not night-001's"
    assert digest[:12] in text, "the finding does not quote the dataset digest"
