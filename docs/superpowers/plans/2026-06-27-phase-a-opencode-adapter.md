# Phase A — opencode Adapter (`@bim-ba/ai-opencode`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `ai` toolkit consumable by **opencode** via a single scoped npm package `@bim-ba/ai-opencode` — a self-wiring plugin that injects the shared behaviour-protocol (as opencode `instructions`) and the shared skills (as opencode `skills.paths`), plus a `session.idle` drift-log reminder — all from one canonical source, with the repo itself made a runnable opencode project for dogfooding.

**Architecture:** opencode reads skills/CLAUDE.md natively but ignores Claude hooks and the marketplace. The adapter is an npm package whose plugin `config(cfg)` hook appends the package's bundled `behaviour-protocol.md` to `cfg.instructions` and its bundled `skills/` dir to `cfg.skills.paths` (existence-guarded, so it no-ops when assets aren't present). The skills + protocol have ONE home (the Claude plugin tree); a Python/`uv` sync script copies them into the package at publish time (never committed). The plugin ships as TypeScript — opencode runs on Bun and loads `.ts` directly, so there is no transpile step.

**Tech Stack:** TypeScript (opencode plugin via `@opencode-ai/plugin` types), Bun (`bun test`, `bun add`), Python 3.9+ stdlib + `uv` (the asset-sync script and its test). opencode `1.15.10` (plugin API stable across `^1.0.0`).

## Global Constraints

- **Brand is `ai`.** The package is `@bim-ba/ai-opencode` (scoped, public), mirroring `github.com/bim-ba/ai`. Naming rule `@bim-ba/ai-<agent>`. Do not reintroduce the retired `spark` name.
- **Single canonical source — no duplication.** Skills live only at `plugins/core/skills/` + `plugins/data/skills/`; the behaviour protocol only at `plugins/core/hooks/behaviour-protocol.md`. The package receives **build-time copies** that are **git-ignored** — never commit them, never hand-edit them.
- **Non-destructive / merge-never-clobber** carries over: `config(cfg)` only *appends* to `cfg.instructions` / `cfg.skills.paths`, never replaces them, and is idempotent.
- **Toolchain split (amends the old uv-only rule):** repo tooling and the Python side stay `uv`/stdlib-only (PEP 723, `dependencies = []`). The opencode adapter under `packages/ai-opencode/` uses the npm/Bun toolchain. The asset-sync script stays Python/`uv`. **Bun is a prerequisite for Phase A work.**
- **Package version pins:** `engines.opencode` = `"^1.0.0"`; `publishConfig.access` = `"public"`; `type` = `"module"`.
- **Claude Code adapter is untouched** by this phase. Publishing/CI automation is Phase B — out of scope here.

---

### Task 1: Asset-sync script (`sync-assets.py`) + git-ignore

**Files:**
- Create: `packages/ai-opencode/scripts/sync-assets.py`
- Create: `tests/test_sync_assets.py`
- Modify: `.gitignore` (append the synced-artifact + node_modules ignores)

**Interfaces:**
- Consumes: the canonical sources `plugins/core/skills/`, `plugins/data/skills/`, `plugins/core/hooks/behaviour-protocol.md`.
- Produces: a CLI `sync-assets.py --repo-root PATH --package-root PATH` that writes `<package-root>/behaviour-protocol.md` and `<package-root>/skills/<skill-name>/…` (one subdir per skill, copied wholesale). Idempotent; writes only inside `<package-root>`. Later tasks rely on these output locations.

- [ ] **Step 1: Write the failing test**

Create `tests/test_sync_assets.py`:

