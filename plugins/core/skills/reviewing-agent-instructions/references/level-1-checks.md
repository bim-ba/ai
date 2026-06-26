# Level 1 — Mechanical Checks

Mechanical checks are deterministic and live in `Taskfile.yml` under the `audit:*` namespace. They are invoked from the skill via `go-task audit:mechanical`, which outputs a single JSON array.

## Invocation

```bash
go-task audit:mechanical
```

Returns a JSON array of findings. Schema per item:

```json
{
  "level": 1,
  "check": "<check-name>",
  "severity": "LOW" | "MED" | "HIGH",
  "file": "<repo-relative path>",
  "detail": "<one-line description of the finding>",
  "suggestion": "<one-line remediation hint>"
}
```

## Checks

| Task | Purpose | Severity drivers |
|------|---------|------------------|
| `audit:size-check` | Files exceeding line threshold (env `SIZE_THRESHOLD`, default 150) | LOW < 2×T, MED 2×T–4×T, HIGH > 4×T |
| `audit:dead-refs` | Markdown link targets that don't exist | Always MED |
| `audit:stale-open` | drift-log `open/*.md` older than threshold (env `STALE_MONTHS`, default 3) | Always MED |
| `audit:ingestion-gap` | APPLIED entry's `affected_source` paths missing, or `applied_in` (if path-shaped) missing | HIGH for missing affected_source, MED for applied_in |
| `audit:hooks-valid` | Hook commands resolve (file exists / on PATH) | Always HIGH |

## Scope (files scanned)

- `.claude/**/*.md` (all skills, drift-log, all instruction files)
- `CLAUDE.md` and nested `*/CLAUDE.md` (excluding `.venv`, `node_modules`, `target`, `dist`, `.git`)
- `.claude/settings.json` (hooks check only)

## What Level 1 does NOT do

- No quality judgments (delegated to `claude-md-improver`)
- No semantic comparison between files (Level 2)
- No "is this a good rule?" reasoning (Level 3)
