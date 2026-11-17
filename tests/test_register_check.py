"""Checks for the Lab 15 month-end register checker."""

import contextlib
import csv
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECK_PATH = ROOT / "evals" / "register_check.py"
SHIPMENTS = ROOT / "data" / "reference" / "shipments.csv"
COLUMNS = ["shipment_id", "ship_date", "carrier_id", "disposition"]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = load("register_check", CHECK_PATH)


def october_rows():
    """The register a perfect run produces: every October 2026 row of shipments.csv."""
    with SHIPMENTS.open(encoding="utf-8", newline="") as source:
        return [
            {"shipment_id": row["shipment_id"], "ship_date": row["ship_date"],
             "carrier_id": row["carrier_id"], "disposition": "release"}
            for row in csv.DictReader(source)
            if row["ship_date"].startswith("2026-10")
        ]


def shipment(shipment_id):
    with SHIPMENTS.open(encoding="utf-8", newline="") as source:
        return [row for row in csv.DictReader(source) if row["shipment_id"] == shipment_id]


class RegisterCheckTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def write(self, rows, columns=COLUMNS, encoding="utf-8", name="register.csv"):
        path = Path(self.directory.name) / name
        with path.open("w", encoding=encoding, newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        return path

    def run_check(self, path):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = check.main([str(path)])
        return code, out.getvalue()

    def test_01_the_october_register_has_69_rows(self):
        self.assertEqual(len(october_rows()), 69)

    def test_02_a_complete_register_passes(self):
        code, text = self.run_check(self.write(october_rows()))
        self.assertEqual(code, 0, text)
        self.assertIn("69", text)

    def test_03_a_missing_row_fails_and_is_named(self):
        rows = october_rows()
        dropped = rows.pop(10)
        code, text = self.run_check(self.write(rows))
        self.assertEqual(code, 1)
        self.assertIn("Missing", text)
        self.assertIn(dropped["shipment_id"], text)

    def test_04_a_duplicated_row_fails_and_is_named(self):
        rows = october_rows()
        rows.append(dict(rows[5]))
        code, text = self.run_check(self.write(rows))
        self.assertEqual(code, 1)
        self.assertIn("Duplicate", text)
        self.assertIn(rows[5]["shipment_id"], text)

    def test_05_an_extra_row_fails_as_unexpected(self):
        rows = october_rows() + [{"shipment_id": "SHP-9999", "ship_date": "2026-10-15",
                                  "carrier_id": "CAR-01", "disposition": "release"}]
        code, text = self.run_check(self.write(rows))
        self.assertEqual(code, 1)
        self.assertIn("Unexpected", text)
        self.assertIn("SHP-9999", text)

    def test_06_a_september_week_09_row_fails_as_unexpected(self):
        (september,) = shipment("SHP-0125")
        self.assertEqual(september["week"], "week-09")
        rows = october_rows() + [{**september, "disposition": "release"}]
        code, text = self.run_check(self.write(rows))
        self.assertEqual(code, 1)
        self.assertIn("Unexpected", text)
        self.assertIn("SHP-0125", text)

    def test_07_only_one_of_shp_0191s_two_rows_fails(self):
        both = shipment("SHP-0191")
        self.assertEqual(len(both), 2)
        rows = [r for r in october_rows()
                if not (r["shipment_id"] == "SHP-0191" and r["carrier_id"] == both[1]["carrier_id"])]
        self.assertEqual(len(rows), 68)
        code, text = self.run_check(self.write(rows))
        self.assertEqual(code, 1)
        self.assertIn("Missing", text)
        self.assertIn(both[1]["carrier_id"], text)

    def test_08_shp_0191_listed_twice_with_the_same_carrier_is_a_duplicate_and_a_miss(self):
        both = shipment("SHP-0191")
        rows = [r for r in october_rows()
                if not (r["shipment_id"] == "SHP-0191" and r["carrier_id"] == both[1]["carrier_id"])]
        rows.append({"shipment_id": "SHP-0191", "ship_date": both[0]["ship_date"],
                     "carrier_id": both[0]["carrier_id"], "disposition": "release"})
        code, text = self.run_check(self.write(rows))
        self.assertEqual(code, 1)
        self.assertIn("Duplicate", text)
        self.assertIn("Missing", text)

    def test_09_dispositions_are_not_judged(self):
        rows = [{**row, "disposition": ""} for row in october_rows()]
        code, text = self.run_check(self.write(rows))
        self.assertEqual(code, 0, text)

    def test_10_a_byte_order_mark_and_stray_spaces_are_tolerated(self):
        rows = [{**row, "shipment_id": f" {row['shipment_id']} "} for row in october_rows()]
        code, text = self.run_check(self.write(rows, encoding="utf-8-sig"))
        self.assertEqual(code, 0, text)

    def test_11_a_register_without_the_key_columns_is_a_usage_error(self):
        path = self.write(october_rows(), columns=["shipment_id", "disposition"])
        code, text = self.run_check(path)
        self.assertEqual(code, 2)
        self.assertIn("carrier_id", text)

    def test_12_a_missing_register_file_is_a_usage_error(self):
        code, text = self.run_check(Path(self.directory.name) / "nope.csv")
        self.assertEqual(code, 2)
        self.assertIn("nope.csv", text)

    def test_13_runs_from_the_command_line(self):
        path = self.write(october_rows())
        done = subprocess.run([sys.executable, str(CHECK_PATH), str(path)],
                              capture_output=True, text=True, timeout=20)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
