"""Generation on Torch, so the loop is not Apple Silicon's alone (M6).

M3 gave this repository a second **trainer** and stopped there, which turned out to be half a
runtime. `sampling_engine` and `gate_engine` both reach `mlx_lm` directly, so on a machine
without Metal the loop could train an adapter and could not draw a single rollout or score a
single gated evaluation. That is exactly the shape the portability arm ran in: it trained on
Linux from examples night #1 had already drawn **on the Mac**, and has never generated a token.

Three things have to be true for the second engine to be worth having, and all three are asserted
here rather than argued:

1. **The prompt is sliced back off.** `mlx_lm.generate.generate` returns the completion alone;
   `transformers.generate` returns the prompt's tokens followed by the completion's. Decoding the
   whole sequence hands the extractor the task's own prompt — which contains the failing test and
   often the fix — and a model that solved nothing scores as having solved everything. This is
   the single most dangerous difference between the two libraries and it fails *silently*.
2. **The gate stays greedy.** `gate_engine` decodes with `sampler_for(1)`, which is
   `greedy_sampler` by identity, so a single-draw gate evaluation and the bake-off are one
   experiment. A sampled gate would make a promotion decision depend on a draw.
3. **The engine follows the artefact, not the host.** `gate_engine_for` dispatches on the
   checkpoint's own recorded backend, `fuse.fuser_for`'s rule: pointing MLX's loader at a Torch
   adapter does not raise, it emits weights, and the gate would publish a promotion decision
   about a model nobody trained.

Nothing here loads a model. `TorchGenerator`'s decode path is exercised against a fake tokeniser
and a fake model, because the property being checked is *what this class does with what the
library returns* — which is where the slicing bug lives — and pinning it must not require an
inference stack. CI is a machine with neither runtime installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from whetstone.bakeoff.generator import Generator
from whetstone.loop import backend, gate, sampling, torch_runtime


def _model_dir(tmp_path: Path, name: str = "base") -> Path:
    directory = tmp_path / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config.json").write_text("{}", encoding="utf-8")
    return directory


def test_the_night_engine_and_seeder_are_chosen_by_the_runtime_that_was_detected() -> None:
    """The hole M3 left: the trainer was dispatched and the engine was not.

    A night on a Torch host recorded `torch` in its ledger, trained with PEFT, and then reached
    for MLX to generate — which on a machine without the extra is not a wrong number, it is no
    night at all.
    """
    assert sampling.engine_for(backend.MLX) is sampling.sampling_engine
    assert sampling.seeder_for(backend.MLX) is sampling.mlx_seeder
    assert sampling.engine_for(backend.TORCH) is torch_runtime.torch_sampling_engine
    assert sampling.seeder_for(backend.TORCH) is torch_runtime.torch_seeder


@pytest.mark.parametrize("historical", ["torch-cpu", "torch-cuda", "torch-mps"])
def test_the_legacy_backend_spellings_still_choose_the_torch_engine(historical: str) -> None:
    """This repository's only real checkpoint records `torch-cpu`, sealed inside its digest."""
    assert sampling.engine_for(historical) is torch_runtime.torch_sampling_engine
    assert sampling.seeder_for(historical) is torch_runtime.torch_seeder


def test_the_seeder_and_the_engine_are_dispatched_separately() -> None:
    """They seed different globals, so pairing one runtime's engine with the other's seeder
    records seeds that were applied to state nothing read — and the ledger would look complete.
    """
    assert sampling.seeder_for(backend.TORCH) is not sampling.mlx_seeder, (
        "WHY THIS IS A FAILURE: a Torch night would seed `mx.random`, which nothing it runs "
        "reads. Every draw would be unreproducible and every recorded seed would be fiction"
    )


class _FakeTokenizer:
    """Returns a fixed token count for the prompt and decodes ids back to a marker string."""

    pad_token_id = 0

    def __init__(self, prompt_tokens: int) -> None:
        self.prompt_tokens = prompt_tokens

    def __call__(self, prompt: str, return_tensors: str = "pt") -> Any:
        return _FakeEncoding(self.prompt_tokens)

    def decode(self, ids: Any, skip_special_tokens: bool = True) -> str:
        return "".join(str(one) for one in ids)


class _FakeEncoding(dict[str, Any]):
    def __init__(self, prompt_tokens: int) -> None:
        super().__init__(input_ids=_FakeTensor([0] * prompt_tokens))

    def to(self, device: str) -> _FakeEncoding:
        return self


class _FakeTensor(list[int]):
    @property
    def shape(self) -> tuple[int, ...]:
        return (1, len(self))


