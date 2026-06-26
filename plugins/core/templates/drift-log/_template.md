---
# IMMUTABLE FIELDS — set on first commit, never edit afterwards
date: YYYY-MM-DD
status: OPEN
priority: LOW | MEDIUM | HIGH
trigger: [N]
session_context: one-line description of what the session was about

# MUTABLE-FOR-RELOCATION FIELDS — these are mechanical pointers. Update them
# when the underlying files are renamed/relocated (in the same commit as the
# rename), so audit:ingestion-gap stays accurate. Do NOT repoint to different
# content — only to follow renames. See drift-log/README.md § Conventions.
affected_source:
  - path/to/file.md
applied_in: (omit while OPEN; fill on transition to APPLIED)
---

## What diverged

<narrative — 1-3 paragraphs describing the divergence>

## Why it seemed better

<narrative — what made the ad-hoc version preferable>

## Proposed change

<concrete diff-style suggestion for updating official instructions>

## Resolution

<add only when transitioning to APPLIED — describes how/where the change was merged>
