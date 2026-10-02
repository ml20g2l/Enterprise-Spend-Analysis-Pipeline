# Data freshness monitoring

## Purpose

This control answers two separate questions for the fictional corporate
pipeline:

1. Did the current scheduled load complete recently enough for downstream use?
2. Does the fixed historical dataset still cover the complete period promised
   by its data contract?

The second question is necessary because the scenario ends on 28 February
2026. Comparing that business date with today's date would label correct,
unchanged portfolio data as stale.

## Rules

| Rule | Evidence | Pass condition | Severity |
|---|---|---|---|
| `operational_load_recency` | Latest `pipeline_load_run.loaded_at_utc` | Within 24 hours and not more than five minutes in the future | Critical |
| `source_period_boundary` | Minimum and maximum expense transaction dates | Exact match to manifest start and end dates | Critical |
| `source_month_partitions` | Distinct expense months | 12 | High |
| `fx_period_coverage` | Minimum and maximum cached FX dates | Starts on or before the period and ends within three days of period end | High |
| `mart_period_boundary` | Minimum and maximum reporting months | Exact match to the declared scenario months | Critical |
| `mart_month_partitions` | Distinct reporting months | 12 | High |

The FX rule allows a three-day end gap because official observations are
business-day data. It does not require a weekend rate.

## Execution and evidence

Airflow runs `monitor_freshness` after successful reconciliation and before the
final summary. Any failed rule exits with a non-zero status, blocks the final
summary, and leaves prior source and mart data unchanged.

Each evaluation writes:

- `freshness.json` and `freshness.md` in the ignored per-run report directory;
- one run record in `pipeline_freshness_run`;
- six rule records in `pipeline_freshness_result`.

The MySQL writes are transactional and keyed by the Airflow run ID, so clearing
and rerunning the same Airflow run updates its audit result instead of creating
duplicates. Reports contain no credentials.

## One-time setup

Apply `sql/ddl/freshness_monitoring.sql` to the existing `enterprise_spend`
database. The migration creates two audit tables only. It does not drop,
recreate, or modify business tables.

For a manual verification after ingestion and dbt build:

```powershell
python -m src.monitoring.data_freshness --project-root .
```

Use `--apply-ddl` only for the initial local setup. The scheduled Airflow task
does not change database structure.

## Scope and limitations

This is batch freshness monitoring for a monthly portfolio pipeline. It does
not provide paging, email delivery, service-level incident management, or
seasonality-based volume anomaly detection. A production implementation would
send failed results to an observability or incident platform and would assign
an owner and response target to every rule.
