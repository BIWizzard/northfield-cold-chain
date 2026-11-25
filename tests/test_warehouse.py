"""Test the warehouse MCP server over a subprocess, and the database behind it."""

import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "warehouse" / "server.py"
REFERENCE = ROOT / "data" / "reference"
TOOLS = {
    "get_shipment", "list_shipments", "get_readings",
    "list_carriers", "list_lanes", "run_sql",
}


def csv_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class Client:
    """Talks newline-delimited JSON-RPC to one server process."""

    def __init__(self, env=None):
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVER)], cwd=ROOT,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", env=dict(os.environ, **(env or {})),
        )
        self.next_id = 0

    def send(self, method, params=None, notify=False):
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        if not notify:
            self.next_id += 1
            message["id"] = self.next_id
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()
        if notify:
            return None
        return json.loads(self.proc.stdout.readline())

    def call(self, name, arguments=None):
        """Call a tool; returns (is_error, parsed JSON text content)."""
        reply = self.send("tools/call", {"name": name, "arguments": arguments or {}})
        result = reply["result"]
        text = result["content"][0]["text"]
        return result.get("isError", False), text

    def call_raw(self, name, arguments):
        """Call a tool with `arguments` sent exactly as given; returns the result."""
        return self.send("tools/call", {"name": name, "arguments": arguments})["result"]

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=10)
        self.proc.stdout.close()
        self.proc.stderr.close()


