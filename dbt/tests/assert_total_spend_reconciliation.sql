select
    cast(sum(amount_gbp) as decimal(24,2)) as actual_amount_gbp
from {{ ref('int_synthetic_spend') }}
having cast(sum(amount_gbp) as decimal(24,2)) <> cast({{ var('expected_amount_gbp') }} as decimal(24,2))
