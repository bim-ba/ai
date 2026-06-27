---
name: setup
description: "Use when bootstrapping a new (or existing) project to reuse the shared ai conventions — scaffolds drift-log, claudelint config, a thin CLAUDE.md, and wires the requested ai plugins (`core` always) into `.claude/settings.json`. Idempotent."
type: skill
category: workflow
---

# /setup — Project Bootstrap Skill

Scaffolds a target project with the ai conventions: drift-log, claudelint config, skills authoring standard, a thin CLAUDE.md, and the required `.claude/settings.json` plugin wiring. Safe to re-run — only creates what is missing.

## Purpose

### What this skill enables

Brings a project into the ai ecosystem in one shot: creates the directory structure and config files every agent-aware repo needs, and wires the requested ai plugins (core always) into `.claude/settings.json` so Claude Code resolves the marketplace correctly.

### When to use it

- Bootstrapping a brand-new project repository.
- Onboarding an existing repository that has no ai scaffold yet.
- Re-running `/setup` after the first pass to catch any files that were missing (idempotent — always safe).

### When NOT to use it

- For updating or replacing an existing `CLAUDE.md` with new content (edit it directly instead).
- For plugin-specific setup steps that are out of scope of the core scaffold (e.g., data-pipeline config, secrets management).
- When the project already has a fully wired ai setup and you only want to update one piece (use Edit directly).

---

## Pre-checks

Before running any step, verify:

1. **Project root is identifiable.** Look for the root via `git rev-parse --show-toplevel 2>/dev/null` or use the working directory if not a git repo. All paths below are relative to `PROJECT_ROOT`.
2. **`CLAUDE_PLUGIN_ROOT` resolves.** This variable points to the `core` plugin directory. It is typically set by the Claude Code plugin loader. If it is unset, run this discovery command before any other step:
   ```bash
   # If CLAUDE_PLUGIN_ROOT is unset, discover the installed core plugin root:
   CLAUDE_PLUGIN_ROOT="$(dirname "$(dirname "$(dirname "$(find "$HOME/.claude/plugins" -type f -path '*/core/skills/setup/SKILL.md' 2>/dev/null | head -1)")")")"
   # Explanation: SKILL.md lives at <plugin_root>/skills/setup/SKILL.md,
   # so three dirname calls (SKILL.md -> setup -> skills -> <plugin_root>) yield the plugin root.
   ```
   If discovery fails (e.g. the plugin is installed in a non-standard location), set `CLAUDE_PLUGIN_ROOT` manually to the absolute path of the `core` plugin directory you loaded this skill from — the directory that directly contains `skills/` and `templates/`.

   After setting it (via env or discovery), always assert it resolved correctly before proceeding:
   ```bash
   [ -d "$CLAUDE_PLUGIN_ROOT/templates" ] || { echo "CLAUDE_PLUGIN_ROOT not resolved correctly: $CLAUDE_PLUGIN_ROOT"; exit 1; }
   ```
   All template source paths below use `${CLAUDE_PLUGIN_ROOT}/templates/`.
3. **Parse flags from the user's invocation:**
   - `--with NAMES` → comma-separated ai plugin names to enable (e.g. `--with core,data`). `core` is always enabled even if omitted. Defaults to `core` when the flag is absent (so a bare `/setup` enables just `core`). Pass the value straight through to `bootstrap.py --with`.

---

## Workflow

### Step 1 — Resolve roots (bash pre-check)

```bash
export PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

# CLAUDE_PLUGIN_ROOT is normally set by the plugin loader. If unset, discover it:
if [ -z "$CLAUDE_PLUGIN_ROOT" ]; then
  CLAUDE_PLUGIN_ROOT="$(dirname "$(dirname "$(dirname "$(find "$HOME/.claude/plugins" -type f -path '*/core/skills/setup/SKILL.md' 2>/dev/null | head -1)")")")"
fi
[ -d "$CLAUDE_PLUGIN_ROOT/templates" ] || { echo "CLAUDE_PLUGIN_ROOT not resolved: $CLAUDE_PLUGIN_ROOT"; exit 1; }
echo "Project root: $PROJECT_ROOT"
```

### Step 2 — Run the scaffold

