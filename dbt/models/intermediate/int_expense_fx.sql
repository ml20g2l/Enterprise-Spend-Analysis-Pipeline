with non_gbp_candidates as (
    select
        e.expense_id,
        r.fx_rate_id,
        r.rate_date,
        r.rate_to_gbp,
        r.fx_source,
        r.cache_file,
        row_number() over (
            partition by e.expense_id
            order by r.rate_date desc, r.fx_rate_id
        ) as rate_rank
    from {{ ref('stg_synthetic_expenses') }} e
    join {{ ref('stg_fx_rates') }} r
      on r.base_currency = e.original_currency
     and r.quote_currency = 'GBP'
     and r.rate_date <= e.transaction_date
    where e.original_currency <> 'GBP'
),
selected_rates as (
    select *
    from non_gbp_candidates
    where rate_rank = 1
)
select
    e.source_record_id,
    e.expense_id,
    e.transaction_date,
    e.original_amount,
    e.original_currency,
    case when e.original_currency = 'GBP' then cast(1 as decimal(20,10)) else r.rate_to_gbp end as fx_rate_to_gbp,
    case when e.original_currency = 'GBP' then e.transaction_date else r.rate_date end as fx_rate_date,
    cast(round(e.original_amount * case when e.original_currency = 'GBP' then 1 else r.rate_to_gbp end, 2) as decimal(20,2)) as amount_gbp,
    case when e.original_currency = 'GBP' then 'GBP identity rate' else r.fx_source end as fx_source,
    case when e.original_currency = 'GBP' then 'GBP_IDENTITY' else r.cache_file end as fx_cache_file
from {{ ref('stg_synthetic_expenses') }} e
left join selected_rates r on e.expense_id = r.expense_id
