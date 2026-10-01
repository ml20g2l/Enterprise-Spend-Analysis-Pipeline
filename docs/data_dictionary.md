# Data dictionary

## Real DEFRA profiling output

Grain: one physical row in one monthly source CSV. Repeated rows remain
separate and retain file and row lineage.

| Field | Meaning |
|---|---|
| `source_record_id` | Deterministic SHA-256 lineage key derived from source file, source row, and record hash. |
| `source_file`, `source_month`, `source_row_number` | Exact origin of the published row. |
| `record_origin`, `is_synthetic` | `real_public_defra` and `false`. |
| `transaction_date_raw`, `transaction_date` | Preserved source text and safely parsed date. |
| `amount_raw`, `amount_gbp` | Preserved source text and parsed GBP amount. |
| `transaction_number` | Incomplete, non-unique business attribute; never a primary key. |
| `po_category_description` | Canonical mapping of both published spelling variants. |
| `exact_record_hash` | Groups fully identical canonical rows without deleting them. |
| `business_key` | Review key based on normalised entity and transaction number; not a uniqueness guarantee. |
| `source_month_match` | Warning flag comparing transaction date month with file month. |
| `quality_status`, `quality_issues` | Valid/warning/quarantine classification and rule codes. |

All other source fields, including supplier, entity, contract number, project
code, postcode, VAT number, and December comments, are preserved. A blank
contract number is not interpreted as non-compliant spend.

## Fictional corporate source fields

| Dataset | Grain | Important fields |
|---|---|---|
| Departments | One department | `department_id`, name, cost centre |
| Vendors | One vendor | `vendor_id`, country, default currency, category, risk tier |
| Contracts | One contract | `contract_id`, `vendor_id`, validity dates, value, approved category |
| Expenses | One expense | `expense_id`, date, department, vendor, category, optional submitted contract, original amount/currency |
| FX rates | One observation | rate date, base/quote currency, rate, source, cache file |
| Approval events | One event | `event_id`, `expense_id`, sequence, type, UTC timestamp, actor role |
| Satisfaction | One response | `response_id`, `vendor_id`, response date, four 1–5 ratings |

Every fictional dataset carries `source_record_id`, `scenario_id`,
`record_origin = 'synthetic_fictional_company'`, and `is_synthetic = true`
where applicable.

## Derived spend and approval fields

| Field | Meaning |
|---|---|
| `matched_contract_id` | Master contract selected after vendor/category/date validation. |
| `contract_compliance_status` | Submitted match, master/alternate match, category mismatch, outside validity, or no active match. |
| `is_contract_compliant` | True only when master-data rules pass. |
| `fx_rate_to_gbp` | GBP value of one unit of original currency; GBP uses 1. |
| `fx_rate_date` | Latest available observation on or before the transaction date. |
| `amount_gbp` | Original amount × FX rate, rounded to two decimals using `ROUND_HALF_UP`. |
| `fx_source`, `fx_cache_file` | Provider and exact cached source; GBP uses `GBP_IDENTITY`. |
| `approval_cycle_hours` | Request to finance approval elapsed hours. |
| `request_to_payment_hours` | Request to payment elapsed hours. |
| `approval_sla_breached` | Whether approval exceeded the configured 72-hour SLA. |

## Reporting marts

| Mart | Grain | Core measures/dimensions |
|---|---|---|
| `mart_department_spend` | Department | expense count, GBP spend, compliance count/rate |
| `mart_vendor_performance` | Vendor | spend, compliance, risk tier, satisfaction aggregates |
| `mart_contract_compliance` | Month × department × category × status | expense count, GBP spend, compliance status |
| `mart_approval_performance` | Month × department | request count, mean durations, SLA breaches/rate |
| `mart_monthly_currency_spend` | Month × currency | expense count, original amount, converted GBP spend |

Column-level dbt descriptions and tests live beside the models under
[`dbt/models`](../dbt/models/).
