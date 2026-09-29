import json
import unittest
from decimal import Decimal
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = PROJECT_ROOT / "reports" / "phase6_analysis_snapshot.json"


class Phase6SnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        cls.metrics = cls.payload["metrics"]

    def test_only_expected_synthetic_marts_are_profiled(self):
        self.assertEqual(
            set(self.payload["source"]["marts"]),
            {
                "mart_department_spend",
                "mart_vendor_performance",
                "mart_contract_compliance",
                "mart_approval_performance",
                "mart_monthly_currency_spend",
            },
        )
        self.assertEqual(
            self.payload["source"]["record_origin"],
            "synthetic_fictional_company",
        )
        self.assertTrue(self.payload["source"]["is_synthetic"])
        self.assertEqual(self.payload["validation"]["status"], "PASS")
        self.assertTrue(all(self.payload["validation"]["checks"].values()))

    def test_headline_spend_reconciles(self):
        overall = self.metrics["overall_spend"]
        self.assertEqual(int(overall["expense_count"]), 5000)
        self.assertEqual(Decimal(overall["amount_gbp"]), Decimal("1160936638.63"))
        self.assertEqual(Decimal(overall["avg_expense_gbp"]), Decimal("232187.33"))

    def test_currency_and_month_totals_reconcile(self):
        expected = Decimal(self.metrics["overall_spend"]["amount_gbp"])
        currency_total = sum(Decimal(row["amount_gbp"]) for row in self.metrics["currency"])
        month_total = sum(Decimal(row["amount_gbp"]) for row in self.metrics["monthly_spend"])
        currency_count = sum(int(row["expense_count"]) for row in self.metrics["currency"])
        month_count = sum(int(row["expense_count"]) for row in self.metrics["monthly_spend"])
        self.assertEqual(currency_total, expected)
        self.assertEqual(month_total, expected)
        self.assertEqual(currency_count, 5000)
        self.assertEqual(month_count, 5000)

    def test_contract_reconciliation(self):
        overall = self.metrics["contract_overall"]
        statuses = self.metrics["contract_status"]
        self.assertEqual(int(overall["expense_count"]), 5000)
        self.assertEqual(int(overall["compliant_expense_count"]), 3660)
        self.assertEqual(Decimal(overall["compliance_pct"]), Decimal("73.20"))
        self.assertEqual(Decimal(overall["non_compliant_amount_gbp"]), Decimal("305916170.54"))
        self.assertEqual(
            sum(Decimal(row["amount_gbp"]) for row in statuses),
            Decimal(overall["amount_gbp"]),
        )

    def test_approval_reconciliation(self):
        overall = self.metrics["approval_overall"]
        self.assertEqual(int(overall["approval_request_count"]), 5000)
        self.assertEqual(int(overall["sla_breach_count"]), 1919)
        self.assertEqual(Decimal(overall["sla_breach_pct"]), Decimal("38.38"))
        self.assertEqual(Decimal(overall["avg_approval_cycle_hours"]), Decimal("60.99"))
        self.assertEqual(Decimal(overall["avg_request_to_payment_hours"]), Decimal("111.09"))


if __name__ == "__main__":
    unittest.main()
