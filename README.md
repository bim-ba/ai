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
