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

# A stand-in audit hook: it echoes the event's IDs into a fixed record. It
# knows nothing about the Lab 7 summary rules.
MINIMAL_AUDIT = '''
import json
import os
import sys

event = json.load(sys.stdin)
record = {
    "timestamp": "2026-01-01T00:00:00Z", "event": event["hook_event_name"],
    "tool_name": event["tool_name"], "tool_use_id": event["tool_use_id"], "summary": "test",
}
with open(os.path.join(os.environ["CLAUDE_PROJECT_DIR"], "audit.jsonl"), "a", encoding="utf-8") as log:
    log.write(json.dumps(record) + "\\n")
'''


def appending_hook(contents, mode="a"):
    """Source for a hook that writes fixed text to audit.jsonl."""
    return (
        "import os\n"
        "path = os.path.join(os.environ['CLAUDE_PROJECT_DIR'], 'audit.jsonl')\n"
        f"with open(path, {mode!r}, encoding='utf-8') as log:\n"
        f"    log.write({contents!r})\n"
    )


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

    def write_fixture(self, hook, name="example", tool="Bash", tool_input=None, expect_exit=0,
                      event_name=None):
        event = {
            "session_id": "test-session", "tool_use_id": name, "tool_name": tool,
            "hook_event_name": event_name or ("PreToolUse" if hook == "claim_guard" else "PostToolUse"),
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
        for text in ("FAIL example", "expected exit 0 and one valid audit record appended", "found 0", "stderr: (empty)"):
            self.assertIn(text, completed.stdout)

    def test_valid_audit_records_pass_in_fresh_directories(self):
        self.write_hook("audit_log", MINIMAL_AUDIT)
        cases = [
            ("bash", "Bash", {"command": "echo test"}),
            ("powershell", "PowerShell", {"command": r"Get-Content .\claims\TST-001.json"}),
            ("read", "Read", {"file_path": "claims/TST-001.json"}),
            ("large", "Search", {"query": "x" * 300}),
        ]
        for name, tool, data in cases:
            self.write_fixture("audit_log", name, tool, data)
        self.write_fixture("audit_log", "failure", "Bash", {"command": "false"},
                           event_name="PostToolUseFailure")
        completed = self.run_harness("audit_log")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("5 passed, 0 failed", completed.stdout)

    def test_long_summary_passes_when_it_is_the_whole_command(self):
        command = "echo " + "x" * 250
        self.write_fixture("audit_log", tool_input={"command": command})
        record = {
            "timestamp": "2026-01-01T00:00:00Z", "event": "PostToolUse", "tool_name": "Bash",
            "tool_use_id": "example", "summary": command,
        }
        self.write_hook("audit_log", appending_hook(json.dumps(record) + "\n"))
        completed = self.run_harness("audit_log")
        self.assertEqual(completed.returncode, 0, completed.stdout)

    def test_bad_audit_records_fail(self):
        self.write_fixture("audit_log")
        valid = {
            "timestamp": "2026-01-01T00:00:00Z", "event": "PostToolUse", "tool_name": "Bash",
            "tool_use_id": "example", "summary": "echo test",
        }
        missing_event = {key: value for key, value in valid.items() if key != "event"}
        invalid_records = {
            "invalid JSON": ("{broken\n", "a"),
            "two lines": ((json.dumps(valid) + "\n") * 2, "a"),
            "no fields": ("{}\n", "a"),
            "not an object": ("[]\n", "a"),
            "no event": (json.dumps(missing_event) + "\n", "a"),
            "wrong event": (json.dumps(dict(valid, event="PreToolUse")) + "\n", "a"),
            "wrong tool": (json.dumps(dict(valid, tool_name="Read")) + "\n", "a"),
            "wrong use ID": (json.dumps(dict(valid, tool_use_id="other")) + "\n", "a"),
            "bad timestamp": (json.dumps(dict(valid, timestamp="yesterday")) + "\n", "a"),
            "empty summary": (json.dumps(dict(valid, summary="")) + "\n", "a"),
            "wrong summary": (json.dumps(dict(valid, summary="x" * 201)) + "\n", "a"),
            "overwrites the file": (json.dumps(valid) + "\n", "w"),
        }
        for name, (contents, mode) in invalid_records.items():
            with self.subTest(name=name):
                self.write_hook("audit_log", appending_hook(contents, mode))
                completed = self.run_harness("audit_log")
                self.assertEqual(completed.returncode, 1, completed.stdout)
                self.assertIn("FAIL example", completed.stdout)

    def test_valid_audit_record_with_wrong_exit_fails(self):
        self.write_fixture("audit_log")
        self.write_hook("audit_log", MINIMAL_AUDIT + "\nsys.exit(1)\n")
        completed = self.run_harness("audit_log")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("actual exit 1", completed.stdout)

    def test_empty_fixture_directory_fails(self):
        completed = self.run_harness("claim_guard")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("expected fixtures; found none", completed.stdout)


if __name__ == "__main__":
    unittest.main()
