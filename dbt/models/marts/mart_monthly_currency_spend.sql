select
    date_format(transaction_date, '%Y-%m-01') as spend_month,
    original_currency,
    count(*) as expense_count,
    cast(sum(original_amount) as decimal(24,2)) as original_amount,
    cast(sum(amount_gbp) as decimal(24,2)) as amount_gbp,
    cast(avg(fx_rate_to_gbp) as decimal(20,10)) as avg_fx_rate_to_gbp,
    min(fx_rate_date) as earliest_fx_rate_date,
    max(fx_rate_date) as latest_fx_rate_date,
    min(record_origin) as record_origin,
    min(is_synthetic) as is_synthetic
from {{ ref('int_synthetic_spend') }}
group by date_format(transaction_date, '%Y-%m-01'), original_currency
