# Phase 3 synthetic data and multi-currency report

## Scope

All records in this phase describe a fictional company. They are separated from real DEFRA records by source directories, table design, `record_origin`, and `is_synthetic`.

## Generated datasets

| Dataset | Rows | Grain |
|---|---:|---|
| Departments | 12 | One fictional department |
| Vendors | 125 | One fictional vendor |
| Contracts | 200 | One fictional contract |
| Expenses | 5,000 | One fictional expense |
| Approval events | 20,000 | One workflow event |
| Approval cycles | 5,000 | One expense approval workflow |
| Satisfaction responses | 300 | One fictional survey response |

## Reconciliation

Automated checks passed: **35 of 35**. Failed: **0**. Quarantined: **0**.

Currency distribution: `{"EUR": 1250, "GBP": 3000, "USD": 750}`. Contract-match statuses: `{"compliant_alternate_master_match": 160, "compliant_master_match": 507, "compliant_submitted_contract": 2993, "no_active_matching_contract": 500, "non_compliant_category_mismatch": 470, "non_compliant_outside_validity": 370}`.

Approval SLA breaches under the configured 72-hour request-to-finance rule: **1,919 of 5,000**. This is a generated scenario result, not a benchmark or real-company metric.

## FX method

EUR and USD are converted using cached Frankfurter v2 rates quoted directly as GBP per unit of original currency. The applied observation is the latest available rate on or before the transaction date. GBP uses an identity rate of 1. Calculations use `Decimal` and round GBP outputs to two decimal places with ROUND_HALF_UP.

## Contract method

A submitted contract is compliant only when vendor, approved category, and transaction date agree with the contract master. If the submitted contract fails, the matcher searches for another active master contract before assigning a non-compliant result. A blank contract reference therefore does not automatically mean off-contract spend.

## Quarantine interpretation

Zero quarantined rows means the deterministic generator produced no records that violated the current hard validation rules. It does not mean that the scenario is free from warnings, modelling assumptions, or business limitations.

## MySQL execution status

Live ingestion completed against MySQL Server 8.0.46, database `enterprise_spend`, using the `spend_app` application account. The verification command did not execute DDL or recreate tables.

All 10 tables were empty before loading. After the first load, the expected source and fact counts were present. The second complete load produced identical row counts and identical currency/GBP totals. All **19 of 19** live database checks passed.

The reconciled converted spend total is **£1,160,936,638.63**: GBP **£753,145,670.04**, EUR transactions converted to **£269,481,892.86**, and USD transactions converted to **£138,309,075.73**.

The first attempted live load failed before commit because GBP identity-rate rows had an empty `fx_cache_file`, which the loader converted to `NULL` while the MySQL column was `NOT NULL`. The generator was corrected to store `GBP_IDENTITY`, a validation rule and regression test were added, and the successful retry confirmed all pre-load table counts were still zero.
