# Phase 0 — Rebrand `spark → ai` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify the project on a single brand `ai` — rename the Claude marketplace from `spark` to `ai` (enablement keys `core@ai` / `data@ai`) across the three functional files and all live prose, leaving existing `@spark` installs to migrate non-destructively.

**Architecture:** The functional surface is exactly three files — `marketplace.json` (the marketplace `name`), `bootstrap.py` (generates `<name>@spark` keys + `extraKnownMarketplaces.spark`), and `verify.py` (checks them). Everything else is prose/brand text. We add the repo's first tests (stdlib `unittest`, run via `uv`) to lock the new `@ai` wiring and prove `bootstrap.py` stays non-destructive (never removes a stale `@spark` key). These tests seed the Phase B CI harness.

**Tech Stack:** Python 3.9+ stdlib only (PEP 723 single-file scripts), `uv run` as the only runner. No new dependencies, no test framework beyond `unittest`.

## Global Constraints

- **Single tooling prerequisite: `uv`.** No `jq`, `yq`, or `npx`. Python invoked only via `uv run`.
- **Scripts & tests are stdlib-only**, carry a PEP 723 header (`# /// script` … `requires-python = ">=3.9"`, `dependencies = []`).
- **`bootstrap.py` stays non-destructive — merge, never clobber.** Phase 0 only *adds* `@ai` keys; it MUST NOT remove or rewrite stale `@spark` keys or any unrelated key in a consumer's `settings.json`.
- **Install command unchanged:** `/plugin marketplace add bim-ba/ai` resolves by repo, not by marketplace name — do not touch it.
- **Out of scope — do NOT edit:** historical design/plan docs under `docs/superpowers/` (they record the `spark`-era state), and the origin note in `PROMPT.md:18` (records the naming discussion). The literal token `spark` is safe to blanket-replace only within the files named in Task 3.
- **Token-replace safety:** in the target files `spark` never appears as a substring of another word, so replacing the literal token `spark` → `ai` is exact.

---

### Task 1: `bootstrap.py` emits `@ai` keys (+ first tests)

**Files:**
- Create: `tests/test_bootstrap.py`
- Modify: `plugins/core/skills/setup/scripts/bootstrap.py` (line 5 docstring; lines 33-34 marketplace key; line 39 plugin key; line 55 help text)

**Interfaces:**
- Consumes: the existing `bootstrap.py` CLI — `--project-root PATH --plugin-root PATH --with CSV`.
- Produces: `bootstrap.py` writes `extraKnownMarketplaces.ai = {"source": {"source": "github", "repo": "bim-ba/ai"}}` and `enabledPlugins["<name>@ai"] = True` for each requested plugin (plus `core`). `tests/test_bootstrap.py` — the e2e harness later tasks/phases reuse (`run_bootstrap`, `load_settings` helpers).

- [ ] **Step 1: Write the failing test**

Create `tests/test_bootstrap.py`:

