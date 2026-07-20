---
name: ch-sql-idioms
description: Small ClickHouse SQL idioms that consistently come up in research queries — CTE inlining vs MATERIALIZED, scalar WITH-aliases, dateDiff, diagnostics in comments not columns
type: rule
impact: MEDIUM
tags: [cte, idiom, style, performance]
---

# Rule: ClickHouse SQL idioms — small but consistent

## Why

ClickHouse SQL looks ANSI-ish but has its own idioms inherited from MergeTree semantics, the analyzer's two-stage resolution, and OLAP-vs-OLTP differences. When research queries follow PostgreSQL muscle memory they end up either wrong (CTEs re-execute under inlining), wasteful (federated calls re-run on every reference), or noisy (interpretation strings stuffed into result columns instead of comments).

## The five idioms

### 1. CTEs inline by default — re-references RE-EXECUTE

```sql
-- BAD — pg_call runs TWICE despite the CTE
with pg_data as (
    select id, value from postgresql(my_named_connection,
        database = 'my_database', schema = 'public', table = 'entities'
    )
)
select 'positive_branch' as branch, count() from pg_data where value > 0
union all
select 'negative_branch' as branch, count() from pg_data where value <= 0
```

ClickHouse's analyzer clones and re-resolves the CTE's `QueryNode` for every reference. Two references → two evaluations. For `postgresql()` that means two PG round-trips. For heavy CH aggregations it means two scans.

**Fix when you must re-reference an expensive CTE: `AS MATERIALIZED`** (experimental, requires both settings):

```sql
-- GOOD — pg_call runs ONCE
with pg_data as materialized (
    select id, value from postgresql(my_named_connection,
        database = 'my_database', schema = 'public', table = 'entities'
    )
)
select 'positive_branch' as branch, count() from pg_data where value > 0
union all
select 'negative_branch' as branch, count() from pg_data where value <= 0
settings enable_analyzer = 1, enable_materialized_cte = 1
```

> `enable_materialized_cte` is experimental. `RECURSIVE` and correlated CTEs are not allowed under MATERIALIZED. Verify CH version supports it (`select value from system.settings where name = 'enable_materialized_cte'`).

**Better fix when possible: restructure to reference once.** Rule 01's CTE-wrap-federation pattern works precisely because the redesigned query references the wrapped CTE one time only — inlining doesn't hurt under single reference.

### 2. `WITH expr AS alias` for scalar constants — NOT `WITH alias AS (SELECT expr)`

```sql
-- BAD — single-row CTE wrapping a scalar, drags subquery machinery for nothing
with ch_clock as (select toUnixTimestamp(now()) as ch_epoch)
select pg.id, pg.created_at, ch_epoch
from postgresql(..., table = 'entities') as pg, ch_clock

-- GOOD — scalar alias, parsed as expression, not subquery
with toUnixTimestamp(now()) as ch_epoch
select id, created_at, ch_epoch from postgresql(..., table = 'entities')

-- BEST when used once — inline at the point of use
select id, created_at, toUnixTimestamp(now()) as ch_epoch
from postgresql(..., table = 'entities')
```

ClickHouse's `ParserWithElement` distinguishes two grammar rules: `<expression> AS <identifier>` (scalar alias) and `<identifier> AS (<select>)` (CTE / subquery). The first does not invoke `QueryNode` resolution — no inlining concerns, no setting required, no implicit `CROSS JOIN` to fold the scalar into the main query.

Use the scalar form when the alias names a value referenced 2+ times in the same `SELECT`. If it's referenced once, inline it directly.

### 3. `dateDiff('unit', a, b)`, NOT `toUnixTimestamp(b) - toUnixTimestamp(a)`

```sql
-- BAD — double conversion, only works on DateTime-coercible inputs
select toUnixTimestamp(end_ts) - toUnixTimestamp(start_ts) as seconds
from events

-- GOOD — idiomatic, accepts Date / Date32 / DateTime / DateTime64 directly
select dateDiff('second', start_ts, end_ts) as seconds from events
```

