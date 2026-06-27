# Design: OIDC publishing, SEO/repo-health, advisory free-model matrix

**Date:** 2026-06-27
**Status:** Approved (design); pending implementation plan
**Branch:** `feat/oidc-seo-model-matrix`

## Context

`bim-ba/ai` is a Claude Code plugin marketplace that also publishes one npm package
(`@bim-ba/ai-opencode`, an opencode adapter). CI already exists: a Python test matrix,
`bun test`, an npm-pack check, an advisory nightly opencode smoke, and a publish-on-tag
release. This work is a hardening + discoverability pass, deliberately scoped to **avoid
adding process** — comparable Claude Code marketplaces ship far less, and the maintainer
wants to stay close to that norm. Release automation (semantic-release / release-please /
Conventional Commits) is **explicitly out of scope** as over-engineering for a solo
<50-file repo.

Two live defects motivate part of the work and are absorbed (not fixed standalone):
- **Bug A — secret name mismatch:** `release.yml` reads `secrets.NPM_TOKEN`, but the repo
  secret added is `NPM_ACCESS_TOKEN`; the first `v*` tag would fail the guard. Absorbed by
  Thread 1 (token usage deleted entirely).
- **Bug B — dead model in the smoke:** `opencode-smoke.yml` calls
  `openrouter/deepseek/deepseek-r1:free`, which is no longer in OpenRouter's free list
  (verified live: 339 models, 26 free, `deepseek-r1:free` absent). Absorbed by Thread 2
  (self-healing model selection + auto-router).

The constraint that the whole repo honors: **`uv` is the only prerequisite on the Claude
side**; extracted scripts are stdlib-only with a PEP-723 header. The npm package uses Bun.
No `jq`/`yq`/`npx`.

## Goals

1. Replace the long-lived npm token with OIDC trusted publishing + provenance.
2. Make the advisory smoke self-healing and add a free-model JSON-schema matrix.
3. Improve discoverability (topics, description) and add the minimal worth-it health files.
4. Keep total workflow-file count at 3 (no new workflow files).

## Non-goals

- No semantic-release / release-please / changesets / Conventional Commits enforcement.
- No CODEOWNERS, FUNDING.yml, CODE_OF_CONDUCT.md, PR/issue templates (defer until real
  external traffic).
- No changes to the marketplace's git-based distribution or `marketplace.json` versioning.
- CLAUDE.md / agent-feature improvements (PROMPT point 1) and DX features (points 2/4) are
  next-session items, not in this spec.

---

## Thread 1 — OIDC trusted publishing (absorbs Bug A)

### What

Rewrite `.github/workflows/release.yml` to authenticate via GitHub OIDC instead of a
long-lived token, and emit provenance. Delete all `NPM_TOKEN` references.

### Design

- Job gains `permissions: { id-token: write, contents: read }`.
- Job runs in the `release` GitHub environment (Thread 4).
- Steps: checkout → setup-uv (for the version assert + sync-assets, which stay) →
  setup-node (node ≥ 22) → `npm install -g npm@latest` (runners ship npm older than the
  required ≥ 11.5.1) → keep the **version==tag assertion** → keep the **sync-assets** step
  → publish with the **npm CLI**: `npm publish --provenance --access public` in
  `packages/ai-opencode`.
