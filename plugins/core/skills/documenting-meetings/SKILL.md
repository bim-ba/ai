---
name: documenting-meetings
description: Use when documenting a meeting from an SRT audio transcript — produces structured meeting notes with decisions, action items, and discussion summary
type: skill
category: workflow
---

# Skill: documenting-meetings

## Purpose

This skill transforms an SRT audio transcript into structured meeting notes with decisions, action items, and discussion summary.

- **Input:** `audio.srt` file — path supplied by the user
- **Output:** `summary.md` written to the output directory supplied by the user (default: `./meeting-notes/`)
- **When to use:** after any team meeting that was recorded and has a transcript
- **When NOT to use:** for meetings without a transcript (no audio.srt)

---

## Pre-checks

- Verify `audio.srt` exists at the path the user supplied
- Check for any supporting files in the same directory (screenshots, diagrams, linked files) — if present, review them for context before reading transcript
- If a team roster or speaker-login map is available (e.g. a team doc), load it to identify speakers by login
- Confirm meeting date and name from the path or user input

---

## Workflow

1. If a team roster exists, read it to map speaker logins to names and roles
2. Check the meeting directory for any supporting materials (screenshots, diagrams, linked files) — note them for use in verification
3. Read the full `audio.srt` transcript
4. Identify all speakers and their contributions
5. Extract: objective, decisions made, action items (with owner and deadline), key discussion points, hidden motivations, open issues, next steps
6. Verify technical claims: for any specific technical fact (field name, system behavior, numeric claim), check against supporting files if available; if not verifiable, mark with `⚠️ Requires verification`
7. Write `summary.md` to the output directory (default: `./meeting-notes/`; use path supplied by user if provided)
8. Re-read the summary and verify it captures all decisions — decisions are the most important section

**Decision points:**

- If transcript quality is poor (fragmented, lots of `[inaudible]`) → note this prominently in the summary header; process what is audible and mark gaps explicitly
- If a technical claim cannot be verified → mark with the warning tag, do not state as fact

---

## Subagent Delegation

For transcripts > ~50 KB (typically 90+ minute meetings), delegate the full workflow to a subagent to preserve orchestrator context. The subagent cannot write files directly (Write calls are blocked), so use this pattern:

**Orchestrator instructs subagent:**
> "Read the SRT transcript at `<path>`. Run the documenting-meetings workflow. Do NOT write any files. Instead, return: (1) the full markdown body of summary.md using the template, (2) a digest: count of decisions, count of action items, count of `⚠️ Requires verification` tags, and the last SRT timestamp."

**Orchestrator receives and verifies:**

1. Spot-check 2–3 factual claims from the digest against the transcript or supporting files
2. Write `summary.md` to the output directory using the returned body
3. Confirm digest counts match the written summary

**Never** have the subagent return only a digest — the full body must be returned inline for the orchestrator to write.

---

## Post-checks

- All decisions are listed (if truly none were made, state explicitly: "No decisions reached")
- All action items have an owner and a deadline (or "No deadline set")
- Technical claims are either verified or marked with `⚠️`
- Summary reads as a standalone document — a reader who wasn't at the meeting understands what happened

---

## Guardrails

- Do NOT state unverified technical claims as facts
- Do NOT omit the "Decisions Made" section — if empty, write "No decisions reached in this meeting"
- Do NOT invent action items that weren't explicitly assigned
- "Hidden Motivations" is always labeled as interpretation, never as fact — use phrases like "may indicate", "likely reflects"
- Do NOT include raw transcript fragments — summarize and synthesize

---

## Artifact Map

| Artifact | Path | Notes |
|----------|------|-------|
| Meeting notes | `<output-dir>/summary.md` (default: `./meeting-notes/summary.md`) | Primary output; output-dir is supplied by user |

---

## References Guide

- Team roster (if available in the project) — maps speaker logins to names and roles; load before reading transcript
- Meeting template (if the project has one under `templates/meeting-notes.md`) — use this structure for all meetings; otherwise use the standard sections: Objective, Decisions Made, Action Items, Key Discussion Points, Open Issues, Next Steps
- Transcript processing rules (if the project has `rules/01-transcript-processing.md`) — how to handle SRT format, poor-quality audio, and technical verification
- Output standards (if the project has `rules/02-output-standards.md`) — required sections, action item format, tracker cross-linking
- For technical claims: check files in the meeting's supporting materials directory
