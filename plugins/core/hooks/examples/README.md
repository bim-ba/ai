# Example hooks

Runnable, agent-agnostic reference hooks that demonstrate the pattern in
`../../templates/hooks-authoring-standard.md`: one readable stdlib-only module per hook, shared
plumbing in `utils.py` / `models.py`, and data (trigger phrases) in a sibling `triggers.json` instead
of in code.

These are EXAMPLES. They are deliberately NOT registered in `../hooks.json`, so they do not auto-run.
Copy the ones you want into your project's `.claude/hooks/` and wire each in your `settings.json`
(see the snippets below), or adapt them. Nothing here fires until you wire it.

## Shared skeleton

| File | Role |
|---|---|
| `models.py` | TypedDict shapes of the stdin payload (`HookEvent`, `ToolInput`). |
| `utils.py` | Shared plumbing: `read_payload` / `tool_input` / `written_text` / `in_project` / `load_sidecar_json` / `emit_additional_context` / `run(main)` (error-swallowing entrypoint). |

## Hooks

| Module | Event | Decides |
|---|---|---|
| `artifact_guard.py` | `PostToolUse(Write|Edit)` | Flags hard-unicode / emoji / smart-arrows / em-dash / hard-wrap in just-written files (keeps Cyrillic + guillemets as content). Non-blocking nudge. |
| `config_guard.py` | `PreToolUse(Write|Edit)` | Warns on weakening a guardrail config (pre-commit / gitleaks / `.mcp.json` / `.claude/settings.json`) or hardcoding a generic-shaped secret. Non-blocking nudge. |
| `brainstorm_router.py` | `UserPromptSubmit` | On a design / multi-option prompt, nudges to explore >= 2 options + cite before committing. Trigger phrases live in `triggers.json`. |

## Testing an example

Each module's docstring has a paste-able `Test:` line. Run it from THIS directory (so `PYTHONPATH=.`
puts the examples on the import path); empty output means the hook decided not to act:

```sh
printf '{"tool_name":"Write","tool_input":{"file_path":"x.md","content":"a \u2014 b"}}' \
  | PYTHONPATH=. python3 -m artifact_guard
```

(`\u2014` is a JSON-escaped em-dash, so this README stays pure ASCII while still exercising the guard.)

## Wiring (one entry per hook in your `settings.json`)

COPY these files into your project first -- `.claude/hooks/examples/` is the path the snippets below
assume. A project `settings.json` is not loaded by the plugin loader, so `$CLAUDE_PLUGIN_ROOT` is
UNSET there and the wiring silently resolves to nothing (`No module named artifact_guard`, exit 0 --
a hook that does not run looks exactly like a hook that found nothing). Use `$CLAUDE_PROJECT_DIR`,
the documented project-root variable, per rule 7 of the authoring standard.

The `PYTHONPATH` prefix puts the directory on the import path (so `import utils` / `import models`
resolve) while cwd stays at the project root (so `in_project()` keeps working). See the authoring
standard for why `PYTHONPATH` and not a bare `-m`.

```jsonc
{
  "hooks": {
    "PostToolUse": [
      { "matcher": "Write|Edit", "hooks": [
        { "type": "command",
          "command": "PYTHONPATH=\"$CLAUDE_PROJECT_DIR/.claude/hooks/examples\" python3 -m artifact_guard" } ] }
    ],
    "PreToolUse": [
      { "matcher": "Write|Edit", "hooks": [
        { "type": "command",
          "command": "PYTHONPATH=\"$CLAUDE_PROJECT_DIR/.claude/hooks/examples\" python3 -m config_guard" } ] }
    ],
    "UserPromptSubmit": [
      { "hooks": [
        { "type": "command",
          "command": "PYTHONPATH=\"$CLAUDE_PROJECT_DIR/.claude/hooks/examples\" python3 -m brainstorm_router" } ] }
    ]
  }
}
```

If you copy the modules into a project instead of running them from the plugin, point `PYTHONPATH` at
wherever you placed them, e.g. `PYTHONPATH="$CLAUDE_PROJECT_DIR/.claude/hooks/examples"`.
