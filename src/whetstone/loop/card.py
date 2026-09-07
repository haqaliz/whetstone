"""The model card: what turns a sealed checkpoint into a repository someone else can use.

A published model on the Hub is a directory whose `README.md` opens with a YAML frontmatter block
— license, base model, library, tags — which the Hub parses as the model's metadata and renders
as its card (https://huggingface.co/docs/hub/en/model-cards). `sft.write_checkpoint` already
seals the two files a LoRA needs; this writes the third, and with it the checkpoint directory
becomes an uploadable repository rather than bytes only this project can interpret.

**A rendering of evidence, never a description of it.** Every figure comes from the night's own
ledger or the checkpoint's own provenance, and this module opens no file — `build_morning_report`'s
rule, for its reason: a document free to read a published home can restate a figure whose only
home is elsewhere. It is also what makes byte-identity a property of the design rather than
something to be careful about, which matters because a card that cannot be re-derived cannot be
checked against the checkpoint it describes.

**A card for a model that does not exist is refused.** A night that wrote no checkpoint recorded
why, and rendering a card beside that reason would advertise a model nobody can download.

**The yield never appears alone.** `6 examples` grows with the number of draws and says nothing
about how much was verified, so it is printed with its denominator and its unverified count or
not at all — the discipline the morning report already applies, and a page written for strangers
has more reason to hold it, not less.

**What is unproven is stated.** This adapter has never been scored against a held-out set by the
promotion gate. A card silent on that reads as though it had passed one.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: The filename the Hub renders as a model card. Not configurable: a repository whose card is
#: called anything else has no card.
MODEL_CARD_FILE = "README.md"

#: The project's license, matching `pyproject.toml` and the roadmap's P0 exit criterion.
LICENSE = "apache-2.0"

#: The library whose loader reads `adapter_config.json` in the vocabulary this project writes.
#: Declared so the Hub's "how to use" widget points at a loader that actually works.
LIBRARY = "peft"


class NothingToPublish(ValueError):
    """The night produced no checkpoint, so there is no model for a card to describe.

    Raised rather than rendered with the figures blank. A card is a page about a model; written
    beside a night that produced none it advertises something nobody can download, and the
    absence has a stated reason that belongs in the refusal instead.
    """


def build_model_card(*, night: Any, checkpoint: Any) -> str:
    """Render one night and its checkpoint into a Hub model card. A pure function of the two.

    `night` is a `morning.LedgerDocument`; `checkpoint` is the mapping `sft.write_checkpoint`
    sealed. Nothing else is read — no clock, no filesystem, no environment — so two renders of
    the same evidence are byte-identical and a reader can regenerate the page to check it.
    """
    if night.checkpoint_digest is None or checkpoint is None:
        raise NothingToPublish(
            f"night {night.run_id!r} wrote no checkpoint, so there is no model to publish a card "
            f"for. The night's own reason: {night.checkpoint_absent!r}"
        )

    base = checkpoint["base"]
    backend = checkpoint["backend"]
    counts = night.dataset

    return "\n".join(
        (
            *_frontmatter(base_model=base["repo_id"], run_id=night.run_id),
            "",
            f"# {night.run_id}: a LoRA adapter verified by re-execution",
            "",
            "A LoRA adapter produced by [Whetstone](https://github.com/haqaliz/whetstone), which",
            "trains a model overnight against an **execution-grounded verifier** — the reward is",
            "deterministic re-execution of the user's own tests, never an LLM judge. The classic",
            "RLVR failure mode, reward-hacking, is designed out rather than monitored for.",
            "",
            "## What produced it",
            "",
            "| | |",
            "|---|---|",
            f"| Base model | `{base['repo_id']}` |",
            f"| Base revision | `{base['revision']}` |",
            f"| Run | `{night.run_id}`, recorded {night.recorded_on} |",
            f"| Run seed | `{night.run_seed}` |",
            f"| Draws per task | {night.draws} |",
            f"| Runtime | {backend['library']} {backend['version']} on {backend['device']} |",
            f"| Training set digest | `{counts.digest}` |",
            "",
            "The seed and the base revision are the immutable inputs: the revision is a commit",
            "sha rather than a tag, because two people resolving the same tag at different times",
            "do not load the same weights.",
            "",
            "## The honest number",
            "",
            _yield_sentence(counts),
            "",
            f"- **Training examples: {counts.examples}** — every one a rollout the STRICT",
            "  verifier passed by re-running the task. `UNVERIFIED` is never training data.",
            f"- **Rollouts drawn: {counts.denominator}.**",
            f"- **Verdicts reached: {counts.coverage}.**",
            f"- **UNVERIFIED: {counts.unverified}** — outcomes the harness could not decide.",
            "  Counted and published rather than dropped: an unverified rollout is not a failure",
            "  and is emphatically not a win.",
            f"- **Validation split:** {counts.valid_split or 'held out from the training set'}.",
            "",
            "## What is *not* claimed",
            "",
            "**This adapter has not been scored against a held-out set by the promotion gate.**",
            "No delta against the base is published here, because none has been measured. A model",
            "card that omitted this would read as though a gate had passed it.",
            "",
            "What any number from this project is allowed to claim was fixed in",
            "[`PREREGISTRATION.md`](https://github.com/haqaliz/whetstone/blob/master/PREREGISTRATION.md)",
            "**before any of those numbers existed** — including the response to a low yield,",
            "which is to stratify by difficulty or raise the number of draws, never to loosen",
            "what counts as a win.",
            "",
            "## Using it",
            "",
            "```python",
            "from peft import PeftModel",
            "from transformers import AutoModelForCausalLM",
            "",
            f'base = AutoModelForCausalLM.from_pretrained("{base["repo_id"]}")',
            f'model = PeftModel.from_pretrained(base, "{night.run_id}")',
            "```",
            "",
            "The adapter is also loadable by `mlx-lm`, whose loader reads the same",
            "`adapter_config.json`; the two vocabularies share the file and do not collide.",
            "",
            "## Limitations",
            "",
            "- Trained on one operator's private task corpus. It is tuned to that code, and",
            "  nothing here measures whether it generalises beyond it.",
            "- The training set is small. Read the counts above before assuming otherwise.",
            "- No safety tuning of any kind was performed. The base model's behaviour is",
            "  otherwise unchanged, and its own card governs.",
            "",
            f"Licensed {LICENSE}. The base model's license governs the base weights.",
            "",
        )
    )


def _frontmatter(*, base_model: str, run_id: str) -> tuple[str, ...]:
    """The YAML block the Hub parses as metadata.

    Emitted by hand rather than through a YAML dumper: the block is a fixed shape with no
    user-supplied structure in it, and a dumper would make the page's bytes depend on a library
    version — which is exactly what byte-identity across renders must not depend on.
    """
    return (
        "---",
        f"license: {LICENSE}",
        f"base_model: {base_model}",
        f"library_name: {LIBRARY}",
        "pipeline_tag: text-generation",
        "tags:",
        "  - lora",
        "  - peft",
        "  - whetstone",
        "  - verified-self-improvement",
        f"model_name: {run_id}",
        "---",
    )


def _yield_sentence(counts: Any) -> str:
    """The yield, with the two figures that make it readable, in one sentence.

    Never the example count alone. A training-set size grows with the number of draws and says
    nothing about how much of the run reached a verdict, so quoting it by itself is the shape of
    number this project exists not to publish.
    """
    return (
        f"**{counts.examples} strict-PASS training examples from {counts.denominator} rollouts**, "
        f"of which {counts.coverage} reached a verdict and {counts.unverified} came back "
        "UNVERIFIED."
    )


def render_card(*, run: Path, checkpoint: Path, out: Path) -> Path:
    """The door: read the night and the sealed checkpoint, render, write, return the path.

    All the file work lives here rather than in `cli.py`, so the guarded root holds **one** new
    edge into this package instead of three. That is not tidiness — every edge from the reward's
    entry point into an exempt package is a line somebody has to defend, and three lines to reach
    one command is three times the argument for the same capability.

    **The checkpoint is re-hashed before a word is rendered from it.** A card describing bytes
    nobody can demonstrate they read is `verify_checkpoint`'s own argument applied to a published
    page: a gitignored directory can be rebuilt, truncated or hand-edited between the night that
    sealed it and the moment somebody publishes a page about it.
    """
    from whetstone.loop.morning import load_named_run, refuse_published_out
    from whetstone.loop.sft import CHECKPOINT_FILE, verify_checkpoint

    refuse_published_out(out.parent, "--out")
    night = load_named_run(run)
    verify_checkpoint(checkpoint)
    sealed = json.loads((checkpoint / CHECKPOINT_FILE).read_text(encoding="utf-8"))

    page = build_model_card(night=night, checkpoint=sealed)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out
