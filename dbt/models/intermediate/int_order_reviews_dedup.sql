with ranked as (
    select
        *,
        row_number() over (
            partition by order_id
            -- nulls last: Postgres sorts NULLs first on DESC by default.
            -- review_created_at and review_id break ties so the result is deterministic.
            order by review_answered_at desc nulls last,
                     review_created_at desc nulls last,
                     review_id desc
        ) as rn
    from {{ ref('stg_reviews') }}
)
select
    order_id,
    review_id,
    review_score,
    review_comment_message is not null as has_comment,
    review_created_at,
    review_answered_at
from ranked
where rn = 1