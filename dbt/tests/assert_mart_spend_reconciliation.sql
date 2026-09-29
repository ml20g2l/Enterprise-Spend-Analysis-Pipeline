select 'department_mart' as failed_mart
where (select cast(sum(amount_gbp) as decimal(24,2)) from {{ ref('mart_department_spend') }})
   <> (select cast(sum(amount_gbp) as decimal(24,2)) from {{ ref('int_synthetic_spend') }})
union all
select 'currency_mart'
where (select cast(sum(amount_gbp) as decimal(24,2)) from {{ ref('mart_monthly_currency_spend') }})
   <> (select cast(sum(amount_gbp) as decimal(24,2)) from {{ ref('int_synthetic_spend') }})
