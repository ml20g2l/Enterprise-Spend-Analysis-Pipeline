select 'synthetic_expenses' as failed_check
where (select count(*) from {{ ref('stg_synthetic_expenses') }}) <> {{ var('expected_synthetic_expense_count') }}
union all
select 'approval_events'
where (select count(*) from {{ ref('stg_synthetic_approval_events') }}) <> {{ var('expected_approval_event_count') }}
union all
select 'approval_cycles'
where (select count(*) from {{ ref('int_approval_cycles') }}) <> {{ var('expected_synthetic_expense_count') }}
