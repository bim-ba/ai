---
name: handling-secrets-safely
type: skill
category: rulebook
description: Use when inspecting, probing, or reporting on any credential-bearing file (.mcp.json, .env, *.pem, ~/.git-credentials, ~/.netrc, a secret store) or when clearing a "no secrets" / security-sweep verdict - the mechanics that keep a well-intentioned command from leaking a value through tool output, a diff echo, a query error, or a shallow history scan. The high-level policy (where secrets live, rotation) is assumed; this is the HOW.
---

# Handling Secrets Safely

The generic posture - secrets live outside repos and gitignored, never echo a secret, rotate any leak - is assumed. This skill is the mechanics that stop a well-intentioned command from disclosing a value anyway. Every rule below is a real incident distilled to a check.

## When to use

- Probing or reading a credential-bearing file: `.mcp.json`, `.env*`, `*.pem`, `~/.git-credentials`, `~/.netrc`, a secret store.
- Clearing a "no secrets committed" or security-sweep verdict.
- Using a secret in a command (a token in an API call, a password in a connection string).
- Writing config that must reference a secret.

## When NOT to use

- Ordinary files with no credential content.
- The high-level secret POLICY (where secrets live, how rotation works) - that belongs in the personal layer / a project CLAUDE.md; this skill is only the leak-mechanics.

## Rules

### 1. A "no secrets" verdict must scan git HISTORY, not the working tree

A secret added then removed still lives on the remote and in every clone. Scan all of history - `gitleaks git --log-opts=--all` (or `git log -p -S'<pattern>' --all`) - a clean working tree is NOT proof. A secret found in history is already leaked: rotate it; deleting the file does not un-leak it.

### 2. On a credential-bearing file, use boolean/count probes ONLY

`grep -c`, `wc -l`, `stat`, `jq 'keys'` / `jq 'paths'` - never a content transform. A `sed`/`awk`/`cut`/regex-substring that fails to match prints the raw line VERBATIM (the secret) to tool output. To USE a value, capture it into a shell variable in one step (`TOKEN=$(jq -r .token file)`) and operate on `$TOKEN` unprinted - never echo it, never pass it to a command whose invocation is logged.

### 3. Never combine a redacting view with a non-redacting fallback

`redacting-cmd || cat file` prints the raw file the moment the first command fails. One command, redacting-only - no `||` / `;` / `&&` fallthrough to a raw view.

### 4. Never edit a secret-bearing file through Write/Edit/patch tools

The harness echoes a FULL-FILE diff on any tracked-file modification, so even a values-suppressing transform lands every leaf secret in the transcript. When a config must hold a secret, use `{env:VAR}` / `{file:path}` indirection to a leaf file the agent never Reads/Writes/Edits. "Never print a value" does NOT cover the file-modified diff echo - this is a separate disclosure path.

### 5. Never put a secret in query or command text

Engines (ClickHouse and most databases) echo a FAILING query verbatim in the error and in `query_log`. A `password='...'` in `CREATE NAMED COLLECTION` is disclosed on the first failure. Resolve secrets server-side (named collections, `from_env()`); treat any errored secret-bearing query as a disclosure and rotate.

### 6. Never inline a secret into a subagent prompt or reproduce one from a log

A dispatched prompt is context - a secret in it is a leak. Never reproduce a credential seen in a log, dump, or config; redact as `[SECRET REDACTED: <type>]`.

## Anti-patterns

- `sed -n 's/token=\(.*\)/\1/p' .env` - prints the whole line when the regex misses. Use `grep -c token .env` (count) or `TOKEN=$(...)` (capture, unprinted).
- `git grep -I '<secret>'` on the working tree to "confirm it is gone" - misses history. Use `--all`.
- `jq 'del(.mcpServers.x.headers.token)' .mcp.json > tmp && mv tmp .mcp.json` - the Write/Edit diff echo still prints the original file. Do not tool-edit a secret file; use `{env:}`/`{file:}` indirection.
- `redact.py file || cat file` - the fallback dumps the secret on any redact error.
- Pasting a token into a Bash command line (echoed) or into a subagent prompt.

## References

Rotation cadence and where-secrets-live policy: the personal layer and each project's `CLAUDE.md`. The `security/config_guard` hook example (`plugins/core/hooks/examples/`) enforces the "no hardcoded secret / no weakened guardrail" slice of this at write time.
