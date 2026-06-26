# spark Polish Follow-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generalize `/setup`'s plugin flag to a scalable `--with` list and enrich the README with badges, a license, and reference tables (domains, skills, MCP servers, hooks).

**Architecture:** Two tasks. Task 1 replaces `bootstrap.py`'s boolean `--data` with `--with NAMES` (comma-separated; `core` always enabled) and updates the `/setup` SKILL.md orchestrator. Task 2 adds an MIT `LICENSE` and rewrites `README.md` with badges + four reference tables + the `--with` quickstart.

**Tech Stack:** Python 3.9+ stdlib (argparse), Markdown, shields.io badges.

## Design Decisions (approved)

- `/setup` ≡ `/setup --with core`. `--with` takes a comma-separated list of spark plugin names.
- **`core` is always enabled** — it carries the behaviour hook, `/setup`, and templates. `--with data` → enables `core` + `data`.
- **No hardcoded plugin-name validation** — scalability over typo-catching. Each requested name becomes `<name>@spark: true`; an unknown name yields a visible inert entry the user can remove.
- License: **MIT**, holder "Sava Znatnov", year 2026. Full badge set (license, Claude Code plugin, powered-by-uv, last-commit).

## Global Constraints

- Single tooling prerequisite is `uv`; no `jq`/`yq`/`npx` introduced.
- `bootstrap.py` stays stdlib-only with its PEP 723 header; remains idempotent (second run overwrites nothing; settings.json written only when a key actually changes; never overwrites `CLAUDE.md`; drift-log dirs only; settings merged non-clobber).
- Marketplace identity fixed: name `spark`, repo `bim-ba/ai`, plugin keys `<name>@spark`.
- README skill/plugin names must resolve on disk; no secrets in any committed file.

---

### Task 1: `/setup --with` scalable plugin flag

**Files:**
- Modify: `plugins/core/skills/setup/scripts/bootstrap.py` (arg parsing + `merge_settings`)
- Modify: `plugins/core/skills/setup/SKILL.md` (frontmatter description, Pre-checks flag note, Workflow Step 2, Artifact Map / wording)

**Interfaces:**
- Consumes: existing templates (unchanged).
- Produces: `bootstrap.py --project-root PATH --plugin-root PATH [--with NAMES]` where `NAMES` is a comma-separated plugin list defaulting to `core`; `core` is always enabled; each resolved name is written as `<name>@spark: true` (non-clobber). `verify.py` is unchanged (still asserts `core@spark`).

- [ ] **Step 1: Replace the `--data` argument with `--with`**

In `plugins/core/skills/setup/scripts/bootstrap.py`, inside `main()`, change the argument definition from:

```python
    ap.add_argument("--data", action="store_true")
```

to:

```python
    ap.add_argument("--with", dest="with_plugins", default="core",
                    help="comma-separated spark plugin names to enable (core is always included)")
```

- [ ] **Step 2: Resolve the plugin list and pass it to the merge**

In `main()`, replace the call `merge_settings(root, args.data, actions)` with logic that resolves the ordered, deduped plugin list (core first, always present) and passes it:

```python
    requested = [p.strip() for p in args.with_plugins.split(",") if p.strip()]
    plugin_names = []
    for name in ["core"] + requested:          # core always first
        if name not in plugin_names:
            plugin_names.append(name)
    merge_settings(root, plugin_names, actions)
```

- [ ] **Step 3: Update `merge_settings` to enable a list of plugins**

Replace the whole `merge_settings` function with the list-based version:

```python
def merge_settings(root, plugin_names, actions):
    path = root / ".claude" / "settings.json"
    settings = json.loads(path.read_text()) if path.exists() else {}
    changed = not path.exists()

    mkts = settings.setdefault("extraKnownMarketplaces", {})
    if "spark" not in mkts:
        mkts["spark"] = {"source": {"source": "github", "repo": "bim-ba/ai"}}
        changed = True

    plugins = settings.setdefault("enabledPlugins", {})
    for name in plugin_names:
        key = name + "@spark"
        if key not in plugins:
            plugins[key] = True
            changed = True

    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(settings, indent=2) + "\n")
    actions.append(("PATCHED" if changed else "SKIPPED", ".claude/settings.json"))
```

- [ ] **Step 4: Smoke-test `--with core,data` and bare default**

