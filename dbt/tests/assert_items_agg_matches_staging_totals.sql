-- Rolling order items up to one row per order must not change item counts or money.
-- Compares the grand totals before and after aggregation.
-- Returns one row when anything differs; passes when it returns 0 rows.

with staging as (
    select
        count(*)           as item_count,
        sum(price)         as items_total,
        sum(freight_value) as freight_total
    from {{ ref('stg_order_items') }}
),

aggregated as (
    select
        sum(item_count)    as item_count,
        sum(items_total)   as items_total,
        sum(freight_total) as freight_total
    from {{ ref('int_order_items_agg') }}
)

select
    staging.item_count    as staging_items,    aggregated.item_count    as aggregated_items,
    staging.items_total   as staging_price,    aggregated.items_total   as aggregated_price,
    staging.freight_total as staging_freight,  aggregated.freight_total as aggregated_freight
from staging
cross join aggregated
where staging.item_count    <> aggregated.item_count
   or staging.items_total   <> aggregated.items_total
   or staging.freight_total <> aggregated.freight_total
