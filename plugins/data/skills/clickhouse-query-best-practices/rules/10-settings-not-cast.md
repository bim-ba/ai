---
name: settings-not-cast
description: Configure null-handling for joins via `settings join_use_nulls = 1` once, not via per-column `nullable()`/`coalesce` casts
type: rule
impact: LOW
tags: [joins, nulls, settings]
---

# Rule: Use SETTINGS, not per-column casts, for null behavior

## Why

By default in ClickHouse, `left join` returns the **default value of the column type** (empty string, 0, zero date) for unmatched rows on the right side — not NULL. This silently turns "no match" into "matched with default value" and is easy to miss.

You can flip the default for the entire query with one setting:

```sql
… settings join_use_nulls = 1
```

— and then `left join` behaves the way every other SQL engine does: unmatched right side returns NULL.

Per-column workarounds (`assumeNotNull(coalesce(t2.col, ...))`, `nullable(t2.col)`) clutter the query and miss columns easily.

## Incorrect

```sql
select t1.entity_id,
    if(t2.event_at = toDateTime64(0, 6), null, t2.event_at) as event_at,  -- magic sentinel
    countIf(t2.entity_id != '00000000-0000-0000-0000-000000000000') as evt_count
from history t1 left join events t2 using (entity_id)
```

`toDateTime64(0, 6)` and the zero-UUID are sentinel-value hacks. Any future column added to the right side needs its own sentinel check.

## Correct

```sql
select t1.entity_id,
    t2.event_at,
    countIf(t2.event_at is not null) as evt_count
from history t1 left join events t2 using (entity_id)
settings join_use_nulls = 1
```

`is not null` works naturally; the right side really is NULL when unmatched.

## When to apply

- Any `left join` / `right join` / `full outer join` where unmatched rows actually exist
- Whenever you want `is null` / `is not null` to mean "did this row match"

## When NOT to apply

- `inner join` only — every row matches by definition, the setting is irrelevant
- Performance-critical hot path with nullable columns slower than fixed-width ones — measure first, but in research queries this is negligible
- When you genuinely want the column to default to "" / 0 (e.g. summing missing groups as 0) — keep the default behavior and skip the setting

## Where to put the setting

End of the query, after `order by` / `limit`:

```sql
select … from a left join b using (k) order by … settings join_use_nulls = 1
```

For batched files with multiple `select`s, the setting applies only to the statement it ends.

## Related settings (research queries)

| Setting | Use |
|---------|-----|
| `join_use_nulls = 1` | NULL for unmatched joined rows (this rule) |
| `max_execution_time = 60` | Hard timeout in seconds — bail on runaway queries |
| `max_memory_usage = '8G'` | Memory cap |
| `max_threads = 16` | Match prod's `max_threads` for fair benchmarking |

Document any non-default `settings` in a comment, especially if it changes correctness.
