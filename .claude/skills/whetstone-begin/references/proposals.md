# Phase A — Diagrams & proposal PDFs

Runs after the PRD approval gate. Everything is written inside the worktree under
`docs/planning/{slug}/`.

## 1. Diagrams (`excalidraw`)

Use the `excalidraw` skill. Decide how many diagrams the work actually needs —
don't pad. Typical set for Whetstone:

| Diagram | When to include |
|---|---|
| System / architecture | Almost always — where the change lives in the nightly loop: task family → verifier → self-play/RL → distillation → promotion gate → morning report |
| Data flow | Data moves across steps (user's tasks → rollouts → execution-grounded reward → training set → checkpoint → held-out eval → report) |
| Sequence | A multi-step interaction matters (a night: sample tasks, roll out, verify, train, evaluate, promote-or-discard, report) |
| Before / after | Behavior or structure changes visibly |
| State machine | A checkpoint lifecycle changes (candidate → evaluated → promoted / rejected / `UNVERIFIED`) |

Save sources to `docs/planning/{slug}/diagrams/`, descriptive names
(e.g. `architecture.excalidraw`, `nightly-loop.excalidraw`).

**Every text element must set `fontFamily: 2` (Helvetica)** — the excalidraw default is hand-drawn (Virgil/Excalifont) and unreadable in stakeholder PDFs. See the excalidraw skill's Rule 5.

**Diagram the loop honestly.** Two rules, and they are the whole product:

- **The reward arrow ends at execution, never at a model.** If a diagram shows where the reward comes from, it comes from re-execution against the verifier. A cloud teacher model may appear — but only on the *distillation* path, never on the reward path. A diagram that shows a model scoring the policy is drawing a different product.
- **The gate has three exits, not one.** Promotion is `promoted` / `rejected` / `UNVERIFIED`, and `UNVERIFIED` is never collapsed into `promoted` for visual tidiness. If the diagram shows a gain, label whether it's a *target* (unmeasured) or a *measured* delta on the held-out verified set.

## 2. Export to SVG (`excalidraw-to-svg`)

Use the `excalidraw-to-svg` skill to render every `.excalidraw` to a sibling `.svg`.
Batch-export the whole `diagrams/` directory. SVG (not PNG) keeps text crisp in the PDF.

## 3. Write the two proposals

Markdown, in `docs/planning/{slug}/proposals/`. Embed the SVGs with **relative** paths
(`../diagrams/architecture.svg`) so `md-to-pdf` inlines them. Generate the two
concurrently — same PRD + diagrams, different audience.

### `<type>-<id>-technical-proposal.md` (engineers)

Filename is prefixed with the type and id (e.g. `feat-task-verifier-technical-proposal.md`) so stakeholders can identify which unit of work a proposal belongs to at a glance.

- **Summary** — one paragraph: what we're building and why.
- **Current state** — how it works today (link before/after diagram).
- **Proposed design** — architecture + components (embed architecture/data-flow/sequence SVGs).
- **Data & interface changes** — task format, verifier contract, reward signal, checkpoint/eval artifacts, report schema.
- **Risks & trade-offs** — failure modes, reward-hacking surface introduced or closed, alternatives considered.
- **Effort & sequencing** — rough phases, dependencies. Name which core-loop element (① verifier, ② nightly loop, ③ promotion gate, ④ morning report, ⑤ local/private — `CLAUDE.md`) this belongs to, and the roadmap phase once `docs/ROADMAP.md` exists.
- **Open questions** — carried from the PRD.

### `<type>-<id>-non-technical-proposal.md` (stakeholders)

Same naming convention (e.g. `feat-task-verifier-non-technical-proposal.md`).

- **The problem** — in plain language, no jargon.
- **What we'll do** — the solution at a high level (embed a simplified diagram).
- **Why it matters** — value to someone who wants their model to get better at their own work, overnight, without trusting a number they can't check.
- **What changes for users** — visible impact.
- **Timeline** — rough, in weeks, not story points.
- **Risks** — stated honestly, in plain terms.

Keep the non-technical version free of stack names, code, and acronyms unless defined (spell out RL, RLVR, LoRA, distillation the first time, or drop them). Don't claim the loop proves more than it checks: a projected improvement is a target, not a result. If the honest answer is "we don't know the size of the gain yet, that's what this measures", say exactly that — an unhyped number is the product's whole positioning.

## 4. Convert to PDF (`md-to-pdf`)

Use the `md-to-pdf` skill. On macOS, point Puppeteer at system Chrome. Output lands
next to the input as `<name>.pdf`.

⚠️ **The proposals embed `../diagrams/*.svg`, which sits ABOVE the `proposals/` folder.**
md-to-pdf's file server is rooted at the markdown's own directory by default, so `../` paths
**silently render as broken images**. You MUST pass `--basedir ..` (the `{slug}` dir, which
contains both `proposals/` and `diagrams/`):

```bash
cd docs/planning/{slug}/proposals
PUPPETEER_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  md-to-pdf <type>-<id>-technical-proposal.md --basedir ..
PUPPETEER_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  md-to-pdf <type>-<id>-non-technical-proposal.md --basedir ..
```

Result: `<type>-<id>-technical-proposal.pdf` and `<type>-<id>-non-technical-proposal.pdf`.

**Verify before the approval gate (do not skip):** a missing image does NOT fail the command,
so you must *look* at the output. Render a page to an image and inspect it:

```bash
pdftoppm -png -r 70 -f 1 -l 1 <type>-<id>-technical-proposal.pdf /tmp/check   # then Read /tmp/check-1.png
```

Both PDFs must exist, be non-trivial in size, and show the diagrams (not broken-image icons).
If an image is broken, the path escaped the basedir — fix `--basedir`/filenames (URL-encode
spaces as `%20`) and re-run.

## 5. Approval gate

Present both PDFs to the user and **stop**. Only after explicit approval continue to the
`tech-plan` phase.
