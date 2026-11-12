-- Rolling payments up to one row per order must not change the money.
-- If the aggregation dropped or double-counted payments, the grand totals differ.
-- Returns one row when they differ; passes when it returns 0 rows.

with staging as (
    select sum(payment_value) as total from {{ ref('stg_payments') }}
),

aggregated as (
    select sum(total_paid) as total from {{ ref('int_order_payments_agg') }}
)

select
    staging.total    as staging_total,
    aggregated.total as aggregated_total
from staging
cross join aggregated
where staging.total <> aggregated.total
