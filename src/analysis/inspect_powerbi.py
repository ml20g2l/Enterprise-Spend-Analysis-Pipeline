"""Inspect the Power BI report package without exposing credentials.

Power BI Desktop files are ZIP packages.  The legacy report layout is JSON
encoded as UTF-16LE, which is enough to verify pages, canvas sizes, visual
types, field bindings, and obvious presentation defects.  This does not
replace a rendered visual review in Power BI Desktop.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import zipfile


EXPECTED_PAGES = [
    "Executive Spend Overview",
    "Contract & Vendor Performance",
    "Approval & Operational Performance",
]


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


def _json_or_empty(value: str | None) -> dict:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def _binding_signature(strings: set[str]) -> str | None:
    candidates = sorted(
        value
        for value in strings
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9 _]*\.[A-Za-z_][A-Za-z0-9 _%]*", value)
    )
    return "|".join(candidates) if candidates else None


def inspect_pbix(path: Path) -> dict:
    path = path.resolve()
    checks: list[dict] = []
    warnings: list[dict] = []

    def check(name: str, passed: bool, actual, expected) -> None:
        checks.append(
            {
                "check": name,
                "status": "PASS" if passed else "FAIL",
                "actual": actual,
                "expected": expected,
            }
        )

    check("pbix_exists", path.exists(), path.exists(), True)
    if not path.exists():
        return {"file": str(path), "checks": checks, "warnings": warnings, "status": "FAIL"}

    check("valid_zip_package", zipfile.is_zipfile(path), zipfile.is_zipfile(path), True)
    if not zipfile.is_zipfile(path):
        return {"file": str(path), "checks": checks, "warnings": warnings, "status": "FAIL"}

    with zipfile.ZipFile(path) as package:
        names = set(package.namelist())
        check("layout_present", "Report/Layout" in names, "Report/Layout" in names, True)
        check("data_model_present", "DataModel" in names, "DataModel" in names, True)
        layout = json.loads(package.read("Report/Layout").decode("utf-16-le"))

    pages = []
    for section in layout.get("sections", []):
        page_name = section.get("displayName", section.get("name", "unnamed"))
        type_counts: Counter[str] = Counter()
        bindings: list[dict] = []
        page_text: set[str] = set()
        for container in section.get("visualContainers", []):
            config = _json_or_empty(container.get("config"))
            query = _json_or_empty(container.get("query"))
            transforms = _json_or_empty(container.get("dataTransforms"))
            visual_type = config.get("singleVisual", {}).get("visualType") or "group_or_unknown"
            type_counts[visual_type] += 1
            strings = set(_strings([config, query, transforms]))
            page_text.update(strings)
            signature = _binding_signature(strings)
            if signature:
                binding = {
                    "visual_type": visual_type,
                    "binding": signature,
                    "x": container.get("x"),
                    "y": container.get("y"),
                    "width": container.get("width"),
                    "height": container.get("height"),
                    "parent_group": config.get("parentGroupName"),
                }
                bindings.append(binding)
        for value in sorted(page_text):
            if "COMPLANCE" in value.upper():
                warnings.append(
                    {
                        "code": "label_typo",
                        "page": page_name,
                        "detail": value,
                        "suggested": value.upper().replace("COMPLANCE", "COMPLIANCE"),
                    }
                )

        pages.append(
            {
                "name": page_name,
                "width": section.get("width"),
                "height": section.get("height"),
                "visual_count": len(section.get("visualContainers", [])),
                "visual_types": dict(sorted(type_counts.items())),
                "bindings": bindings,
            }
        )

    page_names = [page["name"] for page in pages]
    check("expected_pages", page_names == EXPECTED_PAGES, page_names, EXPECTED_PAGES)
    check(
        "page_canvas_1280x720",
        all(page["width"] == 1280 and page["height"] == 720 for page in pages),
        [{"name": page["name"], "width": page["width"], "height": page["height"]} for page in pages],
        "all pages 1280x720",
    )
    check("three_pages", len(pages) == 3, len(pages), 3)

    failed = sum(item["status"] == "FAIL" for item in checks)
    status = "FAIL" if failed else ("NEEDS_VISUAL_REVIEW" if warnings else "STRUCTURE_PASS")
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "file": str(path),
        "file_size_bytes": path.stat().st_size,
        "status": status,
        "checks_passed": sum(item["status"] == "PASS" for item in checks),
        "checks_failed": failed,
        "checks": checks,
        "warnings": warnings,
        "pages": pages,
        "scope_note": "Package-level checks only; rendered visual QA is required before publication.",
    }


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pbix",
        type=Path,
        default=project_root / "powerbi" / "Enterprise_Spend_Analysis_Pipeline.pbix",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "reports" / "powerbi_structure_qa.json",
    )
    args = parser.parse_args()
    report = inspect_pbix(args.pbix)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("status", "checks_passed", "checks_failed", "warnings")}, indent=2))
    if report["checks_failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
