# ai

> Baseline agent behavior is injected each session by `ai/core` via its SessionStart hook (`plugins/core/hooks/behaviour-protocol.md`). This file adds rules specific to developing the marketplace itself.

## Project Overview

`ai` is a Claude Code plugin marketplace published from `github.com/bim-ba/ai`. It ships two plugins:

- **`core`** — generic agent behavior (the SessionStart behaviour-protocol hook + a Stop drift-log reminder), reusable workflow skills, the `/setup` scaffolder, and project templates.
- **`data`** — reusable data-engineering rulebook skills (ClickHouse query practices).

## Structure

- `.claude-plugin/marketplace.json` — marketplace manifest (name `ai`, plugins `core` + `data`).
- `plugins/core/` — `hooks/`, `skills/`, `templates/`.
- `plugins/data/` — `skills/`.
- `docs/superpowers/` — specs and implementation plans.

## Conventions

- **`uv` is the tooling prerequisite for the Claude Code side and all repo Python.** The SessionStart hook and `/setup` run Python through `uv run`; do not introduce `jq`, `yq`, or `npx`.
- **Extracted scripts are stdlib-only** with a PEP 723 header (`requires-python = ">=3.9"`, `dependencies = []`), run via `uv run`.
- **Skills follow** `plugins/core/templates/skills-authoring-standard.md` (workflow vs rulebook categories, naming convention, self-contained structure).
- **Hooks and custom agents follow** `plugins/core/templates/hooks-authoring-standard.md` and `agents-authoring-standard.md` (module-per-hook wired through `settings.json`; self-contained agent prompts with baked-in dispatch guards). Consulted on-demand, not scaffolded by `/setup`.
- **Plugins cannot inject always-on instructions** — generic behavior goes through the `core` SessionStart hook, never a shipped CLAUDE.md.
- **`main` is the published trunk** the marketplace resolves from (`/plugin marketplace add bim-ba/ai`) — keep it working. Do feature work on branches and merge into `main` via PR.