def test_the_prompt_is_sliced_off_by_token_count(tmp_path: Path) -> None:
    """The bug that would have made every night score as a perfect one, silently.

    `transformers.generate` returns prompt tokens followed by completion tokens. If the whole
    sequence were decoded, the extractor would receive the task's own prompt — which holds the
    failing test and frequently the fix — and a base that wrote nothing would look like a base
    that solved everything. Nothing about that failure looks wrong in a log.
    """
    generator = torch_runtime.TorchGenerator.__new__(torch_runtime.TorchGenerator)
    generator._tokenizer = _FakeTokenizer(prompt_tokens=4)  # type: ignore[attr-defined]
    generator._device = "cpu"  # type: ignore[attr-defined]
    generator._draws = 1  # type: ignore[attr-defined]
    generator._max_tokens = 16  # type: ignore[attr-defined]

    class _FakeModel:
        def generate(self, **kwargs: Any) -> list[list[int]]:
            # Four prompt tokens, then three of completion.
            return [[0, 0, 0, 0, 7, 8, 9]]

    generator._model = _FakeModel()  # type: ignore[attr-defined]

    import sys

    sys.modules.setdefault("torch", _FakeTorch())
    answer = generator.generate("a prompt of four tokens")

    assert answer == "789", (
        f"WHY THIS IS A FAILURE: the completion is {answer!r}. The prompt's four tokens were not "
        "sliced off, so the extractor receives the task's own prompt back — and a model that "
        "produced nothing is scored as having produced the answer it was shown"
    )


class _FakeTorch:
    """Just enough `torch` for the decode path: `no_grad` as a context manager."""

    class no_grad:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *exc: object) -> bool:
            return False


def test_the_gate_engine_is_chosen_by_the_checkpoint_not_the_host(tmp_path: Path) -> None:
    """`fuse.fuser_for`'s rule, one layer up: the wrong loader emits weights rather than raising."""
    torch_trained = _checkpoint(backend_name="torch-cpu")
    mlx_trained = _checkpoint(backend_name=backend.MLX)

    assert gate.gate_engine_for(torch_trained) is torch_runtime.torch_gate_engine, (
        "WHY THIS IS A FAILURE: a Torch-trained candidate would be scored through MLX's loader. "
        "That does not raise — it produces weights — so the gate would publish a promotion "
        "decision about a model nobody trained"
    )
    assert gate.gate_engine_for(mlx_trained) is gate.gate_engine


def test_an_untrained_checkpoint_follows_rather_than_choosing() -> None:
    """Nothing trained it, so it records no backend and has no runtime of its own to claim."""
    untrained = _checkpoint(backend_name=None)

    assert gate.gate_engine_for(untrained) is gate.gate_engine, (
        "WHY THIS IS A FAILURE: an untrained checkpoint claimed a runtime. It is the base, "
        "loaded alone; the side it is compared against is what decides the engine"
    )


class _Checkpoint:
    """The two fields `gate_engine_for` reads, and nothing else."""

    def __init__(self, backend_name: str | None) -> None:
        self.backend = None if backend_name is None else {"name": backend_name}
        self.untrained = backend_name is None
        self.directory = Path("/nowhere")


def _checkpoint(*, backend_name: str | None) -> Any:
    return _Checkpoint(backend_name)


def test_a_repo_id_is_refused_before_any_library_is_imported(tmp_path: Path) -> None:
    """`from_pretrained` treats anything not on disk as a Hub id and downloads it at call time.

    Refused at construction, on the path check alone, so the refusal works on a machine with no
    Torch installed at all — which is where an operator most needs to be told they typed a repo
    id rather than a directory.
    """
    with pytest.raises(torch_runtime.NotALocalModelDirectory) as refused:
        torch_runtime.TorchGenerator(
            "Qwen/Qwen2.5-Coder-0.5B-Instruct", revision="ea3f2471", draws=8, max_tokens=64
        )
    assert "DOWNLOADS" in str(refused.value)


def test_a_blank_revision_is_refused(tmp_path: Path) -> None:
    """A blank revision serialises into the ledger as a field that identifies nothing."""
    with pytest.raises(ValueError, match="revision must name"):
        torch_runtime.TorchGenerator(
            _model_dir(tmp_path), revision="   ", draws=8, max_tokens=64
        )


def test_an_adapter_path_that_is_not_a_directory_is_refused(tmp_path: Path) -> None:
    """Loading the base alone in place of a missing adapter scores the comparison as a tie."""
    with pytest.raises(torch_runtime.NotALocalModelDirectory) as refused:
        torch_runtime.TorchGenerator(
            _model_dir(tmp_path),
            revision="ea3f2471",
            draws=1,
            max_tokens=64,
            adapter_path=tmp_path / "absent",
        )
    assert "tie" in str(refused.value)


def test_the_torch_generator_conforms_to_the_generator_protocol() -> None:
    """Asserted rather than assumed: `sweep`, `score` and the gate see only this surface."""
    assert issubclass(torch_runtime.TorchGenerator, Generator)


def test_the_torch_sampler_string_is_not_a_copy_of_mlxs() -> None:
    """The two libraries do not implement the same sampler, so they must not claim to.

    `transformers` renormalises after the top-p cut and applies temperature in a different order
    from `mlx_lm.sample_utils.make_sampler`. The temperature and the cut-off are shared by
    identity; the sentence describing what they mean is not, because a ledger that said the same
    words for both would assert a parity nothing here establishes.
    """
    rendered = torch_runtime.TORCH_SAMPLER.format(
        temperature=sampling.TEMPERATURE, top_p=sampling.TOP_P
    )

    assert rendered != sampling.SAMPLER
    assert "transformers" in rendered and "torch.manual_seed" in rendered
    assert str(sampling.TEMPERATURE) in rendered and str(sampling.TOP_P) in rendered, (
        "WHY THIS IS A FAILURE: the recorded sampler does not name the temperature and cut-off "
        "it actually used, so two runs at different settings would be indistinguishable in the "
        "ledger"
    )
