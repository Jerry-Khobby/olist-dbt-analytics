{#
  Jinja loop: instead of writing one sum(case ...) line per payment type by hand,
  loop over a list. Adding a new payment type is a one-word change to this list.
#}
{%- set payment_types = ['credit_card', 'boleto', 'voucher', 'debit_card'] -%}

select
    order_id,
    sum(payment_value)           as total_paid,
    max(payment_installments)    as max_installments,
    count(*)                     as payment_count,

    -- one column per payment type, e.g. credit_card_amount
    {% for payment_type in payment_types %}
    sum(case when payment_type = '{{ payment_type }}' then payment_value else 0 end)
        as {{ payment_type }}_amount
        {%- if not loop.last %},{% endif %}
    {% endfor %}

from {{ ref('stg_payments') }}
group by order_id
