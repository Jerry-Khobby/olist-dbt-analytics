-- One row per order: the central fact table. Every per-order number lives here,
-- and the reporting marts (monthly_revenue, delivery_delay_by_state) build on it.
--
-- All joins are LEFT joins from stg_orders, so no order is ever dropped:
-- 775 orders have no items, 1 has no payment, and 768 have no review.
-- The intermediate models are one row per order, so no join can fan out.

select
    o.order_id,
    o.customer_id,
    c.customer_unique_id,
    c.customer_state,  -- the delivery address state for THIS order
    o.order_status,

    -- dates
    o.purchased_at,
    o.approved_at,
    o.delivered_at,
    o.estimated_delivery_at,

    -- items and money
    it.item_count,
    it.items_total,
    it.freight_total,
    it.order_total,
    py.total_paid,
    py.payment_count,

    -- review
    rv.review_score,

    -- delivery metrics (NULL when the order was never delivered)
    {{ delivery_days('o.purchased_at', 'o.delivered_at') }}          as days_to_deliver,
    {{ delivery_days('o.estimated_delivery_at', 'o.delivered_at') }} as days_late,  -- negative = early
    {{ delivery_days('o.estimated_delivery_at', 'o.delivered_at') }} > 0 as is_late

from {{ ref('stg_orders') }} as o
left join {{ ref('stg_customers') }}           as c  on o.customer_id = c.customer_id
left join {{ ref('int_order_items_agg') }}     as it on o.order_id = it.order_id
left join {{ ref('int_order_payments_agg') }}  as py on o.order_id = py.order_id
left join {{ ref('int_order_reviews_dedup') }} as rv on o.order_id = rv.order_id
