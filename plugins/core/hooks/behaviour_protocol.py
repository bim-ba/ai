"""SessionStart hook: inject the ai/core Agent Behaviour Protocol as this session's baseline context.

Binds to:  SessionStart (a session begins or resumes; also every subagent start).
Decides:   nothing - this is unconditional baseline context, not a gated nudge, so it always emits.
Channel:   `hookSpecificOutput.additionalContext` on stdout, exit 0. Plain stdout on exit 0 does reach
           the model on SessionStart, but `additionalContext` is the documented field and is what the
           harness labels; do not "simplify" this to a bare `print(text)`.
Source:    `behaviour-protocol.md` beside this file, resolved through `__file__` rather than an argument
           from the manifest - the hook then works from any cwd and its `Test:` line below runs with no
           arguments, which is what makes it testable at all.

Why this file exists: the wiring used to be an inline `python -c '...'` one-liner inside `hooks.json`,
which the authoring standard forbids (see the intro to `templates/hooks-authoring-standard.md`) and
which nothing could test.

Failure behaviour deviates from rule 5, deliberately:
    Every other hook here degrades to SILENCE on error, which is right when the payload is one nudge.
    It is wrong here. This hook carries the ENTIRE baseline protocol, so silence means every rule is
    missing from the session and neither the agent nor the user can tell - the same shape as the
    `echo`-based Stop hook that was a no-op for 24 days. So a read failure emits a short, loud notice
    instead of nothing. Still exit 0, still never blocks: it degrades to a WARNING, not to a no-op.
    The bare `except Exception: pass` below stays as the last-resort guard for anything unexpected.

Kill-criterion:
    Delete this hook if the plugin loader ever gains a native always-on instruction channel (a shipped
    file injected without a hook), which would make it redundant. Not: "if it seems noisy" - noise is
    the point.

Test:
    echo '{}' | python3 behaviour_protocol.py
    # -> one JSON line whose additionalContext equals behaviour-protocol.md byte for byte
"""

from __future__ import annotations

import json
from pathlib import Path

PROTOCOL = Path(__file__).resolve().with_name("behaviour-protocol.md")

# Emitted instead of the protocol when the file cannot be read. Deliberately names the path and the
# reason: an agent that receives this knows its baseline rules are absent, which silence never conveys.
FALLBACK = (
    "[ai/core] WARNING: the agent behaviour protocol could not be loaded from {path} ({error}). "
    "This session is running WITHOUT its baseline conventions. Treat that as a defect to report, "
    "not as permission to proceed unguided."
)


def load_protocol() -> str:
    """Return the protocol text, or a warning naming the failure. Never raises, never returns ''.

    >>> load_protocol().startswith("#") or "WARNING" in load_protocol()
    True
    """
    try:
        return PROTOCOL.read_text(encoding="utf-8")
    except Exception as error:  # unreadable, missing, or undecodable - all the same to the caller
        return FALLBACK.format(path=PROTOCOL, error=type(error).__name__)


def main() -> None:
    """Emit the protocol as SessionStart additionalContext."""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": load_protocol(),
                }
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # a broken hook degrades to a no-op, never to a blocked session
