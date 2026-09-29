# Enterprise Spend Analytics Pipeline

This repository combines a preserved, profiled DEFRA public-spend source with a physically separate fictional-company scenario for multi-currency, contract, approval, and vendor-satisfaction testing. Phase 3 implements deterministic synthetic generation, cached historical FX conversion, validation, MySQL 8.0 DDL, and an idempotent loader. Phase 4 adds a live-tested dbt Core staging, intermediate, mart, test, and documentation layer. Phase 5 orchestrates ingestion, dbt, reconciliation, and reporting with Apache Airflow on Docker Desktop/WSL2. Phase 6 currently contains a validated Power BI specification and live business findings; the `.pbix` report has not yet been built.

## Current evidence

- 12 Windows-1252 source files and 13,830 source rows.
- Parsed transaction-date coverage: 2025-03-03 to 2026-02-27.
- All 13,830 rows fall inside the configured analysis period 2025-03-01 to 2026-02-28.
- 134 additional exact-row occurrences in 87 groups. All exact groups are within a single file; none cross files.
- 190 potential business-duplicate groups (468 rows) where the same entity and transaction number have non-identical content. These are candidates for review, not confirmed duplicates.
- 72 rows have a transaction month different from the source file month.
- No unparseable dates or amounts and no quarantined rows in the current source set.
- 123 rows have no transaction number. The raw grain therefore cannot use that field as a primary key.

See [the data-quality report](reports/data_quality_report.md) for the full results and [the proposed data model](docs/data_model.md) for grain, keys, and relationships.
Source attribution, remote-verification limits, and reuse guidance are in [source provenance](docs/source_provenance.md).

## Phase 3 generated scenario

- 5,000 fictional expenses: GBP 3,000, EUR 1,250, USD 750.
- 125 fictional vendors, 12 departments, and 200 contracts.
- 20,000 approval events and 5,000 derived approval cycles.
- 300 fictional vendor-satisfaction responses.
- Frankfurter EUR/GBP and USD/GBP cache covering 2025-02-19 to 2026-02-28.
- 35 of 35 Phase 3 reconciliation checks passed; no generated records violated the hard quarantine rules.

See [the Phase 3 report](reports/phase3_report.md), [implementation notes](docs/phase3_implementation.md), and [Phase 3 dictionary](docs/phase3_data_dictionary.md).

## Phase 4 dbt results

- `dbt debug`: MySQL 8.0.46 connection passed.
- `dbt build`: 17 models plus 73 tests; 90/90 nodes passed.
- Separate `dbt test`: 73/73 passed with no warnings or skips.
- `dbt docs generate`: manifest and catalog generated successfully.
- Transformed spend and approval grains: 5,000 rows each.
- Five marts: 12 department rows, 125 vendor rows, 2,918 contract-compliance rows, 144 approval-performance rows, and 36 monthly-currency rows.
- dbt GBP total: £1,160,936,638.63, exactly equal to the Phase 3 baseline.
- Row-level spend mismatches: 0; approval-cycle mismatches: 0.
- Existing Python regression suite: 9/9 passed after the dbt implementation.

The dbt project models only the fictional corporate scenario because no DEFRA MySQL source table currently exists. See [the live verification report](reports/dbt_live_verification.md), [Phase 4 report](reports/phase4_report.md), and [dbt design](docs/phase4_dbt_design.md).

## Phase 5 Airflow results

- Apache Airflow 3.3.2 on Docker Desktop with WSL2 and `LocalExecutor`.
- PostgreSQL 16 stores Airflow metadata only; the pipeline continues to use the existing Windows MySQL 8.0.46 database.
- DAG sequence: preflight → idempotent MySQL ingestion → dbt build → live reconciliation → final summary.
- Two complete DAG runs succeeded; all five tasks succeeded in each run.
- Both runs passed 24/24 live reconciliation checks.
- All 10 Phase 3 table counts, source totals, and the £1,160,936,638.63 dbt total were unchanged after the second run.
- A deliberate preflight failure retried once, then stopped all four downstream tasks before ingestion.
- DAG import errors: 0; Linux-container Python regression tests: 12/12 passed.

See [the Phase 5 live report](reports/airflow_live_verification.md) and [Airflow architecture](docs/phase5_airflow_architecture.md).

## Phase 6 Power BI preparation

- Five dbt marts were profiled directly from the live MySQL database using read-only queries.
- Ten source-origin, row-count, spend-total, and approval-completeness checks passed.
- The reporting control total remains 5,000 synthetic expenses and £1,160,936,638.63.
- A three-page report design defines the semantic model, relationships, DAX measures, visuals, slicers, and interaction boundaries.
- Actual scenario findings are documented separately from the real DEFRA source and are explicitly labelled synthetic.
- The complete Python regression suite passes 17/17 tests in the project dbt environment.

See [the Power BI design](docs/phase6_powerbi_design.md), [business findings](reports/phase6_business_findings.md), and [live analysis snapshot](reports/phase6_analysis_snapshot.json). No `.pbix` file has been generated yet.

## Repository layout

