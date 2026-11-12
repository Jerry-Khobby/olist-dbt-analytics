-- customer_id is unique per ORDER; customer_unique_id is the real person.
-- Zip code prefixes stay as text to keep leading zeros (e.g. '01037').
select
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix,
    customer_city,
    customer_state
from {{ source('olist_raw', 'customers') }}
