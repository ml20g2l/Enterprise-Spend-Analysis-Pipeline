"""Evaluate and record freshness controls for the enterprise spend pipeline.

The fictional scenario has a fixed historical business period. The monitor
therefore separates operational freshness (when ingestion last completed) from
period completeness (whether source and mart data cover the promised period).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.ingestion.load_mysql import execute_ddl, mysql_config


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def safe_run_id() -> str:
    raw = os.environ.get("PHASE5_RUN_ID", "manual")
    safe = "".join(char if char.isalnum() or char in "_.-" else "_" for char in raw)
    return safe[:180]


def monitor_run_id() -> str:
    return hashlib.sha256(safe_run_id().encode("utf-8")).hexdigest()[:40]


def load_inputs(project_root: Path) -> tuple[dict, dict]:
    policy = json.loads((project_root / "config" / "data_freshness.json").read_text(encoding="utf-8"))
    manifest = json.loads((project_root / "reports" / "generation_manifest.json").read_text(encoding="utf-8"))
    return policy, manifest


def _scalar(cursor, sql: str):
    cursor.execute(sql)
    return cursor.fetchone()[0]


def collect_evidence(connection) -> dict[str, Any]:
    cursor = connection.cursor()
    try:
        return {
            "last_load_at_utc": _scalar(cursor, "SELECT MAX(loaded_at_utc) FROM pipeline_load_run"),
            "source_min_date": _scalar(cursor, "SELECT MIN(transaction_date) FROM raw_synthetic_expense"),
            "source_max_date": _scalar(cursor, "SELECT MAX(transaction_date) FROM raw_synthetic_expense"),
            "source_month_count": int(_scalar(cursor, "SELECT COUNT(DISTINCT DATE_FORMAT(transaction_date, '%Y-%m')) FROM raw_synthetic_expense")),
            "fx_min_date": _scalar(cursor, "SELECT MIN(rate_date) FROM raw_fx_rate"),
            "fx_max_date": _scalar(cursor, "SELECT MAX(rate_date) FROM raw_fx_rate"),
            "mart_min_month": _scalar(cursor, "SELECT MIN(spend_month) FROM mart_monthly_currency_spend"),
            "mart_max_month": _scalar(cursor, "SELECT MAX(spend_month) FROM mart_monthly_currency_spend"),
            "mart_month_count": int(_scalar(cursor, "SELECT COUNT(DISTINCT spend_month) FROM mart_monthly_currency_spend")),
        }
    finally:
        cursor.close()


def _as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _as_utc_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        value = datetime.fromisoformat(str(value))
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def evaluate_rules(evidence: dict[str, Any], policy: dict, manifest: dict, checked_at: datetime) -> list[dict]:
    period_start = date.fromisoformat(manifest["period_start"])
    period_end = date.fromisoformat(manifest["period_end"])
    expected_start_month = period_start.replace(day=1)
    expected_end_month = period_end.replace(day=1)
    results: list[dict] = []

    def add(rule_id: str, passed: bool, severity: str, observed: Any, expected: str, message: str) -> None:
        results.append({
            "rule_id": rule_id,
            "status": "PASS" if passed else "FAIL",
            "severity": severity,
            "observed": None if observed is None else str(observed),
            "expected": expected,
            "message": message,
        })

    last_load = _as_utc_datetime(evidence.get("last_load_at_utc"))
    if last_load is None:
        load_age_hours = None
        load_passed = False
    else:
        load_age_hours = round((checked_at - last_load).total_seconds() / 3600, 3)
        minimum_age = -float(policy["max_future_clock_skew_minutes"]) / 60
        load_passed = minimum_age <= load_age_hours <= float(policy["max_load_age_hours"])
    add(
        "operational_load_recency",
        load_passed,
        "critical",
        load_age_hours,
        f"between -{policy['max_future_clock_skew_minutes']} minutes and {policy['max_load_age_hours']} hours",
        "The latest idempotent MySQL load must belong to the current operating window.",
    )

    source_min = _as_date(evidence.get("source_min_date"))
    source_max = _as_date(evidence.get("source_max_date"))
    add(
        "source_period_boundary",
        source_min == period_start and source_max == period_end,
        "critical",
        f"{source_min}..{source_max}",
        f"{period_start}..{period_end}",
        "Expense source dates must cover the full declared scenario period.",
    )
    add(
        "source_month_partitions",
        evidence.get("source_month_count") == policy["expected_month_count"],
        "high",
        evidence.get("source_month_count"),
        str(policy["expected_month_count"]),
        "Every expected source month must be present.",
    )

    fx_min = _as_date(evidence.get("fx_min_date"))
    fx_max = _as_date(evidence.get("fx_max_date"))
    fx_end_lag = None if fx_max is None else (period_end - fx_max).days
    fx_passed = (
        fx_min is not None
        and fx_min <= period_start
        and fx_end_lag is not None
        and 0 <= fx_end_lag <= int(policy["fx_period_end_lag_days"])
    )
    add(
        "fx_period_coverage",
        fx_passed,
        "high",
        f"{fx_min}..{fx_max}; end_lag_days={fx_end_lag}",
        f"starts on/before {period_start}; ends within {policy['fx_period_end_lag_days']} days of {period_end}",
        "Cached business-day FX observations must support the scenario period.",
    )

    mart_min = _as_date(evidence.get("mart_min_month"))
    mart_max = _as_date(evidence.get("mart_max_month"))
    add(
        "mart_period_boundary",
        mart_min == expected_start_month and mart_max == expected_end_month,
        "critical",
        f"{mart_min}..{mart_max}",
        f"{expected_start_month}..{expected_end_month}",
        "The reporting mart must expose the full declared monthly period.",
    )
    add(
        "mart_month_partitions",
        evidence.get("mart_month_count") == policy["expected_month_count"],
        "high",
        evidence.get("mart_month_count"),
        str(policy["expected_month_count"]),
        "Every expected reporting month must be present.",
    )
    return results


def build_report(evidence: dict, policy: dict, manifest: dict, checked_at: datetime) -> dict:
    checks = evaluate_rules(evidence, policy, manifest, checked_at)
    failed = [check for check in checks if check["status"] == "FAIL"]
    return {
        "status": "FAIL" if failed else "PASS",
        "monitor_run_id": monitor_run_id(),
        "airflow_run_id": os.environ.get("PHASE5_RUN_ID", "manual"),
        "checked_at_utc": checked_at.isoformat(),
        "policy_version": policy["policy_version"],
        "scenario_id": manifest["scenario_id"],
        "scenario_period": {"start": manifest["period_start"], "end": manifest["period_end"]},
        "checks_passed": len(checks) - len(failed),
        "checks_failed": len(failed),
        "checks": checks,
    }


def record_report(connection, report: dict) -> None:
    run_sql = """
        INSERT INTO pipeline_freshness_run
            (monitor_run_id, airflow_run_id, checked_at_utc, policy_version,
             overall_status, checks_passed, checks_failed, report_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            checked_at_utc = VALUES(checked_at_utc),
            policy_version = VALUES(policy_version),
            overall_status = VALUES(overall_status),
            checks_passed = VALUES(checks_passed),
            checks_failed = VALUES(checks_failed),
            report_json = VALUES(report_json)
    """
    result_sql = """
        INSERT INTO pipeline_freshness_result
            (monitor_run_id, rule_id, rule_status, severity, observed_value,
             expected_value, message)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            rule_status = VALUES(rule_status),
            severity = VALUES(severity),
            observed_value = VALUES(observed_value),
            expected_value = VALUES(expected_value),
            message = VALUES(message)
    """
    cursor = connection.cursor()
    try:
        cursor.execute(run_sql, (
            report["monitor_run_id"], report["airflow_run_id"],
            datetime.fromisoformat(report["checked_at_utc"]).replace(tzinfo=None),
            report["policy_version"], report["status"], report["checks_passed"],
            report["checks_failed"], json.dumps(report, sort_keys=True),
        ))
        cursor.executemany(result_sql, [(
            report["monitor_run_id"], check["rule_id"], check["status"],
            check["severity"], check["observed"], check["expected"], check["message"],
        ) for check in report["checks"]])
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def write_report(project_root: Path, report: dict) -> Path:
    output_dir = project_root / "reports" / "airflow" / "runs" / safe_run_id()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "freshness.json"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Data freshness result",
        "",
        f"- Status: **{report['status']}**",
        f"- Checked at: `{report['checked_at_utc']}`",
        f"- Policy: `{report['policy_version']}`",
        f"- Checks: **{report['checks_passed']} passed, {report['checks_failed']} failed**",
        "",
        "| Rule | Status | Severity | Observed | Expected |",
        "|---|---|---|---|---|",
    ]
    for check in report["checks"]:
        lines.append(
            f"| `{check['rule_id']}` | {check['status']} | {check['severity']} | "
            f"{check['observed']} | {check['expected']} |"
        )
    (output_dir / "freshness.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path


def connect():
    try:
        import mysql.connector  # type: ignore
    except ImportError as exc:
        raise RuntimeError("mysql-connector-python is required") from exc
    return mysql.connector.connect(**mysql_config())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--apply-ddl", action="store_true", help="Create only the additive monitoring audit tables.")
    parser.add_argument("--no-record", action="store_true", help="Evaluate without writing MySQL audit rows.")
    args = parser.parse_args()
    project_root = args.project_root.resolve()
    policy, manifest = load_inputs(project_root)
    connection = connect()
    try:
        if args.apply_ddl:
            execute_ddl(connection, project_root / "sql" / "ddl" / "freshness_monitoring.sql")
        evidence = collect_evidence(connection)
        report = build_report(evidence, policy, manifest, utc_now())
        if not args.no_record:
            record_report(connection, report)
    finally:
        connection.close()
    output = write_report(project_root, report)
    print(json.dumps({
        "status": report["status"],
        "checks_passed": report["checks_passed"],
        "checks_failed": report["checks_failed"],
        "report": str(output),
    }, indent=2, sort_keys=True))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
