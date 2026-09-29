with submitted as (
    select
        e.*,
        c.vendor_id as submitted_vendor_id,
        c.approved_category as submitted_approved_category,
        c.contract_start_date as submitted_start_date,
        c.contract_end_date as submitted_end_date,
        case
            when e.submitted_contract_id is null then null
            when c.contract_id is null then 'invalid_contract_reference'
            when c.vendor_id <> e.vendor_id then 'non_compliant_vendor_mismatch'
            when c.approved_category <> e.spend_category then 'non_compliant_category_mismatch'
            when e.transaction_date not between c.contract_start_date and c.contract_end_date
                then 'non_compliant_outside_validity'
            else 'compliant_submitted_contract'
        end as submitted_status
    from {{ ref('stg_synthetic_expenses') }} e
    left join {{ ref('stg_synthetic_contracts') }} c
      on e.submitted_contract_id = c.contract_id
),
active_candidates as (
    select
        e.expense_id,
        c.contract_id,
        row_number() over (partition by e.expense_id order by c.contract_id) as match_rank
    from {{ ref('stg_synthetic_expenses') }} e
    join {{ ref('stg_synthetic_contracts') }} c
      on c.vendor_id = e.vendor_id
     and c.approved_category = e.spend_category
     and e.transaction_date between c.contract_start_date and c.contract_end_date
),
active_match as (
    select expense_id, contract_id
    from active_candidates
    where match_rank = 1
)
select
    s.source_record_id,
    s.expense_id,
    s.transaction_date,
    s.department_id,
    s.vendor_id,
    s.spend_category,
    s.submitted_contract_id,
    case
        when s.submitted_status = 'compliant_submitted_contract' then s.submitted_contract_id
        when a.contract_id is not null then a.contract_id
        when s.submitted_contract_id is not null then s.submitted_contract_id
        else null
    end as matched_contract_id,
    case
        when s.submitted_status = 'compliant_submitted_contract' then s.submitted_status
        when a.contract_id is not null and s.submitted_contract_id is not null
            then 'compliant_alternate_master_match'
        when a.contract_id is not null then 'compliant_master_match'
        else coalesce(s.submitted_status, 'no_active_matching_contract')
    end as contract_compliance_status,
    case
        when s.submitted_status = 'compliant_submitted_contract' or a.contract_id is not null then 1
        else 0
    end as is_contract_compliant
from submitted s
left join active_match a on s.expense_id = a.expense_id
