---
name: drift-log-immutability
description: What is permanently frozen in a drift-log entry after its first commit, and what limited mutations are permitted.
---

# Drift Log Immutability

## Core principle

A drift-log entry is a historical record. Once committed, the narrative body and the temporal frontmatter fields are permanently frozen — they document what happened and when, and that record must not be altered.

## What is immutable (never edit after first commit)

**Narrative body sections:**
- `## What diverged`
- `## Why it seemed better`
- `## Proposed change`
- `## Resolution` (once written at the APPLIED transition)

**Temporal frontmatter fields:**
- `date` — when the drift was observed
- `status` — set to `OPEN` on creation; the transition to `APPLIED` is a relocation event (the file moves), not an in-place edit of this field
- `priority` — assessed at observation time
- `trigger` — which of the 8 triggers fired
- `session_context` — what the session was about

These fields together form the unambiguous historical record. Editing them would corrupt the audit trail.

## What is mutable (limited, mechanical updates only)

**Relocation pointers** — these are mechanical pointers that follow file renames. They may be updated only when the underlying file is physically moved or renamed:

- `affected_source:` — paths to the files the drift applies to. Update in the same commit as the file rename, and reference the move in the commit message. Do not repoint these to different content — only to follow renames.
- `applied_in:` — set once at the OPEN → APPLIED transition to record where the change was codified. Empty while the entry is OPEN.

**Disposition** — `disposition:` is set once at the OPEN → APPLIED transition (never earlier, never changed after). See `reviewing-drift-logs` skill for allowed values.

## Never delete

Do not delete drift-log entries. The historical record stays even for obsolete or incorrect observations. Always transition through `applied/` using the `reviewing-drift-logs` skill — the `Drop` path exists specifically for observations that turned out to be wrong or no longer relevant.
