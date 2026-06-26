# Level 3 — Architectural Feedback

Narrative review. Always runs, regardless of Level 1+2 findings. The output is 3–9 paragraphs (1–3 per category).

## Inputs

When running Level 3, the agent has:

- Full Level 1 JSON output
- Full Level 2 findings (all categories)
- Full inventory of skill names + sizes
- Full drift-log inventory (open + applied, with frontmatter)
- The CLAUDE.md files (already read for Level 2)

## Categories

### Wheel reinvention / techdebt

**Signals to look for:**

- Same correction appears in multiple drift entries → topic deserves a codified rule or skill
- Same checklist or boilerplate repeated in 2+ skill files → extract to a shared `_template.md`
- A hand-rolled workflow that an existing feature already covers (slash command, hook, MCP server, plugin skill)
- A skill that's mostly a transcription of standard tool usage (could be replaced by a one-line CLAUDE.md note + tool docs)

**Output format:** Narrative paragraph naming the specific files and a proposed consolidation.

### Delegation candidates

For each codified routine in `CLAUDE.md` or a skill, judge where it best lives:

| Property of the routine | Best home |
|-------------------------|-----------|
| Needs LLM judgment, varies per case | Keep in agent context (CLAUDE.md/skill) |
| Deterministic, runs often, regex/path-shaped | Move to a shell script or task runner |
| Should fire automatically, not require remembering | Move to a `.claude/settings.json` hook |
| Composes multiple tools deterministically | Move to a `tasks/*.yml` file |

**Output format:** A table of candidates with current location, proposed home, and the rationale (signal that triggered the suggestion).

### Coverage gaps

Patterns visible in `drift-log/applied/` that have NOT been ingested into `CLAUDE.md` or skills.

**Signals to look for:**

- Multiple drift entries on the same topic over time, none of which produced a CLAUDE.md edit
- A drift entry's "Proposed change" was applied to one file, but the same rule would apply to other files that weren't touched
- An applied drift's resolution was a one-off fix rather than a generalized rule

**Output format:** Narrative paragraph per gap, ending with a concrete proposal ("add rule X to CLAUDE.md § Y" or "extend skill Z").

## Constraints

- No new findings list (Level 3 is narrative, not enumeration)
- Be specific: name files, name proposed changes
- Do not invent problems if there are none — empty Level 3 is acceptable, write "No architectural concerns surfaced this run" and move on
- Cite Level 1 / Level 2 findings as supporting evidence where relevant