```python
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Tests for the opencode-adapter asset-sync script (canonical → package, no duplication)."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SYNC = REPO / "packages" / "ai-opencode" / "scripts" / "sync-assets.py"
SKILL_SOURCE_DIRS = [REPO / "plugins" / "core" / "skills", REPO / "plugins" / "data" / "skills"]
PROTOCOL_SOURCE = REPO / "plugins" / "core" / "hooks" / "behaviour-protocol.md"


def run_sync(package_root):
    return subprocess.run(
        [sys.executable, str(SYNC),
         "--repo-root", str(REPO),
         "--package-root", str(package_root)],
        capture_output=True, text=True)


def source_skill_names():
    names = set()
    for d in SKILL_SOURCE_DIRS:
        for p in d.iterdir():
            if (p / "SKILL.md").is_file():
                names.add(p.name)
    return names


class SyncAssets(unittest.TestCase):
    def test_copies_protocol_and_every_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_sync(tmp)
            self.assertEqual(r.returncode, 0, r.stderr)
            pkg = Path(tmp)
            # behaviour-protocol.md copied verbatim
            self.assertTrue((pkg / "behaviour-protocol.md").is_file())
            self.assertEqual((pkg / "behaviour-protocol.md").read_text(),
                             PROTOCOL_SOURCE.read_text())
            # every source skill landed as <skills>/<name>/SKILL.md
            copied = {p.name for p in (pkg / "skills").iterdir()
                      if (p / "SKILL.md").is_file()}
            self.assertEqual(copied, source_skill_names())
            # known anchors from each plugin
            self.assertTrue((pkg / "skills" / "setup" / "SKILL.md").is_file())
            self.assertTrue((pkg / "skills" / "clickhouse-query-best-practices" / "SKILL.md").is_file())

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_sync(tmp)
            first = sorted(p.relative_to(tmp).as_posix() for p in Path(tmp).rglob("*"))
            run_sync(tmp)
            second = sorted(p.relative_to(tmp).as_posix() for p in Path(tmp).rglob("*"))
            self.assertEqual(first, second)

    def test_writes_only_inside_package_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            sentinel_before = sorted(p.name for p in REPO.iterdir())
            run_sync(tmp)
            sentinel_after = sorted(p.name for p in REPO.iterdir())
            self.assertEqual(sentinel_before, sentinel_after)  # repo root untouched


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --no-project tests/test_sync_assets.py -v`
Expected: FAIL — `sync-assets.py` does not exist yet, so the subprocess returns non-zero and `test_copies_protocol_and_every_skill` fails on `returncode == 0`.

- [ ] **Step 3: Write `sync-assets.py`**

Create `packages/ai-opencode/scripts/sync-assets.py`:

