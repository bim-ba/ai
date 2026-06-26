# spark Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the built `claude-toolkit` (branch `feat/claude-toolkit-bootstrap`) into `spark`: rename the marketplace, apply a skill-naming convention with three renames, convert the drift-log subsystem from templates+go-task into two self-contained skills, and add two rules to the always-on behaviour protocol.

**Architecture:** Sequential edits on the existing branch. Renames happen before the tasks that write new references, so cross-references land on the new names. There is no automated test framework — verification is by JSON parse (`jq`), grep gates (no stale references), structural checks, and a controller-run `/setup` smoke test. The spec is `docs/superpowers/specs/2026-06-26-spark-refactor-design.md`.

**Tech Stack:** Claude Code plugins/marketplace, Markdown SKILL.md, JSON, bash, `git`, `jq`. Dependency reduction is a goal — this refactor REMOVES the `go-task` dependency.

## Global Constraints

- Marketplace internal name is **`spark`** (was `claude-toolkit`). `enabledPlugins` keys: `core@spark`, `data@spark`. `extraKnownMarketplaces` key `spark`, github source `bim-ba/ai` (repo name unchanged).
- Skill naming convention: **workflow** = `<gerund-verb>-<object>`; **rulebook** = `<domain>-<aspect>`. Verb families: `using-`, `documenting-`, `reviewing-`, `researching-`, `creating-`/`writing-`.
- Renames: `auditing-agent-instructions`→`reviewing-agent-instructions`; `operational-meeting-documentation`→`documenting-meetings`; `systematic-research`→`researching-rigorously`. Keep: `using-playwright`, `clickhouse-query-best-practices`, `setup`.
- REMOVE entirely: `templates/drift-log-automated/`, the `--automated` flag, any `go-task`/`Taskfile` reference.
- Drift-log knowledge moves into two new `core` skills: `creating-drift-logs`, `reviewing-drift-logs`.
- `behaviour-protocol.md` stays lean (< ~40 lines) and free of project nouns (`unitrade|x5|clickhouse|yandex|trino|russian`).
- All renamed/new SKILL.md `description` fields keep a concrete "Use when…" trigger and (for these workflow skills) `type: skill` + `category: workflow` frontmatter.
- Use `git mv` for renames (preserve history). Commit per task with explicit `git add <paths>` (never `git add -A` — `.superpowers/` ledger must stay uncommitted).
- Historical mentions of old names inside `docs/superpowers/` (plan/spec/ledger) are RECORDS — do NOT rewrite them. Grep gates target `plugins/` + `.claude-plugin/` + `README.md` only.

---

## File Structure (after refactor)

```
.claude-plugin/marketplace.json            # name: spark
README.md                                  # onboarding -> core@spark
plugins/core/
  hooks/hooks.json                         # Stop reminder -> creating-drift-logs skill
  hooks/behaviour-protocol.md              # + 2 new rules
  skills/
    reviewing-agent-instructions/          # renamed (was auditing-agent-instructions)
    documenting-meetings/                  # renamed (was operational-meeting-documentation)
    researching-rigorously/                # renamed (was systematic-research)
    using-playwright/                      # unchanged
    creating-drift-logs/                   # NEW (SKILL.md + templates/_template.md + rules/)
    reviewing-drift-logs/                  # NEW (SKILL.md + optional references/)
    setup/                                 # overhauled (spark wiring, no --automated, dir-only drift-log)
  templates/
    claudelintignore, claudelintrc.json, CLAUDE.md.tmpl, skills-authoring-standard.md
    # DELETED: drift-log/ and drift-log-automated/
plugins/data/…                             # unchanged
```

---

## Task 1: Rename marketplace to `spark`

**Files:**
- Modify: `/home/sava/dev/shared/.claude-plugin/marketplace.json`
- Modify: `/home/sava/dev/shared/README.md`

