select
    e.source_record_id,
    e.expense_id,
    e.transaction_date,
    e.department_id,
    e.vendor_id,
    e.spend_category,
    e.description,
    e.payment_method,
    c.submitted_contract_id,
    c.matched_contract_id,
    c.contract_compliance_status,
    c.is_contract_compliant,
    f.original_amount,
    f.original_currency,
    f.fx_rate_to_gbp,
    f.fx_rate_date,
    f.amount_gbp,
    f.fx_source,
    f.fx_cache_file,
    e.scenario_id,
    e.generation_seed,
    e.record_origin,
    e.is_synthetic
from {{ ref('stg_synthetic_expenses') }} e
join {{ ref('int_expense_contract_match') }} c on e.expense_id = c.expense_id
join {{ ref('int_expense_fx') }} f on e.expense_id = f.expense_id
