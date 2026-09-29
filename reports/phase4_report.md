# Phase 4 — dbt Core completion report

Phase 4 is complete against MySQL Server 8.0.46 in `enterprise_spend`. The operational dbt DAG contains 17 models: seven staging views, five intermediate views, and five mart tables. The two Phase 3 Python fact tables are comparison baselines only and are not transformation inputs.

## Live results

| Check | Actual result |
|---|---:|
| `dbt debug` | Pass |
| `dbt build` | 90/90 nodes passed |
| Separate `dbt test` | 73/73 passed |
| `dbt docs generate` | Pass; catalog generated |
| Transformed synthetic spend | 5,000 rows |
| Derived approval cycles | 5,000 rows |
| GBP total | £1,160,936,638.63 |
| Spend row mismatches vs Phase 3 | 0 |
| Approval row mismatches vs Phase 3 | 0 |
| Python regression tests | 9/9 passed |

Currency reconciliation also matched the Phase 3 baseline: GBP 3,000 rows / £753,145,670.04; EUR 1,250 rows / £269,481,892.86; USD 750 rows / £138,309,075.73.

## Mart outputs

| Mart | Grain | Rows |
|---|---|---:|
| `mart_department_spend` | Department | 12 |
| `mart_vendor_performance` | Vendor | 125 |
| `mart_contract_compliance` | Month × department × category × compliance status | 2,918 |
| `mart_approval_performance` | Month × department | 144 |
| `mart_monthly_currency_spend` | Month × original currency | 36 |

## Failures found and fixed

1. The first `dbt debug` connected successfully but Windows attempted to write the Korean repository path through CP1252, raising a logging error and leaving the process running. The verifier now forces `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` for every dbt child process.
2. The first four-thread `dbt build` passed 63 nodes, then MySQL returned error 1213 while concurrent view DDL and dependent tests competed for metadata locks. No data assertion failed. The local profile now uses one thread; the complete rerun passed 90/90 and the independent test rerun passed 73/73.

These are environment and adapter-concurrency issues, not defects in the transformed records. The conservative serial profile is appropriate for the current 5,000-expense local workload and for an Alpha/experimental community adapter.

## Scope and interpretation

All dbt facts and marts in this phase describe the deterministic fictional-company scenario. They retain `record_origin = 'synthetic_fictional_company'` and `is_synthetic = 1`. DEFRA remains a separately preserved and profiled public dataset; it was not silently introduced into the dbt DAG because no DEFRA MySQL source table exists.

Machine-readable evidence is in `reports/dbt_live_verification.json`; command logs are in `reports/dbt_debug.log`, `reports/dbt_build.log`, `reports/dbt_test.log`, and `reports/dbt_docs_generate.log`.
