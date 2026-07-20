"""Stop hook: make the agent close every turn with an explicit drift-log verdict.

Binds to:  Stop (the agent finished a turn).
Decides:   remind the agent to close the turn with a drift-log verdict.
Channel:   `hookSpecificOutput.additionalContext` on stdout, exit 0. Plain stdout on exit 0
           reaches the model only on UserPromptSubmit / UserPromptExpansion / SessionStart, so a
           `Stop` hook that echoes a reminder is a silent no-op - the bug this file replaces.

Channels considered and rejected (behaviour-protocol.md:17 requires naming them):
    `{"decision": "block"}`  - reaches the model too, and continues the turn under the SAME
        loop protections, so this is not a force-versus-suggest choice. The difference is that
        block surfaces as a hook ERROR notification while additionalContext is labelled
        `Stop hook feedback`. A routine per-turn convention is not an error; on a 40-turn
        session blocking would raise 40 error notifications for nothing going wrong.
    exit 2 with stderr - same category error, plus it spams stderr.
    A gate on `last_assistant_message` (in the Stop payload; the docs recommend it over the
        transcript file, which can lag) - a real stateless CONTENT signal, and the right shape if
        this reminder ever needs narrowing.
        Not used yet: any keyword list would be a guess about which turns carry drift, and a
        wrong guess silently suppresses the reminder. Revisit with evidence from actual entries.

Why no gate:
    An earlier draft gated on "did the working tree change since this session's last ask",
    keyed by a marker file under /tmp. That was wrong twice over. First, the hook's own verdict
    tells the agent to WRITE a drift entry, so the hook changed the very thing it measured - a
    feedback loop that blocked every turn after the first, including pure conversation. Second,
    all 8 drift triggers (core:creating-drift-logs, rules/01-triggers.md) are CONVERSATIONAL:
    a correction given twice, a convention introduced, a skill that misfired. Trigger 5, which
    that skill calls its strongest signal, leaves no trace in a diff at all. A tree-delta gate
    therefore filtered out precisely the turns worth asking about, while firing on build
    artifacts the same skill's "Do NOT log" list excludes. No state beats wrong state: the
    verdict costs one short line when nothing qualifies.

Once per turn:
    Emits only when the payload says `stop_hook_active` is explicitly false, so a turn that was
    already reminded is not reminded again. An absent field - an older CLI that does not send it
    - yields silence: degrading to a no-op on an unknown harness is the correct failure
    direction for a hook.

Kill-criterion:
    Delete this hook if two consecutive months pass with no `.claude/drift-log/open/` entry
    created in response to it, or if "drift-log delta: none" becomes a reflex that never
    produces an entry. A reminder nobody acts on is a tax, not a gate.

Test:
    echo '{"stop_hook_active": false}' | python3 drift_log_check.py   # -> one JSON line
    echo '{"stop_hook_active": true}'  | python3 drift_log_check.py   # -> silent
    echo '{}'                          | python3 drift_log_check.py   # -> silent (unknown harness)
"""

from __future__ import annotations

import json
import sys

REMINDER = (
    "[ai/core] Standing project convention: a turn closes with a drift-log verdict. "
    "Check this turn against the 8 triggers in the core:creating-drift-logs skill "
    "(an instruction contradicted and followed anyway, a codified pattern refactored, a new "
    "convention introduced, a better approach accepted, the same correction given twice, a "
    "skill that should have fired and did not, a skill that fired and should not have, an "
    "ambiguity resolved in practice). If any fired, write the entry that skill prescribes under "
    ".claude/drift-log/open/. If none fired, say exactly: drift-log delta: none."
)


def read_payload() -> dict | None:
    """Return the Stop event JSON from stdin, or None when it is absent or malformed.

    None is distinct from an empty payload on purpose: a hook that cannot read its input must
    stay silent rather than fall back to defaults and act on a turn it knows nothing about.
    """
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def main() -> None:
    """Remind once per turn to close with a drift-log verdict."""
    payload = read_payload()
    if payload is None:
        return  # unreadable input: stay out of the way
    if payload.get("stop_hook_active") is not False:
        return  # already reminded this turn, or a harness that does not report it
    print(
        json.dumps(
            {"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": REMINDER}}
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # a broken hook degrades to a no-op, never to a blocked session
