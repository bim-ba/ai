---
name: creating-drift-logs
type: skill
category: workflow
description: "Use when you notice a divergence between actual session behavior and codified instructions (one of the 8 drift triggers) — captures it as an immutable drift-log entry under .claude/drift-log/open/ so good conventions can be promoted later."
---

# Creating Drift Logs

## Purpose

A drift-log entry records a divergence between what the session actually did and what the codified instructions (`CLAUDE.md`, skills) prescribe. The goal is to surface patterns where emergent conventions outperform what is written, so official instructions can be improved.

**Use this skill when:** you notice one of the 8 triggers listed below during a session and want to capture it before it is lost.

**Do NOT use this skill for:** one-off project-specific decisions with no general applicability; pure user preferences for a single file (e.g., "rename this variable"); mistakes you made that the user corrected, unless the correction reveals a missing rule.

## Triggers and exclusions

See `rules/01-triggers.md` for the 8 numbered triggers and the do-NOT-log exclusion list.

When uncertain whether something qualifies, err on the side of logging — false positives are cheap, missed insights are expensive.

## Workflow

### Step 1: Identify the trigger

Confirm that one of the 8 triggers from `rules/01-triggers.md` applies. Note the trigger number — it goes into the entry's frontmatter.

### Step 2: Determine the slug

Choose a kebab-case slug that identifies the insight (not the file being edited). Format: `YYYY-MM-DD-<kebab-slug>`.

### Step 3: Create the entry file

Copy `templates/_template.md` to `.claude/drift-log/open/<YYYY-MM-DD>-<kebab-slug>.md` and fill in:

- Frontmatter: `date`, `status: OPEN`, `priority` (LOW / MEDIUM / HIGH), `trigger` (number), `session_context`, `affected_source` (paths), `applied_in` (omit while OPEN)
- Body sections: What diverged, Why it seemed better, Proposed change, Resolution (leave blank while OPEN)

**One insight = one entry.** Split entries by *insight*, not by target file or by the number of files a fix touches. If two observations share a root cause and would be resolved by the same edit, they are one entry.

### Step 4: Announce in chat

After creating the entry, mention it in one line: `Logged drift: open/<file>.md`

## Post-checks

- Entry file exists at `.claude/drift-log/open/<YYYY-MM-DD>-<slug>.md`
- Frontmatter includes `date`, `status: OPEN`, `priority`, `trigger`, `session_context`
- Body has no placeholder text left unfilled (except `Resolution`, which stays blank while OPEN)

## Guardrails

- **Never** edit the narrative body (`What diverged`, `Why it seemed better`, `Proposed change`) after the entry is committed — these are the immutable historical record. See `rules/02-immutability.md`.
- **Never** delete an entry — transition it through `applied/` instead. See the `reviewing-drift-logs` skill for the OPEN → APPLIED lifecycle.
- Do not log mere mistakes corrected by the user unless the correction reveals a missing rule.
- Mark repeated corrections `HIGH` — they are a strong signal of a missing or ambiguous official rule.

## Artifact Map

| Artifact | Path | Naming |
|---|---|---|
| Drift entry | `.claude/drift-log/open/YYYY-MM-DD-<slug>.md` | kebab-case slug; one file per insight |

## References Guide

- `rules/01-triggers.md` — the 8 triggers + do-NOT-log exclusions; consult first when unsure if the event qualifies
- `rules/02-immutability.md` — what is frozen after commit; consult when editing an existing entry
- `rules/03-frontmatter-schema.md` — field list, allowed values, immutable vs mutable fields; consult when filling frontmatter
- `templates/_template.md` — the copyable entry template
