---
name: lowercase-style
description: Lowercase keywords, columns one per line in projection lists, align `as` clauses, trailing semicolon per statement
type: rule
impact: LOW
tags: [style, formatting]
---

# Rule: Lowercase, aligned, one-column-per-line

## Why

Visual consistency. The convention in dbt-ClickHouse projects is lowercase keywords + aligned column lists. Mixed-case queries blend in poorly in diffs and code-review.

Also: lowercase matches the dbt-sqlfmt convention. Production dbt models go through `sqlfmt` which already enforces lowercase — research SQL should match.

## Style

- **Keywords**: lowercase (`select`, `from`, `where`, `group by`, `order by`, `limit`, `with`, `as`)
- **Function names**: ClickHouse functions stay camelCase (`groupUniqArray`, `arraySort`, `toDateTime64`) — that's the ClickHouse house style, don't lowercase them
- **Type names**: PascalCase (`Tuple`, `Array(String)`, `LowCardinality`) — also CH house style
- **One column per line** in `select`, `group by`, `order by` when the list is >3 short items or contains any expression
- **Align `as`** column-alias keywords within the same projection list when it improves scanning
- **Trailing `;`** on every standalone statement (helps when batching through `clickhouse-client` or MCP)
- **Leading commas** are acceptable but trailing commas are the default

## Incorrect (mixed-case, unaligned)

```sql
WITH dim_ids AS (
    SELECT id FROM postgresql(..., table='dim_table')
)
SELECT COUNT() as total_rows,
COUNTIF(foreign_id IN (SELECT id FROM dim_ids)) AS rows_with_valid_fk, total_rows - rows_with_valid_fk AS rows_with_broken_fk
FROM postgresql(...,table='fact_table')
```

## Correct

```sql
with dim_ids as (
    select id from postgresql(
        my_named_connection,
        database = 'my_database',
        schema = 'public',
        table = 'dim_table'
    )
)

select
    count() as total_rows,
    countIf(foreign_id in (select id from dim_ids)) as rows_with_valid_fk,
    total_rows - rows_with_valid_fk as rows_with_broken_fk,
    round(rows_with_broken_fk / total_rows * 100, 4) as rows_with_broken_fk_pct
from postgresql(
    my_named_connection,
    database = 'my_database',
    schema = 'public',
    table = 'fact_table'
)
;
```

## Indentation

- CTEs: keyword on its own line, body indented 4 spaces
- `select` projection list: one column per line, indented 4 spaces from `select`
- `from … join …`: each join on its own line at the same indent level as `from`
- `where`: one condition per line if there are multiple `and`/`or` clauses

## What to relax for short queries

For a one-shot probe like `select count() from t where status = 'open'`, single-line is fine. Style strictness scales with query length and review surface area.

## Linting

There is no automated lint for ad-hoc research SQL today. Production dbt models in `models/**` go through `sqlfmt`. If you want consistency, run `sqlfmt --check` mentally before committing.
