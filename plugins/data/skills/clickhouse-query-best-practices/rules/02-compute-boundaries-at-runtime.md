---
name: compute-boundaries-at-runtime
description: Derive boundary/threshold dates from the data itself via a CTE, never hardcode literal release/cutover dates
type: rule
impact: HIGH
tags: [federation, time-bounds, robustness, ddl-drift]
---

# Rule: Compute boundaries at runtime

## Why

Hardcoded boundary dates (e.g. "the day event-type X was introduced") rot silently:

- backend re-deploys the feature → boundary shifts
- a retroactive backfill emits old `type=N` records → boundary moves earlier
- the timezone of the literal mismatches the column's timezone → off-by-N-hours
- a fresh reader of the SQL has no clue where the magic number came from

If the boundary is **a property of the data**, query the data for it.

## Incorrect

```sql
-- "Type=125 was introduced 2025-12-26"
select count() as total,
    countIf(created_at <  toDateTime64('2025-12-26 00:00:00', 6)) as before_feature,
    countIf(created_at >= toDateTime64('2025-12-26 00:00:00', 6)) as after_feature
from postgresql(my_named_connection, database = 'my_database', schema = 'public', table = 'entity_history')
where type = 1
```

If backend backfills a record for an earlier date, this query keeps returning the old split forever. The magic date also has no provenance — six months from now nobody knows where it came from.

## Correct

```sql
with first_event_of_type_at as (
    select min(created_date) as ts
    from ch_mirror.entity_events
    where type = 125
)
select count() as total,
    countIf(created_at <  (select ts from first_event_of_type_at)) as before_feature,
    countIf(created_at >= (select ts from first_event_of_type_at)) as after_feature
from postgresql(my_named_connection, database = 'my_database', schema = 'public', table = 'entity_history')
where type = 1
```

The boundary is *defined* as "the moment the first event of this type occurred". It auto-tracks reality.

## When to apply

- Any "since release X" / "before feature Y" comparison
- Any "active during quarter Q" computation where the quarter is defined by something in the data (first event of partner, first non-null status, …)
- Migration boundaries — `min(event_time) where new_field is not null`

## When NOT to apply

- Time windows pinned to **wall-clock calendar** (e.g. "rolling 30 days from today"): use `now() - interval 30 day`, not data-derived.
- Audit / billing boundaries that must remain **stable across re-runs** (e.g. month-end financial close) — these should be hardcoded *and* commented with the audit ticket.

## Edge cases

- If `min()` may be NULL (empty source), wrap with `coalesce((select ts from cte), toDateTime64('2000-01-01', 6))` or guard with `where ... or (select ts from cte) is null`.
- Aggregate-in-subquery returns a scalar — fine for `<`, `>=`, `=` comparisons. For multi-row joins use a regular `join`.
- Computing the boundary itself can be slow on huge tables — put it on the CH-mirror (rule 06), not on `postgresql()`.

## See also

- Rule 06 (hybrid source selection) — use CH-mirror for the boundary scan on huge tables