class WarehouseServerTests(unittest.TestCase):
    def setUp(self):
        self.client = Client()
        self.addCleanup(self.client.close)
        self.reply = self.client.send(
            "initialize",
            {"protocolVersion": "2025-06-18", "capabilities": {},
             "clientInfo": {"name": "test", "version": "0"}},
        )
        self.client.send("notifications/initialized", notify=True)

    def rows(self, name, arguments=None):
        is_error, text = self.client.call(name, arguments)
        self.assertFalse(is_error, text)
        return json.loads(text)

    def test_initialize_echoes_version_and_declares_tools(self):
        result = self.reply["result"]
        self.assertEqual(result["protocolVersion"], "2025-06-18")
        self.assertIn("tools", result["capabilities"])

    def test_tools_list_names_six_tools(self):
        reply = self.client.send("tools/list")
        tools = reply["result"]["tools"]
        self.assertEqual({tool["name"] for tool in tools}, TOOLS)
        for tool in tools:
            self.assertEqual(tool["inputSchema"]["type"], "object")

    def test_unknown_method_is_method_not_found(self):
        reply = self.client.send("resources/list")
        self.assertEqual(reply["error"]["code"], -32601)

    def test_get_shipment_returns_rows_with_names(self):
        rows = self.rows("get_shipment", {"shipment_id": "SHP-0001"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["shipment_id"], "SHP-0001")
        self.assertEqual(rows[0]["carrier_name"], "Kestrel Ridge Logistics")
        self.assertIn("route", rows[0])

    def test_get_shipment_returns_every_duplicate_row(self):
        counts = {}
        for row in csv_rows(REFERENCE / "shipments.csv"):
            counts[row["shipment_id"]] = counts.get(row["shipment_id"], 0) + 1
        duplicate = next(key for key, count in counts.items() if count > 1)
        rows = self.rows("get_shipment", {"shipment_id": duplicate})
        self.assertEqual(len(rows), counts[duplicate])

    def test_get_shipment_includes_its_carrier_notes(self):
        note = csv_rows(REFERENCE / "carrier_notes.csv")[0]
        rows = self.rows("get_shipment", {"shipment_id": note["shipment_id"]})
        self.assertIn(note["note"], [n["note"] for n in rows[0]["carrier_notes"]])

    def test_get_shipment_without_notes_has_an_empty_list(self):
        with_notes = {r["shipment_id"] for r in csv_rows(REFERENCE / "carrier_notes.csv")}
        shipment_id = next(
            r["shipment_id"] for r in csv_rows(REFERENCE / "shipments.csv")
            if r["shipment_id"] not in with_notes)
        rows = self.rows("get_shipment", {"shipment_id": shipment_id})
        self.assertEqual(rows[0]["carrier_notes"], [])

    def test_get_shipment_unknown_id_returns_no_rows(self):
        self.assertEqual(self.rows("get_shipment", {"shipment_id": "SHP-9999"}), [])

    def test_list_shipments_filters_and_limits(self):
        rows = self.rows("list_shipments", {"carrier_id": "CAR-03", "limit": 5})
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(row["carrier_id"] == "CAR-03" for row in rows))

    def test_list_shipments_default_limit_is_50_and_max_is_200(self):
        self.assertEqual(len(self.rows("list_shipments")), 50)
        self.assertEqual(len(self.rows("list_shipments", {"limit": 500})), 200)

    def test_list_shipments_by_week(self):
        rows = self.rows("list_shipments", {"week": "week-01"})
        self.assertEqual(len(rows), 16)

    def test_list_shipments_by_date_range(self):
        rows = self.rows(
            "list_shipments", {"date_from": "2026-08-03", "date_to": "2026-08-03"})
        self.assertTrue(rows)
        self.assertTrue(all(row["ship_date"] == "2026-08-03" for row in rows))

    def test_get_readings_returns_the_loggers_rows(self):
        rows = self.rows("get_readings", {"shipment_id": "SHP-0001"})
        logger = ROOT / "data" / "raw" / "loggers" / "week-01" / "SHP-0001.csv"
        expected = csv_rows(logger)
        self.assertEqual(len(rows), len(expected))
        self.assertEqual(rows[0]["timestamp"], expected[0]["timestamp"])
        self.assertEqual(float(rows[0]["temp_c"]), float(expected[0]["temp_c"]))

    def test_list_carriers_and_lanes_match_the_csvs(self):
        self.assertEqual(
            len(self.rows("list_carriers")), len(csv_rows(REFERENCE / "carriers.csv")))
        self.assertEqual(
            len(self.rows("list_lanes")), len(csv_rows(REFERENCE / "lanes.csv")))

    def test_run_sql_returns_rows(self):
        rows = self.rows("run_sql", {"query": "SELECT carrier_id FROM carriers"})
        self.assertEqual(len(rows), len(csv_rows(REFERENCE / "carriers.csv")))

    def test_run_sql_caps_at_200_rows(self):
        rows = self.rows("run_sql", {"query": "SELECT * FROM raw_readings"})
        self.assertEqual(len(rows), 200)

    def test_run_sql_cannot_write(self):
        before = self.rows("run_sql", {"query": "SELECT COUNT(*) AS n FROM shipments"})
        is_error, text = self.client.call(
            "run_sql", {"query": "DELETE FROM shipments WHERE 1=1"})
        self.assertIn("readonly", text.lower().replace(" ", ""))
        after = self.rows("run_sql", {"query": "SELECT COUNT(*) AS n FROM shipments"})
        self.assertEqual(before, after)

    def assert_no_file_written(self, template):
        """run_sql must not create a file, even though the connection is read-only."""
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "out.db"
            is_error, text = self.client.call(
                "run_sql", {"query": template.format(path=target.as_posix())})
            self.assertTrue(is_error, text)
            self.assertFalse(target.exists(), f"{target} was created by: {template}")

    def test_run_sql_cannot_copy_the_database_with_vacuum_into(self):
        self.assert_no_file_written("VACUUM INTO '{path}'")

    def test_run_sql_cannot_create_a_file_with_attach(self):
        self.assert_no_file_written("ATTACH DATABASE '{path}' AS other")

    def test_run_sql_still_runs_select_and_with(self):
        self.assertEqual(
            self.rows("run_sql", {"query": "SELECT COUNT(*) AS n FROM carriers"})[0]["n"], 6)
        rows = self.rows("run_sql", {
            "query": "WITH c AS (SELECT carrier_id FROM carriers) SELECT COUNT(*) AS n FROM c"})
        self.assertEqual(rows[0]["n"], 6)

    def test_run_sql_says_when_it_cut_the_rows(self):
        result = self.client.call_raw("run_sql", {"query": "SELECT * FROM raw_readings"})
        self.assertEqual(len(json.loads(result["content"][0]["text"])), 200)
        self.assertEqual(len(result["content"]), 2)
        self.assertIn("first 200 rows", result["content"][1]["text"])

    def test_run_sql_says_nothing_when_all_rows_fit(self):
        for query in ("SELECT * FROM carriers",
                      "SELECT * FROM raw_readings LIMIT 200"):
            with self.subTest(query=query):
                result = self.client.call_raw("run_sql", {"query": query})
                self.assertEqual(len(result["content"]), 1)

    def test_run_sql_reports_sqlite_errors_as_text(self):
        is_error, text = self.client.call("run_sql", {"query": "SELEC nonsense"})
        self.assertTrue(is_error)
        self.assertIn("syntax error", text)


