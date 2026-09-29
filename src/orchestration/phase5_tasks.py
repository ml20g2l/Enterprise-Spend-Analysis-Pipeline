"""Non-interactive preflight, reconciliation, and summary tasks for Airflow."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from src.ingestion.load_mysql import TABLE_SPECS, mysql_config
from src.ingestion.verify_dbt_phase4 import collect_database_evidence
from src.ingestion.verify_mysql_phase3 import (
    EXPECTED_COUNTS,
    reconciliation_checks,
    source_totals,
    table_counts,
)


EXPECTED_DBT_COUNTS = {
    "int_synthetic_spend": 5000,
    "int_approval_cycles": 5000,
    "mart_department_spend": 12,
    "mart_vendor_performance": 125,
}
EXPECTED_TOTAL_GBP = "1160936638.63"
ALLOWED_FAILURE_TARGETS = {"none", "preflight", "reconciliation"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_run_id() -> str:
    raw = os.environ.get("PHASE5_RUN_ID", "manual")
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)[:180]


def run_directory(project_root: Path) -> Path:
    path = project_root / "reports" / "airflow" / "runs" / safe_run_id()
    path.mkdir(parents=True, exist_ok=True)
    return path


def force_failure_target() -> str:
    value = os.environ.get("PHASE5_FORCE_FAILURE", "none")
    if value not in ALLOWED_FAILURE_TARGETS:
        raise RuntimeError(f"Invalid PHASE5_FORCE_FAILURE value: {value!r}")
    return value


def connect():
    try:
        import mysql.connector  # type: ignore
    except ImportError as exc:
        raise RuntimeError("mysql-connector-python is required") from exc
    return mysql.connector.connect(**mysql_config())


def required_project_files(project_root: Path) -> list[Path]:
    paths = [project_root / relative for _, relative, _, _ in TABLE_SPECS]
    paths.extend([
        project_root / "reports" / "phase3_generation_manifest.json",
        project_root / "dbt" / "dbt_project.yml",
        project_root / "dbt" / "profiles.yml",
    ])
    return paths


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def preflight(project_root: Path) -> None:
    if force_failure_target() == "preflight":
        raise RuntimeError("Intentional Phase 5 preflight failure for safe-path verification")

    missing = [str(path) for path in required_project_files(project_root) if not path.is_file()]
    if missing:
        raise RuntimeError("Required project files are missing: " + ", ".join(missing))

    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT VERSION()")
        server_version = str(cursor.fetchone()[0])
        cursor.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = %s",
            (mysql_config()["database"],),
        )
        existing = {row[0] for row in cursor.fetchall()}
        cursor.close()
    finally:
        connection.close()

    required_tables = set(EXPECTED_COUNTS)
    absent = sorted(required_tables - existing)
    if absent:
        raise RuntimeError("Required MySQL tables are missing: " + ", ".join(absent))

    payload = {
        "status": "PASS",
        "generated_at_utc": utc_now(),
        "run_id": os.environ.get("PHASE5_RUN_ID", "manual"),
        "mysql_server_version": server_version,
        "required_files_checked": len(required_project_files(project_root)),
        "required_tables_checked": len(required_tables),
    }
    write_json(run_directory(project_root) / "preflight.json", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


def reconcile(project_root: Path) -> None:
    connection = connect()
    try:
        counts = table_counts(connection)
        local_totals = source_totals(project_root)
        checks = reconciliation_checks(connection, counts, local_totals)
        dbt_evidence = collect_database_evidence(connection)
    finally:
        connection.close()

    def add(name: str, passed: bool, actual, expected) -> None:
        checks.append({
            "check": name,
            "status": "PASS" if passed else "FAIL",
            "actual": actual,
            "expected": expected,
        })

    for relation, expected in EXPECTED_DBT_COUNTS.items():
        actual = dbt_evidence["relation_counts"][relation]
        add(f"dbt_row_count_{relation}", actual == expected, actual, expected)
    add(
        "dbt_total_matches_phase3_baseline",
        dbt_evidence["total_amount_gbp"] == dbt_evidence["baseline_total_amount_gbp"] == EXPECTED_TOTAL_GBP,
        dbt_evidence["total_amount_gbp"],
        EXPECTED_TOTAL_GBP,
    )
    add("dbt_spend_row_mismatches", dbt_evidence["spend_row_mismatches"] == 0, dbt_evidence["spend_row_mismatches"], 0)
    add("dbt_approval_row_mismatches", dbt_evidence["approval_row_mismatches"] == 0, dbt_evidence["approval_row_mismatches"], 0)

    if force_failure_target() == "reconciliation":
        add("intentional_failure_probe", False, 1, 0)

    failed = [item for item in checks if item["status"] == "FAIL"]
    report = {
        "status": "FAIL" if failed else "PASS",
        "generated_at_utc": utc_now(),
        "run_id": os.environ.get("PHASE5_RUN_ID", "manual"),
        "source_table_counts": counts,
        "source_totals": local_totals,
        "dbt_evidence": dbt_evidence,
        "checks": checks,
        "checks_passed": len(checks) - len(failed),
        "checks_failed": len(failed),
    }
    output = run_directory(project_root) / "reconciliation.json"
    write_json(output, report)
    print(json.dumps({
        "status": report["status"],
        "checks_passed": report["checks_passed"],
        "checks_failed": report["checks_failed"],
        "report": str(output),
    }, indent=2, sort_keys=True))
    if failed:
        raise SystemExit(1)


def summary(project_root: Path) -> None:
    directory = run_directory(project_root)
    reconciliation_path = directory / "reconciliation.json"
    if not reconciliation_path.is_file():
        raise RuntimeError(f"Reconciliation output not found: {reconciliation_path}")
    reconciliation = json.loads(reconciliation_path.read_text(encoding="utf-8"))
    if reconciliation["status"] != "PASS":
        raise RuntimeError("Cannot publish a successful summary for failed reconciliation")

    payload = {
        "status": "PASS",
        "generated_at_utc": utc_now(),
        "run_id": reconciliation["run_id"],
        "checks_passed": reconciliation["checks_passed"],
        "checks_failed": reconciliation["checks_failed"],
        "synthetic_expense_rows": reconciliation["source_table_counts"]["fact_synthetic_spend"],
        "approval_event_rows": reconciliation["source_table_counts"]["raw_synthetic_approval_event"],
        "total_amount_gbp": reconciliation["dbt_evidence"]["total_amount_gbp"],
    }
    write_json(directory / "summary.json", payload)
    markdown = (
        "# Airflow pipeline run summary\n\n"
        f"- Status: **{payload['status']}**\n"
        f"- Run ID: `{payload['run_id']}`\n"
        f"- Checks: **{payload['checks_passed']} passed, {payload['checks_failed']} failed**\n"
        f"- Synthetic expenses: **{payload['synthetic_expense_rows']:,}**\n"
        f"- Approval events: **{payload['approval_event_rows']:,}**\n"
        f"- Reconciled GBP total: **£{payload['total_amount_gbp']}**\n"
    )
    (directory / "summary.md").write_text(markdown, encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preflight", "reconcile", "summary"])
    parser.add_argument("--project-root", type=Path, default=Path("."))
    args = parser.parse_args()
    project_root = args.project_root.resolve()
    if args.command == "preflight":
        preflight(project_root)
    elif args.command == "reconcile":
        reconcile(project_root)
    else:
        summary(project_root)


if __name__ == "__main__":
    main()
