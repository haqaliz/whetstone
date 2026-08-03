# Whetstone: Vision

> A model that trains itself overnight — and proves it didn't cheat.

---

## The bet in one sentence

The valuable, defensible problem in self-improving models is not the RL algorithm — it is
the **reward**. Make the reward an **unhackable, execution-grounded verifier** and
self-improvement stops being a frontier-lab privilege: it runs overnight, on one machine, on
the user's own tasks, with a signed proof that the gains are real and the model didn't cheat.
Whetstone is that loop.

---

## Why now

- **RLVR is the frontier.** Reinforcement learning from *verifiable* rewards is how models
  are getting better at tasks with checkable outcomes — and it's newly within reach of a
  solo engineer with an open base model and a good verifier.
- **Reward-hacking is the open wound.** The moment the reward is soft or an LLM judge, the
  policy learns to game it (judges are foolable — up to 35% false positives; models rewrite
  the timer instead of doing the work). The unlock is a reward that *can't* be gamed.
- **The environments are missing.** Karpathy (Sequoia 2026): the valuable RL environments
  "aren't in the frontier-lab mix." The verifiable-reward substrate is the gap — and the moat.
- **Local + private is finally practical.** Small open models + local runtimes make an
  overnight, on-device improvement loop real, with the user's data never leaving the box.

---

## The founder's unfair advantage

The moat is **engineering** — the RL/self-play loop, the unhackable execution-grounded
verifier, distillation into a small local model, and the evaluation machinery. That is
exactly a **full-stack developer + ML engineer's** edge. Whetstone needs **no** frontier
lab, proprietary dataset, or credential the founder lacks.

---

## Why it's defensible ("gets better as base models improve")

A stronger open base gives a better starting policy and cleaner distillation — it makes
Whetstone *better*, never redundant. The durable core is the verifier, the never-regress
promotion gate, and the compounding record of verified improvements. A better base can't
substitute for a reward that can't be gamed.

---

## Positioning

- **Not a frontier base model.** We sharpen an open base on the user's tasks.
- **Not judge-rewarded RL.** The reward is execution-grounded; that's the whole point.
- **Honest by contract:** promote only on a proven verified gain; `UNVERIFIED` is never a
  win; publish the real delta *and* the reward-hacking attempts caught.

## Relationship to the sibling project

The sibling project proves a single run is correct. Whetstone uses that kind of proof as an
unhackable **reward** to make the model better over time. Verification and improvement, two sides
of the same thesis — and two projects that reinforce each other.

## The wedge → the story

1. **OSS harness:** the nightly verified-improvement loop for one airtight task family. Free,
   local, self-hostable. Publish the harness + the first honest numbers.
2. **Reputation:** "verified self-improvement on a laptop, with proof it didn't cheat" — a
   narrative, not a feature; a benchmark/method others cite and build on.
3. **Later:** more task families, a managed/team layer, the verified-improvement corpus as an
   asset.

---

## Non-goals

- Training frontier base models, or anything requiring a lab / proprietary data.
- LLM-judge rewards dressed up as verification.
- Shipping a regression, or a hyped number the verifier can't back.
- Any design a better base model would make redundant.

---

## The one-line mantra

**Sharpen it every night against an edge it can't fake — and prove the edge held.**
