"""Guards over the orienting documents, so a stale claim cannot quietly survive.

`CLAUDE.md:3` instructs every agent to read it first, and `docs/ROADMAP.md` is the
authoritative technical plan until `docs/technical/ARCHITECTURE.md` exists. Both were
corrected in this branch after the dig found them misleading. A correction nobody tests is a
correction that regresses the next time someone edits around it — and the specific regressions
here are expensive:

- A reader who believes "nothing is built yet" re-does work that exists.
- A reader who believes the runtime is Ollama/vLLM/transformers builds against the wrong stack.
- A reader who believes Belay's replay substrate is being reused inherits a design the roadmap
  spent four reasons declining.
- **Worst:** a reader who believes the inference guard lives in `test_import_guard.py` ports
  the wrong file into P1. In Belay that name bans `mcp`, non-stdlib imports, and `json` in
  `proxy.py` — nothing to do with inference. The guard that keeps models off the reward path
  is `test_verify_zero_llm.py`. P1 is the moat, and it would be built on the wrong guard.

These assert on specific substrings rather than whole files, so ordinary editing does not
break them. Each check is paired with a positive control: a test that reads a file and finds
nothing has proven nothing, so every guard below also asserts the corrected text is present.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# Claims that were true before the roadmap was written and are false now. Each was found in
# the deep dig recorded at docs/planning/_card/understanding.md § 5G and § 5H.
STALE_CLAUDE_CLAIMS = [
    "Nothing is built yet",
    "Ollama / vLLM / transformers",
    "Reuse Belay's verifier/replay where it fits",
]


def _read(name: str) -> str:
    path = REPO_ROOT / name
    text = path.read_text(encoding="utf-8")
    assert text.strip(), (
        f"{name} is empty, so every guard in this module would pass vacuously. "
        "A substring absent from an empty file proves nothing."
    )
    return text


def test_claude_md_carries_none_of_the_stale_claims() -> None:
    """AC-12. Each of these misdirects an agent that was told to read this file first."""
    text = _read("CLAUDE.md")
    survivors = [claim for claim in STALE_CLAUDE_CLAIMS if claim in text]
    assert not survivors, (
        f"CLAUDE.md still contains stale claim(s): {survivors}\n\n"
        "WHY THIS IS A FAILURE: CLAUDE.md:3 tells every coding agent to read this file "
        "first. A stale claim here is not a documentation nit — it is an instruction to "
        "build the wrong thing. 'Nothing is built yet' invites redoing shipped work; the "
        "Ollama/vLLM/transformers line points at a runtime the PRD replaced with MLX; and "
        "the 'reuse Belay's replay' line contradicts ROADMAP.md § 7, which declines that "
        "substrate for four stated reasons."
    )


def test_claude_md_states_what_replaced_the_stale_claims() -> None:
    """Positive control for the guard above.

    Absence is not correctness: deleting CLAUDE.md's body would satisfy the previous test.
    This asserts the corrected content is actually present.
    """
    text = _read("CLAUDE.md")
    for expected in ("mlx-lm", "ROADMAP.md"):
        assert expected in text, (
            f"CLAUDE.md no longer mentions {expected!r}. The stale-claim guard checks for "
            "absence, so a gutted file would pass it — this control is what stops that."
        )


def test_roadmap_does_not_cite_the_wrong_belay_guard() -> None:
    """AC-11. Naming the wrong file here means P1 ports the wrong guard."""
    text = _read("docs/ROADMAP.md")
    assert "test_import_guard.py" not in text, (
        "docs/ROADMAP.md still cites `test_import_guard.py`.\n\n"
        "WHY THIS IS A FAILURE: in Belay that file bans the `mcp` package, all non-stdlib "
        "imports, and `json` inside proxy.py. It has nothing to do with inference "
        "libraries. The guard that proves no model sits on the reward path is "
        "`test_verify_zero_llm.py`, and it is scoped to named packages rather than the "
        "whole tree. P1 builds the moat on this guard; citing the wrong filename means "
        "building it on the wrong invariant."
    )


def test_roadmap_names_the_correct_inference_guard() -> None:
    """Positive control for AC-11, and the reason the correction was worth making."""
    text = _read("docs/ROADMAP.md")
    assert "test_verify_zero_llm.py" in text, (
        "docs/ROADMAP.md no longer names Belay's actual inference guard. The check above "
        "only asserts an absence; without this, deleting the whole section would pass it."
    )


def test_readme_does_not_claim_the_repo_is_greenfield() -> None:
    """The front door contradicted CLAUDE.md until this branch corrected it."""
    text = _read("README.md")
    assert "Nothing is built yet" not in text, (
        "README.md still claims nothing is built. It is the repo's front door and the "
        "first thing a visitor reads; leaving it stale reintroduces exactly the "
        "contradiction with CLAUDE.md that this branch removed."
    )
