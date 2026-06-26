---
name: reviewing-agent-instructions
description: Use when the user wants to review AI-agent instruction files (CLAUDE.md, skills, drift-log, hooks) for pollution, duplication, dead references, contradictions, or architectural debt. Manual on-demand only. Outputs a committed markdown report; does no auto-fix. Always run together with /claude-md-improver for full coverage.
type: skill
category: workflow
---

# Reviewing Agent Instructions

Manual on-demand review of AI-agent instruction surface in this repo. Produces a markdown report; never auto-fixes.

## When to use

- The user asks to audit, review, or check the agent-instruction surface (CLAUDE.md, skills, drift-log, hooks)
- The user is preparing for a cleanup pass and wants a fact-finding report first
- The user runs this together with `claude-md-improver` (recommended — they're complementary)

## When NOT to use

- For project content/research artifacts — those are not part of the agent-instruction surface
- For ad-hoc per-file edits (use Edit directly)
- As a CI check — this is manual on-demand only

## Workflow

### Step 1: Confirm scope with the user

Default scope:

- `CLAUDE.md` (root + any nested)
- `.claude/skills/*/SKILL.md` + `references/`
- `.claude/drift-log/` (open + applied + template + README)
- `.claude/settings.json` + `.claude/settings.local.json` hooks
- `~/.claude/` user-level skills + rules (if present)

Ask: "Run with default scope, or narrow to a specific subset?" Default to full scope if user says yes.

### Step 2: Level 1 — Mechanical

Run the mechanical checks using however this project runs them (a task runner, a shell script, or by hand). The checks are deterministic; the delivery mechanism varies by project.

If a script or task runner is available, run the mechanical checks and write the JSON output to `.claude/audit/YYYY-MM-DD-audit-level1.json`. If no automation is present, perform the equivalent checks manually: grep for dead references (confirm linked paths exist) and check file sizes (`wc -l` on each SKILL.md / CLAUDE.md, flag >150 lines). State in the report which approach was used.

`references/level-1-checks.md` documents the full mechanical check schema — use it as both the spec (when tooling is present) and the manual checklist (when running by hand).

### Step 3: Level 2 — Semantic (LLM, targeted)

Read the targeted file set:

- The `CLAUDE.md` file(s)
- All `.claude/skills/*/SKILL.md`
- Any file flagged by the Level 1 checks above (oversized, dead refs)

Run each check category from `references/level-2-checks.md`:

1. Cross-file contradictions
2. Semantic duplicates
3. Best-practices: skills
4. Best-practices: hooks
5. Best-practices: drift-log entries
6. Semantic ingestion-completeness (bounded — first 3 APPLIED entries)

Findings go into the report grouped by category.

### Step 4: Level 3 — Architectural (always-on narrative)

With Level 1+2 outputs in hand, write the narrative section per `references/level-3-prompts.md`. Three categories: wheel reinvention, delegation candidates, coverage gaps. Empty narrative is acceptable — write "No concerns surfaced" rather than fabricating.

### Step 5: Write the report

Path: `.claude/audit/YYYY-MM-DD-audit.md`. If today's report already exists, append `-N`.

Use the template in `references/output-template.md`. Commit the report:

```bash
git add .claude/audit/<file>.md
git commit -m "chore(audit): YYYY-MM-DD agent-instructions audit"
```

### Step 6: Hand-over message

Tell the user:

- Path to the report
- Findings count (H/M/L)
- Top 3 actionable items
- Reminder to run `/claude-md-improver` for qualitative CLAUDE.md scoring

## Non-goals

- ❌ No auto-fix. Report only.
- ❌ No state tracking. Full re-run every time.
- ❌ No drift-log entries created from findings. Audit findings ≠ drift-log entries.
- ❌ No CLAUDE.md quality scoring (delegated to `claude-md-improver`).

## References

- `references/level-1-checks.md` — mechanical check schema + per-check semantics
- `references/level-2-checks.md` — semantic check rubrics
- `references/level-3-prompts.md` — architectural narrative prompts
- `references/output-template.md` — audit report template

## Related skills

- `claude-md-improver` (claude-md-management plugin) — companion skill for CLAUDE.md qualitative review
- `superpowers:writing-skills` — source of best-practices reference for skill conformance checks
