"""Reproduce decision-oriented aggregates from the real DEFRA source files."""

from __future__ import annotations

import csv
import json
import tempfile
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from src.profiling.profile_defra import run as profile_defra


def analyse(project_root: Path) -> dict:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        profile_defra(
            project_root / "data" / "raw" / "defra",
            temp / "processed",
            temp / "quarantine",
            temp / "reports",
            "2026-09-23T00:00:00+00:00",
        )
        with (temp / "processed" / "defra_transactions_profiled.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))

    monthly: dict[str, dict[str, Decimal | int]] = defaultdict(
        lambda: {"rows": 0, "amount_gbp": Decimal("0")}
    )
    supplier_spend: dict[str, Decimal] = defaultdict(Decimal)
    entity_spend: dict[str, Decimal] = defaultdict(Decimal)
    exact_seen: set[str] = set()
    deduplicated_total = Decimal("0")
    negative_count = 0
    negative_total = Decimal("0")
    blank_contract_count = 0
    blank_transaction_number_count = 0

    for row in rows:
        amount = Decimal(row["amount_gbp"])
        month = row["transaction_date"][:7]
        monthly[month]["rows"] += 1
        monthly[month]["amount_gbp"] += amount
        supplier_spend[row["supplier"].strip() or "[blank supplier]"] += amount
        entity_spend[row["entity"].strip() or "[blank entity]"] += amount
        if row["exact_record_hash"] not in exact_seen:
            exact_seen.add(row["exact_record_hash"])
            deduplicated_total += amount
        if amount < 0:
            negative_count += 1
            negative_total += amount
        if not row["contract_number"].strip():
            blank_contract_count += 1
        if not row["transaction_number"].strip():
            blank_transaction_number_count += 1

    total = sum((Decimal(row["amount_gbp"]) for row in rows), Decimal("0"))
    top_suppliers = sorted(supplier_spend.items(), key=lambda item: item[1], reverse=True)
    top_entities = sorted(entity_spend.items(), key=lambda item: item[1], reverse=True)

    def ranked(items: list[tuple[str, Decimal]], limit: int) -> list[dict]:
        return [
            {
                "name": name,
                "amount_gbp": str(amount.quantize(Decimal("0.01"))),
                "share_pct": str((amount / total * 100).quantize(Decimal("0.01"))),
            }
            for name, amount in items[:limit]
        ]

    monthly_rows = [
        {
            "month": month,
            "rows": values["rows"],
            "amount_gbp": str(values["amount_gbp"].quantize(Decimal("0.01"))),
        }
        for month, values in sorted(monthly.items())
    ]
    top_five_total = sum((amount for _, amount in top_suppliers[:5]), Decimal("0"))
    top_ten_total = sum((amount for _, amount in top_suppliers[:10]), Decimal("0"))

    return {
        "scope": {
            "rows": len(rows),
            "transaction_date_start": min(row["transaction_date"] for row in rows),
            "transaction_date_end": max(row["transaction_date"] for row in rows),
            "published_row_total_gbp": str(total.quantize(Decimal("0.01"))),
        },
        "monthly": monthly_rows,
        "top_suppliers": ranked(top_suppliers, 10),
        "top_entities": ranked(top_entities, 5),
        "supplier_concentration": {
            "supplier_count": len(supplier_spend),
            "top_5_share_pct": str((top_five_total / total * 100).quantize(Decimal("0.01"))),
            "top_10_share_pct": str((top_ten_total / total * 100).quantize(Decimal("0.01"))),
        },
        "quality_context": {
            "exact_duplicate_additional_occurrences": len(rows) - len(exact_seen),
            "published_total_less_exact_repeats_gbp": str(
                deduplicated_total.quantize(Decimal("0.01"))
            ),
            "exact_repeat_total_effect_gbp": str(
                (total - deduplicated_total).quantize(Decimal("0.01"))
            ),
            "negative_row_count": negative_count,
            "negative_row_total_gbp": str(negative_total.quantize(Decimal("0.01"))),
            "blank_contract_number_count": blank_contract_count,
            "blank_transaction_number_count": blank_transaction_number_count,
            "source_month_discrepancy_count": sum(
                row["source_month_match"] == "false" for row in rows
            ),
            "quality_status_counts": dict(Counter(row["quality_status"] for row in rows)),
        },
    }


def main() -> None:
    print(json.dumps(analyse(Path(".").resolve()), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
