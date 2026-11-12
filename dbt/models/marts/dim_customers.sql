-- One row per REAL customer (customer_unique_id), not per customer_id.
-- In the source, a new customer_id is created for every order, so one person
-- who ordered 3 times has 3 customer_ids. Grouping by customer_unique_id fixes that.

with customer_orders as (
    select
        c.customer_unique_id,
        c.customer_zip_code_prefix,
        c.customer_city,
        c.customer_state,
        o.order_id,
        o.purchased_at,
        p.total_paid
    from {{ ref('stg_customers') }} as c
    join {{ ref('stg_orders') }} as o
        on c.customer_id = o.customer_id
    left join {{ ref('int_order_payments_agg') }} as p
        on o.order_id = p.order_id
),

-- A person can use different addresses across orders: keep the most recent one.
latest_address as (
    select
        customer_unique_id,
        customer_zip_code_prefix,
        customer_city,
        customer_state,
        row_number() over (
            partition by customer_unique_id
            order by purchased_at desc, order_id desc
        ) as rn
    from customer_orders
),

order_stats as (
    select
        customer_unique_id,
        count(distinct order_id) as total_orders,
        min(purchased_at)        as first_order_at,
        max(purchased_at)        as last_order_at,
        sum(total_paid)          as lifetime_paid
    from customer_orders
    group by customer_unique_id
)

select
    s.customer_unique_id,
    a.customer_zip_code_prefix,
    a.customer_city,
    a.customer_state,
    s.total_orders,
    s.first_order_at,
    s.last_order_at,
    s.lifetime_paid,
    s.total_orders > 1 as is_repeat_customer
from order_stats as s
join latest_address as a
    on s.customer_unique_id = a.customer_unique_id
   and a.rn = 1
