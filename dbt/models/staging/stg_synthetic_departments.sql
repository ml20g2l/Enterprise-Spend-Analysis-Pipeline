select
    cast(source_record_id as char(64)) as source_record_id,
    cast(department_id as char(20)) as department_id,
    trim(department_name) as department_name,
    trim(cost_centre) as cost_centre,
    scenario_id,
    record_origin,
    cast(is_synthetic as unsigned) as is_synthetic
from {{ source('phase3_raw', 'raw_synthetic_department') }}
