---
name: reuse-alias-in-select
description: Reuse an alias defined earlier in the same `select` to avoid repeating an expression
type: rule
impact: LOW
tags: [readability, idiom, ch-specific]
---

# Rule: Reuse aliases within the same SELECT

## Why

ClickHouse allows you to reference a column alias **inside the same `select` list** (and in `where`, `group by`, `order by`). PostgreSQL does not allow this in the projection list — and the SQL standard formally agrees with PG. So many writers default to either:

1. Repeating the expression
2. Wrapping the whole thing in an outer query

Both are noisy. CH's alias-reuse is a small but real readability win.

## Incorrect

```sql
select count() as total_rows,
    countIf(foreign_id in (select id from dim_ids)) as valid_fk,
    count() - countIf(foreign_id in (select id from dim_ids)) as broken_fk,
    round((count() - countIf(foreign_id in (select id from dim_ids))) * 100.0 / count(), 4) as broken_pct
from postgresql(..., table = 'fact_table')
```

The same `countIf(...)` block appears three times. Edits drift, the third instance loses sync.

## Correct

```sql
select count() as total_rows,
    countIf(foreign_id in (select id from dim_ids)) as valid_fk,
    total_rows - valid_fk as broken_fk,
    round(broken_fk / total_rows * 100, 4) as broken_pct
from postgresql(..., table = 'fact_table')
```

Each aggregate is computed once. Edits to `valid_fk` automatically propagate to `broken_fk` and `broken_pct`.

## When to apply

- Multi-step counters/ratios in the same projection list
- Derived metrics that build on each other (count → ratio → percentile)

## When NOT to apply

- Mixed-engine portability: if the same query may be ported to PostgreSQL, keep expressions repeated or use a CTE — PG won't let you reuse aliases in `select`
- `group by` clauses: reusing aliases there is fine in CH but confuses migration to engines without that feature

## Order of evaluation

CH evaluates the `select` list **top to bottom** for alias resolution: you can reference any alias defined *above* the current line. Don't reference an alias defined *below* — that's not supported.

```sql
select
    a as x,         -- defines x
    x + 1 as y,     -- OK: x is above
    z - 1 as w,     -- ERROR: z is below
    a * 2 as z
```

## Quick note on `where` / `group by` / `order by`

Same logic — aliases from `select` are visible. So this works:

```sql
select count() as cnt, type
from t
group by type
having cnt > 100
order by cnt desc
```

vs the more verbose:

```sql
select count(), type
from t
group by type
having count() > 100
order by count() desc
```
