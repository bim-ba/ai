# spark Repo Polish — Design

**Date:** 2026-06-26
**Branch:** feat/claude-toolkit-bootstrap
**Status:** Approved

## Goal

Polish the `spark` marketplace repo for public consumption and self-dogfooding:
standardize the project on `uv` as its single tooling prerequisite, extract the
`/setup` skill's inline scripts into a tested `scripts/` directory, give the repo
its own agent-instruction surface (CLAUDE.md + AGENTS.md), a low-barrier README,
and a committed `.mcp.example.json` template.

## Global Constraints

- **Single tooling prerequisite: `uv`.** No `jq`, no `yq`, no `npx` introduced by
  this work. Python invoked only via `uv run`.
- **`uv run` must use `--no-project`** wherever it runs inside an arbitrary repo
  (the SessionStart hook, `/setup` against a target project), so it never attaches
  to or syncs the surrounding project's `pyproject.toml`.
- **Extracted scripts are stdlib-only**, carry a PEP 723 header (`# /// script`)
  with empty `dependencies`, and run under `uv run`.
- **No secrets in committed files.** `.mcp.example.json` uses `${VAR}` placeholders
  only. `.mcp.json` stays git-ignored.
- **Idempotency preserved.** `/setup` must remain safe to re-run — second run
  reports every artifact as SKIPPED, creates/overwrites nothing.
- **Marketplace identity unchanged:** name `spark`, repo `bim-ba/ai`, plugin keys
  `core@spark` / `data@spark`.

## Context

Current state worth knowing:

- The only `jq` usage in the repo is the SessionStart hook in
  `plugins/core/hooks/hooks.json`, which wraps `behaviour-protocol.md` into the
  `{hookSpecificOutput:{hookEventName,additionalContext}}` envelope.
- The Stop hook is a pure `echo` reminder — out of scope, unchanged.
- `/setup`'s `SKILL.md` currently embeds bash heredocs + an inline `python3`
  settings-merge. Logic to extract: drift-log dir creation, claudelint config copy,
  skills README copy, CLAUDE.md instantiation + AGENTS symlink, `settings.json`
  merge, summary table, post-checks.
- `.mcp.json` exists locally (git-ignored), holds live secrets, and was verified
  **never committed** (`git log --all -- .mcp.json` empty). Key rotation is the
  user's call and out of scope for this work.
- `uv` 0.11.24 is installed; `uv run --no-project python -c '<json wrap>'` was
  smoke-verified to reproduce the hook envelope (exit 0).

## Components

### 1. Hook tooling → uv

**File:** `plugins/core/hooks/hooks.json` (SessionStart command only).

Replace:
```
jq -Rs '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:.}}' "${CLAUDE_PLUGIN_ROOT}/hooks/behaviour-protocol.md"
```
with an inline `uv run` that does the same wrap via stdlib `json`:
```
uv run --no-project python -c 'import json,sys; print(json.dumps({"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":open(sys.argv[1]).read()}}))' "${CLAUDE_PLUGIN_ROOT}/hooks/behaviour-protocol.md"
```
Keep `timeout: 5`.

**Consequence:** `uv` becomes a hard runtime prerequisite for the `core` plugin —
without it the hook fails and the behaviour protocol is not injected (the session
still runs; Claude Code tolerates hook failure). This is documented in the README
Requirements section (Component 4).

**Verification:** after editing, re-run the exact command against the real
`behaviour-protocol.md` and confirm it prints the envelope with `exit 0`.

### 2. /setup script extraction

**New dir:** `plugins/core/skills/setup/scripts/`

Two stdlib-only PEP 723 scripts, run via `uv run`:

**`bootstrap.py`** — idempotent scaffold, single source of the create/skip logic.
- CLI: `bootstrap.py --project-root PATH --plugin-root PATH [--data]`
- Responsibilities (each create-if-absent; never overwrite):
  1. `mkdir -p .claude/drift-log/{open,applied}`
  2. copy `templates/claudelintrc.json` → `.claudelintrc.json`
  3. copy `templates/claudelintignore` → `.claudelintignore`
  4. copy `templates/skills-authoring-standard.md` → `.claude/skills/README.md`
  5. instantiate `templates/CLAUDE.md.tmpl` → `CLAUDE.md` (substitute
     `{{PROJECT_NAME}}` = git remote repo name, else project-dir basename); only if
     no `CLAUDE.md` exists, and on creation also `ln -s CLAUDE.md AGENTS.md`
     (skip symlink if `AGENTS.md` already exists — warn if it's a real file)
  6. merge `.claude/settings.json` (non-clobber `setdefault`): add
     `extraKnownMarketplaces.spark` (source github / repo `bim-ba/ai`) if absent,
     `enabledPlugins["core@spark"]=true` if absent, and `["data@spark"]=true` if
     `--data` and absent
- Prints the create/skip summary table.
- claudelint binary absence → printed reminder, not an error.

**`verify.py`** — post-checks, exits non-zero on failure.
- CLI: `verify.py --project-root PATH`
- Asserts: both drift-log dirs exist; `settings.json` has `spark` under
  `extraKnownMarketplaces` and `core@spark` under `enabledPlugins`; if `AGENTS.md`
  exists it is a symlink to `CLAUDE.md`.

**`SKILL.md`** slims to a thin orchestrator:
- Pre-check (bash, stays in markdown — env-specific): resolve `PROJECT_ROOT`
  (`git rev-parse --show-toplevel || pwd`) and `CLAUDE_PLUGIN_ROOT` (env, else the
  existing `find`-based discovery), assert `$CLAUDE_PLUGIN_ROOT/templates` exists.
- Parse `--data` flag from the invocation.
- Run `uv run "$CLAUDE_PLUGIN_ROOT/skills/setup/scripts/bootstrap.py" --project-root "$PROJECT_ROOT" --plugin-root "$CLAUDE_PLUGIN_ROOT" [--data]`.
- Run `uv run "$CLAUDE_PLUGIN_ROOT/skills/setup/scripts/verify.py" --project-root "$PROJECT_ROOT"`.
- Keep Purpose / When-to-use / Guardrails / Artifact Map sections; drop the inline
  bash/python bodies now living in the scripts.

**Verification:** smoke test against a fresh temp dir — run bootstrap then verify
(expect all CREATED + verify pass), then run bootstrap again (expect all SKIPPED,
nothing overwritten).

### 3. Repo CLAUDE.md + AGENTS.md

**Files:** `CLAUDE.md` (repo root, hand-authored), `AGENTS.md` → symlink.

Hand-author (NOT from the `/setup` template — this repo is the marketplace itself,
not a consumer project). Contents, thin:
- Project overview: spark is a Claude Code plugin marketplace (`core` + `data`).
- Structure: `plugins/core` (behaviour hook, workflow skills, /setup, templates),
  `plugins/data` (rulebook skills), `.claude-plugin/marketplace.json`.
- Conventions: `uv` is the single tooling prerequisite; extracted scripts are
  stdlib + PEP 723 run via `uv run --no-project`; skills follow
  `templates/skills-authoring-standard.md`; work stays on the feature branch.
- Pointer to `docs/superpowers/` for specs/plans.

`AGENTS.md` is a symlink to `CLAUDE.md` (`ln -s CLAUDE.md AGENTS.md`).

### 4. Standardized README

**File:** `README.md` (overwrite the current minimal one).

Sections, low barrier to entry:
1. Title + one-line description.
2. **Requirements** — `uv` (required: the behaviour hook and `/setup` run through
   it), Claude Code.
3. **Install** — `/plugin marketplace add bim-ba/ai`, enable `core` (+ `data`).
4. **Plugins** — table: `core` (behaviour protocol hook + workflow skills +
   `/setup` + templates) and `data` (clickhouse rulebook), each with its skill list.
5. **Quickstart** — `/setup` in a project; what it scaffolds.
6. **MCP configuration** — `cp .mcp.example.json .mcp.json`, export the referenced
   env vars; note `.mcp.json` is git-ignored.
7. **Contributing** — branch policy, skills authoring standard pointer.

### 5. .mcp.example.json

**File:** `.mcp.example.json` (committed; `.mcp.json` stays ignored).

Servers with `${VAR}` placeholders only — no live values:
- `context7` — http `https://mcp.context7.com/mcp`, header
  `CONTEXT7_API_KEY: ${CONTEXT7_API_KEY}`.
- `deepwiki` — http `https://mcp.deepwiki.com/mcp` (no key).
- `brave` — stdio `npx -y @brave/brave-search-mcp-server --transport stdio`,
  env `BRAVE_API_KEY: ${BRAVE_API_KEY}`.
- `github` — http `https://api.githubcopilot.com/mcp/`, header
  `Authorization: Bearer ${GITHUB_PAT}`.

**Verification:** file parses as JSON; grep confirms no `ctx7sk-`, no
`github_pat_`, no `BSA` literal present.

## Testing Strategy

- **Hook:** re-run the new `uv run --no-project …` command against the real
  `behaviour-protocol.md`; assert it prints the `{hookSpecificOutput…}` envelope
  and exits 0.
- **/setup scripts:** smoke test in a temp dir — `bootstrap.py` (all CREATED) →
  `verify.py` (pass) → `bootstrap.py` again (all SKIPPED, no overwrite). With and
  without `--data`.
- **.mcp.example.json:** `python -c json.load` parses; secret-literal grep is empty.
- **README / CLAUDE.md / AGENTS.md:** AGENTS.md `readlink` → `CLAUDE.md`; manual
  read for accuracy.

## Out of Scope

- Rotating the leaked GitHub PAT / other live keys (user's action).
- Touching the Stop hook (pure echo, unchanged).
- Phase 5 project retrofit and Phase 6 personal `~/.claude` voice (separate, gated).
- Adding any third-party python dependency to the extracted scripts (stdlib only).
