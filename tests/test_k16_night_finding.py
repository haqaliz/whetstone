"""Guards over the K = 16 night's finding, so its quoted counts cannot drift from its ledger.

`docs/planning/k16-night/finding.md` records what the operator run did. A finding is a
quotation of its ledger, and a quotation is only honest while it still equals what the ledger
says, so:

- **Offline**, the pure helper `check_finding` is proven against fixture dicts: a finding whose
  quoted numbers match the ledger passes, and a finding that quotes a wrong count, a wrong
  held-out digest, a draw budget that is not `sampling.K`, or a gate verdict it did not get is
  refused by a named `FindingDisagrees` that carries the disagreeing key and both values.
- **Live**, when the primary checkout's gitignored artefacts exist, the finding's declared
  `**Run:**` path is read back through `ledger.verify_document` (v3 sealed), its held-out digest
  is checked against the committed document through `heldout.document_digest_of`, and — if the
  block names a checkpoint — `sft.verify_checkpoint` re-hashes the candidate. When the finding is
  absent, still the template, or the primary holds no such run, the test **skips loudly, naming
  the artefact**: it never passes silently.

The primary checkout is found from git (`--git-common-dir`), never from a literal path, because a
worktree holds none of the gitignored data — the same helper shape as
`tests/test_gate_leakage_finding.py`.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from whetstone.loop import heldout, ledger, sampling, sft

ROOT = Path(__file__).resolve().parents[1]

#: The finding the operator commits after the night, and the committed held-out document whose
#: digest the finding must quote.
FINDING_RELATIVE = Path("docs/planning/k16-night/finding.md")
TEMPLATE = ROOT / "docs" / "planning" / "k16-night" / "finding-template.md"
HELDOUT_DOCUMENT = ROOT / "tasks" / "heldout" / "source-b.json"

#: The seven sections the finding precedent carries; the template and the real finding both hold
#: them, in this order.
SECTIONS = (
    "## 1. What was run",
    "## 2. The decision",
    "## 3. The counts",
    "## 4. The held-out confound",
    "## 5. The control arm",
    "## 6. What is not claimed",
    "## 7. The next unit",
)

#: The committed held-out document's digest (`tasks/heldout/source-b.json`), recomputed live when
#: the primary is read; this constant is the fixed fixture value the offline tests pin.
HELDOUT_DIGEST = "6b5fbd49e5d20fada7c53c53d5076cf846210ea6a4522046e1ba025142e9980d"

#: The exact keys the evidence block must carry — no more, no fewer.
EVIDENCE_KEYS = (
    "run",
    "probe",
    "draws",
    "heldout_document_digest",
    "denominator",
    "selected",
    "unverified",
    "coverage",
    "checkpoint",
)

#: A template value: a finding still carrying one has not been filled in, so the live guard skips
#: loudly rather than comparing a placeholder against a real ledger.
PLACEHOLDER = "TO-BE-FILLED"

#: The gate's verdict words. A finding with no checkpoint did not run the gate, so naming one of
#: these is a claim it did not get.
GATE_VERDICTS = ("promoted", "rejected")

_RUN_LINE = re.compile(r"^\*\*Run:\*\*\s*`([^`]+)`", re.MULTILINE)
_PROBE_LINE = re.compile(r"^\*\*Probe:\*\*\s*`([^`]+)`", re.MULTILINE)
_JSON_BLOCK = re.compile(r"```json\n(.*?)\n```", re.DOTALL)


class FindingDisagrees(AssertionError):
    """A finding quotes a value its ledger does not carry, or claims a gate it did not run.

    Carries the disagreeing `key` and both values so a reader sees *what* moved without opening
    the ledger, and so the offline tests can pin which comparison fired.
    """

    def __init__(self, key: str, expected: object, got: object) -> None:
        super().__init__(
            f"the finding's {key!r} disagrees with the run: the finding says {got!r}, "
            f"the ledger says {expected!r}"
        )
        self.key = key
        self.expected = expected
        self.got = got


def _declared_run(finding: str) -> str:
    """The path on the `**Run:**` line — the finding's own declaration of what it quotes."""
    match = _RUN_LINE.search(finding)
    if match is None:
        raise FindingDisagrees("run", "a `**Run:**` line naming runs/nights/<id>", None)
    return match.group(1).strip()


def _evidence_block(finding: str) -> dict[str, Any]:
    """The first fenced `json` block, parsed; a missing or malformed block is a named refusal."""
    match = _JSON_BLOCK.search(finding)
    if match is None:
        raise FindingDisagrees("evidence", "one fenced ```json block", None)
    try:
        block = json.loads(match.group(1))
    except ValueError as error:
        raise FindingDisagrees("evidence", "a parsable ```json block", str(error)) from error
    if not isinstance(block, dict):
        raise FindingDisagrees("evidence", "a JSON object", type(block).__name__)
    return block


