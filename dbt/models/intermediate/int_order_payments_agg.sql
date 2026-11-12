select
    order_id,
    sum(payment_value)           as total_paid,
    max(payment_installments)    as max_installments,
    count(*)                     as payment_count
from {{ ref('stg_payments') }}
group by order_id