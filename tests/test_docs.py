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

P1 slice 1 added a second class of guard, because the cheat table in `docs/ROADMAP.md` § 3 is
not prose about the code — it is a **claim about what the reward catches**, and the corpus in
`tests/adversarial/` is the evidence for it. Those two can drift apart in either direction and
both directions are expensive:

- A cheat tested but missing from the table is coverage nobody reading the roadmap knows about.
- **A cheat listed as *Killed* whose fixture says otherwise is the failure this project exists
  to refuse** — a document overclaiming a defence, in the one repository whose premise is not
  fooling yourself.

So `tests/adversarial/corpus.py`'s `CHEATS` is imported here and the table is checked against
it, ids and residual-status both. The document does not get to be more confident than the code.

These assert on specific substrings rather than whole files, so ordinary editing does not
break them. Each check is paired with a positive control: a test that reads a file and finds
nothing has proven nothing, so every guard below also asserts the corrected text is present.
"""

from __future__ import annotations

import re
from pathlib import Path

from adversarial.corpus import BOTH_ACCEPT, CHEATS

# A concrete working branch, e.g. `feat/p0-scaffold/aliz`. The angle-bracket template
# `<type>/<id>/aliz` that documents the naming convention deliberately does not match.
CONCRETE_BRANCH = re.compile(r"\b(?:feat|bug|chore|task)/[a-z0-9][a-z0-9-]*/aliz\b")

REPO_ROOT = Path(__file__).parent.parent

# Claims that were true before the roadmap was written and are false now. Each was found in
# the deep dig recorded at docs/planning/_card/understanding.md § 5G and § 5H.
STALE_CLAUDE_CLAIMS = [
    "Nothing is built yet",
    "Ollama / vLLM / transformers",
    "Reuse Belay's verifier/replay where it fits",
    # Was true until P1 slice 1 landed the reward path. Left here rather than deleted: the
    # sentence is the one a reader would act on by rebuilding `src/whetstone/verify/`.
    "there is no verifier, no reward",
]


def _read(name: str) -> str:
    path = REPO_ROOT / name
    text = path.read_text(encoding="utf-8")
    assert text.strip(), (
        f"{name} is empty, so every guard in this module would pass vacuously. "
        "A substring absent from an empty file proves nothing."
    )
    return text


def _flat(text: str) -> str:
    """Collapse whitespace and blockquote markers, so a guard survives a re-wrap.

    Every prose claim below is asserted against this form. Asserting on the raw text would
    make each guard a line-length guard as well, and the first re-wrap would fail tests that
    have nothing to do with the claim they protect. The `> ` prefixes go for the same reason:
    several of the sentences guarded here live in blockquotes, where the marker lands
    mid-sentence on every continuation line.
    """
    lines = [
        line.lstrip(">").strip() if line.lstrip().startswith(">") else line
        for line in text.splitlines()
    ]
    return " ".join(" ".join(lines).split())


def _section(text: str, heading: str) -> str:
    """The body of one `## ` section, so a claim is checked where it was made.

    A substring found anywhere in a 400-line document is weak evidence: the cheat table's
    wording could be deleted from § 3 and coincidentally satisfied by a sentence in § 7. The
    slice is the difference between "the document says this" and "this section says this".
    """
    marker = f"## {heading}"
    start = text.index(marker)
    rest = text.index("\n## ", start + len(marker))
    return text[start:rest]


def _cheat_rows(roadmap: str) -> dict[int, str]:
    """The cheat table as `{id: status cell}`, parsed out of § 3 and nowhere else.

    Scoped to the section so no other four-column table in the document can supply a row and
    make the completeness check below pass on a table that is not this one.
    """
    rows: dict[int, str] = {}
    for line in _section(roadmap, "3. The cheat surface").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[0].isdigit():
            rows[int(cells[0])] = cells[3]
    return rows


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
    for expected in ("mlx-lm", "ROADMAP.md", "src/whetstone/verify/"):
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


def test_claude_md_does_not_pin_its_status_to_a_working_branch() -> None:
    """Staleness as a category, not as three specific strings.

    The other guards here name particular stale claims, which only ever catches the mistakes
    already made. This catches the mistake that keeps being made: a status block that
    describes work in flight on a named branch is stale the instant that branch merges, and
    the branch is then deleted, so the reference dangles too.

    That is not hypothetical. `CLAUDE.md` was corrected during the P0 cycle to say "P0
    scaffolding is in progress on feat/p0-scaffold/aliz ... nothing from it has landed on
    master" — and both halves were false within the hour, once the PR merged and the branch
    was deleted. Describe `master`; leave in-flight work to the PR.
    """
    text = _read("CLAUDE.md")
    offenders = sorted(set(CONCRETE_BRANCH.findall(text)))
    assert not offenders, (
        f"CLAUDE.md names concrete working branch(es): {offenders}\n\n"
        "WHY THIS IS A FAILURE: CLAUDE.md:3 tells every agent to read this file first, so it "
        "must describe what is true of `master`. A named working branch is transient — it "
        "merges and is deleted — so any claim attached to one expires without anyone editing "
        "the file, and the next agent reads a confident statement about a branch that no "
        "longer exists.\n"
        "Documenting the *convention* is fine: the `<type>/<id>/aliz` template does not match "
        "this pattern. Naming an actual branch is what fails."
    )


def test_the_roadmap_cheat_table_lists_every_cheat_the_corpus_actually_tests() -> None:
    """The table is a claim; `tests/adversarial/` is the evidence. They must not drift.

    Four of the ten entries were found after the original six-row table was believed to
    enumerate the surface, so drift here is the normal case rather than the exotic one. A
    cheat with a fixture but no row is coverage no reader knows about; a row whose fixture was
    deleted is the corpus shrinking silently, which `test_cheats.py`'s own completeness
    control catches from the other side.
    """
    rows = _cheat_rows(_read("docs/ROADMAP.md"))

    assert rows, (
        "no cheat rows parsed out of docs/ROADMAP.md § 3, so every assertion below would pass "
        "vacuously. Either the table moved out of that section or its shape changed."
    )
    assert set(rows) == set(CHEATS), (
        f"tested but unlisted: {sorted(set(CHEATS) - set(rows))}; "
        f"listed but untested: {sorted(set(rows) - set(CHEATS))}"
    )


def test_no_cheat_the_corpus_says_gets_through_is_recorded_as_killed() -> None:
    """A document claiming a defence the fixtures say is absent is the worst failure here.

    Both directions are asserted. A residual marked *Killed* overclaims — the thing this
    project exists to refuse. A killed cheat marked *RESIDUAL* understates, which is cheaper
    but still false, and leaving it unasserted would let the whole table decay to `RESIDUAL`
    and still pass.
    """
    rows = _cheat_rows(_read("docs/ROADMAP.md"))
    residuals = {
        cheat_id for cheat_id, cheat in CHEATS.items() if cheat.differential == BOTH_ACCEPT
    }

    assert residuals, "the corpus records no residual, which is a stronger claim than we make"
    for cheat_id, cheat in CHEATS.items():
        status = rows[cheat_id]
        if cheat_id in residuals:
            assert "RESIDUAL" in status, (
                f"cheat {cheat_id} ({cheat.summary}) is accepted by BOTH verifiers in "
                f"tests/adversarial/, and docs/ROADMAP.md records it as {status!r}. The "
                f"document is claiming a defence the code says is not there."
            )
        else:
            assert "Killed" in status, (
                f"cheat {cheat_id} ({cheat.summary}) is refused by STRICT in "
                f"tests/adversarial/, and docs/ROADMAP.md records it as {status!r}."
            )


def test_the_roadmap_does_not_present_the_cheat_enumeration_as_complete() -> None:
    """Cheat 7 was found by critiquing a PRD; 8, 9 and 10 by building the thing.

    The table therefore has a history of being wrong in the same direction, and the wording
    that says so is load-bearing rather than decorative — a reader who takes the list as
    exhaustive stops looking, which is exactly how cheats 8 to 10 survived being written down.
    """
    section = _flat(_section(_read("docs/ROADMAP.md"), "3. The cheat surface"))
    for expected in ("provisional", "append-only", "never describe it as exhaustive"):
        assert expected in section, (
            f"docs/ROADMAP.md § 3 no longer says {expected!r}. Without it the table reads as a "
            "closed enumeration of the reward-hacking surface, which it has never been."
        )


def test_the_roadmap_verifier_spec_asserts_the_executed_set_not_only_the_exit_status() -> None:
    """AC 1b / M2b. The correction that was a hole in the reward rather than documentation drift.

    Losing this from § 2 would leave the spec describing a check — exit status plus a zero
    skipped count — that cheat 7 defeats while satisfying every line of it. The reason is
    asserted alongside the mechanism, because the mechanism without "deselection is not
    skipping" reads as belt-and-braces and gets dropped as redundant.
    """
    section = _flat(_section(_read("docs/ROADMAP.md"), "2. The verifier"))
    for expected in (
        "EXECUTED node-id set == fail_to_pass + pass_to_pass",
        "Deselection is not skipping",
        "machine-readable report",
    ):
        assert expected in section, f"docs/ROADMAP.md § 2 no longer says {expected!r}"


def test_the_roadmap_states_both_bounds_on_what_the_verifier_guarantees() -> None:
    """The guarantee is bounded twice, and § 3 said neither until P1 corrected it.

    It once read *"the verifier guarantees that the tests genuinely pass on unmodified
    tests"*, qualified only by "the fix may not generalise". Two bounds were missing: the
    boundary is exactly as wide as `test_blobs` (cheat 10), and the sandbox confines writes
    but **not reads**, so the policy can see the assertions it must satisfy. Both were
    observed, not theorised — the read finding is in `understanding.md` § 2c and the manifest
    finding is `test_cheat_10_...` in the corpus.
    """
    section = _flat(_section(_read("docs/ROADMAP.md"), "3. The cheat surface"))
    for expected in (
        "as far as the manifest is complete",
        "confines what the run can write, **not** what it can read",
        "task ingestion",
    ):
        assert expected in section, (
            f"docs/ROADMAP.md § 3 no longer states the bound {expected!r}. An unbounded "
            "guarantee is an overclaim, and this one is the project's central claim."
        )


def test_the_roadmap_records_the_sandbox_it_took_from_belay() -> None:
    """§ 7 listed no sandbox while § 2 requires one — the gap that hid a real decision.

    The decision worth recording is not "we sandbox" but that Seatbelt was verified separable
    from the replay substrate § 7 declines: replay depends on the sandbox, never the reverse.
    Without that sentence a future reader re-opens a question that was already answered, or
    assumes declining replay cost us the sandbox too.
    """
    section = _flat(_section(_read("docs/ROADMAP.md"), "7. What we take from Belay"))
    assert "sandbox/seatbelt.py" in section, (
        "docs/ROADMAP.md § 7's Taken table no longer carries a sandbox row, while § 2 still "
        "requires the verifier to run with the network denied."
    )
    assert "Replay depends on the sandbox; the sandbox never depends on replay" in section, (
        "the separability finding is gone from § 7, so the row no longer says why taking the "
        "sandbox is consistent with declining the replay substrate."
    )


def test_the_relative_import_porting_trap_is_recorded_with_the_others() -> None:
    """Trap 3. Invisible in Belay's guard, and fatal in ours for a structural reason.

    Belay's AST walk skips `ImportFrom` nodes with a non-zero level, so relative imports
    record nothing. Belay survives it because its first-party detection keys on the dotted
    `belay.judge` form that only an absolute import produces. Our reward path is one package
    whose modules import each other relatively, so `from .judge import score` — the exact
    import the guard exists to catch, written the way our own code writes imports — would have
    sailed through a verbatim port.
    """
    text = _flat(_read("docs/ROADMAP.md"))
    assert "node.level == 0" in text, (
        "docs/ROADMAP.md no longer records the relative-import porting trap. It documents two "
        "traps that were caught by reading Belay's source; this is the third, and it is the "
        "one that would have left the guard green while watching nothing."
    )


def test_the_platform_decision_carries_its_clonefile_correction() -> None:
    """`docs/planning/roadmap-and-task-family/prd.md` decision 2 is half right, and says so.

    *"Belay's Seatbelt sandbox and APFS `clonefile` snapshot work natively; no porting phase
    required"* holds for Seatbelt and not for `clonefile`: the snapshot machinery is part of
    the replay substrate `docs/ROADMAP.md` § 7 declines. The row is left standing with a
    correction rather than rewritten, so the record shows what was decided and what it got
    wrong — and this guard is what stops the correction being tidied away later, leaving the
    original claim reading as though it had always been right.
    """
    text = _read("docs/planning/roadmap-and-task-family/prd.md")
    assert "clonefile" in text, (
        "the claim this guard protects has vanished from the PRD; if the row was rewritten "
        "rather than corrected, the record of the mistake went with it."
    )
    assert text.count("[†]") >= 2, (
        "decision 2's correction marker is gone. The uncorrected row states that Belay's "
        "APFS snapshot machinery works natively and needs no porting, which implies we "
        "inherited a snapshot layer that § 7 declines and this repository does not use."
    )
    assert "Correction, 2026-07-28" in text


def test_readme_does_not_claim_the_repo_is_greenfield() -> None:
    """The front door contradicted CLAUDE.md until this branch corrected it."""
    text = _read("README.md")
    assert "Nothing is built yet" not in text, (
        "README.md still claims nothing is built. It is the repo's front door and the "
        "first thing a visitor reads; leaving it stale reintroduces exactly the "
        "contradiction with CLAUDE.md that this branch removed."
    )
