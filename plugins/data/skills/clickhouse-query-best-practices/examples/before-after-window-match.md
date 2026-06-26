# Example: Event-type window-match

**Thesis**: «`entity_events.type=125` mirrors `entity_history.type=1` after the type=125 feature release. Measure the time-distance between matched events.»

**Rules applied in the refactor**: 01 (cte-wrap), 02 (runtime boundary), 03 (limit 1 by), 06 (hybrid sources), 10 (settings).

## BEFORE (original — hardcoded date, exploded join, sentinel hacks)

```sql
-- (a) Headcount before/after type=125 introduction — HARDCODED date
SELECT
    count()                                                       AS total_removed,
    countIf(created_at <  toDateTime64('2025-12-26 00:00:00', 6)) AS removed_before_125,
    countIf(created_at >= toDateTime64('2025-12-26 00:00:00', 6)) AS removed_after_125
FROM postgresql(my_named_connection, database = 'my_database', schema = 'public', table = 'entity_history')
WHERE type = 1;

-- (b) Match-rate — cross-product join with sentinel comparisons
WITH removed AS (
    SELECT entity_id, created_at AS removed_at
    FROM postgresql(..., table = 'entity_history')
    WHERE type = 1 AND created_at >= toDateTime64('2025-12-26 00:00:00', 6)
),
events_125 AS (
    SELECT entity_id, created_date AS event_at
    FROM postgresql(..., table = 'large_event_table')   -- large table through federation!
    WHERE type = 125
),
joined AS (
    SELECT r.entity_id, r.removed_at,
        minIf(abs(date_diff('second', r.removed_at, e.event_at)), e.event_at != toDateTime64(0, 6)) AS min_diff_s,
        countIf(e.event_at != toDateTime64(0, 6)) AS evt_count
    FROM removed r LEFT JOIN events_125 e ON r.entity_id = e.entity_id
    GROUP BY r.entity_id, r.removed_at
)
SELECT count() AS total, ...
FROM joined SETTINGS join_use_nulls = 0;
```

**Issues**:

1. **Hardcoded `2025-12-26`** — when did this feature ship? Where's the provenance? If backend ships a retroactive backfill, the number quietly shifts.
2. **Large event table through `postgresql()`** — that's a high-volume table. The query holds postgres open for minutes.
3. **`LEFT JOIN` with no dedup + min/aggregate inside the join** — a cross product of N × M for entities with multiple Removed and multiple type=125 events. Result is correct but expensive.
4. **Sentinel hack** — `event_at != toDateTime64(0, 6)` because `join_use_nulls = 0` turns unmatched rows into zero-dates instead of NULL. Per-column workaround.
5. **Mixed-case keywords**.

## AFTER (refactored — runtime boundary, hybrid source, dedup → 1:1 join)

```sql
with
    -- Boundary derived from the data — no magic date.
    first_event_125_at as (
        select min(created_date) as ts
        from ch_mirror.entity_events  -- CH mirror; rule 06 — large fact table
        where type = 125
    ),

    -- One earliest Removed per entity.
    history_ as (
        select entity_id, created_at as removed_at
        from postgresql(
            my_named_connection,
            database = 'my_database', schema = 'public',
            table = 'entity_history'
        )
        where type = 1 and created_at >= (select ts from first_event_125_at)
        order by created_at
        limit 1 by entity_id  -- rule 03
    ),

    -- One earliest type=125 per entity (from CH mirror).
    events_ as (
        select entity_id, created_date as event_at
        from ch_mirror.entity_events
        where type = 125
        order by created_date
        limit 1 by entity_id  -- rule 03
    ),

    -- 1:1 join (both sides deduped).
    joined as (
        select
            coalesce(h.entity_id, e.entity_id) as entity_id,
            h.removed_at,
            e.event_at,
            dateDiff('second', h.removed_at, e.event_at) as diff
        from history_ h
        left join events_ e using (entity_id)
    )

select
    multiIf(
        diff is null,    'no_match',
        diff <= 60,      '0-60s',
        diff <= 300,     '61-300s',
        diff <= 3600,    '301-3600s',
        diff <= 86400,   '3601-86400s',
        '>86400s'
    ) as bucket,
    count() as cnt
from joined
group by bucket
order by bucket
settings join_use_nulls = 1
;
```

**What the rules bought us**:

- **Rule 02** (runtime boundary): the hardcoded date literal is gone. The CTE `first_event_125_at` *defines* the cutover as «the earliest type=125 we have seen», so the answer auto-tracks reality.
- **Rule 06** (hybrid sources): `entity_events` (huge fact) → CH mirror. `entity_history` (small) → PG via `postgresql()`. Both `where`-filters happen near the source for predicate push-down.
- **Rule 03** (`limit 1 by entity_id`): both sides deduped to one earliest row → the join is 1:1, no cross product, `diff` is a single scalar per entity.
- **Rule 10** (`settings join_use_nulls = 1`): unmatched right side returns NULL, and we test `diff is null` cleanly. No sentinel comparisons needed.

## Example result shape

| bucket | cnt |
|--------|-----|
| 0-60s | ~20 000 |
| 3601-86400s | ~250 |

— Most entities with a Removed event after the feature release also have a matching type=125 within 60 seconds. The remainder appear within 1h–24h (likely async backfill). Zero `no_match` rows indicates clean mirror coverage.

## Comparison vs original

| Metric | Original (cross-product) | Refactored (dedup-then-join) |
|--------|--------------------------|------------------------------|
| Join type | N × M cross-product | 1:1 (both sides deduped) |
| Large-table source | `postgresql()` — full scan | CH mirror — local scan |
| Boundary | Hardcoded date literal | Derived from data |
| PG round-trips | 2+ (incl. large event table!) | 1 |
| Null-handling | Sentinel `!= toDateTime64(0, 6)` | `diff is null` via `join_use_nulls = 1` |

Both interpretations (cross-product vs dedup-then-join) are valid for different questions. Always document the unit of analysis (per-event-pair vs per-entity) in the thesis comment at the top.

## Rule-by-rule wins

| Rule | Saved |
|------|-------|
| 02 (runtime boundary) | One hardcoded magic date literal |
| 03 (limit 1 by) | Cross-product join → 1:1 join |
| 06 (hybrid source) | A large-table PG remote scan |
| 10 (`settings join_use_nulls`) | Sentinel comparisons in multiple lines |
| 11 (lowercase) | Style consistency |