```text
data/
  raw/defra/       byte-identical working copies of the 12 source CSVs
  raw/synthetic/   fictional-company source files
  raw/fx_rates/    cached Frankfurter API responses
  processed/       reproducible profiled row-level output
  quarantine/      hard validation failures, with headers even when empty
src/profiling/     DEFRA profiler and validator
src/synthetic/     deterministic synthetic generator and FX integration
src/validation/    Phase 3 reconciliation checks
src/ingestion/     optional live MySQL loader
tests/             parser, lineage, source-preservation, and reconciliation tests
reports/           generated inventory and exception evidence
docs/              architecture, model, dictionary, and source-separation rules
sql/ddl/           proposed DEFRA outline and implemented Phase 3 MySQL DDL
dbt/               Phase 4 staging, intermediate, marts, tests, profile and docs
airflow/           Phase 5 Docker Compose runtime and production DAG
powerbi/           reserved for the next phase
```

The 12 CSVs at repository root remain untouched. The copies under `data/raw/defra/` have matching SHA-256 hashes; the test suite verifies this.

## Reproduce the profile

Requires Python 3.11 or newer and no runtime packages.

```powershell
python -m src.profiling.profile_defra
python -m src.synthetic.generate_phase3 --offline
python -m src.validation.validate_phase3
python -m unittest discover -s tests -v
```

The script reads Windows-1252, standardises headers, supports both observed date formats, parses amounts with `Decimal`, and writes generated CSVs as UTF-8 with BOM. Override `--ingestion-timestamp` when byte-stable fixture output is needed.

## Key decisions

- `source_record_id` is a deterministic lineage key derived from file, source row number, and exact source-value hash. It is the raw primary key.
- `transaction_number` is retained as a business identifier but is neither complete nor proven unique.
- Exact duplicates and potential business duplicates are flagged and investigated; neither is removed automatically.
- `source_month` and `transaction_date` are separate fields. Calendar analysis uses transaction date; ingestion controls use source month.
- A row is quarantined only when its date or amount cannot be parsed. Missing descriptive fields and unusual numeric values remain visible warnings.
- A zero quarantine count means no current record violated the defined hard rules; it does not mean the source or scenario has no quality issues.
- Real DEFRA data and future fictional-company data will use separate raw, intermediate, and fact tables. Any optional comparison view must show `record_origin` and `is_synthetic` prominently.

## MySQL status

Live Phase 3 ingestion is verified against MySQL Server 8.0.46 on `enterprise_spend`. All 10 tables reconciled to their source files. A second complete load left every table count and the £1,160,936,638.63 converted total unchanged. The detailed evidence is in `reports/mysql_live_verification.json` and `reports/mysql_live_verification.md`.

## Reproduce Phase 4

The dbt environment is isolated from the ingestion runtime. From PowerShell in the repository root:

```powershell
python -m venv .venv-dbt
$env:PYTHONUTF8='1'
$env:DISABLE_LOGBOOK_CEXT='1'
.\.venv-dbt\Scripts\python.exe -m pip install -r requirements-dbt.txt
.\.venv-dbt\Scripts\python.exe -m src.ingestion.verify_dbt_phase4
```

The final command prompts securely for the local MySQL password and runs debug, build, test, docs generation, and database reconciliation. Credentials are neither printed nor written to project files. The adapter is pinned to `dbt-mysql==1.7.0` with `dbt-core==1.7.19`; see `docs/phase4_dbt_design.md` for its experimental maintenance status and the tested Python 3.13.5 compatibility caveat.

## Reproduce Phase 5

Requirements: Docker Desktop running with the WSL2 engine and the existing
Windows MySQL service running. Generate the ignored local settings file once:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_airflow_env.ps1
```

Enter the existing `spend_app` MySQL password when prompted. Then initialise
and start Airflow from the repository root:

```powershell
docker compose --env-file airflow\.env -f airflow\docker-compose.yml build
docker compose --env-file airflow\.env -f airflow\docker-compose.yml up airflow-init
docker compose --env-file airflow\.env -f airflow\docker-compose.yml up -d airflow-api-server airflow-scheduler airflow-dag-processor
docker compose --env-file airflow\.env -f airflow\docker-compose.yml exec -T airflow-scheduler airflow dags unpause enterprise_spend_pipeline
docker compose --env-file airflow\.env -f airflow\docker-compose.yml exec -T airflow-scheduler airflow dags trigger enterprise_spend_pipeline
```

The UI is available at `http://localhost:8080`. The local admin username and
generated password are stored only in the ignored `airflow/.env`. The production
schedule is 06:00 UTC on day 2 of each month, catch-up is disabled, and only one
DAG run/task may write at a time. Stop services without deleting metadata using:

```powershell
docker compose --env-file airflow\.env -f airflow\docker-compose.yml down
```

## Phase boundary

Phase 5 is complete: two live end-to-end Airflow runs, idempotency reconciliation, retries, downstream failure containment, logs, and per-run summaries are verified. Phase 6 design and evidence are ready, but Phase 6 remains incomplete until the Power BI report is built and validated manually.
