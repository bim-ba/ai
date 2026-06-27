# @bim-ba/ai-opencode

[![npm version](https://img.shields.io/npm/v/@bim-ba/ai-opencode?color=5A67D8)](https://www.npmjs.com/package/@bim-ba/ai-opencode)
[![provenance](https://img.shields.io/badge/npm-provenance-5A67D8?logo=npm)](https://www.npmjs.com/package/@bim-ba/ai-opencode#provenance)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/bim-ba/ai/blob/main/LICENSE)

The [opencode](https://opencode.ai) adapter for **[`ai`](https://github.com/bim-ba/ai)** — a cross-agent toolkit of reusable agent behaviour and skills. Same skills and behaviour protocol that the `ai` Claude Code marketplace ships, delivered to opencode as a self-wiring plugin.

## Install

Add the plugin to your `opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": ["@bim-ba/ai-opencode"]
}
```

That's the whole setup. opencode runs on Bun, so the TypeScript plugin loads directly — no build step.

## What it does (self-wiring)

On load, the plugin's `config()` hook wires everything in, existence-guarded and non-destructive (it never clobbers your own config or double-wires):

- **Behaviour protocol** → injected into `instructions` (baseline conventions for every session).
- **Skills** → added to `skills.paths` so opencode discovers them natively.
- **Drift-log reminder** → a `session.idle` event hook that nudges you to capture divergences between actual behavior and codified conventions.

## Agent parity

| Capability | Claude Code | opencode (this package) |
|------------|-------------|-------------------------|
| Skills (`SKILL.md`) | native | via `skills.paths` (self-wired) |
| Behaviour protocol | SessionStart hook | injected into `instructions` (self-wired) |
| Drift-log reminder | Stop hook | `session.idle` event hook |
| Delivery | git marketplace (`bim-ba/ai`) | npm (`@bim-ba/ai-opencode`) |

## Provenance

Published from GitHub Actions via npm [OIDC trusted publishing](https://docs.npmjs.com/trusted-publishers/) with `--provenance` — every release carries a verifiable supply-chain attestation.

## Links

- **Marketplace & full docs:** https://github.com/bim-ba/ai
- **Issues:** https://github.com/bim-ba/ai/issues
- **License:** [MIT](https://github.com/bim-ba/ai/blob/main/LICENSE)
