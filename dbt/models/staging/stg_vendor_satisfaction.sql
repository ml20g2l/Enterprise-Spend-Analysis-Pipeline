select
    cast(source_record_id as char(64)) as source_record_id,
    cast(response_id as char(20)) as response_id,
    cast(vendor_id as char(20)) as vendor_id,
    cast(response_date as date) as response_date,
    cast(overall_rating as unsigned) as overall_rating,
    cast(delivery_rating as unsigned) as delivery_rating,
    cast(quality_rating as unsigned) as quality_rating,
    cast(support_rating as unsigned) as support_rating,
    response_channel,
    scenario_id,
    record_origin,
    cast(is_synthetic as unsigned) as is_synthetic
from {{ source('phase3_raw', 'raw_synthetic_vendor_satisfaction') }}
