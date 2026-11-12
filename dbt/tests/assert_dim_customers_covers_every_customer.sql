-- dim_customers must contain exactly one row for every distinct real customer
-- in staging: no customer lost by the joins, none duplicated.
-- Returns one row when the counts differ; passes when it returns 0 rows.

with staging as (
    select count(distinct customer_unique_id) as n from {{ ref('stg_customers') }}
),

dim as (
    select count(*) as n from {{ ref('dim_customers') }}
)

select
    staging.n as distinct_customers_in_staging,
    dim.n     as dim_customers_rows
from staging
cross join dim
where staging.n <> dim.n
