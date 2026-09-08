"""The model card: a checkpoint directory that is also a publishable repository.

A published model on the Hub is a directory whose `README.md` carries a YAML frontmatter block —
license, base model, tags — and is rendered as the model card
(https://huggingface.co/docs/hub/en/model-cards). This repository already writes the two files a
LoRA needs beside it; the card is what turns them from bytes on disk into something a person can
find, load and judge.

**The card is a rendering of evidence, never a description of it.** Every number it prints comes
from the night's own ledger and the checkpoint's own provenance, and it opens no other file — the
`build_morning_report` rule, for the same reason: a document free to read a published home can
restate a figure whose only home is elsewhere. That is also what makes byte-identity a property
of the design rather than something to be careful about.

**A card for a model that does not exist is refused.** A night that wrote no checkpoint has a
reason, recorded in `checkpoint_absent`, and rendering a model card beside it would publish a
page about a model nobody can download. The refusal names the reason the night gave.

**`UNVERIFIED` is never rendered as a win**, here as everywhere. The card prints the unverified
count beside the training-set size, because a yield quoted without its denominator and its
unverified count is the number this project exists not to publish.
"""

from __future__ import annotations

from typing import Any

import pytest

from whetstone.loop import card

BASE = "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit"


def _night(**overrides: Any) -> Any:
    """A night document in the shape `morning.read_ledger` returns, with night #1's real counts."""
    from whetstone.loop import morning

    fields: dict[str, Any] = {
        "run_id": "night-001",
        "recorded_on": "2026-09-05",
        "run_seed": 20260906,
        "draws": 8,
        "model": morning.ModelRef(repo_id=BASE, revision="d1e3b690c8e2"),
        "contract": {"sampler": "categorical", "max_tokens": 2048},
        "task_set": morning.TaskCounts(
            private=61, public=1, roots=2, dev_subset=("dev-1",), probe=None
        ),
        "dataset": morning.DatasetCounts(
            digest="3416702298c36a9a", examples=6, denominator=496, unverified=102,
            coverage=394, valid_split="no valid split (strict-PASS set below floor)",
        ),
        "checkpoint_digest": "c" * 64,
        "checkpoint_absent": "",
        "tool_versions": {"python": "3.12.13", "mlx-lm": "0.31.3"},
    }
    fields.update(overrides)
    return morning.LedgerDocument(**fields)


def _provenance(**overrides: Any) -> dict[str, Any]:
    """A checkpoint provenance in the shape `write_checkpoint` seals."""
    document: dict[str, Any] = {
        "schema": "whetstone-checkpoint/1",
        "digest": "c" * 64,
        "base": {"repo_id": BASE, "revision": "d1e3b690c8e2"},
        "dataset_digest": "3416702298c36a9a",
        "run_seed": 20260906,
        "backend": {
            "name": "mlx", "library": "mlx-lm", "version": "0.31.3",
            "device": "Apple M4 Max", "device_memory_bytes": 38654705664,
        },
        "training_args": {"lora_rank": 8, "lora_scale": 20.0, "lora_dropout": 0.0, "iters": 200},
        "tool_versions": {"python": "3.12.13"},
        "validation": "no valid split (strict-PASS set below floor)",
        "capacity_probe": {"peak_bytes": 24696061952, "fits": True},
        "files": [{"name": "adapters.safetensors", "bytes": 33566554, "sha256": "a" * 64}],
    }
    document.update(overrides)
    return document


def _frontmatter(page: str) -> dict[str, Any]:
    """The YAML block the Hub reads, parsed — not regex-matched out of the prose."""
    yaml = pytest.importorskip(
        "yaml", reason="PyYAML is not installed, so the frontmatter cannot be parsed as the Hub "
        "parses it. A regex over the text would assert this repository's idea of YAML"
    )
    assert page.startswith("---\n"), (
        "WHY THIS IS A FAILURE: the page does not open with a `---` frontmatter delimiter, so the "
        "Hub renders the metadata as body text and the model has no license, no base model and "
        "no tags"
    )
    _, block, _ = page.split("---\n", 2)
    parsed = yaml.safe_load(block)
    assert isinstance(parsed, dict), (
        f"WHY THIS IS A FAILURE: the frontmatter is not a mapping: {parsed!r}"
    )
    return parsed


def test_the_card_opens_with_the_metadata_the_hub_reads() -> None:
    """AC1: the frontmatter parses as YAML and names what a Hub repository is required to name.

    Asserted by parsing rather than by searching the text: a regex that finds `license:` in prose
    would pass against a page whose metadata block is malformed and therefore ignored.
    """
    page = card.build_model_card(night=_night(), checkpoint=_provenance())
    meta = _frontmatter(page)

    for key in ("license", "base_model", "library_name", "tags"):
        assert key in meta, (
            f"WHY THIS IS A FAILURE: {key!r} is absent from the frontmatter, so the Hub cannot "
            f"categorise, license or link this model. Got {sorted(meta)}"
        )
    assert meta["base_model"] == BASE, (
        "WHY THIS IS A FAILURE: the card does not name the base it adapts, so nobody can load it "
        "— a LoRA adapter is meaningless without the weights it attaches to"
    )
    assert meta["library_name"] == "mlx", (
        "WHY THIS IS A FAILURE: this provenance records an MLX backend and the card names "
        f"{meta['library_name']!r}. PEFT cannot open an MLX adapter — different weights "
        "filename, different tensor names, transposed matrices (#31) — so the Hub's widget "
        "would hand every reader a snippet that fails on the file it just downloaded"
    )