Run:
```bash
T=$(mktemp -d); git -C "$T" init -q
echo "--- bare (default core) ---"
uv run --no-project plugins/core/skills/setup/scripts/bootstrap.py --project-root "$T" --plugin-root "$(pwd)/plugins/core" >/dev/null
python3 -c "import json; p=json.load(open('$T/.claude/settings.json')); print('enabledPlugins:', list(p['enabledPlugins']))"
T2=$(mktemp -d); git -C "$T2" init -q
echo "--- --with data (core implied) ---"
uv run --no-project plugins/core/skills/setup/scripts/bootstrap.py --project-root "$T2" --plugin-root "$(pwd)/plugins/core" --with data >/dev/null
python3 -c "import json; p=json.load(open('$T2/.claude/settings.json')); print('enabledPlugins:', list(p['enabledPlugins']))"
echo "--- idempotency on T2 ---"
uv run --no-project plugins/core/skills/setup/scripts/bootstrap.py --project-root "$T2" --plugin-root "$(pwd)/plugins/core" --with data | grep -c CREATED
rm -rf "$T" "$T2"
```
Expected: first prints `enabledPlugins: ['core@spark']`; second prints `enabledPlugins: ['core@spark', 'data@spark']`; idempotency prints `0`.

- [ ] **Step 5: Update SKILL.md to the `--with` interface**

In `plugins/core/skills/setup/SKILL.md`:

(a) Frontmatter `description`: change the phrase "wires the `core`/`data` plugins into `.claude/settings.json`" to "wires the requested spark plugins (`core` always) into `.claude/settings.json`".

(b) Pre-checks — replace the `--data` flag bullet (the item describing `--data` / `SETUP_DATA`) with:

```markdown
   - `--with NAMES` → comma-separated spark plugin names to enable (e.g. `--with core,data`). `core` is always enabled even if omitted. Defaults to `core` when the flag is absent (so a bare `/setup` enables just `core`). Pass the value straight through to `bootstrap.py --with`.
```

(c) Workflow Step 2 — change the scaffold invocation and its comment to:

```bash
uv run --no-project "$CLAUDE_PLUGIN_ROOT/skills/setup/scripts/bootstrap.py" \
  --project-root "$PROJECT_ROOT" --plugin-root "$CLAUDE_PLUGIN_ROOT" \
  --with "core"   # replace "core" with the user's --with list, e.g. "core,data"; core is always enabled
```

(d) Any remaining "core/data plugin" phrasing in the Step 2 prose or Artifact Map that implies a fixed two-plugin set: reword to "the requested spark plugins (core always)". Leave Guardrails, verify step, and References intact.

- [ ] **Step 6: Confirm no stale `--data` / `SETUP_DATA` references remain**

Run:
```bash
grep -rn -- "--data\|SETUP_DATA" plugins/core/skills/setup/ && echo "STALE REFS FOUND" || echo "no stale --data refs"
```
Expected: `no stale --data refs`.

- [ ] **Step 7: Commit**

```bash
git add plugins/core/skills/setup/scripts/bootstrap.py plugins/core/skills/setup/SKILL.md
git commit -m "feat(core): /setup --with NAMES (scalable plugin list, core always on)"
```

---

### Task 2: LICENSE + enriched README

**Files:**
- Create: `LICENSE` (MIT)
- Modify: `README.md` (badges, domains/skills/MCP/hooks tables, `--with` quickstart)

**Interfaces:**
- Consumes: the skill inventory and descriptions below (verbatim — do not re-derive); the `--with` interface from Task 1.
- Produces: the public-facing README + license.

- [ ] **Step 1: Create the MIT LICENSE**

Create `LICENSE` at the repo root:

```
MIT License

Copyright (c) 2026 Sava Znatnov

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Overwrite README.md with badges + tables**

Replace the entire contents of `README.md` with:

```markdown
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
```

- [ ] **Step 3: Verify skill names resolve, license badge has a target, and no secrets**

Run:
```bash
for s in setup reviewing-agent-instructions documenting-meetings researching-rigorously using-playwright creating-drift-logs reviewing-drift-logs; do test -f "plugins/core/skills/$s/SKILL.md" || echo "MISSING core/$s"; done
test -f plugins/data/skills/clickhouse-query-best-practices/SKILL.md || echo "MISSING data/clickhouse"
test -f LICENSE && echo "LICENSE present" || echo "MISSING LICENSE"
grep -Eq 'ctx7sk-|github_pat_|BSAmU' README.md && echo "SECRET LEAK" || echo "no secrets OK"
echo "checks done"
```
Expected: no `MISSING` lines; `LICENSE present`; `no secrets OK`; `checks done`.

- [ ] **Step 4: Commit**

```bash
git add LICENSE README.md
git commit -m "docs: MIT LICENSE + README badges and reference tables"
```

---

## Self-Review Notes

- **Design coverage:** `--with` flag → Task 1; badges + license + 4 tables (domains, skills, MCP, hooks) → Task 2. All requested items covered.
- **`core` always enabled** is enforced in `bootstrap.py` Step 2 (core prepended before dedupe) and documented in SKILL.md + README quickstart.
- **No hardcoded validation:** `merge_settings` writes `<name>@spark` for every resolved name without checking against a fixed list — scalable as designed.
- **Idempotency** preserved: `merge_settings` still gates the write on `changed`; Task 1 Step 4 asserts the second run reports `0` CREATED.
- **Consistency:** `verify.py` is intentionally untouched — it asserts `core@spark`, which is always present under the new semantics.
```
