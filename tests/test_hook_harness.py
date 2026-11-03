"""Test harness reporting and audit validation with throwaway hooks."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
PASSING_AUDIT = '''
import json
import os
from pathlib import Path
import sys

event = json.load(sys.stdin)
data = event["tool_input"]
if event["tool_name"] in ("Bash", "PowerShell"):
    summary = data["command"]
elif event["tool_name"] in ("Read", "Write", "Edit"):
    summary = data["file_path"]
else:
    summary = json.dumps(data, separators=(",", ":"))[:200]
path = Path(os.environ["CLAUDE_PROJECT_DIR"]) / "audit.jsonl"
assert not path.exists(), "Each fixture needs a fresh directory"
record = {
    "timestamp": "2026-01-01T00:00:00Z", "tool_name": event["tool_name"],
    "tool_use_id": event["tool_use_id"], "summary": summary,
}
path.write_text(json.dumps(record) + "\\n", encoding="utf-8")
'''


class HookHarnessTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="hook-harness-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.hooks = self.root / "hooks"
        self.fixtures = self.hooks / "fixtures"
        for name in ("claim_guard", "audit_log", "project"):
            (self.fixtures / name).mkdir(parents=True)
        shutil.copyfile(ROOT / "hooks/test_hook.py", self.hooks / "test_hook.py")
        self.working = self.root / "working"
        self.working.mkdir()

    def write_hook(self, name, source):
        (self.hooks / f"{name}.py").write_text(textwrap.dedent(source), encoding="utf-8")

    def write_fixture(self, hook, name="example", tool="Bash", tool_input=None, expect_exit=0):
        event = {
            "session_id": "test-session", "tool_use_id": name, "tool_name": tool,
            "hook_event_name": "PreToolUse" if hook == "claim_guard" else "PostToolUse",
            "tool_input": tool_input if tool_input is not None else {"command": "echo test"},
        }
        fixture = {"name": name, "event": event}
        if hook == "claim_guard":
            fixture["expect_exit"] = expect_exit
        (self.fixtures / hook / f"{name}.json").write_text(json.dumps(fixture), encoding="utf-8")
        return event

    def run_harness(self, name):
        completed = subprocess.run(
            [sys.executable, str(self.hooks / "test_hook.py"), name],
            cwd=self.working, text=True, capture_output=True,
            env=dict(os.environ, CLAUDE_PROJECT_DIR=str(self.working)),
        )
        self.assertFalse((self.working / "audit.jsonl").exists())
        self.assertFalse((self.root / "audit.jsonl").exists())
        self.assertFalse((self.fixtures / "project/audit.jsonl").exists())
        return completed

    def test_passing_claim_hook_receives_event_and_synthetic_project(self):
        self.write_fixture("claim_guard")
        (self.fixtures / "project/marker").write_text("synthetic", encoding="utf-8")
        self.write_hook("claim_guard", '''
            import json
            import os
            from pathlib import Path
            import sys
            assert json.load(sys.stdin)["tool_use_id"] == "example"
            assert (Path(os.environ["CLAUDE_PROJECT_DIR"]) / "marker").is_file()
        ''')
        completed = self.run_harness("claim_guard")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, "PASS example\n1 passed, 0 failed\n")

    def test_wrong_exit_reports_expected_actual_and_stderr(self):
        self.write_fixture("claim_guard", expect_exit=2)
        self.write_hook("claim_guard", '''
            import sys
            print("wrong exit on purpose", file=sys.stderr)
            sys.exit(1)
        ''')
        completed = self.run_harness("claim_guard")
        self.assertEqual(completed.returncode, 1)
        for text in ("FAIL example", "expected exit 2", "actual exit 1", "wrong exit on purpose", "0 passed, 1 failed"):
            self.assertIn(text, completed.stdout)

    def test_expected_block_is_a_pass(self):
        self.write_fixture("claim_guard", expect_exit=2)
        self.write_hook("claim_guard", "import sys\nsys.exit(2)\n")
        completed = self.run_harness("claim_guard")
        self.assertEqual(completed.returncode, 0, completed.stdout)
        self.assertIn("PASS example", completed.stdout)

    def test_audit_hook_that_writes_nothing_fails(self):
        self.write_fixture("audit_log")
        self.write_hook("audit_log", "import sys\nsys.stdin.read()\n")
        completed = self.run_harness("audit_log")
        self.assertEqual(completed.returncode, 1)
        for text in ("FAIL example", "expected exit 0 and one valid audit record", "missing", "stderr: (empty)"):
            self.assertIn(text, completed.stdout)

    def test_valid_audit_records_pass_in_fresh_directories(self):
        self.write_hook("audit_log", PASSING_AUDIT)
        cases = [
            ("bash", "Bash", {"command": "echo " + "x" * 250}),
            ("powershell", "PowerShell", {"command": r"Get-Content .\claims\TST-001.json"}),
            ("read", "Read", {"file_path": "claims/" + "x" * 250}),
            ("write", "Write", {"file_path": "claims/TST-001.json"}),
            ("edit", "Edit", {"file_path": "claims/TST-001.json"}),
            ("large", "Search", {"query": "x" * 300}),
        ]
        for name, tool, data in cases:
            self.write_fixture("audit_log", name, tool, data)
        completed = self.run_harness("audit_log")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(completed.stdout.count("PASS "), len(cases))
        self.assertIn("6 passed, 0 failed", completed.stdout)

    def test_bad_audit_records_fail(self):
        self.write_fixture("audit_log")
        valid = {
            "timestamp": "2026-01-01T00:00:00Z", "tool_name": "Bash",
            "tool_use_id": "example", "summary": "echo test",
        }
        invalid_records = {
            "invalid JSON": "{broken\n",
            "two lines": (json.dumps(valid) + "\n") * 2,
            "no fields": "{}\n",
            "not an object": "[]\n",
            "wrong tool": json.dumps(dict(valid, tool_name="Read")) + "\n",
            "wrong use ID": json.dumps(dict(valid, tool_use_id="other")) + "\n",
            "bad timestamp": json.dumps(dict(valid, timestamp="yesterday")) + "\n",
            "empty summary": json.dumps(dict(valid, summary="")) + "\n",
            "wrong summary": json.dumps(dict(valid, summary="x" * 201)) + "\n",
        }
        for name, contents in invalid_records.items():
            with self.subTest(name=name):
                source = (
                    "import os\nfrom pathlib import Path\n"
                    "path = Path(os.environ['CLAUDE_PROJECT_DIR']) / 'audit.jsonl'\n"
                    f"path.write_text({contents!r}, encoding='utf-8')\n"
                )
                self.write_hook("audit_log", source)
                completed = self.run_harness("audit_log")
                self.assertEqual(completed.returncode, 1, completed.stdout)
                self.assertIn("FAIL example", completed.stdout)

    def test_valid_audit_record_with_wrong_exit_fails(self):
        self.write_fixture("audit_log")
        self.write_hook("audit_log", PASSING_AUDIT + "\nsys.exit(1)\n")
        completed = self.run_harness("audit_log")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("actual exit 1", completed.stdout)

    def test_empty_fixture_directory_fails(self):
        completed = self.run_harness("claim_guard")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("expected fixtures; found none", completed.stdout)


if __name__ == "__main__":
    unittest.main()
