-- Not deduplicated here: review_id repeats and some orders have several reviews.
-- Keep the latest review per order in the intermediate layer.
select
    review_id,
    order_id,
    cast(review_score as integer)              as review_score,
    review_comment_title,
    review_comment_message,
    cast(review_creation_date as timestamp)    as review_created_at,
    cast(review_answer_timestamp as timestamp) as review_answered_at
from {{ source('olist_raw', 'order_reviews') }}
