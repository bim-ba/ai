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
