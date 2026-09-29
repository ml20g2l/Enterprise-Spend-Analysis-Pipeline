with spend as (
    select
        vendor_id,
        count(*) as expense_count,
        cast(sum(amount_gbp) as decimal(24,2)) as amount_gbp,
        cast(avg(amount_gbp) as decimal(20,2)) as avg_expense_gbp,
        sum(case when is_contract_compliant = 1 then 1 else 0 end) as compliant_expense_count
    from {{ ref('int_synthetic_spend') }}
    group by vendor_id
)
select
    v.vendor_id,
    v.vendor_name,
    v.country,
    v.primary_category,
    v.risk_tier,
    coalesce(s.expense_count, 0) as expense_count,
    cast(coalesce(s.amount_gbp, 0) as decimal(24,2)) as amount_gbp,
    s.avg_expense_gbp,
    s.compliant_expense_count,
    case when s.expense_count > 0
        then cast(100.0 * s.compliant_expense_count / s.expense_count as decimal(7,2))
        else null end as contract_compliance_pct,
    q.response_count,
    q.avg_overall_rating,
    q.avg_delivery_rating,
    q.avg_quality_rating,
    q.avg_support_rating,
    v.record_origin,
    v.is_synthetic
from {{ ref('stg_synthetic_vendors') }} v
left join spend s on v.vendor_id = s.vendor_id
left join {{ ref('int_vendor_satisfaction') }} q on v.vendor_id = q.vendor_id
