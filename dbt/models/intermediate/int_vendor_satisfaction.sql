select
    vendor_id,
    count(*) as response_count,
    cast(avg(overall_rating) as decimal(6,2)) as avg_overall_rating,
    cast(avg(delivery_rating) as decimal(6,2)) as avg_delivery_rating,
    cast(avg(quality_rating) as decimal(6,2)) as avg_quality_rating,
    cast(avg(support_rating) as decimal(6,2)) as avg_support_rating,
    min(response_date) as first_response_date,
    max(response_date) as latest_response_date,
    min(record_origin) as record_origin,
    min(is_synthetic) as is_synthetic
from {{ ref('stg_vendor_satisfaction') }}
group by vendor_id
