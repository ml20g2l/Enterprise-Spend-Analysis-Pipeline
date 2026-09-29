"""Orchestrate the verified enterprise spend ingestion and dbt workflow."""

from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator


PROJECT_ROOT = "/opt/project"
PIPELINE_PYTHON = "/opt/pipeline-venv/bin/python"
DBT = "/opt/pipeline-venv/bin/dbt"

COMMON_ENV = {
    "PYTHONPATH": PROJECT_ROOT,
    "PHASE5_RUN_ID": "{{ run_id }}",
    # The task helper accepts only documented fixed values.
    "PHASE5_FORCE_FAILURE": "{{ dag_run.conf.get('force_failure_task', 'none') }}",
}

default_args = {
    "owner": "enterprise-spend",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="enterprise_spend_pipeline",
    description="Idempotent ingestion, dbt build, and reconciliation",
    schedule="0 6 2 * *",
    start_date=pendulum.datetime(2026, 3, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    max_active_tasks=1,
    default_args=default_args,
    tags=["enterprise-spend", "mysql", "dbt", "phase5"],
) as dag:
    preflight = BashOperator(
        task_id="preflight",
        bash_command=(
            "set -euo pipefail; "
            f"{PIPELINE_PYTHON} -m src.orchestration.phase5_tasks "
            f"preflight --project-root {PROJECT_ROOT}"
        ),
        env=COMMON_ENV,
        append_env=True,
    )

    ingest_mysql = BashOperator(
        task_id="ingest_mysql",
        bash_command=(
            "set -euo pipefail; "
            f"{PIPELINE_PYTHON} -m src.ingestion.load_mysql "
            f"--project-root {PROJECT_ROOT}"
        ),
        env=COMMON_ENV,
        append_env=True,
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=(
            "set -euo pipefail; "
            f"{DBT} build --project-dir {PROJECT_ROOT}/dbt "
            f"--profiles-dir {PROJECT_ROOT}/dbt --threads 1 --no-use-colors"
        ),
        env=COMMON_ENV,
        append_env=True,
    )

    reconcile = BashOperator(
        task_id="reconcile",
        bash_command=(
            "set -euo pipefail; "
            f"{PIPELINE_PYTHON} -m src.orchestration.phase5_tasks "
            f"reconcile --project-root {PROJECT_ROOT}"
        ),
        env=COMMON_ENV,
        append_env=True,
    )

    final_summary = BashOperator(
        task_id="final_summary",
        retries=0,
        bash_command=(
            "set -euo pipefail; "
            f"{PIPELINE_PYTHON} -m src.orchestration.phase5_tasks "
            f"summary --project-root {PROJECT_ROOT}"
        ),
        env=COMMON_ENV,
        append_env=True,
    )

    preflight >> ingest_mysql >> dbt_build >> reconcile >> final_summary
