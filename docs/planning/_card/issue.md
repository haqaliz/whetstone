# Card — portability-cpu-dtype

**Source:** inline brief (no GitHub issue exists for this slug; `gh issue list --search`
returns only closed #30/#33/#40/#42/#45/#55/#61 and open #62/#64, none of which is this work).
Fetched 2026-10-11 from the primary checkout; branch `feat/portability-cpu-dtype/aliz`.

## Brief

Change the portability arm's declared CPU precision from `float32` to `bfloat16`
(`DEVICE_PRECISION["cpu"]`, `src/whetstone/loop/torch_runtime.py:53-57`) as a pinned module
constant — never a per-run flag, in the shape of `sampling.K` (`src/whetstone/loop/sampling.py:79`).
`docs/ROADMAP.md` § 13 records that this is the arm's one remaining *code* lever for a larger
base: *"The Torch runtime loads `float32` on CPU by declaration. The 3B base already occupies most
of the declared host's memory; a 7B would need roughly twice what the machine has and cannot be
loaded at all. So **3B is the largest base this runtime supports as written**"* (`:784-787`).

The change must be a **Type 1 `PREREGISTRATION.md` amendment**, *"a code change and an amendment
and alter[ing] what every earlier figure was measured under"* (`docs/ROADMAP.md:788-789`),
committed **before** the night that records the new dtype (`PREREGISTRATION.md` § 8.1).

## Why now

`docs/ROADMAP.md` § 13 (`:769-792`) and § 14's 2026-10-11 correction (`:882-894`) name the
P2 pivot's remaining *untried* responses: **raise k** (demoted — see `docs/ROADMAP.md:991-992`
and `docs/planning/whole-function-edit-finding/measurement-run/finding.md` § 6) and **the
portability arm's CPU dtype**. The patch-representation axis (M1) was measured NO-GO in all
three forms (`docs/planning/whole-function-edit-finding/measurement-run/finding.md`,
`docs/planning/edit-contract-finding/measurement-run/finding.md`,
`docs/planning/patch-representation/finding.md`), so the representation is spent.

## Related issues (all closed; context only)

- **#30** `backend.TORCH_CUDA` → `TORCH` — the backend name is the comparability key; the
  accelerator belongs in `Backend.device`. Precedent for "the record must not silently absorb
  a comparability-relevant fact."
- **#32/#33/#34** the arm's first run's provenance defects; the capacity probe/ceiling shape.
- **#42** four source-B tasks do not mint on Linux — a task is a property of a commit *on a
  platform*.
- **#45/#61** a ledger naming the wrong runtime — the same class as recording the wrong dtype.
