# Audit Report Template

Final output of the skill is written to `.claude/audit/YYYY-MM-DD-audit.md`. If a report for today's date already exists, append `-N` suffix (`2026-05-19-audit-2.md`).

## Template

````markdown
---
date: <YYYY-MM-DD>
levels_run: [1, 2, 3]
findings_count:
  high: <N>
  med: <N>
  low: <N>
---

# Agent Instructions Audit — <YYYY-MM-DD>

## Summary

<1 paragraph: top 3 findings + overall health verdict (clean / minor / significant).>

## Level 1: Mechanical

Source: mechanical checks run via whatever the project uses (task runner, shell script, or by hand). Show a **summary table** of the most actionable findings (top ~20: all HIGH + a representative MED sample). If a full JSON output was produced, it goes to a sidecar file, not inline.

| Check | Severity | File | Detail | Suggestion |
|-------|----------|------|--------|------------|
| <check> | <sev> | <file> | <detail> | <suggestion> |
| ... | | | | |

### Raw JSON: sidecar file (when automated tooling produces JSON output)

Write the full JSON output to `.claude/audit/YYYY-MM-DD-audit-level1.json` (alongside the report). Reference it from the report rather than inlining. Inlining is unworkable when the JSON exceeds ~5 KB (typical run on a large repo is 100+ KB across 500+ entries).

Commit both files together:

```bash
# run the mechanical checks (however your project runs them) and write the JSON to:
# .claude/audit/YYYY-MM-DD-audit-level1.json
# (then write the .md report)
git add .claude/audit/YYYY-MM-DD-audit.md .claude/audit/YYYY-MM-DD-audit-level1.json
```

## Level 2: Semantic findings

### Contradictions

<one entry per finding, or "None.">

### Duplicates

<...>

### Best-practices: skills

<...>

### Best-practices: hooks

<...>

### Best-practices: drift-log entries

<...>

### Ingestion completeness (semantic)

<run only if Level 1 ingestion-gap passed; bounded to first 3 entries by default>

## Level 3: Architectural

### Wheel reinvention / techdebt

<narrative paragraph(s), or "No concerns surfaced.">

### Delegation candidates

| Routine | Current location | Proposed home | Rationale |
|---------|------------------|---------------|-----------|
| ... | | | |

### Coverage gaps

<narrative paragraph(s)>

## Action Backlog

Sorted by severity. Each item should be a single-session task.

- [ ] HIGH: <finding> → <action>
- [ ] MED: ...
- [ ] LOW: ...

## Companion runs

After reviewing this report, also run:
- `/claude-md-improver` — qualitative scoring + targeted edit suggestions for `CLAUDE.md` files
````

## Notes

- The report is committed to git — it's a historical artifact, not a temp file
- If the action backlog is empty, omit the section header rather than write "(none)"
- Levels with no findings still get their section header — present an explicit "None." rather than skipping, so the structure is predictable across runs
