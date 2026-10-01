"""Generate deterministic Phase 3 synthetic data and historical FX conversions."""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable


MONEY = Decimal("0.01")
RATE_PRECISION = Decimal("0.0000000001")
RECORD_ORIGIN = "synthetic_fictional_company"
FX_SOURCE = "Frankfurter v2 blended reference rate"
CATEGORIES = [
    "Cloud Services",
    "Software",
    "Professional Services",
    "Facilities",
    "Marketing",
    "Travel",
    "Telecommunications",
    "Office Supplies",
    "Training",
    "Logistics",
]
COUNTRIES = ["United Kingdom", "Ireland", "Germany", "France", "Netherlands", "United States"]
DEPARTMENT_NAMES = [
    "Finance", "Technology", "Operations", "Procurement", "Marketing", "People",
    "Legal", "Sales", "Customer Success", "Risk", "Facilities", "Research",
]


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def daterange(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def deterministic_id(*parts: object) -> str:
    payload = "|".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_csv(path: Path, rows: Iterable[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_json(url: str, attempts: int = 3) -> object:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "enterprise-spend-analytics-pipeline/1.0",
            "Accept": "application/json",
        },
    )
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    raise RuntimeError(f"Frankfurter API request failed after {attempts} attempts: {url}") from last_error


def fx_cache_path(cache_dir: Path, base: str, start: date, end: date) -> Path:
    return cache_dir / f"frankfurter_v2_{base}_GBP_{start.isoformat()}_{end.isoformat()}.json"


def load_or_fetch_fx_rates(
    cache_dir: Path,
    api_base: str,
    base: str,
    start: date,
    end: date,
    offline: bool,
) -> list[dict]:
    path = fx_cache_path(cache_dir, base, start, end)
    if path.exists():
        cached = load_json(path)
        rates = cached["rates"]
    else:
        if offline:
            raise FileNotFoundError(f"Offline mode requires FX cache: {path}")
        query = urllib.parse.urlencode(
            {"base": base, "quotes": "GBP", "from": start.isoformat(), "to": end.isoformat()}
        )
        url = f"{api_base.rstrip('/')}/rates?{query}"
        response = fetch_json(url)
        if not isinstance(response, list):
            raise ValueError(f"Unexpected Frankfurter response for {base}: expected a list")
        rates = response
        payload = {
            "api_version": "v2",
            "endpoint": url,
            "rate_semantics": f"1 {base} equals rate GBP",
            "source": FX_SOURCE,
            "retrieved_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "rates": rates,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    cleaned = []
    seen_dates = set()
    for item in rates:
        if item.get("base") != base or item.get("quote") != "GBP":
            raise ValueError(f"Unexpected FX pair in {path}: {item}")
        rate_date = parse_iso_date(item["date"])
        rate = Decimal(str(item["rate"]))
        if rate <= 0 or rate_date in seen_dates:
            raise ValueError(f"Invalid or duplicate FX observation in {path}: {item}")
        seen_dates.add(rate_date)
        cleaned.append({"rate_date": rate_date, "rate": rate, "cache_file": path.name})
    return sorted(cleaned, key=lambda item: item["rate_date"])


class RateLookup:
    def __init__(self, observations: dict[str, list[dict]]):
        self.observations = observations
        self.dates = {
            currency: [item["rate_date"] for item in items]
            for currency, items in observations.items()
        }

    def get(self, currency: str, transaction_date: date) -> tuple[Decimal, date, str, str]:
        if currency == "GBP":
            return Decimal("1"), transaction_date, "GBP identity rate", "GBP_IDENTITY"
        items = self.observations[currency]
        position = bisect.bisect_right(self.dates[currency], transaction_date) - 1
        if position < 0:
            raise ValueError(f"No {currency}/GBP rate on or before {transaction_date}")
        item = items[position]
        return item["rate"], item["rate_date"], FX_SOURCE, item["cache_file"]


def generate_departments(config: dict) -> list[dict]:
    count = config["department_count"]
    if count > len(DEPARTMENT_NAMES):
        raise ValueError("department_count exceeds configured names")
    return [
        {
            "department_id": f"D{index:03d}",
            "department_name": name,
            "cost_centre": f"CC-{1000 + index}",
            "scenario_id": config["scenario_id"],
            "record_origin": RECORD_ORIGIN,
            "is_synthetic": "true",
            "source_record_id": deterministic_id(config["scenario_id"], "department", index),
        }
        for index, name in enumerate(DEPARTMENT_NAMES[:count], start=1)
    ]


def generate_vendors(config: dict, rng: random.Random) -> list[dict]:
    vendors = []
    for index in range(1, config["vendor_count"] + 1):
        category = CATEGORIES[(index - 1) % len(CATEGORIES)]
        country = COUNTRIES[(index - 1) % len(COUNTRIES)]
        default_currency = "USD" if country == "United States" else ("EUR" if country in {"Ireland", "Germany", "France", "Netherlands"} else "GBP")
        vendors.append({
            "vendor_id": f"V{index:04d}",
            "vendor_name": f"Fictional Vendor {index:03d} - {category}",
            "country": country,
            "default_currency": default_currency,
            "primary_category": category,
            "risk_tier": rng.choices(["Low", "Medium", "High"], weights=[65, 28, 7], k=1)[0],
            "scenario_id": config["scenario_id"],
            "record_origin": RECORD_ORIGIN,
            "is_synthetic": "true",
            "source_record_id": deterministic_id(config["scenario_id"], "vendor", index),
        })
    return vendors


def generate_contracts(config: dict, vendors: list[dict], rng: random.Random) -> list[dict]:
    analysis_start = parse_iso_date(config["period_start"])
    contract_vendors = vendors[: max(1, len(vendors) - 20)]
    contracts = []
    for index in range(1, config["contract_count"] + 1):
        vendor = rng.choice(contract_vendors)
        start = analysis_start - timedelta(days=120) + timedelta(days=rng.randint(0, 365))
        end = start + timedelta(days=rng.randint(120, 420))
        value = Decimal(rng.randint(5_000_000, 250_000_000)) / 100
        contracts.append({
            "contract_id": f"C{index:05d}",
            "vendor_id": vendor["vendor_id"],
            "contract_start_date": start.isoformat(),
            "contract_end_date": end.isoformat(),
            "contract_value_gbp": format(value.quantize(MONEY), "f"),
            "approved_category": rng.choice([vendor["primary_category"], rng.choice(CATEGORIES)]),
            "contract_status": "approved",
            "scenario_id": config["scenario_id"],
            "record_origin": RECORD_ORIGIN,
            "is_synthetic": "true",
            "source_record_id": deterministic_id(config["scenario_id"], "contract", index),
        })
    return contracts


def choose_date_within(contract: dict, start: date, end: date, rng: random.Random) -> date:
    lower = max(start, parse_iso_date(contract["contract_start_date"]))
    upper = min(end, parse_iso_date(contract["contract_end_date"]))
    if lower > upper:
        raise ValueError(f"Contract has no overlap with analysis period: {contract['contract_id']}")
    return lower + timedelta(days=rng.randint(0, (upper - lower).days))


def choose_date_outside(contract: dict, start: date, end: date, rng: random.Random) -> date | None:
    contract_start = parse_iso_date(contract["contract_start_date"])
    contract_end = parse_iso_date(contract["contract_end_date"])
    options = []
    if start < contract_start:
        options.extend(daterange(start, min(end, contract_start - timedelta(days=1))))
    if contract_end < end:
        options.extend(daterange(max(start, contract_end + timedelta(days=1)), end))
    return rng.choice(options) if options else None


def evaluate_contract(expense: dict, contracts_by_id: dict[str, dict], contracts_by_vendor: dict[str, list[dict]]) -> tuple[str, str]:
    transaction_date = parse_iso_date(expense["transaction_date"])
    submitted = expense["submitted_contract_id"]
    submitted_failure = ""
    if submitted:
        contract = contracts_by_id.get(submitted)
        if contract is None:
            submitted_failure = "invalid_contract_reference"
        elif contract["vendor_id"] != expense["vendor_id"]:
            submitted_failure = "non_compliant_vendor_mismatch"
        elif contract["approved_category"] != expense["spend_category"]:
            submitted_failure = "non_compliant_category_mismatch"
        elif not (parse_iso_date(contract["contract_start_date"]) <= transaction_date <= parse_iso_date(contract["contract_end_date"])):
            submitted_failure = "non_compliant_outside_validity"
        else:
            return "compliant_submitted_contract", contract["contract_id"]

    matches = [
        contract for contract in contracts_by_vendor.get(expense["vendor_id"], [])
        if contract["approved_category"] == expense["spend_category"]
        and parse_iso_date(contract["contract_start_date"]) <= transaction_date <= parse_iso_date(contract["contract_end_date"])
    ]
    if matches:
        match = sorted(matches, key=lambda item: item["contract_id"])[0]
        status = "compliant_alternate_master_match" if submitted else "compliant_master_match"
        return status, match["contract_id"]
    return (submitted_failure or "no_active_matching_contract"), submitted if submitted in contracts_by_id else ""


def generate_expenses(
    config: dict,
    departments: list[dict],
    vendors: list[dict],
    contracts: list[dict],
    rates: RateLookup,
    rng: random.Random,
) -> tuple[list[dict], list[dict]]:
    start = parse_iso_date(config["period_start"])
    end = parse_iso_date(config["period_end"])
    all_dates = daterange(start, end)
    currency_sequence = [currency for currency, count in config["currency_counts"].items() for _ in range(count)]
    if len(currency_sequence) != config["expense_count"]:
        raise ValueError("currency_counts must sum to expense_count")
    rng.shuffle(currency_sequence)

    overlapping = [
        contract for contract in contracts
        if max(start, parse_iso_date(contract["contract_start_date"])) <= min(end, parse_iso_date(contract["contract_end_date"]))
    ]
    outside_candidates = [contract for contract in contracts if choose_date_outside(contract, start, end, rng) is not None]
    no_contract_vendors = vendors[-20:]
    contracts_by_id = {contract["contract_id"]: contract for contract in contracts}
    contracts_by_vendor = defaultdict(list)
    for contract in contracts:
        contracts_by_vendor[contract["vendor_id"]].append(contract)

    modes = (["compliant"] * 3500 + ["category_mismatch"] * 500 + ["outside_validity"] * 500 + ["no_contract"] * 500)
    rng.shuffle(modes)
    raw_rows = []
    processed_rows = []
    for index, (currency, mode) in enumerate(zip(currency_sequence, modes, strict=True), start=1):
        submitted_contract_id = ""
        if mode == "compliant":
            contract = rng.choice(overlapping)
            vendor_id = contract["vendor_id"]
            category = contract["approved_category"]
            transaction_date = choose_date_within(contract, start, end, rng)
            if rng.random() >= 0.15:
                submitted_contract_id = contract["contract_id"]
        elif mode == "category_mismatch":
            contract = rng.choice(overlapping)
            vendor_id = contract["vendor_id"]
            category = rng.choice([item for item in CATEGORIES if item != contract["approved_category"]])
            transaction_date = choose_date_within(contract, start, end, rng)
            submitted_contract_id = contract["contract_id"]
        elif mode == "outside_validity":
            contract = rng.choice(outside_candidates)
            vendor_id = contract["vendor_id"]
            category = contract["approved_category"]
            transaction_date = choose_date_outside(contract, start, end, rng)
            if transaction_date is None:
                raise AssertionError("Outside-validity candidate unexpectedly has no date")
            submitted_contract_id = contract["contract_id"]
        else:
            vendor_id = rng.choice(no_contract_vendors)["vendor_id"]
            category = rng.choice(CATEGORIES)
            transaction_date = rng.choice(all_dates)

        original_amount = (Decimal(rng.randint(10_000, 50_000_000)) / 100).quantize(MONEY)
        expense_id = f"E{index:06d}"
        raw = {
            "expense_id": expense_id,
            "transaction_date": transaction_date.isoformat(),
            "department_id": rng.choice(departments)["department_id"],
            "vendor_id": vendor_id,
            "spend_category": category,
            "description": f"Synthetic {category.lower()} expense {index:06d}",
            "submitted_contract_id": submitted_contract_id,
            "original_amount": format(original_amount, "f"),
            "original_currency": currency,
            "payment_method": rng.choice(["Invoice", "Corporate Card", "Bank Transfer"]),
            "scenario_id": config["scenario_id"],
            "generation_seed": config["random_seed"],
            "record_origin": RECORD_ORIGIN,
            "is_synthetic": "true",
            "source_record_id": deterministic_id(config["scenario_id"], "expense", expense_id),
        }
        status, matched_contract_id = evaluate_contract(raw, contracts_by_id, contracts_by_vendor)
        fx_rate, fx_date, fx_source, fx_cache = rates.get(currency, transaction_date)
        amount_gbp = (original_amount * fx_rate).quantize(MONEY, rounding=ROUND_HALF_UP)
        processed = {
            **raw,
            "matched_contract_id": matched_contract_id,
            "contract_compliance_status": status,
            "is_contract_compliant": str(status.startswith("compliant_")).lower(),
            "fx_rate_to_gbp": format(fx_rate.quantize(RATE_PRECISION), "f"),
            "fx_rate_date": fx_date.isoformat(),
            "amount_gbp": format(amount_gbp, "f"),
            "fx_source": fx_source,
            "fx_cache_file": fx_cache,
        }
        raw_rows.append(raw)
        processed_rows.append(processed)
    return raw_rows, processed_rows


def generate_approval_events(config: dict, expenses: list[dict], rng: random.Random) -> tuple[list[dict], list[dict]]:
    events = []
    cycles = []
    sla_hours = Decimal(str(config["approval_sla_hours"]))
    for expense in expenses:
        transaction_date = parse_iso_date(expense["transaction_date"])
        payment = datetime.combine(transaction_date, datetime_time(hour=rng.randint(10, 18)), tzinfo=timezone.utc)
        finance = payment - timedelta(hours=rng.randint(6, 96))
        manager = finance - timedelta(hours=rng.randint(1, 96))
        request = manager - timedelta(hours=rng.randint(1, 24))
        timeline = [
            ("purchase_request", request, "employee"),
            ("manager_approval", manager, "manager"),
            ("finance_approval", finance, "finance"),
            ("payment", payment, "accounts_payable"),
        ]
        for sequence, (event_type, timestamp, actor_role) in enumerate(timeline, start=1):
            event_id = f"AE-{expense['expense_id']}-{sequence}"
            events.append({
                "event_id": event_id,
                "expense_id": expense["expense_id"],
                "event_sequence": sequence,
                "event_type": event_type,
                "event_timestamp_utc": timestamp.isoformat(),
                "actor_role": actor_role,
                "scenario_id": config["scenario_id"],
                "record_origin": RECORD_ORIGIN,
                "is_synthetic": True,
                "source_record_id": deterministic_id(config["scenario_id"], "approval_event", event_id),
            })
        approval_hours = Decimal(str((finance - request).total_seconds() / 3600)).quantize(Decimal("0.01"))
        payment_hours = Decimal(str((payment - request).total_seconds() / 3600)).quantize(Decimal("0.01"))
        cycles.append({
            "expense_id": expense["expense_id"],
            "request_timestamp_utc": request.isoformat(),
            "manager_approval_timestamp_utc": manager.isoformat(),
            "finance_approval_timestamp_utc": finance.isoformat(),
            "payment_timestamp_utc": payment.isoformat(),
            "approval_cycle_hours": format(approval_hours, "f"),
            "request_to_payment_hours": format(payment_hours, "f"),
            "approval_sla_hours": format(sla_hours, "f"),
            "approval_sla_breached": str(approval_hours > sla_hours).lower(),
            "scenario_id": config["scenario_id"],
            "record_origin": RECORD_ORIGIN,
            "is_synthetic": "true",
            "source_record_id": deterministic_id(config["scenario_id"], "approval_cycle", expense["expense_id"]),
        })
    return events, cycles


def generate_surveys(config: dict, vendors: list[dict], rng: random.Random) -> list[dict]:
    dates = daterange(parse_iso_date(config["period_start"]), parse_iso_date(config["period_end"]))
    rows = []
    for index in range(1, config["survey_response_count"] + 1):
        vendor = rng.choice(vendors)
        response_id = f"S{index:05d}"
        rows.append({
            "response_id": response_id,
            "vendor_id": vendor["vendor_id"],
            "response_date": rng.choice(dates).isoformat(),
            "overall_rating": rng.choices([1, 2, 3, 4, 5], weights=[4, 10, 24, 40, 22], k=1)[0],
            "delivery_rating": rng.randint(1, 5),
            "quality_rating": rng.randint(1, 5),
            "support_rating": rng.randint(1, 5),
            "response_channel": rng.choice(["Email", "Portal", "Quarterly Review"]),
            "scenario_id": config["scenario_id"],
            "record_origin": RECORD_ORIGIN,
            "is_synthetic": "true",
            "source_record_id": deterministic_id(config["scenario_id"], "survey", response_id),
        })
    return rows


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(config_path: Path, project_root: Path, offline: bool = False) -> dict:
    config = load_json(config_path)
    rng = random.Random(config["random_seed"])
    raw_dir = project_root / "data" / "raw" / "synthetic"
    fx_dir = project_root / "data" / "raw" / "fx_rates"
    processed_dir = project_root / "data" / "processed"
    reports_dir = project_root / "reports"
    quarantine_dir = project_root / "data" / "quarantine"

    start = parse_iso_date(config["period_start"])
    end = parse_iso_date(config["period_end"])
    fx_start = start - timedelta(days=config["fx_lookback_days"])
    observations = {
        currency: load_or_fetch_fx_rates(fx_dir, config["frankfurter_api_base"], currency, fx_start, end, offline)
        for currency in ("EUR", "USD")
    }
    rate_lookup = RateLookup(observations)
    departments = generate_departments(config)
    vendors = generate_vendors(config, rng)
    contracts = generate_contracts(config, vendors, rng)
    expenses, converted = generate_expenses(config, departments, vendors, contracts, rate_lookup, rng)
    approval_events, approval_cycles = generate_approval_events(config, expenses, rng)
    surveys = generate_surveys(config, vendors, rng)

    datasets = {
        raw_dir / "departments.csv": (departments, list(departments[0])),
        raw_dir / "vendors.csv": (vendors, list(vendors[0])),
        raw_dir / "contracts.csv": (contracts, list(contracts[0])),
        raw_dir / "expenses.csv": (expenses, list(expenses[0])),
        raw_dir / "vendor_satisfaction.csv": (surveys, list(surveys[0])),
        processed_dir / "synthetic_expenses_gbp.csv": (converted, list(converted[0])),
        processed_dir / "synthetic_approval_cycles.csv": (approval_cycles, list(approval_cycles[0])),
    }
    for path, (rows, fields) in datasets.items():
        write_csv(path, rows, fields)
    approval_path = raw_dir / "approval_events.jsonl"
    write_jsonl(approval_path, approval_events)

    for name, fields in {
        "synthetic_expenses_rejected.csv": list(expenses[0]),
        "synthetic_contracts_rejected.csv": list(contracts[0]),
        "synthetic_approval_events_rejected.csv": list(approval_events[0]),
        "synthetic_vendor_satisfaction_rejected.csv": list(surveys[0]),
    }.items():
        write_csv(quarantine_dir / name, [], fields)

    output_files = [*datasets, approval_path, *[fx_cache_path(fx_dir, c, fx_start, end) for c in ("EUR", "USD")]]
    manifest = {
        "scenario_id": config["scenario_id"],
        "generation_version": config["generation_version"],
        "random_seed": config["random_seed"],
        "period_start": config["period_start"],
        "period_end": config["period_end"],
        "record_origin": RECORD_ORIGIN,
        "is_synthetic": True,
        "dataset_counts": {
            "departments": len(departments),
            "vendors": len(vendors),
            "contracts": len(contracts),
            "expenses": len(expenses),
            "approval_events": len(approval_events),
            "approval_cycles": len(approval_cycles),
            "vendor_satisfaction_responses": len(surveys),
            "quarantined_records": 0,
        },
        "currency_counts": dict(sorted(Counter(row["original_currency"] for row in expenses).items())),
        "contract_status_counts": dict(sorted(Counter(row["contract_compliance_status"] for row in converted).items())),
        "approval_sla_breach_count": sum(row["approval_sla_breached"] == "true" for row in approval_cycles),
        "files": {
            path.relative_to(project_root).as_posix(): {"sha256": file_sha256(path), "bytes": path.stat().st_size}
            for path in sorted(output_files)
        },
    }
    manifest["generation_run_id"] = deterministic_id(
        config["scenario_id"], config["generation_version"], config["random_seed"],
        *[manifest["files"][name]["sha256"] for name in sorted(manifest["files"])],
    )
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "generation_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/phase3_synthetic.json"))
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--offline", action="store_true", help="Require existing FX caches; do not call the API.")
    args = parser.parse_args()
    manifest = generate(args.config, args.project_root.resolve(), args.offline)
    print(json.dumps(manifest["dataset_counts"], indent=2))


if __name__ == "__main__":
    main()
