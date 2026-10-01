# Phase 3 live MySQL verification

## Environment

- MySQL Server: 8.0.46
- Host: `127.0.0.1:3306`
- Database: `enterprise_spend`
- Application user: `spend_app`
- DDL executed by verification command: no

## Table reconciliation

All tables were empty before ingestion.

| Table | Expected | First load | Second load | Result |
|---|---:|---:|---:|---|
| `raw_synthetic_department` | 12 | 12 | 12 | Pass |
| `raw_synthetic_vendor` | 125 | 125 | 125 | Pass |
| `raw_synthetic_contract` | 200 | 200 | 200 | Pass |
| `raw_synthetic_expense` | 5,000 | 5,000 | 5,000 | Pass |
| `raw_synthetic_approval_event` | 20,000 | 20,000 | 20,000 | Pass |
| `raw_synthetic_vendor_satisfaction` | 300 | 300 | 300 | Pass |
| `raw_fx_rate` | 750 | 750 | 750 | Pass |
| `fact_synthetic_spend` | 5,000 | 5,000 | 5,000 | Pass |
| `fact_synthetic_approval` | 5,000 | 5,000 | 5,000 | Pass |
| `pipeline_load_run` | 1 | 1 | 1 | Pass |

## Financial reconciliation

| Original currency | Rows | Original amount | Converted GBP |
|---|---:|---:|---:|
| GBP | 3,000 | 753,145,670.04 GBP | £753,145,670.04 |
| EUR | 1,250 | 312,591,016.58 EUR | £269,481,892.86 |
| USD | 750 | 184,759,495.49 USD | £138,309,075.73 |
| Total | 5,000 | — | **£1,160,936,638.63** |

The source CSV, first database load, and second database load produced identical currency totals and total GBP value.

## Quality checks

All **19 of 19** live checks passed:

- 10 table-count reconciliations
- Currency-level count and amount reconciliation
- Total GBP reconciliation
- FX calculation and rate-date validation
- Raw-expense-to-fact completeness
- Fact-to-raw integrity
- Approval event ordering
- Approval fact completeness
- Second-run row-count stability
- Second-run financial-total stability

## Idempotency conclusion

The first and second loads both ended with the same row counts and £1,160,936,638.63 total converted spend. No duplicate records or financial-total changes were introduced by the second run.

## Failure resolved

The first attempted live load failed before commit because GBP identity-rate rows supplied an empty `fx_cache_file`, which became `NULL` against a `NOT NULL` column. The generator now stores `GBP_IDENTITY`; validation and a regression test enforce this rule. Pre-load counts on the successful retry were all zero, confirming the failed transaction did not partially commit.

The credential-free verifier can reproduce these controls with
`python -m src.ingestion.verify_mysql_phase3`.