```python
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""E2E tests for the /setup bootstrap script — marketplace wiring under the `ai` brand."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BOOTSTRAP = REPO / "plugins" / "core" / "skills" / "setup" / "scripts" / "bootstrap.py"
PLUGIN_ROOT = REPO / "plugins" / "core"


def run_bootstrap(project_root, with_plugins="core"):
    return subprocess.run(
        [sys.executable, str(BOOTSTRAP),
         "--project-root", str(project_root),
         "--plugin-root", str(PLUGIN_ROOT),
         "--with", with_plugins],
        capture_output=True, text=True)


def load_settings(project_root):
    return json.loads((Path(project_root) / ".claude" / "settings.json").read_text())


class BootstrapWiring(unittest.TestCase):
    def test_enables_plugins_under_ai_marketplace(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_bootstrap(tmp, "core,data")
            self.assertEqual(r.returncode, 0, r.stderr)
            s = load_settings(tmp)
            self.assertIn("ai", s["extraKnownMarketplaces"])
            self.assertEqual(
                s["extraKnownMarketplaces"]["ai"],
                {"source": {"source": "github", "repo": "bim-ba/ai"}})
            self.assertIs(s["enabledPlugins"].get("core@ai"), True)
            self.assertIs(s["enabledPlugins"].get("data@ai"), True)

    def test_merge_is_non_destructive(self):
        with tempfile.TemporaryDirectory() as tmp:
            claude = Path(tmp) / ".claude"
            claude.mkdir()
            (claude / "settings.json").write_text(json.dumps({
                "enabledPlugins": {"core@spark": True},
                "customKey": 123,
            }))
            run_bootstrap(tmp, "core")
            s = load_settings(tmp)
            self.assertIs(s["enabledPlugins"].get("core@spark"), True)  # stale key preserved
            self.assertIs(s["enabledPlugins"].get("core@ai"), True)     # new key added
            self.assertEqual(s["customKey"], 123)                       # unrelated key preserved

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_bootstrap(tmp, "core,data")
            first = load_settings(tmp)
            run_bootstrap(tmp, "core,data")
            second = load_settings(tmp)
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --no-project tests/test_bootstrap.py -v`
Expected: `test_enables_plugins_under_ai_marketplace` and `test_merge_is_non_destructive` FAIL (current code writes `core@ai` nowhere — `enabledPlugins["core@ai"]` is `None`). `test_idempotent` passes (idempotency is unaffected by the rename).

- [ ] **Step 3: Rename the marketplace key in `bootstrap.py`**

In `plugins/core/skills/setup/scripts/bootstrap.py`, line 5, change the docstring:

```python
"""Idempotent ai project scaffold. Creates missing artifacts, never overwrites."""
```

Lines 33-34, change the marketplace registration:

```python
    if "ai" not in mkts:
        mkts["ai"] = {"source": {"source": "github", "repo": "bim-ba/ai"}}
```

Line 39, change the enablement key suffix:

```python
        key = name + "@ai"
```

Line 55, change the `--with` help text:

```python
                    help="comma-separated ai plugin names to enable (core is always included)")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --no-project tests/test_bootstrap.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_bootstrap.py plugins/core/skills/setup/scripts/bootstrap.py
git commit -m "feat(setup): bootstrap writes @ai marketplace keys (rebrand spark→ai)"
```

---

### Task 2: `verify.py` checks `@ai` keys (+ roundtrip test)

**Files:**
- Create: `tests/test_verify.py`
- Modify: `plugins/core/skills/setup/scripts/verify.py` (line 5 docstring; lines 28-29 marketplace check; lines 30-31 plugin check)

**Interfaces:**
- Consumes: the `verify.py` CLI — `--project-root PATH`, prints `verify OK` / `verify FAILED`, exits 0 / 1. `bootstrap.py` from Task 1 (already emits `@ai`).
- Produces: `verify.py` passes when `extraKnownMarketplaces.ai` and `enabledPlugins["core@ai"]` are present; its failure message reads `settings.json: enabledPlugins.core@ai absent`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_verify.py`:

```python
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Tests for verify.py post-checks under the `ai` brand, plus a bootstrap→verify roundtrip."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VERIFY = REPO / "plugins" / "core" / "skills" / "setup" / "scripts" / "verify.py"
BOOTSTRAP = REPO / "plugins" / "core" / "skills" / "setup" / "scripts" / "bootstrap.py"
PLUGIN_ROOT = REPO / "plugins" / "core"


def run_verify(project_root):
    return subprocess.run(
        [sys.executable, str(VERIFY), "--project-root", str(project_root)],
        capture_output=True, text=True)


def seed(project_root, settings):
    root = Path(project_root)
    (root / ".claude" / "drift-log" / "open").mkdir(parents=True)
    (root / ".claude" / "drift-log" / "applied").mkdir(parents=True)
    (root / ".claude" / "settings.json").write_text(json.dumps(settings))


