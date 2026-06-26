---
name: drift-log-triggers
description: The 8 conditions that require a drift-log entry, plus the do-NOT-log exclusion list.
---

# Drift Log Triggers

## When to log

Log an entry whenever any of these occur:

1. **Contradiction with official rules**: the user gives an inline instruction that conflicts with a rule in `CLAUDE.md` or in a skill, and the inline instruction is followed.
2. **Refactor of codified patterns**: the user proposes or accepts a refactored solution to something that is already prescribed (e.g., a different file layout, naming convention, error-handling approach, testing pattern).
3. **New concept or rule introduced**: the user introduces a concept, constraint, or convention that has no equivalent in the official files but is treated as authoritative for the rest of the session.
4. **Self-discovered improvement**: you find an approach that works better than what is prescribed, and the user accepts it (explicitly or by not objecting after you flag it).
5. **Repeated correction**: the user corrects the same behavior twice or more within a session — a strong signal the official instructions are missing, ambiguous, or wrong. Mark these `HIGH`.
6. **Skill not triggered when it should have been**: the user manually invokes a behavior a skill should have covered, or you realize mid-task an existing skill applies but was missed.
7. **Skill triggered when it should not have been**: a skill activated for a task it does not fit, and was ignored or overridden.
8. **Ambiguity resolved in practice**: the official instructions left a decision underspecified, and the session resolved it in a way that should become the default.

## Do NOT log

- One-off project-specific decisions with no general applicability.
- Pure user preferences for a single file (e.g., "rename this variable").
- Mistakes you made that the user corrected, unless the correction reveals a missing rule.

## Edge-case guidance

When uncertain whether something qualifies, err on the side of logging — false positives are cheap, missed insights are expensive.

Trigger 5 (Repeated correction) is the strongest signal: it directly indicates missing, ambiguous, or wrong official instructions. Always mark these `HIGH` priority.

Triggers 6 and 7 (skill mis-fire in either direction) both indicate a gap between the skill's trigger conditions and real-world usage patterns.