**Interfaces:**
- Produces: marketplace name `spark`; the `extraKnownMarketplaces` key + `enabledPlugins` suffix `@spark` that Task 5 (`/setup`) and onboarding text consume.

- [ ] **Step 1: Edit `marketplace.json`** — change `"name": "claude-toolkit"` to `"name": "spark"`. Leave the `plugins` array (`core`/`data`, `./plugins/*`) unchanged.

- [ ] **Step 2: Edit `README.md`** — replace onboarding strings: `core@claude-toolkit`→`core@spark`, `data@claude-toolkit`→`data@spark`, and any "marketplace `claude-toolkit`" prose → "marketplace `spark`". Keep `/plugin marketplace add bim-ba/ai` (repo unchanged).

- [ ] **Step 3: Verify**

Run: `jq -e '.name=="spark"' /home/sava/dev/shared/.claude-plugin/marketplace.json` → prints `true`.
Run: `grep -rn 'claude-toolkit' /home/sava/dev/shared/.claude-plugin /home/sava/dev/shared/README.md` → no matches.

- [ ] **Step 4: Commit**

```bash
cd /home/sava/dev/shared
git add .claude-plugin/marketplace.json README.md
git commit -m "refactor: rename marketplace claude-toolkit -> spark"
```

---

## Task 2: Rename three skills (dirs + frontmatter + cross-references)

**Files:**
- Rename: `plugins/core/skills/auditing-agent-instructions/` → `plugins/core/skills/reviewing-agent-instructions/`
- Rename: `plugins/core/skills/operational-meeting-documentation/` → `plugins/core/skills/documenting-meetings/`
- Rename: `plugins/core/skills/systematic-research/` → `plugins/core/skills/researching-rigorously/`
- Modify: each renamed `SKILL.md` frontmatter `name:` field; any in-`plugins/` cross-references.

