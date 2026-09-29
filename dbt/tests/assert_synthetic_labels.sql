select expense_id as record_id, 'int_synthetic_spend' as model_name
from {{ ref('int_synthetic_spend') }}
where is_synthetic <> 1 or record_origin <> 'synthetic_fictional_company'
union all
select expense_id, 'int_approval_cycles'
from {{ ref('int_approval_cycles') }}
where is_synthetic <> 1 or record_origin <> 'synthetic_fictional_company'
