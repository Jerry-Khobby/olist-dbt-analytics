-- fct_orders must have exactly one row per order in stg_orders.
-- More rows means a join fanned out; fewer means a join dropped orders.
-- Returns one row when the counts differ; passes when it returns 0 rows.

with staging as (
    select count(*) as n from {{ ref('stg_orders') }}
),

fact as (
    select count(*) as n from {{ ref('fct_orders') }}
)

select
    staging.n as stg_orders_rows,
    fact.n    as fct_orders_rows
from staging
cross join fact
where staging.n <> fact.n