class VerifyChecks(unittest.TestCase):
    def test_ok_with_ai_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed(tmp, {
                "extraKnownMarketplaces": {
                    "ai": {"source": {"source": "github", "repo": "bim-ba/ai"}}},
                "enabledPlugins": {"core@ai": True},
            })
            r = run_verify(tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("verify OK", r.stdout)

    def test_fails_when_only_spark_key_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed(tmp, {
                "extraKnownMarketplaces": {"spark": {}},
                "enabledPlugins": {"core@spark": True},
            })
            r = run_verify(tmp)
            self.assertEqual(r.returncode, 1)
            self.assertIn("enabledPlugins.core@ai absent", r.stdout)

    def test_bootstrap_then_verify_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(
                [sys.executable, str(BOOTSTRAP),
                 "--project-root", tmp, "--plugin-root", str(PLUGIN_ROOT),
                 "--with", "core,data"], capture_output=True, text=True)
            r = run_verify(tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("verify OK", r.stdout)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --no-project tests/test_verify.py -v`
Expected: `test_ok_with_ai_keys` FAILS (verify still requires `core@spark`, so it returns 1 / "verify FAILED" on an `@ai`-only settings). `test_fails_when_only_spark_key_present` FAILS (current verify is satisfied by `core@spark`, returns 0). `test_bootstrap_then_verify_roundtrip` FAILS (Task 1's bootstrap now writes `core@ai`, which current verify rejects).

- [ ] **Step 3: Rename the checks in `verify.py`**

In `plugins/core/skills/setup/scripts/verify.py`, line 5, change the docstring:

```python
"""Post-checks for ai /setup. Exits non-zero on any failure."""
```

Lines 28-29, change the marketplace check:

```python
        if "ai" not in s.get("extraKnownMarketplaces", {}):
            errors.append("settings.json: extraKnownMarketplaces.ai absent")
```

Lines 30-31, change the plugin check:

```python
        if "core@ai" not in s.get("enabledPlugins", {}):
            errors.append("settings.json: enabledPlugins.core@ai absent")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --no-project tests/test_verify.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_verify.py plugins/core/skills/setup/scripts/verify.py
git commit -m "feat(setup): verify checks @ai marketplace keys (rebrand spark→ai)"
```

---

### Task 3: marketplace `name` + live prose rebrand

**Files:**
- Modify: `.claude-plugin/marketplace.json` (line 3)
- Modify: `CLAUDE.md` (lines 1, 3, 7, 14)
- Modify: `README.md` (lines 1, 34, 60)
- Modify: `plugins/core/templates/CLAUDE.md.tmpl` (line 3)
- Modify: `plugins/core/hooks/behaviour-protocol.md` (line 1)
- Modify: `plugins/core/skills/setup/SKILL.md` (lines 3, 10, 16, 21, 28, 52, 81, 98)

**Interfaces:**
- Consumes: nothing (prose + the marketplace manifest `name`).
- Produces: the marketplace resolves under `name: "ai"`; all live brand text reads `ai`. No code depends on this task.

- [ ] **Step 1: Rename the marketplace manifest**

In `.claude-plugin/marketplace.json`, line 3:

```json
  "name": "ai",
```

- [ ] **Step 2: Rebrand `CLAUDE.md`**

Apply these exact replacements:
- Line 1: `# spark` → `# ai`
- Line 3: ``injected each session by `spark/core` via`` → ``injected each session by `ai/core` via``
- Line 7: ``> `spark` is a Claude Code plugin marketplace`` → ``> `ai` is a Claude Code plugin marketplace``
- Line 14: ``marketplace manifest (name `spark`, plugins`` → ``marketplace manifest (name `ai`, plugins``

- [ ] **Step 3: Rebrand `README.md` and add a migration note**

Apply these exact replacements:
- Line 1: `# spark` → `# ai`
- Line 34: ``Bootstraps a project with spark conventions`` → ``Bootstraps a project with ai conventions``
- Line 60: ``and wires the `spark` marketplace into`` → ``and wires the `ai` marketplace into``

Then, immediately after the install code block (after line 19, before `Then enable the plugins…`), insert this migration note:

```markdown
> **Migrating from a `spark`-era install?** Re-run `/setup` — it adds the new
> `core@ai` / `data@ai` keys to `.claude/settings.json`. The old `@spark` keys are
> left untouched (the scaffold never clobbers); remove them by hand if you like.
```

- [ ] **Step 4: Rebrand the template and hook**

In `plugins/core/templates/CLAUDE.md.tmpl`, line 3:
- ``Baseline agent behavior is provided by spark/core (injected`` → ``Baseline agent behavior is provided by ai/core (injected``

In `plugins/core/hooks/behaviour-protocol.md`, line 1:
- `# Agent Behaviour Protocol (spark/core)` → `# Agent Behaviour Protocol (ai/core)`

- [ ] **Step 5: Rebrand the `setup` SKILL.md**

In `plugins/core/skills/setup/SKILL.md`, replace every literal `spark` token with `ai` (8 occurrences — lines 3, 10, 16, 21, 28, 52, 81, 98). Notable ones:
- Line 3 (description): ``shared spark conventions`` → ``shared ai conventions``; ``the requested spark plugins`` → ``the requested ai plugins``
- Line 81: ``written as `<name>@spark: true` into`` → ``written as `<name>@ai: true` into``
- Line 98: ``git commit -m "chore: bootstrap spark scaffold"`` → ``git commit -m "chore: bootstrap ai scaffold"``

- [ ] **Step 6: Verify no stray live `spark` remains**

Run:
```bash
grep -rIn --exclude-dir=.git --exclude-dir=docs -e 'spark' . | grep -v 'PROMPT.md'
```
Expected: **no output**. (Any hit means a live file still carries the old brand. `docs/` and `PROMPT.md:18` are intentionally excluded — historical.)

- [ ] **Step 7: Re-run both test files to confirm nothing regressed**

Run:
```bash
uv run --no-project tests/test_bootstrap.py -v && uv run --no-project tests/test_verify.py -v
```
Expected: all 6 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add .claude-plugin/marketplace.json CLAUDE.md README.md \
  plugins/core/templates/CLAUDE.md.tmpl plugins/core/hooks/behaviour-protocol.md \
  plugins/core/skills/setup/SKILL.md
git commit -m "docs: rebrand marketplace name and prose spark→ai"
```

---

## Self-Review

**1. Spec coverage (Phase 0 bullet of the design doc):**
- Marketplace `name` → `ai`: Task 3 Step 1. ✓
- Enablement keys `core@ai` / `data@ai`, `extraKnownMarketplaces.ai`: Task 1 (bootstrap) + Task 2 (verify). ✓
- "Functional surface is 3 files (`marketplace.json`, `bootstrap.py`, `verify.py`)": Tasks 1-3 touch exactly these for code; rest is prose. ✓
- "`bootstrap.py` stays non-destructive — adds `@ai`, never removes stale `@spark`": `test_merge_is_non_destructive` (Task 1) asserts both the stale `core@spark` and an unrelated key survive. ✓
- "Breaking change accepted; migration documented in README": stale-key behavior is locked by `test_merge_is_non_destructive`; the migration note is added to README in Task 3 Step 3. ✓
- "Install command `/plugin marketplace add bim-ba/ai` unchanged": no task touches README line 18 or the command. ✓

**2. Placeholder scan:** No TBD/TODO; every code step shows complete code; every command has expected output. ✓

**3. Type consistency:** Helper names `run_bootstrap`/`load_settings` (Task 1) and `run_verify`/`seed` (Task 2) are defined in their own files and used consistently. The marketplace value object `{"source": {"source": "github", "repo": "bim-ba/ai"}}` is identical in `bootstrap.py`, `test_bootstrap.py`, and `test_verify.py`. The failure-message substring `enabledPlugins.core@ai absent` matches between `verify.py` and `test_verify.py`. ✓
