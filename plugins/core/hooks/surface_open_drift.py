"""SessionStart hook: surface the project's unresolved drift-log entries into session context.

Binds to:  SessionStart (a session begins or resumes; also every subagent start).
Decides:   GATED. Emit only when `<project>/.claude/drift-log/open/` holds at least one entry;
           stay silent otherwise (the common case). This is the carve-out's opposite of the
           behaviour-protocol hook beside it: that one is unconditional baseline, this one is a
           conditional nudge and MUST degrade to silence when there is nothing to surface.
Channel:   `hookSpecificOutput.additionalContext` on stdout, exit 0 -- the field that reaches the
           model on SessionStart (plain stdout on exit 0 also reaches it on this event, but the
           documented, harness-labelled field is the one to use).
Project:   resolved from the payload's `cwd`, then `$CLAUDE_PROJECT_DIR`, then the process cwd.
           A PLUGIN-shipped hook cannot resolve project state through `__file__` (that points into
           the version-keyed plugin cache, not the project), so it reads the launch cwd instead.

Why this hook exists: open drift entries are lessons a repo has already paid for but not yet
promoted into an auto-firing rule, so nothing surfaces them -- an agent must voluntarily grep a
directory it has no specific prompt to open. In this project that omission recurred across three
consecutive sessions (see `.claude/drift-log/open/2026-07-22-fanout-drift-recurred-third-time-*`):
each fanned out subagents while the very lesson forbidding un-guarded fan-out sat unread on disk.
A rule telling the agent to "read open/" is the manual fix that already failed three times; making
the entries appear in context on their own is the structural fix that does not depend on recall.

Deviates from nothing in the authoring standard: this is a textbook GATED hook (rule 4) -- read
the payload, decide, emit only if acting -- with the standard error-swallowing entrypoint (rule 5)
degrading to silence, which is correct here because the payload is a nudge, not baseline rules.

Kill-criterion:
    Delete this hook if `.claude/drift-log/open/` stops being where this project tracks open drift
    (the loader gains a native open-entry surface, or the drift workflow moves), or if two
    consecutive months pass in which it fires and no open entry is ever read or closed in response
    -- a surfacer nobody acts on is a tax, not a gate. Not: "it fired and open/ was empty" -- an
    empty open/ makes it silent by construction, which is the design, not a failure.

Test:
    mkdir -p /tmp/dl/.claude/drift-log/open && printf 'priority: HIGH\n## What diverged\nx\n' > /tmp/dl/.claude/drift-log/open/2026-01-01-demo.md
    echo '{"cwd": "/tmp/dl"}' | uv run --no-project python plugins/core/hooks/surface_open_drift.py
    # -> one JSON line naming 2026-01-01-demo.md; with an empty or absent open/ the output is ""
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

MAX_ENTRIES = 15  # cap the list so additionalContext stays well under the 10,000-char limit
MAX_EXCERPT = 160  # per-entry excerpt length
PRIORITY_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def project_root(payload: dict) -> Path:
    """Best-effort project directory: payload `cwd`, then $CLAUDE_PROJECT_DIR, then process cwd."""
    for candidate in (payload.get("cwd"), os.environ.get("CLAUDE_PROJECT_DIR")):
        if candidate:
            return Path(candidate)
    return Path.cwd()


def _priority(text: str) -> str:
    match = re.search(r"^priority:\s*(\w+)", text, re.MULTILINE)
    return match.group(1).upper() if match else "?"


def _diverged_excerpt(text: str) -> str:
    """First non-empty line of the `## What diverged` section, trimmed to MAX_EXCERPT."""
    after = text.split("## What diverged", 1)
    if len(after) < 2:
        return ""
    for line in after[1].splitlines():
        line = line.strip()
        if line:
            return line[:MAX_EXCERPT]
    return ""


def collect(open_dir: Path) -> list[tuple[str, str, str]]:
    """Return (priority, filename, excerpt) for every open entry, HIGH first then by name."""
    entries = []
    for path in open_dir.glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        entries.append((_priority(text), path.name, _diverged_excerpt(text)))
    entries.sort(key=lambda e: (PRIORITY_RANK.get(e[0], 3), e[1]))
    return entries


def render(entries: list[tuple[str, str, str]]) -> str:
    """Build the additionalContext body. Assumes `entries` is non-empty."""
    lines = [
        "[ai/core] This project has {n} unresolved drift-log {noun} under "
        ".claude/drift-log/open/. Each is a lesson this repo already paid for but has not yet "
        "promoted into an auto-firing rule. READ them before your first dispatch, edit, or plan "
        "this session, then apply or close them (core:reviewing-drift-logs).".format(
            n=len(entries), noun="entry" if len(entries) == 1 else "entries"
        ),
        "",
    ]
    for priority, name, excerpt in entries[:MAX_ENTRIES]:
        suffix = " -- " + excerpt if excerpt else ""
        lines.append("- [{p}] {name}{suffix}".format(p=priority, name=name, suffix=suffix))
    if len(entries) > MAX_ENTRIES:
        lines.append("- ... and {} more in open/.".format(len(entries) - MAX_ENTRIES))
    return "\n".join(lines)


def read_payload() -> dict:
    """Return the SessionStart JSON from stdin, or {} when it is absent or malformed."""
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def main() -> None:
    """Emit open drift entries as SessionStart additionalContext, or nothing when there are none."""
    open_dir = project_root(read_payload()) / ".claude" / "drift-log" / "open"
    if not open_dir.is_dir():
        return
    entries = collect(open_dir)
    if not entries:
        return
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": render(entries),
                }
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # a broken hook degrades to a no-op, never to a blocked session
