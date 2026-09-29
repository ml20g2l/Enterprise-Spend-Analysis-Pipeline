select
    cast(source_record_id as char(64)) as source_record_id,
    cast(event_id as char(40)) as event_id,
    cast(expense_id as char(20)) as expense_id,
    cast(event_sequence as unsigned) as event_sequence,
    lower(event_type) as event_type,
    cast(event_timestamp_utc as datetime(6)) as event_timestamp_utc,
    lower(actor_role) as actor_role,
    scenario_id,
    record_origin,
    cast(is_synthetic as unsigned) as is_synthetic
from {{ source('phase3_raw', 'raw_synthetic_approval_event') }}
