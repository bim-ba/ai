# Example: Orphan Removed flow analysis

**Thesis**: «A significant fraction of records in `entity_history` have `Removed` (type=1) without a preceding `Added` (type=2). What is the full lifecycle distribution?»

**Rules applied in the refactor**: 01 (cte-wrap), 04 (map-with-prefix), 05 (groupuniqarray + arraysort), 07 (citation), 11 (lowercase).

## BEFORE (original — too verbose, hard-to-extend cross-tab)

```sql
WITH hist AS (
    SELECT entity_id, foreign_id, type
    FROM postgresql(
        my_named_connection,
        database='my_database',
        schema='public',
        table='entity_history'
    )
),
pairs AS (
    SELECT
        entity_id,
        foreign_id,
        groupUniqArray(type) AS types
    FROM hist
    GROUP BY entity_id, foreign_id
)
SELECT
    has(types, 1) AS has_removed,
    has(types, 2) AS has_added,
    has(types, 3) AS has_declared,
    count()       AS pairs
FROM pairs
GROUP BY has_removed, has_added, has_declared
ORDER BY has_removed DESC, has_added DESC, has_declared DESC;
```

**Issues**:

- Output is 2^3 = 8 rows of booleans — eight ways to be missing or present, hard to read.
- Result row order is alphabetic-ish on booleans, not lifecycle order.
- Adding a 4th event type doubles the row count to 16, half empty.
- `groupUniqArray(type)` returns ints — what is `1`? Reader has to remember.
- Mixed-case keywords.

## AFTER (refactored — single sorted-array group, business order)

```sql
with
    -- src/Domain/YourProject/Enums/EntityHistoryType.cs
    map(
        1, '02-Removed',
        2, '01-Added',
        3, '00-Declared'
    ) as types_,

    flows as (
        select
            entity_id,
            arraySort(groupUniqArray(types_[type])) as flow
        from postgresql(
            my_named_connection,
            database = 'my_database',
            schema = 'public',
            table = 'entity_history'
        )
        group by entity_id
    )

select flow, count()
from flows
group by flow
order by flow
;
```

**What the rules bought us**:

- **Rule 04** (`map(int, 'NN-Name')` + prefix): readable labels in sorted business order.
- **Rule 05** (`arraySort(groupUniqArray(...))`): one column `flow` that is the entire lifecycle pattern; the result has at most N rows where N = combinations actually observed.
- **Rule 07** (citation in comment): one line at the top points the reader to the source enum.
- **Rule 11** (lowercase, alignment): matches sqlfmt convention.

## Example result shape

| flow | count() |
|------|---------|
| `['00-Declared','01-Added','02-Removed']` | 9 363 |
| `['00-Declared','02-Removed']` | 2 683 |
| `['01-Added']` | 9 261 |
| `['01-Added','02-Removed']` | 5 965 |
| `['02-Removed']` | 14 686 |

Five rows, instantly readable: **lifecycle pattern → headcount**.

## Comparison vs original

| Metric | Original (boolean cross-tab) | Refactored (flow array) |
|--------|------------------------------|--------------------------|
| Output shape | 8-row boolean cross-tab | N-row sorted-array pattern (only observed combos) |
| Readability | Must decode 3 booleans per row | Each row is a self-describing lifecycle string |
| Extensibility | New event type → 2× row count | New event type → one more entry in `map(...)` |

## Rule-by-rule wins

| Rule | Saved | Why |
|------|-------|-----|
| 01 (cte-wrap) | Federation calls wrapped once | Prevents round-trip duplication |
| 04 (map + prefix) | Magic-number integer comparisons | Enum is now self-documenting |
| 05 (arraysort+groupuniqarray) | Boolean cross-tab → natural flow shape | Result is compact and sortable |
| 07 (cite source) | Enum lookup burden on the reader | One comment line removes it |
| 11 (lowercase) | Style consistency | Matches sqlfmt convention |
