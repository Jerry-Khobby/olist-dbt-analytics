-- Answers: "How many customers buy more than once?"
-- A single summary row, built on dim_customers (one row per real customer).

select
    count(*)                                         as total_customers,
    count(*) filter (where is_repeat_customer)       as repeat_customers,
    round(
        100.0 * count(*) filter (where is_repeat_customer) / count(*),
        2
    )                                                as repeat_rate_pct,
    round(avg(total_orders), 3)                      as avg_orders_per_customer
from {{ ref('dim_customers') }}
