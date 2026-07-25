---
name: whetstone-report
description: Use when a Whetstone unit of work (bug, task, feature) is done and you want a brief, friendly, non-technical completion note saved on Desktop to share with the team.
allowed-tools: Read, Grep, Glob, Bash, Write
arguments: "type id"
---

# Whetstone Completion Note

A short, friendly, non-technical heads-up that a unit of work is done. Written like a teammate would write it — no jargon, no commit hashes, no checklists. Just one plain-English sentence about what changed, plus a link and a screenshot.

## Arguments

- `type` ∈ `bug | task | feature`
- `id` = the GitHub issue number, or the slug used at begin time

Usage: `/whetstone-report bug 12` or `/whetstone-report feature task-verifier`.

## When to use

- A unit of work is finished and you want to let the team know in a human way.
- You've closed (or are about to close) a GitHub issue, or merged its PR.

## Output

Markdown file saved to `/Users/aliz/Desktop/{type}-{id}-completion.md`.

Examples:
- `/Users/aliz/Desktop/bug-12-completion.md`
- `/Users/aliz/Desktop/task-pin-uv-version-completion.md`
- `/Users/aliz/Desktop/feature-task-verifier-completion.md`

## The template

One template, three small verb tweaks. Keep it warm, short, and free of technical detail.

```markdown
## #{id} - {Feature or area} - {Short Title}

Hey! Quick note that this one's {verb}.

**What changed (in plain words):**
{One or two friendly sentences. What's different for the user now. No jargon. No em dashes.}

**See it live:** {link to the PR, the console area, or the CLI command}
**Screenshot/video:** {attached, or link}

If anything looks off or you'd like a tweak, just say the word.
```

Verb per type:

| Type | Verb |
|---|---|
| `bug` | fixed |
| `task` | done |
| `feature` | shipped |

## Tone rules

- Write like you're messaging a teammate, not filing a ticket.
- Plain English only. Swap out words like *RLVR, reward signal, policy, rollout, self-play, distillation, LoRA, checkpoint, held-out set, promotion gate, reward-hacking, verifier, execution-grounded* for everyday phrasing. "It only counts as an improvement if we can re-run the work and see it" beats "the promotion gate requires a verified delta on a held-out set".
- No checklists, no testing matrices, no commit hashes, no branch names, no file paths — those live in the PR, not in this note.
- Two or three short paragraphs max. If it reads like docs, trim again.
- **Never use the em dash character `—` in the note.** It's a tell that an AI wrote it. Use a comma, a period, or a regular hyphen with spaces (`-`) instead.
- A friendly closer is welcome ("Let me know what you think.", "Happy to revisit if needed.").

## Don't over-claim (this one matters here)

Whetstone's whole product promise is that a reported gain is real and the model didn't cheat to get it. The note has to hold the same line. Plain language is not a licence to inflate:

- **Never quote a number the verifier didn't produce.** No projected gains, no "should improve things by around X". If there's no measured delta on the held-out set, the honest sentence is that this makes the measurement possible, not that it improved anything.
- **Don't say "better", "improved", or "smarter" about the model** unless a checkpoint actually cleared the promotion gate. Building the machinery is not the same as moving the number.
- **Don't call something verified when it came back unverified.** If the honest outcome was "we couldn't check this", say that in plain words. It reads better than an oversold claim, and it's the same discipline the loop enforces.
- If the work is a slice of a bigger capability, say it's a first step rather than implying the whole nightly loop landed.
- The model stays on the user's machine. Don't describe anything in a way that implies data went somewhere it didn't.

## Workflow

1. **Get the context.** Prefer the GitHub issue if reachable; otherwise use the merged PR or what we just did:
   ```bash
   gh issue view "$ID" 2>/dev/null || gh pr view "$PR" 2>/dev/null
   ```
   If neither resolves, write the note from the work you just completed in this session.
2. **Distill** the change into one or two plain sentences. Resist the urge to add detail.
3. **Check whether there's a real number.** If the work produced a measured delta or a caught-hack count, use the actual figure and say what it was measured on. If it didn't, say what the work enables instead. Never split the difference with a vague "notable improvement".
4. **Pick the "See it live" target** that fits the work: the merged PR link, the dashboard page (e.g. `http://localhost:3000/...`) once it exists, or the exact CLI command a teammate would run (`uv run whetstone ...`). For loop-internal work with no visible surface yet, the PR is the honest answer — don't invent a demo that doesn't run.
5. **Ask the user for a screenshot or short video** if one isn't already on hand.
6. **Write** the note to `/Users/aliz/Desktop/{type}-{id}-completion.md` and tell the user it's ready.

## Optional: cross-check

Only include if the user explicitly asks for it. Append one short, friendly line:

```markdown
**Also checked:** {a couple of related areas you peeked at, in plain words}
```

Don't add this by default — it makes the note look like an audit.

## Example (feature)

```markdown
## #34 - Overnight run - Only count a win we can re-check

Hey! Quick note that this one's shipped.

**What changed (in plain words):**
When the overnight run thinks it made the model better, it now has to prove it on a set of tasks it never trained on, by actually running them. If it can't show the improvement, nothing gets kept and the morning note says so instead of quietly claiming a win.

**See it live:** run `uv run whetstone report --last-night` and look at the summary line
**Screenshot/video:** attached

If anything looks off or you'd like a tweak, just say the word.
```
