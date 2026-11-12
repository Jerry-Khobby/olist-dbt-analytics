-- One row per product, with the category name translated to English.
-- Left join: 610 products have no category and 2 categories have no translation;
-- an inner join would silently drop those products.

select
    p.product_id,
    coalesce(
        t.product_category_name_english,  -- English name when a translation exists
        p.product_category_name,          -- otherwise keep the Portuguese name
        'unknown'                         -- product has no category at all
    )                                   as category_name,
    p.product_category_name             as category_name_pt,
    p.product_photos_qty,
    p.product_weight_g,
    p.product_length_cm,
    p.product_height_cm,
    p.product_width_cm
from {{ ref('stg_products') }} as p
left join {{ ref('stg_product_category_translation') }} as t
    on p.product_category_name = t.product_category_name
