# spark Repo Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standardize the spark marketplace repo on `uv`, extract `/setup`'s inline scripts into tested stdlib-python files, and give the repo its own dogfood surface (CLAUDE.md/AGENTS.md, README, `.mcp.example.json`).

**Architecture:** Five independent tasks. The SessionStart hook and `/setup` move from `jq`/inline-bash to `uv run --no-project python`; `/setup` logic lands in two stdlib PEP 723 scripts (`bootstrap.py`, `verify.py`) with `SKILL.md` reduced to a thin orchestrator; the repo gains a hand-authored CLAUDE.md + AGENTS.md symlink, a standardized README, and a committed `.mcp.example.json` with `${VAR}` placeholders.

**Tech Stack:** Claude Code plugins/hooks, `uv` (0.11.24), Python 3.9+ stdlib (`json`, `argparse`, `pathlib`, `shutil`, `subprocess`), JSON config.

## Global Constraints

- Single tooling prerequisite is `uv`; do not introduce `jq`, `yq`, or `npx`.
- Every `uv run` that executes inside an arbitrary repo MUST pass `--no-project`.
- Extracted scripts are stdlib-only, carry a PEP 723 header with `dependencies = []` and `requires-python = ">=3.9"`.
- No secrets in committed files; `.mcp.example.json` uses `${VAR}` placeholders only; `.mcp.json` stays git-ignored.
- `/setup` stays idempotent: a second run overwrites nothing and reports artifacts as SKIPPED.
- Marketplace identity is fixed: name `spark`, repo `bim-ba/ai`, plugin keys `core@spark` / `data@spark`.

---

### Task 1: SessionStart hook → uv

**Files:**
- Modify: `plugins/core/hooks/hooks.json` (SessionStart command only)

**Interfaces:**
- Consumes: `${CLAUDE_PLUGIN_ROOT}/hooks/behaviour-protocol.md` (unchanged).
- Produces: a SessionStart hook command emitting `{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":<file text>}}` via `uv`.

- [ ] **Step 1: Replace the jq command with uv**

In `plugins/core/hooks/hooks.json`, change the SessionStart `command` field from:

```
jq -Rs '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:.}}' "${CLAUDE_PLUGIN_ROOT}/hooks/behaviour-protocol.md"
```

to:

```
uv run --no-project python -c 'import json,sys; print(json.dumps({"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":open(sys.argv[1]).read()}}))' "${CLAUDE_PLUGIN_ROOT}/hooks/behaviour-protocol.md"
```

Leave the `Stop` hook and all `timeout` fields untouched.

- [ ] **Step 2: Verify the file is still valid JSON**

Run: `python3 -c "import json; json.load(open('plugins/core/hooks/hooks.json')); print('hooks.json OK')"`
Expected: `hooks.json OK`

- [ ] **Step 3: Verify the hook command reproduces the envelope**

Run (simulating the plugin loader by setting the env var):
```bash
CLAUDE_PLUGIN_ROOT="$(pwd)/plugins/core" \
  uv run --no-project python -c 'import json,sys; print(json.dumps({"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":open(sys.argv[1]).read()}}))' \
  "$(pwd)/plugins/core/hooks/behaviour-protocol.md" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["hookSpecificOutput"]["hookEventName"]=="SessionStart"; assert "Agent Behaviour Protocol" in d["hookSpecificOutput"]["additionalContext"]; print("hook envelope OK")'
```
Expected: `hook envelope OK`

- [ ] **Step 4: Commit**

```bash
git add plugins/core/hooks/hooks.json
git commit -m "refactor(core): SessionStart hook uses uv run, drops jq"
```

---

### Task 2: Extract /setup into bootstrap.py + verify.py

**Files:**
- Create: `plugins/core/skills/setup/scripts/bootstrap.py`
- Create: `plugins/core/skills/setup/scripts/verify.py`
- Modify: `plugins/core/skills/setup/SKILL.md` (replace the inline Workflow/Post-checks bodies with a thin orchestrator)

