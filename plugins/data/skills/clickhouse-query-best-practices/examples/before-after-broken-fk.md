# Example: Broken-FK probe

**Thesis**: «Some `fact_table.foreign_id` values reference non-existent `dim_table.id`. Measure: how many per `type`?»

**Rules applied in the refactor**: 01 (cte-wrap), 09 (reuse-alias-in-select), 11 (lowercase).

## BEFORE (original — three round-trips, repeated subquery)

```sql
SELECT
    type,
    count() AS history_rows,
    countIf(foreign_id IN (
        SELECT id FROM postgresql(
            my_named_connection,
            database='my_database',
            schema='public',
            table='dim_table'
        )
    )) AS rows_with_valid_fk,
    count() - countIf(foreign_id IN (
        SELECT id FROM postgresql(
            my_named_connection,
            database='my_database',
            schema='public',
            table='dim_table'
        )
    )) AS rows_with_broken_fk
FROM postgresql(
    my_named_connection,
    database='my_database',
    schema='public',
    table='fact_table'
)
GROUP BY type
ORDER BY type;
```

**Issues**:

- `(select id from postgresql(..., dim_table))` appears twice → two round-trips to PG just for the same id list. Plus one for `fact_table` → three total.
- The `count() - countIf(...)` expression repeats the `countIf(...)`. A typo in one drifts.
- Mixed-case keywords, hard to scan.

## AFTER (refactored — one CTE, alias reuse)

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
    type,
    count() as rows,
    countIf(foreign_id in (select id from dim_ids)) as rows_with_valid_fk,
    rows - rows_with_valid_fk as rows_with_broken_fk
from postgresql(
    my_named_connection,
    database = 'my_database',
    schema = 'public',
    table = 'fact_table'
)
group by type
order by type
;
```

**What the rules bought us**:

- **Rule 01** (`dim_ids` CTE): single fetch of `dim_table.id`. Two PG round-trips instead of three.
- **Rule 09** (alias reuse): `rows`, `rows_with_valid_fk` used in derived columns. One source of truth per metric.
- **Rule 11** (lowercase, alignment): matches sqlfmt.

## Bonus: the same probe in the other direction

A companion query checking a second FK demonstrates rule 09 even more clearly — multiple derived metrics chain off the first computation:

```sql
with parent_ids as (
    select id from postgresql(
        my_named_connection,
        database = 'my_database', schema = 'public', table = 'parent_table'
    )
)
select
    count() as total_rows,
    countIf(parent_id in (select id from parent_ids)) as rows_with_valid_parent_fk,
    total_rows - rows_with_valid_parent_fk            as rows_with_broken_parent_fk,
    round(rows_with_broken_parent_fk / total_rows * 100, 4) as rows_with_broken_parent_fk_pct
from postgresql(my_named_connection, database = 'my_database', schema = 'public', table = 'junction_table')
;
```

Four metrics, each computed once. The PG-style equivalent would need either a subquery or three repeated `countIf` blocks.
