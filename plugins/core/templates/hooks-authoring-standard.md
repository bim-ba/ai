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
   third-party imports, no venv startup cost. The dependency rule is non-negotiable; the launcher is
   a tradeoff. This plugin's own hooks run `uv run --no-project python "${CLAUDE_PLUGIN_ROOT}/hooks/<module>.py"`,
   which keeps the interpreter uniform across machines; a project-local `.claude/hooks/src/` module
   uses bare `python3` where per-event startup cost dominates. `--script` is for a module carrying a
   PEP-723 header and is unnecessary for a stdlib-only hook. Never `uv run` WITHOUT `--no-project`:
   that resolves the project's environment and can install packages mid-session.
4. **Read the payload from stdin, decide, and emit only if acting.** Use the shared `read_payload()` and
   emit helpers from `utils.py`; import payload shapes from `models.py`. A hook that decides not to act
   emits nothing.
5. **Run the entrypoint through a wrapper that swallows errors (exit 0).** A hook must never crash a
   tool call or spam stderr. A single `run(main)` in `utils.py` that catches everything and exits 0 is
   the pattern -- a broken hook degrades to a no-op, never to a blocked session.
6. **Keep it ASCII** per the file-artifact rule (`->` not smart arrows, `-` not em/en-dash, no section
   sign) -- hook output is injected into the agent's context as plain text.
7. **Wire it where the hook LIVES, and the form follows from that.** A PROJECT hook goes in
   `settings.json`:
   ```
   PYTHONPATH="$CLAUDE_PROJECT_DIR/.claude/hooks/src" python3 -m <package>.<module>
   ```
   The `PYTHONPATH` prefix puts `src/` on the import path (so `import utils` / `import models` resolve)
   while cwd stays at the project root (so any cwd-relative check the hook does keeps working).
   `$CLAUDE_PROJECT_DIR` is the documented project-root variable, so the hook is cwd-independent.
   A PLUGIN-shipped hook goes in `hooks.json` and addresses its file directly under
   `${CLAUDE_PLUGIN_ROOT}` -- there is no project `src/` to put on the path, and the plugin must run
   identically in a project that has no `.claude/hooks/` at all. This plugin's own hooks take that
   second form; see rule 3 for the launcher tradeoff.
8. **Commit the modules.** Hooks do not fire in a fresh clone (or for a subagent) if the files are
   missing -- an uncommitted hook silently does nothing for anyone else.

---

## 3. Why `PYTHONPATH` (and not a bare `-m`)

`python3 -m a.b.c` resolves `a.b.c` as a dotted MODULE NAME against `sys.path`, never as a filesystem
path. From the project root the package lives under `.claude/hooks/src/`, and `.claude` is not a legal
identifier in a dotted name, so it cannot be addressed by `-m` directly. Putting `src/` on `PYTHONPATH`
is the clean fix and keeps cwd at the project root (a `cd .../src` would work too but then breaks any
cwd-relative check the hook makes). `uv run -m` has the same `sys.path` semantics and adds venv startup
cost, so a PROJECT hook does not use it -- there, per-event startup cost dominates and `python3` is
already the right interpreter. A PLUGIN-shipped hook makes the opposite trade (rule 3): it cannot
assume which `python3` a given machine has, so it pays the startup cost for a uniform interpreter.
Same rule, different constraint -- not an exception.

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

Blocking is per-event, not exclusive to `PreToolUse`, and what "block" MEANS differs per event:
`PreToolUse` prevents the tool from running; `UserPromptSubmit` discards the prompt; `Stop` and
`SubagentStop` refuse to let the turn end and hand the reason back as work to do. `PostToolUse`
runs after the tool has already executed, so it can only feed the model - it cannot undo the call.
Consult the current docs before assuming any of this (https://code.claude.com/docs/en/hooks).

Three channels reach the model, and plain stdout on exit 0 is NOT one of them for most events:

| Channel | How | Reaches the model on |
|---|---|---|
| stdout as context | print the text, exit 0 | `UserPromptSubmit`, `UserPromptExpansion`, `SessionStart` ONLY |
| JSON on stdout, exit 0 | `{"decision":"block","reason":"..."}` or `{"hookSpecificOutput":{"hookEventName":"<Event>","additionalContext":"..."}}` | every event that supports the field |
| stderr, exit 2 | write to stderr, exit 2 | every blocking event |

A `Stop` hook that `echo`s a reminder and exits 0 is a SILENT NO-OP: the text goes to the debug log,
never to the model. This exact bug shipped here and went unnoticed for 24 days -- always verify a
new hook end-to-end against a throwaway project before trusting it.

Choosing between the two JSON channels on `Stop` is a question about the USER, not the model:

| | `decision: block` | `additionalContext` |
|---|---|---|
| Reaches the model | yes, as `reason` | yes, wrapped in a system reminder |
| Keeps the conversation going | yes | yes - identically |
| Loop protections | `stop_hook_active` + the 8-consecutive-continuation cap | the same two |
| Shown to the user | as a hook ERROR notification | labelled `Stop hook feedback` in the transcript, no error notification |
| Use for | a real failure the turn must not end on (build broken, guard tripped) | a standing convention, a status update, guidance the agent should weigh |

The two are NOT "force" versus "suggest" - both continue the turn under the same protections.
The only difference is how it is surfaced, so pick by whether the situation is an ERROR. A hook
that fires routinely and blocks paints an error notification every turn for something that is
not an error, and users learn to ignore notifications. Reserve blocking for actual failures.

`additionalContext` is capped at 10,000 characters, and when several hooks return one for the
same event the model receives all of them.

Guard either channel with the `stop_hook_active` payload field so it fires once per turn rather
than in a loop. Prefer the strict form `payload.get("stop_hook_active") is not False` over a
truthiness test: an older harness that omits the field then degrades to silence instead of
firing every time. The platform also caps consecutive blocks, but never rely on that as the
only brake.

The `Stop` payload also carries `last_assistant_message` - the final assistant text of the turn,
which the docs recommend over reading the transcript file (it may lag). That is the stateless
way to gate on what a turn actually CONTAINED. Reach for them before inventing a
marker file: a hook that keeps state about previous turns can change the thing it measures, and
one that writes that state to a predictable path in a shared temp directory is a symlink
truncation waiting to happen.

## 7. Runnable examples

`plugins/core/hooks/examples/` ships copyable, genericized starters that conform to this standard: a shared `utils.py` + `models.py` skeleton (the `run(main)` error-swallow, `read_payload`, `emit_additional_context` plumbing) plus three example guards -- `artifact_guard.py` (PostToolUse, ASCII / hard-wrap lint), `config_guard.py` (PreToolUse, hardcoded-secret / weakened-guardrail warn), and `brainstorm_router.py` + `triggers.json` (UserPromptSubmit, design-prompt nudge showing the data-not-code trigger pattern). They are EXAMPLES -- not wired into `hooks.json`, so they never auto-run; copy the ones you want into a project's `.claude/hooks/src/` and wire them in `settings.json`. Per-hook wiring snippets are in `examples/README.md`.
