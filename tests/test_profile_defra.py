from __future__ import annotations

import csv
import hashlib
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from src.profiling.profile_defra import (
    SOURCE_MONTH_BY_FILE,
    canonical_header,
    parse_amount,
    parse_date,
    run,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ParsingTests(unittest.TestCase):
    def test_header_typo_maps_to_same_column(self):
        self.assertEqual(canonical_header("PO Catergory Description "), "po_category_description")
        self.assertEqual(canonical_header("PO Category Description "), "po_category_description")

    def test_supported_dates(self):
        self.assertEqual(parse_date("02/02/2026")[0].isoformat(), "2026-02-02")
        self.assertEqual(parse_date("17-Feb-26")[0].isoformat(), "2026-02-17")
        self.assertEqual(parse_date("not-a-date"), (None, "invalid"))

    def test_amount_parser(self):
        self.assertEqual(parse_amount("£1,234.50"), (Decimal("1234.50"), "valid"))
        self.assertEqual(parse_amount("(£25,000.00)"), (Decimal("-25000.00"), "valid"))
        self.assertEqual(parse_amount(""), (None, "missing"))


class FullDatasetTests(unittest.TestCase):
    def test_raw_copies_match_root_files(self):
        for filename in SOURCE_MONTH_BY_FILE:
            root = PROJECT_ROOT / filename
            copied = PROJECT_ROOT / "data" / "raw" / "defra" / filename
            self.assertTrue(root.exists(), filename)
            self.assertTrue(copied.exists(), filename)
            self.assertEqual(hashlib.sha256(root.read_bytes()).digest(), hashlib.sha256(copied.read_bytes()).digest())

    def test_expected_profile_results(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            metrics = run(
                PROJECT_ROOT / "data" / "raw" / "defra",
                temp / "processed",
                temp / "quarantine",
                temp / "reports",
                "2026-09-23T00:00:00+00:00",
            )
            self.assertEqual(metrics["source_file_count"], 12)
            self.assertEqual(metrics["raw_row_count"], 13_830)
            self.assertEqual(metrics["source_month_discrepancy_rows"], 72)
            self.assertEqual(metrics["exact_duplicate_additional_occurrences"], 134)
            self.assertEqual(metrics["exact_cross_file_groups"], 0)
            self.assertEqual(metrics["in_analysis_period_row_count"], 13_830)
            self.assertEqual(metrics["quarantined_rows"], 0)

            with (temp / "processed" / "defra_transactions_profiled.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 13_830)
            self.assertEqual(len({row["source_record_id"] for row in rows}), 13_830)


if __name__ == "__main__":
    unittest.main()

