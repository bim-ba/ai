---
name: setup
description: "Use when bootstrapping a new (or existing) project to reuse the shared spark conventions — scaffolds drift-log, claudelint config, a thin CLAUDE.md, and wires the core/data plugins into .claude/settings.json. Idempotent."
type: skill
category: workflow
---

# /setup — Project Bootstrap Skill

Scaffolds a target project with the spark conventions: drift-log, claudelint config, skills authoring standard, a thin CLAUDE.md, and the required `.claude/settings.json` plugin wiring. Safe to re-run — only creates what is missing.

## Purpose

### What this skill enables

Brings a project into the spark ecosystem in one shot: creates the directory structure and config files every agent-aware repo needs, and wires the `core` (and optionally `data`) plugin into `.claude/settings.json` so Claude Code resolves the marketplace correctly.

### When to use it

- Bootstrapping a brand-new project repository.
- Onboarding an existing repository that has no spark scaffold yet.
- Re-running `/setup` after the first pass to catch any files that were missing (idempotent — always safe).

### When NOT to use it

- For updating or replacing an existing `CLAUDE.md` with new content (edit it directly instead).
- For plugin-specific setup steps that are out of scope of the core scaffold (e.g., data-pipeline config, secrets management).
- When the project already has a fully wired spark setup and you only want to update one piece (use Edit directly).

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
   - `--data` → also enable the `data` plugin in `enabledPlugins`. **When present, run `export SETUP_DATA=1`** now, so the Step 6 merge picks it up.

---

## Workflow

Work through every step below in order. For each file or directory, check whether it already exists before acting. **Never overwrite existing files** — log skips clearly. Collect all created/skipped decisions and report them in Step 7.

### Step 1 — Detect project root and existing `.claude/` state

```bash
export PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
echo "Project root: $PROJECT_ROOT"
ls "$PROJECT_ROOT/.claude/" 2>/dev/null && echo ".claude/ exists" || echo ".claude/ not found — will create"
```

Record whether `.claude/` already exists. Either way, proceed — idempotency is per-file, not per-directory.

### Step 2 — Set up drift-log directories

Create the drift-log directory structure (skip if directories already exist):

```bash
mkdir -p "$PROJECT_ROOT/.claude/drift-log/open"
mkdir -p "$PROJECT_ROOT/.claude/drift-log/applied"
```

Print the following pointer for the user:

> Drift-log conventions live in the `creating-drift-logs` and `reviewing-drift-logs` skills (from the `core` plugin) — no per-project README/template is copied.

### Step 3 — Copy claudelint config

```bash
# .claudelintrc.json — only if absent
[ -f "$PROJECT_ROOT/.claudelintrc.json" ] \
  || cp "${CLAUDE_PLUGIN_ROOT}/templates/claudelintrc.json" \
        "$PROJECT_ROOT/.claudelintrc.json"

# .claudelintignore — only if absent
[ -f "$PROJECT_ROOT/.claudelintignore" ] \
  || cp "${CLAUDE_PLUGIN_ROOT}/templates/claudelintignore" \
        "$PROJECT_ROOT/.claudelintignore"
```

Check whether the binary is available:

```bash
command -v claudelint > /dev/null 2>&1 \
  || echo "claudelint not found — install it to lint your agent surface (config written anyway)."
```

### Step 4 — Copy skills-authoring-standard.md

```bash
mkdir -p "$PROJECT_ROOT/.claude/skills"

# .claude/skills/README.md — only if absent
[ -f "$PROJECT_ROOT/.claude/skills/README.md" ] \
  || cp "${CLAUDE_PLUGIN_ROOT}/templates/skills-authoring-standard.md" \
        "$PROJECT_ROOT/.claude/skills/README.md"
```

### Step 5 — CLAUDE.md and AGENTS.md symlink

**Case A: No root `CLAUDE.md` exists.** Instantiate from the template and create the symlink.

First, read `${CLAUDE_PLUGIN_ROOT}/templates/CLAUDE.md.tmpl` and substitute `{{PROJECT_NAME}}` with the project's directory basename (or the git remote repo name if available):

```bash
PROJECT_NAME=$(basename "$PROJECT_ROOT")
# Optionally, prefer the git remote name:
# PROJECT_NAME=$(git remote get-url origin 2>/dev/null | sed 's|.*/||; s|\.git$||') \
#   || PROJECT_NAME=$(basename "$PROJECT_ROOT")

if [ ! -f "$PROJECT_ROOT/CLAUDE.md" ]; then
  sed "s/{{PROJECT_NAME}}/$PROJECT_NAME/g" \
      "${CLAUDE_PLUGIN_ROOT}/templates/CLAUDE.md.tmpl" \
      > "$PROJECT_ROOT/CLAUDE.md"

  # Create AGENTS.md symlink pointing at CLAUDE.md (only if absent)
  [ -e "$PROJECT_ROOT/AGENTS.md" ] \
    || ln -s CLAUDE.md "$PROJECT_ROOT/AGENTS.md"
fi
```

**Case B: A root `CLAUDE.md` already exists.** Leave it completely untouched. Print exactly:

