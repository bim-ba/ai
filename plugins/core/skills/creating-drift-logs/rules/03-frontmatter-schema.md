---
name: drift-log-frontmatter-schema
description: Field-by-field schema for drift-log entry frontmatter — immutable fields vs relocation-only mutable fields, with allowed values.
---

# Drift Log Frontmatter Schema

## Immutable fields (set on first commit, never edit afterwards)

| Field | Type | Allowed values | Notes |
|---|---|---|---|
| `date` | string | `YYYY-MM-DD` | Date the drift was observed |
| `status` | string | `OPEN` \| `APPLIED` | Set to `OPEN` on creation; becomes `APPLIED` at the lifecycle transition |
| `priority` | string | `LOW` \| `MEDIUM` \| `HIGH` | Assessed at observation time; `HIGH` for repeated corrections (trigger 5) |
| `trigger` | integer | `1` through `8` | The trigger number from `rules/01-triggers.md` that fired |
| `session_context` | string | One-line description | What the session was about when the drift was observed |

## Relocation-only mutable fields

These are mechanical pointers. They may be updated only when the underlying file is physically renamed or relocated — in the same commit as the rename, never separately.

| Field | Type | Notes |
|---|---|---|
| `affected_source` | list of paths | Paths to the source files the drift applies to. Update only to follow renames — do not repoint to different content. |
| `applied_in` | string or path | Omit while `OPEN`. Set at the OPEN → APPLIED transition to record the commit or file where the change was codified. |

## Set once at transition (not on creation)

| Field | Type | Allowed values | Notes |
|---|---|---|---|
| `disposition` | string | `applied` \| `already-done` \| `dropped` \| `refiled` | Set once at the OPEN → APPLIED transition. OPEN entries omit this field. |
| `applied_date` | string | `YYYY-MM-DD` | Date the transition was performed. Set at OPEN → APPLIED. |

### Disposition values

| Value | Meaning | `applied_in:` |
|---|---|---|
| `applied` | Proposed change was merged — a real instruction edit landed | commit hash or file path |
| `already-done` | Already true at HEAD; no new edit needed | pre-existing artifact (optional) |
| `dropped` | Observation no longer holds / rule removed / drift was wrong — no change made | empty |
| `refiled` | Superseded by a new entry with corrected framing | `<new-file>` (set `supersedes:` in the new entry) |

## Grep-friendly conventions

Frontmatter is machine-readable for line-based grep and ripgrep:

```bash
rg '^priority: HIGH' .claude/drift-log/open/
rg '^status: OPEN' .claude/drift-log/
rg '^disposition: dropped' .claude/drift-log/applied/
```

Do not use a full YAML parser directly on `.md` files — the multi-document `---` separator and unquoted values containing `": "` cause parse failures. Extract one field at a time with:

```bash
awk '/^---$/{c++; if (c==2) exit; next} c==1' file.md | grep '^field:'
```
