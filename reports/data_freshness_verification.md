# Data Freshness Verification

## Scope

This report records the live MySQL and Airflow verification of the batch
freshness monitor on 2 October 2026.

## Result

| Check | Result |
|---|---:|
| Freshness rules | 6/6 passed |
| Failed rules | 0 |
| Loader second-run row-count comparison | Unchanged |
| Audit run rows after the same run ID was evaluated twice | 1 |
| Audit rule rows after the same run ID was evaluated twice | 6 |
| Updated Airflow DAG | 6/6 tasks passed in two consecutive runs |
| Reconciliation in updated DAG | 24/24 passed in both runs |
| Freshness in updated DAG | 6/6 passed in both runs |
| Final GBP total | £1,160,936,638.63 |
| Credential values written to reports | 0 |

The live evaluation confirmed current load recency, exact source-period
boundaries, all 12 source months, acceptable business-day FX coverage, exact
mart-period boundaries, and all 12 reporting months.

## Failure-path evidence

Automated tests also confirmed that:

- a load older than the configured 24-hour window fails
  `operational_load_recency`;
- a missing final source and mart month fails the two boundary rules and the two
  monthly-partition rules;
- a complete current pipeline passes all six rules.

The full project regression suite passed 22/22 tests after the monitor was
added. The scheduled Airflow run
`scheduled__2026-10-02T06:00:00+00:00` then passed `preflight`,
`ingest_mysql`, `dbt_build`, `reconcile`, `monitor_freshness`, and
`final_summary` in sequence. A second manual run passed the same six tasks and
kept 5,000 expenses, 20,000 approval events, 24 reconciliation checks, six
freshness checks, and the GBP total unchanged.

## Scope boundary

This implementation records results in MySQL and blocks the Airflow final
summary on failure. It does not send external email, paging, or chat alerts.
That notification layer belongs in a managed production deployment with a
defined owner and incident response target.
