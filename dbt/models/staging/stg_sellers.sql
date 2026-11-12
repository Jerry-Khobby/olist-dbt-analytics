-- Zip code prefixes stay as text to keep leading zeros.
select
    seller_id,
    seller_zip_code_prefix,
    seller_city,
    seller_state
from {{ source('olist_raw', 'sellers') }}
