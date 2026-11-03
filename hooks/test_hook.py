"""Run synthetic events through a hook and report each fixture's result."""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "hooks" / "fixtures"


# Each audit fixture starts with this record already in audit.jsonl, so a hook
# that overwrites the file instead of appending to it fails.
SEED_RECORD = {
    "timestamp": "2026-01-01T00:00:00Z", "event": "PostToolUse", "tool_name": "Seed",
    "tool_use_id": "seed", "summary": "an earlier record that must survive",
}
SEED_LINE = json.dumps(SEED_RECORD)


def audit_result(project, event):
    """Return a failure reason, or an empty string for a valid appended record."""
    try:
        lines = (project / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return f"audit.jsonl unreadable or missing: {exc}"
    if not lines or lines[0] != SEED_LINE:
        return "audit.jsonl lost the record that was already there; append instead of overwriting"
    if len(lines) != 2:
        return f"expected one new line in audit.jsonl; found {len(lines) - 1}"
    try:
        record = json.loads(lines[1])
    except ValueError:
        return "audit.jsonl contains invalid JSON"
    fields = {"timestamp", "event", "tool_name", "tool_use_id", "summary"}
    if not isinstance(record, dict) or not fields.issubset(record):
        return "audit record is missing required fields"
    if record["event"] != event["hook_event_name"]:
        return "audit event does not match the event's hook_event_name"
    if record["tool_name"] != event["tool_name"] or record["tool_use_id"] != event["tool_use_id"]:
        return "audit tool_name or tool_use_id does not match the event"
    timestamp = record["timestamp"]
    try:
        if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
            return "audit timestamp must be UTC ISO-8601 ending in Z"
        datetime.fromisoformat(timestamp[:-1] + "+00:00")
    except ValueError:
        return "audit timestamp is not ISO-8601"
    tool_input = event["tool_input"]
    full_summary = None
    if event["tool_name"] in ("Bash", "PowerShell"):
        full_summary = tool_input["command"]
    elif event["tool_name"] in ("Read", "Write", "Edit"):
        full_summary = tool_input["file_path"]
    summary = record["summary"]
    if not isinstance(summary, str) or not summary:
        return "audit summary must be a non-empty string"
    if len(summary) > 200 and summary != full_summary:
        return "audit summary exceeds 200 characters without matching the command or file path"
    return ""


def run_fixture(hook_name, hook_path, fixture, project):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project.resolve()))
    expected_exit = fixture["expect_exit"] if hook_name == "claim_guard" else 0
    expected = f"exit {expected_exit}"
    if hook_name == "audit_log":
        expected += " and one valid audit record appended"
        (project / "audit.jsonl").write_text(SEED_LINE + "\n", encoding="utf-8")
    try:
        completed = subprocess.run(
            [sys.executable, str(hook_path)], input=json.dumps(fixture["event"]),
            text=True, capture_output=True, env=env, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        stderr = repr(getattr(exc, "stderr", None))
        return False, f"expected {expected}; could not run hook: {exc}; stderr: {stderr}"
    problems = []
    if completed.returncode != expected_exit:
        problems.append(f"exit {completed.returncode}")
    if hook_name == "audit_log":
        problem = audit_result(project, fixture["event"])
        if problem:
            problems.append(problem)
    if problems:
        stderr = repr(completed.stderr.strip()) if completed.stderr.strip() else "(empty)"
        return False, f"expected {expected}; actual {'; '.join(problems)}; stderr: {stderr}"
    return True, ""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hook", choices=("claim_guard", "audit_log"))
    args = parser.parse_args(argv)
    fixture_paths = sorted((FIXTURES / args.hook).glob("*.json"))
    if not fixture_paths:
        print(f"FAIL {args.hook}: expected fixtures; found none")
        print("0 passed, 1 failed")
        return 1
    passed = 0
    for fixture_path in fixture_paths:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        hook_path = ROOT / "hooks" / f"{args.hook}.py"
        if args.hook == "audit_log":
            with tempfile.TemporaryDirectory(prefix="audit-hook-") as directory:
                success, detail = run_fixture(args.hook, hook_path, fixture, Path(directory))
        else:
            success, detail = run_fixture(args.hook, hook_path, fixture, FIXTURES / "project")
        passed += success
        status = "PASS" if success else "FAIL"
        print(f"{status} {fixture['name']}" + (f": {detail}" if detail else ""))
    failed = len(fixture_paths) - passed
    print(f"{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
