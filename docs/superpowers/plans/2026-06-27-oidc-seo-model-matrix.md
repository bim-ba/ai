# OIDC publishing, SEO/repo-health, advisory free-model matrix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the long-lived npm token with OIDC trusted publishing, make the advisory smoke self-healing + add a free-model JSON-schema matrix, and improve discoverability with topics/description + minimal repo-health files.

**Architecture:** Four mostly-independent threads on one branch (`feat/oidc-seo-model-matrix`). A new stdlib-only `uv` script self-heals the free-model list from OpenRouter's live API and validates structured output against a small JSON-Schema subset; its pure functions are unit-tested offline. Workflow changes are guarded by string-assertion tests. Repo metadata + a scoped `release` environment are applied to the live repo via `gh`.

**Tech Stack:** Python 3.9+ stdlib (`urllib`, `json`, `unittest`), `uv run --no-project`, GitHub Actions, `gh` CLI, npm OIDC trusted publishing.

## Global Constraints

- **`uv` is the only Claude-side prerequisite** — no `jq`/`yq`/`npx`. (CLAUDE.md)
- **Extracted scripts are stdlib-only** with a PEP-723 header: `requires-python = ">=3.9"`, `dependencies = []`. (CLAUDE.md)
- **Tests use no third-party deps** — string assertions over YAML, not a YAML parser; `read_text(encoding="utf-8")` always (Windows CI decodes cp1252 by default).
- **Total workflow-file count stays at 3** — rename `opencode-smoke.yml` → `advisory-smoke.yml`; do not add a new workflow file.
- **Publish step uses the npm CLI**, not Bun (Bun lacks OIDC publish — oven-sh/bun#24855); npm must be upgraded to `@latest` (OIDC needs ≥ 11.5.1); node ≥ 22.
- **`main` is the published trunk** — feature branch → PR → merge.

---

### Task 1: Free-model matrix probe script + pure-function unit tests

**Files:**
- Create: `scripts/model-matrix-check.py`
- Test: `tests/test_model_matrix.py`

**Interfaces:**
- Produces: `select_free_structured_models(payload: dict, n: int = 4) -> list[str]`; `validate_against_schema(obj, schema: dict) -> list[str]` (empty list == valid); `PROBE_SCHEMA: dict`; `probe_model(model_id, api_key, prompt=PROBE_PROMPT, schema=PROBE_SCHEMA) -> tuple[bool, str]`; `main() -> int`.
- Consumes: nothing from other tasks. Task 2's workflow invokes this script by path.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_model_matrix.py`:

```python
"""Offline unit tests for the free-model matrix probe (no network)."""
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "model-matrix-check.py"
_spec = importlib.util.spec_from_file_location("model_matrix_check", SCRIPT)
mm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mm)


class TestSelect(unittest.TestCase):
    def _payload(self):
        return {"data": [
            {"id": "b/struct:free", "pricing": {"prompt": "0", "completion": "0"},
             "supported_parameters": ["structured_outputs", "response_format"]},
            {"id": "a/struct:free", "pricing": {"prompt": "0", "completion": "0"},
             "supported_parameters": ["structured_outputs"]},
            {"id": "c/nostruct:free", "pricing": {"prompt": "0", "completion": "0"},
             "supported_parameters": ["tools"]},
            {"id": "d/paid-struct", "pricing": {"prompt": "0.001", "completion": "0"},
             "supported_parameters": ["structured_outputs"]},
        ]}

    def test_selects_only_free_and_structured_sorted(self):
        self.assertEqual(
            mm.select_free_structured_models(self._payload()),
            ["a/struct:free", "b/struct:free"],
        )

    def test_respects_n_cap(self):
        payload = {"data": [
            {"id": f"m{i}:free", "pricing": {"prompt": 0, "completion": 0},
             "supported_parameters": ["structured_outputs"]} for i in range(10)
        ]}
        self.assertEqual(len(mm.select_free_structured_models(payload, n=3)), 3)

    def test_empty_when_none_match(self):
        self.assertEqual(mm.select_free_structured_models({"data": []}), [])


class TestValidate(unittest.TestCase):
    def test_valid_object_passes(self):
        obj = {"project": "ai", "skills": ["a", "b"], "agent_targets": ["claude"]}
        self.assertEqual(mm.validate_against_schema(obj, mm.PROBE_SCHEMA), [])

    def test_missing_required_key_fails(self):
        errs = mm.validate_against_schema({"project": "ai", "skills": ["a"]}, mm.PROBE_SCHEMA)
        self.assertTrue(any("agent_targets" in e for e in errs))

    def test_wrong_type_fails(self):
        obj = {"project": "ai", "skills": "not-a-list", "agent_targets": []}
        errs = mm.validate_against_schema(obj, mm.PROBE_SCHEMA)
        self.assertTrue(any("skills" in e for e in errs))

    def test_non_object_root_fails(self):
        self.assertTrue(mm.validate_against_schema(["x"], mm.PROBE_SCHEMA))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --no-project python -m unittest discover -s tests -t tests -p "test_model_matrix.py" -v`
Expected: FAIL — `FileNotFoundError` because `scripts/model-matrix-check.py` does not exist yet.

- [ ] **Step 3: Write the script**

Create `scripts/model-matrix-check.py`:

```python
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Advisory free-model JSON-schema matrix probe.

NOTE: This primarily exercises OpenRouter and the selected models' structured-output
capability, not this repo's own logic. It is a cross-model capability/health smoke
aligned with the project's cross-agent ethos — advisory signal only, never a gate.

Self-healing: the free-model list is fetched live from OpenRouter and filtered, so it
cannot rot to a delisted model id (the failure mode that left a dead model in the old
smoke). Pure functions (select/validate) are unit-tested offline in tests/.
"""
import json
import os
import sys
import urllib.error
import urllib.request

OPENROUTER_BASE = "https://openrouter.ai/api/v1"

# A JSON-Schema subset used BOTH as the API response_format and for local validation.
PROBE_SCHEMA = {
    "type": "object",
    "required": ["project", "skills", "agent_targets"],
    "properties": {
        "project": {"type": "string"},
        "skills": {"type": "array"},
        "agent_targets": {"type": "array"},
    },
    "additionalProperties": False,
}

PROBE_PROMPT = (
    "Reply ONLY with JSON matching the schema. "
    "project: the string 'ai'. "
    "skills: a list of 2-3 example skill names. "
    "agent_targets: the list of AI agents this project targets."
)

_TYPE_MAP = {
    "object": dict,
    "string": str,
    "array": list,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
}


def select_free_structured_models(payload, n=4):
    """Return up to n model ids that are currently free and support structured outputs.

    free := pricing.prompt == 0 and pricing.completion == 0
    structured := 'structured_outputs' in supported_parameters
    Deterministic: sorted by id.
    """
    out = []
    for m in payload.get("data", []):
        pricing = m.get("pricing") or {}
        try:
            free = (float(pricing.get("prompt", 1)) == 0.0
                    and float(pricing.get("completion", 1)) == 0.0)
        except (TypeError, ValueError):
            free = False
        sp = m.get("supported_parameters") or []
        if free and "structured_outputs" in sp and m.get("id"):
            out.append(m["id"])
    out.sort()
    return out[:n]


def validate_against_schema(obj, schema):
    """Minimal JSON-Schema-subset validator. Returns a list of error strings ([] == valid).

    Supports top-level type, required keys, and per-property primitive types
    (object/string/array/number/integer/boolean). No nested validation beyond type.
    """
    errors = []
    top = schema.get("type")
    if top and not isinstance(obj, _TYPE_MAP.get(top, object)):
        errors.append(f"root: expected {top}, got {type(obj).__name__}")
        return errors
    if top == "object":
        for key in schema.get("required", []):
            if key not in obj:
                errors.append(f"missing required key: {key}")
        for key, spec in (schema.get("properties") or {}).items():
            if key in obj:
                want = spec.get("type")
                if want and not isinstance(obj[key], _TYPE_MAP.get(want, object)):
                    errors.append(f"{key}: expected {want}, got {type(obj[key]).__name__}")
    return errors


def _http_json(url, api_key=None, data=None, timeout=60):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        url, data=body, headers=headers, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def probe_model(model_id, api_key, prompt=PROBE_PROMPT, schema=PROBE_SCHEMA):
    """Call one model with a strict json_schema response_format; return (ok, detail)."""
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "probe", "strict": True, "schema": schema},
        },
    }
    try:
        resp = _http_json(f"{OPENROUTER_BASE}/chat/completions",
                          api_key=api_key, data=payload, timeout=60)
    except (urllib.error.URLError, TimeoutError) as e:
        return False, f"request failed: {e}"
    try:
        content = resp["choices"][0]["message"]["content"]
        obj = json.loads(content)
    except (KeyError, IndexError, ValueError, TypeError) as e:
        return False, f"unparseable response: {e}"
    errs = validate_against_schema(obj, schema)
    return (not errs), ("; ".join(errs) if errs else "valid")


def main():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("OPENROUTER_API_KEY not set — skipping model matrix (advisory).")
        return 0
    try:
        models = _http_json(f"{OPENROUTER_BASE}/models", timeout=30)
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"could not fetch model list: {e}", file=sys.stderr)
        return 1  # total/internal failure; job is continue-on-error regardless
    selected = select_free_structured_models(models, n=4)
    if not selected:
        print("no free structured-output models currently available — advisory skip.")
        return 0
    print(f"Probing {len(selected)} free structured-output models:\n")
    print("| model | result |")
    print("|-------|--------|")
    for mid in selected:
        ok, detail = probe_model(mid, api_key)
        print(f"| `{mid}` | {'✓' if ok else '✗'} {detail} |")
    return 0  # advisory: per-model failures never fail the build


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --no-project python -m unittest discover -s tests -t tests -p "test_model_matrix.py" -v`
Expected: PASS — 7 tests OK.

- [ ] **Step 5: Commit**

```bash
git add scripts/model-matrix-check.py tests/test_model_matrix.py
git commit -m "feat: self-healing free-model JSON-schema probe + offline unit tests"
```

---

### Task 2: Advisory smoke workflow — rename + model-matrix job (absorbs dead-model bug)

**Files:**
- Create: `.github/workflows/advisory-smoke.yml`
- Delete: `.github/workflows/opencode-smoke.yml`
- Create: `tests/test_workflows.py`

**Interfaces:**
- Consumes: `scripts/model-matrix-check.py` (Task 1), invoked by path.
- Produces: nothing for later tasks (Task 3 appends to `tests/test_workflows.py`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_workflows.py`:

```python
"""String-assertion guards for workflow files (no YAML dep)."""
import unittest
from pathlib import Path

WF = Path(__file__).resolve().parents[1] / ".github" / "workflows"


class TestAdvisorySmoke(unittest.TestCase):
    def test_renamed_from_opencode_smoke(self):
        self.assertTrue((WF / "advisory-smoke.yml").exists())
        self.assertFalse((WF / "opencode-smoke.yml").exists())

    def test_dead_model_gone(self):
        txt = (WF / "advisory-smoke.yml").read_text(encoding="utf-8")
        self.assertNotIn("deepseek-r1", txt)

    def test_has_both_jobs(self):
        txt = (WF / "advisory-smoke.yml").read_text(encoding="utf-8")
        self.assertIn("model-matrix", txt)
        self.assertIn("opencode", txt)

    def test_matrix_job_runs_the_script(self):
        txt = (WF / "advisory-smoke.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/model-matrix-check.py", txt)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --no-project python -m unittest discover -s tests -t tests -p "test_workflows.py" -v`
Expected: FAIL — `advisory-smoke.yml` missing / `opencode-smoke.yml` still present.

- [ ] **Step 3: Create the renamed workflow with both jobs**

Create `.github/workflows/advisory-smoke.yml`:

```yaml
name: advisory smoke

on:
  workflow_dispatch:
  schedule:
    - cron: '0 6 * * *'  # nightly 06:00 UTC

jobs:
  opencode:
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
        timeout-minutes: 10
        env:
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
        run: |
          out=$(opencode run --model openrouter/openrouter/free \
            "List the skill names available to you in this project. Reply with the bare names only.")
          echo "$out"
          echo "$out" | grep -qi "setup" \
            && echo "smoke: agent discovered the 'setup' skill ✓" \
            || echo "smoke: 'setup' skill not found (advisory — free-tier models drift)"

  model-matrix:
    name: free-model JSON-schema matrix
    runs-on: ubuntu-latest
    continue-on-error: true
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v8.2.0
        with:
          python-version: '3.12'
      - name: Probe free structured-output models
        timeout-minutes: 10
        env:
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
        run: uv run --no-project scripts/model-matrix-check.py >> "$GITHUB_STEP_SUMMARY"
```

Note: `--model openrouter/openrouter/free` is intentional — opencode provider `openrouter` + OpenRouter's curated always-free model id `openrouter/free`, chosen for churn-resistance. The job is advisory, so a 404 if it is ever delisted does not block anything.

- [ ] **Step 4: Delete the old workflow**

```bash
git rm .github/workflows/opencode-smoke.yml
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --no-project python -m unittest discover -s tests -t tests -p "test_workflows.py" -v`
Expected: PASS — 4 tests OK.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/advisory-smoke.yml tests/test_workflows.py
git commit -m "feat: advisory-smoke with self-healing free-model matrix; drop dead deepseek-r1 model"
```

---

### Task 3: OIDC release workflow + README docs (absorbs npm-token bug)

**Files:**
- Modify: `.github/workflows/release.yml` (full rewrite)
- Modify: `README.md:110-111`
- Modify: `tests/test_workflows.py` (append a `TestReleaseWorkflow` class)

**Interfaces:**
- Consumes: `tests/test_workflows.py` from Task 2 (append, do not overwrite).
- Produces: nothing for later tasks.

- [ ] **Step 1: Append the failing test**

Append to `tests/test_workflows.py` (before the `if __name__` block):

```python
class TestReleaseWorkflow(unittest.TestCase):
    def setUp(self):
        self.txt = (WF / "release.yml").read_text(encoding="utf-8")

    def test_uses_oidc(self):
        self.assertIn("id-token: write", self.txt)

    def test_scoped_to_release_environment(self):
        self.assertIn("environment: release", self.txt)

    def test_publishes_with_provenance(self):
        self.assertIn("--provenance", self.txt)

    def test_no_long_lived_token(self):
        self.assertNotIn("NPM_TOKEN", self.txt)
        self.assertNotIn("NPM_ACCESS_TOKEN", self.txt)
        self.assertNotIn("NODE_AUTH_TOKEN", self.txt)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --no-project python -m unittest discover -s tests -t tests -p "test_workflows.py" -v`
Expected: FAIL — the new `TestReleaseWorkflow` cases fail (current `release.yml` has `NPM_TOKEN`/`NODE_AUTH_TOKEN`, no `id-token`/`environment`/`--provenance`).

- [ ] **Step 3: Rewrite the release workflow**

Replace the entire contents of `.github/workflows/release.yml` with:

```yaml
name: release @bim-ba/ai-opencode

on:
  push:
    tags: ['v*']

permissions:
  contents: read
  id-token: write

jobs:
  publish:
    name: npm publish (OIDC)
    runs-on: ubuntu-latest
    environment: release
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v8.2.0
        with:
          python-version: '3.12'
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          registry-url: 'https://registry.npmjs.org'
      - name: Upgrade npm (OIDC trusted publishing needs >= 11.5.1)
        run: npm install -g npm@latest
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
      - name: Publish with provenance
        run: npm publish --provenance --access public
        working-directory: packages/ai-opencode
```

- [ ] **Step 4: Update README CI & release docs**

In `README.md`, replace lines 110–111 (the "opencode smoke" + "Release" bullets) with:

```markdown
- **Advisory smoke** (`.github/workflows/advisory-smoke.yml`) is advisory — manual (`workflow_dispatch`) + nightly. The `opencode` job runs a live opencode agent on OpenRouter's curated free model to confirm the shared skills are discoverable; the `model-matrix` job self-heals the current free structured-output models from OpenRouter and validates a JSON-Schema response from each. Requires the `OPENROUTER_API_KEY` repo secret; skips cleanly without it. Never blocks a merge.
- **Release** (`.github/workflows/release.yml`) publishes `@bim-ba/ai-opencode` to npm with provenance when a `v<version>` tag is pushed (the tag must match the package version). Auth is **OIDC trusted publishing** — no long-lived token. One-time setup: (1) publish `0.1.0` once manually (`cd packages/ai-opencode && npm login && npm publish --access public`) so the package exists; (2) on npmjs.com → package → Settings → Trusted publishing, add provider GitHub Actions, repo `bim-ba/ai`, workflow `release.yml`, environment `release`; (3) delete any `NPM_ACCESS_TOKEN`/`NPM_TOKEN` secret. After that, every `v*` tag publishes hands-free.
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --no-project python -m unittest discover -s tests -t tests -p "test_workflows.py" -v`
Expected: PASS — all `TestAdvisorySmoke` + `TestReleaseWorkflow` tests OK.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/release.yml README.md tests/test_workflows.py
git commit -m "feat: OIDC trusted publishing for release (drop npm token); update CI docs"
```

---

### Task 4: Minimal repo-health files

**Files:**
- Create: `SECURITY.md`
- Create: `CONTRIBUTING.md`
- Create: `.github/dependabot.yml`
- Test: `tests/test_repo_health.py`

**Interfaces:** none consumed/produced.

- [ ] **Step 1: Write the failing test**

Create `tests/test_repo_health.py`:

```python
"""Presence + minimal-shape checks for repo-health files (no YAML dep)."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestRepoHealth(unittest.TestCase):
    def test_security_exists(self):
        self.assertTrue((ROOT / "SECURITY.md").read_text(encoding="utf-8").strip())

    def test_contributing_exists(self):
        self.assertTrue((ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8").strip())

    def test_dependabot_two_ecosystems(self):
        txt = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
        self.assertIn("github-actions", txt)
        self.assertIn("npm", txt)
        self.assertNotIn("pip", txt)  # Python side is stdlib-only, no deps to bump


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --no-project python -m unittest discover -s tests -t tests -p "test_repo_health.py" -v`
Expected: FAIL — files do not exist.

- [ ] **Step 3: Create `SECURITY.md`**

```markdown
# Security Policy

## Reporting a vulnerability

Please report security issues privately via GitHub's **"Report a vulnerability"**
button (repository → Security → Advisories), or email careless.sava@gmail.com.
Do not open a public issue for security reports.

## Scope

This repo ships installable agent instructions, skills, and the `@bim-ba/ai-opencode`
npm package. Relevant concerns include malicious skill content, supply-chain issues in
the published package, and unsafe commands in scripts. We aim to acknowledge reports
within a few days.
```

- [ ] **Step 4: Create `CONTRIBUTING.md`** (the outer fence below is 4 backticks so the inner command fence renders literally)

````markdown
# Contributing

Thanks for your interest in `ai`.

## Workflow

- Work on a feature branch; open a PR into `main` (the published trunk).
- `uv` is the only prerequisite for the Claude side — no `jq`/`yq`/`npx`. Extracted
  scripts are stdlib-only with a PEP-723 header.
- New skills follow `plugins/core/templates/skills-authoring-standard.md`.
- Specs and plans live under `docs/superpowers/`.

## Tests

```
uv run --no-project python -m unittest discover -s tests -t tests -p "test_*.py" -v
```

The opencode adapter (`packages/ai-opencode/`) uses Bun: `bun test`.
````

- [ ] **Step 5: Create `.github/dependabot.yml`**

```yaml
version: 2
updates:
  - package-ecosystem: github-actions
    directory: "/"
    schedule:
      interval: weekly
  - package-ecosystem: npm
    directory: "/packages/ai-opencode"
    schedule:
      interval: weekly
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run --no-project python -m unittest discover -s tests -t tests -p "test_repo_health.py" -v`
Expected: PASS — 3 tests OK.

- [ ] **Step 7: Commit**

```bash
git add SECURITY.md CONTRIBUTING.md .github/dependabot.yml tests/test_repo_health.py
git commit -m "chore: add SECURITY.md, CONTRIBUTING.md, dependabot config"
```

---

### Task 5: Live repo metadata + `release` environment (via `gh`)

**Files:** none — this task mutates the live GitHub repo. No code/tests; verification is via `gh`.

> This task makes outward-facing changes to `github.com/bim-ba/ai`. Run the commands, then verify. If any `gh` call lacks scope/permission, report it and stop — do not retry silently.

- [ ] **Step 1: Set description + topics**

```bash
gh repo edit bim-ba/ai \
  --description "Claude Code & opencode plugin marketplace — agent-behavior, workflow & data-engineering skills." \
  --add-topic claude-code --add-topic claude-code-plugin --add-topic claude-code-marketplace \
  --add-topic claude-code-skills --add-topic claude-plugin --add-topic claude \
  --add-topic anthropic --add-topic opencode
```

- [ ] **Step 2: Verify description + topics**

Run: `gh repo view bim-ba/ai --json description,repositoryTopics`
Expected: the new description and all 8 topics present.

- [ ] **Step 3: Create the `release` environment**

```bash
gh api -X PUT repos/bim-ba/ai/environments/release
```

- [ ] **Step 4: Verify the environment exists**

Run: `gh api repos/bim-ba/ai/environments/release --jq .name`
Expected: `release`

- [ ] **Step 5: No commit** — this task changed no files. Record completion in the PR description instead.

---

## Final verification (run before opening the PR)

- [ ] Full Python suite green:

```bash
uv run --no-project python -m unittest discover -s tests -t tests -v
```

Expected: all tests pass (incl. `test_model_matrix`, `test_workflows`, `test_repo_health`, plus the pre-existing suites).

- [ ] The script runs end-to-end offline-safe (no key → advisory skip, exit 0):

```bash
env -u OPENROUTER_API_KEY uv run --no-project scripts/model-matrix-check.py; echo "exit=$?"
```

Expected: prints the advisory-skip line; `exit=0`.

- [ ] `gh repo view bim-ba/ai` shows the new description + topics; `gh api repos/bim-ba/ai/environments/release` returns the environment.

---

## Manual maintainer steps (outside this plan — documented for the PR description)

1. Publish `0.1.0` once locally so the npm package exists (OIDC cannot do the first publish — npm/cli#8544).
2. Configure the npm trusted publisher (repo `bim-ba/ai`, workflow `release.yml`, environment `release`).
3. Delete the `NPM_ACCESS_TOKEN` repo secret.
4. Upload a social-preview image (~1280×640) in repo Settings.
5. Submit to the Anthropic plugin directory + claudemarketplaces.com + 2–3 awesome-lists.

## Self-review notes

- **Spec coverage:** Thread 1 → Task 3 (+ manual steps); Thread 2 → Tasks 1–2; Thread 3 → Tasks 4–5 (+ manual image/directory steps); Thread 4 → Task 5. All spec sections map to a task.
- **Placeholders:** none — every code/file step shows full content.
- **Type consistency:** `select_free_structured_models`, `validate_against_schema`, `PROBE_SCHEMA`, `probe_model` names match between Task 1's script and its tests; `tests/test_workflows.py` is created in Task 2 and appended (not redefined) in Task 3.
