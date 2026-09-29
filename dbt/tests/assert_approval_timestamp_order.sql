select expense_id
from {{ ref('int_approval_cycles') }}
where event_count <> 4
   or request_timestamp_utc is null
   or manager_approval_timestamp_utc is null
   or finance_approval_timestamp_utc is null
   or payment_timestamp_utc is null
   or request_timestamp_utc >= manager_approval_timestamp_utc
   or manager_approval_timestamp_utc >= finance_approval_timestamp_utc
   or finance_approval_timestamp_utc >= payment_timestamp_utc
