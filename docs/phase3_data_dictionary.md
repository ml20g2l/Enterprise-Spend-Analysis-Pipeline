# Phase 3 data dictionary

All datasets below are synthetic except the Frankfurter reference-rate cache.

## `expenses.csv`

Grain: one fictional corporate expense.

| Field | Meaning |
|---|---|
| `expense_id` | Scenario-scoped expense identifier. |
| `transaction_date` | Payment/expense date between 2025-03-01 and 2026-02-28. |
| `department_id`, `vendor_id` | Required foreign keys to synthetic masters. |
| `spend_category` | Generated purchase category. |
| `submitted_contract_id` | Optional contract reference supplied with the expense. Blank is not itself non-compliance. |
| `original_amount`, `original_currency` | Unconverted transaction amount and GBP/EUR/USD code. |
| `scenario_id` | `fictional_corporate_spend_v1`. |
| `generation_seed` | Seed used by the deterministic generator. |
| `record_origin`, `is_synthetic` | Mandatory separation controls. |
| `source_record_id` | Deterministic SHA-256 lineage key. |

## `synthetic_expenses_gbp.csv`

Grain: one fictional expense with contract-match and currency-conversion results.

| Field | Meaning |
|---|---|
| `matched_contract_id` | Contract selected after master-data validation, including alternate matches. |
| `contract_compliance_status` | Submitted match, master match, alternate match, category mismatch, date mismatch, or no active match. |
| `is_contract_compliant` | True only when master vendor, category, and validity-period rules pass. |
| `fx_rate_to_gbp` | GBP value of one unit of original currency. GBP uses 1. |
| `fx_rate_date` | Latest available observation date on or before the transaction date. |
| `amount_gbp` | `original_amount × fx_rate_to_gbp`, rounded to two decimals with ROUND_HALF_UP. |
| `fx_source` | Frankfurter v2 blended reference rate or GBP identity rate. |
| `fx_cache_file` | Exact cached API response used; blank for GBP. |

## Master and event grains

| File | Grain | Key |
|---|---|---|
| `departments.csv` | One fictional department | `department_id` |
| `vendors.csv` | One fictional vendor | `vendor_id` |
| `contracts.csv` | One fictional contract | `contract_id` |
| `approval_events.jsonl` | One workflow event | `event_id`; unique `(expense_id, event_sequence)` |
| `synthetic_approval_cycles.csv` | One derived workflow per expense | `expense_id` |
| `vendor_satisfaction.csv` | One fictional response | `response_id` |

