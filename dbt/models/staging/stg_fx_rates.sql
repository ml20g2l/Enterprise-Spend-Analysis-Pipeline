select
    cast(fx_rate_id as char(64)) as fx_rate_id,
    cast(rate_date as date) as rate_date,
    upper(base_currency) as base_currency,
    upper(quote_currency) as quote_currency,
    cast(rate as decimal(20,10)) as rate_to_gbp,
    fx_source,
    cache_file
from {{ source('phase3_raw', 'raw_fx_rate') }}