Equivalent numeric result for second precision, but `dateDiff` accepts native temporal types without coercion and is the documented idiom. Also use `dateDiff('minute', …)`, `dateDiff('hour', …)`, etc.

`timeDiff(a, b)` is a documented shortcut equivalent to `dateDiff('second', a, b)`.

### 4. Diagnostics & interpretation strings live in SQL COMMENTS, not result columns

```sql
-- BAD — pollutes the result set with literal strings, every row carries the same caption
select toUnixTimestamp(pg_now) - toUnixTimestamp(now()) as delta_seconds,
       'positive value = federated read is in the future relative to CH wall clock' as interpretation
from (select pg_now from postgresql(..., table = 'pg_clock'))

-- GOOD — caption in a comment, result columns are pure data
-- positive delta_seconds  → federated read is in the future relative to CH wall clock
-- negative delta_seconds  → CH wall clock is in the future relative to PG
select dateDiff('second', now(), pg_now) as delta_seconds
from (select pg_now from postgresql(..., table = 'pg_clock'))
```

Result rows are for data. SQL comments are for «how to read this». A research query that mixes the two is harder to feed into downstream tooling and noisier on screen.

### 5. `= (scalar subquery)` over `IN (subquery)` when there's a single value

```sql
-- BAD — IN-subquery does not push down to postgresql(); CH evaluates after fetch
with one_id as (select id from ch_mirror.entities order by created_at desc limit 1)
select * from postgresql(..., table = 'entity_events')
where entity_id in (select id from one_id)

-- GOOD — scalar subquery: CH analyzer pre-evaluates to a literal, then pushes `WHERE entity_id = <literal>` to PG
select * from postgresql(..., table = 'entity_events')
where entity_id = (select id from ch_mirror.entities order by created_at desc limit 1)
```

The mechanism is documented in rule 12. The idiom: when you know the subquery yields exactly one value, use `=`, not `IN`. Semantically clearer, and pushdown-friendly across federated calls.

## When to apply

- **Idiom 1** (CTE inlining): any time a CTE is referenced more than once AND the CTE body is non-trivial (federated call, large aggregation, sort over many rows)
- **Idiom 2** (scalar `WITH ... AS`): any time you'd write `WITH x AS (SELECT scalar_expr)` for a single-value constant
- **Idiom 3** (`dateDiff`): any time you'd compute a time delta from two timestamps
- **Idiom 4** (comments not columns): any time you're tempted to add a `'string explaining the query' AS interpretation` column
- **Idiom 5** (`=` over `IN`): any time a subquery is guaranteed to return one row (look for `LIMIT 1`, `argMax`, `groupArray`-of-singleton)

## Anti-patterns checklist

- `with x as (select pg_call(...)) ... select from x ... union all select from x` — pg_call runs twice
- `with c as (select scalar)` — wrap-for-no-reason
- `toUnixTimestamp(a) - toUnixTimestamp(b)` for time diff
- `'positive means X' as interpretation` column in a result set
- `where id in (subquery limit 1)` — should be `where id = (subquery limit 1)`

## See also

- Rule 01 (`cte-wrap-federation`) — when CTE-wrap is the right answer (single reference, postgresql() collapse)
- Rule 12 (`federated-postgresql`) — full pushdown rules, including the `= (subquery)` mechanism explained in idiom 5

## Sources

- ClickHouse docs — WITH: <https://clickhouse.com/docs/sql-reference/statements/select/with> (Restrictions section covers MATERIALIZED CTE and required experimental settings)
- ClickHouse docs — date/time functions: <https://clickhouse.com/docs/sql-reference/functions/date-time-functions> (`dateDiff`, `timeDiff`)
- Source: `src/Analyzer/Passes/QueryAnalyzer.cpp` (CTE re-resolution per reference)
- Source: `ParserWithElement` (grammar split between scalar alias and subquery)
- `MaterializingCTEStep` / `DelayedMaterializingCTEsStep` in the Planner (`AS MATERIALIZED` implementation)
