---
name: dict-helper-macros
description: Prefer Jinja helper macros ({{ has }} / {{ get }} / {{ get_or_null }} / {{ get_or_default }}) over raw dictHas/dictGet/dictGetOrNull/dictGetOrDefault — auto-resolves the schema-qualified dict name, supports tuple-attribute lookup in one call
type: rule
impact: MEDIUM
tags: [dict, jinja, macro, idiom]
---

# Rule: dictionary access via helper macros

## Why

If your dbt-ClickHouse project ships a macro suite wrapping dictionary primitives, prefer those macros over raw `dictGet*` calls. A typical 4-macro suite looks like:

| Macro | Wraps | Returns | When to use |
|---|---|---|---|
| `{{ has(dict, key) }}` | `dictHas` | `Bool` | Factual lookup — is the key in the dict? |
| `{{ get(dict, attr, key) }}` | `dictGet` | Source attribute type | Attribute is guaranteed non-null in the source; missing key returns ClickHouse type-default (epoch for DateTime, 0 for Int, `''` for String) |
| `{{ get_or_null(dict, attr, key) }}` | `dictGetOrNull` | `Nullable(T)` | Lookup may miss — get `NULL` on key absence instead of a confusable default. **Preferred for optional enrichment.** |
| `{{ get_or_default(dict, attr, key, default) }}` | `dictGetOrDefault` | Source attribute type | Need a domain-specific default different from the type-default (e.g. `'Unknown'` instead of `''`) |

Such macros auto-resolve the schema-qualified dictionary name through a `dict_ref()` helper, so you write `'mart__cancellations__dict'` and the macro expands to `dictGet('dbt_mart.mart__cancellations__dict', …)` — no need to hardcode the schema. They also accept a list of attribute names for tuple-lookup in one call:

```sql
{{ get_or_null("dict_name", ["a", "b", "c"], "id") }}
-- → dictGetOrNull('schema.dict_name', ('a', 'b', 'c'), id)
```

One dict round-trip instead of three. Read the tuple result via dot notation: `_t.a`, `_t.b`, `_t.c`.

## How to apply

### New dict access — always use the macros

```sql
-- BAD — raw call, hardcoded or partly-Jinja schema name
dictGet({{ dict_ref('mart__cancellations__dict') }}, 'cancellation_moment', id)

-- GOOD — single-attribute lookup
{{ get_or_null("mart__cancellations__dict", "cancellation_moment", "id") }} as cancelled_at

-- GOOD — tuple-lookup, one round-trip
{{ get_or_null("mart__cancellations__dict",
    ["cancellation_moment", "cancellation_type", "cancellation_owner"], "id") }} as _cancel
-- then read: _cancel.cancellation_moment, _cancel.cancellation_type, _cancel.cancellation_owner
```

### `has` for lifetime flags

```sql
-- BAD — raw dictHas, easy to typo the dict name (no Jinja resolution)
dictHas('dbt_mart.mart__cancellations__dict', id) as is_cancelled

-- GOOD
{{ has("mart__cancellations__dict", "id") }} as is_cancelled
```

### `get_or_null` over `get` when the attribute may be missing

`dictGet` returns the source-attribute-type-default when the key is absent — for `DateTime64(6)` that's `'1970-01-01 00:00:00.000000'`, for `Int32` it's `0`, for `String` it's `''`. These are easy to misread as «real» data in downstream queries. `get_or_null` returns `NULL` instead, which is unambiguous and survives the analyzer.

```sql
-- BAD — cancelled_at = epoch for non-cancelled entities, indistinguishable from a real 1970 record
{{ get("dict", "cancellation_moment", "id") }} as cancelled_at

-- GOOD — NULL when there's no cancellation row, real timestamp when there is
{{ get_or_null("dict", "cancellation_moment", "id") }} as cancelled_at
```

Combined with `{{ has(...) }}` on the same key, you get a self-consistent block: when `is_cancelled = false`, every `*_or_null` companion column is `NULL` by construction.

### Don't wrap `get_or_null` results in `assumeNotNull` / `if(flag, ..., null)`

The macros already produce `Nullable(T)` with the right semantics. Adding `assumeNotNull` or `if(...)` wrapping is double-handling that defeats the macro's contract. If you find yourself writing:

```sql
-- BAD — pointless wrapping; get_or_null already does this
if(is_cancelled,
   {{ get("dict", "cancellation_moment", "id") }},
   null) as cancelled_at
```

…just use `{{ get_or_null(...) }}` directly.

For composite Bool expressions involving Nullable comparisons (`is_cancelled AND cancelled_at < cutoff`), the inferred type will be `Nullable(Bool)` — declare the contract column as `Nullable(Bool)` rather than forcing it to `Bool` via `coalesce(..., false)`. ClickHouse's `false AND null = false` short-circuit means the runtime value is always proper Bool by data invariant.

## Grandfathering

Pre-existing blocks that call `dictGet({{ dict_ref(...) }}, ...)` directly are **not** flagged by this rule. Convert them when you're touching the file for another reason (touch-fix) — not as a standalone refactor. The cost of a sweeping refactor isn't justified for what is purely a stylistic / ergonomic improvement; the cost of a one-block conversion alongside a real change is near-zero.

## See also

- Your project's CLAUDE.md § «Dictionaries» — project-wide rule
- Your project's ADR on dictionary harvest pattern — architectural context
- `macros/utils/get.sql` in your dbt project — the macro implementations + inline usage examples