> `CLAUDE.md` already exists — left as-is. Note: baseline agent behavior now comes from the `core` plugin (injected via the SessionStart hook). You may want to remove generic protocol prose from `CLAUDE.md` that is now duplicated by the plugin baseline.

### Step 6 — Patch `.claude/settings.json`

Read the existing `.claude/settings.json` if it exists (or treat it as `{}`). Merge in the required keys without clobbering any existing top-level keys or nested values the user already has.

The JSON shape to merge follows exactly the convention used in Claude Code settings files. The required additions are:

```json
{
  "extraKnownMarketplaces": {
    "spark": {
      "source": {
        "source": "github",
        "repo": "bim-ba/ai"
      }
    }
  },
  "enabledPlugins": {
    "core@spark": true
  }
}
```

If `--data` was passed, also add to `enabledPlugins`:

```json
{
  "enabledPlugins": {
    "core@spark": true,
    "data@spark": true
  }
}
```

**Merge rules (apply in this order):**

1. If `.claude/settings.json` does not exist, write the above JSON (with the appropriate `enabledPlugins` for flags) as the entire file.
2. If it exists, read it as JSON. For `extraKnownMarketplaces`, add the `spark` key only if it is not already present. For `enabledPlugins`, add `core@spark: true` (and `data@spark: true` if `--data`) only if those keys are not already present. All other existing keys at every level are preserved verbatim.
3. Write the merged JSON back to `.claude/settings.json` with 2-space indentation.

Example: if the existing file already contains `"superpowers@claude-plugins-official": true` in `enabledPlugins`, the result must contain both that entry and the new `core@spark` entry.

Concrete approach using Python (available on most systems):

```bash
# PROJECT_ROOT must be exported (Step 1 does this) so the heredoc can read it.
# If the user passed --data, export SETUP_DATA=1 first so the merge enables the data plugin:
#   export SETUP_DATA=1
python3 - <<'EOF'
import json, os, sys

settings_path = os.path.join(os.environ["PROJECT_ROOT"], ".claude", "settings.json")
enable_data   = os.environ.get("SETUP_DATA", "") == "1"

# Load existing settings or start empty
if os.path.exists(settings_path):
    with open(settings_path) as f:
        settings = json.load(f)
else:
    settings = {}

# Merge extraKnownMarketplaces
mkts = settings.setdefault("extraKnownMarketplaces", {})
if "spark" not in mkts:
    mkts["spark"] = {
        "source": {
            "source": "github",
            "repo": "bim-ba/ai"
        }
    }

# Merge enabledPlugins
plugins = settings.setdefault("enabledPlugins", {})
if "core@spark" not in plugins:
    plugins["core@spark"] = True
if enable_data and "data@spark" not in plugins:
    plugins["data@spark"] = True

os.makedirs(os.path.dirname(settings_path), exist_ok=True)
with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

print("settings.json written.")
EOF
```

### Step 7 — Print summary

Print a summary table of every file that was **created** or **skipped**, followed by next steps.

Example output format:

```
/setup complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 CREATED  .claude/drift-log/open/              (empty dir)
 CREATED  .claude/drift-log/applied/           (empty dir)
 CREATED  .claudelintrc.json
 CREATED  .claudelintignore
 CREATED  .claude/skills/README.md
 CREATED  CLAUDE.md
 CREATED  AGENTS.md  →  CLAUDE.md
 PATCHED  .claude/settings.json               (spark marketplace + core plugin)
 SKIPPED  [any files that already existed]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Next steps:
  1. git add .claude/ CLAUDE.md AGENTS.md .claudelintrc.json .claudelintignore
  2. git commit -m "chore: bootstrap spark scaffold"
  3. Edit CLAUDE.md — fill in Project Overview and project-specific conventions.
```

---

## Post-checks

After running all steps, verify:

1. `.claude/drift-log/open/` and `.claude/drift-log/applied/` exist as directories.
2. `.claude/settings.json` contains the `spark` key under `extraKnownMarketplaces` and `core@spark` under `enabledPlugins`. Quick check:
   ```bash
   python3 -c "import json, os; p=os.path.join(os.environ['PROJECT_ROOT'],'.claude','settings.json'); \
     s=json.load(open(p)); \
     assert 'spark' in s.get('extraKnownMarketplaces', {}); \
     assert 'core@spark' in s.get('enabledPlugins', {}); print('settings.json OK')"
   ```
3. If `CLAUDE.md` was created, confirm `AGENTS.md` is a symlink to it:
   ```bash
   readlink "$PROJECT_ROOT/AGENTS.md"   # should print: CLAUDE.md
   ```
4. No existing files were overwritten. The skipped list in the summary accounts for every file that already existed.

---

## Guardrails

- **Never overwrite `CLAUDE.md`** even if its content looks stale. The user owns it. Print the reminder and stop.
- **Never write drift-log entry files** (`open/*.md`, `applied/*.md`). This skill only creates the `open/` and `applied/` directories (`mkdir -p`); it never writes individual entries. The drift-log is an immutable historical record — entry creation is out of scope for `/setup`.
- **Merge settings.json — never replace it.** The file may contain permissions, hooks, MCP server config, and other keys that are invisible to this skill but critical to the project. A full replace will silently delete them. Merge only the specific keys defined in Step 6.
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
