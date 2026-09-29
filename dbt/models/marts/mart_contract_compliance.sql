select
    date_format(transaction_date, '%Y-%m-01') as spend_month,
    department_id,
    spend_category,
    contract_compliance_status,
    is_contract_compliant,
    count(*) as expense_count,
    cast(sum(amount_gbp) as decimal(24,2)) as amount_gbp,
    count(distinct vendor_id) as vendor_count,
    min(record_origin) as record_origin,
    min(is_synthetic) as is_synthetic
from {{ ref('int_synthetic_spend') }}
group by
    date_format(transaction_date, '%Y-%m-01'),
    department_id,
    spend_category,
    contract_compliance_status,
    is_contract_compliant
