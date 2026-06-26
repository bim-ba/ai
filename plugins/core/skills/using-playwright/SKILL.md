---
name: using-playwright
description: Use when driving any web UI through the Playwright MCP -- logging into SSO-gated portals, filling Monaco or textarea editors, extracting page content, or operating internal tools via browser automation. Covers session/login handling, reliable text input, snapshot-vs-screenshot, and token-efficient extraction.
---

# Skill: using-playwright

## Purpose

Reliable, token-efficient browser automation via the Playwright MCP -- the generic substrate. Service-specific playbooks (per-service login flows, navigation patterns, specific UI quirks) live in a per-project skill (e.g. `using-<service>` with `references/<service>.md`); this skill stays tool-agnostic.

## Pre-checks (every session)

1. **Playwright MCP must be loaded THIS session** -- the tool server pins at session start. If `mcp__playwright__*` is absent, the session predates the MCP -> restart.
2. **Playwright runs its OWN browser session** -- the user's SSO login in their personal browser does NOT carry over. A persistent profile may keep you logged in across runs; verify, don't assume.

## Login handling (keep Playwright on the MAIN session)

- Login pages need a human (SSO) -- do NOT hand Playwright to a subagent for a login flow.
- Navigate to the portal, then **snapshot to check login state** (look for the user's avatar/name or real content vs a login/SSO redirect).
- If already logged in (persistent profile) -- proceed; do NOT ask the user to log in.
- If SSO-gated -- `AskUserQuestion` asking the user to log in manually in the Playwright window, then confirm via a fresh snapshot before driving. Do the navigate first so the login page is actually up.

## Input mechanics (the load-bearing part)

- **Monaco editors** (SQL/YAML code editors): `browser_type`/`fill` FAIL (native-edit-context div) and char-typing triggers auto-indent/auto-close that corrupts multi-line text. Use `browser_evaluate`: `window.monaco.editor.getModels().find(m => m.getValue().includes('<anchor>')).setValue(\`<text>\`)` then read `getValue()` back to verify.
- **Plain textarea** (React-controlled prompt boxes): do NOT `browser_type` a multi-line prompt -- a newline can submit it early. Set the value via the native setter so React's onChange fires, then dispatch `input`:
  ```js
  const ta = document.querySelector('textarea');
  const set = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
  set.call(ta, prompt); ta.dispatchEvent(new Event('input', { bubbles: true }));
  ```
  Verify `ta.value.length`, then click the send button (it enables once React sees input).
- **snapshot over screenshot** for actions -- the snapshot yields element refs to click; refs change per navigation, so re-snapshot after each nav. Screenshot only when you need the visual.

## Token-efficient extraction

- Prefer `browser_evaluate(() => (document.querySelector('main')||document.body).innerText.slice(0, N))` over a full a11y snapshot for reading content.
- Large `browser_evaluate` / snapshot outputs are saved to a file -- `rg`/`jq`/`grep` that file rather than re-reading wholesale.

## Service-specific playbooks

Per-service playbooks (login flows, navigation patterns, UI-specific quirks) live in a per-project skill (e.g. `using-<service>` with `references/<service>.md`). This skill stays tool-agnostic.

## Guardrails

- Read-only by default. Outward writes (create a page/card, submit a form that publishes, click "Create delivery") only on explicit user ok.
- Never reproduce a secret seen on screen -- redact as `[SECRET REDACTED]`.
