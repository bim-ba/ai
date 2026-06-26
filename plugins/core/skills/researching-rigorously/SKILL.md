---
name: researching-rigorously
description: Use for any research, validation, or fact-check task -- before answering a load-bearing question or committing to an approach. Orients via local sources and knowledge tools, fans out parallel subagents per source, cross-validates via MCP servers and web research, and cites sources.
type: skill
category: workflow
---

# Skill: researching-rigorously

## Purpose

Answer a load-bearing question (or de-risk a decision) by triangulating across the sources actually available, instead of trusting training data or a single tool. The output is a cited finding, not a guess.

- **When to use:** any non-trivial fact-check, "is X true in this system?", library/API behavior, locating an object/page/code, parity/source-of-truth questions, validating prior findings.
- **When NOT to use:** a value you can read directly from one known file in one step (just read it).

## The source ladder (cheapest-first)

Stop as soon as a source settles the question; escalate only if it doesn't. Always cite what you used.

1. **Local sources and repos (offline, fastest)**
   - Local file clones and mirrors: `rg`/`fd` them FIRST. Directory trees often mirror external hierarchies, so they also tell you where new content belongs.
   - Read file contents from local clones directly (not via remote API MCPs when a local copy exists).
   - Any locally available knowledge graphs or pre-built indexes — orient before grepping.

2. **Available knowledge tools**
   - Graph/navigation tools if present (query/path/explain operations): orient before grepping; verify load-bearing facts against source.
   - Semantic search indexes, embeddings, or local catalog tools if configured.

3. **MCP servers for live state**
   - Database/query MCPs (data + run history; respect concurrency limits — single-threaded tools stay on the orchestrator).
   - VCS/CI MCPs (server-side entities: PRs, CI runs, approvals — not file contents; read code from local clone).
   - Catalog/lineage MCPs (metadata, schema, data lineage).
   - Wiki/docs MCPs (non-mirrored pages or live content).
   - Task/issue tracker MCPs (tasks, boards, sprints).

4. **SaaS MCPs for external docs**
   - `context7` (library/framework/API docs)
   - `deepwiki` (GitHub repos)
   - `brave` or equivalent (web search)
   - Specialized model/dataset/paper indexes as available.

5. **Web research** — use when no MCP covers the question; cite the exact URL and retrieval date for every load-bearing claim.

## Parallel fan-out

When the question splits into independent sub-questions or distinct sources (e.g. "how is X documented in the catalog?" vs "what does the spec say?" vs "what does the code actually do?"), dispatch **one subagent per source/place in a single message** (see `superpowers:dispatching-parallel-agents`). Keep on the orchestrator: any single-browser-session tool (Playwright) and any concurrency-1 data tools. Subagents cannot write files -- they return inline; the orchestrator writes.

## Cross-validation + citation

- Never let a single source settle a load-bearing claim if a second independent source is cheap. Confirm absence findings with a positive enumeration + a second source (a count from a catalog is not proof).
- Distinguish "confirmed", "refuted", and "couldn't verify (tool missing/unavailable)".
- Cite the exact source for every load-bearing claim: `file:line`, URL, wiki pageId, graph node, or the MCP + query used.

## Known pitfalls (general)

- **Search indexes can be down** — when a search API errors, navigate by known identifiers (FQNs, IDs, slugs) via `get_*` / `list_*` endpoints instead of `search_*`. Absence-by-search is not conclusive.
- **VCS/CI MCPs** = server-side entities only (PRs, CI, approvals); read code from the local clone, not the remote API.
- **Wiki/docs search**: search the local mirror first if one exists; title search can miss pages that exist — absence-by-title-search is not conclusive.
- **Cross-checking agents** (e.g. AI assistants with their own tool access) may lack certain tools (no DB, GitLab 401, etc.) — "not confirmed" from such a source means "couldn't verify", not "refuted".