class RobustnessTests(unittest.TestCase):
    def start(self, env=None):
        client = Client(env)
        self.addCleanup(client.close)
        client.send("initialize", {"protocolVersion": "2025-06-18"})
        client.send("notifications/initialized", notify=True)
        return client

    def test_a_runaway_query_is_stopped_and_the_server_keeps_answering(self):
        client = self.start({"WAREHOUSE_QUERY_TIMEOUT": "1"})
        started = time.monotonic()
        is_error, text = client.call("run_sql", {"query": (
            "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c)"
            " SELECT count(*) FROM c")})
        self.assertLess(time.monotonic() - started, 8)
        self.assertTrue(is_error)
        self.assertIn("stopped after 1 seconds", text)
        is_error, text = client.call("run_sql", {"query": "SELECT COUNT(*) AS n FROM carriers"})
        self.assertFalse(is_error, text)
        self.assertEqual(json.loads(text)[0]["n"], 6)

    def test_arguments_that_are_not_an_object_return_an_error_result(self):
        client = self.start()
        for bad in ([], ["SHP-0001"], "SHP-0001", 5):
            with self.subTest(arguments=bad):
                result = client.call_raw("get_shipment", bad)
                self.assertTrue(result.get("isError"))
                self.assertIn("expected a JSON object", result["content"][0]["text"])
        # The server is still up.
        self.assertFalse(client.call("list_carriers")[0])

    def test_missing_arguments_still_mean_no_arguments(self):
        client = self.start()
        reply = client.send("tools/call", {"name": "list_carriers"})
        self.assertNotIn("isError", reply["result"])

    def test_a_limit_below_one_is_rejected_not_unlimited(self):
        client = self.start()
        for bad in (0, -1, -50):
            with self.subTest(limit=bad):
                is_error, text = client.call("list_shipments", {"limit": bad})
                self.assertTrue(is_error)
                self.assertIn("limit must be 1 or more", text)


    def test_the_run_sql_description_states_the_timeout_that_is_set(self):
        client = self.start({"WAREHOUSE_QUERY_TIMEOUT": "2"})
        tools = client.send("tools/list")["result"]["tools"]
        description = next(tool["description"] for tool in tools if tool["name"] == "run_sql")
        self.assertIn("2 seconds", description)
        self.assertNotIn("5 seconds", description)

    def test_the_run_sql_description_says_5_seconds_by_default(self):
        client = self.start()
        tools = client.send("tools/list")["result"]["tools"]
        description = next(tool["description"] for tool in tools if tool["name"] == "run_sql")
        self.assertIn("5 seconds", description)

class WarehouseDataTests(unittest.TestCase):
    """Row counts in the committed database match the CSVs."""

    def count(self, query):
        client = Client()
        try:
            client.send(
                "initialize",
                {"protocolVersion": "2025-06-18", "capabilities": {},
                 "clientInfo": {"name": "test", "version": "0"}},
            )
            _, text = client.call("run_sql", {"query": query})
            return json.loads(text)[0]["n"]
        finally:
            client.close()

    def test_row_counts_match_the_csvs(self):
        expected = {
            "shipments": len(csv_rows(REFERENCE / "shipments.csv")),
            "carriers": len(csv_rows(REFERENCE / "carriers.csv")),
            "lanes": len(csv_rows(REFERENCE / "lanes.csv")),
            "carrier_notes": len(csv_rows(REFERENCE / "carrier_notes.csv")),
        }
        for table, rows in expected.items():
            with self.subTest(table=table):
                self.assertEqual(self.count(f"SELECT COUNT(*) AS n FROM {table}"), rows)

    def test_raw_readings_count_matches_the_logger_files(self):
        total = 0
        for path in (ROOT / "data" / "raw" / "loggers").glob("week-*/*.csv"):
            total += len(csv_rows(path))
        self.assertEqual(self.count("SELECT COUNT(*) AS n FROM raw_readings"), total)

    def test_ship_date_differs_from_the_csv_only_for_early_departures(self):
        """Warehouse ship_date is the UTC-5 date of departed_at (16 rows, 6 in October)."""
        client = Client()
        try:
            client.send(
                "initialize",
                {"protocolVersion": "2025-06-18", "capabilities": {},
                 "clientInfo": {"name": "test", "version": "0"}},
            )
            _, text = client.call(
                "run_sql", {"query": "SELECT shipment_id, ship_date FROM shipments LIMIT 200"})
        finally:
            client.close()
        warehouse = {}
        for row in json.loads(text):
            warehouse.setdefault(row["shipment_id"], []).append(row["ship_date"])
        changed = []
        for row in csv_rows(REFERENCE / "shipments.csv"):
            if row["ship_date"] not in warehouse[row["shipment_id"]]:
                changed.append(row)
        self.assertEqual(len(changed), 16)
        self.assertEqual(sum(row["ship_date"].startswith("2026-10") for row in changed), 6)


class SelfTestTests(unittest.TestCase):
    def test_self_test_prints_six_tool_names(self):
        result = subprocess.run(
            [sys.executable, str(SERVER), "--self-test"], cwd=ROOT,
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(result.stdout.split()), TOOLS)


class McpConfigTests(unittest.TestCase):
    def test_mcp_json_names_the_warehouse_server(self):
        config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        server = config["mcpServers"]["northfield-warehouse"]
        self.assertEqual(server["command"], "python")
        self.assertEqual(server["args"], ["warehouse/server.py"])


if __name__ == "__main__":
    unittest.main()
