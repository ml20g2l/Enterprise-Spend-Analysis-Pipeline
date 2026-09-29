select m.expense_id
from {{ ref('int_expense_contract_match') }} m
left join {{ ref('stg_synthetic_contracts') }} c on m.matched_contract_id = c.contract_id
where (m.is_contract_compliant = 1 and (
          c.contract_id is null
       or c.vendor_id <> m.vendor_id
       or c.approved_category <> m.spend_category
       or m.transaction_date not between c.contract_start_date and c.contract_end_date
      ))
   or (m.contract_compliance_status like 'compliant_%' and m.is_contract_compliant <> 1)
   or (m.contract_compliance_status not like 'compliant_%' and m.is_contract_compliant <> 0)
