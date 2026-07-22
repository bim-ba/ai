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

When the question splits into independent sub-questions or distinct sources (e.g. "how is X documented in the catalog?" vs "what does the spec say?" vs "what does the code actually do?"), dispatch **one subagent per source/place** (see `superpowers:dispatching-parallel-agents`) -- in a single message when the set is small, otherwise in the affordable waves the first guard below prescribes. Keep on the orchestrator: any single-browser-session tool (Playwright) and any concurrency-1 data tools.

Independence licenses parallelism; it does NOT set the batch size. Each guard below is a failure this discipline actually paid for, so treat them as load-bearing, not optional:

- **Dispatch in waves you can afford to lose, not one burst sized to the problem.** A provider rate-limit can terminate a dozen in-flight agents at once; a wave of ~3-5 with the rest queued survives it, one burst of 12 does not.
- **The orchestrator owns the concurrency budget.** Every dispatch prompt states whether that subagent may fan out further -- default NO. A subagent cannot see its siblings, so an unstated licence makes realised concurrency multiply per level (12 agents each re-applying "parallelize" = ~144, not 12).
- **Subagents write substantial output INCREMENTALLY to a scratch/artifacts path, never buffering to one final write.** In THIS harness subagents CAN write files -- use it. An agent can be killed at any moment (rate limit, user stop), so whatever it has established must already be on disk; this is durability, not merely a way to dodge the HTML-escaping of an inline return. Scope the writes via the agent's system prompt ("only under `artifacts/`"), not a tool ban.
- **A content-emitting agent is bounded by the 64k OUTPUT-token limit, because tool-call arguments are model output.** For bulk uploads, page/record creation, or many-file writes, size by total payload bytes, not item count (~40-50k output tokens of payload max, roughly 4 large docs), and shard the rest across siblings. Being terse does not help -- the payload is the cost, not the commentary.
- **A paginating or scraping agent gets a HARD cap (N pages / N items), never "until exhausted."** A rate-limited endpoint turns "until exhausted" into an unbounded backoff loop the agent will not exit on its own (it reads 429/lockout as "wait and retry," and may spin up a monitor to keep resuming). Set the cap from the value curve, tell it to STOP at the cap and record that it hit it; incremental writes keep the partial yield safe.
- **When 3+ agents in one fan-out need the same invariant** (domain profile, source-diversification rules, output schema, security guardrails), write it ONCE to a versioned repo file each prompt reads first, and keep only the agent-specific task in the prompt. Self-contained means *reachable*, not inlined -- twelve inlined copies cannot absorb a mid-run correction, so the corrected and uncorrected agents silently disagree on their base facts.
- **A constraint discovered after a fan-out has launched is retrofittable** -- SendMessage it to every live agent rather than letting the batch run un-constrained or killing and re-dispatching; messages land at the agent's next tool round.

For research whose findings are small, the simplest shape still holds: subagents return inline (HTML-escaped -- decode before the orchestrator writes), and the orchestrator reconciles and writes the one durable artifact.

## Cross-validation + citation

- Never let a single source settle a load-bearing claim if a second independent source is cheap. Confirm absence findings with a positive enumeration + a second source (a count from a catalog is not proof).
- Distinguish "confirmed", "refuted", and "couldn't verify (tool missing/unavailable)".
- Cite the exact source for every load-bearing claim: `file:line`, URL, wiki pageId, graph node, or the MCP + query used.
- **A RENDERED deliverable is validated by what a renderer produces, not what the build wrote.** For an HTML page / dashboard / diagram / notebook, a green build proves nothing about the DOM: serve it, load it in a browser, and assert on the rendered result -- element counts, the values actually displayed, and the effect of each interactive control. Encoding (a missing `<meta charset>`), load-time script errors and event handlers are invisible to every file-level check.
- **Check aggregate pipelines at their EXTREMES, not their averages.** Read the top and bottom of the sorted output and ask whether each row is real. A median is insensitive to exactly the mislabelled and mis-coerced rows a field-mapping bug produces, so a plausible summary statistic is no evidence the mapping is right.

## Known pitfalls (general)

- **Search indexes can be down** — when a search API errors, navigate by known identifiers (FQNs, IDs, slugs) via `get_*` / `list_*` endpoints instead of `search_*`. Absence-by-search is not conclusive.
- **VCS/CI MCPs** = server-side entities only (PRs, CI, approvals); read code from the local clone, not the remote API.
- **Wiki/docs search**: search the local mirror first if one exists; title search can miss pages that exist — absence-by-title-search is not conclusive.
- **Cross-checking agents** (e.g. AI assistants with their own tool access) may lack certain tools (no DB, GitLab 401, etc.) — "not confirmed" from such a source means "couldn't verify", not "refuted".
