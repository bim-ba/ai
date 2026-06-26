# spark Refactor — Design Spec

**Date:** 2026-06-26
**Status:** Approved (design); pending implementation plan
**Scope:** Refactor the already-built `claude-toolkit` (Phases 0–4, branch `feat/claude-toolkit-bootstrap`, remote `github.com/bim-ba/ai`) before any project retrofit (Phase 5). This is a rename + restructure of a working system, not a greenfield build.

## Goal

Make the agent-assets repo simpler, lower-friction, and publishable: rename the marketplace to `spark`, adopt a consistent skill-naming convention, convert the drift-log subsystem from copied templates (+ a go-task dependency) into self-contained skills, and strengthen the always-on behaviour protocol with two rules (validate-against-current-sources, prefer-existing-solutions).

## Guiding principles (from the user)

- **Low barrier to entry / minimal dependencies.** Assume this becomes a public project. Require only the most standard, ubiquitous tools (git, jq, python3 — already assumed). No `go-task`/Taskfile dependency.
- **Best UX over specialization.** The system must not demand special competence or a toolchain to adopt.
- **Knowledge travels in the plugin, not in per-project file copies** wherever possible.
- **Self-contained skills** (a thin `SKILL.md` router + `rules/`/`templates/`/`references/`/`examples/`/`scripts/` loaded on demand) are the target shape.

## Decisions (locked)

| # | Decision |
|---|---|
| N1 | Marketplace internal name `claude-toolkit` → **`spark`**. Repo stays `bim-ba/ai`. `enabledPlugins` keys become `core@spark` / `data@spark`; `extraKnownMarketplaces` key `spark`, source `github: bim-ba/ai`. (User accepted the Apache-Spark name-collision risk.) |
| N2 | Skill naming convention: **workflow skills** = `<gerund-verb>-<object>`; **rulebook skills** = `<domain>-<aspect>`. Verb families: `using-` (tools/services), `documenting-` (docs), `reviewing-` (review/audit), `researching-` (research/fact-check), `creating-`/`writing-` (authored artifacts). |
| N3 | Renames: `auditing-agent-instructions`→`reviewing-agent-instructions`; `operational-meeting-documentation`→`documenting-meetings`; `systematic-research`→`researching-rigorously`. Unchanged: `using-playwright`, `clickhouse-query-best-practices` (rulebook), `setup` (command-invoked; imperative name kept by exception). |
| N4 | Drift-log subsystem → two new `core` skills `creating-drift-logs` + `reviewing-drift-logs`. Remove `templates/drift-log-automated/` and the `--automated` flag entirely (drops the go-task dependency). |
| N5 | Two new rules added to `behaviour-protocol.md`: validate-against-current-external-sources, and prefer-existing-solutions (anti-NIH). |
| N6 | Codify N2 + the self-contained-skill folder structure in `skills-authoring-standard.md`. |
| N7 | All work continues on `feat/claude-toolkit-bootstrap`; not merged yet (user choice). |

## Workstreams

### A. Marketplace rename → `spark`
- `.claude-plugin/marketplace.json`: `name` `claude-toolkit` → `spark` (plugin entries `core`/`data` and `./plugins/*` paths unchanged).
- `plugins/core/skills/setup/SKILL.md` Step 6 + Artifact Map + examples: `extraKnownMarketplaces.spark` (source `bim-ba/ai`), `enabledPlugins` `core@spark` (+ `data@spark` with `--data`).
- `README.md` + `docs/onboarding.md` (when written): onboarding strings → `core@spark`/`data@spark`; `/plugin marketplace add bim-ba/ai` (repo unchanged).
- No file outside these references the old marketplace name; a repo-wide grep for `claude-toolkit` must return only historical mentions in `docs/superpowers/` (plan/spec/ledger), which are allowed to keep the old name as record.

### B. Skill renames + convention
For each rename: `git mv` the skill directory; update the `name:` frontmatter field in its `SKILL.md`; update every cross-reference (other skills, the Stop hook, `/setup`, the authoring standard, README).
- `plugins/core/skills/auditing-agent-instructions/` → `reviewing-agent-instructions/` (frontmatter `name: reviewing-agent-instructions`; its `references/` files come along unchanged).
- `plugins/core/skills/operational-meeting-documentation/` → `documenting-meetings/`.
- `plugins/core/skills/systematic-research/` → `researching-rigorously/`.
- `skills-authoring-standard.md`: add a **Naming convention** section documenting N2 with examples, and a **Skill structure** section documenting the self-contained layout (thin `SKILL.md` router + on-demand `rules/`/`templates/`/`references/`/`examples/`/`scripts/`). The toolkit's own skills must conform (the renamed `reviewing-agent-instructions` may keep its existing section headers — tracked as a pre-existing follow-up Minor, not in scope here unless trivial).

