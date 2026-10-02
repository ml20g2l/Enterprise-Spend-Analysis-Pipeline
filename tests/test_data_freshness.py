from datetime import date, datetime, timedelta, timezone
import unittest

from src.monitoring.data_freshness import evaluate_rules


class DataFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 2, 7, 0, tzinfo=timezone.utc)
        self.policy = {
            "max_load_age_hours": 24,
            "max_future_clock_skew_minutes": 5,
            "fx_period_end_lag_days": 3,
            "expected_month_count": 12,
        }
        self.manifest = {"period_start": "2025-03-01", "period_end": "2026-02-28"}
        self.evidence = {
            "last_load_at_utc": self.now - timedelta(minutes=10),
            "source_min_date": date(2025, 3, 1),
            "source_max_date": date(2026, 2, 28),
            "source_month_count": 12,
            "fx_min_date": date(2025, 2, 19),
            "fx_max_date": date(2026, 2, 27),
            "mart_min_month": date(2025, 3, 1),
            "mart_max_month": date(2026, 2, 1),
            "mart_month_count": 12,
        }

    def test_complete_current_pipeline_passes_all_rules(self):
        results = evaluate_rules(self.evidence, self.policy, self.manifest, self.now)
        self.assertEqual(len(results), 6)
        self.assertTrue(all(result["status"] == "PASS" for result in results))

    def test_stale_load_fails_operational_rule_only(self):
        self.evidence["last_load_at_utc"] = self.now - timedelta(hours=25)
        results = evaluate_rules(self.evidence, self.policy, self.manifest, self.now)
        failed = [result["rule_id"] for result in results if result["status"] == "FAIL"]
        self.assertEqual(failed, ["operational_load_recency"])

    def test_missing_final_month_fails_source_and_mart_controls(self):
        self.evidence["source_max_date"] = date(2026, 1, 31)
        self.evidence["source_month_count"] = 11
        self.evidence["mart_max_month"] = date(2026, 1, 1)
        self.evidence["mart_month_count"] = 11
        results = evaluate_rules(self.evidence, self.policy, self.manifest, self.now)
        failed = {result["rule_id"] for result in results if result["status"] == "FAIL"}
        self.assertEqual(failed, {
            "source_period_boundary",
            "source_month_partitions",
            "mart_period_boundary",
            "mart_month_partitions",
        })


if __name__ == "__main__":
    unittest.main()
