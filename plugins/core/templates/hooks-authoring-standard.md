# Hooks Authoring Standard

Every Claude Code hook in a project is a standalone, readable module under `.claude/hooks/src/`.
`.claude/settings.json` only wires an event to a module -- it never carries inline logic.

The goal: you can tell what a hook does, change it, and test it in seconds -- none of which is true for
a shell/python one-liner escaped inside JSON.

---

## 1. Layout

Hooks are grouped by DOMAIN (not by event), so the tree documents itself:

```
.claude/hooks/
  README.md              # this standard, or a project-local pointer to it
  src/
    models.py            # TypedDict shapes of the stdin payload (HookEvent, ToolInput, ...)
    utils.py             # shared plumbing: read_payload / emit_additional_context / run
    <domain>/
      __init__.py
      <hook>.py          # one hook module; docstring says which event it binds and what it decides
      triggers.json      # optional: data (phrases, prefixes) the hook reads -- edit data here, not code
    <other-domain>/
      __init__.py
      <hook>.py
```

- `models.py` / `utils.py` are shared so every hook looks the same and imports the same plumbing.
- A domain package (e.g. `security/`, `conventions/`, `session/`) holds the hooks for one concern.
- Data that a hook matches against (phrase lists, tool-name prefixes) lives in a sibling `triggers.json`,
  so tuning behavior is a data edit, not a code edit.

---

## 2. Rules

1. **One module per hook**, in a domain package under `src/`. Add an `__init__.py` to every package.
2. **Start with a module docstring:** which event it binds to, what it decides, why, and a one-line
   `Test:` invocation someone can paste to exercise it.
3. **Standard library only.** A hook runs on every matching event and must start instantly -- no
   third-party imports, no `uv run`, no venv startup cost.
4. **Read the payload from stdin, decide, and emit only if acting.** Use the shared `read_payload()` and
   emit helpers from `utils.py`; import payload shapes from `models.py`. A hook that decides not to act
   emits nothing.
5. **Run the entrypoint through a wrapper that swallows errors (exit 0).** A hook must never crash a
   tool call or spam stderr. A single `run(main)` in `utils.py` that catches everything and exits 0 is
   the pattern -- a broken hook degrades to a no-op, never to a blocked session.
6. **Keep it ASCII** per the file-artifact rule (`->` not smart arrows, `-` not em/en-dash, no section
   sign) -- hook output is injected into the agent's context as plain text.
7. **Wire it in `settings.json`** as:
   ```
   PYTHONPATH="$CLAUDE_PROJECT_DIR/.claude/hooks/src" python3 -m <package>.<module>
   ```
   The `PYTHONPATH` prefix puts `src/` on the import path (so `import utils` / `import models` resolve)
   while cwd stays at the project root (so any cwd-relative check the hook does keeps working).
   `$CLAUDE_PROJECT_DIR` is the documented project-root variable, so the hook is cwd-independent.
8. **Commit the modules.** Hooks do not fire in a fresh clone (or for a subagent) if the files are
   missing -- an uncommitted hook silently does nothing for anyone else.

---

## 3. Why `PYTHONPATH` (and not a bare `-m`)

`python3 -m a.b.c` resolves `a.b.c` as a dotted MODULE NAME against `sys.path`, never as a filesystem
path. From the project root the package lives under `.claude/hooks/src/`, and `.claude` is not a legal
identifier in a dotted name, so it cannot be addressed by `-m` directly. Putting `src/` on `PYTHONPATH`
is the clean fix and keeps cwd at the project root (a `cd .../src` would work too but then breaks any
cwd-relative check the hook makes). `uv run -m` has the same `sys.path` semantics and adds venv startup
cost, so it is not used.

---

## 4. Editing hooks safely (the in-session gotcha)

`settings.json` hooks are re-read live during a session. A `PreToolUse` hook that exits non-zero with
code 2 **blocks** the matched tool, so a broken command (e.g. pointing at a module you just deleted or
renamed) will block your own `Read` / `Bash` / `Glob` mid-session.

When relocating or renaming a hook module, **repoint `settings.json` first, then move/delete the old
file** -- never the reverse. `Edit` is not matched by tool-gating hooks, so you can always fix
`settings.json` with `Edit` even if `Read` / `Bash` are currently blocked.

---

## 5. Testing a hook

Run the module exactly as `settings.json` does (from the project root) and check stdout -- empty output
means the hook decided not to act:

```sh
echo '{"tool_input":{"command":"..."}}' | PYTHONPATH=.claude/hooks/src python3 -m <package>.<module>
```

Feed the module a payload that should trigger it and one that should not; assert it emits on the first
and stays silent on the second. A hook with a `triggers.json` is tested by editing the data and
re-running -- no code change needed.

---

## 6. Event reference

The common events and what a hook on each is for:

| Event | Fires | Typical hook |
|---|---|---|
| `SessionStart` | session begins / resumes | inject baseline reminders or project context via `additionalContext` |
| `UserPromptSubmit` | user sends a prompt | nudge a workflow (e.g. brainstorm an option space) before the agent acts |
| `PreToolUse` | before a matched tool runs | guard: warn or block (exit 2) on a risky action -- secret write, config weakening |
| `PostToolUse` | after a matched tool runs | lint just-written output (unicode, hard-wrap), suggest a follow-up |
| `Stop` | the agent finishes a turn | end-of-turn checks / reminders (e.g. the drift-log nudge) |

Only `PreToolUse` can BLOCK (exit 2). Every other event's hook is advisory -- it emits context or a
reminder and must exit 0.

## 7. Runnable examples

`plugins/core/hooks/examples/` ships copyable, genericized starters that conform to this standard: a shared `utils.py` + `models.py` skeleton (the `run(main)` error-swallow, `read_payload`, `emit_additional_context` plumbing) plus three example guards -- `artifact_guard.py` (PostToolUse, ASCII / hard-wrap lint), `config_guard.py` (PreToolUse, hardcoded-secret / weakened-guardrail warn), and `brainstorm_router.py` + `triggers.json` (UserPromptSubmit, design-prompt nudge showing the data-not-code trigger pattern). They are EXAMPLES -- not wired into `hooks.json`, so they never auto-run; copy the ones you want into a project's `.claude/hooks/src/` and wire them in `settings.json`. Per-hook wiring snippets are in `examples/README.md`.
