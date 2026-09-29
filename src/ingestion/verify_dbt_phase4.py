"""Run the live Phase 4 dbt workflow and write credential-free evidence reports."""

from __future__ import annotations

import getpass
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal

import mysql.connector


MODEL_RELATIONS = [
    "int_synthetic_spend",
    "int_approval_cycles",
    "mart_department_spend",
    "mart_vendor_performance",
    "mart_contract_compliance",
    "mart_approval_performance",
    "mart_monthly_currency_spend",
]


def run_dbt(project_root: Path, args: list[str], env: dict[str, str]) -> dict:
    dbt_exe = Path(sys.executable).with_name("dbt.exe")
    command = [str(dbt_exe), *args, "--project-dir", "dbt", "--profiles-dir", "dbt", "--no-use-colors"]
    completed = subprocess.run(
        command,
        cwd=project_root,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    output = completed.stdout + completed.stderr
    print(output, end="")
    log_name = "dbt_" + "_".join(args).replace(":", "_") + ".log"
    (project_root / "reports" / log_name).write_text(output, encoding="utf-8")
    return {"command": "dbt " + " ".join(args), "exit_code": completed.returncode, "log": f"reports/{log_name}"}


def scalar(cursor, sql: str):
    cursor.execute(sql)
    return cursor.fetchone()[0]


def collect_database_evidence(connection) -> dict:
    cursor = connection.cursor()
    try:
        counts = {name: int(scalar(cursor, f"SELECT COUNT(*) FROM `{name}`")) for name in MODEL_RELATIONS}
        cursor.execute(
            "SELECT original_currency, COUNT(*), SUM(original_amount), SUM(amount_gbp) "
            "FROM int_synthetic_spend GROUP BY original_currency ORDER BY original_currency"
        )
        currency = {
            row[0]: {
                "row_count": int(row[1]),
                "original_amount": format(Decimal(row[2]), "f"),
                "amount_gbp": format(Decimal(row[3]), "f"),
            }
            for row in cursor.fetchall()
        }
        evidence = {
            "relation_counts": counts,
            "currency_reconciliation": currency,
            "total_amount_gbp": format(Decimal(scalar(cursor, "SELECT SUM(amount_gbp) FROM int_synthetic_spend")), "f"),
            "baseline_total_amount_gbp": format(Decimal(scalar(cursor, "SELECT SUM(amount_gbp) FROM fact_synthetic_spend")), "f"),
            "approval_sla_breach_count": int(scalar(cursor, "SELECT SUM(approval_sla_breached) FROM int_approval_cycles")),
            "spend_row_mismatches": int(scalar(cursor, """
                SELECT COUNT(*) FROM int_synthetic_spend d
                JOIN fact_synthetic_spend p ON d.expense_id=p.expense_id
                WHERE d.amount_gbp<>p.amount_gbp
                   OR d.fx_rate_to_gbp<>p.fx_rate_to_gbp
                   OR d.fx_rate_date<>p.fx_rate_date
                   OR NOT (d.matched_contract_id <=> p.matched_contract_id)
                   OR d.contract_compliance_status<>p.contract_compliance_status
            """)),
            "approval_row_mismatches": int(scalar(cursor, """
                SELECT COUNT(*) FROM int_approval_cycles d
                JOIN fact_synthetic_approval p ON d.expense_id=p.expense_id
                WHERE d.approval_cycle_hours<>p.approval_cycle_hours
                   OR d.request_to_payment_hours<>p.request_to_payment_hours
                   OR d.approval_sla_breached<>p.approval_sla_breached
            """)),
        }
        return evidence
    finally:
        cursor.close()


def write_report(project_root: Path, report: dict) -> None:
    reports = project_root / "reports"
    reports.mkdir(exist_ok=True)
    json_path = reports / "dbt_live_verification.json"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    command_rows = "\n".join(
        f"| `{item['command']}` | {item['exit_code']} | `{item['log']}` |" for item in report["commands"]
    )
    db = report.get("database_evidence", {})
    count_rows = "\n".join(f"| `{name}` | {count:,} |" for name, count in db.get("relation_counts", {}).items())
    currency_rows = "\n".join(
        f"| {code} | {values['row_count']:,} | {values['original_amount']} | {values['amount_gbp']} |"
        for code, values in db.get("currency_reconciliation", {}).items()
    )
    status = "PASS" if report["all_commands_passed"] and report.get("reconciliation_passed") else "FAIL"
    markdown = f"""# Phase 4 dbt live verification

Status: **{status}**  
Generated: `{report['generated_at_utc']}`

## Runtime

- Python: `{report['versions']['python']}`
- dbt Core: `{report['versions']['dbt_core']}`
- dbt MySQL adapter: `{report['versions']['dbt_mysql']}`
- MySQL Server: `{report.get('mysql_server_version', 'not queried')}`

## Commands

| Command | Exit code | Log |
|---|---:|---|
{command_rows}

## Built relation counts

| Relation | Rows |
|---|---:|
{count_rows}

## Currency reconciliation

| Currency | Rows | Original amount | GBP amount |
|---|---:|---:|---:|
{currency_rows}

dbt total GBP: **{db.get('total_amount_gbp', 'not queried')}**  
Phase 3 baseline GBP: **{db.get('baseline_total_amount_gbp', 'not queried')}**  
Spend row mismatches: **{db.get('spend_row_mismatches', 'not queried')}**  
Approval row mismatches: **{db.get('approval_row_mismatches', 'not queried')}**

All data in these dbt models is labelled synthetic. No DEFRA table was loaded or modelled in Phase 4 because no DEFRA MySQL source table exists.
"""
    (reports / "dbt_live_verification.md").write_text(markdown, encoding="utf-8")


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    password = os.environ.get("DBT_MYSQL_PASSWORD") or getpass.getpass("MySQL password for spend_app@127.0.0.1: ")
    env = os.environ.copy()
    env.update({
        "DBT_MYSQL_HOST": env.get("DBT_MYSQL_HOST", "127.0.0.1"),
        "DBT_MYSQL_PORT": env.get("DBT_MYSQL_PORT", "3306"),
        "DBT_MYSQL_DATABASE": env.get("DBT_MYSQL_DATABASE", "enterprise_spend"),
        "DBT_MYSQL_USER": env.get("DBT_MYSQL_USER", "spend_app"),
        "DBT_MYSQL_PASSWORD": password,
        # dbt logs the interpreter path. The repository path contains Korean
        # characters, so Windows' cp1252 default can raise and hang colorama.
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "NO_COLOR": "1",
    })
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "versions": {
            "python": sys.version.split()[0],
            "dbt_core": importlib.metadata.version("dbt-core"),
            "dbt_mysql": importlib.metadata.version("dbt-mysql"),
        },
        "commands": [],
    }
    for args in (["debug"], ["build"], ["test"], ["docs", "generate"]):
        result = run_dbt(project_root, list(args), env)
        report["commands"].append(result)
        if result["exit_code"] != 0:
            break
    report["all_commands_passed"] = len(report["commands"]) == 4 and all(
        item["exit_code"] == 0 for item in report["commands"]
    )

    if report["all_commands_passed"]:
        connection = mysql.connector.connect(
            host=env["DBT_MYSQL_HOST"],
            port=int(env["DBT_MYSQL_PORT"]),
            user=env["DBT_MYSQL_USER"],
            password=password,
            database=env["DBT_MYSQL_DATABASE"],
        )
        try:
            report["mysql_server_version"] = connection.server_info
            report["database_evidence"] = collect_database_evidence(connection)
        finally:
            connection.close()
        db = report["database_evidence"]
        report["reconciliation_passed"] = (
            db["relation_counts"]["int_synthetic_spend"] == 5000
            and db["relation_counts"]["int_approval_cycles"] == 5000
            and db["total_amount_gbp"] == "1160936638.63"
            and db["total_amount_gbp"] == db["baseline_total_amount_gbp"]
            and db["spend_row_mismatches"] == 0
            and db["approval_row_mismatches"] == 0
        )
    else:
        report["reconciliation_passed"] = False

    write_report(project_root, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["all_commands_passed"] or not report["reconciliation_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
