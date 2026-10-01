# Phase 5 Airflow runtime

This directory contains the Docker Compose runtime for the existing enterprise
spend pipeline. It does not create, drop, or replace the Windows MySQL database.

The local production-style path is:

`preflight -> Python ingestion -> dbt build -> reconciliation -> run summary`

See `docs/orchestration.md` for design decisions and
`scripts/setup_airflow_env.ps1` for local credential setup.
