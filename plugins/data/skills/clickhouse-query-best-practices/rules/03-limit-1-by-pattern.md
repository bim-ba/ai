---
name: limit-1-by-pattern
description: Use `order by ts [asc|desc] limit 1 by KEY` for per-key first/last selection — not `row_number()` window or `argMax`
type: rule
impact: HIGH
tags: [deduplication, idiom, performance]
---

# Rule: `limit 1 by` is the CH-native per-key picker

## Why

CH has a dedicated modifier `limit N by COLS` (separate from regular `limit`): after ordering, keep at most N rows per distinct value of `COLS`. It is the idiomatic way to express "first per entity_id", "last per session", "top-3 per region".

Alternatives:

- `row_number() over (partition by KEY order by TS) = 1` — works but verbose, drags every column through the window function, less efficient.
- `argMax(field, ts) group by KEY` — only good when you want ONE specific field; if you want a whole row you must `argMax` every column.
- `group by KEY having ts = max(ts)` — wrong and gives duplicates when the timestamp isn't unique.

## Incorrect (verbose)

```sql
-- first Removed event per entity
select entity_id, removed_at
from (
    select entity_id, created_at as removed_at,
           row_number() over (partition by entity_id order by created_at asc) as rn
    from postgresql(..., table = 'entity_history')
    where type = 1
) sub
where rn = 1
```

## Incorrect (lossy)

```sql
-- if multiple events share min(created_at), this returns ALL of them, not one
select entity_id, min(created_at) as removed_at
from postgresql(..., table = 'entity_history')
where type = 1
group by entity_id
-- and we lost any other columns we wanted
```

## Correct

```sql
select entity_id, created_at as removed_at, foreign_id, description
from postgresql(my_named_connection, database = 'my_database', schema = 'public', table = 'entity_history')
where type = 1
order by created_at
limit 1 by entity_id
```

One row per `entity_id` — the earliest by `created_at` — and you keep every column you projected.

## When to apply

- "first / last / Nth event per entity" (per-session, per-day, per-key)
- Preparing one side of a 1:1 join (dedup → join, see example `before-after-window-match.md`)
- "top-K per group" where K is small (use `limit K by KEY`)

## Edge cases

- `limit 1 by KEY` requires `order by` to be deterministic. If multiple rows tie on the order column, CH picks **some** row — add a tie-breaker (e.g. `order by created_at, id`).
- For "last", use `order by ts desc limit 1 by KEY`.
- Combining with `where` is fine — filter happens first, then per-key cap.
- If you need exactly the row with `max(ts)` AND know `ts` is unique, plain `group by KEY having ts = max(ts)` works too — but the `limit 1 by` form is shorter and safer.

## CH-vs-PG cheat

| PostgreSQL | ClickHouse |
|------------|-----------|
| `select distinct on (entity_id) … order by entity_id, ts` | `order by ts limit 1 by entity_id` |
| `row_number() over (partition by entity_id order by ts) = 1` | `order by ts limit 1 by entity_id` |
