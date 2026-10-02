# Controlled Data Boundaries Turn Imperfect Spend Data into Trusted Analytics

> This report uses short sentences, active voice, and defined technical terms.
> It follows an ASD-STE100-style approach. It is not a certified ASD-STE100
> document.

## Executive summary

The Enterprise Spend Analytics Pipeline is an end-to-end portfolio project. It
demonstrates data analysis, analytics engineering, and data engineering in one
controlled system.

- The real-data path profiles 12 DEFRA public spending files and 13,830 rows.
  It preserves 134 exact repeated occurrences and 72 reporting-month warnings.
- The operational path uses a separate deterministic fictional company. It
  contains 5,000 expenses, 20,000 approval events, 125 vendors, 200 contracts,
  12 departments, and 300 survey responses.
- Historical Frankfurter observations convert GBP, EUR, and USD expenses to
  GBP. The reconciled total is £1,160,936,638.63.
- MySQL stores controlled raw and audit relations. dbt Core builds 17 models
  and five reporting marts. Apache Airflow controls a five-task workflow.
- All 73 dbt data tests passed. Two live Airflow runs passed 24 reconciliation
  checks each. Power BI consumes the governed marts on three report pages.

The project does not present fictional corporate results as DEFRA facts. This
boundary is the main governance decision in the design.

## Business and technical problem

Public spending files are useful for data-quality and descriptive analysis.
They do not contain all fields required for a corporate procurement workflow.
The planned analysis required contract validity, approval events, vendor risk,
vendor satisfaction, and multi-currency amounts.

The project therefore solves two related but different problems:

1. It assesses the quality and analytical risk of real public spending data.
2. It demonstrates a complete operational analytics pipeline with a labelled
   fictional company scenario.

This design preserves evidence quality. It also prevents unsupported claims
about a real organisation.

## Implemented architecture

```text
REAL PUBLIC-DATA PATH

12 DEFRA CSV files
        |
        v
Python profiling and validation
        |
        v
Source inventory, quality evidence, duplicate analysis, descriptive findings


FICTIONAL CORPORATE ANALYTICS PATH

Deterministic generator + cached Frankfurter FX observations
        |
        v
Python validation and quarantine controls
        |
        v
MySQL raw tables and independent audit facts
        |
        v
dbt staging -> intermediate models -> five marts and tests
        |
        v
Power BI management report

Airflow controls:
preflight -> ingestion -> dbt build -> reconciliation -> final summary
```

The real DEFRA rows do not enter the fictional MySQL and dbt path. The
fictional path retains `record_origin`, `scenario_id`, and `is_synthetic`.

## Source data and lineage

### Real DEFRA source

The source contains one file for each month from March 2025 to February 2026.
The raw grain is one row in one monthly CSV file.

The profiler preserves:

- source file;
- source month;
- source row number;
- ingestion timestamp;
- original transaction identifier;
- deterministic source record identifier.

The files use Windows-1252 encoding. Date formats vary. December includes an
additional `Comments` column. The category column also has more than one source
spelling. The Python profiler maps these variations to one canonical schema.
It does not modify the original files.

### Fictional corporate source

The generator uses a fixed random seed. The same configuration produces the
same records and identifiers. The generated source contains:

| Dataset | Rows | Grain |
|---|---:|---|
| Departments | 12 | One fictional department |
| Vendors | 125 | One fictional vendor |
| Contracts | 200 | One fictional contract |
| Expenses | 5,000 | One fictional expense |
| Approval events | 20,000 | One workflow event |
| Vendor satisfaction | 300 | One fictional survey response |
| FX observations | 750 | One currency-pair observation for one date |

## Data-quality design

The project separates hard failures from review warnings.

A hard failure prevents a record from supporting the target grain. Examples
include an invalid transaction date, an invalid amount, a missing parent key,
or an invalid approval sequence. These records enter quarantine.

A warning needs investigation but does not prove that the record is invalid.
Examples include an exact repeated row, a non-positive amount, a source-month
difference, or a repeated transaction number.

The current DEFRA result has zero quarantined rows. This result means that no
row failed the current hard rules. It does not mean that the data has no quality
risks.

### Duplicate policy

The profiler found 134 additional exact row occurrences. It did not delete
them. An identical row does not prove a duplicate economic event or payment.

The project distinguishes:

