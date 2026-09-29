select
    s.department_id,
    d.department_name,
    d.cost_centre,
    count(*) as expense_count,
    cast(sum(s.amount_gbp) as decimal(24,2)) as amount_gbp,
    cast(avg(s.amount_gbp) as decimal(20,2)) as avg_expense_gbp,
    count(distinct s.vendor_id) as vendor_count,
    sum(case when s.is_contract_compliant = 1 then 1 else 0 end) as compliant_expense_count,
    cast(100.0 * sum(case when s.is_contract_compliant = 1 then 1 else 0 end) / count(*) as decimal(7,2)) as contract_compliance_pct,
    min(s.record_origin) as record_origin,
    min(s.is_synthetic) as is_synthetic
from {{ ref('int_synthetic_spend') }} s
join {{ ref('stg_synthetic_departments') }} d on s.department_id = d.department_id
group by s.department_id, d.department_name, d.cost_centre