**Interfaces:**
- Produces: the new skill names that Task 3 (authoring standard examples), Task 4 (drift-log skills' "see also"), and Task 5 (Stop hook / setup) may reference.

- [ ] **Step 1: git mv the three directories**

```bash
cd /home/sava/dev/shared
git mv plugins/core/skills/auditing-agent-instructions plugins/core/skills/reviewing-agent-instructions
git mv plugins/core/skills/operational-meeting-documentation plugins/core/skills/documenting-meetings
git mv plugins/core/skills/systematic-research plugins/core/skills/researching-rigorously
```

- [ ] **Step 2: Update each `SKILL.md` `name:` frontmatter**

- `plugins/core/skills/reviewing-agent-instructions/SKILL.md`: `name: auditing-agent-instructions` → `name: reviewing-agent-instructions`. Update the visible H1/title if it embeds the old name. Adjust the `description` wording from "audit" to "review" only where it reads naturally (keep the concrete trigger; it may still mention auditing as the activity).
- `plugins/core/skills/documenting-meetings/SKILL.md`: `name: operational-meeting-documentation` → `name: documenting-meetings`. Update H1/title.
- `plugins/core/skills/researching-rigorously/SKILL.md`: `name: systematic-research` → `name: researching-rigorously`. Update H1/title.

- [ ] **Step 3: Sweep cross-references inside `plugins/`**

Run: `grep -rn 'auditing-agent-instructions\|operational-meeting-documentation\|systematic-research' /home/sava/dev/shared/plugins`
For every hit, replace with the new name (e.g. a "see also" link, the authoring standard, a registry mention). Re-run the grep until it returns nothing.

- [ ] **Step 4: Verify**

Run: `grep -rn 'auditing-agent-instructions\|operational-meeting-documentation\|systematic-research' /home/sava/dev/shared/plugins` → no matches.
Run: `for d in reviewing-agent-instructions documenting-meetings researching-rigorously; do f="plugins/core/skills/$d/SKILL.md"; grep -q "^name: $d$" "$f" && echo "OK $d" || echo "BAD $d"; done` (from repo root) → three `OK` lines.
Run: confirm `reviewing-agent-instructions/references/` (the 4 files) came along: `ls plugins/core/skills/reviewing-agent-instructions/references/`.

- [ ] **Step 5: Commit**

```bash
git add plugins/core/skills
git commit -m "refactor: rename skills to convention (reviewing-agent-instructions, documenting-meetings, researching-rigorously)"
```

---

## Task 3: Codify naming convention + skill structure in the authoring standard

**Files:**
- Modify: `plugins/core/templates/skills-authoring-standard.md`

**Interfaces:**
- Consumes: the new skill names from Task 2 (use them as examples).
- Produces: the documented convention that Task 4's new skills must follow.

- [ ] **Step 1: Add a "Skill naming convention" section** to `skills-authoring-standard.md` (place it near the top, after the intro). Content:

```markdown
## Skill naming convention

Skill directory names are lowercase-kebab and follow one of two shapes by category:

- **Workflow skills** (the skill performs an action) → `<gerund-verb>-<object>`.
  Verb families: `using-` (operate a tool/service), `documenting-` (produce docs),
  `reviewing-` (review/audit), `researching-` (research/fact-check),
  `creating-`/`writing-` (author an artifact).
  Examples: `using-playwright`, `documenting-meetings`, `reviewing-agent-instructions`,
  `researching-rigorously`, `creating-drift-logs`, `reviewing-drift-logs`.
- **Rulebook skills** (a reference body of domain rules, not an action) → `<domain>-<aspect>`.
  Example: `clickhouse-query-best-practices`.

Exception: a skill meant to be invoked as an explicit slash command may keep a short
imperative name (e.g. `setup` → `/setup`).
```

- [ ] **Step 2: Add a "Skill structure (self-contained)" section**. Content:

```markdown
## Skill structure (self-contained)

Prefer self-contained skills. `SKILL.md` is a thin router — when to use it, the
workflow/rules summary, and pointers — while heavier material lives in on-demand
subdirectories so it is loaded only when needed (token-efficient) and the skill is
portable:

- `rules/NN-*.md` — atomic rules, one concern per file.
- `templates/` — copyable artifact templates.
- `references/` — deep reference material loaded on demand.
- `examples/` — worked before/after examples.
- `scripts/` — executable helpers.

Every `rules/`/`examples/`/`templates/` file linked from `SKILL.md` must exist
(no broken internal links).
```

- [ ] **Step 3: Verify** — `grep -n 'Skill naming convention' plugins/core/templates/skills-authoring-standard.md` and `grep -n 'Skill structure' …` each return a line; the examples reference the NEW skill names (grep for `documenting-meetings` returns a hit).

- [ ] **Step 4: Commit**

```bash
git add plugins/core/templates/skills-authoring-standard.md
git commit -m "docs(core): add skill naming convention + self-contained structure to authoring standard"
```

---

## Task 4: Drift-log → two self-contained skills; delete templates

**Files:**
- Create: `plugins/core/skills/creating-drift-logs/SKILL.md`
- Create: `plugins/core/skills/creating-drift-logs/templates/_template.md`
- Create: `plugins/core/skills/creating-drift-logs/rules/01-triggers.md`, `rules/02-immutability.md`, `rules/03-frontmatter-schema.md`
- Create: `plugins/core/skills/reviewing-drift-logs/SKILL.md`
- Delete: `plugins/core/templates/drift-log/` and `plugins/core/templates/drift-log-automated/`
- Source (read, then delete): the current `plugins/core/templates/drift-log/README.md` and `_template.md`.

**Interfaces:**
- Consumes: naming convention + structure from Task 3.
- Produces: skill names `creating-drift-logs` and `reviewing-drift-logs` that Task 5 (Stop hook reminder + `/setup` pointer) references.

- [ ] **Step 1: Read the source** — `plugins/core/templates/drift-log/README.md` (8 triggers, do-NOT-log list, frontmatter schema, immutability rule, OPEN→APPLIED lifecycle, staleness triage, compaction) and `_template.md` (entry frontmatter + 4 body sections). This is the content you are splitting into two skills. Do NOT invent new rules — restructure existing content.

- [ ] **Step 2: Create `creating-drift-logs/SKILL.md`** — frontmatter `name: creating-drift-logs`, `type: skill`, `category: workflow`, and a `description` like: `"Use when you notice a divergence between actual session behavior and codified instructions (one of the 8 drift triggers) — captures it as an immutable drift-log entry under .claude/drift-log/open/ so good conventions can be promoted later."` Body (thin router): Purpose; the 8 triggers + the do-NOT-log list (or point to `rules/01-triggers.md`); how to create an entry (path `.claude/drift-log/open/<YYYY-MM-DD>-<slug>.md`, one insight = one entry, copy `templates/_template.md`); pointers to `rules/`. Keep it scannable.

- [ ] **Step 3: Create `creating-drift-logs/templates/_template.md`** — copy the body/frontmatter schema from the source `templates/drift-log/_template.md` verbatim (it is already generic).

- [ ] **Step 4: Create the three `creating-drift-logs/rules/` files** — split the source README's rule content: `01-triggers.md` (the 8 numbered triggers + the do-NOT-log list), `02-immutability.md` (narrative body + temporal frontmatter are frozen; only relocation pointers + disposition are mutable; never delete — transition through `applied/`), `03-frontmatter-schema.md` (the field list: immutable `date/status/priority/trigger/session_context` vs relocation-only `affected_source/applied_in/disposition`, with allowed values). Each file: a short frontmatter (`name`, one-line `description`) + the rule content.

- [ ] **Step 5: Create `reviewing-drift-logs/SKILL.md`** — frontmatter `name: reviewing-drift-logs`, `type: skill`, `category: workflow`, `description` like: `"Use when triaging the drift-log — promoting open entries to applied, checking staleness, compacting applied entries, or turning an applied insight into a codified rule."` Body: the OPEN→APPLIED transition (`git mv` open→applied, flip `status` + set `disposition: applied|already-done|dropped|refiled`), staleness triage (HIGH 7d / MEDIUM 21d / LOW 60d → Resolve/Refile/Drop, never delete), `applied/` compaction into `INDEX-YYYY-MM.md` past ~50 entries, and promotion (an applied insight that's now a standing rule → add to CLAUDE.md or a skill). Source: the lifecycle/staleness/compaction sections of the README.

- [ ] **Step 6: Delete the template directories**

```bash
cd /home/sava/dev/shared
git rm -r plugins/core/templates/drift-log plugins/core/templates/drift-log-automated
```

- [ ] **Step 7: Verify**
- `for f in $(grep -oE '(rules|templates)/[A-Za-z0-9][^)]+\.md' plugins/core/skills/creating-drift-logs/SKILL.md); do test -f "plugins/core/skills/creating-drift-logs/$f" && echo "OK $f" || echo "MISSING $f"; done` → all OK (every linked rules/templates file exists).
- Both new `SKILL.md` files have `category: workflow` and a trigger-bearing description.
- `grep -rn 'go-task\|Taskfile\|--automated' plugins/core/skills/creating-drift-logs plugins/core/skills/reviewing-drift-logs` → nothing.
- `ls plugins/core/templates/` → no `drift-log` or `drift-log-automated`.
- The 8 triggers from the source README are all present in `creating-drift-logs/rules/01-triggers.md`.

- [ ] **Step 8: Commit**

```bash
git add plugins/core/skills/creating-drift-logs plugins/core/skills/reviewing-drift-logs plugins/core/templates
git commit -m "feat(core): drift-log as creating-drift-logs + reviewing-drift-logs skills; drop go-task templates"
```

---

## Task 5: Overhaul `/setup` (spark wiring, no `--automated`, drift-log dir-only) + Stop hook

**Files:**
- Modify: `plugins/core/skills/setup/SKILL.md`
- Modify: `plugins/core/hooks/hooks.json`

**Interfaces:**
- Consumes: marketplace name `spark` (Task 1); skill name `creating-drift-logs` (Task 4).
- Produces: the final scaffolding behavior verified by the Task 7 smoke test.

- [ ] **Step 1: `setup/SKILL.md` — marketplace wiring → `spark`.** In Step 6 (the JSON shapes + the python merge) and any examples/Artifact-Map/Post-checks: `extraKnownMarketplaces.claude-toolkit`→`extraKnownMarketplaces.spark`, repo stays `bim-ba/ai`; `enabledPlugins` `core@claude-toolkit`→`core@spark`, `data@claude-toolkit`→`data@spark`. Update the python merge dict keys + the post-check assertions accordingly.

- [ ] **Step 2: `setup/SKILL.md` — remove `--automated`.** Delete the `--automated` flag from Pre-checks Step 3, and in Step 2 delete the automated-variant branch and the `Taskfile.audit.yml` copy + its `includes:` note. Remove the `--automated` line from the Step 7 next-steps and the Artifact Map row for `Taskfile.audit.yml`. The `--data` flag stays.

- [ ] **Step 3: `setup/SKILL.md` — drift-log becomes dir-only.** Replace Step 2's drift-log template-copy commands with just:

```bash
mkdir -p "$PROJECT_ROOT/.claude/drift-log/open"
mkdir -p "$PROJECT_ROOT/.claude/drift-log/applied"
```

and a printed pointer: "Drift-log conventions live in the `creating-drift-logs` and `reviewing-drift-logs` skills (from the `core` plugin) — no per-project README/template is copied." Update the Artifact Map (drop the README/_template/Taskfile rows; keep the open/applied dir rows) and Post-checks (drop the README/_template existence checks; keep the dir checks).

- [ ] **Step 4: `hooks/hooks.json` — Stop reminder → skill.** Replace the Stop hook command text with:

```text
echo 'Drift-log check: scan the last turn against the 8 triggers in the creating-drift-logs skill. If any fired, create an entry per that skill at .claude/drift-log/open/$(date +%Y-%m-%d)-<slug>.md. Else acknowledge: "drift-log delta: none".'
```

(keep the JSON structure, `type: command`, `timeout: 5`). Do not touch the SessionStart hook.

- [ ] **Step 5: Verify**
- `jq . plugins/core/hooks/hooks.json` parses; the Stop command references `creating-drift-logs`; SessionStart unchanged (`grep -c behaviour-protocol plugins/core/hooks/hooks.json` → 1).
- `grep -n 'claude-toolkit\|--automated\|Taskfile\|drift-log/README\|drift-log/_template' plugins/core/skills/setup/SKILL.md` → nothing.
- `grep -n 'core@spark' plugins/core/skills/setup/SKILL.md` → present; the python merge writes `spark` + `core@spark`.

- [ ] **Step 6: Commit**

```bash
git add plugins/core/skills/setup/SKILL.md plugins/core/hooks/hooks.json
git commit -m "refactor(core): /setup wires spark, drops --automated, drift-log dir-only; Stop hook points at creating-drift-logs"
```

---

## Task 6: Add two rules to the behaviour protocol

**Files:**
- Modify: `plugins/core/hooks/behaviour-protocol.md`

- [ ] **Step 1: Read the current file** and find the existing "validate / don't trust training data" bullet.

- [ ] **Step 2: Replace/extend** that area with these two bullets (merge with the existing validate bullet so there's no duplicate):

```markdown
- **Validate against current sources.** Before a non-trivial claim or before committing to an approach, verify it against current external tools (e.g. a docs MCP like context7, a web-search tool, a research CLI). Training data goes stale — confirm current versions, APIs, and idioms instead of relying on memory, and don't build a complex solution to something a current library or tool already solves simply.
- **Prefer existing solutions over reinventing.** Before writing custom code, look for a mature, maintained option first — a standard-library feature, a widely-used open-source package, or an existing internal utility. Choose custom only when nothing fits, and state why.
```

- [ ] **Step 3: Verify**
- `wc -l plugins/core/hooks/behaviour-protocol.md` → still under ~40 lines.
- `grep -iE 'unitrade|x5|clickhouse|yandex|trino|russian|httpie' plugins/core/hooks/behaviour-protocol.md` → nothing.
- `jq -Rs '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:.}}' plugins/core/hooks/behaviour-protocol.md | jq -e '.hookSpecificOutput.additionalContext|length>0'` → `true` (injection JSON still valid).
- No duplicate "validate" bullet remains.

- [ ] **Step 4: Commit**

```bash
git add plugins/core/hooks/behaviour-protocol.md
git commit -m "feat(core): protocol rules — validate against current sources, prefer existing solutions"
```

---

## Task 7: Consistency sweep + smoke test + final review (controller-run)

This task is run by the controller (not a fresh implementer): it is verification, not new code.

- [ ] **Step 1: Repo-wide stale-reference gate**

Run from repo root and confirm EACH returns nothing (in `plugins/` + `.claude-plugin/` + `README.md`):
```bash
grep -rn 'claude-toolkit' plugins .claude-plugin README.md
grep -rn 'auditing-agent-instructions\|operational-meeting-documentation\|systematic-research' plugins
grep -rn 'go-task\|Taskfile\|--automated\|drift-log/README\|drift-log/_template' plugins
```
(Stale names inside `docs/superpowers/` are historical records and are allowed.)

- [ ] **Step 2: Manifest + hook parse** — `jq .` on `marketplace.json`, both `plugin.json`, `hooks.json`; confirm marketplace `name=spark`, Stop hook references `creating-drift-logs`, SessionStart injection JSON valid.

- [ ] **Step 3: `/setup` smoke test** — in a throwaway scratch project, follow the overhauled `setup/SKILL.md` (export `CLAUDE_PLUGIN_ROOT`/`PROJECT_ROOT`): confirm it creates `.claude/drift-log/{open,applied}` (and NOT a drift-log README/template), `.claudelintrc.json`, `.claude/skills/README.md`, `CLAUDE.md` + `AGENTS.md` symlink, and a `.claude/settings.json` merged with `spark` + `core@spark` (preserving a pre-seeded user key). Re-run → idempotent skips. Confirm no `--automated` path exists.

- [ ] **Step 4: New-skill link-resolution** — every `rules/`/`templates/` link in `creating-drift-logs/SKILL.md` resolves; both new skills + the three renamed skills carry `category: workflow` and trigger-bearing descriptions.

- [ ] **Step 5: Final whole-branch review** — dispatch a final reviewer (most capable model) over the full branch diff with the spec as the rubric: marketplace↔plugin name consistency under `spark`, all skill cross-references resolve, the two new drift-log skills + three renames conform to the authoring standard + naming convention, behaviour-protocol stays lean and project-noun-free, and the go-task dependency is fully gone. Fix any Critical/Important via a fix subagent + re-review.

- [ ] **Step 6: Push** — `git push` the branch. Update the progress ledger.

---

## Self-Review notes
- **Spec coverage:** A→Task 1; B→Tasks 2+3; C→Tasks 4+5(setup/hook); D→Task 6; E→Task 7. All five workstreams covered.
- **Ordering dependency:** renames (T2) precede authoring-standard examples (T3), drift-log skills (T4), and setup/hook references (T5) — so every new reference uses the final names. T1 (spark) precedes T5 (setup wiring).
- **No new test framework** — verification is grep/jq/structure + the controller smoke test, consistent with the original build.
- **Out of scope (unchanged):** Phase 5 retrofit + Context7-key rotation; Phase 6 personal layer + onboarding docs; repo rename; deferred Minors (auditing section headers — though the rename in T2 touches that skill, leave its section structure unless trivial).
