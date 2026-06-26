# Level 2 — Semantic Checks

LLM-driven analysis of cross-file consistency, duplication, and best-practices conformance. Scope is targeted to keep token cost bounded.

## Scope

For each Level 2 run, read:

- All `CLAUDE.md` files present in the repo (root + any nested)
- All `SKILL.md` files in `.claude/skills/*/`
- Plus any file flagged by Level 1 (size-check, ingestion-gap)

Do NOT read every file under `.claude/`. The targeted set above is the working set.

## Checks

### 1. Cross-file contradictions

Look for rules in `CLAUDE.md` that conflict with examples or instructions in skill files.

Method:

1. Extract bullet-form or directive-form rules from `CLAUDE.md` (Agent Behaviour Protocol, Code and Architecture Standards sections especially)
2. For each rule with a clear keyword (e.g. "httpie not curl", "uv run python not python3"), grep all skills + any task-runner/script files for the prohibited form
3. Triage each hit through the rubric below — only **prescribed** hits are real conflicts

### Triage rubric (where the offending form lives)

| Location of the hit | Treat as | Why |
|---------------------|----------|-----|
| **Prescribed example** in `CLAUDE.md` or a skill's "When to use / examples" section | ✅ Real conflict — flag it | This is us telling agents to do the prohibited thing |
| **Vendor-mirror docs** under `*/references/docs/*` | ❌ Suppress | Not authored by us; mirroring upstream is intentional |
| **Drift-log entry body** (`open/` or `applied/`) | ❌ Suppress unless inside the "Proposed change" section | Drift entries deliberately quote the thing being critiqued — that's not a violation |
| **Code-block comments** explicitly contrasting two forms ("not `curl`, use `httpie`") | ❌ Suppress | The mention is reinforcing the rule, not breaking it |
| **Generated artifacts** (audit reports under `.claude/audit/`, raw JSON) | ❌ Suppress | These quote findings, not author content |

When in doubt: ask whether changing the offending text would make any agent behave better. If yes — real conflict. If no — it's a quotation, suppress.

Output one finding per real conflict:

```json
{
  "level": 2,
  "check": "contradictions",
  "severity": "HIGH",
  "locations": ["CLAUDE.md", ".claude/skills/X/SKILL.md:42"],
  "detail": "CLAUDE.md mandates httpie, but skill X uses curl in example block",
  "suggestion": "Replace curl example with httpie equivalent, or document why curl is justified here"
}
```

### 2. Semantic duplicates

Same rule appearing in 2+ places (even if paraphrased).

Method:

1. Build a list of rules from `CLAUDE.md` (directive lines, table entries)
2. For each, search other files for paraphrases — same intent, different wording
3. Cluster findings by semantic equivalence

Output one finding per cluster:

```json
{
  "level": 2,
  "check": "duplicates",
  "severity": "MED",
  "locations": ["CLAUDE.md:120", ".claude/skills/X/SKILL.md:30", ".claude/skills/Y/SKILL.md:55"],
  "detail": "Rule 'no curl, use httpie' appears in 3 places with no canonical source declared",
  "suggestion": "Keep canonical statement in CLAUDE.md; replace skill copies with a reference link"
}
```

### 3. Best-practices: skills

For each `SKILL.md`, check conformance against `superpowers:writing-skills` AND the category-specific section requirements in `.claude/skills/README.md` §3:

- Frontmatter present with `name`, `description`, AND `category: workflow|rulebook`
- `description` is specific enough to be auto-triggered (anti-pattern: vague verbs like "use when working with X")
- SKILL.md within the layer ceiling (500 lines per `scripts/audit/check-size.sh`); if larger, content should be split into `references/`
- Required sections present for the declared category:
  - **workflow** — Purpose, Pre-checks, Workflow, Post-checks, Guardrails, Artifact Map, References Guide
  - **rulebook** — When to use, When NOT to use, Rules (or domain analogue), Examples, Anti-patterns
- Examples present, with concrete inputs/outputs
- References to other files use relative paths

Output per deviation:

```json
{
  "level": 2,
  "check": "best-practices/skills",
  "severity": "LOW" | "MED",
  "locations": [".claude/skills/X/SKILL.md"],
  "detail": "<specific deviation>",
  "suggestion": "<specific fix>"
}
```

### 4. Best-practices: hooks

For each hook in `.claude/settings.json`:

- Idiomatic exit codes (0 = pass; 2 = block + show stderr to agent)
- **Hook-event semantics differ — apply the right exit-code pattern per event:**
  - `PreToolUse` / `PermissionRequest` / `UserPromptSubmit` / `PostToolBatch`: `exit 2` blocks the pending action — correct for enforcement and file-protection hooks.
  - `Stop` / `SubagentStop`: `exit 2` forces the agent to continue (prevents stopping). Correct **only** when the hook has state-detection (e.g., checks `CLAUDE_STOP_HOOK_ACTIVE` or a lock file) to break the loop after one cycle. **For passive reminders** (fire-and-forget echo to agent context), use `echo '...'` (stdout) + `exit 0`. Using `exit 2` without loop-prevention in a Stop hook creates an infinite loop: hook fires → agent continues → stops again → hook fires → …
  - When in doubt about a Stop hook: if the command contains only `echo` or `printf`, it should use `exit 0`.
- stdout vs stderr clearly distinguished in command
- Paths absolute or rooted at `$CLAUDE_PROJECT_DIR`
- Reasonable timeout (`timeout` field present for non-trivial commands)

### 5. Best-practices: drift-log entries

For each `open/*.md` and `applied/*.md`:

- Frontmatter has all required fields (`date`, `status`, `priority`, `trigger`, `session_context`, `affected_source`)
- For APPLIED: also `applied_in`
- Body has the four required sections: "What diverged", "Why it seemed better", "Proposed change", "Resolution" (APPLIED only)
- `status` field matches the directory (open/ vs applied/)

### 6. Semantic ingestion-completeness (companion to Level 1 ingestion-gap)

For each APPLIED entry, read the "Proposed change" and "Resolution" sections, then read each file in `affected_source:` and judge: is the proposed change actually reflected in the file's current state?

This is a slow check — only run if Level 1 ingestion-gap passed (all paths resolve) and user explicitly opts in for deeper validation. Bound at first 3 entries in initial implementation; expand later if useful.

## Output

Findings stored per-category in the report under "Level 2: Semantic findings". One section per check.
