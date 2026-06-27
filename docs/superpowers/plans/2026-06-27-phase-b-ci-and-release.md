# Phase B — CI Matrix + opencode Smoke + Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up CI for the `ai` repo — a deterministic full-matrix lint+test job (the Python `/setup` suite across OS×Python, the Bun plugin tests, and an `npm pack` tarball-contents check), a non-blocking opencode smoke job (live agent on a free OpenRouter model), and a publish-on-tag release of `@bim-ba/ai-opencode` — plus the one cross-platform fix the matrix requires.

**Architecture:** Real check logic lives in tested scripts/commands (so it's verifiable locally); the workflow YAML is a thin orchestrator that invokes them on the matrix. The deterministic job is the merge gate; the opencode smoke job is advisory (scheduled + manual, secret-gated, `continue-on-error`) because free-tier models are non-deterministic and secrets aren't exposed to fork PRs. Release publishes the npm package on a `v*` tag.

**Tech Stack:** GitHub Actions (`actions/checkout@v4`, `astral-sh/setup-uv@v8`, `oven-sh/setup-bun@v2`, `actions/setup-node@v4`), Python 3.9–3.13 via `uv`, Bun, opencode CLI (`curl … | bash`), OpenRouter (free model).

## Global Constraints

- **Toolchain split (from Phase A):** Python side runs only through `uv` (no `jq`/`yq`/`npx`); committed PEP 723 scripts stay stdlib-only (`dependencies = []`). The opencode adapter uses npm/Bun. Transient YAML validation may use `uv run --with pyyaml` (a uv-managed ephemeral dep — not `jq`/`yq`/`npx`, and not a committed dependency).
- **Full deterministic matrix:** `os: [ubuntu-latest, macos-latest, windows-latest]` × `python: ['3.9','3.10','3.11','3.12','3.13']` for the `/setup` Python suite. Bun tests and the pack-check run once (ubuntu).
- **opencode smoke is advisory, NOT a merge gate:** triggers are `workflow_dispatch` + nightly `schedule`; the live step is `continue-on-error: true` and skips cleanly when `OPENROUTER_API_KEY` is absent (so fork PRs and unconfigured forks never fail). Rationale: free-tier models drift and rate-limit; this validates the *skill layer* on a real agent, not the merge.
- **Release on `v*` tag:** publishes `@bim-ba/ai-opencode` with `npm publish --access public`, gated on `NPM_TOKEN`. The package version must equal the tag.
- **Secrets required (documented for the maintainer):** `OPENROUTER_API_KEY` (smoke), `NPM_TOKEN` (release). Workflows degrade gracefully when absent.
- **Brand is `ai`; package `@bim-ba/ai-opencode`.** Don't reintroduce `spark`.

---

### Task 1: Cross-platform `AGENTS.md` in `bootstrap.py`

The matrix includes Windows specifically to exercise `bootstrap.py`'s `AGENTS.md` creation, which currently calls `agents.symlink_to("CLAUDE.md")` — that raises `OSError` on Windows without Developer Mode/privilege. Make it fall back to a regular-file copy so the Windows matrix leg is green. `verify.py` already passes for a non-symlink `AGENTS.md` (it only errors on a symlink pointing *wrong*), so the fallback is compatible.

**Files:**
- Modify: `plugins/core/skills/setup/scripts/bootstrap.py` (the AGENTS.md creation block, currently around lines 89-96)
- Modify: `tests/test_bootstrap.py` (add a fallback test)

**Interfaces:**
- Consumes: existing `bootstrap.py` `--project-root/--plugin-root/--with` CLI.
- Produces: `bootstrap.py` creates `AGENTS.md` as a symlink when the OS allows, else as a regular file whose content equals `CLAUDE.md`. Behaviour on symlink-capable systems is unchanged.

- [ ] **Step 1: Write the failing test**

Append this method to the test class in `tests/test_bootstrap.py`:

```python
    def test_agents_falls_back_to_copy_when_symlink_unavailable(self):
        import os
        import unittest.mock as mock
        with tempfile.TemporaryDirectory() as tmp:
            # Simulate a platform where symlink creation is not permitted (e.g. Windows).
            with mock.patch.object(os, "symlink", side_effect=OSError("symlink not permitted")):
                r = run_bootstrap(tmp, "core")
            self.assertEqual(r.returncode, 0, r.stderr)
            agents = Path(tmp) / "AGENTS.md"
            claude = Path(tmp) / "CLAUDE.md"
            self.assertTrue(agents.is_file())          # exists as a real file
            self.assertFalse(agents.is_symlink())      # not a (broken) symlink
            self.assertEqual(agents.read_text(), claude.read_text())  # mirrors CLAUDE.md
```

(`Path.symlink_to` calls `os.symlink` under the hood, so patching `os.symlink` exercises the fallback.)

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --no-project tests/test_bootstrap.py -v`
Expected: `test_agents_falls_back_to_copy_when_symlink_unavailable` FAILS — current code lets the `OSError` propagate (bootstrap exits non-zero) or leaves no `AGENTS.md`, so `returncode == 0` / `agents.is_file()` fails.

- [ ] **Step 3: Add the fallback in `bootstrap.py`**

In `plugins/core/skills/setup/scripts/bootstrap.py`, the current block is:

```python
        agents = root / "AGENTS.md"
        if agents.is_symlink():
            actions.append(("SKIPPED", "AGENTS.md (symlink exists)"))
        elif agents.exists():
            actions.append(("WARN", "AGENTS.md is a real file — left as-is"))
        else:
            agents.symlink_to("CLAUDE.md")
            actions.append(("CREATED", "AGENTS.md -> CLAUDE.md"))
```

Replace the `else` branch so symlink failure falls back to a copy:

```python
        agents = root / "AGENTS.md"
        if agents.is_symlink():
            actions.append(("SKIPPED", "AGENTS.md (symlink exists)"))
        elif agents.exists():
            actions.append(("WARN", "AGENTS.md is a real file — left as-is"))
        else:
            try:
                agents.symlink_to("CLAUDE.md")
                actions.append(("CREATED", "AGENTS.md -> CLAUDE.md"))
            except OSError:
                # Windows without privilege/Developer Mode can't create symlinks —
                # fall back to a regular file mirroring CLAUDE.md (verify.py accepts a non-symlink AGENTS.md).
                shutil.copyfile(claude_md, agents)
                actions.append(("CREATED", "AGENTS.md (copy of CLAUDE.md — symlink unavailable)"))
```

(`shutil` and `claude_md` are already imported / in scope in this function.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --no-project tests/test_bootstrap.py -v`
Expected: all tests PASS (the prior 3 + the new fallback test).

- [ ] **Step 5: Commit**

```bash
git add plugins/core/skills/setup/scripts/bootstrap.py tests/test_bootstrap.py
git commit -m "fix(setup): AGENTS.md falls back to a copy when symlinks are unavailable (Windows)"
```

---

### Task 2: Manifest-validity test (lint backbone) + fixture cleanup

A deterministic test that every shipped JSON config parses and holds its key invariants — this is the "lint" the CI runs. Also tightens a Phase 0 deferred-minor: `tests/test_verify.py`'s degenerate `{"spark": {}}` fixture.

**Files:**
- Create: `tests/test_manifests.py`
- Modify: `tests/test_verify.py` (one fixture line)
- Modify: `.gitignore` (ignore Python caches generated by test runs)

**Interfaces:**
- Consumes: the repo's committed JSON files.
- Produces: `tests/test_manifests.py` — asserts JSON validity + invariants for all manifests. No later task depends on it (CI runs it).

- [ ] **Step 1: Write the test**

Create `tests/test_manifests.py`:

```python
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Validity + invariant checks for every shipped JSON config (the CI lint backbone)."""
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

JSON_FILES = [
    ".claude-plugin/marketplace.json",
    "plugins/core/.claude-plugin/plugin.json",
    "plugins/data/.claude-plugin/plugin.json",
    "plugins/core/hooks/hooks.json",
    "plugins/core/templates/claudelintrc.json",
    "opencode.json",
    "packages/ai-opencode/package.json",
]


def load(rel):
    return json.loads((REPO / rel).read_text())


class Manifests(unittest.TestCase):
    def test_all_json_files_parse(self):
        for rel in JSON_FILES:
            with self.subTest(file=rel):
                self.assertTrue((REPO / rel).is_file(), rel + " missing")
                load(rel)  # raises on invalid JSON

    def test_marketplace_identity(self):
        m = load(".claude-plugin/marketplace.json")
        self.assertEqual(m["name"], "ai")
        names = {p["name"] for p in m["plugins"]}
        self.assertEqual(names, {"core", "data"})
        for p in m["plugins"]:
            self.assertTrue((REPO / p["source"]).is_dir(), p["source"] + " missing")

    def test_opencode_package_manifest(self):
        pkg = load("packages/ai-opencode/package.json")
        self.assertEqual(pkg["name"], "@bim-ba/ai-opencode")
        self.assertEqual(pkg["type"], "module")
        self.assertIn("opencode", pkg["engines"])
        self.assertEqual(pkg["publishConfig"]["access"], "public")

    def test_opencode_dogfood_config_points_at_real_paths(self):
        c = load("opencode.json")
        for instr in c["instructions"]:
            self.assertTrue((REPO / instr).is_file(), instr + " missing")
        for sp in c["skills"]["paths"]:
            self.assertTrue((REPO / sp).is_dir(), sp + " missing")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `uv run --no-project tests/test_manifests.py -v`
Expected: 4 tests PASS (these assert the current, already-correct repo state).

- [ ] **Step 3: Tighten the degenerate fixture in `tests/test_verify.py`**

In `tests/test_verify.py`, method `test_fails_when_only_spark_key_present`, change the marketplace fixture from the degenerate empty object to a realistic `spark`-era shape:

```python
                "extraKnownMarketplaces": {
                    "spark": {"source": {"source": "github", "repo": "bim-ba/ai"}}},
```

- [ ] **Step 4: Re-run the verify suite to confirm no regression**

Run: `uv run --no-project tests/test_verify.py -v`
Expected: 3 tests PASS (the negative test still fails verify because `core@ai` is absent — the realistic fixture doesn't change the outcome, only its fidelity).

- [ ] **Step 5: Ignore Python caches**

Append to `.gitignore` (running the suite generates `tests/__pycache__/`):

```
# Python bytecode caches (from running the test suite)
__pycache__/
*.pyc
```

- [ ] **Step 6: Commit**

```bash
git add tests/test_manifests.py tests/test_verify.py .gitignore
git commit -m "test: manifest-validity lint backbone; realistic spark fixture; ignore pycache"
```

---

### Task 3: `npm pack` tarball-contents check

Closes the final-review gap: nothing verifies the *published tarball* actually contains the synced `skills/` + `behaviour-protocol.md`. This script syncs assets, runs `npm pack --dry-run --json`, and asserts the file list.

**Files:**
- Create: `packages/ai-opencode/scripts/check-pack.py`
- Create: `tests/test_check_pack.py`

**Interfaces:**
- Consumes: `sync-assets.py` (Phase A), `npm`, the package at `packages/ai-opencode/`.
- Produces: `check-pack.py --repo-root PATH` — exits 0 and prints `pack OK` when the would-be tarball includes `behaviour-protocol.md` and at least one `skills/<name>/SKILL.md`; non-zero otherwise.

- [ ] **Step 1: Write the failing test**

Create `tests/test_check_pack.py`:

```python
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Tests for the npm-pack tarball-contents check (skips cleanly where npm is absent)."""
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHECK = REPO / "packages" / "ai-opencode" / "scripts" / "check-pack.py"


@unittest.skipIf(shutil.which("npm") is None, "npm not available")
class CheckPack(unittest.TestCase):
    def test_pack_includes_synced_assets(self):
        r = subprocess.run(
            [sys.executable, str(CHECK), "--repo-root", str(REPO)],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("pack OK", r.stdout)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails (or skips)**

Run: `uv run --no-project tests/test_check_pack.py -v`
Expected: if `npm` is present, FAIL — `check-pack.py` doesn't exist yet (subprocess non-zero). If `npm` is absent, the test SKIPS (acceptable; CI has npm and will exercise it).

- [ ] **Step 3: Write `check-pack.py`**

Create `packages/ai-opencode/scripts/check-pack.py`:

```python
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Sync assets, then assert the would-be npm tarball for @bim-ba/ai-opencode contains
the bundled behaviour-protocol.md and at least one skills/<name>/SKILL.md. stdlib only."""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", required=True, type=Path)
    args = ap.parse_args()
    repo = args.repo_root.resolve()
    pkg = repo / "packages" / "ai-opencode"

    sync = pkg / "scripts" / "sync-assets.py"
    rc = subprocess.run([sys.executable, str(sync),
                         "--repo-root", str(repo), "--package-root", str(pkg)])
    if rc.returncode != 0:
        sys.stderr.write("check-pack: sync-assets failed\n")
        return 1

    out = subprocess.run(["npm", "pack", "--dry-run", "--json"],
                         cwd=str(pkg), capture_output=True, text=True)
    if out.returncode != 0:
        sys.stderr.write("check-pack: npm pack failed\n" + out.stderr)
        return 1

    entries = json.loads(out.stdout)[0]["files"]
    paths = {f["path"] for f in entries}
    has_protocol = "behaviour-protocol.md" in paths
    has_skill = any(p.startswith("skills/") and p.endswith("/SKILL.md") for p in paths)
    if not has_protocol or not has_skill:
        sys.stderr.write(
            "check-pack: tarball missing assets (protocol={}, skill={})\n".format(has_protocol, has_skill))
        return 1

    print("pack OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --no-project tests/test_check_pack.py -v`
Expected: where `npm` is present, 1 test PASS (`pack OK`); otherwise SKIP.

- [ ] **Step 5: Commit**

```bash
git add packages/ai-opencode/scripts/check-pack.py tests/test_check_pack.py
git commit -m "test(opencode): verify npm tarball contains synced skills + behaviour-protocol"
```

---

### Task 4: Deterministic CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: all `tests/test_*.py`, the Bun plugin tests, `check-pack.py`.
- Produces: a CI workflow (the merge gate) with three jobs: `python` (OS×Python matrix), `plugin` (Bun), `pack` (tarball check).

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  python:
    name: setup suite (${{ matrix.os }} · py${{ matrix.python }})
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python: ['3.9', '3.10', '3.11', '3.12', '3.13']
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v8
        with:
          python-version: ${{ matrix.python }}
      - name: Run the Python test suite
        run: uv run --no-project python -m unittest discover -s tests -t tests -p "test_*.py" -v

  plugin:
    name: opencode plugin tests (bun)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: oven-sh/setup-bun@v2
      - name: Install plugin deps
        run: bun install
        working-directory: packages/ai-opencode
      - name: Run plugin tests
        run: bun test
        working-directory: packages/ai-opencode

  pack:
    name: npm tarball contents
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v8
        with:
          python-version: '3.12'
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Verify the published tarball contains the synced assets
        run: uv run --no-project packages/ai-opencode/scripts/check-pack.py --repo-root .
```

- [ ] **Step 2: Validate the workflow YAML parses**

Run: `uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('ci.yml OK')"`
Expected: `ci.yml OK`.

- [ ] **Step 3: Sanity-check the matrix commands locally**

Run the exact suite command the matrix uses, to confirm discovery works:
`uv run --no-project python -m unittest discover -s tests -t tests -p "test_*.py" -v`
Expected: all tests across `tests/` PASS (or SKIP where npm absent). No discovery/import errors.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: deterministic matrix — setup suite (OS×py), bun plugin tests, npm tarball check"
```

---

### Task 5: opencode smoke workflow (advisory)

**Files:**
- Create: `.github/workflows/opencode-smoke.yml`

**Interfaces:**
- Consumes: the repo's dogfood `opencode.json` + skills; `OPENROUTER_API_KEY` secret.
- Produces: an advisory workflow (manual + nightly) that runs a live opencode agent and checks it can see the `ai` skills. Never gates a merge.

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/opencode-smoke.yml`:

```yaml
name: opencode smoke (advisory)

on:
  workflow_dispatch:
  schedule:
    - cron: '0 6 * * *'  # nightly 06:00 UTC

jobs:
  smoke:
    name: live opencode skill discovery
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Guard — require OPENROUTER_API_KEY
        id: guard
        env:
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
        run: |
          if [ -z "$OPENROUTER_API_KEY" ]; then
            echo "OPENROUTER_API_KEY not set — skipping live smoke." >> "$GITHUB_STEP_SUMMARY"
            echo "run=false" >> "$GITHUB_OUTPUT"
          else
            echo "run=true" >> "$GITHUB_OUTPUT"
          fi
      - name: Install opencode
        if: steps.guard.outputs.run == 'true'
        run: |
          curl -fsSL https://opencode.ai/install | bash
          echo "$HOME/.opencode/bin" >> "$GITHUB_PATH"
      - name: Run a live skill-discovery prompt
        if: steps.guard.outputs.run == 'true'
        continue-on-error: true
        env:
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
        run: |
          out=$(opencode run --model openrouter/deepseek/deepseek-r1:free \
            "List the skill names available to you in this project. Reply with the bare names only.")
          echo "$out"
          echo "$out" | grep -qi "setup" \
            && echo "smoke: agent discovered the 'setup' skill ✓" \
            || echo "smoke: 'setup' skill not found in agent output (advisory — free-tier models drift)"
```

- [ ] **Step 2: Validate the workflow YAML parses**

Run: `uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('.github/workflows/opencode-smoke.yml')); print('smoke.yml OK')"`
Expected: `smoke.yml OK`.

- [ ] **Step 3: Verify the advisory wiring is correct**

Run:
```bash
grep -q 'continue-on-error: true' .github/workflows/opencode-smoke.yml \
  && grep -q 'workflow_dispatch' .github/workflows/opencode-smoke.yml \
  && grep -q 'schedule' .github/workflows/opencode-smoke.yml \
  && ! grep -q 'pull_request' .github/workflows/opencode-smoke.yml \
  && echo "advisory wiring OK"
```
Expected: `advisory wiring OK` (manual + nightly, never on PR, never blocks).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/opencode-smoke.yml
git commit -m "ci: advisory opencode smoke (manual + nightly, secret-gated, non-blocking)"
```

---

### Task 6: Release workflow + README CI badges + secrets docs

**Files:**
- Create: `.github/workflows/release.yml`
- Modify: `README.md` (CI badge + a short "CI & release" section documenting the secrets)

**Interfaces:**
- Consumes: `sync-assets.py`, the package, `NPM_TOKEN` secret.
- Produces: a `v*`-tag-triggered workflow that publishes `@bim-ba/ai-opencode`; README documents CI status and required secrets.

- [ ] **Step 1: Write the release workflow**

Create `.github/workflows/release.yml`:

```yaml
name: release @bim-ba/ai-opencode

on:
  push:
    tags: ['v*']

jobs:
  publish:
    name: npm publish
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v8
        with:
          python-version: '3.12'
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          registry-url: 'https://registry.npmjs.org'
      - name: Guard — require NPM_TOKEN
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
        run: |
          if [ -z "$NODE_AUTH_TOKEN" ]; then
            echo "NPM_TOKEN not set — cannot publish." >&2
            exit 1
          fi
      - name: Assert package version matches the tag
        run: |
          tag="${GITHUB_REF_NAME#v}"
          ver=$(uv run --no-project python -c "import json; print(json.load(open('packages/ai-opencode/package.json'))['version'])")
          if [ "$tag" != "$ver" ]; then
            echo "tag v$tag != package.json version $ver" >&2
            exit 1
          fi
          echo "version $ver matches tag"
      - name: Sync canonical assets into the package
        run: uv run --no-project packages/ai-opencode/scripts/sync-assets.py --repo-root . --package-root packages/ai-opencode
      - name: Publish
        run: npm publish --access public
        working-directory: packages/ai-opencode
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
```

- [ ] **Step 2: Validate the workflow YAML parses**

Run: `uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml')); print('release.yml OK')"`
Expected: `release.yml OK`.

- [ ] **Step 3: Add the CI badge + secrets docs to README**

In `README.md`, add a CI badge directly under the existing badge block (after the `GitHub last commit` badge line):

```markdown
[![CI](https://github.com/bim-ba/ai/actions/workflows/ci.yml/badge.svg)](https://github.com/bim-ba/ai/actions/workflows/ci.yml)
```

Then add this section just before the `## License` section:

```markdown
## CI & release

- **CI** (`.github/workflows/ci.yml`) runs on every push/PR to `main`: the `/setup` Python suite across `ubuntu`/`macos`/`windows` × Python 3.9–3.13, the opencode plugin's Bun tests, and an `npm pack` tarball-contents check. This is the merge gate.
- **opencode smoke** (`.github/workflows/opencode-smoke.yml`) is advisory — manual (`workflow_dispatch`) + nightly. It runs a live opencode agent on a free OpenRouter model to confirm the shared skills are discoverable. Requires the `OPENROUTER_API_KEY` repo secret; skips cleanly without it. Never blocks a merge.
- **Release** (`.github/workflows/release.yml`) publishes `@bim-ba/ai-opencode` to npm when a `v<version>` tag is pushed (the tag must match the package version). Requires the `NPM_TOKEN` repo secret.
```

- [ ] **Step 4: Verify badge + docs reference real workflows**

Run:
```bash
grep -q 'workflows/ci.yml/badge.svg' README.md \
  && grep -q 'OPENROUTER_API_KEY' README.md \
  && grep -q 'NPM_TOKEN' README.md \
  && test -f .github/workflows/release.yml \
  && echo "release docs OK"
```
Expected: `release docs OK`.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/release.yml README.md
git commit -m "ci: publish-on-tag release for @bim-ba/ai-opencode; README CI badge + secrets docs"
```

---

## Self-Review

**1. Spec coverage (Phase B bullet of the design doc + accumulated deferred items):**
- CI (full lint + e2e `/setup` matrix, deterministic): Task 4 (`ci.yml` python matrix) + Task 2 (manifest lint) + Task 1 (Windows-green via the symlink fix). ✅
- opencode-smoke job: Task 5 (advisory, secret-gated, non-blocking). ✅
- npm `publish`-on-tag for `@bim-ba/ai-opencode`: Task 6 (`release.yml`). ✅
- Deferred (Phase 0 M1) degenerate spark fixture: Task 2 Step 3. ✅
- Deferred (Phase 0/A) "no single test-runner": Task 4 `unittest discover` is the unified Python runner; Bun job runs the TS suite. ✅
- Deferred (Phase A final review) `npm pack` tarball coverage: Task 3 + wired into Task 4's `pack` job. ✅
- Deferred (Phase A final review) `engines.opencode` advisory → real gate in CI: partially — the version-match guard is in Task 6 release; opencode runtime-version enforcement remains advisory (documented). Noted as acceptable; no hard runtime gate added (YAGNI for an advisory engine key).
- Deferred (Phase A) `session.idle` surfacing validated first in Phase B: Task 5's live smoke is the validation vehicle; the fallback (fold into `instructions`) remains documented inline. ✅

**2. Placeholder scan:** No TBD/TODO. Every YAML/script/test step shows complete content; every command has expected output. The free-model id (`deepseek/deepseek-r1:free`) is concrete (advisory job; if the catalog drops it, the job degrades to a non-blocking miss — documented). ✅

**3. Type consistency:** `sync-assets.py --repo-root/--package-root` reused identically in Task 3 (`check-pack.py`), Task 6 (release sync step). `check-pack.py --repo-root` matches its test and the `pack` job. `unittest discover -s tests -t tests -p "test_*.py"` is the same command in Task 4 Step 1 (workflow) and Step 3 (local sanity). The `pack OK` / `ci.yml OK` / `release docs OK` sentinels match between their producing step and the asserting grep. ✅

## Note on operational decisions (confirm at plan review)
- **opencode smoke is advisory (not a PR gate).** Free-tier models are non-deterministic and rate-limited, and secrets aren't exposed to fork PRs — a blocking leg would flake the merge gate. If you want it blocking on `main` pushes (post-merge), that's a one-line trigger change; say so.
- **Task 1 modifies Phase-0 code** (`bootstrap.py`). It is in Phase B because the Windows matrix is what surfaces the symlink limitation; the matrix can't be green without it.
