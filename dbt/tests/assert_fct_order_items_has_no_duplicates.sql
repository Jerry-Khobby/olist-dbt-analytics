-- An incremental model must never duplicate rows when it re-processes the lookback
-- window. Each (order_id, order_item_id) pair must appear exactly once.
-- Returns duplicated pairs; passes when it returns 0 rows.

select
    order_id,
    order_item_id,
    count(*) as copies
from {{ ref('fct_order_items') }}
group by order_id, order_item_id
having count(*) > 1
