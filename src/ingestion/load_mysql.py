"""Idempotently load Phase 3 files into an existing MySQL 8.0 database.

Connection settings are read from MYSQL_HOST, MYSQL_PORT, MYSQL_USER,
MYSQL_PASSWORD, and MYSQL_DATABASE. Secrets are never written to reports.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from src.synthetic.generate_phase3 import FX_SOURCE, deterministic_id


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def mysql_config() -> dict:
    required = ["MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing required MySQL environment variables: {', '.join(missing)}")
    return {
        "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
        "user": os.environ["MYSQL_USER"],
        "password": os.environ["MYSQL_PASSWORD"],
        "database": os.environ["MYSQL_DATABASE"],
        "autocommit": False,
    }


def execute_ddl(connection, path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    statements = []
    current = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        current.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(current))
            current = []
    if current:
        statements.append("\n".join(current))
    cursor = connection.cursor()
    try:
        for statement in statements:
            cursor.execute(statement)
        connection.commit()
    finally:
        cursor.close()


def coerce_value(column: str, value):
    if value == "":
        return None
    if column in {"is_synthetic", "is_contract_compliant", "approval_sla_breached"}:
        return str(value).lower() == "true"
    if column.endswith("_timestamp_utc") or column == "loaded_at_utc":
        return datetime.fromisoformat(str(value)).replace(tzinfo=None)
    if column in {
        "original_amount", "contract_value_gbp", "rate", "fx_rate_to_gbp", "amount_gbp",
        "approval_cycle_hours", "request_to_payment_hours", "approval_sla_hours",
    }:
        return Decimal(str(value))
    return value


def build_upsert_sql(table: str, columns: list[str], key_columns: set[str]) -> str:
    quoted = ", ".join(f"`{column}`" for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join(
        f"`{column}` = VALUES(`{column}`)" for column in columns if column not in key_columns
    )
    return f"INSERT INTO `{table}` ({quoted}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {updates}"


def upsert_rows(connection, table: str, rows: list[dict], columns: list[str], key_columns: set[str]) -> None:
    if not rows:
        return
    sql = build_upsert_sql(table, columns, key_columns)
    cursor = connection.cursor()
    try:
        values = [tuple(coerce_value(column, row.get(column, "")) for column in columns) for row in rows]
        for offset in range(0, len(values), 1000):
            cursor.executemany(sql, values[offset : offset + 1000])
    finally:
        cursor.close()


def fx_rows(project_root: Path) -> list[dict]:
    rows = []
    for path in sorted((project_root / "data" / "raw" / "fx_rates").glob("frankfurter_v2_*_GBP_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload["rates"]:
            rows.append({
                "fx_rate_id": deterministic_id(FX_SOURCE, item["date"], item["base"], item["quote"]),
                "rate_date": item["date"],
                "base_currency": item["base"],
                "quote_currency": item["quote"],
                "rate": str(item["rate"]),
                "fx_source": FX_SOURCE,
                "cache_file": path.name,
            })
    unique = {row["fx_rate_id"]: row for row in rows}
    return [unique[key] for key in sorted(unique)]


TABLE_SPECS = [
    ("raw_synthetic_department", "data/raw/synthetic/departments.csv", [
        "source_record_id", "department_id", "department_name", "cost_centre", "scenario_id", "record_origin", "is_synthetic"
    ], {"source_record_id"}),
    ("raw_synthetic_vendor", "data/raw/synthetic/vendors.csv", [
        "source_record_id", "vendor_id", "vendor_name", "country", "default_currency", "primary_category", "risk_tier", "scenario_id", "record_origin", "is_synthetic"
    ], {"source_record_id"}),
    ("raw_synthetic_contract", "data/raw/synthetic/contracts.csv", [
        "source_record_id", "contract_id", "vendor_id", "contract_start_date", "contract_end_date", "contract_value_gbp", "approved_category", "contract_status", "scenario_id", "record_origin", "is_synthetic"
    ], {"source_record_id"}),
    ("raw_synthetic_expense", "data/raw/synthetic/expenses.csv", [
        "source_record_id", "expense_id", "transaction_date", "department_id", "vendor_id", "spend_category", "description", "submitted_contract_id", "original_amount", "original_currency", "payment_method", "scenario_id", "generation_seed", "record_origin", "is_synthetic"
    ], {"source_record_id"}),
    ("raw_synthetic_approval_event", "data/raw/synthetic/approval_events.jsonl", [
        "source_record_id", "event_id", "expense_id", "event_sequence", "event_type", "event_timestamp_utc", "actor_role", "scenario_id", "record_origin", "is_synthetic"
    ], {"source_record_id"}),
    ("raw_synthetic_vendor_satisfaction", "data/raw/synthetic/vendor_satisfaction.csv", [
        "source_record_id", "response_id", "vendor_id", "response_date", "overall_rating", "delivery_rating", "quality_rating", "support_rating", "response_channel", "scenario_id", "record_origin", "is_synthetic"
    ], {"source_record_id"}),
    ("fact_synthetic_spend", "data/processed/synthetic_expenses_gbp.csv", [
        "source_record_id", "expense_id", "transaction_date", "department_id", "vendor_id", "spend_category", "submitted_contract_id", "matched_contract_id", "contract_compliance_status", "is_contract_compliant", "original_amount", "original_currency", "fx_rate_to_gbp", "fx_rate_date", "amount_gbp", "fx_source", "fx_cache_file", "scenario_id", "generation_seed", "record_origin", "is_synthetic"
    ], {"source_record_id"}),
    ("fact_synthetic_approval", "data/processed/synthetic_approval_cycles.csv", [
        "source_record_id", "expense_id", "request_timestamp_utc", "manager_approval_timestamp_utc", "finance_approval_timestamp_utc", "payment_timestamp_utc", "approval_cycle_hours", "request_to_payment_hours", "approval_sla_hours", "approval_sla_breached", "scenario_id", "record_origin", "is_synthetic"
    ], {"source_record_id"}),
]


def load_once(connection, project_root: Path) -> dict[str, int]:
    for table, relative_path, columns, keys in TABLE_SPECS:
        path = project_root / relative_path
        rows = read_jsonl(path) if path.suffix == ".jsonl" else read_csv(path)
        upsert_rows(connection, table, rows, columns, keys)
    fx = fx_rows(project_root)
    upsert_rows(
        connection,
        "raw_fx_rate",
        fx,
        ["fx_rate_id", "rate_date", "base_currency", "quote_currency", "rate", "fx_source", "cache_file"],
        {"fx_rate_id"},
    )
    manifest = json.loads((project_root / "reports" / "generation_manifest.json").read_text(encoding="utf-8"))
    upsert_rows(connection, "pipeline_load_run", [{
        "generation_run_id": manifest["generation_run_id"],
        "scenario_id": manifest["scenario_id"],
        "generation_version": manifest["generation_version"],
        "random_seed": manifest["random_seed"],
        "manifest_json": json.dumps(manifest, ensure_ascii=False, sort_keys=True),
        "loaded_at_utc": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="microseconds"),
    }], ["generation_run_id", "scenario_id", "generation_version", "random_seed", "manifest_json", "loaded_at_utc"], {"generation_run_id"})
    connection.commit()

    tables = [spec[0] for spec in TABLE_SPECS] + ["raw_fx_rate", "pipeline_load_run"]
    counts = {}
    cursor = connection.cursor()
    try:
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            counts[table] = int(cursor.fetchone()[0])
    finally:
        cursor.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--apply-ddl", action="store_true")
    parser.add_argument("--verify-idempotency", action="store_true")
    args = parser.parse_args()
    try:
        import mysql.connector  # type: ignore
    except ImportError as exc:
        raise SystemExit("Install requirements-mysql.txt before running the MySQL loader.") from exc

    project_root = args.project_root.resolve()
    connection = mysql.connector.connect(**mysql_config())
    try:
        if args.apply_ddl:
            execute_ddl(connection, project_root / "sql" / "ddl" / "phase3_mysql.sql")
        first_counts = load_once(connection, project_root)
        report = {"first_run_counts": first_counts, "idempotency_verified": False}
        if args.verify_idempotency:
            second_counts = load_once(connection, project_root)
            report["second_run_counts"] = second_counts
            report["idempotency_verified"] = first_counts == second_counts
            if not report["idempotency_verified"]:
                raise RuntimeError("MySQL row counts changed on the second load")
        output = project_root / "reports" / "mysql_load_report.json"
        output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
