---
name: federated-postgresql
description: Pushdown rules and patterns for the `postgresql()` table function — what does and does not push to PostgreSQL, why `count()` is wasteful, correct workarounds, and named-connection hygiene
type: rule
impact: HIGH
tags: [federation, postgresql, pushdown, performance]
---

# Rule: Federated PostgreSQL via `postgresql()` table function

## Why

`postgresql()` is a remote table function — every invocation opens a connection, sends a translated query, and streams rows back. ClickHouse's PG connector pushes down **only** a narrow set of WHERE predicates; everything else (aggregations, joins, sort, group by) runs in CH **after** the full filtered rowset is transferred. On large tables this turns a "small" SELECT into a multi-GB transfer.

ClickHouse executes the remote SELECT as `COPY (SELECT ...) TO STDOUT` inside a read-only PG transaction. The SELECT body is whatever survived the pushdown gate (`isCompatible()` in `transformQueryForExternalDatabase.cpp`).

## Pushdown rules

### What pushes to PostgreSQL

- Comparison operators with constants: `=`, `!=`, `>`, `>=`, `<`, `<=`
- `IN (1, 2, 3)` — **literal** list
- `LIMIT N` — **only on ClickHouse ≥ 24.7** for the PostgreSQL storage/table function. On older versions LIMIT is CH-side.
- Scalar subquery on the RHS of `=`: `WHERE id = (SELECT id FROM x LIMIT 1)` — works because the CH analyzer pre-evaluates the scalar subquery into a literal *before* the predicate hits the pushdown gate.

### What does NOT push to PostgreSQL

- Aggregations (`count`, `sum`, `min`, `max`, `avg`, `uniq*`, …) — always CH-side
- `JOIN`, `ORDER BY`, `GROUP BY` — always CH-side
- `IN (subquery)` — the subquery form is not in `isCompatible()`; CH applies it post-fetch (or raises with `external_table_strict_query = 1`)
- `BETWEEN a AND b` — not in the whitelist. Rewrite as `>= a AND <= b` to enable pushdown.
- `LIKE`, `ILIKE` — not in the whitelist.

> With `external_table_strict_query = 1` an incompatible predicate raises instead of being silently dropped. Useful while authoring a query — turn it on to discover what actually pushes down.

## Incorrect

### A. `count(*)` over `postgresql(...)`

```sql
-- BAD: pulls every row over the wire just to count
select count() from postgresql(
    my_named_connection,
    database = 'my_database', schema = 'public', table = 'large_table'
)
```

PG returns the whole table; CH counts locally. On large tables this pegs PG and times out CH.

### B. `IN (subquery)` against `postgresql(...)`

```sql
-- BAD: IN-subquery does not push; PG sends every row matching no other filter
select count() from postgresql(my_named_connection,
    database = 'my_database', schema = 'public', table = 'large_event_table')
where entity_id in (select id from postgresql(..., table = 'entities'))
```

### C. `BETWEEN` over `postgresql(...)`

```sql
-- BAD: BETWEEN doesn't translate; CH fetches everything in the table, then filters
select * from postgresql(..., table = 'entities')
where created_at between '2026-05-01' and '2026-05-25'
```

## Correct

### A. PG-side `count()` — three working patterns

There is **no** `postgresql(..., table = '(SELECT count(*) FROM x) AS subq')` form. The `table` parameter accepts only a remote table name (optionally qualified by `schema`). Subquery injection there is not supported by the connector. Use one of:

1. **Estimate via `pg_class.reltuples`** (stale by autovacuum interval, but free):

   ```sql
   select reltuples::bigint as estimated_rows
   from postgresql(
       my_named_connection,
       database = 'my_database', schema = 'pg_catalog', table = 'pg_class'
   )
   where relname = 'large_table'
   ```

2. **PG-side view** wrapping the count, then read it as a normal `postgresql()` table:

   ```sql
   -- on PG (DBA / migration):
   -- CREATE VIEW reporting.large_table_count_v AS SELECT count(*) AS n FROM large_table;
   select n from postgresql(
       my_named_connection,
       database = 'my_database', schema = 'reporting', table = 'large_table_count_v'
   )
   ```

3. **Switch source** to the ClickHouse mirror (preferred for any aggregation on a large table — see rule 06):

   ```sql
   -- mirror in CH, real-time via Debezium / CDC
   select count() from ch_mirror.large_table
   ```

### B. Force pushdown with `=` + scalar subquery

```sql
-- GOOD: scalar subquery pre-evaluated by CH → arrives at PG as `WHERE id = <literal>`
select * from postgresql(..., table = 'entities')
where id = (select id from ch_mirror.entities order by created_at desc limit 1)
```

For multi-value lookups against a small set, materialise CH-side and inline as a literal list:

```sql
-- GOOD: literal IN-list pushes; build it CH-side first
with target_ids as (
    select groupArray(id) as ids from ch_mirror.entities where status = 5
)
select * from postgresql(..., table = 'entity_events')
where entity_id in (select ids from target_ids)
```

### C. Rewrite `BETWEEN` as `>=` + `<=`

```sql
-- GOOD: two compatible comparisons push to PG
select * from postgresql(..., table = 'entities')
where created_at >= '2026-05-01' and created_at <= '2026-05-25'
```

## Named-connection hygiene

Named connections point at specific clusters or hosts — they are **not** interchangeable aliases. If your project has multiple named connections (e.g. for separate microservice databases), verify which connection reaches the correct live cluster before writing comparison queries. Treat different named connections as separate origins.

To inspect a named connection's host/port at any time:

```sql
select name, collection.host, collection.port, collection.database
from system.named_collections
where name like 'your_connection_prefix%'
settings format_display_secrets_in_show_and_select = 1
```

**Never** write a symmetric `UNION ALL` that counts the same table on two different named connections expecting to compare identical data — if one connection is a stale snapshot, you'd be comparing live vs. abandoned data.

## Hot-table red-flags

Aggregations and row counts through `postgresql()` on very large tables (tens of millions+ rows) will lock up PG or time out CH. Check your project's table-size documentation and always use the CH mirror for high-volume tables (e.g. `ch_mirror.*` or equivalent project namespace).

## When to apply

Any time you write SQL that calls `postgresql(...)`. The pushdown rules govern correctness as much as performance — a query that "works" on a 10k-row dev table can pull 100M rows in prod once the silent fallback kicks in.

## See also

- Rule 01 (`cte-wrap-federation`) — collapse repeated remote calls into one
- Rule 06 (`hybrid-source-selection`) — when to abandon `postgresql()` entirely for a CH mirror
- Rule 13 (`ch-sql-idioms`) — CTE materialization (`AS MATERIALIZED`) for cases where CTE inlining would re-execute a federated call

## Sources

- ClickHouse docs — `postgresql()` table function, Implementation Details: <https://clickhouse.com/docs/sql-reference/table-functions/postgresql>
- Source: `src/Storages/transformQueryForExternalDatabase.cpp` — `isCompatible()` pushdown whitelist
- LIMIT pushdown for PostgreSQL storage/table function landed in 24.7 (verify on your CH version via `select version()`)
