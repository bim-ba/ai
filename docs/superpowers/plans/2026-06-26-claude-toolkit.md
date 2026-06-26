# claude-toolkit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single git repo `claude-toolkit` that is BOTH a Claude Code plugin marketplace AND the single source of truth for the user's reusable agent behavior + artifacts, so every current and future project (and every teammate) reuses them without copy-paste.

**Architecture:** Two concerns travel by two mechanisms. (1) **Generic behavior** lives in the `core` plugin and is delivered live by hooks (`SessionStart` injects the Agent Behaviour Protocol; `Stop` injects the drift-log reminder) — no per-project files, centrally updated. (2) **Generic file-based scaffolding** (drift-log skeleton, claudelint config, thin CLAUDE.md, settings wiring) is generated **once per project** by a `/setup` skill shipped in `core`; those files get committed to the project repo, so teammates receive them on `git clone`. Project-specific skills/instructions stay in each project's `.claude/`. A second `data` plugin carries genuinely-reusable data-engineering skills.

**Tech Stack:** Claude Code plugins + marketplace (`.claude-plugin/marketplace.json`, `plugin.json`), Markdown SKILL.md files, JSON settings/hooks, bash hook commands, `git`, `gh` (GitHub CLI). Optional: `claudelint` (external linter for agent-instruction surfaces).

## Global Constraints