def check_finding(
    finding: str,
    ledger: Mapping[str, Any],
    committed_heldout_digest: str,
    *,
    expected_draws: int = sampling.K,
) -> None:
    """Refuse a finding whose quoted counts are not the ledger's, or whose budget is not `K`.

    Pure and stdlib-only: the finding text and the parsed ledger are the only inputs, so the
    refusal path is provable offline. The seven ledger-backed values are compared by identity to
    the ledger's own fields; `run` is compared to the finding's declared `**Run:**` line; `probe`
    is a declared path, not a ledger count, so it is compared to the optional `**Probe:**` line
    and otherwise shape-checked. A `draws` that is not `expected_draws` is refused even when the
    ledger agrees with it, because `K` is the pre-committed budget and not the run's own claim.
    """
    declared_run = _declared_run(finding)
    block = _evidence_block(finding)

    expected_run = f"runs/nights/{ledger['run_id']}"
    if declared_run != expected_run:
        raise FindingDisagrees("run", expected_run, declared_run)

    missing = sorted(set(EVIDENCE_KEYS) - set(block))
    extra = sorted(set(block) - set(EVIDENCE_KEYS))
    if missing or extra:
        raise FindingDisagrees("keys", list(EVIDENCE_KEYS), sorted(block))

    if block["draws"] != expected_draws:
        raise FindingDisagrees("draws", expected_draws, block["draws"])

    task_set = ledger["task_set"]
    heldout = task_set.get("heldout") if isinstance(task_set, Mapping) else None
    ledger_digest = heldout.get("document_digest") if isinstance(heldout, Mapping) else None
    if ledger_digest != committed_heldout_digest:
        raise FindingDisagrees("heldout_document_digest", committed_heldout_digest, ledger_digest)

    declared_probe = _PROBE_LINE.search(finding)
    if declared_probe is not None and block["probe"] != declared_probe.group(1).strip():
        raise FindingDisagrees("probe", declared_probe.group(1).strip(), block["probe"])
    if not isinstance(block["probe"], str) or not block["probe"].strip():
        raise FindingDisagrees("probe", "a runs/night-probe/<id> path", block["probe"])

    dataset = ledger["dataset"]
    checkpoint = ledger["checkpoint"]
    expected: dict[str, Any] = {
        "run": declared_run,
        "draws": ledger["draws"],
        "heldout_document_digest": committed_heldout_digest,
        "denominator": dataset["denominator"],
        "selected": dataset["examples"],
        "unverified": dataset["unverified"],
        "coverage": dataset["coverage"],
        "checkpoint": checkpoint["digest"],
    }
    for key, want in expected.items():
        if block[key] != want:
            raise FindingDisagrees(key, want, block[key])

    if block["checkpoint"] is None:
        for word in GATE_VERDICTS:
            if re.search(rf"\b{word}\b", finding, re.IGNORECASE):
                raise FindingDisagrees(
                    "checkpoint",
                    "no gate verdict without a checkpoint",
                    f"the finding says {word!r}",
                )


def _primary() -> Path:
    """The primary checkout, found from git's common dir — a worktree holds none of the data."""
    try:
        common = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        pytest.skip(
            "SKIPPED LOUDLY: git could not name the primary checkout, so the K = 16 night's "
            f"finding cannot be re-checked against its gitignored run ({error})"
        )
    return Path(common).parent


def _ledger(
    *,
    run_id: str = "night-002",
    draws: int = 16,
    heldout_digest: str = HELDOUT_DIGEST,
    denominator: int = 52,
    examples: int = 0,
    unverified: int = 12,
    coverage: str = "0/52",
    checkpoint_digest: str | None = None,
) -> dict[str, Any]:
    """A fixture ledger document, shaped like `whetstone-run/3` for the keys the finding quotes."""
    return {
        "run_id": run_id,
        "draws": draws,
        "task_set": {"heldout": {"document_digest": heldout_digest, "membership_count": 7}},
        "dataset": {
            "denominator": denominator,
            "examples": examples,
            "unverified": unverified,
            "coverage": coverage,
        },
        "checkpoint": {"digest": checkpoint_digest, "absent": None},
    }


def _finding(
    *,
    run: str = "runs/nights/night-002",
    probe: str = "runs/night-probe/probe-002",
    draws: int = 16,
    heldout_digest: str = HELDOUT_DIGEST,
    denominator: int = 52,
    selected: int = 0,
    unverified: int = 12,
    coverage: str = "0/52",
    checkpoint: str | None = None,
    prose: str = "",
) -> str:
    """A fixture finding: the declared `**Run:**` line and one fenced `json` evidence block."""
    block = {
        "run": run,
        "probe": probe,
        "draws": draws,
        "heldout_document_digest": heldout_digest,
        "denominator": denominator,
        "selected": selected,
        "unverified": unverified,
        "coverage": coverage,
        "checkpoint": checkpoint,
    }
    return (
        "# Finding — the K = 16 night\n\n"
        f"**Run:** `{run}`\n\n"
        "## 1. What was run\n\nIt ran once.\n\n"
        "```json\n" + json.dumps(block, indent=2) + "\n```\n\n" + prose + "\n"
    )


