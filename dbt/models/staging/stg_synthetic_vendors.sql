select
    cast(source_record_id as char(64)) as source_record_id,
    cast(vendor_id as char(20)) as vendor_id,
    trim(vendor_name) as vendor_name,
    trim(country) as country,
    upper(default_currency) as default_currency,
    trim(primary_category) as primary_category,
    lower(risk_tier) as risk_tier,
    scenario_id,
    record_origin,
    cast(is_synthetic as unsigned) as is_synthetic
from {{ source('phase3_raw', 'raw_synthetic_vendor') }}
