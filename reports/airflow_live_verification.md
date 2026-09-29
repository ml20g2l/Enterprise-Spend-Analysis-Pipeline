# Phase 5 Airflow live verification

Status: **PASS**  
Verified: `2026-09-29`  

## Runtime

| Component | Verified version / mode |
|---|---|
| Windows Subsystem for Linux | 2.7.14.0, Ubuntu on WSL2 |
| Docker Engine | 29.8.1 |
| Docker Compose | 5.5.1 |
| Apache Airflow | 3.3.2, Python 3.11, LocalExecutor |
| Airflow metadata | PostgreSQL 16 container |
| Pipeline database | Existing Windows MySQL 8.0.46 |
| dbt | Core 1.7.19, dbt-mysql 1.7.0, one thread |

The Airflow containers reached MySQL through
`host.docker.internal:3306`. The DAG did not create, drop, or recreate the
`enterprise_spend` database or its source tables.

## Successful end-to-end runs

| Run ID | Result | Tasks | Reconciliation | GBP total |
|---|---|---:|---:|---:|
| `scheduled__2026-09-02T06:00:00+00:00` | PASS | 5/5 | 24/24 | £1,160,936,638.63 |
| `phase5_verify_1` | PASS | 5/5 | 24/24 | £1,160,936,638.63 |

Each run executed `preflight`, `ingest_mysql`, `dbt_build`, `reconcile`, and
`final_summary` in that order. Both dbt builds completed all 90 nodes (17
models and 73 tests).

## Two-run reconciliation

| Table | Run 1 | Run 2 |
|---|---:|---:|
| `raw_synthetic_department` | 12 | 12 |
| `raw_synthetic_vendor` | 125 | 125 |
| `raw_synthetic_contract` | 200 | 200 |
| `raw_synthetic_expense` | 5,000 | 5,000 |
| `raw_synthetic_approval_event` | 20,000 | 20,000 |
| `raw_synthetic_vendor_satisfaction` | 300 | 300 |
| `fact_synthetic_spend` | 5,000 | 5,000 |
| `fact_synthetic_approval` | 5,000 | 5,000 |
| `raw_fx_rate` | 750 | 750 |
| `pipeline_load_run` | 1 | 1 |

All 10 table counts were identical. Source currency totals, FX conversion,
source-to-fact completeness, approval ordering, dbt relation grains, and
row-level spend/approval comparisons passed in both runs. The dbt total and
Phase 3 fact baseline were both `1160936638.63` after each run.

## Failure and retry verification

The manual run `phase5_failure_probe` deliberately failed in `preflight` before
opening the ingestion path.

- First attempt moved to `up_for_retry`.
- The configured two-minute delay elapsed.
- The second attempt (`try_number=2`) failed as expected.
- `ingest_mysql`, `dbt_build`, `reconcile`, and `final_summary` all became
  `upstream_failed` and did not execute.
- The DAG run finished `failed`; no source or target row count changed.

## Additional validation

- DAG import errors: 0.
- Airflow API server, scheduler, PostgreSQL, and DAG processor started
  successfully; health-enabled services reported healthy.
- Linux-container Python regression suite: 12/12 passed.
- `airflow/.env` is ignored by Git; credentials were neither printed nor copied
  into reports.
- Generated per-run evidence is retained locally under
  `reports/airflow/runs/<run-id>/` and ignored by Git.

Airflow logs showed no DAG parsing error. The only observed runtime warning was
the Airflow/FAB development rate-limit backend warning during one-time metadata
initialisation; it does not affect this single-user local portfolio runtime.
