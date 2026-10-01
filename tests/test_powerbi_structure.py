from __future__ import annotations

import unittest
from pathlib import Path

from src.analysis.inspect_powerbi import EXPECTED_PAGES, inspect_pbix


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PowerBIStructureTests(unittest.TestCase):
    def test_pbix_has_expected_pages_and_model(self):
        report = inspect_pbix(PROJECT_ROOT / "powerbi" / "Enterprise_Spend_Analysis_Pipeline.pbix")
        self.assertEqual(report["checks_failed"], 0)
        self.assertEqual([page["name"] for page in report["pages"]], EXPECTED_PAGES)
        self.assertTrue(all(page["width"] == 1280 and page["height"] == 720 for page in report["pages"]))

    def test_each_page_contains_cards_and_analytical_visuals(self):
        report = inspect_pbix(PROJECT_ROOT / "powerbi" / "Enterprise_Spend_Analysis_Pipeline.pbix")
        for page in report["pages"]:
            self.assertGreaterEqual(page["visual_types"].get("cardVisual", 0), 4, page["name"])
            analytical = sum(
                count
                for visual_type, count in page["visual_types"].items()
                if visual_type in {
                    "lineChart", "donutChart", "clusteredBarChart", "scatterChart",
                    "tableEx", "pivotTable", "lineClusteredColumnComboChart",
                }
            )
            self.assertGreaterEqual(analytical, 3, page["name"])


if __name__ == "__main__":
    unittest.main()
