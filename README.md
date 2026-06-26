# spark

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-5A67D8)](https://docs.claude.com/en/docs/claude-code)
[![powered by uv](https://img.shields.io/badge/powered%20by-uv-DE5FE9)](https://docs.astral.sh/uv/)
[![GitHub last commit](https://img.shields.io/github/last-commit/bim-ba/ai)](https://github.com/bim-ba/ai/commits)

A Claude Code plugin marketplace providing reusable agent behavior, project scaffolding, and data-engineering skills.

## Requirements

- [`uv`](https://docs.astral.sh/uv/) — **required**. The `core` SessionStart hook and the `/setup` scripts run Python through `uv run`. Without `uv`, the behaviour-protocol injection is skipped (the session still works).
- Claude Code.

## Install

```
/plugin marketplace add bim-ba/ai
```

Then enable the plugins you need — `core` for any project, `data` for data projects.

## Domains

| Domain | Purpose | Enable when |
|--------|---------|-------------|
| `core` | Generic agent behavior (injected each session), reusable workflow skills, the `/setup` scaffolder, and project templates. | Always — it is the baseline for any project. |
| `data` | Data-engineering rulebook skills (ClickHouse / federated-query practices). | Working in a dbt / ClickHouse data project. |

## Skills

| Skill | Domain | What it does | Triggers |
|-------|--------|--------------|----------|
| `setup` | core | Bootstraps a project with spark conventions (drift-log dirs, claudelint config, a thin CLAUDE.md + AGENTS.md, plugin wiring). Idempotent. | Manual: `/setup` |
| `creating-drift-logs` | core | Captures a divergence between actual behavior and codified instructions as an immutable drift-log entry, so good conventions can be promoted later. | Auto (8 drift triggers); nudged by the Stop hook |
| `reviewing-drift-logs` | core | Triages the drift-log — promotes open→applied, checks staleness, compacts entries, codifies insights into rules. | Manual |
| `reviewing-agent-instructions` | core | Audits the agent-instruction surface (CLAUDE.md, skills, drift-log, hooks) for pollution, duplication, dead refs, and contradictions. Report-only, no auto-fix. | Manual |
| `researching-rigorously` | core | Rigorous research / validation / fact-check: fans out parallel subagents per source, cross-validates via MCP + web, and cites sources. | Auto on research / validation tasks |
| `documenting-meetings` | core | Turns an SRT audio transcript into structured meeting notes (decisions, action items, discussion summary). | Manual |
| `using-playwright` | core | Drives web UIs through the Playwright MCP — SSO login, Monaco/textarea editors, content extraction. | Auto when using the Playwright MCP |
| `clickhouse-query-best-practices` | data | Rulebook for ad-hoc research SQL in dbt-ClickHouse and federated `postgresql()` queries (CTE-wrapping, dedup, flow analysis, source citation, style). | Auto when writing / reviewing ClickHouse SQL |

## Hooks (core)

| Hook | What it does | When |
|------|--------------|------|
| `SessionStart` | Injects the `core` behaviour protocol (`behaviour-protocol.md`) as baseline conventions for the session. | Every session / subagent start |
| `Stop` | Reminds the agent to scan the last turn against the 8 drift triggers and log an entry if any fired. | When the agent finishes a turn |

## Quickstart

In any project:

```
/setup                   # enable just core
/setup --with core,data  # enable core + data
/setup --with data       # same as above — core is always enabled
```

`/setup` creates the drift-log directories, claudelint config, a skills-authoring standard, a thin `CLAUDE.md` (+ `AGENTS.md` symlink), and wires the `spark` marketplace into `.claude/settings.json`. It is idempotent — safe to re-run.

## MCP configuration

The repo ships an `.mcp.example.json` with the MCP servers used during development:

| Server | Purpose | API key |
|--------|---------|---------|
| `context7` | Up-to-date library / framework / API documentation. | `CONTEXT7_API_KEY` (optional) |
| `deepwiki` | Q&A over public GitHub repository docs. | none |
| `brave` | Web search. | `BRAVE_API_KEY` |
| `github` | GitHub repository / PR / issue operations (Copilot MCP endpoint). | `GITHUB_PAT` |

To use it:

```
cp .mcp.example.json .mcp.json
```

Then export the referenced environment variables. `.mcp.json` is git-ignored — never commit real keys.

## Contributing

- Work happens on feature branches.
- New skills follow `plugins/core/templates/skills-authoring-standard.md`.
- Specs and plans live in `docs/superpowers/`.

## License

[MIT](LICENSE) © 2026 Sava Znatnov
