-- The monthly report must add up to the fact table it was built from.
-- Compares total revenue across all months with the same filter applied to fct_orders.
-- Returns one row when they differ; passes when it returns 0 rows.

with report as (
    select sum(revenue) as total from {{ ref('monthly_revenue') }}
),

fact as (
    select sum(total_paid) as total
    from {{ ref('fct_orders') }}
    where order_status not in ('canceled', 'unavailable')
)

select
    report.total as monthly_revenue_total,
    fact.total   as fct_orders_total
from report
cross join fact
where report.total <> fact.total
