---
name: groupuniqarray-arraysort-flows
description: Model per-entity event flow as `arraySort(groupUniqArray(label))` returning an Array(String), then group by the array directly
type: rule
impact: HIGH
tags: [array-functions, flow-analysis, idiom]
---

# Rule: Flow = `arraySort(groupUniqArray(label))`

## Why

When you want to answer "which combinations of events does each entity see?" (the classic flow-analysis question — e.g. "how many entities had Added but no Removed?"), you have two choices:

1. **Cross-tab of booleans**: `has(types, 1) and not has(types, 2)` → 2^N rows, exponential blowup, awkward filtering.
2. **One sorted array of labels per entity**, then group by the array directly: clean, scales, sortable.

The second one composes naturally with rule 04 (prefixed labels) to put the flow in business order automatically.

## Incorrect

```sql
with flows as (
    select entity_id, groupUniqArray(type) as types
    from postgresql(..., table = 'entity_history')
    group by entity_id
)
select
    has(types, 1) as has_removed,
    has(types, 2) as has_added,
    has(types, 3) as has_declared,
    count() as entities
from flows
group by has_removed, has_added, has_declared
order by has_removed desc, has_added desc, has_declared desc;
```

You get 8 rows (2^3), some of which are unused. Reading the result requires mentally decoding three booleans. Adding a fourth event type doubles the rows.

## Correct

```sql
with
    map(1, '02-Removed', 2, '01-Added', 3, '00-Declared') as types_,
    flows as (
        select entity_id, arraySort(groupUniqArray(types_[type])) as flow
        from postgresql(my_named_connection, database = 'my_database', schema = 'public', table = 'entity_history')
        group by entity_id
    )
select flow, count() as entities
from flows
group by flow
order by flow;
```

Result is N rows where N = number of actually-observed flow combinations (usually << 2^K). Each row reads as "this lifecycle pattern occurred this many times". The `arraySort` + prefixed labels (rule 04) make the array print in lifecycle order: `['00-Declared', '01-Added', '02-Removed']`.

## When to apply

- "How many entities have flow X?"
- "What lifecycle patterns exist?"
- Sanity-checking SCD2 builds — orphan / inconsistent flows surface as their own rows

## When NOT to apply

- When you specifically need numeric counts of each event (not just presence) → keep `count`/`countIf`
- When event order within an entity matters → use a sequence aggregation like `groupArray(label)` with `order by ts`, NOT `groupUniqArray` (which throws away order and duplicates)

## Variations

| You want | Use |
|----------|-----|
| Set of distinct labels per entity, unordered | `groupUniqArray(label)` |
| Set of distinct labels per entity, business-ordered | `arraySort(groupUniqArray(label))` |
| Ordered sequence with duplicates (full history) | `groupArray(label)` with proper `order by ts` |
| Top-N most frequent labels per entity | `topK(N)(label)` |

## Group-by-array gotchas

- CH allows `group by` on arrays directly — no need to convert to string.
- `order by` on Array(String) is lexicographic per element — works correctly when each element is prefix-padded (rule 04).
- For diffing flows in downstream queries, treat the array as the natural primary key.
