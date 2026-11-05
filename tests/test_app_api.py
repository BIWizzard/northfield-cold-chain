"""Checks for the local shipment API and HTTP server."""

from collections import Counter
from contextlib import redirect_stderr
import csv
from http.client import HTTPConnection
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[1]
# Import the app the way `python app/serve.py` does, with app/ on the import path.
sys.path.insert(0, str(ROOT / "app"))

import api  # noqa: E402
import serve  # noqa: E402


def read_shipments(root):
    with (root / "data/reference/shipments.csv").open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        return reader.fieldnames, list(reader)


def read_rows(root, path):
    with (root / path).open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


class AppApiTests(unittest.TestCase):
    def setUp(self):
        self.columns, self.rows = read_shipments(ROOT)
        self.thresholds = json.loads((ROOT / "data/sop/thresholds.json").read_text(encoding="utf-8"))
        self.carriers = read_rows(ROOT, "data/reference/carriers.csv")
        self.lanes = read_rows(ROOT, "data/reference/lanes.csv")

    def lookup(self, records, key, value):
        return next(record for record in records if record[key] == value)

    def test_weeks(self):
        status, payload = api.handle("/api/weeks", {}, ROOT)
        expected = sorted({row["week"] for row in self.rows})
        self.assertEqual(len(expected), 13)
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"source": "data/reference/shipments.csv", "weeks": expected})

    def test_shipments_preserve_rows_and_columns(self):
        duplicate_id = next(key for key, count in Counter(row["shipment_id"] for row in self.rows).items()
                            if count > 1)
        week = next(row["week"] for row in self.rows if row["shipment_id"] == duplicate_id)
        expected = [row for row in self.rows if row["week"] == week]
        status, payload = api.handle("/api/shipments", {"week": [week]}, ROOT)
        self.assertEqual(status, 200)
        self.assertEqual(payload, {
            "source": "data/reference/shipments.csv", "week": week, "shipments": expected,
        })
        for row in payload["shipments"]:
            self.assertEqual(list(row), self.columns)
            self.assertTrue(all(isinstance(value, str) for value in row.values()))

    def test_missing_or_unknown_week(self):
        for query, expected in (({}, 400), ({"week": ["not-a-week"]}, 404)):
            with self.subTest(query=query):
                status, payload = api.handle("/api/shipments", query, ROOT)
                self.assertEqual(status, expected)
                self.assertEqual(set(payload), {"error"})
                self.assertIsInstance(payload["error"], str)

    def test_detail_readings_and_limits(self):
        for category in self.thresholds["categories"]:
            row = next(row for row in self.rows if row["product_category"] == category
                       and (ROOT / row["logger_file"]).is_file())
            with self.subTest(category=category):
                status, payload = api.handle("/api/shipments/" + row["shipment_id"], {}, ROOT)
                expected_matches = []
                for match in self.rows:
                    if match["shipment_id"] != row["shipment_id"]:
                        continue
                    path = ROOT / match["logger_file"]
                    readings = []
                    if path.is_file():
                        with path.open(newline="", encoding="utf-8") as source:
                            readings = [{"timestamp": entry["timestamp"], "temp_c": float(entry["temp_c"])}
                                        for entry in csv.DictReader(source)]
                    expected_matches.append({
                        "row": match,
                        "carrier": self.lookup(self.carriers, "carrier_id", match["carrier_id"]),
                        "lane": self.lookup(self.lanes, "lane_id", match["lane_id"]),
                        "limits": self.thresholds["categories"][match["product_category"]],
                        "logger": {"path": match["logger_file"], "found": path.is_file(), "readings": readings},
                    })
                self.assertEqual(status, 200)
                self.assertEqual(payload, {
                    "shipment_id": row["shipment_id"],
                    "source": "data/reference/shipments.csv",
                    "thresholds_source": "data/sop/thresholds.json",
                    "units": self.thresholds["units"],
                    "reading_interval_minutes": self.thresholds["reading_interval_minutes"],
                    "matches": expected_matches,
                })
                readings = payload["matches"][0]["logger"]["readings"]
                self.assertTrue(readings)
                self.assertTrue(all(isinstance(entry["temp_c"], float) for entry in readings))
                if category == "frozen":
                    self.assertIsNone(payload["matches"][0]["limits"]["min_c"])

    def test_duplicate_id_returns_two_matches(self):
        counts = Counter(row["shipment_id"] for row in self.rows)
        duplicates = [key for key, count in counts.items() if count == 2]
        self.assertTrue(duplicates, "Expected a duplicated shipment ID in the reference CSV")
        shipment_id = duplicates[0]
        status, payload = api.handle("/api/shipments/" + shipment_id, {}, ROOT)
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["matches"]), 2)
        self.assertEqual([match["row"] for match in payload["matches"]],
                         [row for row in self.rows if row["shipment_id"] == shipment_id])

    def test_missing_logger(self):
        missing = [row for row in self.rows if not (ROOT / row["logger_file"]).exists()]
        self.assertTrue(missing, "Expected a missing logger in the reference CSV")
        row = missing[0]
        status, payload = api.handle("/api/shipments/" + row["shipment_id"], {}, ROOT)
        self.assertEqual(status, 200)
        match = next(match for match in payload["matches"] if match["row"] == row)
        self.assertEqual(match["logger"], {"path": row["logger_file"], "found": False, "readings": []})

    def test_detail_names_carrier_and_lane(self):
        row = self.rows[0]
        status, payload = api.handle("/api/shipments/" + row["shipment_id"], {}, ROOT)
        self.assertEqual(status, 200)
        match = payload["matches"][0]
        self.assertEqual(match["carrier"], self.lookup(self.carriers, "carrier_id", row["carrier_id"]))
        self.assertEqual(list(match["carrier"]), ["carrier_id", "name"])
        self.assertEqual(match["lane"], self.lookup(self.lanes, "lane_id", row["lane_id"]))
        self.assertEqual(list(match["lane"]), ["lane_id", "origin", "destination", "transit_hours"])

    def test_overview(self):
        status, payload = api.handle("/api/overview", {}, ROOT)
        weeks = sorted({row["week"] for row in self.rows})
        week_ranges = []
        for week in weeks:
            dates = sorted(row["ship_date"] for row in self.rows if row["week"] == week)
            week_ranges.append({
                "week": week, "first_ship_date": dates[0], "last_ship_date": dates[-1], "rows": len(dates),
            })
        dates = sorted(row["ship_date"] for row in self.rows)
        self.assertEqual(status, 200)
        self.assertEqual(payload, {
            "source": "data/reference/shipments.csv",
            "carriers_source": "data/reference/carriers.csv",
            "lanes_source": "data/reference/lanes.csv",
            "thresholds_source": "data/sop/thresholds.json",
            "loggers_source": "data/raw/loggers/",
            "weeks": week_ranges,
            "latest_week": week_ranges[-1],
            "first_ship_date": dates[0],
            "last_ship_date": dates[-1],
            "shipment_rows": len(self.rows),
            "carriers": len(self.carriers),
            "lanes": len(self.lanes),
            "plants": len({lane["origin"] for lane in self.lanes}),
            "distribution_centers": len({lane["destination"] for lane in self.lanes}),
            "categories": list(self.thresholds["categories"]),
            "reading_interval_minutes": self.thresholds["reading_interval_minutes"],
        })
        self.assertEqual(sum(entry["rows"] for entry in payload["weeks"]), len(self.rows))

    def test_reference(self):
        status, payload = api.handle("/api/reference", {}, ROOT)
        self.assertEqual(status, 200)
        self.assertEqual(payload, {
            "carriers_source": "data/reference/carriers.csv",
            "lanes_source": "data/reference/lanes.csv",
            "thresholds_source": "data/sop/thresholds.json",
            "carriers": self.carriers,
            "lanes": self.lanes,
            "categories": self.thresholds["categories"],
        })
        for row in payload["carriers"] + payload["lanes"]:
            self.assertTrue(all(isinstance(value, str) for value in row.values()))

    def test_unknown_paths_and_exact_id_matching(self):
        shipment_id = self.rows[0]["shipment_id"]
        paths = ["/api/shipments/not-a-shipment", "/api/unknown", "/api/weeks/extra",
                 "/api/overview/extra", "/api/reference/extra",
                 "/api/shipments/", "/api/shipments/" + shipment_id + "/extra",
                 "/api/shipments/" + shipment_id.lower(), "/api/shipments/" + shipment_id + " "]
        for path in paths:
            with self.subTest(path=path):
                status, payload = api.handle(path, {}, ROOT)
                self.assertEqual(status, 404)
                self.assertEqual(set(payload), {"error"})


class FixtureApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        for directory in ("data/reference", "data/raw", "data/sop"):
            (self.root / directory).mkdir(parents=True)
        for name in ("carriers.csv", "lanes.csv"):
            shutil.copy(ROOT / "data/reference" / name, self.root / "data/reference" / name)
        self.columns, rows = read_shipments(ROOT)
        self.row = dict(rows[0], shipment_id="fixture-id", week="week-01",
                        product_category="fresh", logger_file="data/raw/logger.csv")
        self.thresholds = json.loads((ROOT / "data/sop/thresholds.json").read_text(encoding="utf-8"))
        self.write_shipments()
        self.write_thresholds()
        self.logger_path = self.root / self.row["logger_file"]
        self.logger_path.write_text("timestamp,temp_c\n2026-01-01T00:00:00Z,3.4\n", encoding="utf-8")

    def write_shipments(self):
        with (self.root / "data/reference/shipments.csv").open("w", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=self.columns)
            writer.writeheader()
            writer.writerow(self.row)

    def write_thresholds(self):
        (self.root / "data/sop/thresholds.json").write_text(json.dumps(self.thresholds), encoding="utf-8")

    def detail(self):
        return api.handle("/api/shipments/" + self.row["shipment_id"], {}, self.root)

    def write_outside_logger(self):
        outside = self.root.parent / "outside.csv"
        outside.write_text(self.logger_path.read_text(encoding="utf-8"), encoding="utf-8")
        return outside

    def assert_logger_not_read(self, path):
        self.row["logger_file"] = path
        self.write_shipments()
        status, payload = self.detail()
        self.assertEqual(status, 200)
        self.assertEqual(payload["matches"][0]["logger"], {
            "path": path, "found": False, "readings": [],
        })

    def test_logger_path_traversal(self):
        outside = self.write_outside_logger()
        for path in ("../outside.csv", "data/reference/shipments.csv", str(outside)):
            with self.subTest(path=path):
                self.assert_logger_not_read(path)

    def test_logger_symlink_traversal(self):
        outside = self.write_outside_logger()
        try:
            (self.root / "data/raw/link.csv").symlink_to(outside)
        except OSError as error:
            # Windows needs admin rights or Developer Mode to create symlinks.
            self.skipTest(f"Cannot create a symlink here: {error}")
        self.assert_logger_not_read("data/raw/link.csv")

    def test_rereads_shipments(self):
        status, before = api.handle("/api/weeks", {}, self.root)
        self.assertEqual(status, 200)
        self.assertEqual(before["weeks"], ["week-01"])
        self.row["week"] = "week-99"
        self.write_shipments()
        status, after = api.handle("/api/weeks", {}, self.root)
        self.assertEqual(status, 200)
        self.assertEqual(after["weeks"], ["week-99"])

    def test_rereads_thresholds_and_logger(self):
        status, before = self.detail()
        self.assertEqual(status, 200)
        self.thresholds["categories"]["fresh"]["max_c"] = 7
        self.write_thresholds()
        self.logger_path.write_text("timestamp,temp_c\n2026-01-01T00:00:00Z,6\n", encoding="utf-8")
        status, after = self.detail()
        self.assertEqual(status, 200)
        self.assertNotEqual(before, after)
        self.assertEqual(after["matches"][0]["limits"]["max_c"], 7)
        self.assertEqual(after["matches"][0]["logger"]["readings"][0]["temp_c"], 6.0)

    def test_rereads_overview_and_reference(self):
        status, before = api.handle("/api/overview", {}, self.root)
        self.assertEqual(status, 200)
        self.assertEqual([entry["week"] for entry in before["weeks"]], ["week-01"])
        self.assertEqual(before["latest_week"], {
            "week": "week-01", "first_ship_date": self.row["ship_date"],
            "last_ship_date": self.row["ship_date"], "rows": 1,
        })
        self.row["week"] = "week-99"
        self.write_shipments()
        self.thresholds["categories"]["fresh"]["max_c"] = 7
        self.write_thresholds()
        (self.root / "data/reference/carriers.csv").write_text(
            "carrier_id,name\nCAR-99,Fixture Freight\n", encoding="utf-8")
        status, after = api.handle("/api/overview", {}, self.root)
        self.assertEqual(status, 200)
        self.assertEqual(after["latest_week"]["week"], "week-99")
        self.assertEqual(after["carriers"], 1)
        status, payload = api.handle("/api/reference", {}, self.root)
        self.assertEqual(status, 200)
        self.assertEqual(payload["carriers"], [{"carrier_id": "CAR-99", "name": "Fixture Freight"}])
        self.assertEqual(payload["categories"]["fresh"]["max_c"], 7)

    def test_overview_with_no_shipments(self):
        (self.root / "data/reference/shipments.csv").write_text(",".join(self.columns) + "\n", encoding="utf-8")
        status, payload = api.handle("/api/overview", {}, self.root)
        self.assertEqual(status, 200)
        self.assertEqual(payload["weeks"], [])
        self.assertIsNone(payload["latest_week"])
        self.assertIsNone(payload["first_ship_date"])
        self.assertEqual(payload["shipment_rows"], 0)

    def test_unknown_carrier_and_lane_have_null_records(self):
        self.row["carrier_id"] = "CAR-99"
        self.row["lane_id"] = "LN-99"
        self.write_shipments()
        status, payload = self.detail()
        self.assertEqual(status, 200)
        self.assertIsNone(payload["matches"][0]["carrier"])
        self.assertIsNone(payload["matches"][0]["lane"])

    def test_unknown_category_has_null_limits(self):
        self.row["product_category"] = "unknown"
        self.write_shipments()
        status, payload = self.detail()
        self.assertEqual(status, 200)
        self.assertIsNone(payload["matches"][0]["limits"])

    def test_blank_logger_lines_are_skipped(self):
        self.logger_path.write_text("timestamp,temp_c\n\n   \nfirst,3\n\nsecond,4\n", encoding="utf-8")
        status, payload = self.detail()
        self.assertEqual(status, 200)
        self.assertEqual(payload["matches"][0]["logger"]["readings"], [
            {"timestamp": "first", "temp_c": 3.0}, {"timestamp": "second", "temp_c": 4.0},
        ])

    def test_empty_logger_has_no_readings(self):
        for content in ("", "timestamp,temp_c\n"):
            with self.subTest(content=content):
                self.logger_path.write_text(content, encoding="utf-8")
                status, payload = self.detail()
                self.assertEqual(status, 200)
                self.assertEqual(payload["matches"][0]["logger"], {
                    "path": self.row["logger_file"], "found": True, "readings": [],
                })

    def test_invalid_logger_rows_return_error(self):
        for row in ("first,not-a-number", "first", ",", "first,3,extra", "first,NaN"):
            with self.subTest(row=row):
                self.logger_path.write_text("timestamp,temp_c\n" + row + "\n", encoding="utf-8")
                terminal = io.StringIO()
                with redirect_stderr(terminal):
                    status, payload = self.detail()
                self.assertEqual(status, 500)
                self.assertEqual(set(payload), {"error"})
                self.assertIn("Traceback", terminal.getvalue())


