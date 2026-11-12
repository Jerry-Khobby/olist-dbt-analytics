{#
  Whole days between two timestamps, as an integer.
  Returns NULL when either side is NULL (e.g. an order that was never delivered).

  Usage:  {{ delivery_days('o.purchased_at', 'o.delivered_at') }}
  Compiles to:  (o.delivered_at::date - o.purchased_at::date)
#}
{% macro delivery_days(start_column, end_column) -%}
    ({{ end_column }}::date - {{ start_column }}::date)
{%- endmacro %}