- Bun is fine for build/test, but the **publish step must use npm CLI** — Bun does not yet
  support OIDC trusted publishing (oven-sh/bun#24855).
- Remove the "Guard — require NPM_TOKEN" step and both `NODE_AUTH_TOKEN` env blocks.

### Constraint: first publish cannot use OIDC

npm cannot configure a trusted publisher for a package that does not yet exist
(npm/cli#8544). `@bim-ba/ai-opencode` has never been published. Therefore `0.1.0` must be
published once by a traditional method before OIDC can take over.

### Manual one-time steps (maintainer; documented, not automated)

1. Publish `0.1.0` once locally: `cd packages/ai-opencode && npm login && uv run
   scripts/sync-assets.py --repo-root ../.. --package-root . && npm publish --access public`.
   (Or use the existing token for a single bootstrap publish.)
2. On npmjs.com → package → Settings → Trusted publishing: provider GitHub Actions, repo
   `bim-ba/ai`, workflow `release.yml`, environment `release`.
3. Delete the `NPM_ACCESS_TOKEN` repository secret.

After this, every `v*` tag publishes hands-free with provenance.

### Acceptance

- `release.yml` contains no `NPM_TOKEN`/`NPM_ACCESS_TOKEN`/`NODE_AUTH_TOKEN` references.
- `release.yml` has `id-token: write`, `environment: release`, `npm install -g npm@latest`,
  and `npm publish --provenance`.
- Version-assert and sync-assets steps still present and unchanged in behavior.
- README "secrets" docs updated: token path replaced by the OIDC one-time-setup checklist.

---

## Thread 2 — Advisory free-model matrix (absorbs Bug B)

### What

Rename `opencode-smoke.yml` → `advisory-smoke.yml`. Keep it advisory
(`workflow_dispatch` + nightly cron; `continue-on-error`). It gains a second job. Both jobs
guard on `OPENROUTER_API_KEY` and degrade gracefully when absent.

### Job `opencode` (existing, fixed)

Unchanged except the model: replace `openrouter/deepseek/deepseek-r1:free` with the
`openrouter/free` auto-router so it cannot rot to a delisted model id.

### Job `model-matrix` (new)

A stdlib-only PEP-723 script `scripts/model-matrix-check.py` run via `uv run --no-project`:

1. **Self-healing selection.** GET `https://openrouter.ai/api/v1/models`; filter to models
   that are currently free (`pricing.prompt == 0 && pricing.completion == 0`) AND advertise
   `structured_outputs` in `supported_parameters`. Take the first N=4 by a stable sort on
   `id`. (This is the fix for the class of bug that delisted `deepseek-r1:free`.)
2. **Probe.** For each selected model, POST to `/api/v1/chat/completions` with a fixed
   prompt and a strict `response_format` of type `json_schema` (a small schema, e.g.
   `{ project: string, skills: string[], agent_targets: string[] }`). Use only stdlib
   (`urllib.request`, `json`); read the key from `OPENROUTER_API_KEY`.
3. **Validate.** Assert the response body parses as JSON and conforms to the schema via a
   tiny hand-rolled validator (required keys present, types match — no `jsonschema` dep).
4. **Report.** Print a per-model ✓/✗ table to `$GITHUB_STEP_SUMMARY`. Advisory: the script
   exits 0 even on per-model failures; it only surfaces a non-zero exit on a total/internal
   error (e.g. the models endpoint is unreachable), and the job is `continue-on-error`
   regardless.

Honest framing recorded in the spec and the script's header comment: this primarily
exercises OpenRouter + the models' structured-output capability, not this repo's logic. It
is a cross-model capability/health smoke aligned with the project's cross-agent ethos —
valuable as advisory signal, never as a gate.

### Rate-limit awareness (verified)

OpenRouter free tier: 20 req/min; 50 req/day (1000/day if ≥ $10 credits ever purchased);
429s under load; provider-side throttling at peak; free list churns without notice. N=4
sequential probes nightly stays well inside limits. The script tolerates 429/timeout per
model as a ✗ row, not a crash.

### Testing (TDD)

- A unit test for the schema validator (valid object passes; missing key / wrong type
  fails) — pure, offline, runs in the existing Python CI matrix.
- A unit test for the free+structured filter given a sample `/models` payload fixture
  (offline; no network).
- No network calls in the test suite. The live probe runs only in the advisory workflow.

### Acceptance

- `advisory-smoke.yml` has two jobs (`opencode`, `model-matrix`), both advisory and
  key-guarded; the dead `deepseek-r1:free` id is gone.
- `scripts/model-matrix-check.py` is stdlib-only with a PEP-723 header and self-heals the
  model list from the live API.
- The validator + filter have offline unit tests added to `tests/` and pass in CI.

---

## Thread 3 — SEO + repo health

### Repository metadata (via `gh`)

- **Topics:** `claude-code, claude-code-plugin, claude-code-marketplace, claude-code-skills,
  claude-plugin, claude, anthropic, opencode`.
- **Description:** "Claude Code & opencode plugin marketplace — agent-behavior, workflow &
  data-engineering skills."

### Files added

- `SECURITY.md` — short (enables the "Report a vulnerability" button); private-disclosure
  contact, supported scope.
- `CONTRIBUTING.md` — short: branch-and-PR-to-`main` flow, `uv`-only Python prerequisite,
  how to run the tests (`uv run -m unittest discover -t tests`), skill-authoring pointer.
- `.github/dependabot.yml` — two ecosystems: `github-actions` (`directory: "/"`) and `npm`
  (`directory: "/packages/ai-opencode"`); weekly. No pip (Python side has zero deps).

### Manual checklist (maintainer; documented in spec, not automated)

- Upload a social-preview image (~1280×640) in repo Settings.
- Submit to: the Anthropic plugin directory (clau.de/plugin-directory-submission),
  claudemarketplaces.com, and 2–3 awesome-lists (e.g. `jmanhype/awesome-claude-code`,
  `Chat2AnyLLM/awesome-claude-plugins`). Drafting these submission PRs is an optional
  follow-up, out of this spec.

### Explicitly skipped

CODEOWNERS, FUNDING.yml, CODE_OF_CONDUCT.md, PR/issue templates — cargo-cult for a solo
repo at this stage.

### Acceptance

- `gh repo view` shows the new description and topics.
- `SECURITY.md`, `CONTRIBUTING.md`, `.github/dependabot.yml` exist and are valid.

---

## Thread 4 — `release` environment

Create one GitHub environment named `release` (via `gh api`), used solely to scope the OIDC
publish in Thread 1. No reviewer/wait-timer protection rules (solo maintainer → review
gates are theater). The trusted-publisher config (Thread 1 manual step) names this
environment.

### Acceptance

- `gh api repos/bim-ba/ai/environments/release` returns the environment.
- `release.yml` references `environment: release`.

---

## Delivery

- One feature branch `feat/oidc-seo-model-matrix`, subagent-driven implementation
  (maintainer's established pattern), merged to `main` via PR.
- Order: Thread 2 (code + tests) and Thread 3 files can proceed in parallel; Thread 1 +
  Thread 4 are coupled (the workflow references the environment).
- Verification before completion: the Python suite (incl. new validator/filter tests) green
  locally and in CI; `release.yml` and `advisory-smoke.yml` validated; `gh` confirms
  topics/description/environment applied.

## Risks / open points

- The model-matrix smoke is genuinely low-value-signal (tests OpenRouter, not the repo).
  Accepted as advisory because it matches the project's cross-agent ethos and the maintainer
  asked for it; revisit if it produces noise.
- OIDC bootstrap requires a manual first publish; until `0.1.0` exists on npm and the
  trusted publisher is configured, the release workflow will fail at publish — this is
  expected and documented.
