---
name: map-with-sortable-prefix
description: Translate integer enums via `map(N, 'NN-Name')` literal with zero-padded numeric prefix so lexicographic sort matches business order
type: rule
impact: HIGH
tags: [enum, readability, sorting, idiom]
---

# Rule: `map(int, 'NN-Name')` with sortable prefix

## Why

When you translate an integer enum (`type = 1, 2, 3, …`) into a label, two things matter:

1. **Readability**: future readers see `'Removed'`, not `1`.
2. **Sort order**: when you later `group by label` and `order by label`, you want business order — not alphabetical.

Solution: prefix the label with a zero-padded integer in the **business order you want sorted**. Then plain `arraySort` / `order by` gives the right sequence.

## Why not `case when` / `multiIf`

`case when type = 1 then 'Removed' when type = 2 then 'Added' …` works but:

- spreads the mapping across the query
- forces you to remember the mapping every time
- alphabetic sort of unprefixed names is wrong: `'Added' < 'Declared' < 'Removed'`, but business order may be `Declared → Added → Removed`

`map()` literal collects the mapping in one place, near the top. Prefix encodes order.

## Incorrect

```sql
-- magic numbers everywhere
select count() from t
where type = 1                 -- what is 1?
   or type = 3;                -- and 3?

-- alphabetical order is wrong
select multiIf(type = 1, 'Removed', type = 2, 'Added', type = 3, 'Declared', 'unknown') as label,
       count()
from t
group by label
order by label;
-- returns: Added, Declared, Removed  ← alphabetic, NOT business-order
```

## Correct

```sql
with
    -- path/to/YourEnum.cs  (or: ref('stg__your_model') / wiki: domain/lifecycle)
    map(
        1, '02-Removed',
        2, '01-Added',
        3, '00-Declared'
    ) as types_

select types_[type] as label, count()
from postgresql(my_named_connection, database = 'my_database', schema = 'public', table = 'entity_history')
group by label
order by label
-- returns: 00-Declared, 01-Added, 02-Removed  ← lifecycle order, correct
```

## When to apply

- Any enum that has a **natural business order** (lifecycle, severity, layer)
- When you'll `group by` the label or include it in an `arraySort` (see rule 05)
- When you want the label to be self-documenting

## When NOT to apply

- One-off projection where order doesn't matter — plain `multiIf` is fine
- High-cardinality lookups (>50 values) — make a dictionary instead

## Numbering convention

| Style | When |
|-------|------|
| `01-`, `02-`, …, `99-` | ≤99 enum values, single lifecycle dimension |
| `0001-`, `0002-`, … | Larger ranges; rare |
| `A-`, `B-`, `C-` | Alphabetic categories where letters carry meaning |

Always zero-pad to the max width — `9` and `10` lex-sort wrong unless you write `09` and `10`.

## Citing the source enum

Always include the enum source as a leading comment in the CTE so the reader can verify the mapping. See rule 07.
