# Cross-Agent opencode Adapter — Design (Phase A)

**Date:** 2026-06-27
**Branch:** TBD (`feat/opencode-adapter`)
**Status:** Draft — awaiting user review

## Goal

Make the `spark` marketplace consumable by **opencode** as a first-class target,
without forking content. Today spark targets Claude Code only: a git-resolved
marketplace (`.claude-plugin/marketplace.json`) plus a `core` plugin whose generic
behavior is injected by a `SessionStart` hook and whose drift-log nudge is a `Stop`
hook. This phase adds an opencode adapter — published to npm as `@bim-ba/ai` — that
delivers the same skills, the same always-on behaviour-protocol, and the same
drift-log reminder, **from a single shared source** in one monorepo.

This is **Phase A** of a larger cross-agent effort. **Phase B** (CI matrix +
release pipeline) is a separate spec and depends on this one landing.

## Scope decomposition (context, not part of this spec)

The full idea ("matrix CI + cross-agent support") decomposes into:

- **Phase A — this spec:** opencode adapter + monorepo scaffolding. Makes spark
  cross-agent.
- **Phase B — separate spec:** CI (full lint + e2e `/setup` matrix, deterministic),
  opencode-smoke job, and npm `publish`-on-tag for `@bim-ba/ai`. Depends on A.

## Decisions locked (from brainstorming)

- **Topology: monorepo + adapters.** One repo, one source of truth for the portable
  assets (skills, `behaviour-protocol.md`, templates). Per-agent differences live in
  thin adapter layers. Rejected: multi-repo (would force duplicating/syncing skills —
  the highest-value, byte-identical-across-agents asset — guaranteeing drift).
- **Claude Code install unchanged:** `/plugin marketplace add bim-ba/ai` keeps
  working. `.claude-plugin/marketplace.json` stays at repo root; the `plugins/`
  layout is untouched.
- **opencode delivery: npm, scoped `@bim-ba/ai`** (public). Consumer adds one line:
  `"plugin": ["@bim-ba/ai"]`. opencode does **not** accept git/github specs in the
  `plugin` array (npm name, `file://`, or local path only — verified via opencode
  docs), so npm is the path to a clean one-liner with full feature parity.
- **No source duplication.** Skills + `behaviour-protocol.md` have exactly one home
  in the repo (the Claude plugin tree, whose loader is the strictest). The npm
  package receives **build-time copies**, not a second source.

## What maps to opencode (research summary)

| spark mechanism | opencode equivalent | Work |
|---|---|---|
| Skills (`SKILL.md`) | Native: opencode reads `.claude/skills/`, `~/.claude/skills/`, plus its own `skills.paths`/`skills.urls` | 0 — open standard |
| `CLAUDE.md` / `AGENTS.md` | Read natively | 0 |
| `SessionStart` → inject `behaviour-protocol.md` | `instructions` field in merged config; a plugin can push the path via the `config(cfg)` hook | small |
| `Stop` → drift-log reminder | Plugin `event` hook on `session.idle` | small |
| `marketplace.json` / `plugin.json` | No marketplace in opencode; distribution = npm package referenced by name | new packaging channel |

## Architecture

### Self-wiring npm plugin (the elegant core)

The consumer writes exactly one line in their `opencode.json`:

```json
{ "$schema": "https://opencode.ai/config.json", "plugin": ["@bim-ba/ai"] }
```

On load, `@bim-ba/ai`'s plugin function returns a `Hooks` object whose `config(cfg)`
hook mutates the live merged config so the consumer never hand-wires paths:

- appends the package's bundled `behaviour-protocol.md` to `cfg.instructions`
  (always-on behavior — the `SessionStart` analogue);
- appends the package's bundled skills directory to `cfg.skills.paths`
  (so opencode discovers every `SKILL.md` spark ships).

Because the package is installed under `~/.cache/opencode/node_modules/@bim-ba/ai/`,
its bundled assets are on local disk — satisfying opencode's "skills must exist
locally" constraint. (Verified: `config` hook may mutate merged config and register
instructions/skills; `skills.paths` is scanned recursively for `**/SKILL.md`.)

### drift-log reminder

The same plugin registers an `event` hook firing on `session.idle`, emitting the
same reminder text the Claude `Stop` hook prints (scan the last turn against the 8
drift-log triggers; create an entry or acknowledge "none").

> **Known semantic difference to validate during implementation:** Claude's `Stop`
> fires per assistant turn; opencode's `session.idle` fires when the session goes
> idle (not strictly per turn). For a non-blocking nudge this is acceptable, but the
> implementation must confirm the event fires often enough to be useful and not so
> often as to spam. If `session.idle` proves wrong, fall back to the closest
> per-turn event available.

### Repository layout (target)

