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

Deviates from rule 4 (read the payload from stdin, emit only if acting), deliberately:
    This hook reads no stdin and always emits. There is nothing to decide - the baseline protocol is
    unconditional - so a payload gate would be decoration, and a hook that can decide NOT to emit is
    a hook that can lose the protocol for a reason nobody chose. See the always-emits paragraph in
    section 5 of the authoring standard for how such a hook is tested.

Deviates from rule 5 (degrade to a no-op), deliberately, and only so far:
    Every other hook here degrades to SILENCE on error, which is right when the payload is one nudge.
    It is wrong here. This hook carries the ENTIRE baseline protocol, so silence means every rule is
    missing from the session and neither the agent nor the user can tell - the same shape as the
    `echo`-based Stop hook that was a no-op for 24 days. So a failure to obtain the protocol emits a
    short, loud notice instead of nothing. Still exit 0, still never blocks: a WARNING, not a no-op.

    Scope of that guarantee, stated honestly: it holds only once execution reaches this file. Every
    failure EARLIER in the chain is still silent and nothing here can change that - `uv` missing from
    PATH, `CLAUDE_PLUGIN_ROOT` unset, no interpreter available, an inherited broken `VIRTUAL_ENV`, or
    the manifest's 10s timeout expiring. `README.md` already records the first of those ("Without
    `uv`, both `core` hooks are skipped ... the session still works, silently"). The `except
    Exception: pass` below is likewise a last-resort guard that can swallow the warning itself if
    `print` fails on a closed stdout. Loud where we control it; not a claim about the launcher.

Kill-criterion:
    Delete this hook if the plugin loader ever gains a native always-on instruction channel (a shipped
    file injected without a hook), which would make it redundant. Not: "if it seems noisy" - noise is
    the point.

Test:
    echo '{}' | uv run --no-project python plugins/core/hooks/behaviour_protocol.py
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

    An EMPTY read counts as a failure, not as an empty protocol. `read_text` succeeds on a zero-byte
    file, so a truncated cache write or a bad merge would otherwise emit "" - silently, which is the
    exact outcome this hook's whole design exists to prevent.

    >>> load_protocol().startswith("#") or "WARNING" in load_protocol()
    True
    """
    try:
        text = PROTOCOL.read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError("protocol file is empty")
        return text
    except Exception as error:  # unreadable, missing, undecodable, or empty - same to the caller
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