Pass `--with` with the user's plugin list (core is always enabled even if omitted):

```bash
uv run --no-project "$CLAUDE_PLUGIN_ROOT/skills/setup/scripts/bootstrap.py" \
  --project-root "$PROJECT_ROOT" --plugin-root "$CLAUDE_PLUGIN_ROOT" \
  --with "core"   # replace "core" with the user's --with list, e.g. "core,data"; core is always enabled
```

`bootstrap.py` is idempotent — it creates only missing artifacts and prints a CREATED/SKIPPED/PATCHED summary. It never overwrites `CLAUDE.md`, never writes drift-log entries, and merges `.claude/settings.json` without clobbering existing keys. Each requested plugin name (plus `core`, always) is written as `<name>@ai: true` into `.claude/settings.json`, non-clobber.

### Step 3 — Verify

```bash
uv run --no-project "$CLAUDE_PLUGIN_ROOT/skills/setup/scripts/verify.py" --project-root "$PROJECT_ROOT"
```

Expected: `verify OK`. On `verify FAILED`, report the listed problems to the user.

### Step 4 — Report

Relay the `bootstrap.py` summary table to the user, then print next steps:

```
Next steps:
  1. git add .claude/ CLAUDE.md AGENTS.md .claudelintrc.json .claudelintignore
  2. git commit -m "chore: bootstrap ai scaffold"
  3. Edit CLAUDE.md — fill in Project Overview and project-specific conventions.
```

---

## Post-checks

Post-checks are performed by `verify.py` in Workflow Step 3 (drift-log dirs, settings.json keys, AGENTS.md symlink). On `verify FAILED`, surface the listed problems.

---

## Guardrails

- **Never overwrite `CLAUDE.md`** even if its content looks stale. The user owns it. Print the reminder and stop.
- **Never write drift-log entry files** (`open/*.md`, `applied/*.md`). This skill only creates the `open/` and `applied/` directories (`mkdir -p`); it never writes individual entries. The drift-log is an immutable historical record — entry creation is out of scope for `/setup`.
- **Merge settings.json — never replace it.** The file may contain permissions, hooks, MCP server config, and other keys that are invisible to this skill but critical to the project. A full replace will silently delete them. Merge only the marketplace + enabledPlugins keys (handled by `bootstrap.py` in Workflow Step 2).
- **`AGENTS.md` symlink: check before creating.** If `AGENTS.md` already exists as a file (not a symlink), do not replace it — warn the user.
- **claudelint binary absence is not an error.** Print the install reminder and continue — the config is still useful for when the binary is later installed.
- **Do not install claudelint or any binary.** `/setup` is a scaffolding skill only. Binary installation is out of scope.

---

## Artifact Map

| Artifact | Output path | Created when |
|---|---|---|
| Drift-log open dir | `.claude/drift-log/open/` | always |
| Drift-log applied dir | `.claude/drift-log/applied/` | always |
| Claudelint config | `.claudelintrc.json` | always |
| Claudelint ignore | `.claudelintignore` | always |
| Skills README | `.claude/skills/README.md` | always |
| CLAUDE.md | `CLAUDE.md` (project root) | only if no `CLAUDE.md` exists |
| AGENTS.md symlink | `AGENTS.md` (project root) → `CLAUDE.md` | only if `CLAUDE.md` was just created |
| Claude settings | `.claude/settings.json` | always (create or merge) |

---

## References Guide

This skill has no `references/index/` files — all inputs are plugin templates resolved via `${CLAUDE_PLUGIN_ROOT}/templates/` and all outputs are written directly into the target project. No external navigation is required.

For the template sources, see:

| Template | Source path |
|---|---|
| `CLAUDE.md.tmpl` | `${CLAUDE_PLUGIN_ROOT}/templates/CLAUDE.md.tmpl` |
| `claudelintrc.json` | `${CLAUDE_PLUGIN_ROOT}/templates/claudelintrc.json` |
| `claudelintignore` | `${CLAUDE_PLUGIN_ROOT}/templates/claudelintignore` |
| `skills-authoring-standard.md` | `${CLAUDE_PLUGIN_ROOT}/templates/skills-authoring-standard.md` |
