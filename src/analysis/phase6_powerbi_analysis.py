"""Create a credential-free Phase 6 snapshot from the five dbt marts.

This module performs SELECT statements only. Connection details come from the
same MYSQL_* environment variables used by the existing pipeline.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from src.ingestion.load_mysql import mysql_config


MARTS = [
    "mart_department_spend",
    "mart_vendor_performance",
    "mart_contract_compliance",
    "mart_approval_performance",
    "mart_monthly_currency_spend",
]


def serialise(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def rows(cursor, sql: str) -> list[dict]:
    cursor.execute(sql)
    names = [column[0] for column in cursor.description]
    return [{name: serialise(value) for name, value in zip(names, row)} for row in cursor.fetchall()]


def one(cursor, sql: str) -> dict:
    result = rows(cursor, sql)
    if len(result) != 1:
        raise RuntimeError(f"Expected one row, received {len(result)}")
    return result[0]


def build_snapshot(connection) -> dict:
    cursor = connection.cursor()
    try:
        schemas = {}
        origin_profiles = {}
        for mart in MARTS:
            cursor.execute(f"SHOW FULL COLUMNS FROM `{mart}`")
            schemas[mart] = [
                {
                    "column": row[0],
                    "type": row[1],
                    "nullable": row[3] == "YES",
                    "key": row[4] or None,
                    "comment": row[8] or None,
                }
                for row in cursor.fetchall()
            ]
            origin_profiles[mart] = one(
                cursor,
                f"""
                SELECT COUNT(*) AS row_count,
                       COUNT(DISTINCT record_origin) AS origin_count,
                       MIN(record_origin) AS record_origin,
                       MIN(is_synthetic) AS min_is_synthetic,
                       MAX(is_synthetic) AS max_is_synthetic
                FROM `{mart}`
                """,
            )

        overall_spend = one(cursor, """
            SELECT SUM(expense_count) AS expense_count,
                   CAST(SUM(amount_gbp) AS DECIMAL(24,2)) AS amount_gbp,
                   CAST(SUM(amount_gbp) / SUM(expense_count) AS DECIMAL(20,2)) AS avg_expense_gbp,
                   MIN(spend_month) AS first_month,
                   MAX(spend_month) AS last_month
            FROM mart_monthly_currency_spend
        """)
        monthly_spend = rows(cursor, """
            SELECT spend_month,
                   SUM(expense_count) AS expense_count,
                   CAST(SUM(amount_gbp) AS DECIMAL(24,2)) AS amount_gbp
            FROM mart_monthly_currency_spend
            GROUP BY spend_month ORDER BY spend_month
        """)
        currency = rows(cursor, """
            SELECT original_currency,
                   SUM(expense_count) AS expense_count,
                   CAST(SUM(original_amount) AS DECIMAL(24,2)) AS original_amount,
                   CAST(SUM(amount_gbp) AS DECIMAL(24,2)) AS amount_gbp
            FROM mart_monthly_currency_spend
            GROUP BY original_currency ORDER BY amount_gbp DESC
        """)
        departments = rows(cursor, """
            SELECT department_id, department_name, cost_centre, expense_count,
                   amount_gbp, avg_expense_gbp, vendor_count,
                   compliant_expense_count, contract_compliance_pct
            FROM mart_department_spend ORDER BY amount_gbp DESC
        """)
        vendors = rows(cursor, """
            SELECT vendor_id, vendor_name, country, primary_category, risk_tier,
                   expense_count, amount_gbp, avg_expense_gbp,
                   compliant_expense_count, contract_compliance_pct,
                   response_count, avg_overall_rating, avg_delivery_rating,
                   avg_quality_rating, avg_support_rating
            FROM mart_vendor_performance ORDER BY amount_gbp DESC
        """)
        vendor_risk = rows(cursor, """
            SELECT risk_tier, COUNT(*) AS vendor_count,
                   SUM(expense_count) AS expense_count,
                   CAST(SUM(amount_gbp) AS DECIMAL(24,2)) AS amount_gbp,
                   CAST(SUM(compliant_expense_count) / NULLIF(SUM(expense_count),0) * 100 AS DECIMAL(7,2)) AS compliance_pct,
                   CAST(SUM(avg_overall_rating * response_count) / NULLIF(SUM(response_count),0) AS DECIMAL(7,2)) AS avg_overall_rating
            FROM mart_vendor_performance GROUP BY risk_tier ORDER BY amount_gbp DESC
        """)
        contract_overall = one(cursor, """
            SELECT SUM(expense_count) AS expense_count,
                   SUM(CASE WHEN is_contract_compliant=1 THEN expense_count ELSE 0 END) AS compliant_expense_count,
                   CAST(100 * SUM(CASE WHEN is_contract_compliant=1 THEN expense_count ELSE 0 END) / SUM(expense_count) AS DECIMAL(7,2)) AS compliance_pct,
                   CAST(SUM(amount_gbp) AS DECIMAL(24,2)) AS amount_gbp,
                   CAST(SUM(CASE WHEN is_contract_compliant=0 THEN amount_gbp ELSE 0 END) AS DECIMAL(24,2)) AS non_compliant_amount_gbp,
                   CAST(100 * SUM(CASE WHEN is_contract_compliant=0 THEN amount_gbp ELSE 0 END) / SUM(amount_gbp) AS DECIMAL(7,2)) AS non_compliant_spend_pct
            FROM mart_contract_compliance
        """)
        contract_status = rows(cursor, """
            SELECT contract_compliance_status, is_contract_compliant,
                   SUM(expense_count) AS expense_count,
                   CAST(SUM(amount_gbp) AS DECIMAL(24,2)) AS amount_gbp
            FROM mart_contract_compliance
            GROUP BY contract_compliance_status, is_contract_compliant
            ORDER BY amount_gbp DESC
        """)
        contract_category = rows(cursor, """
            SELECT spend_category, SUM(expense_count) AS expense_count,
                   CAST(SUM(amount_gbp) AS DECIMAL(24,2)) AS amount_gbp,
                   CAST(SUM(CASE WHEN is_contract_compliant=0 THEN amount_gbp ELSE 0 END) AS DECIMAL(24,2)) AS non_compliant_amount_gbp,
                   CAST(100 * SUM(CASE WHEN is_contract_compliant=0 THEN amount_gbp ELSE 0 END) / SUM(amount_gbp) AS DECIMAL(7,2)) AS non_compliant_spend_pct
            FROM mart_contract_compliance
            GROUP BY spend_category ORDER BY non_compliant_amount_gbp DESC
        """)
        contract_department = rows(cursor, """
            SELECT c.department_id, d.department_name,
                   SUM(c.expense_count) AS expense_count,
                   CAST(SUM(c.amount_gbp) AS DECIMAL(24,2)) AS amount_gbp,
                   CAST(SUM(CASE WHEN c.is_contract_compliant=0 THEN c.amount_gbp ELSE 0 END) AS DECIMAL(24,2)) AS non_compliant_amount_gbp,
                   CAST(100 * SUM(CASE WHEN c.is_contract_compliant=0 THEN c.amount_gbp ELSE 0 END) / SUM(c.amount_gbp) AS DECIMAL(7,2)) AS non_compliant_spend_pct
            FROM mart_contract_compliance c
            JOIN mart_department_spend d ON d.department_id=c.department_id
            GROUP BY c.department_id, d.department_name
            ORDER BY non_compliant_amount_gbp DESC
        """)
        approval_overall = one(cursor, """
            SELECT SUM(approval_request_count) AS approval_request_count,
                   CAST(SUM(avg_approval_cycle_hours * approval_request_count) / SUM(approval_request_count) AS DECIMAL(12,2)) AS avg_approval_cycle_hours,
                   CAST(SUM(avg_request_to_payment_hours * approval_request_count) / SUM(approval_request_count) AS DECIMAL(12,2)) AS avg_request_to_payment_hours,
                   SUM(sla_breach_count) AS sla_breach_count,
                   CAST(100 * SUM(sla_breach_count) / SUM(approval_request_count) AS DECIMAL(7,2)) AS sla_breach_pct
            FROM mart_approval_performance
        """)
        approval_month = rows(cursor, """
            SELECT spend_month, SUM(approval_request_count) AS approval_request_count,
                   CAST(SUM(avg_approval_cycle_hours * approval_request_count) / SUM(approval_request_count) AS DECIMAL(12,2)) AS avg_approval_cycle_hours,
                   CAST(SUM(avg_request_to_payment_hours * approval_request_count) / SUM(approval_request_count) AS DECIMAL(12,2)) AS avg_request_to_payment_hours,
                   SUM(sla_breach_count) AS sla_breach_count,
                   CAST(100 * SUM(sla_breach_count) / SUM(approval_request_count) AS DECIMAL(7,2)) AS sla_breach_pct
            FROM mart_approval_performance GROUP BY spend_month ORDER BY spend_month
        """)
        approval_department = rows(cursor, """
            SELECT a.department_id, d.department_name,
                   SUM(a.approval_request_count) AS approval_request_count,
                   CAST(SUM(a.avg_approval_cycle_hours * a.approval_request_count) / SUM(a.approval_request_count) AS DECIMAL(12,2)) AS avg_approval_cycle_hours,
                   CAST(SUM(a.avg_request_to_payment_hours * a.approval_request_count) / SUM(a.approval_request_count) AS DECIMAL(12,2)) AS avg_request_to_payment_hours,
                   SUM(a.sla_breach_count) AS sla_breach_count,
                   CAST(100 * SUM(a.sla_breach_count) / SUM(a.approval_request_count) AS DECIMAL(7,2)) AS sla_breach_pct
            FROM mart_approval_performance a
            JOIN mart_department_spend d ON d.department_id=a.department_id
            GROUP BY a.department_id, d.department_name
            ORDER BY sla_breach_pct DESC
        """)

        total_spend = Decimal(overall_spend["amount_gbp"])
        top_five_spend = sum(Decimal(row["amount_gbp"]) for row in vendors[:5])
        vendor_concentration = {
            "top_5_amount_gbp": format(top_five_spend, "f"),
            "top_5_spend_pct": format(top_five_spend / total_spend * 100, ".2f"),
        }

        expected_count = int(overall_spend["expense_count"])
        expected_spend = Decimal(overall_spend["amount_gbp"])
        checks = {
            "all_marts_have_one_synthetic_origin": all(
                int(profile["origin_count"]) == 1
                and profile["record_origin"] == "synthetic_fictional_company"
                and int(profile["min_is_synthetic"]) == 1
                and int(profile["max_is_synthetic"]) == 1
                for profile in origin_profiles.values()
            ),
            "currency_count_reconciles": sum(int(row["expense_count"]) for row in currency) == expected_count,
            "currency_spend_reconciles": sum(Decimal(row["amount_gbp"]) for row in currency) == expected_spend,
            "department_count_reconciles": sum(int(row["expense_count"]) for row in departments) == expected_count,
            "department_spend_reconciles": sum(Decimal(row["amount_gbp"]) for row in departments) == expected_spend,
            "vendor_count_reconciles": sum(int(row["expense_count"]) for row in vendors) == expected_count,
            "vendor_spend_reconciles": sum(Decimal(row["amount_gbp"]) for row in vendors) == expected_spend,
            "contract_count_reconciles": int(contract_overall["expense_count"]) == expected_count,
            "contract_spend_reconciles": Decimal(contract_overall["amount_gbp"]) == expected_spend,
            "approval_count_reconciles": int(approval_overall["approval_request_count"]) == expected_count,
        }

        return {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": {
                "database": mysql_config()["database"],
                "marts": MARTS,
                "record_origin": "synthetic_fictional_company",
                "is_synthetic": True,
                "origin_profiles": origin_profiles,
            },
            "schemas": schemas,
            "validation": {
                "status": "PASS" if all(checks.values()) else "FAIL",
                "checks": checks,
            },
            "metrics": {
                "overall_spend": overall_spend,
                "monthly_spend": monthly_spend,
                "currency": currency,
                "departments": departments,
                "vendors": vendors,
                "vendor_risk": vendor_risk,
                "vendor_concentration": vendor_concentration,
                "contract_overall": contract_overall,
                "contract_status": contract_status,
                "contract_category": contract_category,
                "contract_department": contract_department,
                "approval_overall": approval_overall,
                "approval_month": approval_month,
                "approval_department": approval_department,
            },
        }
    finally:
        cursor.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    args = parser.parse_args()
    try:
        import mysql.connector  # type: ignore
    except ImportError as exc:
        raise SystemExit("mysql-connector-python is required") from exc

    connection = mysql.connector.connect(**mysql_config())
    try:
        snapshot = build_snapshot(connection)
    finally:
        connection.close()

    if snapshot["validation"]["status"] != "PASS":
        failed = [name for name, passed in snapshot["validation"]["checks"].items() if not passed]
        raise RuntimeError(f"Phase 6 reconciliation failed: {', '.join(failed)}")

    output = args.project_root.resolve() / "reports" / "reporting_analysis_snapshot.json"
    output.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "status": snapshot["validation"]["status"],
        "checks_passed": sum(snapshot["validation"]["checks"].values()),
        "marts": len(snapshot["source"]["marts"]),
        "expense_count": snapshot["metrics"]["overall_spend"]["expense_count"],
        "total_amount_gbp": snapshot["metrics"]["overall_spend"]["amount_gbp"],
        "output": str(output),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
