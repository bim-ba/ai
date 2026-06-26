---
name: hybrid-source-selection
description: Choose `postgresql()` for small dim/lookup tables, ClickHouse-mirror for large fact/event tables — even within the same query
type: rule
impact: HIGH
tags: [federation, performance, layering]
---

# Rule: Pick source by table size, not by habit

## Why

The `postgresql()` table function is a remote call to PostgreSQL. Predicate push-down is limited and the entire matched row-set comes back through the wire.

- **Small dim tables** (lookups, enum-like masters, FK lists with <1M rows): `postgresql()` is fine and gives you the freshest state.
- **Large fact tables** (event streams, high-volume CDC tables with tens-of-millions+ rows): use the ClickHouse-mirror table instead.

The CH mirror is dedup-aware: MergeTree consumers expose latest state via `argMax(_tx_timestamp)`, ReplacingMergeTree exposes it via `FINAL` (with `_tx_is_deleted = 0`).

Mixing both sources in **one** query is the right move when the join is "small dim ⋈ huge fact".

## Incorrect

```sql
-- pulling tens-of-millions of event rows through postgresql() — query times out, PG pegged
with large_events as (
    select entity_id, created_date
    from postgresql(my_named_connection, database = 'my_database', schema = 'public', table = 'large_event_table')
    where type = 125
)
select count() from large_events
```

## Correct

```sql
-- huge fact through CH mirror
with large_events as (
    select entity_id, created_date
    from ch_mirror.large_event_table
    where type = 125
),
-- small dim through postgresql() — freshest state
dim_records as (
    select id, created_at, status
    from postgresql(my_named_connection, database = 'my_database', schema = 'public', table = 'dim_table')
)
select e.entity_id, d.created_at as dim_created
from large_events e
left join dim_records d on d.id = e.entity_id
```

Always state the rationale in a comment when mixing — future readers will wonder why one CTE uses `postgresql()` and another doesn't:

```sql
-- using ch_mirror.large_event_table instead of postgresql(...) because of the large table size
```

## When to apply

- Any query touching high-volume fact or event tables
- Joins where one side is small (dim tables, FK lookups) and one side is huge (event/history tables)

## When NOT to apply

- The CH mirror lags behind PostgreSQL — for "what does PG see RIGHT NOW" debugging, use `postgresql()` regardless of size and accept the cost
- When you need a postgres-specific feature (e.g. `to_tsvector` text search) on the data — push the operation into PG

## Decision table

| Table characteristic | Source |
|----------------------|--------|
| Dim / lookup / small FK table (<1M rows) | `postgresql()` |
| Medium table (~10M rows) | `postgresql()` or CH mirror — either |
| Large fact / event / CDC table (50M+ rows) | CH mirror **always** |

## Dedup awareness on CH mirror

When you switch to a CH mirror, remember the dedup:

| Mirror engine | Dedup recipe |
|---------------|--------------|
| MergeTree | `argMax(field, _tx_timestamp) group by id` |
| ReplacingMergeTree | `select … from t final where _tx_is_deleted = 0` |
| dbt dictionary | `dictGet('schema.dict_name', 'field', id)` |

For probe queries that count cardinality (not exact state), you can sometimes skip dedup — but document it in a comment.

## See also

- Rule 01 (cte-wrap-federation) — wrap the `postgresql()` side once, then join
