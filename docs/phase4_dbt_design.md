# Phase 4 dbt design

## Responsibility boundary

Python remains responsible for API access, FX-cache persistence, deterministic synthetic generation, JSON/CSV parsing, quarantine handling, and idempotent raw loading. dbt starts from the seven MySQL raw tables and owns relational cleaning, latest-prior-date FX selection, contract matching, approval-cycle derivation, reusable aggregates, tests, and documentation. The two Phase 3 Python fact tables are audit baselines only; no dbt model selects from them except reconciliation tests.

## Compatibility decision

`dbt-mysql==1.7.0` is the newest community MySQL adapter release and matches `dbt-core==1.7.19`. The adapter is labelled Alpha/experimental by its maintainers, was released in April 2024, and documents MySQL 8.0 support. Its published Python support statement is older than this project environment. Installation and CLI startup were therefore tested in an isolated Python 3.13.5 environment; this is project evidence, not a claim of upstream Python 3.13 support. `requirements-dbt.txt` pins the verified pair.

The first live `dbt build` used four threads and encountered MySQL error 1213 while creating `int_expense_contract_match`; 63 independent nodes passed and 26 downstream nodes were skipped. This was a metadata/DDL concurrency failure, not a failed data assertion. The profile now uses one thread because the local 5,000-row workload does not benefit materially from parallelism and deterministic execution is more important with an experimental adapter.

## Layer grains

| Layer/model | Grain | Main responsibility |
|---|---|---|
| `stg_synthetic_*` | One source row at its declared raw grain | Names, types, null semantics, synthetic labels |
| `stg_fx_rates` | One provider/base/quote/date observation | Decimal rate and cache lineage |
| `int_expense_contract_match` | One fictional expense | Master-data relationship and date-valid contract status |
| `int_expense_fx` | One fictional expense | GBP identity or latest available historical rate on/before transaction date |
| `int_synthetic_spend` | One fictional expense | Reusable transformed spend relation |
| `int_approval_cycles` | One fictional expense workflow | Event pivot, durations and 72-hour SLA |
| `int_vendor_satisfaction` | One surveyed fictional vendor | Survey aggregates |
| `mart_department_spend` | One fictional department | Spend and compliance summary |
| `mart_vendor_performance` | One fictional vendor | Spend, compliance, risk and satisfaction |
| `mart_contract_compliance` | Month × department × category × status | Contract-compliance analysis |
| `mart_approval_performance` | Month × department | Approval timing and SLA analysis |
| `mart_monthly_currency_spend` | Month × original currency | Currency exposure and GBP spend |

## Real/synthetic boundary

Every scenario model retains `record_origin` and `is_synthetic`. These models are not DEFRA facts and must not be described as government performance. DEFRA is intentionally absent from the operational dbt DAG because Phase 3 did not create or load a DEFRA MySQL source table.