class HttpSmokeTests(unittest.TestCase):
    def setUp(self):
        self.server = serve.make_server(0, ROOT)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, method, path):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, path)
            response = connection.getresponse()
            body = response.read()
            self.assertEqual(response.getheader("Cache-Control"), "no-store")
            self.assertNotIn(b"Traceback", body)
            return response.status, response.getheader("Content-Type"), body
        finally:
            connection.close()

    def test_http_smoke(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        status, content_type, body = self.request("GET", "/api/weeks?ignored=yes")
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "application/json")
        self.assertEqual(json.loads(body), api.handle("/api/weeks", {}, ROOT)[1])

        status, content_type, body = self.request("GET", "/?refresh=1")
        self.assertIn(status, (200, 404))
        if (ROOT / "app/web/index.html").is_file():
            self.assertEqual(status, 200)
            self.assertEqual(content_type, "text/html")
            self.assertEqual(body, (ROOT / "app/web/index.html").read_bytes())
        else:
            self.assertEqual(status, 404)

        for path in ("/../README.md", "/%2e%2e/README.md", "/%2e%2e%2fREADME.md"):
            with self.subTest(path=path):
                self.assertEqual(self.request("GET", path)[0], 404)

        for method in ("POST", "PUT", "DELETE", "PATCH", "OPTIONS", "TRACE", "CUSTOM"):
            with self.subTest(method=method):
                status, content_type, body = self.request(method, "/api/weeks")
                self.assertEqual(status, 405)
                self.assertEqual(content_type, "application/json")
                self.assertEqual(set(json.loads(body)), {"error"})

        for path in ("/api/overview", "/api/reference"):
            with self.subTest(path=path):
                status, content_type, body = self.request("GET", path)
                self.assertEqual(status, 200)
                self.assertEqual(content_type, "application/json")
                self.assertEqual(json.loads(body), api.handle(path, {}, ROOT)[1])

        status, content_type, body = self.request("HEAD", "/api/weeks")
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "application/json")
        self.assertEqual(body, b"")


if __name__ == "__main__":
    unittest.main()