- **Plugins cannot inject CLAUDE.md / always-on instructions directly.** Always-on guidance MUST travel via a `SessionStart`/`Stop` hook (confirmed: superpowers does exactly this). Do not attempt to ship a "global CLAUDE.md" in a plugin.
- **`~/.claude/` is user-local and NOT shared with teammates.** Only personal items go there. Everything team-shared goes in `claude-toolkit` (plugin or scaffolded-into-repo file).
- **Migrate only genuinely-general skills/artifacts.** Project-specific or single-project skills stay in their project. Decided split is in Task 1.2 / Appendix A.
- **`graphify` is out of scope** — its skill is auto-installed by the `graphify` CLI (not the user's authorship). Do NOT migrate the skill or the grep→graphify `PreToolUse` hook.
- **Genericize on copy:** when moving a skill, strip project-specific paths/hostnames/queue-names. The frontmatter `description` must keep a concrete trigger (claudelint enforces `skill-description-missing-trigger: error` + `skill-description-quality: error`).
- **No secrets in the repo.** Never commit API keys (see the Context7-key issue in Phase 5).
- Skill `description` style and the 7-section SKILL.md contract follow the existing `skills/README.md` authoring standard (migrated in Task 1.7).

## Decisions taken (defaults; confirm before Phase 0)

| # | Decision | Default chosen | Confirm? |
|---|---|---|---|
| D1 | Repo host + access | ✅ Private repo `github.com/bim-ba/ai` (created); local working copy = `/home/sava/dev/shared`; marketplace internal name stays `claude-toolkit` | ✅ resolved |
| D2 | Plugin split | `core` (everyone) + `data` (data projects) | ✅ confirmed by user |
| D3 | `/setup` drift-log default | `lightweight` (hand-maintained); `--automated` flag scaffolds the go-task `audit:*` variant | confirm |
| D4 | Behaviour Protocol scope | Team-generic only (research-before-acting, confidence gate, check-in/no-auto-proceed, challenge, error-handling, verification gate, orchestration guards). Personal Russian-voice does NOT go here | confirm |
| D5 | Personal voice | `~/.claude/CLAUDE.md` (Russian-answer preference). "Artifacts in English / one-thought-per-line" = optional team convention in the protocol | confirm |
| D6 | Retrofit existing 5 projects | Separate phase (Phase 5), after toolkit validated end-to-end | confirm |
| D7 | claudelint | Assumed installable/installed by team; `/setup` writes config + prints an install reminder if the binary is absent | confirm |

---

## File Structure (target repo)

```
claude-toolkit/
├─ .claude-plugin/
│  └─ marketplace.json                 # lists core + data plugins
├─ plugins/
│  ├─ core/
│  │  ├─ .claude-plugin/plugin.json
│  │  ├─ hooks/hooks.json              # SessionStart (protocol) + Stop (drift)
│  │  ├─ hooks/behaviour-protocol.md   # text the SessionStart hook echoes
│  │  ├─ skills/
│  │  │  ├─ auditing-agent-instructions/ (SKILL.md + references/)
│  │  │  ├─ using-playwright/SKILL.md
│  │  │  ├─ systematic-research/SKILL.md
│  │  │  ├─ operational-meeting-documentation/SKILL.md
│  │  │  └─ setup/SKILL.md             # the /setup project scaffolder
│  │  └─ templates/                    # files /setup copies into a project
│  │     ├─ drift-log/README.md
│  │     ├─ drift-log/_template.md
│  │     ├─ drift-log-automated/…      # go-task variant (Taskfile snippet + README)
│  │     ├─ claudelintrc.json
│  │     ├─ claudelintignore
│  │     ├─ CLAUDE.md.tmpl             # thin per-project skeleton
│  │     └─ skills-authoring-standard.md
│  └─ data/
│     ├─ .claude-plugin/plugin.json
│     └─ skills/
│        └─ clickhouse-query-best-practices/SKILL.md
├─ README.md                           # what this is, how teammates onboard
└─ docs/
   └─ onboarding.md                    # add-marketplace + /setup walkthrough
```

---

## Phase 0 — Repo + marketplace skeleton

### Task 0.1: Initialize the repo

**Files:**
- Create: `/home/sava/dev/shared/.claude-plugin/marketplace.json`
- Create: `/home/sava/dev/shared/README.md`
- Create: `/home/sava/dev/shared/.gitignore`

**Interfaces:**
- Produces: marketplace name `claude-toolkit`; plugin names `core`, `data` (referenced by every project's `enabledPlugins` later).

- [ ] **Step 1: git init (if not already)**

Run: `git -C /home/sava/dev/shared init && git -C /home/sava/dev/shared branch -M main`
Expected: empty repo on `main`.

- [ ] **Step 2: Write `.gitignore`**

```gitignore
.claude/settings.local.json
*.log
.DS_Store
```

- [ ] **Step 3: Write `marketplace.json`** (schema: object with `name`, `plugins[]`)

```json
{
  "name": "claude-toolkit",
  "plugins": [
    { "name": "core", "source": "./plugins/core", "description": "Generic agent behavior + reusable skills + /setup scaffolder for any project." },
    { "name": "data", "source": "./plugins/data", "description": "Reusable data-engineering skills (ClickHouse/dbt query practices)." }
  ]
}
```

- [ ] **Step 4: Write `README.md`** (onboarding summary)

Content: 1-paragraph purpose; "Teammate onboarding: `/plugin marketplace add bim-ba/ai` then enable `core` (and `data` for data projects), or just `git clone` a project that already lists them in `.claude/settings.json` and run `/setup`."

- [ ] **Step 5: Commit**

```bash
git -C /home/sava/dev/shared add -A
git -C /home/sava/dev/shared commit -m "chore: scaffold claude-toolkit marketplace"
```

- [ ] **Step 6 (D1): Push to remote** (repo `bim-ba/ai` already created; remote already added)

Run: `git -C /home/sava/dev/shared push -u origin feat/claude-toolkit-bootstrap`
Expected: branch pushed.

**Verification:** `cat .claude-plugin/marketplace.json | jq .` parses; `gh repo view bim-ba/claude-toolkit` succeeds (after Step 6).

---

## Phase 1 — `core` plugin

### Task 1.1: core plugin manifest

**Files:**
- Create: `plugins/core/.claude-plugin/plugin.json`

- [ ] **Step 1: Write `plugin.json`**

```json
{
  "name": "core",
  "version": "0.1.0",
  "description": "Generic agent behavior (delivered via hooks), reusable skills, and the /setup project scaffolder.",
  "author": { "name": "bim-ba" }
}
```

- [ ] **Step 2: Commit** `git add plugins/core/.claude-plugin/plugin.json && git commit -m "feat(core): add plugin manifest"`

**Verification:** `jq . plugins/core/.claude-plugin/plugin.json` parses.

---

### Task 1.2: Behaviour Protocol content (the always-on text)

**Files:**
- Create: `plugins/core/hooks/behaviour-protocol.md`

**Interfaces:**
- Produces: the markdown block echoed by the `SessionStart` hook (Task 1.3).

- [ ] **Step 1: Extract the GENERIC behavior** common to all 5 projects' CLAUDE.md. Source to read for wording: `/home/sava/dev/unitrade/CLAUDE.md` (richest "Agent Behaviour Protocol" + "Agent Workflow & Orchestration" sections) and `/home/sava/dev/x5/CLAUDE.md`. Include ONLY team-generic items (D4): research-before-acting; validate-don't-trust-training-data; 100%-confidence-or-ask; clarify before each task; challenge the approach; check-in after every task + wait, never auto-proceed; error handling (report, don't silently retry/skip); Plan-Act-Reflect verification gate (evidence before assertions, distrust a subagent's "done ✅", re-read authoritative state to confirm writes); knowledge-lives-in-versioned-surfaces; orchestration guards (parallelize within-task, sequential between-tasks, self-contained subagent prompts, review proportionality). EXCLUDE: personal Russian-voice (→ Phase 6), project stacks, repo maps, MCP topology, tool prefs that are project-bound.

- [ ] **Step 2: Write the file** as a tight, scannable block (target < 60 lines so per-session injection is cheap). Start it with a header line: `# Agent Behaviour Protocol (claude-toolkit/core)` and a one-line note: "These are baseline conventions for every project. Project CLAUDE.md adds domain rules on top; user instructions override these."

- [ ] **Step 3: De-dup check against superpowers** — superpowers already injects skill-discipline/TDD/debugging. Do NOT restate those; this file is the *user's* workflow protocol, not skill mechanics. Remove any line that merely repeats superpowers guidance.

- [ ] **Step 4: Commit** `git add plugins/core/hooks/behaviour-protocol.md && git commit -m "feat(core): add agent behaviour protocol text"`

**Verification:** file is < 60 lines (`wc -l`), contains no project nouns (grep for `unitrade|x5|clickhouse|yandex|ClickHouse|Trino` returns nothing).

---

### Task 1.3: Hooks — SessionStart (protocol) + Stop (drift reminder)

**Files:**
- Create: `plugins/core/hooks/hooks.json`

**Interfaces:**
- Consumes: `behaviour-protocol.md` (Task 1.2). The hook command reads + echoes it. Plugin hook commands can reference the plugin dir via `${CLAUDE_PLUGIN_ROOT}`.

- [ ] **Step 1: Write `hooks.json`**

```json
{
  "SessionStart": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "cat \"${CLAUDE_PLUGIN_ROOT}/hooks/behaviour-protocol.md\"",
          "timeout": 5
        }
      ]
    }
  ],
  "Stop": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "echo 'Drift-log check: scan last turn against .claude/drift-log/README.md triggers (1-8). If any fired — create .claude/drift-log/open/$(date +%Y-%m-%d)-<slug>.md from _template.md. Else acknowledge: \"drift-log delta: none\".'",
          "timeout": 5
        }
      ]
    }
  ]
}
```

- [ ] **Step 2: Verify `${CLAUDE_PLUGIN_ROOT}` is the correct plugin-root variable** for the installed Claude Code version (check plugin hooks docs; if the variable name differs, use the documented one). This is the one externally-dependent fact — confirm before relying on it.

- [ ] **Step 3: Commit** `git add plugins/core/hooks/hooks.json && git commit -m "feat(core): SessionStart protocol + Stop drift-log hooks"`

**Verification (end-to-end, after install):** in a scratch project with `core` enabled, start a session → the protocol text appears as SessionStart additional context; end a turn → the drift reminder appears. (Covered by Phase 4.)

---

### Task 1.4: Migrate `auditing-agent-instructions` skill

**Files:**
- Create: `plugins/core/skills/auditing-agent-instructions/SKILL.md`
- Create: `plugins/core/skills/auditing-agent-instructions/references/{level-1-checks.md,level-2-checks.md,level-3-checks.md,output-template.md}`
- Source (read, do not move): `/home/sava/Documents/Finance/.claude/skills/auditing-agent-instructions/` (has the full 4-file references set)

- [ ] **Step 1: Copy** SKILL.md + the 4 reference files from the Finance source into the new path.
- [ ] **Step 2: Genericize** — remove the hard-coded "this repo runs the lightweight drift-log, no `go-task audit:*`" assumption; parameterize so it works whether the project uses the lightweight or automated drift-log variant. Keep the "run together with /claude-md-improver" note.
- [ ] **Step 3: Frontmatter check** — `description` keeps a concrete "Use when…" trigger.
- [ ] **Step 4: Commit** `git add plugins/core/skills/auditing-agent-instructions && git commit -m "feat(core): migrate auditing-agent-instructions skill"`

**Verification:** `claudelint plugins/core/skills/auditing-agent-instructions/SKILL.md` passes (or, if claudelint absent, manually confirm description has a trigger and the 7 sections per the authoring standard).

---

### Task 1.5: Migrate `using-playwright` skill

**Files:**
- Create: `plugins/core/skills/using-playwright/SKILL.md`
- Source: `/home/sava/dev/x5/.claude/skills/using-playwright/SKILL.md`

- [ ] **Step 1: Copy** the file.
- [ ] **Step 2: Genericize** — the "X5-service specifics" section currently points to the `using-x5-services` skill. Replace with a generic note: "Service-specific playbooks live in a per-project skill (e.g. `using-<service>` with `references/<service>.md`); this skill stays tool-agnostic." Keep ALL the load-bearing mechanics verbatim (Monaco `setValue`, React-textarea native-setter, snapshot-vs-screenshot, token-efficient extraction, guardrails).
- [ ] **Step 3: Commit** `git add plugins/core/skills/using-playwright && git commit -m "feat(core): migrate using-playwright skill"`

**Verification:** grep the file for `x5|copilot.x5|data.x5|Bach|Kaiten` → only the generic example note remains; mechanics intact.

---

### Task 1.6: Migrate `systematic-research` skill (genericized)

**Files:**
- Create: `plugins/core/skills/systematic-research/SKILL.md`
- Source: `/home/sava/dev/x5/.claude/skills/systematic-research/SKILL.md`

- [ ] **Step 1: Copy** the file.
- [ ] **Step 2: Genericize the source ladder** — replace the X5-specific chain (local mirrors → graphify → corporate MCPs → copilot.x5) with a generic ladder: local sources/repos → available knowledge tools → MCP servers → web research; "fan out parallel subagents per source, cross-validate, cite sources." Keep the method (triangulate, parallel fan-out, adversarial cross-check, citations).
- [ ] **Step 3: Commit** `git add plugins/core/skills/systematic-research && git commit -m "feat(core): migrate systematic-research skill (genericized)"`

**Verification:** grep for `x5|copilot|corporate` → no project-specific bindings remain.

---

### Task 1.7: Migrate `operational-meeting-documentation` skill + skills-authoring standard

**Files:**
- Create: `plugins/core/skills/operational-meeting-documentation/SKILL.md`
- Create: `plugins/core/templates/skills-authoring-standard.md`
- Sources: `/home/sava/dev/unitrade/.claude/skills/operational-meeting-documentation/SKILL.md`; `/home/sava/dev/unitrade/.claude/skills/README.md`

- [ ] **Step 1: Copy** the meeting-documentation SKILL.md; strip any `repos/<workspace>/operational/` output-path assumption → make output path a parameter/argument the user supplies (default `./meeting-notes/`).
- [ ] **Step 2: Copy** `skills/README.md` → `templates/skills-authoring-standard.md` (the 7-section SKILL.md contract + language/quality bar). This is reference material `/setup` can drop into a project's `.claude/skills/README.md`.
- [ ] **Step 3: Commit** `git add plugins/core/skills/operational-meeting-documentation plugins/core/templates/skills-authoring-standard.md && git commit -m "feat(core): migrate meeting-docs skill + authoring standard"`

**Verification:** meeting skill description retains a concrete SRT trigger; no `repos/`/workspace path remains.

---

### Task 1.8: Drift-log + claudelint templates

**Files:**
- Create: `plugins/core/templates/drift-log/README.md`
- Create: `plugins/core/templates/drift-log/_template.md`
- Create: `plugins/core/templates/drift-log-automated/README.md` (+ a `Taskfile.audit.yml` snippet)
- Create: `plugins/core/templates/claudelintrc.json`
- Create: `plugins/core/templates/claudelintignore`
- Create: `plugins/core/templates/CLAUDE.md.tmpl`
- Sources: lightweight drift-log = `/home/sava/Documents/Finance/.claude/drift-log/{README.md,_template.md}`; automated variant + `audit:*` tasks = `/home/sava/dev/unitrade/.claude/drift-log/README.md` (+ its go-task `audit:*` definitions); claudelint = `/home/sava/dev/unitrade/.claudelintrc.json` + `.claudelintignore`.

- [ ] **Step 1: Copy** the lightweight drift-log `README.md` + `_template.md` into `templates/drift-log/`. These are already project-agnostic (the 8 triggers, immutability rules, open→applied lifecycle, staleness triage). Remove any project-name examples.
- [ ] **Step 2: Copy** the automated variant into `templates/drift-log-automated/` and include the `audit:drift-index-sync` / `audit:stale-open` / `audit:stale-applied` task definitions as a `Taskfile.audit.yml` snippet a project can include.
- [ ] **Step 3: Copy** `claudelintrc.json` → `templates/claudelintrc.json`. Keep `extends: "claudelint:recommended"` + the three overrides (`skill-reference-not-linked: off`, `skill-description-missing-trigger: error`, `skill-description-quality: error`). Copy `.claudelintignore` → `templates/claudelintignore` but strip project-specific ignore lines (the `repos/`, vendor-mirror, `.claude/audit/` entries) down to a generic baseline; leave a comment block showing optional project additions.
- [ ] **Step 4: Write `CLAUDE.md.tmpl`** — a thin skeleton: a title placeholder, a "## Project Overview" stub, a "## Project-Specific Conventions" stub, and a note "Baseline agent behavior is provided by claude-toolkit/core (injected each session); add only project-specific rules here." No generic protocol text (that lives in the hook).
- [ ] **Step 5: Commit** `git add plugins/core/templates && git commit -m "feat(core): add drift-log/claudelint/CLAUDE.md templates"`

**Verification:** `jq . templates/claudelintrc.json` parses; drift-log README contains the 8 triggers and the open→applied lifecycle; `CLAUDE.md.tmpl` contains no generic-protocol duplication.

---

## Phase 2 — `/setup` skill (the scaffolder)

### Task 2.1: Write the `/setup` skill

**Files:**
- Create: `plugins/core/skills/setup/SKILL.md`

**Interfaces:**
- Consumes: every file under `plugins/core/templates/` (Tasks 1.7–1.8), referenced via `${CLAUDE_PLUGIN_ROOT}/templates/…`.
- Produces (in the target project): `.claude/drift-log/{open,applied}/` (+ README + _template), `.claudelintrc.json`, `.claudelintignore`, `.claude/skills/README.md`, a `CLAUDE.md` from the template (only if absent), `AGENTS.md` symlink → `CLAUDE.md`, and `.claude/settings.json` patched with `extraKnownMarketplaces` + `enabledPlugins`.

- [ ] **Step 1: Write SKILL.md** describing the procedure the agent follows when the user runs `/setup` (optionally `/setup --automated` for the go-task drift-log variant, `/setup --data` to also enable the `data` plugin). The skill is instructions, not a binary; it tells the agent to:
  1. Detect project root + whether `.claude/` already exists (idempotent — never overwrite an existing CLAUDE.md or drift entries; only create what's missing).
  2. Copy the drift-log templates (lightweight by default; automated if `--automated`).
  3. Copy claudelint config; if the `claudelint` binary is absent, print: "claudelint not found — install it to lint your agent surface (config written anyway)."
  4. Copy `skills-authoring-standard.md` → `.claude/skills/README.md`.
  5. If no root `CLAUDE.md`: instantiate from `CLAUDE.md.tmpl` and create the `AGENTS.md` symlink. If one exists: leave it, and print a one-line reminder that baseline behavior now comes from `core`.
  6. Patch `.claude/settings.json` (create if missing) to add `extraKnownMarketplaces.claude-toolkit` (github source `bim-ba/ai`) and `enabledPlugins` (`core@claude-toolkit`; plus `data@claude-toolkit` if `--data`). Merge, don't clobber existing keys.
  7. Print a summary of created/skipped files and next steps (commit, `git add`).

- [ ] **Step 2: Frontmatter** — `description: "Use when bootstrapping a new (or existing) project to reuse the shared claude-toolkit conventions — scaffolds drift-log, claudelint config, a thin CLAUDE.md, and wires the core/data plugins into .claude/settings.json. Idempotent."`

- [ ] **Step 3: Commit** `git add plugins/core/skills/setup && git commit -m "feat(core): add /setup project scaffolder skill"`

**Verification:** covered end-to-end in Phase 4.

---

## Phase 3 — `data` plugin

### Task 3.1: data plugin manifest + clickhouse skill

**Files:**
- Create: `plugins/data/.claude-plugin/plugin.json`
- Create: `plugins/data/skills/clickhouse-query-best-practices/SKILL.md`
- Source: `/home/sava/dev/unitrade/.claude/skills/clickhouse-query-best-practices/SKILL.md`

- [ ] **Step 1: Write `plugin.json`**

```json
{
  "name": "data",
  "version": "0.1.0",
  "description": "Reusable data-engineering skills: ClickHouse/dbt query best practices.",
  "author": { "name": "bim-ba" }
}
```

- [ ] **Step 2: Copy + genericize the clickhouse skill** — remove the project paths (`analyses/adhoc/**`, the specific federated `postgresql()` host names). Keep the ClickHouse/dbt idioms and the federated-query guidance as generic patterns; turn paths into "your project's ad-hoc SQL dir".
- [ ] **Step 3: Commit** `git add plugins/data && git commit -m "feat(data): add plugin + clickhouse-query-best-practices skill"`

**Verification:** `jq . plugins/data/.claude-plugin/plugin.json` parses; grep skill for `unitrade|adhoc/` → only generic phrasing remains.

---

## Phase 4 — End-to-end validation in a scratch project

### Task 4.1: Install marketplace + dry-run /setup

**Files:**
- Create (scratch): `/tmp/claude-1000/-home-sava-dev-shared/16c5a0eb-7e17-449f-8b4e-a09731fdd0ef/scratchpad/setup-test/` (a throwaway git repo)

- [ ] **Step 1: Register the local marketplace** — `/plugin marketplace add /home/sava/dev/shared` (local path works before the remote exists), enable `core`.
- [ ] **Step 2: Start a fresh session in the scratch project** and confirm the `SessionStart` hook injects the Behaviour Protocol text (it appears as additional context).
- [ ] **Step 3: Run `/setup`** in the scratch project. Confirm it creates: `.claude/drift-log/{open,applied}/` + README + _template, `.claudelintrc.json`, `.claudelintignore`, `.claude/skills/README.md`, `CLAUDE.md` + `AGENTS.md` symlink, and patches `.claude/settings.json` with the marketplace + `enabledPlugins`.
- [ ] **Step 4: End a turn** → confirm the `Stop` hook prints the drift reminder.
- [ ] **Step 5: Idempotency** — run `/setup` again; confirm it skips existing files and overwrites nothing.
- [ ] **Step 6: If claudelint installed** — run it against the scaffolded skills; expect pass. If absent — confirm `/setup` printed the install reminder.

**Verification:** all six steps observed; the scratch `.claude/settings.json` contains valid `extraKnownMarketplaces` + `enabledPlugins`. Delete the scratch repo after.

---

## Phase 5 — Retrofit existing projects (one task each; do AFTER Phase 4 passes)

> For each project: enable the plugin(s), thin the CLAUDE.md (remove the now-centralized generic protocol; keep project-specific sections), delete the project-local copies of migrated skills, remove the duplicated `Stop` hook from `settings.json` (now provided by `core`), and verify a session still behaves. Commit per project. Keep a rollback point (branch) per repo.

### Task 5.1: unitrade
- [ ] Enable `core` + `data` in `.claude/settings.json`; remove the duplicated `Stop` hook (keep the `PreToolUse` graphify hook — graphify is local here).
- [ ] Delete project-local `auditing-agent-instructions`, `operational-meeting-documentation`, `clickhouse-query-best-practices` (now from plugins). KEEP `yandex-360-*`, `documentation-dpds`, `documentation-backend`, `operational-projects-presentation` (project-specific).
- [ ] Thin `CLAUDE.md`: remove the generic "Agent Behaviour Protocol" + "Agent Workflow & Orchestration" prose (now hook-injected); keep Repository/Documentation Maps, Tech Stack, MCP topology, git hygiene.
- [ ] Verify a session: protocol still injected (from `core`), kept skills still load. Commit on a branch.

### Task 5.2: x5
- [ ] Enable `core` + `data`; remove duplicated `Stop` hook.
- [ ] Delete project-local `using-playwright`, `systematic-research`, `operational-meeting-documentation`. KEEP `using-x5-services`, `operational-projects-presentation`, the `/graphify` shim in `.claude/CLAUDE.md`.
- [ ] Thin root `CLAUDE.md` (it's the symlink target of `AGENTS.md`): drop generic protocol; keep Tech Stack, Repo/Doc maps, `.mcp.json` topology, multi-repo git hygiene (x5 email/PAT/no-trailer).
- [ ] Verify + commit on a branch.

### Task 5.3: Finance
- [ ] Enable `core` (+ `data` — uses dbt/clickhouse). Remove duplicated `Stop` hook (keep `PreToolUse` graphify hook).
- [ ] Delete project-local `auditing-agent-instructions`. KEEP `clean-architecture` (project-specific).
- [ ] Fix the dead skill references in `CLAUDE.md` (`handoff-updated`, `dbt-modeling` — no matching dirs). Thin the generic protocol.
- [ ] Verify + commit on a branch.

### Task 5.4: Ideas
- [ ] Enable `core`. Remove duplicated `Stop` hook (keep `PreToolUse` graphify hook).
- [ ] Delete project-local `auditing-agent-instructions`. (graphify stays — CLI-managed.)
- [ ] Replace the hand-synced `AGENTS.md`/`CLAUDE.md` duplicate with a symlink (`ln -sf CLAUDE.md AGENTS.md`). Thin the generic protocol.
- [ ] Verify + commit on a branch.

### Task 5.5: Jobs
- [ ] Enable `core`. Remove duplicated `Stop` hook.
- [ ] Delete project-local `auditing-agent-instructions`. KEEP the career skills (`interview-*`, `cv-analyse`, `offer-decision-support`) — domain-specific, stay local.
- [ ] **Security:** rotate + remove the committed Context7 API key from `.mcp.json`; move it to `.claude/settings.local.json` (gitignored) or an env var. Thin the generic protocol.
- [ ] Verify + commit on a branch.

---

## Phase 6 — Personal layer + housekeeping

### Task 6.1: Personal `~/.claude` voice
- [ ] Create `~/.claude/CLAUDE.md` with the personal voice preference ("answer Sava in Russian; artifacts in English; one-thought-per-line"). This is user-local by design (D5). Confirm whether "artifacts in English" should instead be a team convention added to `behaviour-protocol.md` — if so, move that line there.

### Task 6.2: Onboarding docs
- [ ] Write `docs/onboarding.md` in `claude-toolkit`: teammate flow (`/plugin marketplace add bim-ba/ai`, enable `core`/`data`, or clone a `/setup`-bootstrapped project), and a maintainer flow (how to add a new shared skill, version bump, the genericize-on-migrate rule).

---

## Self-Review notes

- **Spec coverage:** core behavior (hooks) ✓ Task 1.2–1.3; reusable skills ✓ 1.4–1.7, 3.1; scaffolding `/setup` ✓ 2.1; drift-log/claudelint templates ✓ 1.8; data split ✓ Phase 3; future-proofing (any new project) ✓ via `/setup`; team access ✓ via marketplace in committed settings; retrofit ✓ Phase 5; personal/security/housekeeping ✓ Phase 6 + 5.5/5.3/5.4.
- **External-dependency risks flagged:** (a) exact plugin-root env var name in hooks (Task 1.3 Step 2); (b) `claudelint` installability (D7); (c) D1 repo host. These are the only non-self-contained facts — verify each before relying on it.
- **Out of scope, intentionally:** graphify skill + grep→graphify hook (CLI-managed); project-specific skills listed as KEEP in Phase 5.
