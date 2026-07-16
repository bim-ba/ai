"""Shared helpers for the example hooks (see README.md in this directory + the hooks authoring standard).

Every hook reads the event payload as JSON on stdin and, when it decides to act, prints a directive to stdout and exits 0.
These helpers keep that plumbing in one place so each hook file is about WHAT it decides, not HOW it talks to the harness.
Standard library only - hooks run on every matching tool call and must start instantly.
"""
from __future__ import annotations

import json
import os
import sys

from models import HookEvent, ToolInput


def read_payload() -> HookEvent:
    """Return the hook event JSON from stdin, or {} if it is absent or malformed."""
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def tool_input(payload: HookEvent) -> ToolInput:
    """Return the tool_input sub-object, falling back to the payload itself; never a non-dict."""
    value = payload.get("tool_input", payload)
    return value if isinstance(value, dict) else {}


def written_text(tool_name: str, ti: ToolInput) -> str:
    """The text a Write/Edit is about to persist: Write.content or Edit.new_string, else ''."""
    if tool_name == "Write":
        return str(ti.get("content") or "")
    if tool_name == "Edit":
        return str(ti.get("new_string") or "")
    return ""


def in_project(file_path: str) -> bool:
    """True when file_path resolves inside the current project tree (cwd)."""
    root = os.path.abspath(os.getcwd())
    target = os.path.abspath(file_path)
    return target == root or target.startswith(root + os.sep)


def load_sidecar_json(module_file: str, name: str = "triggers.json") -> dict:
    """Load a JSON data file next to the caller module (pass __file__), or {} if absent/malformed."""
    path = os.path.join(os.path.dirname(module_file), name)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def emit_additional_context(event: str, context: str) -> None:
    """Inject extra context for an event by printing the harness directive (exit 0 follows)."""
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}))


def run(main) -> None:
    """Run a hook entrypoint, swallowing any error so the hook always exits 0.

    Hooks fire on every matching tool call; a crash must never block the tool or spam stderr.
    A broken hook must degrade to a no-op, never to a blocked session.
    """
    try:
        main()
    except Exception:
        pass
