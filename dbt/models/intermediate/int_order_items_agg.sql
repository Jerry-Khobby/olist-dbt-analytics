-- One row per order. Like payments, items must be aggregated BEFORE joining to
-- orders: joining stg_order_items directly would repeat each order once per item
-- and inflate any order-level number (join fan-out).
select
    order_id,
    count(*)                          as item_count,
    count(distinct product_id)        as distinct_products,
    count(distinct seller_id)         as distinct_sellers,
    sum(price)                        as items_total,
    sum(freight_value)                as freight_total,
    sum(price) + sum(freight_value)   as order_total
from {{ ref('stg_order_items') }}
group by order_id
