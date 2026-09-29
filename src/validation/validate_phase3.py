"""Validate Phase 3 synthetic datasets and write reconciliation evidence."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from src.synthetic.generate_phase3 import (
    FX_SOURCE,
    MONEY,
    RateLookup,
    evaluate_contract,
    load_json,
    load_or_fetch_fx_rates,
    parse_iso_date,
    write_csv,
)


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def check(results: list[dict], name: str, condition: bool, actual: object, expected: object, severity: str = "critical") -> None:
    results.append({
        "check_name": name,
        "status": "PASS" if condition else "FAIL",
        "actual": actual,
        "expected": expected,
        "severity": severity,
    })


def unique_count(rows: list[dict], column: str) -> int:
    return len({row[column] for row in rows})


def classify_quarantine(
    departments: list[dict],
    vendors: list[dict],
    contracts: list[dict],
    expenses: list[dict],
    events: list[dict],
    surveys: list[dict],
) -> dict[str, list[dict]]:
    """Classify hard failures without altering any raw source row."""
    department_ids = {row["department_id"] for row in departments}
    vendor_ids = {row["vendor_id"] for row in vendors}
    contract_ids = {row["contract_id"] for row in contracts}
    expense_ids = {row["expense_id"] for row in expenses}

    rejected_contracts = []
    for row in contracts:
        reasons = []
        try:
            start, end = parse_iso_date(row["contract_start_date"]), parse_iso_date(row["contract_end_date"])
            if start > end:
                reasons.append("contract_date_order_invalid")
        except (ValueError, TypeError):
            reasons.append("contract_date_invalid")
        try:
            if Decimal(row["contract_value_gbp"]) <= 0:
                reasons.append("contract_value_not_positive")
        except Exception:
            reasons.append("contract_value_invalid")
        if row.get("vendor_id") not in vendor_ids:
            reasons.append("vendor_fk_invalid")
        if reasons:
            rejected_contracts.append({**row, "rejection_reasons": "|".join(sorted(set(reasons)))})

    rejected_expenses = []
    for row in expenses:
        reasons = []
        required = ["expense_id", "transaction_date", "department_id", "vendor_id", "spend_category", "original_amount", "original_currency", "source_record_id"]
        if any(not str(row.get(column, "")).strip() for column in required):
            reasons.append("required_field_missing")
        try:
            parse_iso_date(row["transaction_date"])
        except (ValueError, TypeError):
            reasons.append("transaction_date_invalid")
        try:
            if Decimal(row["original_amount"]) <= 0:
                reasons.append("original_amount_not_positive")
        except Exception:
            reasons.append("original_amount_invalid")
        if row.get("original_currency") not in {"GBP", "EUR", "USD"}:
            reasons.append("currency_invalid")
        if row.get("department_id") not in department_ids:
            reasons.append("department_fk_invalid")
        if row.get("vendor_id") not in vendor_ids:
            reasons.append("vendor_fk_invalid")
        if row.get("submitted_contract_id") and row["submitted_contract_id"] not in contract_ids:
            reasons.append("submitted_contract_fk_invalid")
        if reasons:
            rejected_expenses.append({**row, "rejection_reasons": "|".join(sorted(set(reasons)))})

    events_by_expense = defaultdict(list)
    for row in events:
        events_by_expense[row.get("expense_id", "")].append(row)
    invalid_event_expenses = set()
    expected_types = ["purchase_request", "manager_approval", "finance_approval", "payment"]
    for expense_id, group in events_by_expense.items():
        try:
            ordered = sorted(group, key=lambda item: int(item["event_sequence"]))
            timestamps = [datetime.fromisoformat(item["event_timestamp_utc"]) for item in ordered]
            if len(ordered) != 4 or [item["event_type"] for item in ordered] != expected_types or timestamps != sorted(timestamps) or len(set(timestamps)) != 4:
                invalid_event_expenses.add(expense_id)
        except (ValueError, TypeError, KeyError):
            invalid_event_expenses.add(expense_id)
    rejected_events = []
    for row in events:
        reasons = []
        if row.get("expense_id") not in expense_ids:
            reasons.append("expense_fk_invalid")
        if row.get("expense_id") in invalid_event_expenses:
            reasons.append("approval_sequence_invalid")
        if reasons:
            rejected_events.append({**row, "rejection_reasons": "|".join(sorted(set(reasons)))})

    rejected_surveys = []
    for row in surveys:
        reasons = []
        if row.get("vendor_id") not in vendor_ids:
            reasons.append("vendor_fk_invalid")
        try:
            if not all(1 <= int(row[column]) <= 5 for column in ("overall_rating", "delivery_rating", "quality_rating", "support_rating")):
                reasons.append("rating_out_of_range")
        except (ValueError, TypeError, KeyError):
            reasons.append("rating_invalid")
        if reasons:
            rejected_surveys.append({**row, "rejection_reasons": "|".join(sorted(set(reasons)))})
    return {
        "synthetic_expenses_rejected.csv": rejected_expenses,
        "synthetic_contracts_rejected.csv": rejected_contracts,
        "synthetic_approval_events_rejected.csv": rejected_events,
        "synthetic_vendor_satisfaction_rejected.csv": rejected_surveys,
    }


def validate(project_root: Path, write_reports: bool = True) -> tuple[list[dict], dict]:
    config = load_json(project_root / "config" / "phase3_synthetic.json")
    raw = project_root / "data" / "raw" / "synthetic"
    processed = project_root / "data" / "processed"
    fx_dir = project_root / "data" / "raw" / "fx_rates"
    quarantine = project_root / "data" / "quarantine"
    reports = project_root / "reports"

    departments = read_csv(raw / "departments.csv")
    vendors = read_csv(raw / "vendors.csv")
    contracts = read_csv(raw / "contracts.csv")
    expenses = read_csv(raw / "expenses.csv")
    converted = read_csv(processed / "synthetic_expenses_gbp.csv")
    events = read_jsonl(raw / "approval_events.jsonl")
    cycles = read_csv(processed / "synthetic_approval_cycles.csv")
    surveys = read_csv(raw / "vendor_satisfaction.csv")

    quarantine_sets = classify_quarantine(departments, vendors, contracts, expenses, events, surveys)
    source_examples = {
        "synthetic_expenses_rejected.csv": expenses,
        "synthetic_contracts_rejected.csv": contracts,
        "synthetic_approval_events_rejected.csv": events,
        "synthetic_vendor_satisfaction_rejected.csv": surveys,
    }
    for filename, rejected_rows in quarantine_sets.items():
        examples = source_examples[filename]
        fields = [*list(examples[0]), "rejection_reasons"]
        write_csv(quarantine / filename, rejected_rows, fields)

    results: list[dict] = []
    expected_counts = {
        "departments": config["department_count"],
        "vendors": config["vendor_count"],
        "contracts": config["contract_count"],
        "expenses": config["expense_count"],
        "converted expenses": config["expense_count"],
        "approval events": config["expense_count"] * 4,
        "approval cycles": config["expense_count"],
        "survey responses": config["survey_response_count"],
    }
    actual_datasets = {
        "departments": departments,
        "vendors": vendors,
        "contracts": contracts,
        "expenses": expenses,
        "converted expenses": converted,
        "approval events": events,
        "approval cycles": cycles,
        "survey responses": surveys,
    }
    for name, rows in actual_datasets.items():
        check(results, f"row_count_{name.replace(' ', '_')}", len(rows) == expected_counts[name], len(rows), expected_counts[name])

    id_columns = {
        "departments": "department_id", "vendors": "vendor_id", "contracts": "contract_id",
        "expenses": "expense_id", "converted expenses": "expense_id", "approval events": "event_id",
        "approval cycles": "expense_id", "survey responses": "response_id",
    }
    for name, column in id_columns.items():
        rows = actual_datasets[name]
        check(results, f"unique_{name.replace(' ', '_')}_{column}", unique_count(rows, column) == len(rows), unique_count(rows, column), len(rows))

    department_ids = {row["department_id"] for row in departments}
    vendor_ids = {row["vendor_id"] for row in vendors}
    contract_ids = {row["contract_id"] for row in contracts}
    expense_ids = {row["expense_id"] for row in expenses}
    check(results, "expense_department_fk", all(row["department_id"] in department_ids for row in expenses), sum(row["department_id"] not in department_ids for row in expenses), 0)
    check(results, "expense_vendor_fk", all(row["vendor_id"] in vendor_ids for row in expenses), sum(row["vendor_id"] not in vendor_ids for row in expenses), 0)
    check(results, "contract_vendor_fk", all(row["vendor_id"] in vendor_ids for row in contracts), sum(row["vendor_id"] not in vendor_ids for row in contracts), 0)
    check(results, "submitted_contract_fk", all(not row["submitted_contract_id"] or row["submitted_contract_id"] in contract_ids for row in expenses), sum(bool(row["submitted_contract_id"]) and row["submitted_contract_id"] not in contract_ids for row in expenses), 0)
    check(results, "approval_expense_fk", all(row["expense_id"] in expense_ids for row in events), sum(row["expense_id"] not in expense_ids for row in events), 0)
    check(results, "survey_vendor_fk", all(row["vendor_id"] in vendor_ids for row in surveys), sum(row["vendor_id"] not in vendor_ids for row in surveys), 0)

    currency_counts = Counter(row["original_currency"] for row in expenses)
    check(results, "currency_distribution", currency_counts == Counter(config["currency_counts"]), json.dumps(dict(sorted(currency_counts.items()))), json.dumps(config["currency_counts"], sort_keys=True))
    check(results, "allowed_currencies", set(currency_counts) == {"GBP", "EUR", "USD"}, ",".join(sorted(currency_counts)), "EUR,GBP,USD")
    start, end = parse_iso_date(config["period_start"]), parse_iso_date(config["period_end"])
    check(results, "expense_date_range", all(start <= parse_iso_date(row["transaction_date"]) <= end for row in expenses), "all rows in range", f"{start}..{end}")
    check(results, "positive_original_amount", all(Decimal(row["original_amount"]) > 0 for row in expenses), sum(Decimal(row["original_amount"]) <= 0 for row in expenses), 0)

    contracts_by_id = {row["contract_id"]: row for row in contracts}
    contracts_by_vendor = defaultdict(list)
    for row in contracts:
        contracts_by_vendor[row["vendor_id"]].append(row)
    recomputed = {}
    for row in expenses:
        recomputed[row["expense_id"]] = evaluate_contract(row, contracts_by_id, contracts_by_vendor)
    contract_mismatches = sum(
        recomputed[row["expense_id"]] != (row["contract_compliance_status"], row["matched_contract_id"])
        for row in converted
    )
    check(results, "contract_match_reconciliation", contract_mismatches == 0, contract_mismatches, 0)
    invalid_contract_ranges = sum(parse_iso_date(row["contract_start_date"]) > parse_iso_date(row["contract_end_date"]) for row in contracts)
    check(results, "contract_date_order", invalid_contract_ranges == 0, invalid_contract_ranges, 0)

    fx_start = start - __import__("datetime").timedelta(days=config["fx_lookback_days"])
    observations = {
        currency: load_or_fetch_fx_rates(fx_dir, config["frankfurter_api_base"], currency, fx_start, end, offline=True)
        for currency in ("EUR", "USD")
    }
    lookup = RateLookup(observations)
    raw_by_id = {row["expense_id"]: row for row in expenses}
    fx_mismatches = 0
    fx_future_dates = 0
    for row in converted:
        source = raw_by_id[row["expense_id"]]
        currency = source["original_currency"]
        transaction_date = parse_iso_date(source["transaction_date"])
        rate, rate_date, fx_source, _ = lookup.get(currency, transaction_date)
        expected_gbp = (Decimal(source["original_amount"]) * rate).quantize(MONEY, rounding=ROUND_HALF_UP)
        if Decimal(row["fx_rate_to_gbp"]) != rate.quantize(Decimal("0.0000000001")) or Decimal(row["amount_gbp"]) != expected_gbp or parse_iso_date(row["fx_rate_date"]) != rate_date:
            fx_mismatches += 1
        if parse_iso_date(row["fx_rate_date"]) > transaction_date:
            fx_future_dates += 1
        if not row["fx_cache_file"]:
            fx_mismatches += 1
        if currency == "GBP" and row["fx_cache_file"] != "GBP_IDENTITY":
            fx_mismatches += 1
        if currency != "GBP" and row["fx_source"] != FX_SOURCE:
            fx_mismatches += 1
    check(results, "fx_conversion_reconciliation", fx_mismatches == 0, fx_mismatches, 0)
    check(results, "fx_rate_not_after_transaction", fx_future_dates == 0, fx_future_dates, 0)

    events_by_expense = defaultdict(list)
    for row in events:
        events_by_expense[row["expense_id"]].append(row)
    expected_event_types = ["purchase_request", "manager_approval", "finance_approval", "payment"]
    invalid_sequences = 0
    for expense_id in expense_ids:
        ordered = sorted(events_by_expense[expense_id], key=lambda row: int(row["event_sequence"]))
        timestamps = [datetime.fromisoformat(row["event_timestamp_utc"]) for row in ordered]
        if len(ordered) != 4 or [row["event_type"] for row in ordered] != expected_event_types or timestamps != sorted(timestamps) or len(set(timestamps)) != 4:
            invalid_sequences += 1
    check(results, "approval_event_sequence", invalid_sequences == 0, invalid_sequences, 0)

    rating_errors = sum(
        not all(1 <= int(row[column]) <= 5 for column in ("overall_rating", "delivery_rating", "quality_rating", "support_rating"))
        for row in surveys
    )
    check(results, "survey_rating_range", rating_errors == 0, rating_errors, 0)

    synthetic_lineage_errors = sum(
        row.get("record_origin") != "synthetic_fictional_company" or str(row.get("is_synthetic")).lower() != "true"
        for rows in actual_datasets.values() for row in rows
    )
    check(results, "synthetic_lineage_labels", synthetic_lineage_errors == 0, synthetic_lineage_errors, 0)
    defra_path = processed / "defra_transactions_profiled.csv"
    defra = read_csv(defra_path) if defra_path.exists() else []
    defra_lineage_errors = sum(row["record_origin"] != "real_public_defra" or row["is_synthetic"] != "false" for row in defra)
    check(results, "defra_lineage_unchanged", bool(defra) and defra_lineage_errors == 0, defra_lineage_errors if defra else "DEFRA file missing", 0)

    quarantined_count = sum(len(rows) for rows in quarantine_sets.values())
    check(results, "quarantine_count", quarantined_count == 0, quarantined_count, 0, severity="high")

    summary = {
        "checks_total": len(results),
        "checks_passed": sum(row["status"] == "PASS" for row in results),
        "checks_failed": sum(row["status"] == "FAIL" for row in results),
        "expense_count": len(expenses),
        "approval_event_count": len(events),
        "currency_counts": dict(sorted(currency_counts.items())),
        "contract_status_counts": dict(sorted(Counter(row["contract_compliance_status"] for row in converted).items())),
        "approval_sla_breach_count": sum(row["approval_sla_breached"] == "true" for row in cycles),
        "quarantined_count": quarantined_count,
    }

    if write_reports:
        write_csv(reports / "phase3_reconciliation.csv", results, ["check_name", "status", "actual", "expected", "severity"])
        lines = [
            "# Phase 3 synthetic data and multi-currency report",
            "",
            "## Scope",
            "",
            "All records in this phase describe a fictional company. They are separated from real DEFRA records by source directories, table design, `record_origin`, and `is_synthetic`.",
            "",
            "## Generated datasets",
            "",
            "| Dataset | Rows | Grain |",
            "|---|---:|---|",
            f"| Departments | {len(departments):,} | One fictional department |",
            f"| Vendors | {len(vendors):,} | One fictional vendor |",
            f"| Contracts | {len(contracts):,} | One fictional contract |",
            f"| Expenses | {len(expenses):,} | One fictional expense |",
            f"| Approval events | {len(events):,} | One workflow event |",
            f"| Approval cycles | {len(cycles):,} | One expense approval workflow |",
            f"| Satisfaction responses | {len(surveys):,} | One fictional survey response |",
            "",
            "## Reconciliation",
            "",
            f"Automated checks passed: **{summary['checks_passed']} of {summary['checks_total']}**. Failed: **{summary['checks_failed']}**. Quarantined: **{quarantined_count}**.",
            "",
            f"Currency distribution: `{json.dumps(summary['currency_counts'], sort_keys=True)}`. Contract-match statuses: `{json.dumps(summary['contract_status_counts'], sort_keys=True)}`.",
            "",
            f"Approval SLA breaches under the configured {config['approval_sla_hours']}-hour request-to-finance rule: **{summary['approval_sla_breach_count']:,} of {len(cycles):,}**. This is a generated scenario result, not a benchmark or real-company metric.",
            "",
            "## FX method",
            "",
            "EUR and USD are converted using cached Frankfurter v2 rates quoted directly as GBP per unit of original currency. The applied observation is the latest available rate on or before the transaction date. GBP uses an identity rate of 1. Calculations use `Decimal` and round GBP outputs to two decimal places with ROUND_HALF_UP.",
            "",
            "## Contract method",
            "",
            "A submitted contract is compliant only when vendor, approved category, and transaction date agree with the contract master. If the submitted contract fails, the matcher searches for another active master contract before assigning a non-compliant result. A blank contract reference therefore does not automatically mean off-contract spend.",
            "",
            "## Quarantine interpretation",
            "",
            "Zero quarantined rows means the deterministic generator produced no records that violated the current hard validation rules. It does not mean that the scenario is free from warnings, modelling assumptions, or business limitations.",
            "",
            "## MySQL execution status",
            "",
            "The repository had no implemented MySQL loader or deployed schema at the start of Phase 3, and this environment has no MySQL client or server. MySQL DDL and an idempotent loader are supplied as implementation artifacts, but database row counts and second-run behaviour remain unverified against a live MySQL instance.",
            "",
        ]
        (reports / "phase3_report.md").write_text("\n".join(lines), encoding="utf-8")
    return results, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    args = parser.parse_args()
    results, summary = validate(args.project_root.resolve())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if any(row["status"] == "FAIL" for row in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
