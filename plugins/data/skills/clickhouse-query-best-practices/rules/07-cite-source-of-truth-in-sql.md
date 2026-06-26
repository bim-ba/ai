---
name: cite-source-of-truth-in-sql
description: Link enum/status/code-path semantics to the source definition inside a SQL comment so the query is self-documenting six months later
type: rule
impact: MEDIUM
tags: [documentation, enums, comments]
---

# Rule: Cite the source of truth in a SQL comment

## Why

Research queries outlive their context. Six months from now, the document they were attached to is gone, the ticket comment is buried, and the next reader sees only the SQL — possibly in a code-review diff or in `git blame`.

If the query contains `where type = 125` with no comment, the reader has to:

1. Guess what `type` means on that table
2. Hunt the codebase for the enum
3. Match `125` to a name
4. Verify the file hasn't been renamed since

A 1-line comment with the file path collapses all four steps:

```sql
-- src/Domain/YourProject/Enums/EntityHistoryType.cs
map(
    1, '02-Removed',
    2, '01-Added',
    3, '00-Declared'
) as types_
```

Now `git grep` or "Go to file" gets the reader straight to the enum.

## Incorrect

```sql
select count() from t where type = 1 or type = 3
```

## Correct

```sql
-- src/Domain/YourProject/Enums/EntityHistoryType.cs
-- 1 = Removed, 3 = Declared
select count() from t where type in (1, 3)
```

Or even better, use rule 04 (map literal) which makes the enum explicit:

```sql
with map(1, 'Removed', 2, 'Added', 3, 'Declared') as types_  -- src/Domain/YourProject/Enums/EntityHistoryType.cs
select count() from t where types_[type] in ('Removed', 'Declared')
```

## What to cite

| Source kind | Cite as |
|-------------|---------|
| Application enum file | `-- path/to/Enum.cs` (or `.java`, `.ts`, etc.) |
| Tracker issue defining business meaning | `-- YOURPROJECT-NNN` |
| Wiki page | `-- wiki: data/domains/entity/lifecycle` |
| dbt model with the canonical definition | `-- ref('stg__entity__events__dict')` |
| Decision made in a specific PR | `-- PR-id NNN: rationale` |

## Where to put the citation

- **Top of a `with` block** when the citation explains the entire CTE
- **Above the `where` filter** when the citation explains a specific magic literal
- **Inline next to the literal** when one column among many uses an enum

## What NOT to cite

- "Created by Claude on date X" — not useful; use `git blame`
- "See TICKET-NNN" — only useful if the ticket actually contains the enum definition; otherwise it's a stale pointer
- Anything that will outlive the query but go stale faster than the source code

## When to apply

Any SQL that includes:

- A bare integer compared to a `type` / `status` / `code` column
- A magic UUID (owner id, partner id, config id) — cite the constants file
- A time threshold tied to a business event (cite the related ADR or PR)

## When NOT to apply

- Self-explanatory primitives — `where created_at > today() - interval 7 day` doesn't need a citation
- Column expressions that don't depend on external code (`name like 'TEST_%'`)
