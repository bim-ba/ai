---
name: clickhouse-query-best-practices
type: skill
category: rulebook
description: Use when writing or reviewing ad-hoc research SQL in a dbt-ClickHouse project, or running federated queries via `postgresql()` from ClickHouse for data-quality investigations — covers CTE-wrapping of federation, dedup via `limit 1 by`, flow analysis with `groupUniqArray + arraySort`, runtime-computed boundary dates, hybrid PG/CH source selection, source-of-truth citation, and style.
---

# ClickHouse Query Best Practices

How to write idiomatic, readable, performant research SQL in ClickHouse — especially when crossing into PostgreSQL via the `postgresql()` table function. This skill is about **the SQL you write to investigate**, not about table design.

## When to use

- Writing or reviewing ad-hoc investigations in your project's ad-hoc SQL directory (e.g. `analyses/adhoc/` or equivalent)
- Operational research SQL stored under any project research directory
- Federation queries that pull from a named PostgreSQL connection (or any other `postgresql()`) into ClickHouse
- Any data-quality probe that mixes ClickHouse-mirror tables with `postgresql()` calls

## When NOT to use

- Schema / table design - out of scope for this skill
- dbt SQL inside `models/**` (production) - out of scope; for `.yml` `description:` text + the dbt-score gate see your project's yaml-conventions documentation
- Type mapping for composite Tuple types - out of scope for this skill
- Pure data-modeling decisions (PK ordering, partitioning) - out of scope for this skill

## Rules (read these before writing)