```
ai/                                    # repo root = github.com/bim-ba/ai
├── .claude-plugin/
│   └── marketplace.json               # Claude Code entry — UNCHANGED location
├── opencode.json                      # makes the repo itself a working opencode project (dogfood + Phase B smoke)
├── .opencode/
│   └── plugin/
│       └── spark.ts                   # one-line re-export of packages/opencode-spark (local dogfood)
│
├── plugins/                           # Claude Code adapter — layout fixed by loader, UNCHANGED
│   ├── core/
│   │   ├── .claude-plugin/plugin.json
│   │   ├── hooks/
│   │   │   ├── hooks.json
│   │   │   └── behaviour-protocol.md  # ◀ CANONICAL shared source
│   │   ├── skills/                    # ◀ CANONICAL shared source (all SKILL.md)
│   │   └── templates/
│   └── data/
│       ├── .claude-plugin/plugin.json
│       └── skills/
│
├── packages/
│   └── opencode-spark/                # opencode adapter — published as @bim-ba/ai
│       ├── package.json               # name "@bim-ba/ai", publishConfig.access public, engines.opencode
│       ├── src/plugin.ts              # config() injection + session.idle drift-log
│       ├── scripts/sync-assets.py     # PEP 723 stdlib, uv run — copies canonical assets in (prepare step)
│       └── (build output: behaviour-protocol.md + skills/ copied here, git-ignored)
│
├── docs/superpowers/{specs,plans}/
├── CLAUDE.md   AGENTS.md→CLAUDE.md   README.md   LICENSE
```

Note: the dogfood `opencode.json` at root can reference the canonical assets
directly (`skills.paths: ["plugins/core/skills","plugins/data/skills"]`,
`instructions: ["plugins/core/hooks/behaviour-protocol.md"]`) — it does not need the
npm package to be built. The npm package is for *external* consumers; the root config
is for running opencode *inside* this repo.

### Asset sync (no source duplication)

A `prepare`/`prepack` step copies the canonical assets into the package before
publish:

- `plugins/core/skills/` + `plugins/data/skills/` → `packages/opencode-spark/skills/`
- `plugins/core/hooks/behaviour-protocol.md` → `packages/opencode-spark/behaviour-protocol.md`

The copy target is git-ignored (build artifact, never committed) so the source has
exactly one home. **The sync script is Python stdlib via `uv run`** (PEP 723 header,
empty deps) — consistent with `bootstrap.py`/`verify.py` and the repo's uv-only
tooling convention, invoked from npm's `prepare` script.

## Convention impact (must acknowledge)

CLAUDE.md currently states **"`uv` is the single tooling prerequisite … Do not
introduce `jq`, `yq`, or `npx`."** The opencode adapter unavoidably introduces a
Node/bun toolchain for `packages/opencode-spark` (the plugin runtime is TypeScript;
npm publish needs npm/bun). This phase therefore **amends the convention** to scope
it: *uv-only applies to repo tooling and the Claude/Python side; the opencode adapter
under `packages/` uses the npm/bun toolchain.* The asset-sync script stays Python/uv
to keep "move files around" in one language. CLAUDE.md is updated to reflect this.

## Components & interfaces

- **`packages/opencode-spark/src/plugin.ts`** — exports the opencode plugin function.
  Returns `{ config(cfg), event({event}) }`. Depends on `@opencode-ai/plugin` types.
  Pure: no network, no writes except the reminder it emits.
- **`packages/opencode-spark/scripts/sync-assets.py`** — copies canonical assets into
  the package. stdlib only, idempotent, `uv run`-invoked. Input: repo root. Output:
  the git-ignored `skills/` + `behaviour-protocol.md` inside the package.
- **`packages/opencode-spark/package.json`** — name `@bim-ba/ai`, `type: module`,
  `publishConfig.access: public`, `engines.opencode` (minimum version — **verify
  latest stable at implementation time, do not guess**), `files` whitelist (dist +
  synced assets), `prepare` → runs sync-assets.
- **`.opencode/plugin/spark.ts`** — one-line re-export of the package, so the repo is
  a runnable opencode project for dogfooding and the Phase B smoke test.
- **`opencode.json` (root)** — dogfood config pointing at canonical asset paths.
- **`README.md`** — dual install instructions (git one-liner for Claude, npm
  one-liner for opencode) + a feature-parity table.

## Error handling

- `config(cfg)` must merge, never clobber: append to existing `instructions` /
  `skills.paths` arrays, create them only if absent. Mirrors `/setup`'s
  merge-not-replace guarantee for `settings.json`.
- Asset paths resolved relative to the package's own location (so it works from
  `~/.cache/opencode/node_modules/`), with a clear thrown error if assets are missing
  (i.e. published without the `prepare` step running).
- `session.idle` handler must be defensive: a failure in the reminder must not crash
  the session.

## Testing (Phase A scope)

- **`sync-assets.py`**: unit-style — run against the repo, assert every canonical
  `SKILL.md` and `behaviour-protocol.md` lands in the package; assert idempotency
  (re-run is a no-op / clean overwrite); assert it never writes outside the package.
- **Plugin `config()` logic**: with `@opencode-ai/plugin` test harness (bun test) —
  assert it appends instruction + skills paths, and that a pre-populated config keeps
  its existing entries (merge-not-clobber).
- **Smoke (deferred to Phase B):** a real `opencode run` against a free OpenRouter
  model, asserting the agent can list/load a spark skill. Validates the skill layer
  on a live agent; cannot validate the Claude hook/marketplace layer (opencode
  ignores those by design).

## Out of scope (this phase)

- CI workflow, release/publish automation, opencode-smoke job → **Phase B**.
- Porting Claude `commands`/`agents` formats (spark ships neither).
- Any change to the Claude Code adapter's behavior or install flow.

## Open questions (resolve during implementation, with defaults)

1. **`engines.opencode` minimum** — pin to current stable; verify at build time.
2. **Build tool** — bun (matches opencode's own toolchain) vs tsc-only. Default: bun.
3. **session.idle vs alternative event** — validate fires appropriately; fall back if
   not (see drift-log note above).