- an exact duplicate, which has the same canonical source values; and
- a business duplicate candidate, which repeats a business identifier but has
  different content.

The public-data analysis retains all source rows and reports duplicate
sensitivity. The exact repetitions create a £35.53m, or 0.62%, sensitivity in
the £5.75bn public-row total.

### Identifier policy

The DEFRA `transaction_number` is not a primary key. It has 123 missing values.
It also repeats across non-identical rows. The project retains it as a business
attribute. A deterministic `source_record_id` provides raw lineage.

## Historical FX integration

The Python generator uses the Frankfurter v2 public API. It requests EUR/GBP
and USD/GBP observations for the analysis period. GBP uses an identity rate of
1.

The implementation applies these controls:

- a 45-second request timeout;
- up to three attempts with increasing wait times;
- response pair, date, duplicate, and positive-rate validation;
- a JSON cache for offline reruns;
- the latest available rate on or before the transaction date;
- no future-dated rate;
- `Decimal` arithmetic and `ROUND_HALF_UP` to two GBP decimal places;
- applied rate, rate date, source, and cache-file lineage on each fact.

The pipeline stops when it has no valid rate. It does not invent a replacement
rate. The tracked cache makes later runs independent from API availability.

## Relational ingestion and idempotency

MySQL 8 stores seven raw tables, two audit facts, and one deterministic
generation-run table. Primary keys, unique constraints, foreign keys, check
constraints, and `DECIMAL` columns protect the declared grains.

The Python loader uses stable keys and `INSERT ... ON DUPLICATE KEY UPDATE`.
It processes rows in batches of 1,000. It commits the multi-table load only
after all writes succeed.

The live verifier ran the loader twice. The second run did not change any row
count or financial total. The result remained:

- 5,000 expense facts;
- 5,000 approval facts;
- 20,000 approval events; and
- £1,160,936,638.63 converted spend.

## dbt transformation layer

Python owns external I/O, cache persistence, raw parsing, and raw loading. dbt
owns relational transformation, reusable business rules, tests, lineage, and
documentation.

| Layer | Models | Main responsibility |
|---|---:|---|
| Staging | 7 | Standard names, types, null meaning, and source labels |
| Intermediate | 5 | FX selection, contract matching, approval cycles, and survey logic |
| Marts | 5 | Governed reporting outputs at declared business grains |

The five marts are:

| Mart | Grain | Verified rows |
|---|---|---:|
| `mart_department_spend` | One department for the full period | 12 |
| `mart_vendor_performance` | One vendor for the full period | 125 |
| `mart_contract_compliance` | Month × department × category × compliance status | 2,918 |
| `mart_approval_performance` | Month × department | 144 |
| `mart_monthly_currency_spend` | Month × original currency | 36 |

The project uses uniqueness, required-value, relationship, accepted-value, and
custom SQL tests. Custom tests validate approval order, contract results, FX
rules, source counts, synthetic labels, and financial totals.

dbt was implemented before Airflow. This order proved the transformation logic
before the project automated it. It also separated SQL failures from workflow
runtime failures.

## Airflow orchestration

Airflow 3.3.2 runs in Linux containers through Docker Desktop and WSL2. MySQL
runs on Windows and is reached through `host.docker.internal`. PostgreSQL stores
only Airflow metadata.

The DAG runs at 06:00 UTC on day 2 of each month. Catch-up is disabled. The DAG
allows one active run and one active task. This configuration prevents
concurrent writes and local MySQL DDL conflicts.

| Task | Responsibility | Failure result |
|---|---|---|
| `preflight` | Check files, database access, and required tables | Stop before any write |
| `ingest_mysql` | Run the transactional idempotent loader | Roll back incomplete work and stop dbt |
| `dbt_build` | Build 17 models and run 73 tests | Stop reconciliation and publication |
| `reconcile` | Compare counts, FX results, grains, and totals | Exit with a failed run |
| `final_summary` | Write a credential-free run result | Run only after all prior tasks pass |

Two complete DAG runs passed all five tasks and 24 reconciliation checks per
run. A controlled failure probe also proved that a preflight failure blocks all
downstream work.

## Power BI reporting layer

Power BI consumes only the five dbt marts. It does not recreate the main FX,
contract, or approval rules in Power Query. The report has three pages:

