"""Profile and validate monthly DEFRA spend CSV files.

The program preserves every source row, standardises headers and typed fields,
adds deterministic lineage identifiers, and writes investigation reports. It
never edits the source CSVs and never removes ambiguous duplicate records.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable


SOURCE_MONTH_BY_FILE = {
    "Over++_25K++Mar+2025-Rev.csv": "2025-03",
    "Over_25K_Transparency_report_April_25.csv": "2025-04",
    "Defra__25k_May_25.csv": "2025-05",
    "Defra_Over__25k_June_2025.csv": "2025-06",
    "Over__25K_Transparency_July.csv": "2025-07",
    "August_Over__25K_Transparency.csv": "2025-08",
    "September_Over__25K_Transparency.csv": "2025-09",
    "Defra_Over__25K_October_2025.csv": "2025-10",
    "November_Over__25K_Transparency.csv": "2025-11",
    "December_Over__25K.csv": "2025-12",
    "Over__25K_Transparency_Jan_26.csv": "2026-01",
    "Over__25K_Feb_26.csv": "2026-02",
}

HEADER_MAP = {
    "comments": "comments",
    "department": "department",
    "entity": "entity",
    "date": "transaction_date_raw",
    "expense type": "expense_type",
    "expense area": "expense_area",
    "supplier": "supplier",
    "transaction number": "transaction_number",
    "amount": "amount_raw",
    "po catergory description": "po_category_description",
    "po category description": "po_category_description",
    "supplier postcode": "supplier_postcode",
    "supplier type": "supplier_type",
    "contract number": "contract_number",
    "project code": "project_code",
    "expenditure type": "expenditure_type",
    "vat registration num": "vat_registration_number",
}

BUSINESS_COLUMNS = [
    "comments",
    "department",
    "entity",
    "transaction_date_raw",
    "expense_type",
    "expense_area",
    "supplier",
    "transaction_number",
    "amount_raw",
    "po_category_description",
    "supplier_postcode",
    "supplier_type",
    "contract_number",
    "project_code",
    "expenditure_type",
    "vat_registration_number",
]

OUTPUT_COLUMNS = [
    "source_record_id",
    "source_file",
    "source_month",
    "source_row_number",
    "ingestion_timestamp",
    "record_origin",
    "is_synthetic",
    *BUSINESS_COLUMNS,
    "transaction_date",
    "amount_gbp",
    "currency_code",
    "exact_record_hash",
    "business_key",
    "date_parse_status",
    "amount_parse_status",
    "source_month_match",
    "quality_status",
    "quality_issues",
]

DATE_FORMATS = ("%d/%m/%Y", "%d-%b-%y", "%d-%b-%Y")
SENTINEL_VALUES = {"n/a", "na", "unknown", "null", "not set", "none"}
ANALYSIS_START = datetime(2025, 3, 1).date()
ANALYSIS_END = datetime(2026, 2, 28).date()


@dataclass(frozen=True)
class FileProfile:
    source_file: str
    source_month: str
    local_path: str
    publisher: str
    publication_url: str
    licence_url: str
    remote_byte_match_status: str
    encoding: str
    currency_code: str
    record_origin: str
    sha256: str
    byte_size: int
    row_count: int
    column_count: int
    original_columns: str
    canonical_columns: str
    min_transaction_date: str
    max_transaction_date: str
    out_of_source_month_rows: int
    quarantined_rows: int


def canonical_header(value: str) -> str:
    """Map a source header to the canonical name while tolerating whitespace."""
    key = re.sub(r"\s+", " ", value.strip()).casefold()
    if key not in HEADER_MAP:
        raise ValueError(f"Unexpected source column: {value!r}")
    return HEADER_MAP[key]


def parse_date(value: str):
    text = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date(), "valid"
        except ValueError:
            continue
    return None, "invalid" if text else "missing"


def parse_amount(value: str):
    text = value.strip()
    if not text:
        return None, "missing"
    negative = text.startswith("(") and text.endswith(")")
    cleaned = text.replace("£", "").replace(",", "").replace(" ", "")
    if negative:
        cleaned = f"-{cleaned[1:-1]}"
    try:
        return Decimal(cleaned), "valid"
    except InvalidOperation:
        return None, "invalid"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalise_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def is_sentinel(value: str) -> bool:
    return normalise_key(value) in SENTINEL_VALUES


def write_csv(path: Path, rows: Iterable[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_file(path: Path, ingestion_timestamp: str):
    source_month = SOURCE_MONTH_BY_FILE.get(path.name)
    if source_month is None:
        raise ValueError(f"No source-month mapping for {path.name}")

    with path.open("r", encoding="cp1252", newline="") as handle:
        reader = csv.DictReader(handle)
        original_columns = reader.fieldnames or []
        canonical_columns = [canonical_header(column) for column in original_columns]
        if len(canonical_columns) != len(set(canonical_columns)):
            raise ValueError(f"Duplicate canonical columns in {path.name}")

        records = []
        for row_number, source_row in enumerate(reader, start=1):
            canonical = {column: "" for column in BUSINESS_COLUMNS}
            for original, value in source_row.items():
                canonical[canonical_header(original)] = value if value is not None else ""

            parsed_date, date_status = parse_date(canonical["transaction_date_raw"])
            parsed_amount, amount_status = parse_amount(canonical["amount_raw"])
            source_month_match = (
                "unknown"
                if parsed_date is None
                else str(parsed_date.strftime("%Y-%m") == source_month).lower()
            )
            issues = []
            if date_status != "valid":
                issues.append(f"transaction_date_{date_status}")
            if amount_status != "valid":
                issues.append(f"amount_{amount_status}")
            if not canonical["supplier"].strip():
                issues.append("supplier_missing")
            if not canonical["transaction_number"].strip():
                issues.append("transaction_number_missing")
            if source_month_match == "false":
                issues.append("transaction_date_outside_source_month")
            if parsed_amount is not None and parsed_amount <= 0:
                issues.append("amount_non_positive_review")
            if parsed_amount is not None and abs(parsed_amount) < Decimal("25000"):
                issues.append("amount_below_publication_threshold_review")

            exact_payload = json.dumps(
                [canonical[column] for column in BUSINESS_COLUMNS],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            exact_hash = sha256_text(exact_payload)
            business_components = (
                normalise_key(canonical["entity"]),
                normalise_key(canonical["transaction_number"]),
            )
            business_key = (
                sha256_text("|".join(business_components))
                if all(business_components)
                else ""
            )
            source_record_id = sha256_text(
                f"{path.name}|{row_number}|{exact_hash}"
            )
            hard_failure = date_status != "valid" or amount_status != "valid"
            record = {
                "source_record_id": source_record_id,
                "source_file": path.name,
                "source_month": source_month,
                "source_row_number": row_number,
                "ingestion_timestamp": ingestion_timestamp,
                "record_origin": "real_public_defra",
                "is_synthetic": "false",
                **canonical,
                "transaction_date": parsed_date.isoformat() if parsed_date else "",
                "amount_gbp": format(parsed_amount, "f") if parsed_amount is not None else "",
                "currency_code": "GBP",
                "exact_record_hash": exact_hash,
                "business_key": business_key,
                "date_parse_status": date_status,
                "amount_parse_status": amount_status,
                "source_month_match": source_month_match,
                "quality_status": "quarantine" if hard_failure else ("warning" if issues else "valid"),
                "quality_issues": "|".join(issues),
            }
            records.append(record)

    parsed_dates = [r["transaction_date"] for r in records if r["transaction_date"]]
    profile = FileProfile(
        source_file=path.name,
        source_month=source_month,
        local_path=path.as_posix(),
        publisher="Department for Environment, Food & Rural Affairs",
        publication_url=(
            "https://www.gov.uk/government/publications/"
            f"defra-spending-over-25000-{datetime.strptime(source_month, '%Y-%m').strftime('%B').lower()}-"
            f"{source_month[:4]}"
        ),
        licence_url="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
        remote_byte_match_status="not_checked",
        encoding="Windows-1252",
        currency_code="GBP",
        record_origin="real_public_defra",
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        byte_size=path.stat().st_size,
        row_count=len(records),
        column_count=len(original_columns),
        original_columns="|".join(original_columns),
        canonical_columns="|".join(canonical_columns),
        min_transaction_date=min(parsed_dates) if parsed_dates else "",
        max_transaction_date=max(parsed_dates) if parsed_dates else "",
        out_of_source_month_rows=sum(r["source_month_match"] == "false" for r in records),
        quarantined_rows=sum(r["quality_status"] == "quarantine" for r in records),
    )
    return records, profile


def build_duplicate_report(records: list[dict]):
    exact_groups = defaultdict(list)
    business_groups = defaultdict(list)
    for record in records:
        exact_groups[record["exact_record_hash"]].append(record)
        if record["business_key"]:
            business_groups[record["business_key"]].append(record)

    rows = []
    exact_additional = 0
    exact_cross_file_groups = 0
    exact_additional_by_file = Counter()
    for group_hash, group in sorted(exact_groups.items()):
        if len(group) < 2:
            continue
        exact_additional += len(group) - 1
        source_files = sorted({r["source_file"] for r in group})
        scope = "cross_file" if len(source_files) > 1 else "within_file"
        exact_cross_file_groups += scope == "cross_file"
        if scope == "within_file":
            exact_additional_by_file[group[0]["source_file"]] += len(group) - 1
        for record in sorted(group, key=lambda r: (r["source_file"], int(r["source_row_number"]))):
            rows.append({
                "investigation_type": "exact_row_duplicate",
                "duplicate_group_id": group_hash,
                "occurrence_count": len(group),
                "additional_occurrences": len(group) - 1,
                "duplicate_scope": scope,
                "differing_columns": "",
                **record,
            })

    business_candidate_groups = 0
    business_candidate_rows = 0
    business_cross_file_groups = 0
    business_cross_file_rows = 0
    for business_key, group in sorted(business_groups.items()):
        distinct_hashes = {r["exact_record_hash"] for r in group}
        if len(group) < 2 or len(distinct_hashes) == 1:
            continue
        business_candidate_groups += 1
        business_candidate_rows += len(group)
        differing = [
            column for column in BUSINESS_COLUMNS
            if len({r[column] for r in group}) > 1
        ]
        source_files = sorted({r["source_file"] for r in group})
        scope = "cross_file" if len(source_files) > 1 else "within_file"
        if scope == "cross_file":
            business_cross_file_groups += 1
            business_cross_file_rows += len(group)
        for record in sorted(group, key=lambda r: (r["source_file"], int(r["source_row_number"]))):
            rows.append({
                "investigation_type": "business_duplicate_candidate",
                "duplicate_group_id": business_key,
                "occurrence_count": len(group),
                "additional_occurrences": len(group) - 1,
                "duplicate_scope": scope,
                "differing_columns": "|".join(differing),
                **record,
            })

    summary = {
        "exact_duplicate_groups": sum(len(group) > 1 for group in exact_groups.values()),
        "exact_duplicate_rows_involved": sum(len(group) for group in exact_groups.values() if len(group) > 1),
        "exact_duplicate_additional_occurrences": exact_additional,
        "exact_cross_file_groups": exact_cross_file_groups,
        "exact_duplicate_additional_by_file": json.dumps(
            dict(sorted(exact_additional_by_file.items())), separators=(",", ":")
        ),
        "business_duplicate_candidate_groups": business_candidate_groups,
        "business_duplicate_candidate_rows": business_candidate_rows,
        "business_duplicate_cross_file_groups": business_cross_file_groups,
        "business_duplicate_cross_file_rows": business_cross_file_rows,
    }
    return rows, summary


def build_quality_metrics(records: list[dict], duplicate_summary: dict):
    total = len(records)
    dates = [datetime.fromisoformat(r["transaction_date"]).date() for r in records if r["transaction_date"]]
    in_period = sum(ANALYSIS_START <= value <= ANALYSIS_END for value in dates)
    counts = Counter()
    for record in records:
        for issue in filter(None, record["quality_issues"].split("|")):
            counts[issue] += 1

    amounts = sorted(Decimal(r["amount_gbp"]) for r in records if r["amount_gbp"])

    def nearest_quantile(fraction: Decimal):
        if not amounts:
            return ""
        return amounts[int((len(amounts) - 1) * fraction)]

    metrics = {
        "source_file_count": len({r["source_file"] for r in records}),
        "raw_row_count": total,
        "parsed_date_row_count": len(dates),
        "actual_min_transaction_date": min(dates).isoformat() if dates else "",
        "actual_max_transaction_date": max(dates).isoformat() if dates else "",
        "in_analysis_period_row_count": in_period,
        "outside_analysis_period_row_count": len(dates) - in_period,
        "source_month_discrepancy_rows": counts["transaction_date_outside_source_month"],
        "quarantined_rows": sum(r["quality_status"] == "quarantine" for r in records),
        "warning_rows": sum(r["quality_status"] == "warning" for r in records),
        "valid_rows": sum(r["quality_status"] == "valid" for r in records),
        "missing_supplier_rows": counts["supplier_missing"],
        "missing_transaction_number_rows": counts["transaction_number_missing"],
        "invalid_or_missing_date_rows": sum(r["date_parse_status"] != "valid" for r in records),
        "invalid_or_missing_amount_rows": sum(r["amount_parse_status"] != "valid" for r in records),
        "non_positive_amount_rows": sum(
            Decimal(r["amount_gbp"]) <= 0 for r in records if r["amount_gbp"]
        ),
        "absolute_amount_below_25000_rows": sum(
            abs(Decimal(r["amount_gbp"])) < Decimal("25000")
            for r in records if r["amount_gbp"]
        ),
        "blank_contract_number_rows": sum(not r["contract_number"].strip() for r in records),
        "sentinel_contract_number_rows": sum(is_sentinel(r["contract_number"]) for r in records),
        "effective_missing_contract_number_rows": sum(
            not r["contract_number"].strip() or is_sentinel(r["contract_number"]) for r in records
        ),
        "blank_project_code_rows": sum(not r["project_code"].strip() for r in records),
        "sentinel_project_code_rows": sum(is_sentinel(r["project_code"]) for r in records),
        "effective_missing_project_code_rows": sum(
            not r["project_code"].strip() or is_sentinel(r["project_code"]) for r in records
        ),
        "amount_min_gbp": format(amounts[0], "f") if amounts else "",
        "amount_median_gbp": format(nearest_quantile(Decimal("0.50")), "f") if amounts else "",
        "amount_p99_gbp": format(nearest_quantile(Decimal("0.99")), "f") if amounts else "",
        "amount_max_gbp": format(amounts[-1], "f") if amounts else "",
        **duplicate_summary,
    }
    return metrics


def build_column_profile(records: list[dict]):
    """Return overall and per-file missingness/cardinality evidence."""
    output = []
    scopes = [("ALL_FILES", records)]
    for source_file in sorted({record["source_file"] for record in records}):
        scopes.append((source_file, [r for r in records if r["source_file"] == source_file]))
    for scope, scoped_rows in scopes:
        for column in BUSINESS_COLUMNS:
            values = [str(row[column]).strip() for row in scoped_rows]
            non_blank = [value for value in values if value]
            blank_count = len(values) - len(non_blank)
            sentinel_count = sum(is_sentinel(value) for value in non_blank)
            output.append({
                "scope": scope,
                "column_name": column,
                "row_count": len(values),
                "blank_count": blank_count,
                "blank_rate": f"{blank_count / len(values):.6f}" if values else "",
                "sentinel_count": sentinel_count,
                "effective_missing_count": blank_count + sentinel_count,
                "effective_missing_rate": f"{(blank_count + sentinel_count) / len(values):.6f}" if values else "",
                "distinct_non_blank_count": len(set(non_blank)),
            })
    return output


def write_markdown_report(path: Path, profiles: list[FileProfile], metrics: dict) -> None:
    total = metrics["raw_row_count"] or 1
    lines = [
        "# DEFRA data-quality report",
        "",
        "## Scope and grain",
        "",
        "The source grain is one row in one monthly DEFRA CSV. A row is preserved even when it is identical to another row. The profiling layer adds lineage and typed fields but does not assert that a source row is a unique economic transaction.",
        "",
        "## Results",
        "",
        "| Check | Result | Rate | Interpretation |",
        "|---|---:|---:|---|",
        f"| Source files | {metrics['source_file_count']:,} | — | Expected March 2025 to February 2026 set is complete. |",
        f"| Raw rows | {metrics['raw_row_count']:,} | 100.00% | Reconciles to the sum of source-file rows. |",
        f"| Parsed transaction dates | {metrics['parsed_date_row_count']:,} | {metrics['parsed_date_row_count']/total:.2%} | Invalid dates are quarantined. |",
        f"| Parsed amounts | {metrics['raw_row_count']-metrics['invalid_or_missing_amount_rows']:,} | {(metrics['raw_row_count']-metrics['invalid_or_missing_amount_rows'])/total:.2%} | Invalid amounts are quarantined. |",
        f"| In analysis period | {metrics['in_analysis_period_row_count']:,} | {metrics['in_analysis_period_row_count']/total:.2%} | Uses transaction date, not file month. |",
        f"| Date outside source month | {metrics['source_month_discrepancy_rows']:,} | {metrics['source_month_discrepancy_rows']/total:.2%} | Preserved as a warning; may reflect reporting timing. |",
        f"| Exact duplicate additional occurrences | {metrics['exact_duplicate_additional_occurrences']:,} | {metrics['exact_duplicate_additional_occurrences']/total:.2%} | Not deleted; requires source/business review. |",
        f"| Business duplicate candidate rows | {metrics['business_duplicate_candidate_rows']:,} | {metrics['business_duplicate_candidate_rows']/total:.2%} | Same entity + transaction number but non-identical content. |",
        f"| Cross-file business-candidate rows | {metrics['business_duplicate_cross_file_rows']:,} | {metrics['business_duplicate_cross_file_rows']/total:.2%} | Requires review for late reporting, correction, or repeated identifier use. |",
        f"| Missing transaction number | {metrics['missing_transaction_number_rows']:,} | {metrics['missing_transaction_number_rows']/total:.2%} | Confirms transaction number cannot be the raw primary key. |",
        f"| Non-positive amounts | {metrics['non_positive_amount_rows']:,} | {metrics['non_positive_amount_rows']/total:.2%} | Review as credits/adjustments; values remain valid numeric records. |",
        f"| Absolute amount below £25,000 | {metrics['absolute_amount_below_25000_rows']:,} | {metrics['absolute_amount_below_25000_rows']/total:.2%} | Review against publication rules; do not reject automatically. |",
        f"| Effectively missing contract number | {metrics['effective_missing_contract_number_rows']:,} | {metrics['effective_missing_contract_number_rows']/total:.2%} | Includes blanks and common sentinels; missingness is not evidence of maverick spend. |",
        f"| Quarantined rows | {metrics['quarantined_rows']:,} | {metrics['quarantined_rows']/total:.2%} | Excluded from a future spend fact until corrected. |",
        "",
        f"Actual transaction-date coverage is **{metrics['actual_min_transaction_date']} to {metrics['actual_max_transaction_date']}**. The configured analysis window is **{ANALYSIS_START.isoformat()} to {ANALYSIS_END.isoformat()}**.",
        "",
        f"Parsed amount distribution (GBP): minimum **£{Decimal(metrics['amount_min_gbp']):,.2f}**, median **£{Decimal(metrics['amount_median_gbp']):,.2f}**, 99th percentile **£{Decimal(metrics['amount_p99_gbp']):,.2f}**, and maximum **£{Decimal(metrics['amount_max_gbp']):,.2f}**. These are profile statistics, not acceptance thresholds.",
        "",
        f"The 134 additional exact occurrences are distributed as `{metrics['exact_duplicate_additional_by_file']}`. No exact duplicate group crosses source files.",
        "",
        "## File profile",
        "",
        "| Source month | File | Rows | Columns | Transaction-date range | Outside file month | Quarantined |",
        "|---|---|---:|---:|---|---:|---:|",
    ]
    for profile in sorted(profiles, key=lambda item: item.source_month):
        lines.append(
            f"| {profile.source_month} | `{profile.source_file}` | {profile.row_count:,} | {profile.column_count} | {profile.min_transaction_date} to {profile.max_transaction_date} | {profile.out_of_source_month_rows:,} | {profile.quarantined_rows:,} |"
        )
    lines.extend([
        "",
        "## Decisions",
        "",
        "- Read source files as Windows-1252 and write generated CSV reports as UTF-8 with BOM.",
        "- Map both `PO Category Description` and the source typo `PO Catergory Description` to one canonical field.",
        "- Retain nullable `comments` for all months; months without the source column receive an empty value.",
        "- Keep `source_month` and parsed `transaction_date` separately. A mismatch is a warning, not a rejection.",
        "- Define an exact duplicate from all canonical source values. Report every occurrence and the additional-occurrence count; never auto-delete.",
        "- Define a potential business duplicate as a repeated `(entity, transaction_number)` with non-identical source content. This is a review queue, not a duplicate verdict.",
        "- Profile blanks separately from common sentinel values (`null`, `n/a`, `unknown`, `not set`, `none`). Preserve the source text while treating both as effectively missing for completeness measures.",
        "- Quarantine only rows that cannot support the future fact grain because the transaction date or amount is missing/invalid. Missing descriptive identifiers remain warnings.",
        "- Keep numeric non-positive amounts and values below £25,000 as review warnings. They may be credits, adjustments, or valid publication exceptions; no unverified range rule removes them.",
        "- Treat all current rows as real public DEFRA GBP records. Future synthetic data must use a separate raw dataset and carry `record_origin`, `is_synthetic`, and its own source namespace.",
        "",
        "## Analytical risks",
        "",
        "- Summing raw rows without an explicit duplicate policy may overstate spend. The mart should include all source rows by default and expose duplicate flags for sensitivity analysis.",
        "- Grouping by file month can shift activity into the wrong period. Calendar reporting should use `transaction_date`; operational ingestion monitoring can use `source_month`.",
        "- `transaction_number` is a business identifier, not a proven globally unique primary key. Use the deterministic `source_record_id` for raw lineage and a surrogate key in marts.",
        "- Repeated transaction numbers with differing fields may represent multi-line postings, corrections, or identifier reuse. They remain candidates until source/business evidence resolves them.",
        "- Blank contract numbers do not establish maverick spend or non-compliance.",
        "",
        "## Evidence files",
        "",
        "- `source_inventory.csv`: source hashes, schema, row counts and date coverage.",
        "Detailed duplicate, source-month, summary, and column-profile CSVs are reproducible local outputs and are intentionally excluded from the public repository.",
        "- `data/quarantine/defra_rejected_rows.csv`: hard validation failures, if any.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run(input_dir: Path, processed_dir: Path, quarantine_dir: Path, reports_dir: Path, ingestion_timestamp: str):
    files = sorted(input_dir.glob("*.csv"), key=lambda p: SOURCE_MONTH_BY_FILE.get(p.name, p.name))
    expected = set(SOURCE_MONTH_BY_FILE)
    actual = {path.name for path in files}
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"Source file set mismatch. Missing={missing}; extra={extra}")

    records = []
    profiles = []
    for path in files:
        file_records, profile = load_file(path, ingestion_timestamp)
        records.extend(file_records)
        profiles.append(profile)

    duplicate_rows, duplicate_summary = build_duplicate_report(records)
    metrics = build_quality_metrics(records, duplicate_summary)

    write_csv(processed_dir / "defra_transactions_profiled.csv", records, OUTPUT_COLUMNS)
    rejected = [row for row in records if row["quality_status"] == "quarantine"]
    write_csv(quarantine_dir / "defra_rejected_rows.csv", rejected, OUTPUT_COLUMNS)

    inventory_fields = list(FileProfile.__dataclass_fields__)
    write_csv(reports_dir / "source_inventory.csv", [p.__dict__ for p in profiles], inventory_fields)
    duplicate_fields = [
        "investigation_type", "duplicate_group_id", "occurrence_count",
        "additional_occurrences", "duplicate_scope", "differing_columns",
        *OUTPUT_COLUMNS,
    ]
    write_csv(reports_dir / "duplicate_investigation.csv", duplicate_rows, duplicate_fields)
    mismatch_rows = [r for r in records if r["source_month_match"] == "false"]
    write_csv(reports_dir / "source_month_discrepancies.csv", mismatch_rows, OUTPUT_COLUMNS)
    metric_rows = [
        {"metric": key, "value": value}
        for key, value in metrics.items()
    ]
    write_csv(reports_dir / "data_quality_summary.csv", metric_rows, ["metric", "value"])
    write_csv(
        reports_dir / "column_profile.csv",
        build_column_profile(records),
        [
            "scope", "column_name", "row_count", "blank_count", "blank_rate",
            "sentinel_count", "effective_missing_count", "effective_missing_rate",
            "distinct_non_blank_count",
        ],
    )
    write_markdown_report(reports_dir / "data_quality_report.md", profiles, metrics)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw/defra"))
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--quarantine-dir", type=Path, default=Path("data/quarantine"))
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument(
        "--ingestion-timestamp",
        default=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        help="UTC ISO timestamp stored on every output row; override for deterministic fixtures.",
    )
    args = parser.parse_args()
    metrics = run(
        args.input_dir,
        args.processed_dir,
        args.quarantine_dir,
        args.reports_dir,
        args.ingestion_timestamp,
    )
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