```python
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Copy the canonical `ai` assets (skills + behaviour-protocol) into the opencode
package so they ship in the npm tarball. Build artifact — output is git-ignored and
must never be hand-edited. Idempotent; writes only inside --package-root."""
import argparse
import shutil
import sys
from pathlib import Path

SKILL_SOURCE_RELS = ["plugins/core/skills", "plugins/data/skills"]
PROTOCOL_SOURCE_REL = "plugins/core/hooks/behaviour-protocol.md"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", required=True, type=Path)
    ap.add_argument("--package-root", required=True, type=Path)
    args = ap.parse_args()
    repo = args.repo_root.resolve()
    pkg = args.package_root.resolve()
    pkg.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(repo / PROTOCOL_SOURCE_REL, pkg / "behaviour-protocol.md")

    skills_dst = pkg / "skills"
    if skills_dst.exists():
        shutil.rmtree(skills_dst)
    skills_dst.mkdir(parents=True)
    for src_rel in SKILL_SOURCE_RELS:
        src = repo / src_rel
        for skill_dir in sorted(p for p in src.iterdir() if (p / "SKILL.md").is_file()):
            shutil.copytree(skill_dir, skills_dst / skill_dir.name)

    print("synced assets to {}".format(pkg))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --no-project tests/test_sync_assets.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 5: Add git-ignore entries**

Append to `.gitignore`:

```
# opencode adapter — build artifacts (synced from the canonical source; never committed)
packages/ai-opencode/skills/
packages/ai-opencode/behaviour-protocol.md
packages/ai-opencode/node_modules/
```

- [ ] **Step 6: Commit**

```bash
git add packages/ai-opencode/scripts/sync-assets.py tests/test_sync_assets.py .gitignore
git commit -m "feat(opencode): asset-sync script copies canonical skills+protocol into the package"
```

---

### Task 2: Package manifest + self-wiring `config()` plugin

**Files:**
- Create: `packages/ai-opencode/package.json`
- Create: `packages/ai-opencode/src/plugin.ts`
- Create: `packages/ai-opencode/src/plugin.test.ts`

**Interfaces:**
- Consumes: the asset layout from Task 1 (`<package-root>/behaviour-protocol.md`, `<package-root>/skills/`).
- Produces:
  - `applyConfig(cfg: any, paths: { protocol: string; skillsDir: string }): any` — pure, existence-guarded, idempotent merge of `instructions` + `skills.paths`. Task 3 leaves this untouched.
  - `AiOpencode: Plugin` (also the default export) — the plugin whose `config` hook calls `applyConfig` with the package's real bundled paths. Task 3 ADDS an `event` hook to the same returned object.

- [ ] **Step 1: Create the package manifest and install the type dependency**

Create `packages/ai-opencode/package.json`:

```json
{
  "name": "@bim-ba/ai-opencode",
  "version": "0.1.0",
  "description": "opencode adapter for the ai agent toolkit — injects the shared behaviour protocol + skills and a drift-log reminder.",
  "type": "module",
  "exports": { ".": "./src/plugin.ts" },
  "files": ["src/plugin.ts", "skills", "behaviour-protocol.md"],
  "engines": { "opencode": "^1.0.0" },
  "publishConfig": { "access": "public" },
  "scripts": {
    "test": "bun test",
    "prepack": "uv run --no-project scripts/sync-assets.py --repo-root ../.. --package-root ."
  }
}
```

Then, from `packages/ai-opencode/`, add the plugin types as a dev dependency (pins the current version into `package.json` + creates `bun.lockb`):

Run: `cd packages/ai-opencode && bun add -d @opencode-ai/plugin`
Expected: `package.json` gains a `devDependencies["@opencode-ai/plugin"]` entry; `bun.lockb` created.

- [ ] **Step 2: Write the failing test**

Create `packages/ai-opencode/src/plugin.test.ts`:

```typescript
import { test, expect, beforeAll, afterAll } from "bun:test"
import { mkdtempSync, writeFileSync, mkdirSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { applyConfig } from "./plugin"

let dir: string
let protocol: string
let skillsDir: string

beforeAll(() => {
  dir = mkdtempSync(join(tmpdir(), "ai-opencode-"))
  protocol = join(dir, "behaviour-protocol.md")
  skillsDir = join(dir, "skills")
  writeFileSync(protocol, "# protocol")
  mkdirSync(skillsDir)
})
afterAll(() => rmSync(dir, { recursive: true, force: true }))

test("applyConfig appends protocol to instructions and skills dir to skills.paths", () => {
  const cfg: any = {}
  applyConfig(cfg, { protocol, skillsDir })
  expect(cfg.instructions).toEqual([protocol])
  expect(cfg.skills.paths).toEqual([skillsDir])
})

test("applyConfig is non-destructive: existing entries are preserved", () => {
  const cfg: any = { instructions: ["existing.md"], skills: { paths: ["/other/skills"] }, customKey: 1 }
  applyConfig(cfg, { protocol, skillsDir })
  expect(cfg.instructions).toEqual(["existing.md", protocol])
  expect(cfg.skills.paths).toEqual(["/other/skills", skillsDir])
  expect(cfg.customKey).toBe(1)
})

test("applyConfig is idempotent: a second call adds no duplicates", () => {
  const cfg: any = {}
  applyConfig(cfg, { protocol, skillsDir })
  applyConfig(cfg, { protocol, skillsDir })
  expect(cfg.instructions).toEqual([protocol])
  expect(cfg.skills.paths).toEqual([skillsDir])
})

test("applyConfig no-ops for paths that do not exist", () => {
  const cfg: any = {}
  applyConfig(cfg, { protocol: join(dir, "missing.md"), skillsDir: join(dir, "missing") })
  expect(cfg.instructions).toBeUndefined()
  expect(cfg.skills).toBeUndefined()
})
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd packages/ai-opencode && bun test`
Expected: FAIL — `./plugin` has no export `applyConfig` (module-not-found / undefined import).

- [ ] **Step 4: Write `src/plugin.ts`**

Create `packages/ai-opencode/src/plugin.ts`:

```typescript
import type { Plugin } from "@opencode-ai/plugin"
import { existsSync } from "node:fs"
import { fileURLToPath } from "node:url"
import { join } from "node:path"

// Package root = parent of this src/ dir. After publish the bundled assets sit here.
const PKG_ROOT = fileURLToPath(new URL("../", import.meta.url))
const PROTOCOL = join(PKG_ROOT, "behaviour-protocol.md")
const SKILLS_DIR = join(PKG_ROOT, "skills")

/**
 * Append the behaviour-protocol path to `instructions` and the skills dir to
 * `skills.paths`, only if each exists on disk. Idempotent and non-destructive:
 * existing entries are preserved, duplicates are not added.
 */
export function applyConfig(cfg: any, paths: { protocol: string; skillsDir: string }): any {
  if (existsSync(paths.protocol)) {
    cfg.instructions ??= []
    if (!cfg.instructions.includes(paths.protocol)) cfg.instructions.push(paths.protocol)
  }
  if (existsSync(paths.skillsDir)) {
    cfg.skills ??= {}
    cfg.skills.paths ??= []
    if (!cfg.skills.paths.includes(paths.skillsDir)) cfg.skills.paths.push(paths.skillsDir)
  }
  return cfg
}

export const AiOpencode: Plugin = async () => {
  return {
    config(cfg: any) {
      applyConfig(cfg, { protocol: PROTOCOL, skillsDir: SKILLS_DIR })
    },
  }
}

export default AiOpencode
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd packages/ai-opencode && bun test`
Expected: 4 tests PASS, output pristine.

- [ ] **Step 6: Commit**

```bash
git add packages/ai-opencode/package.json packages/ai-opencode/bun.lockb \
  packages/ai-opencode/src/plugin.ts packages/ai-opencode/src/plugin.test.ts
git commit -m "feat(opencode): @bim-ba/ai-opencode self-wiring config() plugin"
```

---

### Task 3: `session.idle` drift-log reminder hook

**Files:**
- Modify: `packages/ai-opencode/src/plugin.ts` (add `DRIFT_LOG_REMINDER` export and an `event` hook to the returned object)
- Modify: `packages/ai-opencode/src/plugin.test.ts` (add event-hook tests)

**Interfaces:**
- Consumes: `AiOpencode` from Task 2 (adds a second hook to the same returned `Hooks` object; the `config` hook is unchanged).
- Produces: `DRIFT_LOG_REMINDER: string` (exported) and an `event({ event })` hook that emits the reminder via `console.log` exactly when `event.type === "session.idle"`.

> **Validation note (carry to Phase B smoke):** opencode's `session.idle` is the closest analogue to Claude's `Stop` hook, but it fires when the session goes idle (not strictly per turn), and a plugin `event` handler's `console.log` lands in opencode's logs — whether it resurfaces into the agent's context is exactly what the Phase B smoke test must confirm. If it does not surface usefully, the documented fallback is to fold the drift-log reminder into the always-on `instructions` (the behaviour-protocol) instead of an event hook. This task implements and unit-tests the hook's *logic*; the surfacing behaviour is validated live in Phase B.

- [ ] **Step 1: Write the failing test**

Append to `packages/ai-opencode/src/plugin.test.ts`:

```typescript
import { AiOpencode, DRIFT_LOG_REMINDER } from "./plugin"

test("DRIFT_LOG_REMINDER mentions the creating-drift-logs skill and the 'none' acknowledgement", () => {
  expect(DRIFT_LOG_REMINDER).toContain("creating-drift-logs")
  expect(DRIFT_LOG_REMINDER).toContain("drift-log delta: none")
})

test("event hook logs the reminder on session.idle and nothing otherwise", async () => {
  const hooks = await AiOpencode({} as any)
  const logged: string[] = []
  const orig = console.log
  console.log = (...a: any[]) => { logged.push(a.join(" ")) }
  try {
    await hooks.event!({ event: { type: "session.updated" } } as any)
    expect(logged).toEqual([])
    await hooks.event!({ event: { type: "session.idle" } } as any)
    expect(logged).toEqual([DRIFT_LOG_REMINDER])
  } finally {
    console.log = orig
  }
})
```

(The existing `import { applyConfig } from "./plugin"` line at the top of the file stays; this adds a second import line for `AiOpencode` and `DRIFT_LOG_REMINDER`.)

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd packages/ai-opencode && bun test`
Expected: FAIL — `DRIFT_LOG_REMINDER` is undefined and `hooks.event` is undefined (the plugin returns only `config` so far).

- [ ] **Step 3: Add the reminder constant and the `event` hook**

In `packages/ai-opencode/src/plugin.ts`, add the constant just below the `SKILLS_DIR` line:

```typescript
export const DRIFT_LOG_REMINDER =
  "Drift-log check: scan the last turn against the 8 triggers in the creating-drift-logs skill. " +
  "If any fired, create an entry per that skill under .claude/drift-log/open/ named <YYYY-MM-DD>-<slug>.md. " +
  'Otherwise acknowledge: "drift-log delta: none".'
```

Then change the `AiOpencode` returned object to include the `event` hook alongside the existing `config` hook:

```typescript
export const AiOpencode: Plugin = async () => {
  return {
    config(cfg: any) {
      applyConfig(cfg, { protocol: PROTOCOL, skillsDir: SKILLS_DIR })
    },
    event: async ({ event }: { event: { type: string } }) => {
      if (event.type === "session.idle") {
        console.log(DRIFT_LOG_REMINDER)
      }
    },
  }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd packages/ai-opencode && bun test`
Expected: all 6 tests PASS (4 from Task 2 + 2 new), output pristine.

- [ ] **Step 5: Commit**

```bash
git add packages/ai-opencode/src/plugin.ts packages/ai-opencode/src/plugin.test.ts
git commit -m "feat(opencode): session.idle drift-log reminder hook"
```

---

### Task 4: Repo-as-opencode-project (dogfood config)

**Files:**
- Create: `opencode.json` (repo root)
- Create: `.opencode/plugin/ai.ts`

**Interfaces:**
- Consumes: the canonical asset paths (`plugins/core/skills`, `plugins/data/skills`, `plugins/core/hooks/behaviour-protocol.md`) and the `AiOpencode` default export from Task 2/3.
- Produces: a root `opencode.json` that makes the repo a runnable opencode project, and a local plugin re-export that activates the drift-log `event` hook in-repo. (Phase B's smoke test runs opencode against this.)

Design note: the root `opencode.json` wires `instructions` + `skills.paths` to the **canonical** repo paths directly. The local plugin re-exports the package plugin; its `config()` is existence-guarded and the package's synced assets are NOT present in-repo (git-ignored, never synced for dogfood), so `config()` adds nothing and there is no double-wiring — only the `event` hook is active in-repo.

- [ ] **Step 1: Create the dogfood opencode config**

Create `opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": ["plugins/core/hooks/behaviour-protocol.md"],
  "skills": { "paths": ["plugins/core/skills", "plugins/data/skills"] }
}
```

- [ ] **Step 2: Create the local plugin re-export**

Create `.opencode/plugin/ai.ts`:

```typescript
// Dogfood: load the opencode adapter from the in-repo package so the repo itself
// runs as an opencode project (used by the Phase B smoke test). config() is
// existence-guarded and the package's synced assets are absent in-repo, so only
// the session.idle drift-log hook activates here; instructions + skills come from
// the canonical paths in ../../opencode.json.
export { default } from "../../packages/ai-opencode/src/plugin"
```

- [ ] **Step 3: Verify the config is valid JSON with the expected keys**

Run:
```bash
uv run --no-project python -c "import json; c=json.load(open('opencode.json')); assert c['instructions']==['plugins/core/hooks/behaviour-protocol.md']; assert c['skills']['paths']==['plugins/core/skills','plugins/data/skills']; print('opencode.json OK')"
```
Expected: `opencode.json OK`.

- [ ] **Step 4: Verify the re-export target exists**

Run:
```bash
test -f packages/ai-opencode/src/plugin.ts && grep -q 'export { default }' .opencode/plugin/ai.ts && echo "re-export wired"
```
Expected: `re-export wired`.

- [ ] **Step 5: Commit**

```bash
git add opencode.json .opencode/plugin/ai.ts
git commit -m "feat(opencode): make the repo a runnable opencode project (dogfood)"
```

---

### Task 5: Docs — dual-install + parity table + convention amendment

**Files:**
- Modify: `README.md` (Requirements, Install, and a new feature-parity table)
- Modify: `CLAUDE.md` (amend the uv-only convention to scope it)

**Interfaces:**
- Consumes: nothing.
- Produces: user-facing install instructions for both agents and the documented toolchain split. No code depends on this task.

- [ ] **Step 1: Add the opencode install path to README**

In `README.md`, the `## Requirements` section currently lists `uv` and `Claude Code`. Add an opencode line so it reads:

```markdown
## Requirements

- [`uv`](https://docs.astral.sh/uv/) — **required** for Claude Code. The `core` SessionStart hook and the `/setup` scripts run Python through `uv run`. Without `uv`, the behaviour-protocol injection is skipped (the session still works).
- **Claude Code** — install via the marketplace (below). Or **opencode** — install the npm plugin (below). Either works; the skills and behaviour protocol are shared.
```

Then change the `## Install` section to cover both agents:

```markdown
## Install

**Claude Code** — add the marketplace, then enable the plugins you need:

```
/plugin marketplace add bim-ba/ai
```

`core` for any project, `data` for data projects.

**opencode** — add the plugin to your `opencode.json`:

```json
{ "$schema": "https://opencode.ai/config.json", "plugin": ["@bim-ba/ai-opencode"] }
```

The plugin self-wires: it injects the shared behaviour protocol as `instructions` and the shared skills into `skills.paths`, and registers a `session.idle` drift-log reminder. Requires opencode (runs on Bun).
```

- [ ] **Step 2: Add a feature-parity table to README**

Immediately after the `## Install` section, add:

```markdown
## Agent parity

| Capability | Claude Code | opencode |
|------------|-------------|----------|
| Skills (`SKILL.md`) | ✅ native | ✅ via `skills.paths` (self-wired) |
| Behaviour protocol | ✅ SessionStart hook | ✅ injected into `instructions` (self-wired) |
| Drift-log reminder | ✅ Stop hook | ✅ `session.idle` event hook |
| Delivery | git marketplace (`bim-ba/ai`) | npm (`@bim-ba/ai-opencode`) |
```

- [ ] **Step 3: Amend the uv-only convention in CLAUDE.md**

In `CLAUDE.md`, under `## Conventions`, replace the bullet:

```markdown
- **`uv` is the single tooling prerequisite.** The SessionStart hook and `/setup` run Python through `uv run`. Do not introduce `jq`, `yq`, or `npx`.
```

with:

```markdown
- **`uv` is the tooling prerequisite for the Claude Code side and all repo Python.** The SessionStart hook and `/setup` run Python through `uv run`; do not introduce `jq`, `yq`, or `npx`. The opencode adapter under `packages/ai-opencode/` is the one exception: it uses the npm/Bun toolchain (the plugin is TypeScript loaded by opencode). Its asset-sync script stays Python/`uv`.
```

- [ ] **Step 4: Verify the docs render and reference real artifacts**

Run:
```bash
grep -q '@bim-ba/ai-opencode' README.md && grep -q 'plugin marketplace add bim-ba/ai' README.md && grep -q 'packages/ai-opencode/' CLAUDE.md && echo "docs OK"
```
Expected: `docs OK`.

- [ ] **Step 5: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs(opencode): dual-agent install, parity table, scoped uv-only convention"
```

---

## Self-Review

**1. Spec coverage (Phase A section of the design doc):**
- Self-wiring npm plugin (`config()` appends instructions + skills.paths): Task 2. ✅
- `session.idle` drift-log reminder + the known-semantic-difference caveat: Task 3 (+ validation note). ✅
- Skills must be on disk / bundled via build-time copy, single source: Task 1 (`sync-assets.py`, git-ignored output). ✅
- `@bim-ba/ai-opencode` scoped public, `engines.opencode`, `type: module`, `publishConfig.access`: Task 2 manifest. ✅
- `.opencode/plugin/ai.ts` re-export + root `opencode.json` dogfood: Task 4. ✅
- README dual-install + parity table; CLAUDE.md convention amendment (toolchain split): Task 5. ✅
- Out of scope correctly deferred: publishing/CI automation → Phase B (stated in Global Constraints). ✅
- Open questions resolved with the approved defaults: `engines.opencode` = `^1.0.0` (verified opencode 1.15.10); build tool = Bun (plugin shipped as TS, no transpile); `session.idle` validated live in Phase B with a documented fallback. ✅

**2. Placeholder scan:** No TBD/TODO. Every code step shows complete code; every command has expected output. The one deferred item (`session.idle` surfacing) is explicitly scoped to Phase B with a concrete fallback, not left vague. ✅

**3. Type consistency:** `applyConfig(cfg, { protocol, skillsDir })` — same signature in Task 2's definition, Task 2's tests, and Task 3 (unchanged). `AiOpencode: Plugin` default export — defined Task 2, extended Task 3 (adds `event`), re-exported Task 4. `DRIFT_LOG_REMINDER` — defined and exported Task 3, asserted in Task 3 tests. `sync-assets.py --repo-root/--package-root` — same flags in Task 1 script, Task 1 test, and Task 2's `prepack` script. Output paths `<package-root>/behaviour-protocol.md` + `<package-root>/skills/` — produced by Task 1, resolved by Task 2's `PROTOCOL`/`SKILLS_DIR`. ✅
