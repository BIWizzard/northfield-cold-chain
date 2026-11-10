"""Checks for the metrics Stop hook and the script that reports its totals."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = ROOT / "hooks" / "lab_metrics.py"
TOOL_PATH = ROOT / "tools" / "lab_metrics.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = load("lab_metrics_hook", HOOK_PATH)
tool = load("lab_metrics_tool", TOOL_PATH)


def usage(input_tokens=0, output_tokens=0, cache_creation=0, cache_read=0):
    return {"input_tokens": input_tokens, "output_tokens": output_tokens,
            "cache_creation_input_tokens": cache_creation, "cache_read_input_tokens": cache_read}


def assistant(message_id, stamp, message_usage, sidechain=False):
    entry = {"type": "assistant", "timestamp": stamp,
             "message": {"id": message_id, "usage": message_usage}}
    if sidechain:
        entry["isSidechain"] = True
    return json.dumps(entry)


def user(stamp):
    return json.dumps({"type": "user", "timestamp": stamp, "message": {"content": "hi"}})


def write_transcript(directory, lines, name="session.jsonl"):
    path = Path(directory) / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class ParseTranscriptTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def parse(self, lines):
        return hook.parse_transcript(write_transcript(self.directory.name, lines))

    def test_01_sums_the_four_token_kinds(self):
        totals = self.parse([
            user("2026-11-05T10:00:00Z"),
            assistant("m1", "2026-11-05T10:00:05Z", usage(10, 20, 30, 40)),
            assistant("m2", "2026-11-05T10:00:09Z", usage(1, 2, 3, 4)),
        ])
        self.assertEqual(totals["input_tokens"], 11)
        self.assertEqual(totals["output_tokens"], 22)
        self.assertEqual(totals["cache_creation_tokens"], 33)
        self.assertEqual(totals["cache_read_tokens"], 44)
        self.assertEqual(totals["total_tokens"], 66)
        self.assertEqual(totals["messages"], 2)

    def test_02_a_message_repeated_on_several_lines_counts_once(self):
        totals = self.parse([
            assistant("m1", "2026-11-05T10:00:01Z", usage(5, 50, 0, 100)),
            assistant("m1", "2026-11-05T10:00:02Z", usage(5, 50, 0, 100)),
            assistant("m1", "2026-11-05T10:00:03Z", usage(5, 50, 0, 100)),
        ])
        self.assertEqual(totals["total_tokens"], 55)
        self.assertEqual(totals["messages"], 1)

    def test_03_a_repeated_message_keeps_its_largest_counts(self):
        totals = self.parse([
            assistant("m1", "2026-11-05T10:00:01Z", usage(5, 10, 0, 0)),
            assistant("m1", "2026-11-05T10:00:02Z", usage(5, 50, 0, 0)),
        ])
        self.assertEqual(totals["output_tokens"], 50)

    def test_04_subagent_entries_are_not_counted(self):
        totals = self.parse([
            assistant("main", "2026-11-05T10:00:01Z", usage(1, 1, 1, 1)),
            assistant("agent", "2026-11-05T10:00:02Z", usage(900, 900, 900, 900), sidechain=True),
        ])
        self.assertEqual(totals["total_tokens"], 3)

    def test_05_unreadable_and_half_written_lines_are_skipped(self):
        path = Path(self.directory.name) / "session.jsonl"
        good = assistant("m1", "2026-11-05T10:00:01Z", usage(1, 2, 3, 4))
        path.write_bytes((good + "\nnot json at all\n\xff\xfe broken\n"
                          '{"type": "assistant", "message": {"id": "m2", "usa').encode("utf-8", "surrogateescape"))
        totals = hook.parse_transcript(path)
        self.assertEqual(totals["total_tokens"], 6)
        self.assertEqual(totals["messages"], 1)

    def test_06_missing_or_odd_usage_counts_as_zero(self):
        totals = self.parse([
            json.dumps({"type": "assistant", "message": {"id": "a"}}),
            json.dumps({"type": "assistant", "message": {"id": "b", "usage": "oops"}}),
            json.dumps({"type": "assistant", "message": {"id": "c", "usage": {"input_tokens": "7", "output_tokens": None}}}),
            json.dumps({"type": "assistant", "message": {"id": "d", "usage": {"output_tokens": 5}}}),
            json.dumps(["not", "an", "object"]),
            json.dumps({"type": "assistant", "message": {"usage": usage(100, 100, 100, 100)}}),
        ])
        self.assertEqual(totals["output_tokens"], 5)
        self.assertEqual(totals["total_tokens"], 5)

    def test_07_minutes_run_from_first_to_last_message(self):
        totals = self.parse([
            user("2026-11-05T10:00:00Z"),
            assistant("m1", "2026-11-05T10:03:30.250Z", usage(1, 1, 0, 0)),
            user("2026-11-05T10:12:00Z"),
            assistant("m2", "2026-11-05T10:15:00Z", usage(1, 1, 0, 0)),
        ])
        self.assertEqual(totals["minutes"], 15.0)

    def test_08_other_entry_types_and_subagents_do_not_stretch_the_time(self):
        totals = self.parse([
            json.dumps({"type": "queue-operation", "timestamp": "2026-11-05T09:00:00Z"}),
            user("2026-11-05T10:00:00Z"),
            assistant("m1", "2026-11-05T10:05:00Z", usage(1, 1, 0, 0)),
            assistant("agent", "2026-11-05T11:00:00Z", usage(1, 1, 0, 0), sidechain=True),
            json.dumps({"type": "last-prompt", "timestamp": "2026-11-05T12:00:00Z"}),
        ])
        self.assertEqual(totals["minutes"], 5.0)

    def test_09_an_empty_transcript_totals_zero(self):
        path = Path(self.directory.name) / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        totals = hook.parse_transcript(path)
        self.assertEqual(totals["total_tokens"], 0)
        self.assertEqual(totals["minutes"], 0.0)

    def test_10_a_missing_transcript_raises_for_the_caller_to_report(self):
        with self.assertRaises(OSError):
            hook.parse_transcript(Path(self.directory.name) / "nope.jsonl")


class StopHookTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        # A folder name with a space, like many client laptops have.
        self.project = Path(self.directory.name) / "my project"
        self.project.mkdir()

    def run_hook(self, stdin_text):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.project))
        return subprocess.run([sys.executable, str(HOOK_PATH)], input=stdin_text,
                              text=True, capture_output=True, env=env, timeout=20)

    def event(self, transcript, session_id="s1"):
        return json.dumps({"session_id": session_id, "transcript_path": str(transcript),
                           "hook_event_name": "Stop", "cwd": str(self.project)})

    def records(self):
        lines = (self.project / "metrics.jsonl").read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines]

    def sample_transcript(self):
        return write_transcript(self.project, [
            user("2026-11-05T10:00:00Z"),
            assistant("m1", "2026-11-05T10:02:00Z", usage(10, 20, 30, 40)),
        ])

    def test_01_appends_one_record_with_the_totals_and_exits_0(self):
        done = self.run_hook(self.event(self.sample_transcript()))
        self.assertEqual(done.returncode, 0, done.stderr)
        (record,) = self.records()
        self.assertEqual(record["session_id"], "s1")
        self.assertEqual(record["total_tokens"], 60)
        self.assertEqual(record["minutes"], 2.0)
        self.assertTrue(record["timestamp"].endswith("Z"))
        for field in ("input_tokens", "output_tokens", "cache_creation_tokens",
                      "cache_read_tokens", "transcript_path", "messages"):
            self.assertIn(field, record)

    def test_02_keeps_the_lines_already_in_the_file(self):
        (self.project / "metrics.jsonl").write_text('{"session_id": "old"}\n', encoding="utf-8")
        self.run_hook(self.event(self.sample_transcript()))
        self.assertEqual([r["session_id"] for r in self.records()], ["old", "s1"])

    def test_03_each_turn_adds_a_line_with_running_totals(self):
        path = self.sample_transcript()
        self.run_hook(self.event(path))
        with path.open("a", encoding="utf-8") as transcript:
            transcript.write(assistant("m2", "2026-11-05T10:05:00Z", usage(1, 1, 1, 1)) + "\n")
        self.run_hook(self.event(path))
        first, second = self.records()
        self.assertEqual((first["total_tokens"], second["total_tokens"]), (60, 63))
        self.assertEqual((first["minutes"], second["minutes"]), (2.0, 5.0))

    def test_04_exits_0_and_says_why_when_the_event_is_not_json(self):
        done = self.run_hook("this is not json")
        self.assertEqual(done.returncode, 0)
        self.assertIn("lab_metrics", done.stderr)
        self.assertFalse((self.project / "metrics.jsonl").exists())

    def test_05_exits_0_and_says_why_when_the_transcript_is_missing(self):
        done = self.run_hook(self.event(self.project / "gone.jsonl"))
        self.assertEqual(done.returncode, 0)
        self.assertIn("lab_metrics", done.stderr)
        self.assertFalse((self.project / "metrics.jsonl").exists())

    def test_06_exits_0_when_the_event_lacks_fields(self):
        done = self.run_hook(json.dumps({"hook_event_name": "Stop"}))
        self.assertEqual(done.returncode, 0)
        self.assertIn("lab_metrics", done.stderr)

    def test_07_exits_0_when_the_project_folder_cannot_be_written(self):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.project / "does-not-exist"))
        done = subprocess.run([sys.executable, str(HOOK_PATH)],
                              input=self.event(self.sample_transcript()),
                              text=True, capture_output=True, env=env, timeout=20)
        self.assertEqual(done.returncode, 0)
        self.assertIn("lab_metrics", done.stderr)

    def test_08_prints_nothing_to_stdout(self):
        done = self.run_hook(self.event(self.sample_transcript()))
        self.assertEqual(done.stdout, "")


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name)

    def record(self, session_id, transcript, **overrides):
        record = {"session_id": session_id, "transcript_path": str(transcript), "minutes": 1.0,
                  "input_tokens": 1, "output_tokens": 1, "cache_creation_tokens": 1,
                  "cache_read_tokens": 1, "total_tokens": 3, "messages": 1}
        record.update(overrides)
        return json.dumps(record)

    def report(self, lines):
        (self.project / "metrics.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = tool.main(["--project", str(self.project)])
        return code, out.getvalue()

    def test_01_prints_minutes_and_tokens_for_the_latest_session(self):
        transcript = write_transcript(self.project, [
            user("2026-11-05T10:00:00Z"),
            assistant("m1", "2026-11-05T10:12:30Z", usage(1000, 2000, 3000, 4000)),
        ])
        code, text = self.report([
            self.record("old", transcript, minutes=99, total_tokens=1),
            self.record("new", transcript),
        ])
        self.assertEqual(code, 0)
        self.assertIn("Session: new", text)
        self.assertIn("Total minutes: 12.5", text)
        self.assertIn("Total tokens: 6,000", text)
        self.assertIn("Cache reads:  4,000", text)

    def test_02_totals_the_transcript_again_so_a_lagging_last_turn_is_not_lost(self):
        transcript = write_transcript(self.project, [
            user("2026-11-05T10:00:00Z"),
            assistant("m1", "2026-11-05T10:01:00Z", usage(100, 0, 0, 0)),
            assistant("m2", "2026-11-05T10:04:00Z", usage(50, 0, 0, 0)),
        ])
        # The saved record was written before the second message reached the file.
        code, text = self.report([self.record("s", transcript, minutes=1.0, total_tokens=100)])
        self.assertIn("Total tokens: 150", text)
        self.assertIn("Total minutes: 4.0", text)

    def test_03_falls_back_to_the_saved_totals_when_the_transcript_is_gone(self):
        code, text = self.report([
            self.record("s", self.project / "gone.jsonl", minutes=7.5, total_tokens=1234),
        ])
        self.assertEqual(code, 0)
        self.assertIn("Total minutes: 7.5", text)
        self.assertIn("Total tokens: 1,234", text)

    def test_04_says_what_to_do_when_there_are_no_metrics_yet(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = tool.main(["--project", str(self.project)])
        self.assertEqual(code, 1)
        self.assertIn("No metrics yet", out.getvalue())

    def test_05_skips_damaged_lines_in_the_metrics_file(self):
        transcript = self.project / "gone.jsonl"
        code, text = self.report([
            self.record("good", transcript, total_tokens=42),
            "this line is damaged",
        ])
        self.assertEqual(code, 0)
        self.assertIn("Session: good", text)
        self.assertIn("Total tokens: 42", text)


if __name__ == "__main__":
    unittest.main()