| # | Rule | Impact |
|---|------|--------|
| 01 | [cte-wrap-federation](rules/01-cte-wrap-federation.md) — wrap each `postgresql()` call in a named CTE once, reference by alias | CRITICAL |
| 02 | [compute-boundaries-at-runtime](rules/02-compute-boundaries-at-runtime.md) — never hardcode release dates; derive from `min/max` of the relevant signal | HIGH |
| 03 | [limit-1-by-pattern](rules/03-limit-1-by-pattern.md) — use `order by X limit 1 by KEY` for per-key first/last, not `argMax` or `row_number()` | HIGH |
| 04 | [map-with-sortable-prefix](rules/04-map-with-sortable-prefix.md) — translate enum ints via `map(1, '01-Added', 2, '02-Removed')` with numeric prefixes for lexicographic-sort ordering | HIGH |
| 05 | [groupuniqarray-arraysort-flows](rules/05-groupuniqarray-arraysort-flows.md) — model per-entity event flow as `arraySort(groupUniqArray(label))`, group by the array | HIGH |
| 06 | [hybrid-source-selection](rules/06-hybrid-source-selection.md) — small / dimensional → `postgresql()`; huge / append-only → CH mirror | HIGH |
| 07 | [cite-source-of-truth-in-sql](rules/07-cite-source-of-truth-in-sql.md) — link enum / status-code semantics to the source definition (e.g. C# enum file path) in a SQL comment | MEDIUM |
| 08 | [numbered-subquestions](rules/08-numbered-subquestions.md) — keep `(a)` `(b)` sub-queries for the same thesis in one file | MEDIUM |
| 09 | [reuse-alias-in-select](rules/09-reuse-alias-in-select.md) — use prior column aliases in the same `select` instead of repeating expressions | LOW |
| 10 | [settings-not-cast](rules/10-settings-not-cast.md) — fix join null behavior with `settings join_use_nulls = 1` once, not per-column casts | LOW |
| 11 | [lowercase-style](rules/11-lowercase-style.md) — lowercase keywords, columns one per line, align `as`, trailing semicolon | LOW |
| 12 | [federated-postgresql](rules/12-federated-postgresql.md) — `postgresql()` pushdown rules (what does / does not push), correct `count()` workarounds (PG view / dictionary / mirror — **NOT** `table='(SELECT …)'`), named-connection → cluster map, hot-table red-flags | HIGH |
| 13 | [ch-sql-idioms](rules/13-ch-sql-idioms.md) — CTE inlining + `AS MATERIALIZED`, scalar `WITH expr AS alias`, `dateDiff` vs `toUnixTimestamp` subtraction, diagnostics in comments not result columns, `= (subquery)` vs `IN (subquery)` | MEDIUM |
| 14 | [dict-helper-macros](rules/14-dict-helper-macros.md) — prefer `{{ has }}` / `{{ get }}` / `{{ get_or_null }}` / `{{ get_or_default }}` Jinja wrappers over raw `dictHas` / `dictGet` / `dictGetOrNull` / `dictGetOrDefault`; tuple-attribute lookup in one call; pre-existing bare-`dictGet` blocks are grandfathered | MEDIUM |

## Quick reference (pattern recipes)

### Federation: wrap once, reference everywhere

```sql
with source_records as (
    select id from postgresql(
        my_named_connection,
        database = 'my_database', schema = 'public', table = 'source_table'
    )
)
select count() as total_rows,
       countIf(foreign_id in (select id from source_records)) as valid_fk,
       total_rows - valid_fk as broken_fk
from postgresql(my_named_connection, database = 'my_database', schema = 'public', table = 'fact_table')
```

**The named-collection (NC) is an identifier — never single-quote it.** The first positional
arg to `postgresql(...)` is the NC *name*, passed bare (as above:
`postgresql(my_named_connection, …)`). Quoting it —
`postgresql('my_named_connection', …)` — makes ClickHouse read the
string as a `host:port` connection literal instead of resolving the collection, so the call
fails (or misroutes). Quote the `database=`/`schema=`/`table=` *values*; never the collection
name. (Re-taught 3× before it was codified — drift G1.)

### Boundary date from data, not hardcoded

```sql
with first_event_of_type_at as (
    select min(created_date) as ts from ch_mirror.entity_events where type = <event_type_id>
)
select countIf(created_at >= (select ts from first_event_of_type_at)) as after_release
from postgresql(my_named_connection, database = 'my_database', schema = 'public', table = 'entity_history')
where type = 1
```

### Dedup → 1:1 join

```sql
with a as (select entity_id, ts from src_a order by ts limit 1 by entity_id),
     b as (select entity_id, ts from src_b order by ts limit 1 by entity_id)
select ...
from a left join b using (entity_id)
settings join_use_nulls = 1
```

### Flow as a sorted array

```sql
with
    map(1, '02-Removed', 2, '01-Added', 3, '00-Declared') as types_,
    flows as (
        select entity_id, arraySort(groupUniqArray(types_[type])) as flow
        from postgresql(my_named_connection, database = 'my_database', schema = 'public', table = 'entity_history')
        group by entity_id
    )
select flow, count() from flows group by flow order by flow
```

### Hybrid source selection

```sql
-- small dim → postgresql()
with dim_records as (
    select id from postgresql(my_named_connection, database = 'my_database', schema = 'public', table = 'dim_table')
)
-- huge fact → ClickHouse mirror (e.g. fact_events with hundreds of millions of rows)
select count() from ch_mirror.fact_events where type = <type_id> and entity_id in (select id from dim_records)
```

### Federation pushdown — force PG-side filtering

```sql
-- BAD: IN-subquery does not push, BETWEEN does not push
where entity_id in (select id from postgresql(..., table = 'entities'))
  and created_at between '2026-05-01' and '2026-05-25'

-- GOOD: literal IN-list + comparison operators both push to PG
with target_ids as (select groupArray(id) as ids from ch_mirror.entities where status = 5)
select * from postgresql(..., table = 'entity_events')
where entity_id in (select ids from target_ids)
  and created_at >= '2026-05-01' and created_at <= '2026-05-25'
```

### Scalar constants — `WITH expr AS alias`, not `WITH alias AS (SELECT expr)`

```sql
-- BAD — subquery wrapping a single value, drags CROSS JOIN to fold into main query
with ch_clock as (select toUnixTimestamp(now()) as ch_epoch)
select pg.id, ch_epoch from postgresql(..., table = 'entities') as pg, ch_clock

-- GOOD — scalar alias, parsed as expression
with toUnixTimestamp(now()) as ch_epoch
select id, ch_epoch from postgresql(..., table = 'entities')
```

### CTEs inline by default — `AS MATERIALIZED` to evaluate once when referenced multiple times

```sql
-- BAD — pg_data evaluated TWICE (once per reference)
with pg_data as (select id, value from postgresql(..., table = 'entities'))
select count() from pg_data where value > 0
union all
select count() from pg_data where value <= 0

-- GOOD — single evaluation; experimental, requires both settings
with pg_data as materialized (select id, value from postgresql(..., table = 'entities'))
select count() from pg_data where value > 0
union all
select count() from pg_data where value <= 0
settings enable_analyzer = 1, enable_materialized_cte = 1
```

### `dateDiff('unit', a, b)` for time differences

```sql
-- BAD: double conversion, only works on DateTime-coercible inputs
select toUnixTimestamp(b) - toUnixTimestamp(a) as seconds from events

-- GOOD: idiomatic, native temporal types accepted directly
select dateDiff('second', a, b) as seconds from events
```

### Never use `count()` directly on a big federated table

```sql
-- BAD: pulls all rows over the wire just to count
select count() from postgresql(my_named_connection, ..., table = 'large_table')

-- GOOD: real-time mirror in CH
select count() from ch_mirror.large_table

-- GOOD: PG-side estimate (≈ within autovacuum interval) via pg_class
select reltuples::bigint as estimated_rows
from postgresql(..., schema = 'pg_catalog', table = 'pg_class')
where relname = 'large_table'
```

## Examples (RED → GREEN)

Three worked rewrites of real research queries. Each file shows the original (RED) and the refactored (GREEN) version with a rule-by-rule breakdown.

### [before-after-broken-fk](examples/before-after-broken-fk.md) — rules 01, 09, 11

**Thesis**: FK-integrity probe — count `fact_table` rows where `foreign_id` has no match in `dim_table`.

RED: `postgresql(...)` for `dim_table.id` appears twice in the same query → 3 PG round-trips; `count() - countIf(...)` expression repeated 3×.

GREEN: one `dim_ids` CTE (rule 01) collapses to 2 round-trips; alias reuse (rule 09) means each aggregate is written once.

### [before-after-orphan-removed](examples/before-after-orphan-removed.md) — rules 01, 04, 05, 07, 11

**Thesis**: lifecycle-distribution probe — which combinations of Removed / Added / Declared events does each entity see?

RED: `groupUniqArray(type)` returns raw ints + 2^3 boolean cross-tab with hard-to-read rows.

GREEN: `map(int, 'NN-Name')` (rule 04) + `arraySort(groupUniqArray(label))` (rule 05) → one `flow` column per entity; result collapses to N actually-observed patterns. Citation comment (rule 07) points to the source enum.

### [before-after-window-match](examples/before-after-window-match.md) — rules 01, 02, 03, 06, 10

**Thesis**: event-mirror validation — does `entity_events.type=125` appear within 60 s of `entity_history.type=1` after the feature release?

RED: hardcoded release date literal; large event table queried through `postgresql()` (full scan); N × M cross-product join; sentinel `!= toDateTime64(0, 6)` for null-detection.

GREEN: `first_event_125_at` CTE derives boundary from data (rule 02); large table moved to CH mirror (rule 06); both sides deduped with `limit 1 by` (rule 03) → 1:1 join; `settings join_use_nulls = 1` (rule 10) makes `diff is null` work cleanly.

## ClickHouse-vs-PostgreSQL idiom map

Covers `row_number()` → `limit 1 by`, `case when` → `multiIf` / `map[key]`, `array_agg(distinct …)` → `groupUniqArray`, date function differences, null handling. Refer to your project's CH-vs-PG idiom documentation.

## Common mistakes

| Mistake | Symptom | Fix (rule) |
|---------|---------|-----------|
| Repeating `postgresql(...)` 3× in one query | Three round-trips to PG, ~3× latency | Rule 01 |
| Hardcoded `toDateTime64('2025-12-26', 6)` | Goes stale silently when release date shifts or backfill happens | Rule 02 |
| `row_number() over (partition by entity_id order by ts)` | Verbose, drags all columns through window | Rule 03 |
| `case when type = 1 then 'Removed' …` | Hard to sort lexically, magic numbers everywhere | Rule 04 |
| Multi-condition `has(types, 1) and not has(types, 2)` | Cross-tab explosion in `group by` | Rule 05 |
| Pulling hundreds-of-millions-row fact table through `postgresql()` | Query times out, postgres pegged | Rule 06 |
| Magic int `where type = 125` with no comment | 6 months later: "what's 125?" | Rule 07 |
| `count(distinct entity_id)` | Slower than `uniqExact` on large groups | Prefer `uniqExact` |
| `select count() from postgresql(..., table = 'large_table')` | Pulls all rows over the wire | Rule 12 — use CH mirror, PG-side view, or `pg_class.reltuples` |
| `where x in (select id from postgresql(...))` | IN-subquery does NOT push → PG fetches everything | Rule 12 — materialise CH-side first, then literal IN-list |
| `where created_at between a and b` against `postgresql()` | BETWEEN does NOT push → PG fetches everything | Rule 12 — rewrite as `>= a and <= b` |
| Comparing same DB via two different named connections | One may be a stale snapshot, the other live — check your cluster routing map | Rule 12 — verify named-connection → cluster map |
| `with x as (select ...) ... select from x ... union all select from x` | CTEs are inlined → subquery re-executes per reference; on `postgresql()` calls means N round-trips | Rule 13 — single-reference restructure OR `as materialized` with `enable_analyzer=1, enable_materialized_cte=1` |
| `with x as (select toUnixTimestamp(now()) as e) select ..., e from t, x` | Subquery-wrap of a scalar, implicit CROSS JOIN | Rule 13 — `with toUnixTimestamp(now()) as e select ..., e from t` |
| `toUnixTimestamp(b) - toUnixTimestamp(a)` for delta seconds | Verbose, double conversion, fails on Date/Date32 inputs | Rule 13 — `dateDiff('second', a, b)` |
| An `'interpretation' as caption` column literal in a result set | Pollutes the result, every row carries identical caption | Rule 13 — put the caption in a SQL comment above the query |
| `where id in (subquery limit 1)` against `postgresql(...)` | IN-subquery does not push down; CH evaluates after fetch | Rule 13 + 12 — `where id = (subquery limit 1)` so CH analyzer pre-evaluates and pushes equality |

## Red flags — STOP and refactor

- Same `postgresql(...)` block typed twice in one query
- Any hardcoded date literal like `'2025-12-26'` or `'2026-04-17'`
- `row_number() over` for "first per key" — use `limit 1 by`
- `case when type = N` with bare integers — use `map(...)` + cite the enum source
- Two separate files for `(a)` and `(b)` of the same thesis
- Mixed `SELECT` + `select` in the same file
- `count()` / `sum()` / `min()` / `max()` directly on a `postgresql(...)` call against a hot/large table — pulls everything over the wire
- `where x in (select … from postgresql(...))` — IN-subquery does not push down; rewrite as literal list materialised CH-side
- `between a and b` against `postgresql(...)` — does not push; rewrite as `>= a and <= b`
- `postgresql(..., table = '(SELECT …) AS subq')` — fictional syntax, `table` accepts only a remote table name. Use a PG-side view, a dictionary with `<query>`, or `PostgreSQL()` engine
- CTE referenced 2+ times in the same query when the CTE body is non-trivial (federated call, large scan) — inlining re-executes per reference; either restructure to single reference or add `AS MATERIALIZED`
- `with x as (select <scalar>) ... select ..., x from t, x` — subquery-wrap of a scalar; use `with <scalar> as alias` instead
- `toUnixTimestamp(b) - toUnixTimestamp(a)` — non-idiomatic; use `dateDiff('second', a, b)`
- An `'interpretation' as caption` column literal — caption belongs in a SQL comment, not in result rows

If any of these appear in code you're about to commit, the relevant rule applies.
