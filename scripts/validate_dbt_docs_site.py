"""Validate the minimal static dbt documentation artifact before publication."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


EXPECTED_MODELS = {
    "stg_synthetic_departments",
    "stg_synthetic_vendors",
    "stg_synthetic_contracts",
    "stg_synthetic_expenses",
    "stg_fx_rates",
    "stg_synthetic_approval_events",
    "stg_vendor_satisfaction",
    "int_expense_contract_match",
    "int_expense_fx",
    "int_synthetic_spend",
    "int_approval_cycles",
    "int_vendor_satisfaction",
    "mart_department_spend",
    "mart_vendor_performance",
    "mart_contract_compliance",
    "mart_approval_performance",
    "mart_monthly_currency_spend",
}

EXPECTED_MARTS = {name for name in EXPECTED_MODELS if name.startswith("mart_")}
REQUIRED_FILES = {"index.html", "manifest.json", "catalog.json"}
FORBIDDEN_MARKERS = {
    "MYSQL_PASSWORD",
    "DBT_MYSQL_PASSWORD",
}


def validate(site_dir: Path) -> list[str]:
    errors: list[str] = []
    present = {path.name for path in site_dir.iterdir()} if site_dir.is_dir() else set()
    missing_files = REQUIRED_FILES - present
    if missing_files:
        errors.append(f"Missing site files: {sorted(missing_files)}")
        return errors

    for filename in REQUIRED_FILES:
        if (site_dir / filename).stat().st_size == 0:
            errors.append(f"Empty site file: {filename}")

    manifest_path = site_dir / "manifest.json"
    catalog_path = site_dir / "catalog.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

    models = {
        node["name"]: node
        for node in manifest.get("nodes", {}).values()
        if node.get("resource_type") == "model"
    }
    missing_models = EXPECTED_MODELS - set(models)
    unexpected_models = set(models) - EXPECTED_MODELS
    if missing_models:
        errors.append(f"Missing dbt models: {sorted(missing_models)}")
    if unexpected_models:
        errors.append(f"Unexpected dbt models: {sorted(unexpected_models)}")
    for model_name in sorted(EXPECTED_MODELS & set(models)):
        if not str(models[model_name].get("description", "")).strip():
            errors.append(f"Model has no description: {model_name}")

    catalog_nodes = catalog.get("nodes", {})
    for mart_name in sorted(EXPECTED_MARTS):
        manifest_node = models.get(mart_name)
        if not manifest_node:
            continue
        catalog_node = catalog_nodes.get(manifest_node["unique_id"])
        if not catalog_node:
            errors.append(f"Mart missing from catalog: {mart_name}")
            continue
        documented = {
            name.lower(): str(details.get("description", "")).strip()
            for name, details in manifest_node.get("columns", {}).items()
        }
        physical_columns = {
            str(details["name"]).lower()
            for details in catalog_node.get("columns", {}).values()
        }
        undocumented = sorted(
            column for column in physical_columns if not documented.get(column)
        )
        if undocumented:
            errors.append(f"Undocumented mart columns for {mart_name}: {undocumented}")

    combined = "\n".join(
        (site_dir / filename).read_text(encoding="utf-8", errors="ignore")
        for filename in REQUIRED_FILES
    )
    for marker in sorted(FORBIDDEN_MARKERS):
        if marker in combined:
            errors.append(f"Forbidden credential marker found in site: {marker}")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-dir", type=Path, required=True)
    args = parser.parse_args()
    errors = validate(args.site_dir.resolve())
    result = {
        "status": "FAIL" if errors else "PASS",
        "site_dir": str(args.site_dir.resolve()),
        "expected_models": len(EXPECTED_MODELS),
        "expected_marts": len(EXPECTED_MARTS),
        "errors": errors,
    }
    print(json.dumps(result, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
