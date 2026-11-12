-- Business rule from the project plan: what the customer paid should equal
-- item prices + freight. A small number of orders are EXPECTED to differ
-- (e.g. installment interest, vouchers), so this test warns instead of failing.
-- Returns the orders that differ by more than 1 cent.

{{ config(severity = 'warn') }}

select
    order_id,
    order_total,
    total_paid,
    total_paid - order_total as difference
from {{ ref('fct_orders') }}
where order_total is not null
  and total_paid is not null
  and abs(total_paid - order_total) > 0.01
