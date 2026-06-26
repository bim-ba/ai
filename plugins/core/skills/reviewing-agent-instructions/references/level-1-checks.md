# Level 1 — Mechanical Checks

Mechanical checks are deterministic. Run them via whatever the project uses — a task runner, a shell script, or by hand. The output (whether automated or manually assembled) is a JSON array of findings.

## Invocation

Run the mechanical checks (however your project runs them) and write the JSON to `.claude/audit/YYYY-MM-DD-audit-level1.json`. If running manually, assemble the findings into the same JSON schema.

The JSON array schema per item:

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

| Check | Purpose | Severity drivers |
|-------|---------|------------------|
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
