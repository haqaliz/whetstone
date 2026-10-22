"""Guards over the orienting documents, so a stale claim cannot quietly survive.

`CLAUDE.md:3` instructs every agent to read it first, and `docs/ROADMAP.md` is the
authoritative technical plan until `docs/technical/ARCHITECTURE.md` exists. Both were
corrected in this branch after the dig found them misleading. A correction nobody tests is a
correction that regresses the next time someone edits around it — and the specific regressions
here are expensive:

- A reader who believes "nothing is built yet" re-does work that exists.
- A reader who believes the runtime is Ollama/vLLM/transformers builds against the wrong stack.
- A reader who believes the sibling project's replay substrate is being reused inherits a design
  the roadmap spent four reasons declining.
- **Worst:** a reader who believes the inference guard lives in `test_import_guard.py` ports
  the wrong file into P1. In the sibling project that name bans `mcp`, non-stdlib imports, and
  `json` in `proxy.py` — nothing to do with inference. The guard that keeps models off the reward
  path is `test_verify_zero_llm.py`. P1 is the moat, and it would be built on the wrong guard.

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
import subprocess
from pathlib import Path

import pytest
from adversarial.corpus import BOTH_ACCEPT, CHEATS
from test_night_runbook_guards import RETAINED

from whetstone.bakeoff import sources
from whetstone.loop import heldout, sampling, torch_runtime

# A concrete working branch, e.g. `feat/p0-scaffold/aliz`. The angle-bracket template
# `<type>/<id>/aliz` that documents the naming convention deliberately does not match.
CONCRETE_BRANCH = re.compile(r"\b(?:feat|bug|chore|task)/[a-z0-9][a-z0-9-]*/aliz\b")

REPO_ROOT = Path(__file__).parent.parent

# Claims that were true before the roadmap was written and are false now. Each was found in
# the deep dig recorded at docs/planning/_card/understanding.md § 5G and § 5H.
STALE_CLAUDE_CLAIMS = [
    "Nothing is built yet",
    "Ollama / vLLM / transformers",
    "Reuse the sibling project's verifier/replay where it fits",
    # Was true until P1 slice 1 landed the reward path. Left here rather than deleted: the
    # sentence is the one a reader would act on by rebuilding `src/whetstone/verify/`.
    "there is no verifier, no reward",
    # Was true until P1 slice 4 landed PREREGISTRATION.md. The status block listed the
    # bake-off and the pre-registration together as "both still open"; one of them is not.
    "both still open",
]

PREREGISTRATION = "PREREGISTRATION.md"

# The claim four documents made in the present tense, in every spelling they actually used.
# It was true until the bake-off ran; `reports/baseline/` now holds the numbers it denies.
NO_NUMBER_CLAIM = re.compile(
    r"no (?:number|figure) about a model exists"
    r"|not one number about a model exists"
    r"|no model has been run",
    re.IGNORECASE,
)

# The documents that describe the tree in the present tense, so a false claim in them is read
# as current. `PREREGISTRATION.md` is deliberately absent: it is append-only, and its § *Status
# at the time of writing* says of itself that every claim in it is checkable in the tree it was
# committed to, which makes it history by construction rather than a live assertion.
PRESENT_TENSE_DOCS = ("CLAUDE.md", "README.md", "CHANGELOG.md")

# Every section of the pre-registration, asserted one at a time so a document that lost one
# fails naming it. `_section()` is deliberately not used on this file: it slices to the next
# `\n## ` and raises on a document's final section.
PREREGISTRATION_SECTIONS = (
    "## What this is, and what it is not",
    "## Status at the time of writing",
    "## 1. The headline",
    "## 2. The metrics, defined before they are measured",
    "## 3. The baseline protocol",
    "## 4. How the result is reported",
    "## 5. Success, and what is not pre-registered",
    "## 6. Disclosed limitations",
    "## 7. Open at the time of writing",
    "## 8. The amendment rule",
    "## 9. Provenance",
)

# The sibling project's `PHASE0_RESULTS.md` carried `**TO-BE-FILLED**` for ten days; the rest
# are the spellings a hurried edit reaches for instead.
PLACEHOLDERS = ("TO-BE-FILLED", "TBD", "TODO", "FIXME", "XXX", "???", "_____")

# The four clauses of docs/ROADMAP.md § 6 (:478-488).
SECTION_6_CONTRACT = (
    "The private source (B) is the headline",
    "Both sources are always published together",
    "reported as a finding",
    "Public-gain-with-private-flat is the expected signature of contamination",
)

# What a reader must be told before the number, not after it. Each phrase is asserted on its
# own so a document carrying most of them fails naming the one it dropped.
DISCLOSURES = (
    ("source-B self-selection", "the author's own repos"),
    ("the refused `donor C` mitigation", "`donor C` was refused"),
    ("source A's corpus of one", "1 eligible instance of 300"),
    ("the two cheat residuals", "Cheats 6 and 10"),
    ("the sandbox's read bound", "not what it may read"),
    ("source B's data locality", "never leaves the box"),
    ("pre-registration's own limit", "not an independence control"),
)

# docs/ROADMAP.md:569-574 — genuinely undecided, and a guess here would be worse than the gap.
OPEN_ITEMS = (
    ("the held-out split", "held-out split size and stratification"),
    ("the retry count", "retry count `R`"),
    ("the open base", "Which open base"),
)

AMENDMENT_EXCEPTION = "may never introduce a success threshold"

# Every `docs/ROADMAP.md:START-END` citation the pre-registration makes, paired with text that
# must appear inside those exact lines. Five of these were wrong when first written: the same
# commit corrected a paragraph in § 4 and pushed everything after it down, so the citations
# named the wrong sections. Anchors, not line numbers, are what make the guard survive the
# next edit — a shifted section fails loudly here instead of misleading a reader silently.
ROADMAP_CITATIONS = (
    ("518", "528", "The private source (B) is the headline"),
    ("355", "356", "**`PREREGISTRATION.md` is committed**"),
    ("476", "477", "The headline matches what `PREREGISTRATION.md` committed to"),
    ("364", "368", "not one number about a model exists anywhere in this repository"),
    ("62", "72", "reward := exit status, folded with the assertions above"),
    ("106", "117", "N := count(rollouts where WEAK == PASS and STRICT == FAIL)"),
    ("504", "513", "Measured once, re-measured never"),
    ("480", "481", "A zero or negative delta is a valid, publishable outcome"),
    ("187", "190", "confines what the run can write, **not** what it can read"),
    ("609", "614", "The held-out split size and stratification"),
)


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


def _reports_without_preregistration(root: Path) -> list[str]:
    """Report files that exist in a tree holding no `PREREGISTRATION.md`, as sorted paths.

    Takes the root as an argument rather than closing over `REPO_ROOT` so it can be exercised
    against synthetic trees. `reports/` does not exist here today, so a guard hard-wired to
    this repository would pass without ever running its own logic.
    """
    if (root / PREREGISTRATION).is_file():
        return []
    reports = root / "reports"
    return sorted(
        path.relative_to(root).as_posix() for path in reports.rglob("*") if path.is_file()
    )


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
        "the 'reuse the sibling's replay' line contradicts ROADMAP.md § 7, which declines "
        "that substrate for four stated reasons."
    )


def test_claude_md_states_what_replaced_the_stale_claims() -> None:
    """Positive control for the guard above.

    Absence is not correctness: deleting CLAUDE.md's body would satisfy the previous test.
    This asserts the corrected content is actually present.
    """
    text = _read("CLAUDE.md")
    for expected in ("mlx-lm", "ROADMAP.md", "**STRICT** verifier"):
        assert expected in text, (
            f"CLAUDE.md no longer mentions {expected!r}. The stale-claim guard checks for "
            "absence, so a gutted file would pass it — this control is what stops that."
        )


def test_no_document_still_claims_that_no_number_about_a_model_exists() -> None:
    """The positive form of the stale-claim guard: the tree may not deny what it now holds.

    `reports/baseline/` exists, so every present-tense sentence saying no model has been run,
    or that no number about a model exists, is now false. `STALE_CLAUDE_CLAIMS` above names
    strings that went stale in earlier cycles; this names the *claim* — in every spelling the
    documents actually used — and asserts it survives only where it is marked as history.

    **`docs/ROADMAP.md` is checked differently, and deliberately.** `PREREGISTRATION.md` cites
    `docs/ROADMAP.md:364-368` on the exact sentence *"not one number about a model exists anywhere
    in this repository"*, and that file is **append-only**, so the sentence cannot be deleted or
    moved without breaking a citation a stranger is invited to check. It is therefore kept inside
    those lines as a dated, quoted correction — the precedent § 4 already sets for P4's claim about
    the sibling project — and this guard asserts the claim appears in the roadmap only inside a
    blockquote, never in the running prose. A correction that is quietly tidied away later leaves
    the original claim reading as though it had always been right.

    The blockquote half is also this test's anti-vacuity control: a repository that had simply
    deleted every trace of the sentence would satisfy the absence checks while breaking the
    citation guard below, and would prove nothing here.
    """
    for name in PRESENT_TENSE_DOCS:
        found = sorted(set(NO_NUMBER_CLAIM.findall(_flat(_read(name)))))
        assert not found, (
            f"{name} still claims, in the present tense, that no number about a model "
            f"exists: {found}\n\n"
            "WHY THIS IS A FAILURE: `reports/baseline/` holds the bake-off report, so the "
            "sentence is false about the tree it ships in. A document that denies the "
            "measurement it ships beside is the exact failure mode this repository exists to "
            "refuse, and CLAUDE.md:3 tells every agent to read one of these files first."
        )

    lines = _read("docs/ROADMAP.md").splitlines()
    prose = _flat("\n".join(line for line in lines if not line.lstrip().startswith(">")))
    quoted = _flat("\n".join(line for line in lines if line.lstrip().startswith(">")))

    assert not sorted(set(NO_NUMBER_CLAIM.findall(prose))), (
        "docs/ROADMAP.md asserts in running prose that no number about a model exists: "
        f"{sorted(set(NO_NUMBER_CLAIM.findall(prose)))}\n\n"
        "WHY THIS IS A FAILURE: the claim may stay in this file only as a quoted, dated "
        "correction, because PREREGISTRATION.md cites the lines it sits on and that document "
        "is append-only. Outside a blockquote it reads as present tense and is false."
    )
    assert NO_NUMBER_CLAIM.search(quoted), (
        "docs/ROADMAP.md no longer carries the falsified claim as a quotation anywhere.\n\n"
        "WHY THIS IS A FAILURE: the checks above assert absences, which deleting the sentence "
        "would satisfy — and deleting it would break PREREGISTRATION.md's citation of "
        "docs/ROADMAP.md:364-368 in an append-only document, leaving a reader pointed at "
        "lines that no longer say what they are cited for."
    )


def test_roadmap_does_not_cite_the_wrong_sibling_guard() -> None:
    """AC-11. Naming the wrong file here means P1 ports the wrong guard."""
    text = _read("docs/ROADMAP.md")
    assert "test_import_guard.py" not in text, (
        "docs/ROADMAP.md still cites `test_import_guard.py`.\n\n"
        "WHY THIS IS A FAILURE: in the sibling project that file bans the `mcp` package, all "
        "non-stdlib imports, and `json` inside proxy.py. It has nothing to do with inference "
        "libraries. The guard that proves no model sits on the reward path is "
        "`test_verify_zero_llm.py`, and it is scoped to named packages rather than the "
        "whole tree. P1 builds the moat on this guard; citing the wrong filename means "
        "building it on the wrong invariant."
    )


def test_roadmap_names_the_correct_inference_guard() -> None:
    """Positive control for AC-11, and the reason the correction was worth making."""
    text = _read("docs/ROADMAP.md")
    assert "test_verify_zero_llm.py" in text, (
        "docs/ROADMAP.md no longer names the sibling's actual inference guard. The check above "
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


def test_the_roadmap_records_the_sandbox_it_took_from_the_sibling() -> None:
    """§ 7 listed no sandbox while § 2 requires one — the gap that hid a real decision.

    The decision worth recording is not "we sandbox" but that Seatbelt was verified separable
    from the replay substrate § 7 declines: replay depends on the sandbox, never the reverse.
    Without that sentence a future reader re-opens a question that was already answered, or
    assumes declining replay cost us the sandbox too.
    """
    section = _flat(_section(_read("docs/ROADMAP.md"), "7. What we take from the sibling project"))
    assert "sandbox/seatbelt.py" in section, (
        "docs/ROADMAP.md § 7's Taken table no longer carries a sandbox row, while § 2 still "
        "requires the verifier to run with the network denied."
    )
    assert "Replay depends on the sandbox; the sandbox never depends on replay" in section, (
        "the separability finding is gone from § 7, so the row no longer says why taking the "
        "sandbox is consistent with declining the replay substrate."
    )


def test_the_relative_import_porting_trap_is_recorded_with_the_others() -> None:
    """Trap 3. Invisible in the sibling project's guard, and fatal in ours for a structural reason.

    The sibling project's AST walk skips `ImportFrom` nodes with a non-zero level, so relative
    imports record nothing. It survives that because its first-party detection keys on the dotted
    `<sibling>.judge` form that only an absolute import produces. Our reward path is one package
    whose modules import each other relatively, so `from .judge import score` — the exact import the
    guard exists to catch, written the way our own code writes imports — would have sailed through a
    verbatim port.
    """
    text = _flat(_read("docs/ROADMAP.md"))
    assert "node.level == 0" in text, (
        "docs/ROADMAP.md no longer records the relative-import porting trap. It documents two "
        "traps that were caught by reading the sibling's source; this is the third, and it is "
        "the one that would have left the guard green while watching nothing."
    )


def test_the_platform_decision_carries_its_clonefile_correction() -> None:
    """`docs/planning/roadmap-and-task-family/prd.md` decision 2 is half right, and says so.

    *"the sibling project's Seatbelt sandbox and APFS `clonefile` snapshot work natively; no
    porting phase required"* holds for Seatbelt and not for `clonefile`: the snapshot machinery is
    part of the replay substrate `docs/ROADMAP.md` § 7 declines. The row is left standing with a
    correction rather than rewritten, so the record shows what was decided and what it got wrong —
    and this guard is what stops the correction being tidied away later, leaving the original claim
    reading as though it had always been right.
    """
    text = _read("docs/planning/roadmap-and-task-family/prd.md")
    assert "clonefile" in text, (
        "the claim this guard protects has vanished from the PRD; if the row was rewritten "
        "rather than corrected, the record of the mistake went with it."
    )
    assert text.count("[†]") >= 2, (
        "decision 2's correction marker is gone. The uncorrected row states that the sibling's "
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


def test_the_readme_status_table_does_not_deny_what_is_built() -> None:
    """The front door's status table, checked against the tree rather than proof-read.

    This guard exists because the table was found carrying three live falsehoods at once while
    the morning-report unit was editing it: the never-regress promotion gate and the held-out
    split were listed under "Not built" months after P3 merged them, and the release row said
    *no tags, no PyPI package, no version* with v0.3.0 onward tagged and published.

    That is the same failure `CLAUDE.md` records against itself — *"This line read 'nothing has
    been published to PyPI' until 2026-08-20; it had been false since v0.3.0"* — and it recurred
    because nothing was checking. A README is the one file every visitor reads first and the one
    file nobody re-reads, so the check is mechanical.
    """
    text = _read("README.md")
    built = text.split("❌", 1)[1].split("|", 2)[1] if "❌" in text else ""

    for shipped in ("promotion gate", "held-out split"):
        assert shipped not in built.lower(), (
            f"WHY THIS IS A FAILURE: README's 'Not built' row still lists the {shipped}, which "
            "shipped in P3. A front door that under-reports the project is how a reader forms a "
            "wrong first impression that nothing later corrects."
        )

    tags = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "tag"],
        capture_output=True,
        text=True,
        check=False,
    )
    if tags.returncode != 0 or not tags.stdout.strip():
        pytest.skip("no tags reachable here (a shallow clone has none); nothing to compare")
    assert "No tags, no PyPI package, no version" not in text, (
        "WHY THIS IS A FAILURE: README claims nothing is released, and `git tag` lists "
        f"{sorted(tags.stdout.split())}. This exact sentence has been false once before and was "
        "corrected by PyPI's own index rather than by anyone reading it."
    )


def test_the_preregistration_exists_and_carries_its_sections() -> None:
    """P1 exit criterion 6, and the anti-vacuity floor for every guard below it.

    `docs/ROADMAP.md:481-482` requires this file committed *"in **P1**, before any number
    exists"*, and `:452-453` grades P4's published headline against it. A file that does not
    exist cannot be checked, and `_read` would raise `FileNotFoundError` rather than say why,
    so the existence assertion is made explicitly and first.

    The heading list is asserted one at a time rather than as a set, so a document that lost
    a single section fails naming that section. Every absence-guard below this one would pass
    on a gutted file; this is what stops that.
    """
    path = REPO_ROOT / PREREGISTRATION
    assert path.is_file(), (
        f"{PREREGISTRATION} does not exist.\n\n"
        "WHY THIS IS A FAILURE: it is P1 exit criterion 6, and its whole value is its commit "
        "date — docs/ROADMAP.md:481-482 requires it committed before any number exists, so "
        "that git history proves the headline rule was fixed before results were visible. "
        "Written after the bake-off it is not a commitment, it is a rationalisation."
    )
    text = _read(PREREGISTRATION)
    for heading in PREREGISTRATION_SECTIONS:
        assert heading in text, (
            f"{PREREGISTRATION} no longer carries the section {heading!r}.\n\n"
            "WHY THIS IS A FAILURE: the guards below assert content by substring, so a "
            "deleted section makes them pass on text that is simply gone. Each section "
            "carries one of the commitments P4 is graded against."
        )


def test_the_preregistration_contains_no_placeholder() -> None:
    """The failure this document exists to refuse, borrowed from the sibling that made it.

    The sibling project's `PHASE0_RESULTS.md` — the document gating PROCEED vs PIVOT — carried 20
    `TO-BE-FILLED` markers from 2026-07-19 to 2026-07-29. It was eventually filled, with a
    PIVOT, and published; but for ten days it read as a commitment while committing to
    nothing.

    **A pre-registration containing a blank is worse than no pre-registration**, because a
    reader takes the document's existence as evidence the question was settled. Everything
    here is decided at commit time, or named as open with the mechanism that closes it — and
    an open item named in § 7 is a commitment, while a blank is an IOU.
    """
    text = _read(PREREGISTRATION)
    found = [marker for marker in PLACEHOLDERS if marker in text]
    assert not found, (
        f"{PREREGISTRATION} contains placeholder(s): {found}\n\n"
        "WHY THIS IS A FAILURE: a pre-registration with a blank in it commits to nothing "
        "while reading as a commitment. Decide it now, or move it to § 7 as an open item "
        "with the amendment that closes it and the deadline it closes by."
    )


def test_the_preregistration_states_no_figure_about_a_model() -> None:
    """No model has been run, so any performance figure here would be invented.

    `docs/ROADMAP.md:364-368`: *"not one number about a model exists anywhere in this
    repository."* `CLAUDE.md:119`, quoted at `:595-596`: *"If you need a statistic that isn't
    here, do not invent one."* This document is written **before** the first measurement, so
    a figure in it could only be a target dressed as a result.

    The ban covers the word as well as the glyph. A guard that `%` alone would satisfy is
    evaded by writing "percent", and a rule that is trivially sidestepped buys false
    confidence — which `CONTRIBUTING.md:56-60` names as worse than no guard at all. The
    grounded external statistics this project may cite live in `docs/ROADMAP.md` § 11, which
    is the right place for them.

    The positive half is this test's own anti-vacuity control: deleting the file's body would
    satisfy the ban, so the document must also *state* the rule, proving it is deliberate
    rather than an accident of style.
    """
    text = _read(PREREGISTRATION)
    lowered = text.lower()
    found = [token for token in ("%", "percent", "percentage") if token in lowered]
    assert not found, (
        f"{PREREGISTRATION} states a proportion: {found}\n\n"
        "WHY THIS IS A FAILURE: this file is committed before the first measurement exists, "
        "so a proportion in it is either a target being smuggled in as a result or a number "
        "that leaked back from one. Report counts over their denominators; grounded external "
        "statistics belong in docs/ROADMAP.md § 11."
    )
    assert "no figure about a model" in _flat(text), (
        f"{PREREGISTRATION} no longer states its own no-figure rule. The check above asserts "
        "an absence, which an emptied file would satisfy; this is the control that stops it, "
        "and it is also what tells a reader the omission is deliberate."
    )


def test_the_preregistration_carries_the_roadmap_section_6_contract() -> None:
    """§ 6 is the contract this document discharges; these four clauses are all of it.

    `docs/ROADMAP.md:478-488`. Dropping any one of them re-opens the post-hoc selection the
    section exists to close — most of all the last, since a disagreement between the sources
    resolved by picking the flattering one is the precise failure two sources invite.
    """
    flat = _flat(_read(PREREGISTRATION))
    for expected in SECTION_6_CONTRACT:
        assert expected in flat, (
            f"{PREREGISTRATION} no longer states {expected!r}.\n\n"
            "WHY THIS IS A FAILURE: docs/ROADMAP.md:478-488 is the contract this file exists "
            "to discharge. A clause dropped here is a commitment silently withdrawn, and P4 "
            "grades its published headline against this document."
        )


def test_the_preregistration_carries_every_disclosure() -> None:
    """Five things a reader must be told up front rather than discover in the result.

    Each is asserted separately and by its own phrase, so a document carrying four of five
    fails naming the missing one. Asserted as a set, one strong disclosure could mask an
    absent one — and the absent one would be the disclosure a later reader most needed.

    The `donor C` clause is the subtle one. `docs/planning/p1-task-ingestion/prd.md:343-344`
    offers *"D3's inclusion of donor C is the mitigation"* for source B's self-selection —
    but donor C was **refused** for having no `uv.lock` (`tasks/README.md:171`). Carrying
    § 8.3 verbatim would ship a mitigation that does not exist, so the document states the
    disclosure and records that its mitigation did not land.
    """
    flat = _flat(_read(PREREGISTRATION))
    for label, expected in DISCLOSURES:
        assert expected in flat, (
            f"{PREREGISTRATION} dropped the {label} disclosure (looked for {expected!r}).\n\n"
            "WHY THIS IS A FAILURE: a limitation a reader finds for themselves, after the "
            "number is published, reads as something that was hidden. Disclosed in advance "
            "it is a bound on the claim. The difference is entirely one of timing, which is "
            "the same reason this file is committed before the measurement."
        )


def test_the_preregistration_names_what_is_open_without_guessing_it() -> None:
    """Three things are genuinely undecided, and a guessed number would be the worse answer.

    `docs/ROADMAP.md:569-574` leaves the held-out split, the retry count *R* (*"to be set from
    the observed unverified rate rather than guessed"*), and the open base — the last decided
    *by* the bake-off this document must precede. A pre-registration is supposed to fix
    thresholds up front, but fixing these today would breach `CLAUDE.md:119` in the one
    document whose subject is not fooling yourself.

    So each is named with the mechanism and the deadline that closes it. That makes the
    amendment rule load-bearing, and it opens a hole: an amendment could close an open item
    *and* smuggle in a success threshold once a number is visible, which is the post-hoc
    selection § 6 forbids. The exception clause is what shuts that, so it is asserted here
    rather than left to the prose.
    """
    flat = _flat(_read(PREREGISTRATION))
    for label, expected in OPEN_ITEMS:
        assert expected in flat, (
            f"{PREREGISTRATION} no longer names {label} as open (looked for {expected!r}).\n\n"
            "WHY THIS IS A FAILURE: an item silently dropped from § 7 has not been decided — "
            "it has stopped being tracked. The next reader cannot tell those apart, and the "
            "measurement it governs runs with the question unanswered."
        )
    assert AMENDMENT_EXCEPTION in flat, (
        f"{PREREGISTRATION} no longer forbids an amendment adding a success threshold.\n\n"
        "WHY THIS IS A FAILURE: § 7 lets a dated amendment close an open item, and § 5 "
        "pre-registers that no numeric success bar exists. Without this clause those two "
        "combine into a loophole: an 'amendment' adding a threshold once the result is "
        "visible, which is exactly the post-hoc selection docs/ROADMAP.md § 6 exists to "
        "refuse."
    )


def test_the_honest_number_amendment_claims_no_count_measured_here() -> None:
    """§ 10.9 discloses the delta/final series before any figure, in the § 10.6 shape.

    The honest-number report's home is admitted on the changed-series ground — the
    report measures the P4 headline under the loop's generation contract, whose seeded
    categorical sampler (`sampling.K = 16`) differs from every published contract's
    greedy sampler — and the disclosure must precede the first figure measured under it,
    exactly as § 10.6 preceded the larger-base arm's. The sentence that says no count
    has been measured yet is the disclosure's whole value: without it, a reader finding
    counts in the home later could not tell when they appeared. Asserted in the § 10.6
    shape, sentence by sentence.
    """
    flat = _flat(_read(PREREGISTRATION))
    assert "10.9" in flat, (
        f"{PREREGISTRATION} no longer carries a § 10.9 amendment. The honest-number "
        "home was admitted on the changed-series argument; without the disclosure the "
        "home's figures would be a series nobody was told about."
    )
    assert (
        "seeded categorical sampler" in flat
        and "differs from every published contract's greedy sampler" in flat
    ), (
        f"{PREREGISTRATION} § 10.9 no longer discloses the final side's generation "
        "contract. The sampler is part of the contract § 10.1 obliges a report to "
        "state, and the difference from every published contract is the ground the "
        "series is declared non-comparable on."
    )
    assert "At the time of this amendment no count has been measured under the report, " in (
        flat
    ) and "and none is claimed here" in flat, (
        f"{PREREGISTRATION} § 10.9 does not state that no count has been measured under "
        "the report and that none is claimed here. The sentence is the § 10.6 "
        "disclosure's own shape, and its absence would let the home's first figure "
        "appear without a record of when the claim began."
    )


def test_the_base_amendment_closes_section_7_3_and_claims_no_count_measured_here() -> None:
    """§ 10.10 closes § 7.3 by a Type 1 amendment before night #1, in the § 10.9 shape.

    The fine-tuned base must be pinned in the pre-registration before the night it
    governs runs (§ 8.1): a night that trained unpinned would be a silent breach of
    the amendment rule. The amendment names the base the night runbook already pins
    (the same repo_id the runbook guard holds), claims no count measured under the
    night, and records its closure in the amendment log. Asserted in the § 10.9 shape,
    sentence by sentence.
    """
    flat = _flat(_read(PREREGISTRATION))
    assert "10.10" in flat, (
        f"{PREREGISTRATION} no longer carries a § 10.10 amendment. The fine-tuned base "
        "must be pinned before the night it governs runs (§ 8.1); without the "
        "amendment, night #1 would train on a base the pre-registration never named."
    )
    assert "Type 1 (§ 8.1): closes § 7.3" in flat, (
        f"{PREREGISTRATION} § 10.10 no longer states the Type 1 closure of § 7.3. The "
        "amendment must close the open item by § 8.1's rule, committed before the "
        "measurement it governs runs."
    )
    assert RETAINED in flat, (
        f"{PREREGISTRATION} § 10.10 no longer names the fine-tuned base. The repo_id "
        "must match the night runbook's own pin, or the pre-registration and the night "
        "can drift apart silently."
    )
    assert (
        "At the time of this amendment no night has run, no count has been measured "
        "under it, and none is claimed here" in flat
    ), (
        f"{PREREGISTRATION} § 10.10 does not state that no count has been measured "
        "under the night and that none is claimed here. The sentence is the disclosure "
        "shape § 10.9 pins, and its absence would let a night's figures appear without "
        "a record of when the claim began."
    )
    assert "§ 7.3 is closed by the amendment below (§ 10.10)" in flat, (
        f"{PREREGISTRATION}'s open-items status sentence no longer records that § 7.3 "
        "is closed by § 10.10. The status paragraph is the one live sentence above "
        "§ 10 and must track the closure."
    )
    assert (
        "The fine-tuned base is pinned; § 7.3 is closed by the amendment below (§ 10.10)"
        in flat
    ), (
        f"{PREREGISTRATION}'s amendment log no longer records the § 10.10 row closing "
        "an open item. A closure that is not in the log is a silent edit (§ 8.4)."
    )


def test_the_preregistration_states_the_training_pool_reading() -> None:
    """§ 10.17 reads § 3's pinned "task set" as the scoring held-out split, before any re-mine.

    The reading is asserted nowhere else; without it a reader must re-derive whether
    training-pool growth is a § 3 change, and could re-derive it the other way. Asserted in the
    § 10.9/§ 10.10 disclosure shape, sentence by sentence.
    """
    flat = _flat(_read(PREREGISTRATION))
    assert "10.17" in flat, (
        f"{PREREGISTRATION} no longer carries a § 10.17 amendment. The night re-mines the "
        "training pool before it draws; whether that is a § 3 change is asserted nowhere, and "
        "without a dated reading a future reader could re-derive it the other way."
    )
    assert "Type 2 (§ 8.2): a disclosure, added" in flat, (
        f"{PREREGISTRATION} § 10.17 no longer states its type. The reading discloses behaviour "
        "and claims no threshold; it must be a Type 2 disclosure, not a Type 1 pin."
    )
    assert 'reads § 3\'s "the task set" as the scoring set' in flat, (
        f"{PREREGISTRATION} § 10.17 no longer states the reading itself — that § 3's pinned "
        '"the task set" is the scoring held-out split, not the pool the model learns from. '
        "Without it the reading is exactly the one a future reader must re-derive."
    )
    assert "the held-out split" in flat and "does not move" in flat, (
        f"{PREREGISTRATION} § 10.17 no longer states that the held-out split does not move. The "
        "reading is load-bearing only if the scoring input is unchanged."
    )
    assert "no new baseline is required" in flat, (
        f"{PREREGISTRATION} § 10.17 no longer states that no new baseline is required. A reading "
        "that moved the pinned input would start a new series; this one must say it does not."
    )
    assert "at the time of this amendment no night has re-mined" in flat, (
        f"{PREREGISTRATION} § 10.17 does not state that no night has re-mined. The sentence is "
        "the disclosure shape § 10.9 and § 10.10 pin; its absence would let a night's figures "
        "appear without a record of when the claim began."
    )
    assert "and none is claimed here" in flat, (
        f"{PREREGISTRATION} § 10.17 does not state that no count is claimed under it."
    )
    assert (
        'The night re-mines the training pool; § 3\'s pinned "task set" is the scoring '
        "held-out split (§ 10.17)" in flat
    ), (
        f"{PREREGISTRATION}'s amendment log no longer records the § 10.17 row. A dated reading "
        "that is not in the log is a silent edit (§ 8.4)."
    )


def test_the_raised_draw_budget_is_amended_and_pinned() -> None:
    """§ 10.19 pins the loop's draw budget at 16 before any night records it, in the § 10.18 shape.

    § 8.1 requires the input of a measurement be pinned **before** the measurement it governs
    runs, and the loop's draw budget is such an input. The code now declares `sampling.K = 16`,
    so the document must name that value — the doc↔code cross-pin the dig found absent — and
    must mark § 10.9's disclosed `sampling.K = 8` superseded without editing its body (the
    document is append-only). The assertion interpolates the constant rather than hard-coding
    `16`, so a drift between § 10.19 and the code fails by name.
    """
    flat = _flat(_read(PREREGISTRATION))
    assert sampling.K == 16, (
        f"the loop declares sampling.K = {sampling.K}, not the 16 § 10.19 pre-registers. "
        "The amendment pins a budget the code does not use, which is a document describing a "
        "loop that does not exist."
    )
    assert "10.19" in flat, (
        f"{PREREGISTRATION} no longer carries a § 10.19 amendment. The raised draw budget is "
        "an input of the main series' measurement and must be pinned before the night it "
        "governs runs (§ 8.1); without it a night would record 16 under a document that names 8."
    )
    assert f"sampling.K = {sampling.K}" in flat, (
        f"{PREREGISTRATION} § 10.19 does not name the value in force, `sampling.K = "
        f"{sampling.K}`. The cross-pin is the whole point of the amendment: a reader must be "
        "able to compare the document's budget against the code's constant by identity."
    )
    assert "pins an input of the measurement it precedes" in flat, (
        f"{PREREGISTRATION} § 10.19 no longer states its Type 1 ground. § 8.1 permits the "
        "amendment precisely because it pins an input before the measurement it governs; "
        "dropping the sentence would leave the raise reading as a post-hoc change."
    )
    assert "from 8 to 16" in flat, (
        f"{PREREGISTRATION} § 10.19 no longer states the move from 8 to 16. The old value is "
        "the one § 10.9 disclosed, and the amendment exists to record the change between them."
    )
    assert "non-comparable" in flat and "the old series is not extended" in flat, (
        f"{PREREGISTRATION} § 10.19 no longer states the § 3 series consequence. Every loop "
        "figure measured under `sampling.K = 8` is non-comparable to one measured under `16`, "
        "and § 3 treats a change to a pinned input as starting over."
    )
    assert "§ 10.9 is superseded, not edited" in flat, (
        f"{PREREGISTRATION} § 10.19 no longer records the supersession of § 10.9. § 10.9 "
        "disclosed `sampling.K = 8` as the value then in force; that value is now historical, "
        "and § 10.9's body is preserved byte-intact because this document is append-only."
    )
    assert (
        "2026-10-17 | The nightly loop's draw budget is raised from 8 to 16 (§ 10.19) | "
        "1 — pins the inputs of a measurement | Yes" in flat
    ), (
        f"{PREREGISTRATION}'s amendment log no longer records the § 10.19 row. A dated "
        "amendment that is not in the log is a silent edit (§ 8.4)."
    )


def test_the_scorable_rule_amendment_re_derives_the_split_before_any_scoring() -> None:
    """§ 10.16 re-derives the held-out split under the scorable rule, in the § 10.7 shape.

    A gate pointed at a split whose members' oracles cannot be built under the sealed
    budget can never fire (`unverified == 0`), so the split is re-derived before any
    candidate scores against it. The pre-registration must record that as a dated Type 1
    amendment committed before the measurement it governs runs (§ 8.1), naming the rule
    and the re-minted corpus identity, stating the § 3 series consequence, and editing
    nothing silently. Asserted in the § 10.7/§ 10.10 shape, sentence by sentence, with
    the budget figure cross-pinned against the code by identity.
    """
    flat = _flat(_read(PREREGISTRATION))
    budget = heldout._RULE_PARAMETERS["oracle_budget_chars"]
    assert budget == sources.ORACLE_BUDGET_CHARS, (
        f"the held-out rule seals oracle_budget_chars={budget}, but the bakeoff enforces "
        f"sources.ORACLE_BUDGET_CHARS={sources.ORACLE_BUDGET_CHARS}. The two code constants "
        "must be one number, or the amendment's figure is pinned to a rule the bakeoff "
        "does not use."
    )
    assert "10.16" in flat, (
        f"{PREREGISTRATION} no longer carries a § 10.16 amendment. The held-out split is "
        "re-derived under the scorable rule, and the re-derivation must be recorded as a "
        "dated amendment committed before any candidate scores against the new document "
        "(§ 8.1); without it the gate would consume a split the pre-registration never "
        "named."
    )
    assert (
        "Type 1 (§ 8.1): pins the inputs of a measurement, committed before any candidate "
        "scores against the re-derived split" in flat
    ), (
        f"{PREREGISTRATION} § 10.16 no longer states the Type 1 pin of the measurement's "
        "inputs. The amendment must be committed before the measurement it governs runs "
        "(§ 8.1), and the sentence must name the split it re-derives."
    )
    assert f"oracle_budget_chars = {budget}" in flat, (
        f"{PREREGISTRATION} § 10.16 no longer states the sealed budget figure "
        f"oracle_budget_chars = {budget}. The amendment pins the budget the rule applies, "
        "and this assertion derives the figure from heldout._RULE_PARAMETERS so a drift "
        "between the amendment and the code fails by name."
    )
    assert "donor-a-" in flat and "donor-b-" in flat, (
        f"{PREREGISTRATION} § 10.16 no longer names the re-minted corpus identity. The "
        "re-derived split is drawn over the `donor-a-*`/`donor-b-*` label-form ids, and "
        "the amendment must name them or the new corpus cannot be told from the old one."
    )
    assert "the #62 pairing" in flat and "one re-derivation" in flat, (
        f"{PREREGISTRATION} § 10.16 no longer records the pairing with the #62 re-mint. "
        "The corpus is swapped once, by a scripted step, and the amendment must say so or "
        "the re-derivation reads as a repeatable re-roll."
    )
    assert "by class" in flat and "never a hand-picked membership" in flat, (
        f"{PREREGISTRATION} § 10.16 no longer states the exclusion's class property. The "
        "rule excludes oracle-unfittable members as a class — a digest-sealed function in "
        "heldout.py — never a hand-picked membership, and dropping the property is the "
        "cherry-picking optics issue #60 warns about."
    )
    assert "described the take, not the floor" in flat, (
        f"{PREREGISTRATION} § 10.16 no longer records that § 10.7's \"4 tasks per band\" "
        "sentence described the take, not the floor. The floors bind over the scorable "
        "members, and the supersession must be stated, never quietly edited."
    )
    assert "night denominators" in flat and "gate-001" in flat and "non-comparable" in flat, (
        f"{PREREGISTRATION} § 10.16 no longer states the § 3 series consequence. Prior "
        "figures keyed to the old document — the night denominators, gate-001 — are "
        "non-comparable, and a reader who could still compare them would read a delta "
        "across a changed pinned input."
    )
    assert "the old series is never extended" in flat, (
        f"{PREREGISTRATION} § 10.16 no longer states that the old series is never "
        "extended. § 3 treats a change to a pinned input as starting over, and the "
        "amendment must say so in words."
    )
    assert "the old series is superseded" in flat, (
        f"{PREREGISTRATION} § 10.16 no longer states what a decision on the new document "
        "means: the old series is superseded."
    )
    assert "the document's `excluded` field names them" in flat and "never hidden" in flat, (
        f"{PREREGISTRATION} § 10.16 no longer states that the oracle-unfittable tasks stay "
        "in the corpus with their status reported. The excluded class is named by the "
        "document's `excluded` field and never hidden, or the record would silently lose "
        "a denominator."
    )
    assert "`rejected` 0-0 is a valid first decision" in flat and "never dressed as a win" in (
        flat
    ), (
        f"{PREREGISTRATION} § 10.16 no longer states that a rejected 0-0 is a valid first "
        "decision. The re-derivation is a liveness fix, not a yield fix, and the amendment "
        "must not imply otherwise."
    )
    assert "does not change" in flat and "all stand unchanged" in flat, (
        f"{PREREGISTRATION} § 10.16 no longer carries the does-not-change clause. The base "
        "§ 10.10 pinned, the verifier, the gate's terms and the budget value all stand "
        "unchanged, and the amendment must say so or a reader could misread the re-derived "
        "split as a loosening."
    )
    assert "introduces no success threshold" in flat, (
        f"{PREREGISTRATION} § 10.16 no longer states the no-threshold invariance. § 8.3 "
        "forbids an amendment introducing a success threshold, and the amendment must "
        "carry that sentence or the exclusion reads as a threshold in disguise."
    )
    assert "No measurement has been run against the re-derived split" in flat and (
        "and none is claimed here" in flat
    ), (
        f"{PREREGISTRATION} § 10.16 does not state that no count has been measured under "
        "the re-derived split and that none is claimed here. The sentence is the disclosure "
        "shape § 10.7 pins, and its absence would let the new document's first figures "
        "appear without a record of when the claim began."
    )
    assert (
        "2026-09-27 | The held-out source-B split is re-derived under the scorable rule "
        "(§ 10.16) | 1 — pins the inputs of a measurement" in flat
    ), (
        f"{PREREGISTRATION}'s amendment log no longer records the § 10.16 row as a Type 1 "
        "pin of a measurement's inputs. A re-derivation that is not in the log is a silent "
        "edit (§ 8.4)."
    )
    assert "The split § 10.7 fixed is re-derived by the dated amendment below (§ 10.16)" in (
        flat
    ), (
        f"{PREREGISTRATION}'s open-items status sentence no longer records that the split "
        "§ 10.7 fixed is re-derived by § 10.16. The status paragraph is the one live "
        "sentence above § 10 and must track the supersession."
    )
    assert "No amendment has introduced a success threshold" in flat, (
        f"{PREREGISTRATION}'s standing integrity sentence no longer holds. After the "
        "§ 10.16 edit the document must still state that no amendment has introduced a "
        "success threshold."
    )


def test_the_cpu_dtype_amendment_pins_the_precision() -> None:
    """§ 10.18 pins the portability arm's CPU precision, in the § 10.13 shape.

    A dtype moves every figure measured under it, so it is a pinned input (§ 8.1;
    `docs/ROADMAP.md`:788), and the portability arm's declared CPU precision must be
    fixed by a dated Type 1 amendment committed before the training it governs runs.
    This is a new amendment shape: § 10.11 through § 10.15 each pinned a *base*; § 10.18 pins a
    *runtime input*. The amendment must carry the Type 1 line, the no-threshold/no-§ 1/
    § 4/§ 6-rewording line, the non-comparability sentence naming the precision, the
    "what is not claimed" sentence, and its amendment-log row. The literal `bfloat16`
    is cross-pinned against `torch_runtime.DEVICE_PRECISION["cpu"]`, so a drift between
    the document and the code fails by name.
    """
    flat = _flat(_read(PREREGISTRATION))
    precision = torch_runtime.DEVICE_PRECISION["cpu"]
    assert precision == "bfloat16", (
        f"DEVICE_PRECISION['cpu'] is {precision!r}, not 'bfloat16'. § 10.18 pins the arm's "
        "CPU precision, and the amendment's literal must equal the constant the runtime "
        "reads, or the document and the code have drifted."
    )
    assert "### 10.18" in flat, (
        f"{PREREGISTRATION} no longer carries a § 10.18 amendment. The portability arm's "
        "CPU precision is a pinned input (§ 8.1; docs/ROADMAP.md:788), and it must be "
        "recorded as a dated Type 1 amendment committed before the training it governs; "
        "without it, a night would train under a precision the pre-registration never named."
    )
    assert (
        "Type 1 (§ 8.1): pins the input of an existing arm, committed before the training "
        "it governs runs" in flat
    ), (
        f"{PREREGISTRATION} § 10.18 no longer states the Type 1 pin of an existing arm's "
        "input. § 8.1's rule is that the input is pinned before the training it governs, and "
        "the sentence must name the arm it pins for."
    )
    assert "introduces no success threshold" in flat and (
        "rewords nothing in § 1, § 4 or § 6" in flat
    ), (
        f"{PREREGISTRATION} § 10.18 no longer carries the no-threshold/no-rewording line. "
        "§ 8.3 forbids an amendment introducing a success threshold, and this one must also "
        "leave § 1, § 4 and § 6 untouched or the dtype reads as a loosening."
    )
    assert "does not change the base § 10.10 pinned" in flat, (
        f"{PREREGISTRATION} § 10.18 no longer states that § 10.10's base is untouched. The "
        "32B base and the MLX runtime remain the main series' pinned inputs; a reader who "
        "could not tell that from this amendment might read it as a base change."
    )
    assert "new shape of amendment" in flat and "pins a runtime input" in flat, (
        f"{PREREGISTRATION} § 10.18 no longer names its own shape. § 10.11 through § 10.15 each "
        "pinned a base; this pins a runtime input, and the distinction must be stated or the "
        "amendment reads as one more base step."
    )
    assert f"moves from `float32` to `{precision}`" in flat, (
        f"{PREREGISTRATION} § 10.18 no longer states the change of precision. The declared "
        f"CPU precision moves from `float32` to `{precision}`, and the sentence must name "
        "both ends or the change cannot be told from the state it replaced."
    )
    assert 'DEVICE_PRECISION["cpu"]' in flat, (
        f"{PREREGISTRATION} § 10.18 no longer names the constant the change lives in. The "
        "amendment pins a code input, and naming `DEVICE_PRECISION[\"cpu\"]` is what lets a "
        "stranger find it."
    )
    assert "training, rollouts and gate verdicts" in flat, (
        f"{PREREGISTRATION} § 10.18 no longer states the blast radius. The one map is read by "
        "both the trainer and the generator/gate loader, so training, rollouts and gate "
        "verdicts all move together, and the amendment must say so."
    )
    assert (
        f"non-comparable to any figure measured under the new `{precision}` precision" in flat
    ), (
        f"{PREREGISTRATION} § 10.18 no longer carries the non-comparability sentence naming "
        f"the new precision. Every prior arm figure — training, rollouts, gate verdict — is "
        f"non-comparable to a figure measured under `{precision}` (§ 3), and the sentence must "
        "name the precision or a reader could still compare across the change."
    )
    assert "the old series is not extended" in flat, (
        f"{PREREGISTRATION} § 10.18 no longer states that the old series is never extended. "
        "§ 3 treats a change to a pinned input as starting over, and the amendment must say so."
    )
    assert "No training has run under this dtype" in flat, (
        f"{PREREGISTRATION} § 10.18 no longer states that no training has run under the new "
        "precision. The sentence is the disclosure shape § 10.13 pins, and its absence would "
        "let a figure under the new dtype appear without a record of when the claim began."
    )
    assert "the § 3 baseline remains unspent" in flat, (
        f"{PREREGISTRATION} § 10.18 no longer states that the § 3 baseline is unspent. The "
        "dtype change spends no baseline, and a reader must be told so."
    )
    assert "accept the finding" in flat, (
        f"{PREREGISTRATION} § 10.18 no longer records that *\"accept the finding\"* remains a "
        "legitimate outcome. A zero under the new dtype is entirely possible "
        "(docs/ROADMAP.md:790), and the amendment must not imply the change guarantees a fit."
    )
    assert (
        "2026-10-11 | The portability arm's CPU precision is declared "
        f"`{precision}` (§ 10.18) | 1 — pins the inputs of a measurement | Yes" in flat
    ), (
        f"{PREREGISTRATION}'s amendment log no longer records the § 10.18 row as a Type 1 pin "
        "of a measurement's inputs. An amendment that is not in the log is a silent edit (§ 8.4)."
    )


def test_the_torch_mps_amendment_pins_the_new_series() -> None:
    """§ 10.20 makes the Torch/MPS 7B series the main series, in the § 10.18 shape.

    The new series' base, revision, runtime, device and precision are pinned inputs (§ 8.1), and
    every one of them is committed before the training it governs runs. The amendment must carry
    the Type 1 line, the no-threshold/no-§ 1/§ 4/§ 6-rewording line, the non-comparability
    paragraph ending "the old series is not extended", the no-training-run sentence and its
    amendment-log row. `float16` is cross-pinned against
    `torch_runtime.DEVICE_PRECISION["mps"]`, so a drift between the document and the code fails by
    name. The sheet cross-pin moved to § 10.21 when the base moved; § 10.20 keeps its own text.
    """
    flat = _flat(_read(PREREGISTRATION))
    base = "Qwen/Qwen2.5-Coder-7B-Instruct"
    revision = "c03e6d358207e414f1eca0bb1891e29f1db0e242"
    precision = torch_runtime.DEVICE_PRECISION["mps"]
    assert precision == "float16", (
        f"DEVICE_PRECISION['mps'] is {precision!r}, not 'float16'. § 10.20 pins the MPS series' "
        "precision, and the amendment's literal must equal the constant the runtime reads."
    )
    assert "### 10.20" in flat, (
        f"{PREREGISTRATION} no longer carries a § 10.20 amendment. The Torch/MPS series' base, "
        "revision, runtime, device and precision are pinned inputs (§ 8.1), and they must be "
        "recorded as a dated Type 1 amendment committed before the training they govern; without "
        "it, a night would train a series the pre-registration never named."
    )
    assert (
        "Type 1 (§ 8.1): pins the inputs of a new series, committed before the training it "
        "governs runs" in flat
    ), (
        f"{PREREGISTRATION} § 10.20 no longer states the Type 1 pin of a new series' inputs. "
        "§ 8.1's rule is that the input is pinned before the training it governs, and the "
        "sentence must say the series is new rather than an edit of an existing one."
    )
    assert "introduces no success threshold" in flat and (
        "rewords nothing in § 1, § 4 or § 6" in flat
    ), (
        f"{PREREGISTRATION} § 10.20 no longer carries the no-threshold/no-rewording line. "
        "§ 8.3 forbids an amendment introducing a success threshold, and this one must also "
        "leave § 1, § 4 and § 6 untouched or the new series reads as a loosening."
    )
    assert "does not edit § 10.10" in flat, (
        f"{PREREGISTRATION} § 10.20 no longer states that § 10.10 is untouched. This document is "
        "append-only, and the amendment that opened the 32B series must keep its text byte-intact."
    )
    assert base in flat and revision in flat, (
        f"{PREREGISTRATION} § 10.20 no longer names the pinned base {base!r} at revision "
        f"{revision!r}. A base named without an immutable revision is not a pinned input."
    )
    assert 'DEVICE_PRECISION["mps"]' in flat and "`float16`" in flat, (
        f"{PREREGISTRATION} § 10.20 no longer names the runtime input. The series' precision "
        "lives in `DEVICE_PRECISION[\"mps\"]`, and the amendment must name both the constant "
        "and the dtype it declares."
    )
    assert "non-comparable" in flat and "different kernels and a different precision" in flat, (
        f"{PREREGISTRATION} § 10.20 no longer carries the non-comparability paragraph naming "
        "weights, runtime, device, kernels and precision. Every 32B/MLX or arm figure is "
        "non-comparable to one measured under this series (§ 3), and each of those differences "
        "is sufficient on its own."
    )
    assert "the old series is not extended" in flat, (
        f"{PREREGISTRATION} § 10.20 no longer states that the old series is never extended. "
        "§ 3 treats a change to a pinned input as starting over, and the amendment must say so."
    )
    assert "No training has run" in flat, (
        f"{PREREGISTRATION} § 10.20 no longer states that no training has run under the series. "
        "The sentence is the disclosure shape § 10.18 pins, and its absence would let a figure "
        "appear without a record of when the claim began."
    )
    assert "the § 3 baseline remains unspent" in flat, (
        f"{PREREGISTRATION} § 10.20 no longer states that the § 3 baseline is unspent. A new "
        "series starts no baseline measurement, and a reader must be told so."
    )
    assert (
        "2026-10-20 | The main series moves to Torch/MPS on a pinned 7B HF base; the 32B/MLX "
        "series remains separate and unretired (§ 10.20) | 1 — pins the inputs of a new series "
        "| Yes" in flat
    ), (
        f"{PREREGISTRATION}'s amendment log no longer records the § 10.20 row as a Type 1 pin of "
        "a new series' inputs. An amendment that is not in the log is a silent edit (§ 8.4)."
    )


def test_the_base_swap_amendment_pins_the_8b_base() -> None:
    """§ 10.21 moves the main series to Qwen3-8B, in the § 10.20 shape.

    The 7B measured its wall (613 NO_DIFF of 816, zero solved) and the pre-flight cleared the
    format bar at 6 of 8 private tasks. The new base and its revision are pinned inputs (§ 8.1)
    committed before the training they govern; § 10.20 stays byte-intact and its series stays a
    separate, non-retired evidence series. The sheet must carry the same base and revision.
    """
    flat = _flat(_read(PREREGISTRATION))
    base = "Qwen/Qwen3-8B"
    revision = "b968826d9c46dd6066d109eabc6255188de91218"
    assert "### 10.21" in flat, (
        f"{PREREGISTRATION} no longer carries a § 10.21 amendment. The 8B base, its revision and "
        "the unchanged inputs are pinned by this amendment; without it the night trains a series "
        "the pre-registration never named."
    )
    assert (
        "Type 1 (§ 8.1): pins the inputs of a new series, committed before the training it "
        "governs runs" in flat
    ), (
        f"{PREREGISTRATION} § 10.21 no longer states the Type 1 pin of a new series' inputs. "
        "§ 8.1's rule is that the input is pinned before the training it governs."
    )
    assert "introduces no success threshold" in flat and (
        "rewords nothing in § 1, § 4 or § 6" in flat
    ), (
        f"{PREREGISTRATION} § 10.21 no longer carries the no-threshold/no-rewording line. "
        "§ 8.3 forbids an amendment introducing a success threshold."
    )
    assert "does not edit § 10.20" in flat, (
        f"{PREREGISTRATION} § 10.21 no longer states that § 10.20 is untouched. This document is "
        "append-only, and the 7B pin keeps its text byte-intact."
    )
    assert base in flat and revision in flat, (
        f"{PREREGISTRATION} § 10.21 no longer names the pinned base {base!r} at revision "
        f"{revision!r}. A base named without an immutable revision is not a pinned input."
    )
    assert "8.96 GB" in flat and "25.6" in flat, (
        f"{PREREGISTRATION} § 10.21 no longer records the measured MPS fit (8.96 GB peak against "
        "the 25.6 GB headroom). The fit is the input the night's capacity probe is read against."
    )
    assert "non-comparable" in flat and "the old series is not extended" in flat, (
        f"{PREREGISTRATION} § 10.21 no longer carries the non-comparability paragraph and the "
        "'old series is not extended' sentence. § 3 starts over on a pinned-input change."
    )
    assert "No training has run" in flat and "the § 3 baseline remains unspent" in flat, (
        f"{PREREGISTRATION} § 10.21 no longer states that no training has run and that the § 3 "
        "baseline is unspent. A new series starts no baseline measurement."
    )
    assert "format conformance" in flat and "not a solve" in flat, (
        f"{PREREGISTRATION} § 10.21 no longer states that the pre-flight GO is format conformance, "
        "not a solve. The pre-flight solved nothing."
    )
    assert (
        "2026-10-22 | The main series' base moves to a pinned 8B HF model; the 7B Torch/MPS "
        "series remains separate and unretired (§ 10.21) | 1 — pins the inputs of a new series "
        "| Yes" in flat
    ), (
        f"{PREREGISTRATION}'s amendment log no longer records the § 10.21 row as a Type 1 pin of "
        "a new series' inputs. An amendment that is not in the log is a silent edit (§ 8.4)."
    )
    sheet = _flat(_read("docs/planning/torch-mps-series/night-door/runbook.md"))
    assert base in sheet and revision in sheet, (
        "docs/planning/torch-mps-series/night-door/runbook.md no longer names the same base and "
        f"revision § 10.21 pins ({base!r} @ {revision!r}). The amendment and the sheet describe "
        "one input; a drift means the night trains something the pre-registration never named."
    )


def test_the_roadmap_records_the_re_derived_split_by_dated_correction() -> None:
    """AC8. § 12 referenced the § 10.7 split as live; the correction records the re-derivation.

    The roadmap's operator chain and "same split" sentence point at the held-out split § 10.7
    fixed. That document is re-derived by § 10.16, and the roadmap records the supersession
    the way it records every supersession: a dated correction blockquote naming the amendment
    and the non-comparability consequence, never an edit of the old text.
    """
    lines = _read("docs/ROADMAP.md").splitlines()
    quoted = _flat("\n".join(line for line in lines if line.lstrip().startswith(">")))
    assert "Corrected 2026-09-27" in quoted, (
        "docs/ROADMAP.md no longer carries the 2026-09-27 dated correction recording the "
        "held-out split's re-derivation. The roadmap records every supersession as a dated "
        "correction blockquote, never as an edit of the old text."
    )
    assert "the held-out source-B split is re-derived" in quoted, (
        "docs/ROADMAP.md's dated correction no longer states that the held-out source-B "
        "split is re-derived. The correction must say what changed or it records nothing."
    )
    assert "10.16" in quoted, (
        "docs/ROADMAP.md's dated correction no longer names § 10.16. The correction must "
        "point at the amendment that records the re-derivation, or a reader cannot find "
        "the rule."
    )
    assert "non-comparable" in quoted, (
        "docs/ROADMAP.md's dated correction no longer states the non-comparability "
        "consequence. Prior figures keyed to the old document may not be compared with "
        "figures on the re-derived one (§ 3), and the correction must say so."
    )


def test_the_roadmap_records_the_night_remine_by_dated_correction() -> None:
    """§ 13's "The corpus does not grow" is superseded by a dated correction, not an edit.

    The paragraph is made false by the night re-mining before it draws, and the roadmap records
    every supersession as a dated correction blockquote naming the amendment and the
    consequence, never by rewriting the old text. The blockquote also reconciles § 9 (which
    never named re-mining) and § 14 (which holds the only identified lever on the zero).
    """
    lines = _read("docs/ROADMAP.md").splitlines()
    quoted = _flat("\n".join(line for line in lines if line.lstrip().startswith(">")))
    assert "Corrected 2026-10-11" in quoted, (
        "docs/ROADMAP.md no longer carries the 2026-10-11 dated correction recording the "
        "night re-mine. § 13's corpus paragraph is made false by the change, and the roadmap "
        "records every supersession as a dated correction, never an edit of the old text."
    )
    assert "re-mines before it draws" in quoted, (
        "docs/ROADMAP.md's dated correction no longer states that the night re-mines before "
        "it draws. The correction must say what changed or it records nothing."
    )
    assert "10.17" in quoted, (
        "docs/ROADMAP.md's dated correction no longer names § 10.17. The reading that makes "
        "training-pool growth no § 3 change lives there, and the correction must point at it."
    )
    assert "not a lever on the zero" in quoted, (
        "docs/ROADMAP.md's dated correction no longer states that re-mining is not a lever on "
        "the zero strict-PASS yield. A bigger pool says nothing about whether a candidate "
        "improves, and § 14's M1 remains the only identified lever."
    )


def test_no_present_tense_document_asserts_that_the_corpus_does_not_grow() -> None:
    """The corpus grows now, and only the dated correction may quote the old claim.

    § 13 is an appended, dated snapshot, and the roadmap records a supersession as a dated
    correction blockquote rather than by editing the old text (the § 12/§ 10.16 precedent). So
    the falsified sentence is allowed in the roadmap only inside the correction that quotes it,
    and in no present-tense document at all — CLAUDE.md, README.md and CHANGELOG.md describe the
    tree as it is. The positive control is the quotation itself: deleting the sentence outright
    would satisfy the absence checks while recording nothing.
    """
    for name in PRESENT_TENSE_DOCS:
        assert "The corpus does not grow" not in _flat(_read(name)), (
            f"{name} still asserts, in the present tense, that the corpus does not grow. The "
            "night re-mines the declared donor before it draws, so the sentence is false about "
            "the tree it ships in."
        )
    lines = _read("docs/ROADMAP.md").splitlines()
    quoted = _flat("\n".join(line for line in lines if line.lstrip().startswith(">")))
    assert "The corpus does not grow" in quoted, (
        "docs/ROADMAP.md no longer preserves the falsified sentence as a quotation anywhere. "
        "The absence checks above would be satisfied by deleting it, which would hide that the "
        "claim was ever made."
    )


def test_the_write_up_records_the_night_remine() -> None:
    """A capability is written up in the commit that lands it (`CLAUDE.md`).

    The STATUS entry is append-only history; the CHANGELOG phrase is asserted anywhere in the
    file so it survives a release moving `[Unreleased]` content under a version — pinning the
    `[Unreleased]` heading would fail the moment a release removes it.
    """
    assert "night-corpus-remine" in _read("docs/STATUS.md"), (
        "docs/STATUS.md no longer records the night-corpus-remine unit. The repo's rule is that "
        "a capability is written up in the commit that lands it, and STATUS.md is that history."
    )
    assert "re-mines before it draws" in _read("CHANGELOG.md"), (
        "CHANGELOG.md no longer records the night re-mine. This file records what shipped, and "
        "the night now re-mines before it draws."
    )


def test_the_write_up_records_the_k16_night_guards() -> None:
    """A capability is written up in the commit that lands it (`CLAUDE.md`).

    The guards landed before the operator's night: the durability guard, the `check-probe` budget
    and `--heldout` split pins, and the finding guard. The night itself is unrun, so the entry
    claims no number. As with `test_the_write_up_records_the_night_remine`, the STATUS entry is
    append-only history and the CHANGELOG phrase is asserted anywhere in the file so it survives a
    release moving `[Unreleased]` content under a version.
    """
    assert "k16-night" in _read("docs/STATUS.md"), (
        "docs/STATUS.md no longer records the k16-night unit. The repo's rule is that a capability "
        "is written up in the commit that lands it, and STATUS.md is that history."
    )
    assert "the K=16 night is unrun" in _read("CHANGELOG.md"), (
        "CHANGELOG.md no longer records that the K=16 night is unrun. This file records what "
        "shipped, and the guards shipped without running the night or claiming a number."
    )


def test_the_write_up_records_the_torch_mps_series() -> None:
    """A capability is written up in the commit that lands it (`CLAUDE.md`).

    The series landed before the operator's night: § 10.20, the `--runtime` flag, the MPS load
    path and the Torch/MPS sheet. The night is unrun, so the entry claims no number. The STATUS
    entry is append-only and the CHANGELOG phrase is asserted anywhere in the file so it survives
    a release moving `[Unreleased]` content under a version.
    """
    assert "torch-mps-series" in _read("docs/STATUS.md"), (
        "docs/STATUS.md no longer records the torch-mps-series unit. The repo's rule is that a "
        "capability is written up in the commit that lands it, and STATUS.md is that history."
    )
    assert "the Torch/MPS night is unrun" in _read("CHANGELOG.md"), (
        "CHANGELOG.md no longer records that the Torch/MPS night is unrun. This file records "
        "what shipped, and the series shipped without running the night or claiming a number."
    )


def test_the_write_up_records_public_task_offline() -> None:
    """A capability is written up in the commit that lands it (`CLAUDE.md`).

    The mirror/reuse/hooks and the sheet's pre-warm/caffeinate landed before any night; no night
    ran, so the entry claims no number. As with the k16 and torch-mps guards, the STATUS entry is
    append-only history and the CHANGELOG phrase is asserted anywhere in the file so it survives a
    release moving `[Unreleased]` content under a version.
    """
    assert "public-task-offline" in _read("docs/STATUS.md"), (
        "docs/STATUS.md no longer records the public-task-offline unit. The repo's rule is that a "
        "capability is written up in the commit that lands it, and STATUS.md is that history."
    )
    assert "the public task is provisioned offline" in _read("CHANGELOG.md"), (
        "CHANGELOG.md no longer records that the public task is provisioned offline. This file "
        "records what shipped, and the mirror/reuse/hooks shipped without running a night or "
        "claiming a number."
    )


def test_the_roadmap_records_the_cpu_precision_change_by_dated_correction() -> None:
    """AC7. § 13 said the runtime loaded `float32` on CPU; the correction records § 10.18.

    The roadmap's hardware-ceiling paragraph pinned the CPU dtype in the present tense:
    *"The Torch runtime loads `float32` on CPU by declaration."* `DEVICE_PRECISION["cpu"]`
    is now `bfloat16` (§ 10.18), so the roadmap records the supersession the way it records
    every supersession — a dated correction blockquote naming the amendment and the
    non-comparability consequence, never an edit of the old text. The original sentence is
    kept inside that correction as a quotation; the repo's convention keeps it as history
    rather than deleting it.
    """
    lines = _read("docs/ROADMAP.md").splitlines()
    quoted = _flat("\n".join(line for line in lines if line.lstrip().startswith(">")))
    assert "Corrected 2026-10-11" in quoted, (
        "docs/ROADMAP.md no longer carries the 2026-10-11 dated correction recording the "
        "CPU precision change. The roadmap records every supersession as a dated correction "
        "blockquote, never as an edit of the old text."
    )
    assert "CPU precision" in quoted, (
        "docs/ROADMAP.md's dated correction no longer names the CPU precision. The "
        "correction must say what changed or it records nothing."
    )
    assert "10.18" in quoted, (
        "docs/ROADMAP.md's dated correction no longer names § 10.18. The correction must "
        "point at the amendment that records the precision change, or a reader cannot find "
        "the pin."
    )
    assert "The Torch runtime loads `float32` on CPU by declaration" in quoted, (
        "docs/ROADMAP.md's dated correction no longer preserves the original sentence as a "
        "quotation. The repo's convention keeps the superseded sentence as history inside "
        "the correction rather than deleting it, so the change is recorded and not silently "
        "rewritten."
    )
    assert "non-comparable" in quoted, (
        "docs/ROADMAP.md's dated correction no longer states the non-comparability "
        "consequence. Every portability-arm figure measured under the earlier precision may "
        "not be compared with one measured under the new one (§ 10.18), and the correction "
        "must say so."
    )


def test_the_roadmap_records_the_raised_draw_budget_by_dated_correction() -> None:
    """AC3.1. § 13 said raising *k* was untried; the correction records § 10.19.

    The roadmap's pivot paragraph pinned the old budget in the present tense:
    *"Raising *k* remains untried: `K = 8` is a declared constant and never a flag."*
    `sampling.K` is now `16` (§ 10.19), so the roadmap records the supersession the way it
    records every supersession — a dated correction blockquote naming the amendment and the
    non-comparability consequence, rather than leaving the false sentence standing. The
    superseded sentence is preserved inside that correction as a quotation, so the change is
    recorded and the old text is history rather than lost.

    The prose/blockquote split is what lets the guard require the old sentence's absence from
    the live text while it remains present as a quotation, so deleting the sentence outright
    cannot satisfy this.
    """
    lines = _read("docs/ROADMAP.md").splitlines()
    quoted = _flat("\n".join(line for line in lines if line.lstrip().startswith(">")))
    live = _flat("\n".join(line for line in lines if not line.lstrip().startswith(">")))
    assert "Corrected 2026-10-17" in quoted, (
        "docs/ROADMAP.md no longer carries the 2026-10-17 dated correction recording the "
        "raised draw budget. § 13's pivot paragraph is made false by the change, and the "
        "roadmap records every supersession as a dated correction rather than leaving the "
        "false sentence standing."
    )
    assert "10.19" in quoted, (
        "docs/ROADMAP.md's dated correction no longer names § 10.19. The correction must "
        "point at the amendment that pins the new budget, or a reader cannot find the pin."
    )
    assert "Raising *k* remains untried" in quoted, (
        "docs/ROADMAP.md's dated correction no longer preserves the original sentence as a "
        "quotation. The superseded sentence is kept as history inside the correction rather "
        "than lost, so the change is recorded and not silently rewritten."
    )
    assert "`K = 8`" in quoted, (
        "docs/ROADMAP.md's dated correction no longer quotes the superseded budget `K = 8`. "
        "The correction must say what changed or it records nothing."
    )
    assert "non-comparable" in quoted, (
        "docs/ROADMAP.md's dated correction no longer states the non-comparability "
        "consequence. Every loop figure measured under `K = 8` may not be compared with one "
        "measured under `16` (§ 10.19), and the correction must say so."
    )
    for stale in ("Raising k remains untried", "`K = 8`"):
        assert stale not in live, (
            f"docs/ROADMAP.md still says {stale!r} in live prose. The declared budget is "
            "`16` (§ 10.19), so the old sentence is false about the tree it ships in and may "
            "survive only as a quotation inside the dated correction."
        )


def test_the_arm_report_names_the_declared_cpu_precision() -> None:
    """AC9 (S1). The arm's report names the pinned CPU precision, without adding a figure.

    `DEVICE_PRECISION["cpu"]` is `bfloat16` (§ 10.18), and the arm's own declaration must
    state the precision its runtime declares. This is a name, never a count: the report's
    `N of M` figures are pinned by `tests/bakeoff/test_report.py`, and the guard here
    asserts only that the dtype is stated.
    """
    text = _read("reports/portability-arm/report.md")
    precision = torch_runtime.DEVICE_PRECISION["cpu"]
    assert precision in text, (
        "reports/portability-arm/report.md no longer names the arm's declared CPU precision "
        f"({precision!r}). The arm declares its pinned inputs, and its report must state the "
        "dtype its runtime now declares (§ 10.18)."
    )
def test_a_report_without_its_preregistration_is_reported_as_an_offender(
    tmp_path: Path,
) -> None:
    """The ordering guard, watched failing — otherwise it proves nothing today.

    `reports/` does not exist in this repository, so the real-tree assertion two tests below
    would pass on a helper that always returned an empty list. `CONTRIBUTING.md:56-60` is
    explicit that a guard nobody has seen fail may be passing vacuously, and that a vacuous
    honesty guard is worse than none because it buys false confidence. So the helper is
    exercised against a tree built by hand where the ordering is violated.
    """
    (tmp_path / "reports" / "baseline").mkdir(parents=True)
    (tmp_path / "reports" / "baseline" / "bakeoff.md").write_text("a number", encoding="utf-8")

    assert _reports_without_preregistration(tmp_path) == ["reports/baseline/bakeoff.md"], (
        "a tree holding a baseline report with no PREREGISTRATION.md was not flagged, so the "
        "real-repository guard below is asserting nothing."
    )


def test_a_report_beside_its_preregistration_is_accepted(tmp_path: Path) -> None:
    """The other half of the control: the guard must not fire when the ordering holds.

    Paired with the test above, each is the other's anti-vacuity control — a helper that
    always flagged would pass that one and fail this one, and a helper that never flagged
    would do the reverse. Only a helper that actually looks satisfies both.
    """
    (tmp_path / "reports" / "baseline").mkdir(parents=True)
    (tmp_path / "reports" / "baseline" / "bakeoff.md").write_text("a number", encoding="utf-8")
    (tmp_path / PREREGISTRATION).write_text("the commitment", encoding="utf-8")

    assert _reports_without_preregistration(tmp_path) == [], (
        "a report was flagged even though its pre-registration is committed beside it. The "
        "guard would then block the bake-off slice it exists to sequence, not to prevent."
    )


def test_no_report_may_exist_without_its_preregistration() -> None:
    """A baseline report can never land in a tree that lacks its pre-registration.

    `docs/ROADMAP.md:481-482` requires this document committed *"before any number exists"*,
    and the bake-off under `reports/baseline/` produces the first per-source numbers this
    project will hold. A headline rule written once those are visible is not a commitment.

    **What this proves, and what it does not.** It proves the two cannot co-exist in the wrong
    order *in a working tree*. It does **not** prove temporal ordering: a single commit adding
    both would satisfy it. The temporal claim is verifiable only by `git log`, and § 9 of
    `PREREGISTRATION.md` gives the exact command. The bound is stated here rather than left
    for a reader to discover, because a guard that is quietly weaker than it looks is the
    shape of problem this repository exists to refuse.
    """
    offenders = _reports_without_preregistration(REPO_ROOT)
    assert offenders == [], (
        f"reports exist without {PREREGISTRATION}: {offenders}\n\n"
        "WHY THIS IS A FAILURE: the pre-registration's entire value is that it precedes the "
        "first number. A report committed into a tree without it means the headline rule was "
        "either never fixed or was fixed with a result already visible, which is the post-hoc "
        "selection docs/ROADMAP.md § 6 exists to prevent."
    )


def test_the_roadmap_p1_records_that_no_criterion_remains_open() -> None:
    """P1's open-criterion count has now moved twice, and this guard moves with it.

    **The count is slice-scoped by design, and both superseded spellings are recorded here.**
    The test was written when `docs/ROADMAP.md:364` read *"Two criteria remain open, and
    neither is nearly done"*; slice 4 landed `PREREGISTRATION.md` and the sentence became
    *"One criterion remains open"*, which is what this guard required until now. Slice 5 closes
    the last one: the bake-off ran and `reports/baseline/` exists. So the required literal has
    changed for the second time — that is the point of it. A count phrased so that it can never
    go stale is a count that says nothing, and `CLAUDE.md` requires a capability to be written
    up in the commit that lands it.

    Both earlier spellings are forbidden rather than merely un-required, so the sentence cannot
    regress to a smaller number than the tree actually holds.
    """
    phases = _flat(_section(_read("docs/ROADMAP.md"), "4. Phases"))
    for superseded in ("Two criteria remain open", "One criterion remains open"):
        assert superseded not in phases, (
            f"docs/ROADMAP.md § 4 still says {superseded!r}, but both `PREREGISTRATION.md` and "
            "`reports/baseline/` exist in this tree.\n\n"
            "WHY THIS IS A FAILURE: the roadmap is the authoritative technical plan until "
            "ARCHITECTURE.md exists. A reader planning the next slice would size work that is "
            "already done, which is the staleness the guards above this one exist to catch."
        )
    assert "No criterion remains open" in phases, (
        "docs/ROADMAP.md § 4 no longer states how many P1 criteria are open. The check above "
        "asserts absences, which deleting the paragraph would satisfy; this is the control "
        "that stops that, and it is what tells the next slice that P1 is closed."
    )


def test_the_roadmap_does_not_overstate_the_siblings_unfilled_gate() -> None:
    """The roadmap made a factual claim about a sibling project, and it went stale in a day.

    `docs/ROADMAP.md:456-460` said the sibling project's `PHASE0_RESULTS.md` *"still carries 20
    `TO-BE-FILLED` markers"*. That was exactly true at its `801b457` (2026-07-28) and
    false by `77adc8f` (2026-07-29), which filled the document and recorded a PIVOT — a
    negative result, published. Verified by `grep -c TO-BE-FILLED` at the time of writing: 0.

    **A claim about another project's honesty, inside our own section about honesty, must not
    be the stale one.** The replacement cites its own *"Ordering: what actually happened"*
    admission — that its criteria were fixed in a planning file and never copied into the
    document publishing the number before the run. That is a historical fact and cannot
    un-happen, so unlike a live marker count it cannot re-stale.
    """
    phases = _flat(_section(_read("docs/ROADMAP.md"), "4. Phases"))
    assert "still carries 20" not in phases, (
        "docs/ROADMAP.md § 4 still claims the sibling's PHASE0_RESULTS.md carries 20 "
        "TO-BE-FILLED markers. It carries none — the document was filled on 2026-07-29 and "
        "records a PIVOT.\n\n"
        "WHY THIS IS A FAILURE: this repository's premise is not fooling yourself, and the "
        "sentence sits in the phase about publishing an honest number. Overclaiming about a "
        "sibling project's failure, in that paragraph, is the worst place in the document to "
        "be wrong."
    )
    assert "was not copied into the document that publishes the number" in phases, (
        "docs/ROADMAP.md § 4 no longer carries the corrected reading of the sibling's gate. The "
        "check above asserts an absence, which deleting the paragraph would satisfy — and the "
        "lesson is the reason PREREGISTRATION.md sits at the repository root."
    )


def test_every_roadmap_citation_in_the_preregistration_resolves() -> None:
    """The document's citations must point at the lines they name, not near them.

    This guard exists because the slice that wrote `PREREGISTRATION.md` broke it. The same
    commit corrected a stale paragraph in `docs/ROADMAP.md` § 4, and that correction pushed
    every later section down by about twenty lines — so five citations written against the
    pre-edit file pointed into the wrong section by the time the commit landed. An adversarial
    review caught it; nothing in this module did, because every other guard here asserts
    substrings and a substring does not know what line it is on.

    A document whose stated value is that a stranger can check it (`PREREGISTRATION.md:13`)
    cannot ship pointers that dissolve when the target is edited. So each citation is paired
    with an anchor that must appear **inside the lines it names**, and the pairing is asserted
    to be exhaustive in both directions: a citation with no anchor fails, and an anchor for a
    citation the document no longer makes fails too. Adding a citation therefore forces adding
    its anchor, which is the only version of this guard that cannot rot quietly.
    """
    prereg = _read(PREREGISTRATION)
    lines = _read("docs/ROADMAP.md").splitlines()

    cited = set(re.findall(r"docs/ROADMAP\.md:(\d+)-(\d+)", prereg))
    assert cited, (
        "no docs/ROADMAP.md citations parsed out of PREREGISTRATION.md, so this guard would "
        "pass vacuously. Either the citation style changed or the document lost them."
    )
    assert {(start, end) for start, end, _ in ROADMAP_CITATIONS} == cited, (
        "the citation table in this module and PREREGISTRATION.md disagree.\n"
        f"  cited but unanchored: {sorted(cited - {(s, e) for s, e, _ in ROADMAP_CITATIONS})}\n"
        f"  anchored but uncited: {sorted({(s, e) for s, e, _ in ROADMAP_CITATIONS} - cited)}\n\n"
        "WHY THIS IS A FAILURE: an unanchored citation is unchecked, and an anchor for a "
        "citation that no longer exists is a guard watching nothing. Either way the next line "
        "shift goes unnoticed, which is exactly how these five citations broke."
    )

    for start, end, anchor in ROADMAP_CITATIONS:
        cited_text = _flat("\n".join(lines[int(start) - 1 : int(end)]))
        assert anchor in cited_text, (
            f"PREREGISTRATION.md cites docs/ROADMAP.md:{start}-{end}, but those lines do not "
            f"contain {anchor!r}.\n\n"
            "WHY THIS IS A FAILURE: docs/ROADMAP.md was edited and the citation was not "
            "recomputed, so the pre-registration now points a reader at the wrong section. "
            "The document's whole claim is that a stranger can check it against its sources."
        )
