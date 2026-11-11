"""Checks for the Lab 12 judge: reading scores and measuring agreement."""

import csv
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
# Import the judge the way `python evals/judge.py` does, with evals/ on the import path.
sys.path.insert(0, str(ROOT / "evals"))

import judge  # noqa: E402


def all_yes():
    return {check: "yes" for check in judge.CHECKS}


class AgreementTests(unittest.TestCase):
    def test_identical_scores_agree_everywhere(self):
        scores = {"draft-1": all_yes(), "draft-2": all_yes()}
        result = judge.agreement(scores, scores)
        for check in judge.CHECKS:
            self.assertEqual(result["per_check"][check], (2, 2))
        self.assertEqual(result["overall"], (8, 8))

    def test_one_disagreement_lowers_one_check_and_the_overall(self):
        human = {"draft-1": all_yes(), "draft-2": all_yes()}
        model = {"draft-1": all_yes(), "draft-2": {**all_yes(), "tone": "no"}}
        result = judge.agreement(model, human)
        self.assertEqual(result["per_check"]["tone"], (1, 2))
        self.assertEqual(result["per_check"]["evidence"], (2, 2))
        self.assertEqual(result["overall"], (7, 8))

    def test_a_draft_the_human_left_blank_is_not_counted(self):
        human = {"draft-1": all_yes()}
        model = {"draft-1": all_yes(), "draft-2": {check: "no" for check in judge.CHECKS}}
        result = judge.agreement(model, human)
        self.assertEqual(result["overall"], (4, 4))

    def test_a_check_the_human_left_blank_is_not_counted(self):
        human = {"draft-1": {"evidence": "yes", "tone": "yes"}}
        model = {"draft-1": all_yes()}
        result = judge.agreement(model, human)
        self.assertEqual(result["per_check"]["evidence"], (1, 1))
        self.assertEqual(result["per_check"]["payload_fields"], (0, 0))
        self.assertEqual(result["overall"], (2, 2))

    def test_a_draft_the_judge_did_not_score_is_not_counted(self):
        human = {"draft-1": all_yes(), "draft-2": all_yes()}
        model = {"draft-1": all_yes()}
        self.assertEqual(judge.agreement(model, human)["overall"], (4, 4))

    def test_no_scores_at_all_gives_zero_over_zero(self):
        result = judge.agreement({}, {})
        self.assertEqual(result["overall"], (0, 0))
        self.assertEqual(result["per_check"]["evidence"], (0, 0))

    def test_percent_handles_an_empty_count(self):
        self.assertEqual(judge.percent((3, 4)), "75%")
        self.assertEqual(judge.percent((0, 0)), "n/a")


class ParseReplyTests(unittest.TestCase):
    def test_reads_the_checks_object(self):
        reply = '{"checks": {"evidence": "yes", "no_outside_facts": "no", "payload_fields": "yes", "tone": "yes"}}'
        self.assertEqual(judge.parse_reply(reply)["no_outside_facts"], "no")

    def test_reads_json_wrapped_in_a_code_fence_and_extra_words(self):
        reply = 'Here is my verdict:\n```json\n{"checks": {"evidence": "YES", "tone": "No"}}\n```\n'
        self.assertEqual(judge.parse_reply(reply), {"evidence": "yes", "tone": "no"})

    def test_ignores_unknown_checks_and_values_that_are_not_yes_or_no(self):
        reply = '{"checks": {"evidence": "maybe", "vibes": "yes", "tone": "yes"}}'
        self.assertEqual(judge.parse_reply(reply), {"tone": "yes"})

    def test_reads_the_verdict_when_the_notes_before_it_contain_braces(self):
        reply = (
            'The draft opens with {"shipment_id": "SHP-0082"} and has no category.\n'
            '{"checks": {"evidence": "yes", "payload_fields": "no"}}'
        )
        self.assertEqual(judge.parse_reply(reply), {"evidence": "yes", "payload_fields": "no"})

    def test_reads_the_verdict_when_a_note_after_it_contains_braces(self):
        reply = '{"checks": {"tone": "yes"}}\n(the {above} part is my verdict)'
        self.assertEqual(judge.parse_reply(reply), {"tone": "yes"})

    def test_uses_the_last_verdict_when_there_are_two(self):
        reply = '{"checks": {"tone": "no"}} On reflection: {"checks": {"tone": "yes"}}'
        self.assertEqual(judge.parse_reply(reply), {"tone": "yes"})

    def test_a_reply_with_no_json_gives_no_scores(self):
        self.assertEqual(judge.parse_reply("I could not decide."), {})


class ReadHumanScoresTests(unittest.TestCase):
    def write_csv(self, rows):
        folder = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(folder, ignore_errors=True))
        path = Path(folder) / "human_scores.csv"
        with path.open("w", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=["draft", *judge.CHECKS])
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_reads_filled_cells_and_skips_blank_ones(self):
        path = self.write_csv([
            {"draft": "draft-1", "evidence": "yes", "no_outside_facts": "no",
             "payload_fields": "", "tone": " YES "},
            {"draft": "draft-2", "evidence": "", "no_outside_facts": "",
             "payload_fields": "", "tone": ""},
        ])
        scores = judge.read_human_scores(path)
        self.assertEqual(scores["draft-1"], {"evidence": "yes", "no_outside_facts": "no", "tone": "yes"})
        self.assertNotIn("draft-2", scores)

    def test_the_shipped_template_is_blank_and_lists_every_draft(self):
        scores = judge.read_human_scores(ROOT / "evals/judge/human_scores.csv")
        self.assertEqual(scores, {})
        with (ROOT / "evals/judge/human_scores.csv").open(newline="", encoding="utf-8") as source:
            listed = [row["draft"] for row in csv.DictReader(source)]
        on_disk = sorted(path.stem for path in (ROOT / "evals/judge/drafts").glob("*.json"))
        self.assertEqual(sorted(listed), on_disk)
        self.assertEqual(len(listed), 8)


if __name__ == "__main__":
    unittest.main()
