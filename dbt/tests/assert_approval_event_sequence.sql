with per_expense as (
    select
        expense_id,
        count(*) as event_count,
        count(distinct event_sequence) as sequence_count,
        sum(event_type = 'purchase_request' and event_sequence = 1) as request_ok,
        sum(event_type = 'manager_approval' and event_sequence = 2) as manager_ok,
        sum(event_type = 'finance_approval' and event_sequence = 3) as finance_ok,
        sum(event_type = 'payment' and event_sequence = 4) as payment_ok
    from {{ ref('stg_synthetic_approval_events') }}
    group by expense_id
)
select expense_id
from per_expense
where event_count <> 4
   or sequence_count <> 4
   or request_ok <> 1
   or manager_ok <> 1
   or finance_ok <> 1
   or payment_ok <> 1
