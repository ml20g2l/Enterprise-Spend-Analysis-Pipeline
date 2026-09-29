"""Run live Phase 3 MySQL ingestion and two-run reconciliation.

The password is read with getpass and is never persisted or printed. Existing
tables are used as-is; this command never executes DDL or drops objects.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import json
from decimal import Decimal
from pathlib import Path

from src.ingestion.load_mysql import TABLE_SPECS, load_once


TABLES = [spec[0] for spec in TABLE_SPECS] + ["raw_fx_rate", "pipeline_load_run"]
EXPECTED_COUNTS = {
    "raw_synthetic_department": 12,
    "raw_synthetic_vendor": 125,
    "raw_synthetic_contract": 200,
    "raw_synthetic_expense": 5000,
    "raw_synthetic_approval_event": 20000,
    "raw_synthetic_vendor_satisfaction": 300,
    "fact_synthetic_spend": 5000,
    "fact_synthetic_approval": 5000,
    "raw_fx_rate": 750,
    "pipeline_load_run": 1,
}


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def table_counts(connection) -> dict[str, int]:
    cursor = connection.cursor()
    counts = {}
    try:
        for table in TABLES:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            counts[table] = int(cursor.fetchone()[0])
    finally:
        cursor.close()
    return counts


def scalar(connection, query: str):
    cursor = connection.cursor()
    try:
        cursor.execute(query)
        return cursor.fetchone()[0]
    finally:
        cursor.close()


def database_totals(connection) -> dict:
    cursor = connection.cursor()
    totals = {}
    try:
        cursor.execute(
            "SELECT original_currency, COUNT(*), SUM(original_amount), SUM(amount_gbp) "
            "FROM fact_synthetic_spend GROUP BY original_currency ORDER BY original_currency"
        )
        totals["currency"] = {
            row[0]: {
                "count": int(row[1]),
                "original_amount": format(Decimal(row[2]), "f"),
                "amount_gbp": format(Decimal(row[3]), "f"),
            }
            for row in cursor.fetchall()
        }
        cursor.execute("SELECT SUM(amount_gbp) FROM fact_synthetic_spend")
        total_gbp = cursor.fetchone()[0]
        totals["total_amount_gbp"] = format(Decimal(total_gbp or 0), "f")
    finally:
        cursor.close()
    return totals


def source_totals(project_root: Path) -> dict:
    rows = read_csv(project_root / "data" / "processed" / "synthetic_expenses_gbp.csv")
    by_currency = {}
    for currency in ("EUR", "GBP", "USD"):
        subset = [row for row in rows if row["original_currency"] == currency]
        by_currency[currency] = {
            "count": len(subset),
            "original_amount": format(sum((Decimal(row["original_amount"]) for row in subset), Decimal("0")), "f"),
            "amount_gbp": format(sum((Decimal(row["amount_gbp"]) for row in subset), Decimal("0")), "f"),
        }
    return {
        "currency": by_currency,
        "total_amount_gbp": format(sum((Decimal(row["amount_gbp"]) for row in rows), Decimal("0")), "f"),
    }


def reconciliation_checks(connection, counts: dict[str, int], local_totals: dict) -> list[dict]:
    checks = []

    def add(name: str, passed: bool, actual, expected) -> None:
        checks.append({"check": name, "status": "PASS" if passed else "FAIL", "actual": actual, "expected": expected})

    for table, expected in EXPECTED_COUNTS.items():
        add(f"row_count_{table}", counts[table] == expected, counts[table], expected)

    db_totals = database_totals(connection)
    add("currency_totals", db_totals["currency"] == local_totals["currency"], db_totals["currency"], local_totals["currency"])
    add("total_amount_gbp", db_totals["total_amount_gbp"] == local_totals["total_amount_gbp"], db_totals["total_amount_gbp"], local_totals["total_amount_gbp"])

    fx_errors = int(scalar(connection, """
        SELECT COUNT(*)
        FROM fact_synthetic_spend
        WHERE amount_gbp <> ROUND(original_amount * fx_rate_to_gbp, 2)
           OR fx_rate_date > transaction_date
           OR (original_currency = 'GBP' AND (fx_rate_to_gbp <> 1 OR fx_rate_date <> transaction_date))
           OR (original_currency <> 'GBP' AND fx_source <> 'Frankfurter v2 blended reference rate')
    """))
    add("fx_conversion", fx_errors == 0, fx_errors, 0)

    raw_without_fact = int(scalar(connection, """
        SELECT COUNT(*) FROM raw_synthetic_expense r
        LEFT JOIN fact_synthetic_spend f ON f.expense_id = r.expense_id
        WHERE f.expense_id IS NULL
    """))
    fact_without_raw = int(scalar(connection, """
        SELECT COUNT(*) FROM fact_synthetic_spend f
        LEFT JOIN raw_synthetic_expense r ON r.expense_id = f.expense_id
        WHERE r.expense_id IS NULL
    """))
    add("raw_expense_to_fact_completeness", raw_without_fact == 0, raw_without_fact, 0)
    add("fact_to_raw_expense_integrity", fact_without_raw == 0, fact_without_raw, 0)

    approval_errors = int(scalar(connection, """
        SELECT COUNT(*) FROM (
            SELECT expense_id, COUNT(*) AS event_count,
                   MIN(CASE WHEN event_sequence=1 THEN event_timestamp_utc END) AS request_ts,
                   MIN(CASE WHEN event_sequence=2 THEN event_timestamp_utc END) AS manager_ts,
                   MIN(CASE WHEN event_sequence=3 THEN event_timestamp_utc END) AS finance_ts,
                   MIN(CASE WHEN event_sequence=4 THEN event_timestamp_utc END) AS payment_ts
            FROM raw_synthetic_approval_event
            GROUP BY expense_id
            HAVING event_count <> 4
                OR NOT (request_ts < manager_ts AND manager_ts < finance_ts AND finance_ts < payment_ts)
        ) invalid
    """))
    add("approval_event_sequence", approval_errors == 0, approval_errors, 0)

    approval_fact_missing = int(scalar(connection, """
        SELECT COUNT(*) FROM raw_synthetic_expense e
        LEFT JOIN fact_synthetic_approval a ON a.expense_id=e.expense_id
        WHERE a.expense_id IS NULL
    """))
    add("approval_fact_completeness", approval_fact_missing == 0, approval_fact_missing, 0)
    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--database", default="enterprise_spend")
    parser.add_argument("--user", default="spend_app")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    args = parser.parse_args()

    try:
        import mysql.connector  # type: ignore
    except ImportError as exc:
        raise SystemExit("mysql-connector-python is not importable. Add the user site-packages directory to PYTHONPATH.") from exc

    password = getpass.getpass(f"MySQL password for {args.user}@{args.host}: ")
    project_root = args.project_root.resolve()
    connection = mysql.connector.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=password,
        database=args.database,
        autocommit=False,
    )
    password = ""
    try:
        server_version = connection.server_info
        pre_counts = table_counts(connection)
        first_counts = load_once(connection, project_root)
        local_totals = source_totals(project_root)
        first_totals = database_totals(connection)
        checks = reconciliation_checks(connection, first_counts, local_totals)
        second_counts = load_once(connection, project_root)
        second_totals = database_totals(connection)
        checks.append({
            "check": "second_run_row_counts_unchanged",
            "status": "PASS" if first_counts == second_counts else "FAIL",
            "actual": second_counts,
            "expected": first_counts,
        })
        checks.append({
            "check": "second_run_totals_unchanged",
            "status": "PASS" if first_totals == second_totals else "FAIL",
            "actual": second_totals,
            "expected": first_totals,
        })
        report = {
            "server_version": server_version,
            "connection": {"host": args.host, "port": args.port, "database": args.database, "user": args.user},
            "ddl_executed": False,
            "pre_load_counts": pre_counts,
            "first_load_counts": first_counts,
            "second_load_counts": second_counts,
            "source_totals": local_totals,
            "first_load_totals": first_totals,
            "second_load_totals": second_totals,
            "checks": checks,
            "checks_passed": sum(item["status"] == "PASS" for item in checks),
            "checks_failed": sum(item["status"] == "FAIL" for item in checks),
            "idempotency_verified": first_counts == second_counts and first_totals == second_totals,
        }
        output = project_root / "reports" / "mysql_live_verification.json"
        output.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
        print(json.dumps({
            "server_version": server_version,
            "pre_load_counts": pre_counts,
            "first_load_counts": first_counts,
            "second_load_counts": second_counts,
            "checks_passed": report["checks_passed"],
            "checks_failed": report["checks_failed"],
            "idempotency_verified": report["idempotency_verified"],
            "report": str(output),
        }, indent=2, sort_keys=True))
        if report["checks_failed"]:
            raise SystemExit(1)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
