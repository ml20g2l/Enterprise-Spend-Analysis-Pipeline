select expense_id
from {{ ref('int_expense_fx') }}
where fx_rate_to_gbp is null
   or fx_rate_date is null
   or amount_gbp is null
   or fx_rate_date > transaction_date
   or amount_gbp <> round(original_amount * fx_rate_to_gbp, 2)
   or (original_currency = 'GBP' and (fx_rate_to_gbp <> 1 or fx_rate_date <> transaction_date))
