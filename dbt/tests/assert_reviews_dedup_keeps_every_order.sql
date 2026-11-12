-- Deduplicating reviews must remove duplicate reviews, never whole orders.
-- Returns every order that had a review in staging but is missing after dedup.
-- Passes when it returns 0 rows.

select distinct r.order_id
from {{ ref('stg_reviews') }} as r
where not exists (
    select 1
    from {{ ref('int_order_reviews_dedup') }} as d
    where d.order_id = r.order_id
)
