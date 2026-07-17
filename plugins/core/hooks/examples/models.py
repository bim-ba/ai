"""Typed shapes for the hook event payload (see README.md in this directory).

These document - and let editors check - what a hook actually receives on stdin, instead of every hook re-discovering the dict shape by hand.
total=False because Claude Code only sends the fields relevant to the firing tool/event.
"""
from __future__ import annotations

from typing import TypedDict


class ToolInput(TypedDict, total=False):
    """The tool's arguments; which keys are present depends on the tool."""

    command: str     # Bash
    file_path: str   # Read / Edit / Write
    pattern: str     # Glob / Grep
    path: str        # Glob / Grep search root
    content: str     # Write
    new_string: str  # Edit
    old_string: str  # Edit


class HookEvent(TypedDict, total=False):
    """The JSON object Claude Code sends to a hook on stdin."""

    hook_event_name: str
    tool_name: str
    tool_input: ToolInput
    cwd: str
    transcript_path: str  # Stop / SubagentStop / SessionStart
    source: str           # SessionStart: startup / resume / clear / compact
    prompt: str           # UserPromptSubmit
