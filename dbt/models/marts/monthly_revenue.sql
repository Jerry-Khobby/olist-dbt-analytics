-- Answers: "How is revenue trending month over month?"
-- One row per month. Canceled and unavailable orders are excluded: they did not
-- turn into real sales. The first and last months in the data are partial.

with monthly as (
    select
        date_trunc('month', purchased_at)::date as month,
        count(*)                                as order_count,
        sum(total_paid)                         as revenue
    from {{ ref('fct_orders') }}
    where order_status not in ('canceled', 'unavailable')
    group by 1
)

select
    month,
    order_count,
    revenue,
    round(revenue / nullif(order_count, 0), 2) as avg_order_value,
    lag(revenue) over (order by month)         as previous_month_revenue,
    round(
        100.0 * (revenue - lag(revenue) over (order by month))
        / nullif(lag(revenue) over (order by month), 0),
        1
    )                                          as revenue_growth_pct
from monthly
order by month
