{#
  INCREMENTAL MODEL: one row per item sold.

  First run (or `dbt run --full-refresh`): builds the whole table.
  Later runs: only re-processes orders purchased in the last N days
  (var `incremental_lookback_days`, default 3) and merges them in:
    - delete+insert removes existing rows with the same (order_id, order_item_id)
      and inserts the fresh versions, so updated orders (e.g. a status change)
      are corrected instead of duplicated.
    - the lookback window catches late-arriving data for recent orders.
#}

{{
    config(
        materialized = 'incremental',
        unique_key = ['order_id', 'order_item_id'],
        incremental_strategy = 'delete+insert'
    )
}}

select
    i.order_id,
    i.order_item_id,
    i.product_id,
    i.seller_id,
    o.customer_id,
    o.order_status,
    o.purchased_at,
    i.price,
    i.freight_value,
    i.price + i.freight_value as item_total
from {{ ref('stg_order_items') }} as i
join {{ ref('stg_orders') }} as o
    on i.order_id = o.order_id

{% if is_incremental() %}
-- {{ this }} is this model's own existing table in the warehouse.
where o.purchased_at >= (
    select max(purchased_at) - interval '{{ var("incremental_lookback_days", 3) }} days'
    from {{ this }}
)
{% endif %}
