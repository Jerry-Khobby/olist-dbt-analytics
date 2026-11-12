-- Answers: "Which regions receive orders late, and by how many days?"
-- One row per customer state, using delivered orders only.

select
    customer_state,
    count(*)                                              as delivered_orders,
    count(*) filter (where is_late)                       as late_orders,
    round(100.0 * count(*) filter (where is_late) / count(*), 1) as late_pct,
    round(avg(days_to_deliver), 1)                        as avg_days_to_deliver,
    round(avg(days_late) filter (where is_late), 1)       as avg_days_late_when_late
from {{ ref('fct_orders') }}
where delivered_at is not null
group by customer_state
order by late_pct desc
