"""Check the eval cases in evals/cases/ before the harness runs them."""

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals/cases"
BUCKETS = {"disposition", "lookup", "guardrail", "ask"}
SMOKE_ID = "smoke"
SEED_COUNT = 14
LAB13_TAG = "lab13"
LAB13_PER_BUCKET = 2
DISPOSITIONS = {"release", "excursion", "hold", "reject"}

# The fields each grader type needs, from the Graders table in the spec.
GRADER_FIELDS = {
    "contains": {"value"},
    "not_contains": {"value"},
    "disposition": {"expect"},
    "tool_called": {"tool", "match"},
    "tool_not_called": {"tool", "match"},
    "permission_denied": {"tool", "match"},
    "judge": {"rubric"},
}
CASE_FIELDS = {"id", "bucket", "prompt", "graders"}
OPTIONAL_CASE_FIELDS = {"tags"}


def load_cases():
    """Every case file, parsed, keyed by file name without `.json`."""
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(CASES.glob("*.json"))
    }


class CaseFileTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(CASES.is_dir(), "evals/cases/ is missing")
        self.cases = load_cases()

    def test_every_case_parses(self):
        for path in sorted(CASES.glob("*.json")):
            with self.subTest(case=path.name):
                case = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsInstance(case, dict)

    def test_fields(self):
        for name, case in self.cases.items():
            with self.subTest(case=name):
                missing = CASE_FIELDS - case.keys()
                self.assertFalse(missing, f"missing fields: {sorted(missing)}")
                unknown = case.keys() - CASE_FIELDS - OPTIONAL_CASE_FIELDS
                self.assertFalse(unknown, f"unknown fields: {sorted(unknown)}")
                self.assertIsInstance(case["prompt"], str)
                self.assertTrue(case["prompt"].strip(), "prompt is empty")
                tags = case.get("tags", [])
                self.assertIsInstance(tags, list)
                self.assertTrue(all(isinstance(tag, str) for tag in tags))

    def test_id_matches_file_name(self):
        for name, case in self.cases.items():
            with self.subTest(case=name):
                self.assertEqual(case.get("id"), name)
                self.assertRegex(name, r"^[a-z0-9]+(-[a-z0-9]+)*$")

    def test_bucket_is_known(self):
        for name, case in self.cases.items():
            with self.subTest(case=name):
                if name == SMOKE_ID:
                    self.assertEqual(case.get("bucket"), SMOKE_ID)
                else:
                    self.assertIn(case.get("bucket"), BUCKETS)

    def test_graders_are_known_and_complete(self):
        for name, case in self.cases.items():
            graders = case.get("graders")
            with self.subTest(case=name):
                self.assertIsInstance(graders, list)
                self.assertTrue(graders, "a case needs at least one grader")
            for index, grader in enumerate(graders or []):
                with self.subTest(case=name, grader=index):
                    kind = grader.get("type")
                    self.assertIn(kind, GRADER_FIELDS)
                    fields = set(grader) - {"type"}
                    self.assertEqual(fields, GRADER_FIELDS[kind])
                    for field in fields:
                        self.assertIsInstance(grader[field], str)
                        self.assertTrue(grader[field], f"{field} is empty")
                    if kind == "disposition":
                        self.assertIn(grader["expect"], DISPOSITIONS)
                    if "tool" in grader:
                        re.compile(grader["tool"])

    def test_seed_dispositions_make_no_severity_ruling(self):
        # The SOP leaves minor and serious undefined, so the seeds use only
        # release and excursion. hold and reject are for cases the room rules on.
        for name, case in self.cases.items():
            for grader in case.get("graders", []):
                if grader.get("type") == "disposition":
                    with self.subTest(case=name):
                        self.assertIn(grader["expect"], {"release", "excursion"})

    def test_fourteen_seeds_plus_smoke(self):
        self.assertIn(SMOKE_ID, self.cases)
        seeds = [name for name in self.cases if name != SMOKE_ID]
        self.assertEqual(len(seeds), SEED_COUNT)

    def test_lab13_tags_two_per_bucket(self):
        tagged = [case for case in self.cases.values() if LAB13_TAG in case.get("tags", [])]
        self.assertEqual(len(tagged), LAB13_PER_BUCKET * len(BUCKETS))
        for bucket in sorted(BUCKETS):
            with self.subTest(bucket=bucket):
                count = sum(case.get("bucket") == bucket for case in tagged)
                self.assertEqual(count, LAB13_PER_BUCKET)


if __name__ == "__main__":
    unittest.main()
