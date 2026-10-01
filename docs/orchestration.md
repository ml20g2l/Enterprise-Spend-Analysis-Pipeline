# Airflow orchestration

## Decision

Airflow runs as a local, production-style workflow in Linux containers through
Docker Desktop and WSL2. The existing
MySQL 8.0.46 server remains on Windows and is reached from the containers as
`host.docker.internal:3306`. No MySQL DDL is run by the DAG.

Airflow 3.3.2 uses PostgreSQL only for its own metadata. The pipeline database
remains `enterprise_spend`. `LocalExecutor` is sufficient for this single-host,
strictly sequential portfolio workflow and avoids unnecessary Celery/Redis
services.

dbt Core 1.7.19, dbt-mysql 1.7.0, and MySQL Connector are installed in the
isolated `/opt/pipeline-venv` environment. They do not alter Airflow's Python
environment.

## DAG and task contract

The `enterprise_spend_pipeline` DAG runs monthly at 06:00 UTC on the second day
of each month and can also be started manually. Catch-up is disabled. Both
`max_active_runs` and `max_active_tasks` are one, so concurrent writes and MySQL
view-DDL deadlocks are prevented.

| Order | Task | Responsibility | Failure behaviour |
|---:|---|---|---|
| 1 | `preflight` | Check mounted inputs, required existing tables, and MySQL authentication | Stops all downstream work |
| 2 | `ingest_mysql` | Run the existing transactional, idempotent upsert loader | Rolls back an incomplete transaction and stops dbt |
| 3 | `dbt_build` | Build 17 models and execute 73 tests with one dbt thread | Stops reconciliation and publication |
| 4 | `reconcile` | Compare source counts, facts, FX calculations, dbt grain, and GBP totals | Exits non-zero on any mismatch |
| 5 | `final_summary` | Publish a credential-free per-run JSON/Markdown result | Runs only after every prior task succeeds |

Tasks receive credentials through an untracked local `airflow/.env`. Commands do
not print passwords. Reports are written beneath
`reports/airflow/runs/<run-id>/`; run folders are ignored because Airflow logs
and generated reports are runtime evidence rather than source code.

## Idempotency and recovery

The ingestion loader uses stable source record IDs and MySQL upserts. dbt models
are recreated from the same source grain. A failed run may therefore be cleared
and rerun without adding rows. Live verification must run the successful DAG
twice and compare row counts and totals. It should also trigger a deliberate
reconciliation failure: the final summary must not execute, proving downstream
failure containment without corrupting source data.

## Source separation

This phase orchestrates only the Phase 3 synthetic corporate tables and Phase 4
dbt models. It does not relabel or merge them with actual DEFRA transactions.
The `record_origin`, `scenario_id`, and `is_synthetic` lineage remain unchanged.
