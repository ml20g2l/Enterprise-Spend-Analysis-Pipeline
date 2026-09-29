from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src.ingestion.load_mysql import build_upsert_sql
from src.synthetic.generate_phase3 import generate
from src.validation.validate_phase3 import classify_quarantine, validate


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Phase3ValidationTests(unittest.TestCase):
    def test_all_reconciliation_checks_pass(self):
        results, summary = validate(PROJECT_ROOT, write_reports=False)
        self.assertEqual(summary["checks_failed"], 0)
        self.assertTrue(all(row["status"] == "PASS" for row in results))
        self.assertEqual(summary["currency_counts"], {"EUR": 1250, "GBP": 3000, "USD": 750})
        self.assertEqual(summary["expense_count"], 5000)
        self.assertEqual(summary["approval_event_count"], 20000)
        with (PROJECT_ROOT / "data" / "processed" / "synthetic_expenses_gbp.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            import csv
            rows = list(csv.DictReader(handle))
        gbp_rows = [row for row in rows if row["original_currency"] == "GBP"]
        self.assertTrue(gbp_rows)
        self.assertTrue(all(row["fx_cache_file"] == "GBP_IDENTITY" for row in gbp_rows))

    def test_offline_generation_is_reproducible(self):
        manifest = json.loads((PROJECT_ROOT / "reports" / "phase3_generation_manifest.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            target_fx = temp_root / "data" / "raw" / "fx_rates"
            target_fx.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(PROJECT_ROOT / "data" / "raw" / "fx_rates", target_fx)
            regenerated = generate(
                PROJECT_ROOT / "config" / "phase3_synthetic.json",
                temp_root,
                offline=True,
            )
            for relative_path, metadata in manifest["files"].items():
                if relative_path.startswith("data/raw/fx_rates/"):
                    continue
                regenerated_path = temp_root / relative_path
                digest = hashlib.sha256(regenerated_path.read_bytes()).hexdigest()
                self.assertEqual(digest, metadata["sha256"], relative_path)
            self.assertEqual(regenerated["generation_run_id"], manifest["generation_run_id"])

    def test_mysql_statement_is_upsert(self):
        sql = build_upsert_sql(
            "raw_synthetic_vendor",
            ["source_record_id", "vendor_id", "vendor_name"],
            {"source_record_id"},
        )
        self.assertIn("ON DUPLICATE KEY UPDATE", sql)
        self.assertNotIn("`source_record_id` = VALUES(`source_record_id`)", sql)
        self.assertIn("`vendor_name` = VALUES(`vendor_name`)", sql)

    def test_invalid_expense_is_classified_for_quarantine(self):
        departments = [{"department_id": "D001"}]
        vendors = [{"vendor_id": "V0001"}]
        contracts = [{
            "contract_id": "C00001", "vendor_id": "V0001",
            "contract_start_date": "2025-01-01", "contract_end_date": "2025-12-31",
            "contract_value_gbp": "1000.00",
        }]
        expense = {
            "expense_id": "E1", "transaction_date": "not-a-date", "department_id": "D999",
            "vendor_id": "V0001", "spend_category": "Software", "original_amount": "-1.00",
            "original_currency": "CAD", "submitted_contract_id": "", "source_record_id": "x",
        }
        quarantined = classify_quarantine(departments, vendors, contracts, [expense], [], [])
        self.assertEqual(len(quarantined["synthetic_expenses_rejected.csv"]), 1)
        reasons = quarantined["synthetic_expenses_rejected.csv"][0]["rejection_reasons"]
        self.assertIn("transaction_date_invalid", reasons)
        self.assertIn("department_fk_invalid", reasons)
        self.assertIn("currency_invalid", reasons)
        self.assertIn("original_amount_not_positive", reasons)


if __name__ == "__main__":
    unittest.main()
