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

    def test_08_cli_at_exact_allowance(self):
        """The CLI reports a shipment sitting exactly at its allowance as no excursion."""
        checker = self.load_checker()
        thresholds = checker.load_thresholds(str(ROOT / "data/sop/thresholds.json"))
        with (ROOT / "data/reference/shipments.csv").open(newline="", encoding="utf-8") as source:
            rows = list(csv.DictReader(source))
        id_counts = {}
        for row in rows:
            id_counts[row["shipment_id"]] = id_counts.get(row["shipment_id"], 0) + 1

        # Find a shipment whose time out of range equals its allowance, using
        # your own functions, then check the command line agrees.
        target = None
        for row in rows:
            logger = ROOT / row["logger_file"]
            if id_counts[row["shipment_id"]] != 1 or not logger.is_file():
                continue
            limits = thresholds["categories"][row["product_category"]]
            assessed = checker.assess(checker.load_readings(str(logger)), limits)
            if assessed["minutes_out_of_range"] == limits["max_minutes_out_of_range"]:
                target = (row, limits["max_minutes_out_of_range"])
                break
        self.assertIsNotNone(target, "No shipment sits exactly at its allowance; check assess().")
        row, allowance = target

        completed = subprocess.run(
            [sys.executable, "tools/excursion_check.py", row["shipment_id"]],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, "")
        result = json.loads(completed.stdout)
        self.assertEqual(result["shipment_id"], row["shipment_id"])
        self.assertEqual(result["product_category"], row["product_category"])
        self.assertEqual(result["minutes_out_of_range"], allowance)
        self.assertIs(result["excursion"], False)


if __name__ == "__main__":
    unittest.main()
