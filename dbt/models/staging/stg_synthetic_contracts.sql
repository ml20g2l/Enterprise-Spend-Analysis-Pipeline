select
    cast(source_record_id as char(64)) as source_record_id,
    cast(contract_id as char(20)) as contract_id,
    cast(vendor_id as char(20)) as vendor_id,
    cast(contract_start_date as date) as contract_start_date,
    cast(contract_end_date as date) as contract_end_date,
    cast(contract_value_gbp as decimal(20,2)) as contract_value_gbp,
    trim(approved_category) as approved_category,
    lower(contract_status) as contract_status,
    scenario_id,
    record_origin,
    cast(is_synthetic as unsigned) as is_synthetic
from {{ source('phase3_raw', 'raw_synthetic_contract') }}
