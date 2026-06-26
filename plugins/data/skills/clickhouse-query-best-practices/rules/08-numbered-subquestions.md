---
name: numbered-subquestions
description: Keep `(a)` `(b)` sub-queries for the same research thesis in one `.sql` file, separated by `--` and a one-line description
type: rule
impact: MEDIUM
tags: [organisation, comments, research-style]
---

# Rule: One thesis = one file, numbered sub-queries

## Why

A research thesis ("event type X was introduced on date D and now mirrors history type Y in real time") usually requires 2–4 small queries to substantiate:

- (a) Did the event type appear after that date? (headcount before/after)
- (b) After it appeared, does it match history events within minutes? (match-rate)
- (c) Sanity check: distinct entities covered

Splitting these into separate files makes the thesis evidence harder to follow — the reviewer has to open 3 files to verify one claim. Inlining them with `--` separators keeps the whole investigation reproducible from one file.

## Incorrect

```text
research/
├── 04a-event-headcount.sql
├── 04b-event-window.sql
└── 04c-event-distinct.sql
```

The numbers are good (rule 11) but each file is too small. The thesis lives across three files.

## Correct

```text
research/
└── 04-event-window-match.sql
```

Inside:

```sql
-- 04-event-window-match.sql
--
-- Thesis (A4): after event type=125 was introduced (timestamp derived from data),
-- ~80% of Removed events have a corresponding type=125 within 1 minute.
-- Layer: postgres source via postgresql(). Boundary: computed in CTE.

with first_event_of_type_at as (
    select min(created_date) as ts from ch_mirror.entity_events where type = 125
)

-- (a) Headcount of Removed events before/after type=125 introduction
select count() as total_removed,
    countIf(created_at <  (select ts from first_event_of_type_at)) as removed_before_feature,
    countIf(created_at >= (select ts from first_event_of_type_at)) as removed_after_feature
from postgresql(my_named_connection, database = 'my_database', schema = 'public', table = 'entity_history')
where type = 1
;

-- (b) Match-rate by time window
with first_event_of_type_at as (
    select min(created_date) as ts from ch_mirror.entity_events where type = 125
),
history_ as (
    select entity_id, created_at as removed_at
    from postgresql(my_named_connection, database = 'my_database', schema = 'public', table = 'entity_history')
    where type = 1 and created_at >= (select ts from first_event_of_type_at)
    order by created_at limit 1 by entity_id
),
events_ as (
    select entity_id, created_date as event_at
    from ch_mirror.entity_events
    where type = 125
    order by created_date limit 1 by entity_id
)
select ... from history_ left join events_ using (entity_id)
```

## When to apply

- Two or more related queries that share a CTE, share a hypothesis, or sum up to the same conclusion
- Sub-queries that need to be re-run together as the data changes

## When NOT to apply

- Two queries on completely different theses — separate files
- One enormous query that has no natural decomposition — keep it as one (but consider splitting if it's >100 lines)

## Header convention

Every research file starts with:

```sql
-- NN-<short-name>.sql
--
-- Thesis (A<N>): <one-paragraph summary of what is being measured and why>
-- Layer: <postgresql() source / CH mirror / CDC stream>
-- Expected metric: <if from prior analysis>
-- Citation: <link to ticket / wiki page / source enum>
```

Sub-queries below the header are `-- (a)`, `-- (b)`, `-- (c)` with a one-line description each.

## Separating sub-queries

- A single `;` and a blank line between sub-queries
- Each sub-query may define its own `with` CTEs (CH scopes `with` to the next `select … ;`)
- Shared CTEs that span multiple sub-queries: put them once at the very top and let each sub-query reference them (works in `clickhouse-client` / MCP batch if sent as a batch)
