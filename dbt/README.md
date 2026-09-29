# Phase 4 dbt Core

This project transforms the seven Phase 3 synthetic/FX raw tables in MySQL. It does not model DEFRA because no DEFRA table is currently loaded into MySQL. The pre-existing Python facts are referenced only by singular reconciliation tests.

## Secure local run (PowerShell)

From the repository root:

```powershell
python -m venv .venv-dbt
$env:PYTHONUTF8='1'
$env:DISABLE_LOGBOOK_CEXT='1'
.\.venv-dbt\Scripts\python.exe -m pip install -r requirements-dbt.txt
.\.venv-dbt\Scripts\python.exe -m src.ingestion.verify_dbt_phase4
```

The verifier prompts for the MySQL password without echoing it, sets it only in the child-process environment, runs `dbt debug`, `dbt build`, `dbt test`, and `dbt docs generate`, then writes credential-free evidence under `reports/`. `profiles.yml` contains only environment-variable references and safe local defaults.

The verifier also forces UTF-8 for dbt child-process output. This is required on Windows because the repository path contains Korean characters and a CP1252 log stream cannot encode the interpreter path.

The profile intentionally uses one dbt thread. A four-thread live build caused MySQL error 1213 when concurrent view DDL and dependent tests competed for metadata locks; serial execution avoids that adapter/database concurrency edge case for this small dataset.

To run individual commands, set `DBT_MYSQL_PASSWORD` only for the current PowerShell session and use:

```powershell
.\.venv-dbt\Scripts\dbt.exe debug --project-dir dbt --profiles-dir dbt
.\.venv-dbt\Scripts\dbt.exe build --project-dir dbt --profiles-dir dbt
```
