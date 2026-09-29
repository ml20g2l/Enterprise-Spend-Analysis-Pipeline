select d.expense_id
from {{ ref('int_approval_cycles') }} d
join {{ source('phase3_audit', 'fact_synthetic_approval') }} p on d.expense_id = p.expense_id
where d.request_timestamp_utc <> p.request_timestamp_utc
   or d.manager_approval_timestamp_utc <> p.manager_approval_timestamp_utc
   or d.finance_approval_timestamp_utc <> p.finance_approval_timestamp_utc
   or d.payment_timestamp_utc <> p.payment_timestamp_utc
   or d.approval_cycle_hours <> p.approval_cycle_hours
   or d.request_to_payment_hours <> p.request_to_payment_hours
   or d.approval_sla_breached <> p.approval_sla_breached
