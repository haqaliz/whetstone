# Spec — pascal-4bit / night-door

**PRD:** `../prd.md`. **Understanding:** `../understanding.md`. **Branch:**
`feat/pascal-4bit/aliz`. **Date:** 2026-11-23. **Sheet:** `runbook.md`.

## Problem slice

Move the main series' operator surface to `x202` at `torch 2.14.1+cu126` with 4-bit NF4 weights
(bf16 compute) declared by `quantize.json`, and run § 10.27's near-miss sample less its two
macOS-only tasks: 18 private + the public task = 19 tasks × 16 = **304 draws**, `--probe 18`.

## In-scope

1. **`PREREGISTRATION.md` § 10.28** (Type 1, 2026-11-23) + its log row after § 10.27's. It states
   the host (x202, 3× GTX 1080 8 GB, one GPU), the CUDA build, the unchanged base/revision, the
   4-bit NF4/bf16 sidecar, the measured 6.75 tokens/s and 6.07 GB, the 18+1 sample and the two
   excluded ids with their Darwin reasons, the unchanged K/R/repair/verifier/gate/held-out, the
   GO, the non-comparability, the MPS series not retired, the corpus-removal rule, and that no
   count is measured.
2. **`TorchGenerator.provenance()`**: one `"quantization"` key — `""` without a sidecar,
   otherwise the compact deterministic value. Reuses `QUANTIZE_SIDECAR`; no loader change.
3. **The sheet** (`runbook.md`): env block (`$REPO`, `PATH`, `UV_CACHE_DIR`,
   `UV_PYTHON_INSTALL_DIR`, `HF_HOME`, `TORCHDYNAMO_DISABLE`, `TORCH_COMPILE_DISABLE`,
   `WHETSTONE_REPO_MIRRORS`); setup (`gcc`/`g++`, `uv sync --extra torch`, the cu126 wheel,
   `snapshot_download` at the pinned revision, the exact sidecar, both donor clones and the flask
   mirror); the 30-link near-miss root; the `--probe 18` probe; the `check-probe` block; the full
   52-task night; the two decisions; the finding home and the corpus-removal rule.
4. **Guards.** `tests/test_pascal_4bit_runbook_guards.py` (14 properties, listed in its
   docstring), `tests/test_docs.py::test_the_pascal_4bit_amendment_pins_the_series`, and the
   provenance tests in `tests/loop/test_torch_engine.py`.
5. **Write-up.** `CHANGELOG.md` Unreleased, `docs/STATUS.md`, the `docs/ROADMAP.md` § 14 M1 dated
   correction.

## Out-of-scope

- Any probe or night run; any GPU job; touching `runs/` or `checkpoints/`.
- The loader, the sampler, the gate, the reward path, the corpus, the sample lists, the held-out
  document, `K`, `R`, `R_repair`.
- Retiring or extending the MPS series; restating any MPS figure.
- A `check-probe` quantization pin (the provenance key is the record).

## Acceptance (test-first)

- **Provenance.** The three new tests fail with `KeyError: 'quantization'` before the key exists:
  the sidecar value is `nf4/bf16/double`, the no-sidecar value is `""`, and key order does not
  move it. All values remain strings and the mapping remains read-only.
- **Sheet.** The guard module fails on a missing sheet and on a stub with `--probe 20`, a probe
  `--dev-subset`, relative writable paths, a worktree, `caffeinate`, missing excluded ids or no
  mirrors export. It passes only on the real sheet. The 30 prep links are exactly the 18 sample +
  the 12 committed held-out members; the 18 are in `tasks/local-ledger.json` and none is held out.
- **Amendment.** The docs test fails before § 10.28 exists; after, the section carries every pinned
  phrase and both excluded ids, and the log row follows § 10.27's.
- `uv run pytest tests/test_docs.py tests/test_pascal_4bit_runbook_guards.py -q`, the
  doc-adjacent guard set, `uv run ruff check .` and `uv run mypy src/` green; no GPU.

## Non-goals stated for the reader

A green `check-probe` is the harness rule, not the GO. A NO-GO returns the lever to a human,
never to a loosened verifier. Every figure is non-comparable to the MPS series.
