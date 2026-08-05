# Aspect spec — instrumentation

**Feature:** `p2-yield-probe` · **PRD:** `docs/planning/p2-yield-probe/prd.md`
**Covers:** R1, R2, D5, D2a. **Does not cover:** the search/replace converter (R3–R5), the report
(R7–R8), or the pre-registration amendment (D8) — those are later aspects.

---

## Why this aspect exists

`reports/baseline/` records that 142 of 152 verdict-reaching rollouts never got a patch onto disk,
and **nothing on disk can say why**. `bakeoff/scoring.py:432-435` generates a completion, extracts
from it, and drops the text. `NOT_APPLIED` means only *"git refused it"*
(`verify/strict.py:171-183` → `verify/repo.py:100,108,118`), which conflates at least five distinct
causes.

PRD D2 puts diagnosis first so the format choice in the next aspect is evidence-led. This aspect
builds the instrument; running it is an operator step, and the run's output is what the next
aspect reads.

## The design decision this aspect turns on

**Instrumentation is a `Generator` wrapper, not a new parameter.**

`generator.py:44-70` makes `Generator` a one-method `Protocol` on purpose: *"A seam with two
methods is a seam whose implementations can disagree about which one the caller uses."* Threading a
transcript sink through `score()` → `sweep()` → `run()` would widen three signatures and put a
recording concern inside the scoring path.

Instead a `RecordingGenerator` **implements `Generator`** and delegates. `score()`,
`sweep()` and every existing test are untouched. It composes with the existing `Sealed` wrapper
(`run.py:180-208`), and it goes **outside** it so a `ContractChanged` refusal still raises
uninstrumented rather than being recorded as a generation that happened.

## Acceptance criteria

**AC1 — a wrapper records what was sent and what came back.**
`RecordingGenerator(inner, sink)` satisfies `isinstance(x, Generator)`, returns `inner`'s
completion **unchanged**, and writes one record per call carrying the prompt, its SHA-256, the
completion text, and the candidate and task it belongs to.

**AC2 — the completion is returned unaltered.**
Asserted byte-for-byte against a stub, including for a completion containing no diff, an empty
string, and non-UTF-8-safe content. A recorder that normalised its passthrough would change the
thing it exists to observe.

**AC3 — a refused prompt is not recorded as a generation.**
Composed as `Recording(Sealed(engine))`, a prompt outside the frozen contract raises
`ContractChanged` and **no** transcript record is written for it.

**AC4 — replay re-derives extraction offline, with no model.**
Given a transcript, `extract_patch` re-run over the stored completion yields the same `Extraction`
the live run produced. Asserted with no `mlx` import anywhere in the test.

**AC5 — the cause breakdown is derived, and its taxonomy is provisional.**
Replay classifies each non-applying rollout using `patch.py`'s **own** outcomes and reasons as the
source of truth, not a taxonomy invented here (PRD § 8 flags the invented one as 🔴). At minimum it
separates: no fenced block; a diff header with no hunk; truncated before the first hunk; extracted
but git refused to parse; extracted and parsed but git refused to apply. The last two require a
checkout and are distinguished by which of `verify/repo.py`'s three `PatchError` sites fired.

**AC6 — the transcript never lands in the repository.**
Its documented home is a gitignored root (`.gitignore:20-24`). A test asserts, via
`git check-ignore`, that the documented path is ignored, and that the transcript is not written
under `--out`. For source B a completion quotes the user's private donor code, so this is a
locality guarantee, not tidiness.

**AC7 — the reproduction check compares against the committed record, as far as it goes.**
**Amended 2026-08-05, on building it.** This criterion asked for a per-`(candidate, task_id)`
comparison. That cannot be made against the record that exists: `reports/baseline/report.json`
carries per-candidate *counts* and no per-task field, and the P1 run's journal — which is
per-task — was never committed, because `--journal` is undefaulted and its output belongs under a
gitignored root. Verified on this machine: no journal or run artifact from the P1 bake-off
survives.

So the comparison is over counts, and it is **necessary but not sufficient**: two runs can agree
on every count while disagreeing about which tasks produced them, since one task moving from
`no_diff` to `not_applied` and another moving the other way cancels exactly. `compare_to_counts`
says so in its own docstring, `tests/bakeoff/test_reproduction.py` asserts the premise against the
real file, and a caller may not describe a clean result as per-task reproduction. **Any divergence
is still a finding that halts the slice** (PRD D2a).

Forward-looking, and it costs nothing to state: a run invoked with `--journal` *and*
`--transcript` **is** per-task checkable afterwards. That is the reason to always pass both, and
it is what makes arm A's own successor stronger than arm A can be about P1.

**AC8 — nothing on the reward path changes.**
No file under `src/whetstone/verify/` is modified; `GUARDED_ROOTS` is not widened;
`tests/test_no_inference_on_reward_path.py` and
`tests/test_reward_path_scope_is_partitioned.py` pass unchanged.

**AC9 — no figure is published by this aspect.**
Instrumentation produces local artifacts only. The breakdown is a figure about a model and may not
be written into any document; it reaches a reader only through the next aspect's report.
`tests/bakeoff/test_report.py:961`'s file list is **unchanged** by this aspect.

## Out of scope

Changing the prompt, the extractor, or the token budget; publishing anything under `reports/`;
amending `PREREGISTRATION.md`; and the arm-A run itself, which is an operator action after this
lands.

## Open, and deliberately so

- **Whether "hit the token cap" is measurable.** `mlx_runtime.generate` returns text with no finish
  reason (`mlx_runtime.py:206-221`), so truncation is *inferred* from `patch.py`'s
  truncated-mid-hunk and truncated-before-first-hunk cases rather than measured. Recording a token
  count would need a second method on the seam, which AC1's design exists to avoid. Inference is
  used, and the report must say so rather than implying a measurement.
