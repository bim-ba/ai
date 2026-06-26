---
name: cte-wrap-federation
description: Wrap each `postgresql()` call in a named CTE once, reference by alias for every subsequent use in the same query
type: rule
impact: CRITICAL
tags: [federation, postgresql, cte, performance, readability]
---

# Rule: CTE-wrap federation

## Why

Each `postgresql(...)` invocation is a **remote round-trip** to PostgreSQL. CH does not de-duplicate identical federation calls within the same query — every textual occurrence runs again.

Wrapping it once in a named CTE:

- collapses N round-trips into 1
- centralises auth args (no need to re-type `database=..., schema=..., table=...`)
- gives the call a semantic name (`source_ids`, not `(select id from postgresql(...))`)
- makes schema drift fail in one place

## Incorrect

```sql
select type, count() as rows,
    countIf(foreign_id in (
        select id from postgresql(
            my_named_connection,
            database = 'my_database', schema = 'public', table = 'dim_table'
        )
    )) as valid_fk,
    count() - countIf(foreign_id in (
        select id from postgresql(
            my_named_connection,
            database = 'my_database', schema = 'public', table = 'dim_table'
        )
    )) as broken_fk
from postgresql(
    my_named_connection,
    database = 'my_database', schema = 'public', table = 'fact_history'
)
group by type
```

Three round-trips to PG: one to fetch the history, two to fetch `dim_table.id` (identical subqueries).

## Correct

```sql
with dim_ids as (
    select id from postgresql(
        my_named_connection,
        database = 'my_database', schema = 'public', table = 'dim_table'
    )
)
select type,
    count() as rows,
    countIf(foreign_id in (select id from dim_ids)) as valid_fk,
    rows - valid_fk as broken_fk
from postgresql(
    my_named_connection,
    database = 'my_database', schema = 'public', table = 'fact_history'
)
group by type
```

Two round-trips total (one CTE + one fact-source). Reads top-down.

## When to apply

Every time the same `postgresql(...)` block — same DB/schema/table — appears more than once in a query, or even if the call is heavy enough that you want to name it for clarity.

## Edge cases

- If the CTE is filtered (e.g. only `select id where status = 'open'`), put the `where` inside the CTE, not outside — CH cannot push predicates into a remote subquery as freely as into a CH-native table.
- For very large dim tables (>10M rows), prefer the CH-mirror table instead of a `postgresql()`-wrapped CTE — see rule 06.
- `with` blocks in CH allow forward references between CTEs (CTE B can reference CTE A above it). Order them top-down by dependency.

## See also

- Rule 06 (hybrid source selection) — when CTE-wrap isn't enough and you should switch source entirely
