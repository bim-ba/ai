# Drift Log

Per-entry log of divergences between ad-hoc session behavior and codified instructions (`CLAUDE.md`, skills). Purpose: surface patterns where emergent conventions outperform what's codified, so official instructions can be improved.

`CLAUDE.md` § Session Drift Tracking carries the mandate; the triggers and process live here. See `_template.md` for the entry format.

> **Lightweight variant.** This repo runs the drift-log *concept* without the `go-task audit:*` Taskfile tooling. There is no automated index-sync or staleness check — the OPEN/APPLIED index below is maintained by hand. Keep it in lock-step with `open/` manually.

## When to log (triggers)

Log an entry whenever any of these occur:

1. **Contradiction with official rules**: the user gives an inline instruction that conflicts with a rule in `CLAUDE.md` or in a skill, and the inline instruction is followed.
2. **Refactor of codified patterns**: the user proposes or accepts a refactored solution to something that is already prescribed (e.g., a different file layout, naming convention, error-handling approach, testing pattern).
3. **New concept or rule introduced**: the user introduces a concept, constraint, or convention that has no equivalent in the official files but is treated as authoritative for the rest of the session.
4. **Self-discovered improvement**: you find an approach that works better than what is prescribed, and the user accepts it (explicitly or by not objecting after you flag it).
5. **Repeated correction**: the user corrects the same behavior twice or more within a session — a strong signal the official instructions are missing, ambiguous, or wrong. Mark these `HIGH`.
6. **Skill not triggered when it should have been**: the user manually invokes a behavior a skill should have covered, or you realize mid-task an existing skill applies but was missed.
7. **Skill triggered when it should not have been**: a skill activated for a task it does not fit, and was ignored or overridden.
8. **Ambiguity resolved in practice**: the official instructions left a decision underspecified, and the session resolved it in a way that should become the default.

Do NOT log:

- One-off project-specific decisions with no general applicability.
- Pure user preferences for a single file (e.g., "rename this variable").
- Mistakes you made that the user corrected, unless the correction reveals a missing rule.

When you log, mention it in chat in one line (`Logged drift: open/<file>.md`). If uncertain whether something qualifies, err on the side of logging — false positives are cheap, missed insights are expensive.

**One insight = one entry.** Split entries by *insight*, not by target-file or by the number of files a fix touches. If two observations share a root cause and would be resolved by the same edit, they are one entry.

## Conventions

- One file per drift entry: `YYYY-MM-DD-<kebab-slug>.md`
- Files live in `open/` until merged into official instructions, then `git mv` to `applied/`
- Frontmatter is machine-readable (`rg '^priority: HIGH'`, `rg '^status: OPEN'`). **Note:** mikefarah/yq v4 fails on `.md` files due to the multi-document `---` separator — extract frontmatter with `awk '/^---$/{c++; if (c==2) exit; next} c==1' file.md | yq '.field'`
- **Immutability — narrative body is immutable, index fields are mutable.** Once a file is committed:
  - **Immutable (never edit):** the four body sections (`What diverged`, `Why it seemed better`, `Proposed change`, `Resolution`), and the temporal frontmatter (`date`, `status`, `priority`, `trigger`, `session_context`). These are the historical record.
  - **Mutable for relocations only:** `affected_source:` and `applied_in:` paths MAY be updated when the underlying files are renamed or relocated. Update with the same commit that performs the file move, and reference the move in the commit message. Do not rewrite paths to point to different content — only to follow renames.
- The `_` prefix on `_template.md` follows the agent-private file convention (never published)

## Creating a new entry

1. Copy `_template.md` to `open/<YYYY-MM-DD>-<kebab-slug>.md` and fill it in.
2. **In the same change, add a summary line to the `## OPEN` section below**, in the same shape as the entries there — a markdown link titled `<date> — <title>` pointing at the new `open/…` file, then `— PRIORITY.` and a one-paragraph hook. The index line is part of entry creation, not an afterthought (symmetric with the OPEN → APPLIED transition step that moves it).

## Status transition (OPEN → APPLIED)

1. `git mv open/<file>.md applied/<file>.md`
2. Edit frontmatter: `status: OPEN` → `status: APPLIED`; add `applied_date:` and `applied_in:` fields
3. Update this README: move the entry line from `## OPEN` to `## APPLIED`

## Staleness — what to do with old `open/` entries

When triaging a stale `open/` entry (older than ~3 months), choose one path:

| Path | When to choose | Action |
|------|----------------|--------|
| **Resolve** | The drift's proposed change still applies and is feasible | Implement the change → follow OPEN → APPLIED transition above |
| **Refile** | The original framing is wrong but the underlying observation is still relevant | Create a NEW entry with corrected framing, set `supersedes: <old-file>` in its frontmatter, then move the old file to `applied/` with `status: APPLIED`, `applied_in: <new-file>`, and a one-paragraph Resolution explaining the refile |
| **Drop** | The observation no longer holds (underlying code/process changed; the drift was wrong; the rule it would change has been removed) | Move to `applied/` with `status: APPLIED`, `applied_date:` today, leave `applied_in:` empty, and write a Resolution paragraph explaining why no change is needed |

Never simply delete the file — the historical record stays. Always transition through `applied/` so the review trail is preserved.

## Compaction — old `applied/` entries

Once `applied/` grows past ~50 entries or the oldest entries are >6 months old, run a compaction pass:

- Group entries by **theme**.
- Write `applied/INDEX-<YYYY-MM>.md` summarising each theme — one paragraph per entry covering: date, slug, what changed, the file paths that codified the change. Link to each original entry.
- Keep the original entries — they remain immutable historical records. The index just adds a navigable summary so the directory listing doesn't grow unbounded.
- Update this README's `## APPLIED` section to list the index file at the top and collapse the entries it covers into a single line "covered in `applied/INDEX-<YYYY-MM>.md`".

## OPEN

<!-- Add new drift entries here, one line each, in the form:
     - [YYYY-MM-DD — title](open/YYYY-MM-DD-kebab-slug.md) — PRIORITY. One-paragraph hook.
-->

## APPLIED

<!-- Move entries here (or to a monthly INDEX file) when status transitions to APPLIED. -->
