# Enterprise Spend Analytics Pipeline

[![Python regression](https://github.com/ml20g2l/Enterprise-Spend-Analysis-Pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/ml20g2l/Enterprise-Spend-Analysis-Pipeline/actions/workflows/ci.yml)

A portfolio project demonstrating data quality, analytics engineering,
orchestration, and management reporting with Python, MySQL, dbt Core, Apache
Airflow, and Power BI.

> **Data boundary:** the 13,830 DEFRA rows are real UK government open data and
> are used for profiling and descriptive analysis only. The operational MySQL → dbt → Airflow →
> Power BI path uses a deterministic fictional company scenario plus real
> Frankfurter reference FX rates. Corporate findings are not claims about DEFRA.

## At a glance

| Area | Verified result |
|---|---:|
| Real public data quality | 12 DEFRA files · 13,830 rows · 134 repeated occurrences · 72 source-month warnings |
| Fictional corporate scenario | 5,000 expenses · 125 vendors · 200 contracts · 20,000 approval events |
| Multi-currency | GBP 60% · EUR 25% · USD 15% · £1,160,936,638.63 reconciled |
| Analytics engineering | 17 dbt models · 73 dbt tests · five reporting marts |
| Orchestration | two complete five-task Airflow runs · 24/24 reconciliations each |
| Reporting | three Power BI pages · package and rendered QA passed |

## Architecture

```text
REAL PUBLIC-DATA ANALYSIS PATH
12 DEFRA CSVs ──► Python profiling ──► inventory + quality + findings

FICTIONAL CORPORATE ANALYTICS PATH
deterministic generator + cached FX
                │
                ▼
         Python validation
                │
                ▼
     MySQL raw + audit facts
                │
                ▼
 dbt staging ─► intermediate ─► marts/tests
                │
                ▼
      Power BI management report

Airflow orchestrates: preflight ─► ingestion ─► dbt build ─► reconciliation ─► summary
```

This is intentionally a split architecture. DEFRA is not loaded into MySQL or
modelled by dbt. The fictional scenario retains `record_origin`, `scenario_id`,
and `is_synthetic` throughout the operational path.

See the implemented [architecture](docs/architecture.md),
[data model](docs/data_model.md), [data dictionary](docs/data_dictionary.md),
[dbt design](docs/dbt_architecture.md),
[orchestration design](docs/orchestration.md), and
[Power BI model](docs/powerbi_model.md).

For a single technical narrative across data analysis, analytics engineering,
and data engineering, see the
[portfolio project report](docs/project_portfolio_report.md).
The generated [dbt documentation](https://ml20g2l.github.io/Enterprise-Spend-Analysis-Pipeline/)
provides a public model catalogue and lineage graph.

## Business findings

### Real DEFRA data

The published rows total **£5.75bn**, but the analysis identifies two controls
that should precede procurement conclusions: `EA` and `Environment Agency` are
split entity labels, and the 134 exact-row repetitions create a **£35.53m
(0.62%)** sensitivity in the total. The leading supplier label represents
28.14% of net value, but counterparty classification is required before treating
that as commercial vendor concentration. See the
[DEFRA spend findings](reports/defra_spend_findings.md).

### Fictional corporate scenario

The Power BI report demonstrates how a procurement team could prioritise
control and workflow issues in the fictional scenario:

1. **Contract coverage is the largest control opportunity.** £116.95m has no
   active matching contract, ahead of category mismatch (£105.15m) and spend
   outside contract validity (£83.82m).
2. **High-risk vendors need a focused review.** Seven high-risk vendors account
   for £44.35m and have 53.37% contract compliance versus 73.20% overall.
3. **Approval issues have different causes.** Procurement has the longest mean
   approval cycle (64.04 hours), while Research has the highest SLA breach rate
   (42.04%); the controls should not treat them as the same problem.

These are deterministic fictional results intended to demonstrate analytical
reasoning. Full evidence and caveats are in
[business findings](reports/business_findings.md).

## Dashboard

The final [Power BI report](powerbi/Enterprise_Spend_Analysis_Pipeline.pbix)
consumes five governed dbt marts and does not recreate business logic in Power
Query.

### Executive Spend Overview

![Executive Spend Overview](docs/images/dashboard_executive_spend.png)

Tracks spend, transaction volume, monthly movement, currency exposure,
department allocation, and leading vendors.

### Contract & Vendor Performance

![Contract and Vendor Performance](docs/images/dashboard_contract_vendor.png)

Prioritises non-compliant spend by cause, department, category, vendor risk,
and satisfaction context.

### Approval & Operational Performance

![Approval and Operational Performance](docs/images/dashboard_approval_operations.png)

Compares approval duration, request-to-payment time, SLA breaches, monthly
movement, and department-level performance.

Package, render, and quantitative checks are documented in the
[Power BI QA report](reports/powerbi_qa_report.md).

## Engineering highlights

- **Lineage:** deterministic `source_record_id` values connect records to their
  source. DEFRA rows additionally preserve file, reporting month, and row number.
- **Data quality:** exact repeats and business-duplicate candidates are flagged,
  not silently removed. A zero quarantine count means no hard rule failed—not
  that the source has no warnings.
- **Financial accuracy:** `Decimal` arithmetic, latest-prior-date FX matching,
  applied rate lineage, and currency-level reconciliation.
- **Referential integrity:** MySQL foreign keys and dbt relationship tests cover
  expenses, vendors, departments, contracts, events, and surveys.
- **Idempotency:** stable keys and upserts leave counts and financial totals
  unchanged on a second load.
- **Failure containment:** Airflow retries preflight failures and blocks all
  downstream work before any write when prerequisites fail.
- **Reporting governance:** Power BI uses aggregate marts at declared grains;
  unsupported cross-mart relationships are avoided.

## Validation evidence

### Real DEFRA source path

| Check | Result |
|---|---:|
| Controlled source inventory | 12 files · hashes verified |
| Raw source rows | 13,830 |
| Exact repeated occurrences | 134 retained for review |
| Transaction month differs from file month | 72 retained with both values |
| Hard-rule quarantine | 0 |

### Fictional corporate analytics path

| Layer | Result |
|---|---:|
| Deterministic generation | 35/35 controls passed |
| MySQL live load | 19/19 passed · second load unchanged |
| dbt build | 90/90 nodes passed |
| dbt data tests | 73/73 passed |
| Spend / approval row mismatches | 0 / 0 |
| Reconciled GBP total | **£1,160,936,638.63** |
| Airflow live runs | 5/5 tasks · 24/24 checks each · two runs |
| Power BI mart checks | 10/10 passed |
| Clone-safe Python regression | 19/19 passed |

The combined record is in
[final end-to-end verification](reports/final_end_to_end_verification.md).
Focused evidence is available for [data quality](reports/data_quality_report.md),
[MySQL](reports/mysql_live_verification.md),
[dbt](reports/dbt_live_verification.md), and
[Airflow](reports/airflow_live_verification.md).

## Repository map

```text
.github/workflows/       clone-safe Python regression CI
config/                  deterministic scenario configuration
data/raw/defra/          preserved public DEFRA CSVs
data/raw/fx_rates/       cached Frankfurter responses for offline reruns
src/                     profiling, generation, validation, ingestion, analysis
sql/                     executable MySQL DDL and independent audit SQL
dbt/                     sources, staging, intermediate, marts, tests, docs
airflow/                 Docker runtime and scheduled containerised DAG
powerbi/                 final PBIX report
tests/                   offline regression suite
docs/                    implemented architecture and reporting design
reports/                 concise verification and analytical evidence
```

Generated row-level fictional data, processed files, quarantine outputs,
runtime logs, local credentials, environments, detailed duplicate extracts,
prototypes, and temporary exports are excluded from Git.

## Reproduce locally

The project is Windows-first. Python-only checks and CI are platform-neutral;
the documented live stack uses Windows MySQL plus Docker Desktop/WSL2 for
Airflow.

### 1. Python profiling, generation, and regression

Python 3.11+ is required. Generation can run offline from the tracked FX cache.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-mysql.txt
python -m src.profiling.profile_defra
python -m src.analysis.defra_spend_analysis
python -m src.synthetic.generate_phase3 --offline
python -m src.validation.validate_phase3
python -m unittest discover -s tests -v
```

### 2. MySQL ingestion

Install MySQL 8, create the `enterprise_spend` database and a least-privilege
`spend_app` account, and keep its password outside Git. Apply the existing DDL
without recreating tables:

```powershell
Get-Content .\sql\ddl\phase3_mysql.sql | mysql -u root -p enterprise_spend
python -m src.ingestion.verify_mysql_phase3
```

The verifier requests the application password without echoing it, loads twice,
and fails if counts, FX calculations, completeness, or totals change.

### 3. dbt Core

```powershell
python -m venv .venv-dbt
.\.venv-dbt\Scripts\python.exe -m pip install -r requirements-dbt.txt
.\.venv-dbt\Scripts\python.exe -m src.ingestion.verify_dbt_phase4
```

The verifier runs `dbt debug`, `dbt build`, `dbt test`, and docs generation
against the existing MySQL tables. Verified versions are MySQL 8.0.46, dbt Core
1.7.19, and dbt-mysql 1.7.0.

### 4. Airflow

Airflow runs locally in Docker Desktop/WSL2 and connects to Windows MySQL via
`host.docker.internal`. The setup script creates an ignored `airflow/.env` and
does not print generated secrets.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_airflow_env.ps1
docker compose --env-file airflow\.env -f airflow\docker-compose.yml build
docker compose --env-file airflow\.env -f airflow\docker-compose.yml up airflow-init
docker compose --env-file airflow\.env -f airflow\docker-compose.yml up -d
```

The UI is available at `http://localhost:8080`. The DAG is scheduled for 06:00
UTC on day 2 of each month with catch-up disabled and can also be triggered
manually.

### 5. Power BI

Open the tracked PBIX in Power BI Desktop, provide the local MySQL credential,
and refresh the five dbt marts. See [Power BI model](docs/powerbi_model.md) for
the semantic model and interaction boundaries.

## Limitations

- Corporate analysis is synthetic by design and supports method demonstration,
  not operational claims about a real organisation.
- The real DEFRA work currently stops at profiling and descriptive analysis; it
  is not an operational MySQL/dbt fact pipeline or Power BI report.
- The Airflow deployment is a local portfolio environment, not a managed
  production service with enterprise secrets, alerting, or cloud observability.
- The tracked source hashes verify repository preservation, not byte identity
  with every current remote GOV.UK download.
- `dbt-mysql` is community maintained and would require an adapter/support
  review before production adoption.

## Data attribution and licensing

DEFRA provenance and Open Government Licence attribution are documented in
[source provenance](docs/source_provenance.md). Frankfurter is used as reference
FX data. Original project code is released under the [MIT License](LICENSE).
