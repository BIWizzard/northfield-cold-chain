"""Test the SQL guard harness and its fixtures, not the hook.

Every test here uses a throwaway hook, so it passes whether `hooks/sql_guard.py`
is the stub or the completed hook.
"""

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
SQL_FIXTURES = ROOT / "hooks" / "fixtures" / "sql"
RUN_SQL = "mcp__northfield-warehouse__run_sql"


def real_fixtures():
    return [json.loads(path.read_text(encoding="utf-8")) | {"_path": path}
            for path in sorted(SQL_FIXTURES.glob("*.json"))]


class SqlFixtureTests(unittest.TestCase):
    """The fixtures in hooks/fixtures/sql are well formed."""

    def test_every_fixture_is_a_run_sql_event_with_an_expected_exit(self):
        fixtures = real_fixtures()
        self.assertTrue(fixtures)
        for fixture in fixtures:
            path = fixture["_path"]
            with self.subTest(fixture=path.name):
                self.assertEqual(fixture["name"], path.stem)
                self.assertIn(fixture["expect_exit"], (0, 2))
                event = fixture["event"]
                self.assertEqual(event["hook_event_name"], "PreToolUse")
                self.assertEqual(event["tool_name"], RUN_SQL)
                self.assertIsInstance(event["tool_input"]["query"], str)
                self.assertTrue(event["tool_input"]["query"].strip())

    def test_names_say_whether_the_fixture_blocks(self):
        for fixture in real_fixtures():
            with self.subTest(fixture=fixture["name"]):
                expected = 0 if fixture["name"].startswith("allow-") else 2
                self.assertEqual(fixture["expect_exit"], expected)

    def test_the_spec_cases_are_covered(self):
        names = {fixture["name"] for fixture in real_fixtures()}
        for name in ("allow-updated-at-column", "allow-like-delete", "allow-with-select",
                     "block-insert", "block-raw-readings", "block-no-where-or-limit",
                     "bypass-write-after-block-comment", "bypass-mixed-case-delete",
                     "bypass-select-then-delete", "bypass-with-delete"):
            with self.subTest(fixture=name):
                self.assertIn(name, names)


class SqlHarnessTests(unittest.TestCase):
    """hooks/test_hook.py runs SQL fixtures and reports PASS and FAIL."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sql-harness-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.hooks = self.root / "hooks"
        self.fixtures = self.hooks / "fixtures" / "sql"
        self.fixtures.mkdir(parents=True)
        (self.hooks / "fixtures" / "project").mkdir()
        shutil.copyfile(ROOT / "hooks/test_hook.py", self.hooks / "test_hook.py")

    def write_hook(self, source):
        (self.hooks / "sql_guard.py").write_text(textwrap.dedent(source), encoding="utf-8")

    def write_fixture(self, name, query, expect_exit):
        fixture = {"name": name, "expect_exit": expect_exit, "event": {
            "session_id": "test-session", "hook_event_name": "PreToolUse", "tool_name": RUN_SQL,
            "tool_input": {"query": query}, "tool_use_id": name,
        }}
        (self.fixtures / f"{name}.json").write_text(json.dumps(fixture), encoding="utf-8")

    def run_harness(self):
        return subprocess.run(
            [sys.executable, str(self.hooks / "test_hook.py"), "sql_guard"],
            cwd=self.root, text=True, capture_output=True, env=dict(os.environ),
        )

    def test_hook_receives_the_query_and_is_judged_on_the_expected_exit(self):
        self.write_fixture("allowed", "SELECT 1 LIMIT 1", 0)
        self.write_fixture("blocked", "DELETE FROM shipments", 2)
        self.write_hook('''
            import json
            import sys
            query = json.load(sys.stdin)["tool_input"]["query"]
            sys.exit(2 if query.startswith("DELETE") else 0)
        ''')
        completed = self.run_harness()
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(completed.stdout, "PASS allowed\nPASS blocked\n2 passed, 0 failed\n")

    def test_a_hook_that_lets_a_blocking_fixture_through_fails(self):
        self.write_fixture("blocked", "DELETE FROM shipments", 2)
        self.write_hook("import sys\nsys.stdin.read()\n")
        completed = self.run_harness()
        self.assertEqual(completed.returncode, 1)
        for text in ("FAIL blocked", "expected exit 2", "actual exit 0", "0 passed, 1 failed"):
            self.assertIn(text, completed.stdout)

    def test_a_hook_that_blocks_an_allowed_fixture_fails_and_shows_its_reason(self):
        self.write_fixture("allowed", "SELECT 1 LIMIT 1", 0)
        self.write_hook('''
            import sys
            print("too strict", file=sys.stderr)
            sys.exit(2)
        ''')
        completed = self.run_harness()
        self.assertEqual(completed.returncode, 1)
        for text in ("FAIL allowed", "expected exit 0", "actual exit 2", "too strict"):
            self.assertIn(text, completed.stdout)

    def test_the_real_fixtures_run_and_split_by_expected_exit(self):
        """A hook that never blocks passes the allowed fixtures and fails the rest."""
        for path in SQL_FIXTURES.glob("*.json"):
            shutil.copyfile(path, self.fixtures / path.name)
        self.write_hook("import sys\nsys.stdin.read()\n")
        completed = self.run_harness()
        fixtures = real_fixtures()
        allowed = sum(fixture["expect_exit"] == 0 for fixture in fixtures)
        self.assertEqual(completed.returncode, 1)
        self.assertIn(f"{allowed} passed, {len(fixtures) - allowed} failed", completed.stdout)
        for fixture in fixtures:
            status = "PASS" if fixture["expect_exit"] == 0 else "FAIL"
            with self.subTest(fixture=fixture["name"]):
                self.assertIn(f"{status} {fixture['name']}", completed.stdout)

    def test_no_fixtures_fails(self):
        self.write_hook("import sys\n")
        completed = self.run_harness()
        self.assertEqual(completed.returncode, 1)
        self.assertIn("expected fixtures; found none", completed.stdout)


if __name__ == "__main__":
    unittest.main()
