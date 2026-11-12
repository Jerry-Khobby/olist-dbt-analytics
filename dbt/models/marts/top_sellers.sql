-- Answers: "Who are the best and worst sellers by revenue and review score?"
-- One row per seller, with ranks for both.
--
-- Revenue must come from ORDER ITEMS, not fct_orders: one order can contain items
-- from several sellers, so order-level totals can't be split between them.
-- Each order's review is credited to every seller in that order.

with seller_items as (
    select
        i.seller_id,
        i.order_id,
        i.price,
        f.review_score
    from {{ ref('stg_order_items') }} as i
    join {{ ref('fct_orders') }} as f
        on i.order_id = f.order_id
    where f.order_status not in ('canceled', 'unavailable')
),

-- review per seller per order, so an order with 3 items from one seller
-- counts once towards that seller's average, not three times
seller_order_reviews as (
    select distinct seller_id, order_id, review_score
    from seller_items
),

revenue as (
    select
        seller_id,
        count(distinct order_id) as order_count,
        count(*)                 as items_sold,
        sum(price)               as revenue
    from seller_items
    group by seller_id
),

reviews as (
    select
        seller_id,
        count(review_score)              as reviewed_orders,
        round(avg(review_score), 2)      as avg_review_score
    from seller_order_reviews
    group by seller_id
)

select
    s.seller_id,
    s.seller_city,
    s.seller_state,
    r.order_count,
    r.items_sold,
    r.revenue,
    rv.reviewed_orders,
    rv.avg_review_score,
    rank() over (order by r.revenue desc) as revenue_rank,
    -- an average over 2 reviews is noise: only rank sellers with 10+ reviewed orders
    case
        when rv.reviewed_orders >= 10
            then rank() over (
                partition by rv.reviewed_orders >= 10
                order by rv.avg_review_score desc
            )
    end                                   as review_rank
from revenue as r
join {{ ref('dim_sellers') }} as s
    on r.seller_id = s.seller_id
left join reviews as rv
    on r.seller_id = rv.seller_id
