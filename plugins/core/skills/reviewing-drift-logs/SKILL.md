---
name: reviewing-drift-logs
type: skill
category: workflow
description: "Use when triaging the drift-log — promoting open entries to applied, checking staleness, compacting applied entries, or turning an applied insight into a codified rule."
---

# Reviewing Drift Logs

## Purpose

This skill covers the full lifecycle of drift-log entries after they are created: triage, OPEN → APPLIED transition, staleness review, applied-directory compaction, and promotion of a recurring insight into a standing rule.

**Use this skill when:**
- Triaging existing `open/` entries to decide whether to resolve, refile, or drop them
- Transitioning an entry from OPEN to APPLIED after implementing its proposed change
- Checking whether any `open/` entries are overdue (past their priority threshold)
- Compacting the `applied/` directory once it grows large
- Promoting a frequently-applied insight into a codified rule in CLAUDE.md or a skill

**Do NOT use this skill for:**
- Creating a new drift-log entry (use the `creating-drift-logs` skill instead)
- Editing the narrative body of an existing entry (that body is immutable — see `creating-drift-logs/rules/02-immutability.md`)

## Pre-checks

- Confirm `.claude/drift-log/` exists and has `open/` and `applied/` subdirectories.
- List `.claude/drift-log/open/` to see current OPEN entries (each file there is an open entry).
- Identify the task: transition a specific entry, triage all stale entries, compact `applied/`, or promote an insight.

## Workflow

### Path A: OPEN → APPLIED transition

Run this when the proposed change in a drift entry has been implemented (or when dropping/refiling):

1. `git mv .claude/drift-log/open/<file>.md .claude/drift-log/applied/<file>.md`
2. Edit frontmatter:
   - `status: OPEN` → `status: APPLIED`
   - Add `applied_date: YYYY-MM-DD` (today)
   - Add `applied_in: <commit-hash-or-file-path>` (where the change landed; leave empty for `dropped`)
   - Add `disposition:` — one of `applied | already-done | dropped | refiled`
3. Fill in the `## Resolution` section: one paragraph explaining how/where the change was merged (or why it was dropped/refiled).
4. The entry is now in `applied/` — no separate index update needed for OPEN (the `open/` directory itself is the live OPEN index). Add a summary entry to the current `applied/INDEX-YYYY-MM.md` (theme-grouped; create the month's index file if it does not exist).

### Path B: Staleness triage

An OPEN entry is overdue when its age past `date:` exceeds its priority's threshold:

| Priority | Overdue after |
|----------|---------------|
| `HIGH`   | 7 days        |
| `MEDIUM` | 21 days       |
| `LOW`    | 60 days       |

To find overdue entries:
```bash
rg '^date:' .claude/drift-log/open/ --no-heading | sort
```

For each overdue entry, choose one path:

| Path | When to choose | Action |
|------|----------------|--------|
| **Resolve** | The drift's proposed change still applies and is feasible | Implement the change → follow Path A above; set `disposition: applied` (or `already-done` if already true at HEAD) |
| **Refile** | The original framing is wrong but the underlying observation is still relevant | Create a NEW entry with corrected framing, set `supersedes: <old-file>` in its frontmatter, then move the old file to `applied/` with `status: APPLIED`, `applied_in: <new-file>`, Resolution explaining the refile, `disposition: refiled` |
| **Drop** | The observation no longer holds (underlying code/process changed; drift was wrong; the rule it would change has been removed) | Move to `applied/` with `status: APPLIED`, `applied_date:` today, `applied_in:` empty, Resolution explaining why no change is needed, `disposition: dropped` |

**Never simply delete the file** — the historical record stays. Always transition through `applied/`.

### Path C: Compaction of `applied/`

Run this when `applied/` grows past ~50 entries or the oldest uncovered entries are >6 months old:

1. Group entries by **theme**.
2. Write `applied/INDEX-YYYY-MM.md` — one paragraph per entry covering: date, slug, what changed, the file paths that codified the change. Link to each original entry.
3. Keep the original entries — they remain immutable historical records. The index adds a navigable summary.
4. The `applied/INDEX-YYYY-MM.md` file is the summary for that month's applied entries. Original entry files remain in place alongside it.

### Path D: Promote an applied insight to a rule

Run this when a recurring pattern in `applied/` entries indicates a missing standing rule:

1. Identify the pattern across multiple `disposition: applied` entries.
2. Decide the target: a new rule in an existing skill's `rules/` directory, a new skill, or a section in `CLAUDE.md`.
3. Draft the rule text in plain language — what is required, what is forbidden, edge cases.
4. Apply it to the target file and commit.
5. Back-reference the source entries in the commit message (e.g., `closes drift open/2024-01-15-foo.md`).

## Post-checks

**After OPEN → APPLIED transition:**
- The file exists in `applied/`, not in `open/`
- Frontmatter has `status: APPLIED`, `applied_date`, `disposition`
- `## Resolution` section is filled
- The file no longer appears in `open/` (confirming the `git mv` succeeded)
- The month's `applied/INDEX-YYYY-MM.md` has a summary for the entry

**After staleness triage:**
- Every overdue entry has been resolved, refiled, or dropped
- No overdue entry remains in `open/` without a decision

**After compaction:**
- `applied/INDEX-YYYY-MM.md` exists and links every entry it covers
- Original entry files remain in place (not deleted)

## Guardrails

- **Never delete** an entry — always transition through `applied/`
- **Never edit** the narrative body of an existing entry — it is an immutable historical record
- The `disposition:` field is set exactly once, at the OPEN → APPLIED transition — never earlier, never changed after
- The `Refile` path creates a NEW entry; it does not rewrite the old one's narrative
- `applied_in:` for `dropped` entries is intentionally empty — do not fill it with a placeholder

## Artifact Map

| Artifact | Path | Naming |
|---|---|---|
| Applied entry | `.claude/drift-log/applied/YYYY-MM-DD-<slug>.md` | Moved from `open/`; same filename |
| Monthly index | `.claude/drift-log/applied/INDEX-YYYY-MM.md` | One per calendar month |
| Promoted rule | `<target-skill>/rules/NN-<topic>.md` or `CLAUDE.md` | Per authoring standard |

## References Guide

- For entry frontmatter field definitions and allowed values, read `creating-drift-logs/rules/03-frontmatter-schema.md`
- For immutability constraints (what you can and cannot edit), read `creating-drift-logs/rules/02-immutability.md`
- For the original trigger taxonomy, read `creating-drift-logs/rules/01-triggers.md`
- For creating a new entry (instead of triaging existing ones), use the `creating-drift-logs` skill