**Interfaces:**
- Consumes: `${CLAUDE_PLUGIN_ROOT}/templates/{claudelintrc.json,claudelintignore,skills-authoring-standard.md,CLAUDE.md.tmpl}` (existing files).
- Produces:
  - `bootstrap.py --project-root PATH --plugin-root PATH [--data]` — scaffolds, prints a summary, exit 0.
  - `verify.py --project-root PATH` — post-checks, exit 0 on pass / 1 on failure.

- [ ] **Step 1: Write `bootstrap.py`**

Create `plugins/core/skills/setup/scripts/bootstrap.py`:

```python
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Idempotent spark project scaffold. Creates missing artifacts, never overwrites."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def project_name(root):
    try:
        url = subprocess.check_output(
            ["git", "-C", str(root), "remote", "get-url", "origin"],
            stderr=subprocess.DEVNULL, text=True).strip()
        if url:
            name = url.rstrip("/").split("/")[-1]
            return name[:-4] if name.endswith(".git") else name
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return root.name


def merge_settings(root, enable_data, actions):
    path = root / ".claude" / "settings.json"
    settings = json.loads(path.read_text()) if path.exists() else {}
    changed = not path.exists()

    mkts = settings.setdefault("extraKnownMarketplaces", {})
    if "spark" not in mkts:
        mkts["spark"] = {"source": {"source": "github", "repo": "bim-ba/ai"}}
        changed = True

    plugins = settings.setdefault("enabledPlugins", {})
    if "core@spark" not in plugins:
        plugins["core@spark"] = True
        changed = True
    if enable_data and "data@spark" not in plugins:
        plugins["data@spark"] = True
        changed = True

    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(settings, indent=2) + "\n")
    actions.append(("PATCHED" if changed else "SKIPPED", ".claude/settings.json"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", required=True, type=Path)
    ap.add_argument("--plugin-root", required=True, type=Path)
    ap.add_argument("--data", action="store_true")
    args = ap.parse_args()

    root = args.project_root.resolve()
    templates = args.plugin_root.resolve() / "templates"
    actions = []

    def mkdir(rel):
        p = root / rel
        actions.append(("SKIPPED" if p.is_dir() else "CREATED", rel + "/"))
        p.mkdir(parents=True, exist_ok=True)

    def copy(src_name, rel):
        dst = root / rel
        if dst.exists():
            actions.append(("SKIPPED", rel))
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(templates / src_name, dst)
        actions.append(("CREATED", rel))

    mkdir(".claude/drift-log/open")
    mkdir(".claude/drift-log/applied")
    copy("claudelintrc.json", ".claudelintrc.json")
    copy("claudelintignore", ".claudelintignore")
    copy("skills-authoring-standard.md", ".claude/skills/README.md")

    claude_md = root / "CLAUDE.md"
    if claude_md.exists():
        actions.append(("SKIPPED", "CLAUDE.md"))
    else:
        tmpl = (templates / "CLAUDE.md.tmpl").read_text()
        claude_md.write_text(tmpl.replace("{{PROJECT_NAME}}", project_name(root)))
        actions.append(("CREATED", "CLAUDE.md"))
        agents = root / "AGENTS.md"
        if agents.is_symlink():
            actions.append(("SKIPPED", "AGENTS.md (symlink exists)"))
        elif agents.exists():
            actions.append(("WARN", "AGENTS.md is a real file — left as-is"))
        else:
            agents.symlink_to("CLAUDE.md")
            actions.append(("CREATED", "AGENTS.md -> CLAUDE.md"))

    merge_settings(root, args.data, actions)

    if shutil.which("claudelint") is None:
        print("note: claudelint not found — install it to lint your agent surface "
              "(config written anyway).")

    print("/setup complete")
    print("=" * 51)
    for status, label in actions:
        print(" {:<8} {}".format(status, label))
    print("=" * 51)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Write `verify.py`**

Create `plugins/core/skills/setup/scripts/verify.py`:

```python
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Post-checks for spark /setup. Exits non-zero on any failure."""
import argparse
import json
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", required=True, type=Path)
    args = ap.parse_args()
    root = args.project_root.resolve()
    errors = []

    for d in (".claude/drift-log/open", ".claude/drift-log/applied"):
        if not (root / d).is_dir():
            errors.append("missing dir: " + d)

    settings_path = root / ".claude" / "settings.json"
    if not settings_path.exists():
        errors.append("missing .claude/settings.json")
    else:
        s = json.loads(settings_path.read_text())
        if "spark" not in s.get("extraKnownMarketplaces", {}):
            errors.append("settings.json: extraKnownMarketplaces.spark absent")
        if "core@spark" not in s.get("enabledPlugins", {}):
            errors.append("settings.json: enabledPlugins.core@spark absent")

    agents = root / "AGENTS.md"
    if agents.is_symlink() and str(agents.readlink()) != "CLAUDE.md":
        errors.append("AGENTS.md symlink points to {}, expected CLAUDE.md".format(agents.readlink()))

    if errors:
        print("verify FAILED:")
        for e in errors:
            print("  - " + e)
        return 1
    print("verify OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Smoke-test bootstrap + verify against a fresh temp dir**

Run:
```bash
T=$(mktemp -d); git -C "$T" init -q
uv run --no-project plugins/core/skills/setup/scripts/bootstrap.py --project-root "$T" --plugin-root "$(pwd)/plugins/core" --data
uv run --no-project plugins/core/skills/setup/scripts/verify.py --project-root "$T"
echo "--- check symlink ---"; readlink "$T/AGENTS.md"
echo "--- check settings ---"; cat "$T/.claude/settings.json"
echo "$T"
```
Expected: bootstrap prints all `CREATED`/`PATCHED`; `verify OK`; `readlink` prints `CLAUDE.md`; settings.json contains `spark`, `core@spark`, and `data@spark`.

- [ ] **Step 4: Verify idempotency (second run skips everything)**

Run (reuse `$T` from Step 3, or recreate and run bootstrap once first):
```bash
uv run --no-project plugins/core/skills/setup/scripts/bootstrap.py --project-root "$T" --plugin-root "$(pwd)/plugins/core" --data | grep -c CREATED
```
Expected: `0` (every artifact already exists → all SKIPPED). Then clean up: `rm -rf "$T"`.

- [ ] **Step 5: Slim `SKILL.md` to a thin orchestrator**

In `plugins/core/skills/setup/SKILL.md`, replace the entire `## Workflow` section (all of Steps 1–7 and their code blocks) with:

````markdown
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

Pass `--data` only if the user invoked `/setup --data` (also enables the `data` plugin):

```bash
uv run --no-project "$CLAUDE_PLUGIN_ROOT/skills/setup/scripts/bootstrap.py" \
  --project-root "$PROJECT_ROOT" --plugin-root "$CLAUDE_PLUGIN_ROOT"   # add --data when requested
```

`bootstrap.py` is idempotent — it creates only missing artifacts and prints a CREATED/SKIPPED/PATCHED summary. It never overwrites `CLAUDE.md`, never writes drift-log entries, and merges `.claude/settings.json` without clobbering existing keys.

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
  2. git commit -m "chore: bootstrap spark scaffold"
  3. Edit CLAUDE.md — fill in Project Overview and project-specific conventions.
```
````

Then update the `## Post-checks` section body to a single line: "Post-checks are performed by `verify.py` in Workflow Step 3 (drift-log dirs, settings.json keys, AGENTS.md symlink). On `verify FAILED`, surface the listed problems." Leave the `## Purpose`, `## Pre-checks` intro, `## Guardrails`, `## Artifact Map`, and `## References Guide` sections intact (the Pre-checks `--data` note and Guardrails still apply).

- [ ] **Step 6: Verify SKILL.md no longer contains inline python heredocs**

Run: `grep -c "python3 - <<" plugins/core/skills/setup/SKILL.md || true`
Expected: `0`

- [ ] **Step 7: Commit**

```bash
git add plugins/core/skills/setup/scripts/bootstrap.py plugins/core/skills/setup/scripts/verify.py plugins/core/skills/setup/SKILL.md
git commit -m "refactor(core): extract /setup into bootstrap.py + verify.py, slim SKILL.md"
```

---

### Task 3: Repo CLAUDE.md + AGENTS.md symlink

**Files:**
- Create: `CLAUDE.md` (repo root, hand-authored)
- Create: `AGENTS.md` (symlink → `CLAUDE.md`)

**Interfaces:**
- Consumes: nothing.
- Produces: the repo's own agent-instruction surface.

- [ ] **Step 1: Write the repo CLAUDE.md**

Create `CLAUDE.md` at the repo root:

```markdown
# spark

> Baseline agent behavior is injected each session by `spark/core` via its SessionStart hook (`plugins/core/hooks/behaviour-protocol.md`). This file adds rules specific to developing the marketplace itself.

## Project Overview

`spark` is a Claude Code plugin marketplace published from `github.com/bim-ba/ai`. It ships two plugins:

- **`core`** — generic agent behavior (the SessionStart behaviour-protocol hook + a Stop drift-log reminder), reusable workflow skills, the `/setup` scaffolder, and project templates.
- **`data`** — reusable data-engineering rulebook skills (ClickHouse query practices).

## Structure

- `.claude-plugin/marketplace.json` — marketplace manifest (name `spark`, plugins `core` + `data`).
- `plugins/core/` — `hooks/`, `skills/`, `templates/`.
- `plugins/data/` — `skills/`.
- `docs/superpowers/` — specs and implementation plans.

## Conventions

- **`uv` is the single tooling prerequisite.** The SessionStart hook and `/setup` run Python through `uv run --no-project`. Do not introduce `jq`, `yq`, or `npx`.
- **Extracted scripts are stdlib-only** with a PEP 723 header (`requires-python = ">=3.9"`, `dependencies = []`), run via `uv run`.
- **Skills follow** `plugins/core/templates/skills-authoring-standard.md` (workflow vs rulebook categories, naming convention, self-contained structure).
- **Plugins cannot inject always-on instructions** — generic behavior goes through the `core` SessionStart hook, never a shipped CLAUDE.md.
- Work stays on the feature branch (`feat/claude-toolkit-bootstrap`); do not merge to `main` without an explicit ask.
```

- [ ] **Step 2: Create the AGENTS.md symlink**

Run:
```bash
ln -s CLAUDE.md AGENTS.md
```

- [ ] **Step 3: Verify the symlink**

Run: `readlink AGENTS.md`
Expected: `CLAUDE.md`

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md AGENTS.md
git commit -m "docs: add repo CLAUDE.md + AGENTS.md symlink (dogfood)"
```

---

### Task 4: Standardized README

**Files:**
- Modify: `README.md` (replace the current minimal content)

**Interfaces:**
- Consumes: the skill inventory of `core` and `data` (listed below — do not re-derive).
- Produces: a low-barrier onboarding README.

- [ ] **Step 1: Overwrite README.md**

Replace the entire contents of `README.md` with:

```markdown
# spark

A Claude Code plugin marketplace providing reusable agent behavior, project scaffolding, and data-engineering skills.

- **`core`** — generic agent behavior (injected each session), reusable workflow skills, and a `/setup` scaffolder.
- **`data`** — data-engineering rulebook skills (ClickHouse query practices).

## Requirements

- [`uv`](https://docs.astral.sh/uv/) — **required**. The `core` SessionStart hook and the `/setup` scripts run Python through `uv run`. Without `uv`, the behaviour-protocol injection is skipped (the session still works).
- Claude Code.

## Install

```
/plugin marketplace add bim-ba/ai
```

Then enable the plugins you need — `core` for any project, `data` for data projects.

## Plugins

| Plugin | Skills |
|--------|--------|
| `core` | `setup`, `reviewing-agent-instructions`, `documenting-meetings`, `researching-rigorously`, `using-playwright`, `creating-drift-logs`, `reviewing-drift-logs` |
| `data` | `clickhouse-query-best-practices` |

## Quickstart

In any project, run:

```
/setup            # scaffold core conventions
/setup --data     # also enable the data plugin
```

`/setup` creates the drift-log directories, claudelint config, a skills-authoring standard, a thin `CLAUDE.md` (+ `AGENTS.md` symlink), and wires the `spark` marketplace into `.claude/settings.json`. It is idempotent — safe to re-run.

## MCP configuration

The repo ships an `.mcp.example.json` with the MCP servers used during development (context7, deepwiki, brave, github). To use it:

```
cp .mcp.example.json .mcp.json
```

Then export the referenced environment variables (`CONTEXT7_API_KEY`, `BRAVE_API_KEY`, `GITHUB_PAT`). `.mcp.json` is git-ignored — never commit real keys.

## Contributing

- Work happens on feature branches.
- New skills follow `plugins/core/templates/skills-authoring-standard.md`.
- Specs and plans live in `docs/superpowers/`.
```

- [ ] **Step 2: Verify the skill names listed in the README exist**

Run:
```bash
for s in setup reviewing-agent-instructions documenting-meetings researching-rigorously using-playwright creating-drift-logs reviewing-drift-logs; do test -f "plugins/core/skills/$s/SKILL.md" || echo "MISSING core/$s"; done
test -f plugins/data/skills/clickhouse-query-best-practices/SKILL.md || echo "MISSING data/clickhouse"
echo "skill-name check done"
```
Expected: only `skill-name check done` (no `MISSING` lines).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: standardized README with requirements, plugins, quickstart"
```

---

### Task 5: .mcp.example.json

**Files:**
- Create: `.mcp.example.json` (committed)

**Interfaces:**
- Consumes: nothing.
- Produces: an MCP config template using `${VAR}` placeholders.

- [ ] **Step 1: Confirm `.mcp.example.json` is not git-ignored**

Run: `git check-ignore .mcp.example.json && echo "IGNORED (bad)" || echo "tracked OK"`
Expected: `tracked OK` (only `.mcp.json` is ignored, not the example).

- [ ] **Step 2: Write `.mcp.example.json`**

Create `.mcp.example.json` at the repo root:

```json
{
  "mcpServers": {
    "context7": {
      "type": "http",
      "url": "https://mcp.context7.com/mcp",
      "headers": {
        "CONTEXT7_API_KEY": "${CONTEXT7_API_KEY}"
      }
    },
    "deepwiki": {
      "type": "http",
      "url": "https://mcp.deepwiki.com/mcp"
    },
    "brave": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@brave/brave-search-mcp-server", "--transport", "stdio"],
      "env": {
        "BRAVE_API_KEY": "${BRAVE_API_KEY}"
      }
    },
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": {
        "Authorization": "Bearer ${GITHUB_PAT}"
      }
    }
  }
}
```

- [ ] **Step 3: Verify it parses and contains no secret literals**

Run:
```bash
python3 -c "import json; json.load(open('.mcp.example.json')); print('json OK')"
grep -Eq 'ctx7sk-|github_pat_|BSAmU1' .mcp.example.json && echo "SECRET LEAK" || echo "no secrets OK"
```
Expected: `json OK` then `no secrets OK`.

- [ ] **Step 4: Commit**

```bash
git add .mcp.example.json
git commit -m "chore: ship .mcp.example.json template with placeholder env vars"
```

---

## Self-Review Notes

- **Spec coverage:** Component 1 → Task 1; Component 2 → Task 2; Component 3 → Task 3; Component 4 → Task 4; Component 5 → Task 5. All five covered.
- **Idempotency** (global constraint) is exercised by Task 2 Step 4.
- **No-secrets** (global constraint) is exercised by Task 5 Step 3.
- **`--no-project`** appears on every `uv run` in the plan. It is strictly required only for the hook's `python -c` form (no script file → uv would otherwise do project discovery); for the PEP 723 script invocations it is redundant but harmless (a `# /// script` file runs in uv's script mode and ignores the surrounding project — verified: the script ran cleanly even from inside a project with an unresolvable dependency). Adding it everywhere keeps the global constraint literally true and removes any project-attachment risk.
```
