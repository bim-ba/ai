---
name: thinning-agent-instructions
type: skill
category: workflow
description: Use when a project CLAUDE.md is bloated, predates the canonical skeleton, or duplicates the shared home layers (the ai/core behaviour-protocol and the personal ~/.claude/CLAUDE.md) - thins it to the 10-section skeleton by removing content the home layers already provide while preserving every project-specific fact. The FIX companion to reviewing-agent-instructions (which only audits). Do NOT use it to change project rules or to edit a CLAUDE.md that is already thin and conformant.
---

# Thinning Agent Instructions

Bring a project `CLAUDE.md` into the canonical 10-section skeleton by removing content the shared home layers already provide, keeping ONLY project-specific facts. This is the FIX companion to `reviewing-agent-instructions` (which audits and reports but never edits).

## Purpose

### What this skill enables

A project `CLAUDE.md` is paid on every single turn's context. Anything it repeats from a shared always-on layer is pure overhead. This skill relocates that generic content to where it belongs (or deletes it because the layer already carries it) and reshapes what remains into the canonical skeleton - so the file holds only what is TRUE HERE and would surprise an agent applying defaults.

### When to use it

- A `CLAUDE.md` carries a generic "Agent Behaviour Protocol", "Communication Style"/voice spec, or generic git/secrets/tooling/orchestration rules that duplicate the home layers.
- A `CLAUDE.md` predates the 10-section skeleton (`templates/CLAUDE.md.tmpl`) and needs restructuring.
- Onboarding an existing project to the standard, or acting on a `reviewing-agent-instructions` audit that flagged oversize/duplication.

### When NOT to use it

- The `CLAUDE.md` is already thin and skeleton-conformant - use `Edit` for a small tweak.
- To CHANGE project rules - this preserves them; it only relocates the generic ones.
- On project content / research / docs - those are not the agent-instruction surface.

## Pre-checks

1. **Know the home layers** (so you know what is safe to remove because it is already provided):
   - `ai/core` behaviour-protocol (`plugins/core/hooks/behaviour-protocol.md`) - generic agent discipline (research / validate / challenge / check-in / verification / lethal-trifecta / orchestration guards), injected every session.
   - The personal `~/.claude/CLAUDE.md` - the user's voice, tooling, git, research, and secrets defaults.
   - The canonical skeleton `plugins/core/templates/CLAUDE.md.tmpl` - the target 10-section shape.
   Read/ skim these first; you are removing what they already cover.
2. **Measure the baseline** and record it: `wc -l CLAUDE.md`, `wc -c CLAUDE.md`, and `uvx count-tokens CLAUDE.md`. You will report the delta.
3. **Read the WHOLE current `CLAUDE.md`.** You cannot classify content you have not read.
4. **Check the repo topology.** `git worktree list` and `git -C <repo> rev-parse --git-common-dir` - see the Guardrails note on worktrees before editing.

## Workflow

### Step 1 - Classify every section and bullet

Sort the current content into two buckets:

- **Generic (remove)** - duplicates a home layer: an "Agent Behaviour Protocol"/rules-of-engagement section, a "Communication Style"/voice spec, generic git-hygiene / secrets / tooling / "research before acting" / orchestration guidance.
- **Project-specific (keep)** - TRUE HERE and not derivable from defaults: the stack, the source-of-truth ladder, project rule deltas (naming, migration mechanics, git-hygiene specifics like "not a monorepo, stage explicit paths"), the repository map, docs map, skills registry + task router, project CLI/MCP gotchas, directory/file conventions, project extras.

### Step 2 - Extract project-specific facts trapped inside generic sections

A generic section often embeds a project-specific nugget (e.g. an asymmetric source-of-truth rule living inside "Agent Behaviour Protocol", or a "never put a secret in a ClickHouse query" rule inside a generic secrets paragraph). EXTRACT each such fact into its proper skeleton section BEFORE deleting the generic wrapper. Losing one is the primary failure mode of this skill.

### Step 3 - Rebuild against the skeleton

Reshape the kept content into `templates/CLAUDE.md.tmpl`'s order:

1. **Header** - a one-line project description + the "baseline injected by ai/core; personal defaults from the user layer; this file holds ONLY project-specific facts" note.
2. Then only the sections that have project content: Stack & layout / Source-of-truth / **Project-specific rules** (mandatory) / Repository Map / Documentation Map / Skills Registry + task router / CLI Tools & MCP / Directory & File Conventions / project extras.

Delete any skeleton section with no project content. Cross-link source-of-truth files instead of copying them; prefer tables over prose; keep it ASCII (`->` not arrows, `-` not em/en-dash).

### Step 4 - Handle genuine overrides explicitly

If a project rule genuinely CONFLICTS with a home-layer default (not merely duplicates it), keep it and state that it overrides (e.g. "do NOT append a Co-Authored-By trailer here - overrides the personal-layer default"). Only remove content that is redundant, never content that contradicts a default.

## Post-checks

1. **Coverage (the critical check).** Enumerate every project-specific fact/link/identifier in the OLD file and confirm each appears in the new one. Nothing project-specific may be lost - diff the old file's project bullets against the new. If in doubt, it was not safe to remove.
2. **Re-measure** lines / chars / tokens and report the reduction delta.
3. **Skeleton conformance.** Sections are a subset of the canonical order; Header and Project-specific rules are present; no empty placeholder sections remain.
4. **No residual generic content** that a home layer already provides.

## Guardrails

- **Never drop a project-specific fact.** Thinning removes DUPLICATION, not project knowledge. When unsure whether a bullet is generic or project-specific, KEEP it.
- **Do not invent content** to fill a skeleton section - delete the empty section instead.
- **Preserve exact identifiers, paths, and links** when relocating a fact; never rename while moving.
- **This is a large diff.** Commit a clean baseline first, present before/after for review, and commit only on the user's approval (per the check-in rule).
- **Worktrees / multiple branches of ONE repo:** if the project is checked out as several `git worktree`s on diverged branches, thin ONCE on the canonical branch, merge it to the mainline, and let the other branches inherit via merge/rebase. Do NOT hand-thin each worktree - that creates three divergent `CLAUDE.md`s and guarantees merge conflicts. Verify with `git worktree list` in Pre-checks.

## Artifact Map

| Artifact | Output path | Notes |
|---|---|---|
| Thinned `CLAUDE.md` | `<project-root>/CLAUDE.md` | in-place rewrite; the old content is recoverable via git |
| Before/after measurement | reported in the check-in (not a file) | lines / chars / tokens delta |

## References Guide

- `plugins/core/templates/CLAUDE.md.tmpl` - the canonical 10-section skeleton (the target shape).
- `plugins/core/hooks/behaviour-protocol.md` - what the generic layer already covers (so you know what is safe to remove).
- `reviewing-agent-instructions` - run FIRST for the audit that flags oversize / duplication / dead refs; this skill acts on those findings.

## Related work

Re-homing a project's personal agent MEMORY entries into versioned surfaces (CLAUDE.md / skills / docs) is the sibling of this task - same principle ("knowledge lives in versioned surfaces, not local memory"), different source. Handle it separately; this skill covers the `CLAUDE.md` surface only.
