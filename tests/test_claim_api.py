"""Exercise the mock claim tool in an isolated repository."""

from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ClaimApiTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="claim-api-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "tools").mkdir()
        self.tool = self.root / "tools/carrier_claim_api.py"
        shutil.copyfile(ROOT / "tools/carrier_claim_api.py", self.tool)
        self.submitted = self.root / "claims/submitted.jsonl"
        self.payload = {
            "shipment_id": "TST-001", "carrier_id": "CAR-TEST",
            "disposition": "hold", "logger_file": "data/raw/loggers/TST-001.csv",
            "product_category": "fresh", "minutes_out_of_range": 15,
            "summary": "Synthetic claim for testing.",
        }

    def run_tool(self, *args, cwd=None):
        return subprocess.run(
            [sys.executable, str(self.tool), *args], cwd=cwd or self.root,
            text=True, capture_output=True,
        )

    def write_payload(self, value):
        payload_path = self.root / "payload with spaces.json"
        payload_path.write_text(json.dumps(value), encoding="utf-8")
        return payload_path

    def records(self):
        return [json.loads(line) for line in self.submitted.read_text(encoding="utf-8").splitlines()]

    def test_valid_payload_prints_and_records_claim(self):
        path = self.write_payload(self.payload)
        completed = self.run_tool("--payload", str(path))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, "")
        self.assertRegex(
            completed.stdout,
            r"^Claim CLM-\d{6} filed for TST-001\. Mock only: nothing was sent\.\n$",
        )
        records = self.records()
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(set(record), {"filed_at", "claim_id", "payload"})
        self.assertEqual(record["payload"], self.payload)
        self.assertEqual(record["claim_id"], re.search(r"CLM-\d{6}", completed.stdout).group())
        self.assertTrue(record["filed_at"].endswith("Z"))
        datetime.fromisoformat(record["filed_at"][:-1] + "+00:00")

    def test_payload_argument_is_required(self):
        completed = self.run_tool()
        self.assertEqual(completed.returncode, 2)
        self.assertIn("--payload", completed.stderr)
        self.assertFalse(self.submitted.exists())

    def test_missing_file_fails_without_record(self):
        completed = self.run_tool("--payload", "absent.json")
        self.assertEqual(completed.returncode, 1)
        self.assertTrue(completed.stderr)
        self.assertEqual(completed.stdout, "")
        self.assertFalse(self.submitted.exists())

    def test_invalid_json_fails_without_record(self):
        path = self.root / "invalid.json"
        path.write_text('{"shipment_id":', encoding="utf-8")
        completed = self.run_tool("--payload", str(path))
        self.assertEqual(completed.returncode, 1)
        self.assertTrue(completed.stderr)
        self.assertEqual(completed.stdout, "")
        self.assertFalse(self.submitted.exists())

    def test_claims_append_instead_of_overwriting(self):
        for shipment_id in ("TST-001", "TST-002"):
            path = self.write_payload(dict(self.payload, shipment_id=shipment_id))
            completed = self.run_tool("--payload", str(path))
            self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            [record["payload"]["shipment_id"] for record in self.records()],
            ["TST-001", "TST-002"],
        )

    def test_no_evidence_or_schema_checks(self):
        values = [dict(self.payload, disposition="release"), {}, ["TST-001"], None]
        for value in values:
            with self.subTest(payload=value):
                path = self.write_payload(value)
                completed = self.run_tool("--payload", str(path))
                self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([record["payload"] for record in self.records()], values)

    def test_output_root_comes_from_script_not_working_directory(self):
        working = self.root / "elsewhere"
        working.mkdir()
        path = self.write_payload(self.payload)
        completed = self.run_tool("--payload", str(path), cwd=working)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(len(self.records()), 1)
        self.assertFalse((working / "claims").exists())

    def test_relative_backslash_payload_path(self):
        folder = self.root / "inputs"
        folder.mkdir()
        (folder / "claim.json").write_text(json.dumps(self.payload), encoding="utf-8")
        completed = self.run_tool("--payload", r"inputs\claim.json")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.records()[0]["payload"], self.payload)


if __name__ == "__main__":
    unittest.main()
