select d.expense_id
from {{ ref('int_synthetic_spend') }} d
join {{ source('phase3_audit', 'fact_synthetic_spend') }} p on d.expense_id = p.expense_id
where d.amount_gbp <> p.amount_gbp
   or d.fx_rate_to_gbp <> p.fx_rate_to_gbp
   or d.fx_rate_date <> p.fx_rate_date
   or not (d.matched_contract_id <=> p.matched_contract_id)
   or d.contract_compliance_status <> p.contract_compliance_status
   or d.is_contract_compliant <> p.is_contract_compliant
union all
select coalesce(d.expense_id, p.expense_id)
from {{ ref('int_synthetic_spend') }} d
right join {{ source('phase3_audit', 'fact_synthetic_spend') }} p on d.expense_id = p.expense_id
where d.expense_id is null
union all
select d.expense_id
from {{ ref('int_synthetic_spend') }} d
left join {{ source('phase3_audit', 'fact_synthetic_spend') }} p on d.expense_id = p.expense_id
where p.expense_id is null
