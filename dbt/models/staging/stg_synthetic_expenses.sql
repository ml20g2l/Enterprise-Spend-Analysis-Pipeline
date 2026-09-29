select
    cast(source_record_id as char(64)) as source_record_id,
    cast(expense_id as char(20)) as expense_id,
    cast(transaction_date as date) as transaction_date,
    cast(department_id as char(20)) as department_id,
    cast(vendor_id as char(20)) as vendor_id,
    trim(spend_category) as spend_category,
    trim(description) as description,
    nullif(trim(submitted_contract_id), '') as submitted_contract_id,
    cast(original_amount as decimal(20,2)) as original_amount,
    upper(original_currency) as original_currency,
    trim(payment_method) as payment_method,
    scenario_id,
    generation_seed,
    record_origin,
    cast(is_synthetic as unsigned) as is_synthetic
from {{ source('phase3_raw', 'raw_synthetic_expense') }}
