"""Lab 3 checks for cumulative temperature excursions."""

import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "excursion_check.py"


class ExcursionCheckTests(unittest.TestCase):
    def load_checker(self):
        """Load inside each test so a missing implementation fails each test."""
        self.assertTrue(
            MODULE_PATH.is_file(),
            f"Missing implementation: {MODULE_PATH}. Create tools/excursion_check.py.",
        )
        spec = importlib.util.spec_from_file_location("excursion_check", MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_01_all_readings_in_range(self):
        checker = self.load_checker()
        limits = {"min_c": -2, "max_c": 4, "max_minutes_out_of_range": 30}
        result = checker.assess([-2, 0, 3], limits)
        self.assertEqual(result, {
            "min_temp_c": -2,
            "max_temp_c": 3,
            "minutes_out_of_range": 0,
            "excursion": False,
        })

    def test_02_reading_at_max_is_in_range(self):
        checker = self.load_checker()
        limits = {"min_c": -2, "max_c": 4, "max_minutes_out_of_range": 0}
        result = checker.assess([4], limits)
        self.assertEqual(result["minutes_out_of_range"], 0)
        self.assertIs(result["excursion"], False)

    def test_03_frozen_has_no_lower_bound(self):
        checker = self.load_checker()
        limits = {"min_c": None, "max_c": -18, "max_minutes_out_of_range": 30}
        result = checker.assess([-100, -20], limits)
        self.assertEqual(result["minutes_out_of_range"], 0)
        self.assertIs(result["excursion"], False)

    def test_04_separate_runs_are_summed(self):
        checker = self.load_checker()
        limits = {"min_c": -2, "max_c": 4, "max_minutes_out_of_range": 45}
        result = checker.assess([5, 6, 0, -3, -4], limits)
        self.assertEqual(result["minutes_out_of_range"], 60)
        self.assertIs(result["excursion"], True)

    def test_05_one_interval_over_allowance_is_excursion(self):
        checker = self.load_checker()
        limits = {"min_c": -2, "max_c": 4, "max_minutes_out_of_range": 30}
        result = checker.assess([5, 5, 5], limits)
        self.assertEqual(result["minutes_out_of_range"], 45)
        self.assertIs(result["excursion"], True)

    def test_06_exact_allowance_is_not_excursion(self):
        checker = self.load_checker()
        limits = {"min_c": -2, "max_c": 4, "max_minutes_out_of_range": 30}
        result = checker.assess([5, 5], limits)
        self.assertEqual(result["minutes_out_of_range"], 30)
        self.assertIs(result["excursion"], False)

    def test_07_passed_limits_change_result(self):
        checker = self.load_checker()
        limits = {"min_c": 0, "max_c": 4, "max_minutes_out_of_range": 15}
        temps = [5, 5]
        strict = checker.assess(temps, limits)
        wider = checker.assess(temps, dict(limits, max_c=6))
        longer = checker.assess(temps, dict(limits, max_minutes_out_of_range=30))
        self.assertEqual(strict["minutes_out_of_range"], 30)
        self.assertIs(strict["excursion"], True)
        self.assertEqual(wider["minutes_out_of_range"], 0)
        self.assertIs(wider["excursion"], False)
        self.assertEqual(longer["minutes_out_of_range"], 30)
        self.assertIs(longer["excursion"], False)

    def test_08_borderline_shipment_cli(self):
        self.load_checker()
        with (ROOT / "data/reference/shipments.csv").open(newline="", encoding="utf-8") as source:
            matches = [row for row in csv.DictReader(source) if row["shipment_id"] == "SHP-0197"]
        self.assertEqual(len(matches), 1)
        category = matches[0]["product_category"]
        with (ROOT / "data/sop/thresholds.json").open(encoding="utf-8") as source:
            thresholds = json.load(source)
        allowance = thresholds["categories"][category]["max_minutes_out_of_range"]

        completed = subprocess.run(
            [sys.executable, "tools/excursion_check.py", "SHP-0197"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, "")
        result = json.loads(completed.stdout)
        self.assertEqual(result["shipment_id"], "SHP-0197")
        self.assertEqual(result["product_category"], category)
        self.assertEqual(result["minutes_out_of_range"], allowance)
        self.assertIs(result["excursion"], False)


if __name__ == "__main__":
    unittest.main()
