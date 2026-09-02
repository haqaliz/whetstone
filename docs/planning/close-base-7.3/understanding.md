# Understanding — close-base-7.3

**Written:** 2026-09-02, from the dig (Phase 2). Card: `docs/planning/_card/issue.md`.

## What the work really is

Close `PREREGISTRATION.md` § 7.3 ("Which open base is fine-tuned") by a **Type 1 amendment
under § 8.1** — a committed, dated, append-only amendment naming
`mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` at its pinned revision as the base the
nightly loop fine-tunes, **before night #1 trains**. This is the first step of the launch
path's operator chain (`docs/ROADMAP.md` § 12, corrected 2026-09-01) and a hard
precondition: § 8.1 (`PREREGISTRATION.md:266-268`) requires the amendment to precede the
measurement it governs, so the night cannot legally train until it lands.

It is a **documentation / pre-registration unit, not a code feature**: no reward path, no
gate logic, no sandbox is touched. The deliverable is the amendment itself plus the repo's
state-description files, all in one commit — the repo's own contract ("a capability is
written up in the same commit that lands it", `CLAUDE.md`).

## What the dig established

**The amendment's exact shape (the § 10.7 / § 10.8 model, `git log` on PREREGISTRATION.md):**

1. A new **§ 10.10** section, structured like § 10.8: a `**Type 1 (§ 8.1): closes § 7.3,
   committed before the night it governs runs.** It introduces no success threshold and
   rewords nothing in § 1, § 4, or § 6.` opening; a `**The base.**` block naming repo_id +
   revision + provenance home; a `**The evidence it was chosen on.**` block pointing at
   `docs/planning/larger-base-arm/finding.md` and `reports/larger-base/` (never restating a
   figure); a `**What is not claimed.**` block ("No measurement has been run under the
   night, and none is claimed here…").
2. A **new log row** appended at the bottom of the amendment log table (`:318`), columns
   Date | Amendment | Type (§ 8) | Closes an open item → **Yes**.
3. **Exactly one edit above § 10**: the open-items clause of the status paragraph
   (`:321-324`) — "§ 7.3 is still **open**" becomes "§ 7.3 is closed by the dated amendment
   below (§ 10.10)". Precedent: `df7ae15` (§ 10.7) and `c28bb55` (§ 10.8) both made exactly
   this edit. No other text above § 10 changes — § 7.3's own paragraph (including "Naming a
   base here would be the mistake") stays as first committed; the closure is recorded in
   § 10 and the log, not by rewriting § 7.

**The pin to name, byte-for-byte:** `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` @
`d1e3b690c8e225d7795bccddf971ca6be68b2012` — identical in the night runbook
(`docs/planning/p2-rollouts/night-door/runbook.md:14,57,92`), its guard
(`tests/test_night_runbook_guards.py:65`), the larger-base runbook (`:19`), the finding
(`finding.md:13,22`), and `weights/provenance.json:497-498` (gitignored, primary checkout
only — per-file sha256 records, no aggregate digest; re-hashed on every run by
`src/whetstone/bakeoff/weights.py:134`). The excluded base is
`mlx-community/Qwen2.5-Coder-7B-Instruct-4bit`.

**Evidence the amendment rests on** (cited, never restated): the larger-base arm's first
nonzero strict-PASS yield with the control discipline intact (`finding.md:41-43`), the fork
rule that routed there (`docs/planning/larger-base-arm/prd.md:46-51`), and the finding's
own statement that § 7.3 closes only by a Type 1 amendment (`finding.md:50-53`). The
figures' only home is `reports/larger-base/`; the amendment may say "first nonzero
strict-PASS yield" (no digit) but must not restate any count.

**Test trip-hazards (tests/test_docs.py):** no `%` / `percent` / `percentage` in any
position; no placeholder tokens; the phrase "no figure about a model" must remain; no
success threshold; **no new `docs/ROADMAP.md:NN-NN` citation without extending
`ROADMAP_CITATIONS`** — § 10.7/§ 10.8 cite only internal `:NN-NN` refs and file paths, and
§ 10.10 should do the same. There is no amendment-log structure guard today; the § 10.9
precedent (`d037967`, 38 lines added) shows the shape for any new guard.

**Stale-prose inventory (current-state, updated in this unit):** `CLAUDE.md:151-153` ("still
open, and now open on evidence… § 7.3 stays open" — the "Still open" section describes
master-state and must move to settled); `docs/STATUS.md` and `CHANGELOG.md` gain append-only
entries. ROADMAP § 12's operator-chain prose stays accurate (the chain starts with this
amendment). ROADMAP § 4's "no base is selected" (`:370-372`) is the dated bake-off record —
the roadmap's own convention is a dated correction blockquote around it, which belongs in
this unit or is deferred explicitly.

## Open questions for the interview

1. **Guard or no guard?** The two Type 1 predecessors landed with no test_docs.py change;
   § 10.9 added a shape guard. Does this unit pin the amendment's shape (e.g. "the log's
   last row closes § 7.3", "§ 10.10 claims no count measured here") — the repo's test-first
   contract says yes, and a shape guard is the only thing that can "watch failing first"
   for a docs amendment.
2. **ROADMAP.md § 4 correction blockquote** — add the dated "Corrected" note next to
   "no base is selected" (the convention used elsewhere, e.g. `:364-368`), or leave § 4 as
   the bake-off's dated record?
3. **How the hash is named** — provenance.json carries per-file sha256, no aggregate. Name
   the revision + the provenance home ("recorded by per-file hash in
   `weights/provenance.json`", re-hashed on every run), or mint an aggregate digest first?
   The former is honest; the latter is new machinery this docs unit does not need.
4. **What "the night's pinned input" is** — the night consumes the repo_id via `--only` and
   the revision via provenance; the amendment names exactly those two. Confirm no third
   field is owed.