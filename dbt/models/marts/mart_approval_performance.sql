select
    date_format(s.transaction_date, '%Y-%m-01') as spend_month,
    s.department_id,
    count(*) as approval_request_count,
    cast(avg(a.approval_cycle_hours) as decimal(12,2)) as avg_approval_cycle_hours,
    cast(avg(a.request_to_payment_hours) as decimal(12,2)) as avg_request_to_payment_hours,
    sum(a.approval_sla_breached) as sla_breach_count,
    cast(100.0 * sum(a.approval_sla_breached) / count(*) as decimal(7,2)) as sla_breach_pct,
    min(s.record_origin) as record_origin,
    min(s.is_synthetic) as is_synthetic
from {{ ref('int_approval_cycles') }} a
join {{ ref('int_synthetic_spend') }} s on a.expense_id = s.expense_id
group by date_format(s.transaction_date, '%Y-%m-01'), s.department_id
