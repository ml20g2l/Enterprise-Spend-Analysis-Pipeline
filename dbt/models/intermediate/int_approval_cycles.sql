with pivoted as (
    select
        expense_id,
        max(case when event_type = 'purchase_request' then event_timestamp_utc end) as request_timestamp_utc,
        max(case when event_type = 'manager_approval' then event_timestamp_utc end) as manager_approval_timestamp_utc,
        max(case when event_type = 'finance_approval' then event_timestamp_utc end) as finance_approval_timestamp_utc,
        max(case when event_type = 'payment' then event_timestamp_utc end) as payment_timestamp_utc,
        count(*) as event_count,
        min(scenario_id) as scenario_id,
        min(record_origin) as record_origin,
        min(is_synthetic) as is_synthetic
    from {{ ref('stg_synthetic_approval_events') }}
    group by expense_id
)
select
    expense_id,
    request_timestamp_utc,
    manager_approval_timestamp_utc,
    finance_approval_timestamp_utc,
    payment_timestamp_utc,
    cast(timestampdiff(microsecond, request_timestamp_utc, finance_approval_timestamp_utc) / 3600000000 as decimal(12,2)) as approval_cycle_hours,
    cast(timestampdiff(microsecond, request_timestamp_utc, payment_timestamp_utc) / 3600000000 as decimal(12,2)) as request_to_payment_hours,
    cast({{ var('approval_sla_hours') }} as decimal(12,2)) as approval_sla_hours,
    case
        when timestampdiff(microsecond, request_timestamp_utc, finance_approval_timestamp_utc) / 3600000000 > {{ var('approval_sla_hours') }} then 1
        else 0
    end as approval_sla_breached,
    event_count,
    scenario_id,
    record_origin,
    is_synthetic
from pivoted
