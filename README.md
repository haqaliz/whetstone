<p align="center">
  <img src="assets/logo.svg" alt="Whetstone" width="200">
</p>

<h1 align="center">Whetstone</h1>

<p align="center">
  <em>A model that trains itself overnight — and proves it didn't cheat.</em>
</p>

---

> **Status: early.** [`docs/ROADMAP.md`](docs/ROADMAP.md) is written and merged — it commits
> to the first task family, specifies its verifier, and phases the work through to the first
> honest number. The Python scaffold is in progress; **no reward, loop, or gate exists yet,
> and nothing has been released.** [`VISION.md`](VISION.md) holds the thesis,
> [`CLAUDE.md`](CLAUDE.md) the guardrails.

Point Whetstone at your tasks. Each night a local loop runs self-play / RL against an
**execution-grounded verifier** — never an LLM judge it can fool — distils the wins into a
small local model, and produces a signed morning report: the verified delta, what changed,
and the reward-hacking attempts caught and rejected.

The reward is deterministic re-execution, so the classic RLVR failure mode — a policy that
learns to game a soft judge instead of getting genuinely better — is designed out.

- **Local and private.** The loop, the data, and the model stay on your machine.
- **Never regress.** A checkpoint is promoted only on a proven gain over a held-out
  verified set. `UNVERIFIED` is never a win.
- **Honest numbers.** Publish the real delta and the caught hack-attempts, even when modest.

Read [`VISION.md`](VISION.md) for the thesis, the moat, and the non-goals.

## The mark

`assets/logo.svg` — a W drawn as two rounded parallelograms plus a dot. It inherits
`currentColor` and flips to a light fill on dark backgrounds.
