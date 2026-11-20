"""Check claim evidence and failures through the guard's entry point."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "hooks/claim_guard.py"
FIXTURES = ROOT / "hooks/fixtures"


class ClaimGuardTests(unittest.TestCase):
    def run_guard(self, event, project=None):
        return subprocess.run(
            [sys.executable, str(GUARD)], input=event, text=True, capture_output=True,
            env=dict(os.environ, CLAUDE_PROJECT_DIR=str(project or FIXTURES / "project")),
            timeout=10,
        )

    def fixture_event(self, name):
        fixture = json.loads((FIXTURES / "claim_guard" / name).read_text(encoding="utf-8"))
        return json.dumps(fixture["event"])

    def assert_block(self, completed, reason):
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertEqual(completed.stdout, "")
        self.assertEqual(completed.stderr, reason + "\n")

    def test_all_claim_fixtures(self):
        for path in sorted((FIXTURES / "claim_guard").rglob("*.json")):
            with self.subTest(fixture=path.name):
                fixture = json.loads(path.read_text(encoding="utf-8"))
                completed = self.run_guard(json.dumps(fixture["event"]))
                self.assertEqual(completed.returncode, fixture["expect_exit"], completed.stderr)
                self.assertEqual(completed.stdout, "")
                if fixture["expect_exit"] == 0:
                    self.assertEqual(completed.stderr, "")
                else:
                    self.assertEqual(len(completed.stderr.splitlines()), 1)

    def test_deep_payload_blocks_with_payload_reason(self):
        completed = self.run_guard(self.fixture_event("deep-nesting.json"))
        payload = FIXTURES / "project/claims/deep-nesting.json"
        self.assert_block(completed, f"Create a readable, valid JSON payload at {payload} before filing.")

    def test_deep_stdin_blocks_with_event_reason(self):
        event = self.fixture_event("plumbing/good-bash.json")
        nested = (FIXTURES / "project/claims/deep-nesting.json").read_text(encoding="utf-8")
        event = event[:-1] + ', "nested": ' + nested + "}"
        completed = self.run_guard(event)
        self.assert_block(completed, "Provide a valid JSON hook event on stdin.")

    def test_shipments_with_bom_allows_valid_claim(self):
        with tempfile.TemporaryDirectory(prefix="claim-guard-bom-") as directory:
            project = Path(directory) / "project"
            shutil.copytree(FIXTURES / "project", project)
            shipments = project / "data/reference/shipments.csv"
            contents = shipments.read_text(encoding="utf-8")
            shipments.write_text(contents, encoding="utf-8-sig")
            completed = self.run_guard(self.fixture_event("plumbing/good-bash.json"), project)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, "")
        self.assertEqual(completed.stderr, "")

    def run_with_exception(self, error):
        event = self.fixture_event("plumbing/good-bash.json").encode("utf-8")
        with io.TextIOWrapper(io.BytesIO(event), encoding="utf-8") as stdin:
            with mock.patch.object(sys, "path", [str(GUARD.parent), *sys.path]), \
                    mock.patch("claim_call.find_claim_call", side_effect=error), \
                    mock.patch.object(sys, "stdin", stdin):
                runpy.run_path(str(GUARD), run_name="__main__")

    def test_unexpected_exception_blocks(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as raised:
                self.run_with_exception(RuntimeError("unexpected failure"))
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "Cannot verify the claim: unexpected RuntimeError.\n")

    def test_system_exit_and_keyboard_interrupt_propagate(self):
        for error in (SystemExit(7), KeyboardInterrupt()):
            with self.subTest(exception=type(error).__name__):
                stdout, stderr = io.StringIO(), io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    with self.assertRaises(type(error)) as raised:
                        self.run_with_exception(error)
                self.assertIs(raised.exception, error)
                self.assertEqual(stdout.getvalue(), "")
                self.assertEqual(stderr.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
