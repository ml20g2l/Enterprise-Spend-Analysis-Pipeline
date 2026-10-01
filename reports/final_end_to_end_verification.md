# Final end-to-end verification

Status: **PASS within reviewed scope**  
Verification date: **2026-10-01**

## Scope and outcome

The final check covers the portfolio path from preserved source files through
deterministic generation, MySQL loading, dbt transformation, Airflow evidence,
and the Power BI package. Actual DEFRA data remains separate from the fictional
corporate scenario used for contract, approval, vendor, and dashboard analysis.

| Layer | Verification | Result |
|---|---|---:|
| Python | full clone-safe regression suite | **19/19 passed** |
| DEFRA | 12 inventory hashes and 13,830-row profile | **passed** |
| Synthetic generation | offline deterministic generation and 35 controls | **35/35 passed** |
| MySQL 8.0.46 | live row counts, FX, completeness and two-run idempotency | **19/19 passed** |
| dbt Core 1.7.19 | live build | **90/90 passed** |
| dbt Core 1.7.19 | independent data tests | **73/73 passed** |
| dbt reconciliation | spend and approval row mismatches | **0 / 0** |
| dbt control total | total GBP vs Phase 3 fact | **£1,160,936,638.63 matched** |
| Reporting marts | live MySQL read-only checks | **10/10 passed** |
| Airflow 3.3.2 | two previously captured complete DAG runs | **24/24 checks each** |
| Power BI package | file, model, pages and canvas structure | **7/7 passed** |

## Stable live table counts

| Table | Rows |
|---|---:|
| `raw_synthetic_department` | 12 |
| `raw_synthetic_vendor` | 125 |
| `raw_synthetic_contract` | 200 |
| `raw_synthetic_expense` | 5,000 |
| `raw_synthetic_approval_event` | 20,000 |
| `raw_synthetic_vendor_satisfaction` | 300 |
| `raw_fx_rate` | 750 |
| `fact_synthetic_spend` | 5,000 |
| `fact_synthetic_approval` | 5,000 |
| `pipeline_load_run` | 1 |

The first and second loader executions left every count and reconciled amount
unchanged. The latest run started from the already-loaded counts above, proving
that repeat execution remains idempotent rather than merely succeeding from an
empty database.

## dbt mart reconciliation

| Mart | Rows |
|---|---:|
| `mart_department_spend` | 12 |
| `mart_vendor_performance` | 125 |
| `mart_contract_compliance` | 2,918 |
| `mart_approval_performance` | 144 |
| `mart_monthly_currency_spend` | 36 |

Currency subtotals reconcile to the same GBP total:

- GBP: £753,145,670.04 across 3,000 expenses
- EUR: £269,481,892.86 across 1,250 expenses
- USD: £138,309,075.73 across 750 expenses

## Airflow evidence boundary

The versioned Airflow evidence records two successful five-task DAG runs,
24/24 reconciliation checks per run, zero import errors, stable database totals,
and a deliberate failure probe that retried preflight and blocked all downstream
tasks before ingestion. The current Codex execution environment did not expose
the Docker CLI, so a third DAG was not triggered during this final review. The
fresh Python, MySQL, dbt, and mart checks above validate the same executable
components independently on 2026-10-01.

## Power BI publication gate

The PBIX contains the three expected 1280×720 pages and an embedded data model.
The three-page PDF and README PNGs were visually reviewed: titles, charts,
tables, KPI cards, units, and synthetic labels are readable with no observed
clipping or overlap. Package structure and rendered default views passed the
defined QA scope.

## Credential and repository review

- Local `.env` files and credentials remain ignored.
- A scan for the locally configured password/secret values found no copies in
  repository text files.
- Root-level duplicate CSVs, generated row-level data, logs, prototypes, and
  temporary exports are removed from Git tracking but preserved locally.
- Canonical DEFRA source files, FX cache, code, tests, concise evidence, PBIX,
  and final screenshots are the intended GitHub deliverables.