def test_every_number_on_the_card_comes_from_the_evidence() -> None:
    """AC2: the yield is printed with its denominator and its unverified count, or not at all.

    `6 examples` alone is the number this project exists not to publish: it grows with the number
    of draws and says nothing about how much was verified. The morning report already refuses to
    print a training-set size alone, and a page meant for strangers has more reason to, not less.
    """
    night = _night()
    page = card.build_model_card(night=night, checkpoint=_provenance())

    for figure in (str(night.dataset.examples), str(night.dataset.denominator),
                   str(night.dataset.unverified)):
        assert figure in page, (
            f"WHY THIS IS A FAILURE: {figure!r} is absent. A yield quoted without its "
            "denominator and its unverified count is exactly the number this project refuses "
            "to publish"
        )
    assert "UNVERIFIED" in page.upper(), (
        "WHY THIS IS A FAILURE: the card never mentions unverified outcomes, so a reader takes "
        "the training-set size for a success rate"
    )


def test_a_night_that_produced_no_model_gets_no_card() -> None:
    """AC3: no checkpoint, no card — and the refusal repeats the night's own stated reason.

    Night #1 is the live case: 496 rollouts, controls INTACT on every one, and no checkpoint,
    because training raised. A model card rendered beside that would advertise a model nobody can
    download.
    """
    absent = _night(checkpoint_digest=None, checkpoint_absent="training raised KeyError: 'dropout'")

    with pytest.raises(card.NothingToPublish) as refusal:
        card.build_model_card(night=absent, checkpoint=None)

    assert "dropout" in str(refusal.value), (
        f"WHY THIS IS A FAILURE: the refusal does not repeat the night's own reason, so an "
        f"operator cannot tell a zero-yield night from a crashed one. Got {str(refusal.value)!r}"
    )


def test_the_card_names_the_runtime_and_the_seed_it_came_from() -> None:
    """AC4: the card is reproducible from what it prints.

    The run seed, the base revision and the runtime are what let a reader re-derive this adapter
    rather than take its word. The revision is the immutable sha, never a tag: two people
    resolving the same tag at different times do not load the same weights.
    """
    page = card.build_model_card(night=_night(), checkpoint=_provenance())

    assert "20260906" in page, "WHY THIS IS A FAILURE: the run seed is absent, so the night that "\
        "produced this adapter cannot be reproduced"
    assert "d1e3b690c8e2" in page, "WHY THIS IS A FAILURE: the base revision is absent, so "\
        "'the base model' names a moving target rather than specific bytes"
    assert "Apple M4 Max" in page and "mlx-lm" in page, (
        "WHY THIS IS A FAILURE: the runtime that produced the adapter is unnamed. Two adapters "
        "from different runtimes are not comparable, and a card silent on it invites the "
        "comparison the gate refuses to make"
    )


def test_two_renders_are_byte_identical() -> None:
    """AC5: the card is a pure function of its two documents, so it can be re-derived and diffed.

    Anything read from the clock, the filesystem or the environment would make the page differ
    from itself between two renders of the same evidence — and a card that cannot be regenerated
    cannot be checked against the checkpoint it describes.
    """
    first = card.build_model_card(night=_night(), checkpoint=_provenance())
    second = card.build_model_card(night=_night(), checkpoint=_provenance())

    assert first == second, (
        "WHY THIS IS A FAILURE: two renders of the same evidence differ, so something outside "
        "the two documents reached the page"
    )


def test_the_card_states_what_is_unproven_about_it() -> None:
    """AC6: the page says what has not been measured, not only what has.

    This adapter has never been scored against a held-out set by the promotion gate, and a model
    card that omits that reads as though it had. `PREREGISTRATION.md` fixed what any number here
    may claim before any number existed; the card points at it rather than paraphrasing it.
    """
    page = card.build_model_card(night=_night(), checkpoint=_provenance())

    assert "PREREGISTRATION" in page, (
        "WHY THIS IS A FAILURE: the card does not point at the pre-registration, so a reader has "
        "no way to check what these numbers were allowed to claim before they existed"
    )
    lowered = page.lower()
    assert "not" in lowered and ("held-out" in lowered or "gate" in lowered), (
        "WHY THIS IS A FAILURE: the card does not state that this adapter has not been scored by "
        "the promotion gate, so its silence reads as a passing grade"
    )


def test_the_card_names_the_loader_that_can_open_this_checkpoint() -> None:
    """#31: the "how to use" snippet dispatches on the runtime that trained the adapter.

    The card used to print PEFT's snippet unconditionally and add a line saying the adapter was
    "also loadable by `mlx-lm`, whose loader reads the same `adapter_config.json`". Both halves
    were wrong in the same way: the config was never what stopped the other loader — the weights
    filename, the tensor names and the orientation of the matrices all differ. A card is the
    first thing a stranger reads, so this is the surface where the error costs the most.
    """
    mlx_page = card.build_model_card(night=_night(), checkpoint=_provenance())
    assert "from mlx_lm import load" in mlx_page
    assert "PeftModel" not in mlx_page, (
        "WHY THIS IS A FAILURE: an MLX checkpoint's card offers `PeftModel.from_pretrained`, "
        "which fails on the file it just told the reader to download"
    )

    torch_page = card.build_model_card(
        night=_night(),
        checkpoint=_provenance(
            backend={
                "name": "torch-cpu", "library": "torch", "version": "2.14.0+cu130",
                "device": "cpu", "device_memory_bytes": 16637317120,
            }
        ),
    )
    assert "from peft import PeftModel" in torch_page
    assert "from mlx_lm import load" not in torch_page

    for page in (mlx_page, torch_page):
        assert "fuse it into its base" in page, (
            "WHY THIS IS A FAILURE: the card does not say how to run this adapter under the "
            "other runtime. The answer is fusing, and a reader who does not find it here will "
            "try renaming the file — which loads nothing and raises nothing"
        )