1. Executive Spend Overview.
2. Contract and Vendor Performance.
3. Approval and Operational Performance.

The marts have different grains. The semantic model avoids unsupported direct
many-to-many relationships between them.

## Analytical findings

The corporate results below are deterministic fictional scenario results. They
are not claims about DEFRA or a real company.

- Contract coverage is the largest control opportunity. £116.95m has no active
  matching contract. Category mismatch accounts for £105.15m. Spend outside
  contract validity accounts for £83.82m.
- Seven high-risk vendors account for £44.35m. Their contract compliance rate
  is 53.37%, compared with 73.20% across the full scenario.
- Procurement has the longest mean approval cycle at 64.04 hours. Research has
  the highest SLA breach rate at 42.04%. The two departments need different
  corrective actions.

The real DEFRA analysis identifies two material interpretation risks. Supplier
labels fragment one entity into `EA` and `Environment Agency`. Exact repetitions
also affect the total. These controls must be addressed before the data supports
strong procurement conclusions.

## Verification record

| Layer | Verified result |
|---|---:|
| DEFRA source inventory | 12 files and hashes verified |
| DEFRA raw rows | 13,830 |
| Deterministic generation | 35/35 controls passed |
| MySQL live load | 19/19 checks passed; second load unchanged |
| dbt build | 90/90 nodes passed |
| dbt data tests | 73/73 passed |
| dbt spend and approval mismatches | 0 and 0 |
| Reconciled GBP total | £1,160,936,638.63 |
| Airflow live runs | Two runs; 5/5 tasks and 24/24 checks each |
| Power BI mart checks | 10/10 passed |
| Clone-safe Python regression | 19/19 passed |

GitHub Actions runs the offline regression suite for pushes and pull requests.
The workflow creates deterministic inputs in a clean Linux environment. This
check reduces dependence on local files and local Python state.

## Capability coverage

### Data analysis

- Source profiling and data-quality interpretation.
- Duplicate sensitivity and period analysis.
- KPI design and business finding communication.
- Power BI report and management-facing conclusions.

### Analytics engineering

- Declared model grain and lineage.
- Layered dbt transformation architecture.
- Reusable business rules and governed marts.
- Generic and custom data tests.
- Source-to-mart financial reconciliation.

### Data engineering

- Deterministic generation and stable identifiers.
- Historical API integration, retries, validation, and cache replay.
- Transactional and idempotent MySQL loading.
- Referential integrity and constraint design.
- Containerised Airflow orchestration and failure containment.
- Clone-safe continuous integration.

## Production changes

The current runtime is a local portfolio environment. A production migration
would require these changes:

- replace fictional inputs with governed source contracts and named owners;
- use separate development, test, and production environments;
- move files and caches to controlled object storage;
- use a supported managed database or analytical warehouse;
- use private networking, encryption, role-based access, and a secret manager;
- manage infrastructure with code and reviewed deployment pipelines;
- add append-only run history, source freshness SLAs, alerts, and incident
  procedures;
- add backups, retention, disaster recovery, and recovery tests;
- add cost budgets and resource teardown controls;
- review the community `dbt-mysql` adapter before production use; and
- publish Power BI through managed workspaces with suitable access controls.

## Limitations

- Corporate results are fictional and demonstrate method.
- The real DEFRA path stops at profiling and descriptive analysis.
- The Airflow and MySQL runtime is local, not a managed production service.
- The project has no production alert channel or formal freshness SLA.
- The current `dbt-mysql` adapter is community maintained.
- Source hashes prove repository preservation. They do not prove byte identity
  with every future GOV.UK download.

## Evidence and implementation

- [Implemented architecture](architecture.md)
- [Data model and grains](data_model.md)
- [dbt architecture](dbt_architecture.md)
- [Airflow orchestration](orchestration.md)
- [Power BI model](powerbi_model.md)
- [Data-quality report](../reports/data_quality_report.md)
- [Final end-to-end verification](../reports/final_end_to_end_verification.md)
- [Real DEFRA findings](../reports/defra_spend_findings.md)
- [Fictional corporate findings](../reports/business_findings.md)

## Data and code boundary

Original DEFRA files and cached reference FX observations are retained with
source attribution. Generated row-level fictional files, runtime logs, local
credentials, local environments, and temporary exports are excluded from Git.
The code is released under the MIT License.