def test_a_matching_finding_passes() -> None:
    check_finding(_finding(), _ledger(), HELDOUT_DIGEST)


def test_a_wrong_selected_count_is_refused() -> None:
    with pytest.raises(FindingDisagrees) as error:
        check_finding(_finding(selected=1), _ledger(), HELDOUT_DIGEST)
    assert error.value.key == "selected"


def test_a_wrong_heldout_digest_is_refused() -> None:
    with pytest.raises(FindingDisagrees) as error:
        check_finding(_finding(heldout_digest="a" * 64), _ledger(), HELDOUT_DIGEST)
    assert error.value.key == "heldout_document_digest"


def test_a_draws_value_that_is_not_sampling_K_is_refused() -> None:
    with pytest.raises(FindingDisagrees) as error:
        check_finding(_finding(draws=sampling.K - 1), _ledger(draws=sampling.K - 1), HELDOUT_DIGEST)
    assert error.value.key == "draws"


def test_a_finding_that_names_a_gate_verdict_without_a_checkpoint_is_refused() -> None:
    with pytest.raises(FindingDisagrees) as error:
        check_finding(_finding(prose="The gate promoted the candidate."), _ledger(), HELDOUT_DIGEST)
    assert error.value.key == "checkpoint"


def test_the_template_carries_the_seven_sections_and_a_placeholder_block() -> None:
    """The template must agree with the guard, so a copy of it cannot read as a filled finding."""
    assert TEMPLATE.is_file(), f"the finding template is absent: {TEMPLATE.relative_to(ROOT)}"
    text = TEMPLATE.read_text(encoding="utf-8")
    positions = []
    for heading in SECTIONS:
        assert heading in text, f"the template lacks the section {heading!r}"
        positions.append(text.index(heading))
    assert positions == sorted(positions), "the seven sections are out of order"
    block = _evidence_block(text)
    assert set(block) == set(EVIDENCE_KEYS), "the template's block does not carry the nine keys"
    for key, value in block.items():
        assert isinstance(value, str) and PLACEHOLDER in value, (
            f"the template's {key!r} is not a placeholder, so the live guard would not skip it"
        )


def test_the_real_finding_matches_the_real_run() -> None:
    """The live guard: skip loudly until the operator's night and finding exist.

    Offline the helper is proven against fixtures; here the real finding is read back against
    the primary checkout's gitignored ledger through the same helper. Every absent artefact — the
    finding, its declared run, or the committed held-out document — is a loud skip that names it,
    and a template finding is never compared as if it were filled in.
    """
    primary = _primary()
    finding_path = primary / FINDING_RELATIVE
    if not finding_path.is_file():
        pytest.skip(
            "SKIPPED LOUDLY: the K = 16 night has not run, so its finding is absent "
            f"({FINDING_RELATIVE.as_posix()} in the primary checkout {primary})"
        )
    finding = finding_path.read_text(encoding="utf-8")
    present = [finding.index(heading) for heading in SECTIONS if heading in finding]
    assert len(present) == len(SECTIONS) and present == sorted(present), (
        "the finding does not carry its seven sections, in order"
    )
    block = _evidence_block(finding)
    placeholders = sorted(k for k, v in block.items() if isinstance(v, str) and PLACEHOLDER in v)
    if placeholders:
        pytest.skip(
            "SKIPPED LOUDLY: the K = 16 night's finding is still its unfilled template — "
            f"{', '.join(placeholders)} carry {PLACEHOLDER!r}"
        )
    if not HELDOUT_DOCUMENT.is_file():
        pytest.skip(
            "SKIPPED LOUDLY: the committed held-out document is absent, so the finding's digest "
            f"cannot be re-checked ({HELDOUT_DOCUMENT})"
        )
    run_directory = primary / _declared_run(finding)
    ledger_path = run_directory / "ledger.json"
    if not ledger_path.is_file():
        pytest.skip(
            "SKIPPED LOUDLY: the K = 16 night's finding declares a run the primary checkout "
            f"does not hold ({ledger_path})"
        )
    verified = ledger.verify_document(ledger_path)
    committed = heldout.document_digest_of(
        json.loads(HELDOUT_DOCUMENT.read_text(encoding="utf-8"))
    )
    check_finding(finding, verified.document, committed)

    digest = block["checkpoint"]
    if digest is not None:
        checkpoint = sft.verify_checkpoint(primary / "checkpoints" / run_directory.name)
        assert checkpoint.digest == digest, (
            "the finding quotes a checkpoint digest the primary's checkpoint does not re-hash to"
        )
