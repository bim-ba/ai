"""UserPromptSubmit hook -> nudge to brainstorm the option space before committing to one approach.

Fires when the submitted prompt looks like a DESIGN / multi-option decision (explicit "which approach",
"how should we", "compare", "pros and cons", "architecture for" intent - a deliberately high-precision
phrase set in triggers.json) and is a real task (not a one-line ack). Emits a non-blocking nudge to
explore >= 2 options and cite sources before proposing one - operationalizing the "research before
acting" habit and the brainstorming-before-implementation practice (e.g. the superpowers:brainstorming
skill), which exist but are not reliably triggered.

This is the LOWEST-precision hook in the set by nature (intent is semantic, not deterministic): it is
tuned conservative - it catches explicit design asks and accepts that an implicit one is missed. Tune
via triggers.json (phrases + min_len), not in code, so this source stays pure ASCII. The shipped phrase
list is GENERIC placeholder examples - replace it with your project's own trigger phrases. Non-blocking.

Test (run from this examples directory):
    printf '{"prompt":"How should we design this loader - which approach to pick and the pros and cons?"}' | PYTHONPATH=. python3 -m brainstorm_router
    printf '{"prompt":"ok, commit"}' | PYTHONPATH=. python3 -m brainstorm_router   # no output
"""
from __future__ import annotations

from utils import emit_additional_context, load_sidecar_json, read_payload, run

_T = load_sidecar_json(__file__)
DESIGN_SIGNALS = tuple(str(s).lower() for s in _T.get("design_signals", []))
_MIN_LEN = int(_T.get("min_len", 30))

NUDGE = (
    "This prompt reads as a design / multi-option decision. Before committing to one approach: explore "
    "the option space (>= 2 candidate approaches) and cite sources - do not race to the first solution. "
    "A 'usually done this way' reflex without a citation is a guess. If this is a feature/design task, "
    "load a brainstorming skill (e.g. superpowers:brainstorming) first."
)


def main() -> None:
    prompt = str(read_payload().get("prompt", ""))
    if len(prompt.strip()) < _MIN_LEN:
        return
    low = prompt.lower()
    if not any(sig in low for sig in DESIGN_SIGNALS):
        return
    emit_additional_context("UserPromptSubmit", NUDGE)


if __name__ == "__main__":
    run(main)