### C. Drift-log → skills; remove go-task
- **Delete** `plugins/core/templates/drift-log-automated/` (incl. `Taskfile.audit.yml`) and `plugins/core/templates/drift-log/`.
- **New skill `plugins/core/skills/creating-drift-logs/`** (category: workflow):
  - `SKILL.md` — when to create a drift-log entry (the 8 triggers), the do-NOT-log list, and how to write one (where it lives: `.claude/drift-log/open/<YYYY-MM-DD>-<slug>.md`; immutability of the narrative body + temporal frontmatter).
  - `templates/_template.md` — the entry template (frontmatter schema + the 4 body sections).
  - `rules/` — atomic rules: the 8 triggers, the immutability rule, the frontmatter-field schema (immutable vs relocation-only).
  - Source content: the current `templates/drift-log/README.md` (triggers, schema) + `_template.md`.
- **New skill `plugins/core/skills/reviewing-drift-logs/`** (category: workflow):
  - `SKILL.md` — the lifecycle: OPEN→APPLIED transition (`git mv` + status/disposition flip), staleness triage (HIGH 7d / MEDIUM 21d / LOW 60d → Resolve/Refile/Drop, never delete), `applied/` compaction into `INDEX-YYYY-MM.md` past ~50 entries, and promotion of an applied insight into a codified rule/CLAUDE.md.
  - Source content: the lifecycle/staleness/compaction sections of the current `templates/drift-log/README.md`.
- **`/setup` change:** remove the `--automated` flag and the drift-log template-copy steps. `/setup` now only `mkdir -p .claude/drift-log/{open,applied}` and prints: "Drift-log conventions live in the `creating-drift-logs` / `reviewing-drift-logs` skills (from the `core` plugin) — no per-project README needed." Update Pre-checks flag list, Step 2, Artifact Map, Post-checks, and the summary accordingly.
- **Stop hook (`hooks/hooks.json`):** reword the reminder to reference the `creating-drift-logs` skill and its 8 triggers, NOT `.claude/drift-log/README.md` (which no longer exists). Keep it a plain `echo`.

### D. Behaviour-protocol rules
Add two concise bullets to `plugins/core/hooks/behaviour-protocol.md` (keep the file lean, still < ~40 lines), generic and tool-illustrative (names as "e.g."):
1. **Validate against current sources.** Before a non-trivial claim or committing to an approach, verify against current external tools (e.g. context7 MCP for library/API docs, a web-search/brave tool, parallel-cli). Training data goes stale — confirm versions/APIs/best-practices rather than relying on memory, and don't overengineer what a current tool or library already solves simply.
2. **Prefer existing solutions over reinventing.** Before building something custom, search for a mature, maintained solution (a standard-library feature, a well-adopted open-source package, an existing internal utility). Reach for custom code only when nothing fits, and say why.

These extend the existing "validate-don't-trust-training-data" line rather than duplicating it; fold/merge so there's no redundant bullet.

### E. Consistency cascade + verification
- Repo-wide grep after edits: no live reference to old skill names (`auditing-agent-instructions`, `operational-meeting-documentation`, `systematic-research`), old marketplace name (`claude-toolkit`) outside `docs/superpowers/`, `--automated`, `go-task`, `Taskfile`, or `drift-log/README.md` remains in `plugins/`.
- Re-run the controller smoke test (scratch `/setup`): scaffold now creates only `.claude/drift-log/{open,applied}` + claudelint + skills README + CLAUDE.md + settings wiring with `core@spark`; idempotency + non-clobber still hold; SessionStart hook injection still valid.
- Final whole-branch review (cross-cutting): marketplace↔plugin name consistency under `spark`, all skill cross-references resolve, the two new drift-log skills conform to the authoring standard + naming convention, behaviour-protocol still passes its no-project-nouns check and stays lean.

## Out of scope (unchanged from prior decisions)
- Phase 5 retrofit of the 5 existing projects + Context7-key rotation (separate, user-gated).
- Phase 6 personal `~/.claude` voice + onboarding docs (after the refactor).
- Renaming the git repo `bim-ba/ai`.
- The follow-up Minors deferred from the final review (M2 section headers, M3/M4 illustrative examples) unless trivially fixed in passing.

## Risks / notes
- **`spark` name collision** (Apache Spark, GitHub Spark, etc.) — accepted by the user; affects discoverability/SEO if public, not function.
- **Renames break references** if any cross-reference is missed → the grep gate in E is the safety net; the smoke test + final review are the backstops.
- **Drift-log knowledge moving into skills** means a project that hasn't enabled `core` loses the drift-log documentation. Acceptable: the whole model assumes `core` is enabled; `/setup` wires it.
