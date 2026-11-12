-- One row per payment; an order can have several (e.g. voucher + credit card).
-- Aggregate to one row per order in the intermediate layer before joining.
select
    order_id,
    cast(payment_sequential as integer)   as payment_sequential,
    payment_type,
    cast(payment_installments as integer) as payment_installments,
    cast(payment_value as numeric(12,2))  as payment_value
from {{ source('olist_raw', 'order_payments') }}
