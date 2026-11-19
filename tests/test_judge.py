"""Checks for the shared judge call (graders.run_judge) and the Lab 12 judge (evals/judge.py)."""

import csv
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
# Import the modules the way `python evals/judge.py` does, with evals/ on the import path.
sys.path.insert(0, str(ROOT / "evals"))

import graders  # noqa: E402
import judge  # noqa: E402


def all_yes():
    return {check: True for check in judge.CHECKS}


def reply(checks):
    """What `claude -p --output-format json` prints when the judge answers `checks`."""
    return json.dumps({"result": json.dumps({"checks": checks})})


def completed(stdout="", returncode=0, stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class ParseChecksTests(unittest.TestCase):
    def test_reads_yes_and_no_as_booleans(self):
        text = '{"checks": {"evidence": "yes", "no_outside_facts": "no", "payload_fields": "yes", "tone": "yes"}}'
        self.assertEqual(
            graders.parse_checks(text),
            {"evidence": True, "no_outside_facts": False, "payload_fields": True, "tone": True},
        )

    def test_reads_json_wrapped_in_a_code_fence_and_extra_words(self):
        text = 'Here is my verdict:\n```json\n{"checks": {"evidence": "YES", "tone": "No"}}\n```\n'
        self.assertEqual(graders.parse_checks(text), {"evidence": True, "tone": False})

    def test_reads_the_verdict_when_the_notes_before_it_contain_braces(self):
        text = (
            'The draft opens with {"shipment_id": "SHP-0082"} and has no category.\n'
            '{"checks": {"evidence": "yes", "payload_fields": "no"}}'
        )
        self.assertEqual(graders.parse_checks(text), {"evidence": True, "payload_fields": False})

    def test_reads_the_verdict_when_a_note_after_it_contains_braces(self):
        text = '{"checks": {"tone": "yes"}}\n(the {above} part is my verdict)'
        self.assertEqual(graders.parse_checks(text), {"tone": True})

    def test_uses_the_last_verdict_when_there_are_two(self):
        text = '{"checks": {"tone": "no"}} On reflection: {"checks": {"tone": "yes"}}'
        self.assertEqual(graders.parse_checks(text), {"tone": True})

    def test_keeps_every_check_the_judge_named(self):
        text = '{"checks": {"evidence": "yes", "vibes": "no"}}'
        self.assertEqual(graders.parse_checks(text), {"evidence": True, "vibes": False})

    def test_a_reply_with_no_json_is_an_error(self):
        with self.assertRaises(graders.JudgeError):
            graders.parse_checks("I could not decide.")

    def test_a_reply_with_no_checks_is_an_error(self):
        with self.assertRaises(graders.JudgeError):
            graders.parse_checks('{"checks": {}}')

    def test_an_answer_that_is_not_yes_or_no_is_an_error_that_names_the_check(self):
        with self.assertRaises(graders.JudgeError) as caught:
            graders.parse_checks('{"checks": {"evidence": "maybe", "tone": "yes"}}')
        self.assertIn("evidence", str(caught.exception))


class RunJudgeTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(folder, ignore_errors=True))
        self.rubric = Path(folder) / "rubric.md"
        self.rubric.write_text("RUBRIC TEXT: answer yes or no.", encoding="utf-8")
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("EVALS_CLAUDE", None)

    def run_judge(self, stdout=None, **kwargs):
        stdout = reply({"evidence": "yes", "tone": "no"}) if stdout is None else stdout
        with mock.patch("graders.subprocess.run", return_value=completed(stdout)) as run:
            result = graders.run_judge(self.rubric, "THE TEXT TO GRADE", **kwargs)
        return result, run

    def test_returns_each_check_as_a_boolean(self):
        result, _ = self.run_judge()
        self.assertEqual(result, {"evidence": True, "tone": False})

    def test_calls_claude_with_p_and_json_output_and_no_project_settings(self):
        with mock.patch("graders.shutil.which", return_value="/usr/bin/claude"):
            _, run = self.run_judge()
        args = run.call_args.args[0]
        self.assertEqual(args[0], "/usr/bin/claude")
        self.assertEqual(args[1], "-p")
        self.assertEqual(args[3:], ["--output-format", "json"])
        self.assertNotIn("--settings", args)

    def test_the_prompt_holds_the_rubric_and_the_text(self):
        _, run = self.run_judge()
        prompt = run.call_args.args[0][2]
        self.assertIn("RUBRIC TEXT: answer yes or no.", prompt)
        self.assertIn("THE TEXT TO GRADE", prompt)
        self.assertLess(prompt.index("RUBRIC TEXT"), prompt.index("THE TEXT TO GRADE"))

    def test_passes_the_model_only_when_one_is_given(self):
        _, without = self.run_judge()
        self.assertNotIn("--model", without.call_args.args[0])
        _, with_model = self.run_judge(model="haiku")
        args = with_model.call_args.args[0]
        self.assertEqual(args[args.index("--model") + 1], "haiku")

    def test_evals_claude_names_the_command(self):
        os.environ["EVALS_CLAUDE"] = "/tmp/fake-claude"
        _, run = self.run_judge()
        self.assertEqual(run.call_args.args[0][0], "/tmp/fake-claude")

    def test_falls_back_to_plain_claude_when_it_is_not_on_the_path(self):
        with mock.patch("graders.shutil.which", return_value=None):
            _, run = self.run_judge()
        self.assertEqual(run.call_args.args[0][0], "claude")

    def test_runs_from_an_empty_folder_outside_the_repo_so_no_project_hooks_fire(self):
        seen = {}

        def fake_run(args, **kwargs):
            cwd = Path(kwargs["cwd"])
            seen["inside_repo"] = ROOT in [cwd, *cwd.parents]
            seen["contents"] = os.listdir(cwd)
            return completed(reply({"evidence": "yes"}))

        with mock.patch("graders.subprocess.run", side_effect=fake_run) as run:
            graders.run_judge(self.rubric, "THE TEXT TO GRADE")
        self.assertFalse(seen["inside_repo"])
        self.assertEqual(seen["contents"], [])
        self.assertFalse(Path(run.call_args.kwargs["cwd"]).exists(), "the folder is removed afterwards")

    def test_a_temp_folder_that_cannot_be_removed_does_not_fail_the_call(self):
        # On Windows the folder can still be in use for a moment after claude exits.
        real = tempfile.TemporaryDirectory
        with mock.patch("graders.tempfile.TemporaryDirectory", side_effect=real) as make:
            self.run_judge()
        self.assertTrue(make.call_args.kwargs.get("ignore_cleanup_errors"))

    def test_uses_a_300_second_timeout_by_default(self):
        _, run = self.run_judge()
        self.assertEqual(run.call_args.kwargs["timeout"], 300)
        _, custom = self.run_judge(timeout=45)
        self.assertEqual(custom.call_args.kwargs["timeout"], 45)

    def test_a_timeout_is_an_error(self):
        with mock.patch("graders.subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 300)):
            with self.assertRaises(graders.JudgeError):
                graders.run_judge(self.rubric, "text")

    def test_a_missing_claude_is_an_error(self):
        with mock.patch("graders.subprocess.run", side_effect=FileNotFoundError("claude")):
            with self.assertRaises(graders.JudgeError):
                graders.run_judge(self.rubric, "text")

    def test_output_that_is_not_json_is_an_error(self):
        with mock.patch("graders.subprocess.run", return_value=completed("not json", returncode=1, stderr="boom")):
            with self.assertRaises(graders.JudgeError):
                graders.run_judge(self.rubric, "text")

    def test_an_error_result_is_an_error(self):
        stdout = json.dumps({"is_error": True, "result": "Not logged in"})
        with self.assertRaises(graders.JudgeError) as caught:
            self.run_judge(stdout=stdout)
        self.assertIn("Not logged in", str(caught.exception))

    def test_a_reply_without_checks_is_an_error(self):
        with self.assertRaises(graders.JudgeError):
            self.run_judge(stdout=json.dumps({"result": "Looks fine to me."}))


class AgreementTests(unittest.TestCase):
    def test_identical_scores_agree_everywhere(self):
        scores = {"draft-1": all_yes(), "draft-2": all_yes()}
        result = judge.agreement(scores, scores)
        for check in judge.CHECKS:
            self.assertEqual(result["per_check"][check], (2, 2))
        self.assertEqual(result["overall"], (8, 8))

    def test_one_disagreement_lowers_one_check_and_the_overall(self):
        human = {"draft-1": all_yes(), "draft-2": all_yes()}
        model = {"draft-1": all_yes(), "draft-2": {**all_yes(), "tone": False}}
        result = judge.agreement(model, human)
        self.assertEqual(result["per_check"]["tone"], (1, 2))
        self.assertEqual(result["per_check"]["evidence"], (2, 2))
        self.assertEqual(result["overall"], (7, 8))

    def test_a_draft_the_human_left_blank_is_not_counted(self):
        human = {"draft-1": all_yes()}
        model = {"draft-1": all_yes(), "draft-2": {check: False for check in judge.CHECKS}}
        result = judge.agreement(model, human)
        self.assertEqual(result["overall"], (4, 4))

    def test_a_check_the_human_left_blank_is_not_counted(self):
        human = {"draft-1": {"evidence": True, "tone": True}}
        model = {"draft-1": all_yes()}
        result = judge.agreement(model, human)
        self.assertEqual(result["per_check"]["evidence"], (1, 1))
        self.assertEqual(result["per_check"]["payload_fields"], (0, 0))
        self.assertEqual(result["overall"], (2, 2))

    def test_a_draft_the_judge_did_not_score_is_not_counted(self):
        human = {"draft-1": all_yes(), "draft-2": all_yes()}
        model = {"draft-1": all_yes()}
        self.assertEqual(judge.agreement(model, human)["overall"], (4, 4))

    def test_a_draft_whose_judge_call_failed_is_not_counted(self):
        human = {"draft-1": all_yes()}
        self.assertEqual(judge.agreement({"draft-1": {}}, human)["overall"], (0, 0))

    def test_no_scores_at_all_gives_zero_over_zero(self):
        result = judge.agreement({}, {})
        self.assertEqual(result["overall"], (0, 0))
        self.assertEqual(result["per_check"]["evidence"], (0, 0))

    def test_percent_handles_an_empty_count(self):
        self.assertEqual(judge.percent((3, 4)), "75%")
        self.assertEqual(judge.percent((0, 0)), "n/a")


class ReadHumanScoresTests(unittest.TestCase):
    def write_csv(self, rows):
        folder = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(folder, ignore_errors=True))
        path = Path(folder) / "human_scores.csv"
        with path.open("w", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=["draft", *judge.CHECKS])
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_reads_filled_cells_as_booleans_and_skips_blank_ones(self):
        path = self.write_csv([
            {"draft": "draft-1", "evidence": "yes", "no_outside_facts": "no",
             "payload_fields": "", "tone": " YES "},
            {"draft": "draft-2", "evidence": "", "no_outside_facts": "",
             "payload_fields": "", "tone": ""},
        ])
        scores = judge.read_human_scores(path)
        self.assertEqual(scores["draft-1"], {"evidence": True, "no_outside_facts": False, "tone": True})
        self.assertNotIn("draft-2", scores)

    def test_the_shipped_template_is_blank_and_lists_every_draft(self):
        scores = judge.read_human_scores(ROOT / "evals/judge/human_scores.csv")
        self.assertEqual(scores, {})
        with (ROOT / "evals/judge/human_scores.csv").open(newline="", encoding="utf-8") as source:
            listed = [row["draft"] for row in csv.DictReader(source)]
        on_disk = sorted(path.stem for path in (ROOT / "evals/judge/drafts").glob("*.json"))
        self.assertEqual(sorted(listed), on_disk)
        self.assertEqual(len(listed), 8)


class ScoreDraftsTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(folder, ignore_errors=True))
        self.drafts = Path(folder)
        payload = {"shipment_id": "SHP-0185", "summary": "A short claim."}
        for name in ("draft-1", "draft-2"):
            (self.drafts / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")
        self.rubric = Path(folder) / "rubric.md"
        self.rubric.write_text("rubric", encoding="utf-8")

    @mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_scores_each_draft_through_the_shared_judge_call(self, _stdout):
        with mock.patch("graders.run_judge", return_value=all_yes()) as run:
            scores = judge.score_drafts(sorted(self.drafts.glob("*.json")), self.rubric, "haiku")
        self.assertEqual(scores, {"draft-1": all_yes(), "draft-2": all_yes()})
        self.assertEqual(run.call_count, 2)
        first = run.call_args_list[0]
        self.assertEqual(first.args[0], self.rubric)
        self.assertEqual(first.kwargs.get("model"), "haiku")
        text = first.args[1]
        self.assertIn("A short claim.", text)
        self.assertIn("SHP-0185", text)

    @mock.patch("sys.stdout", new_callable=io.StringIO)
    @mock.patch("sys.stderr", new_callable=io.StringIO)
    def test_a_failed_judge_call_scores_nothing_for_that_draft_and_the_rest_carry_on(self, stderr, _stdout):
        outcomes = [graders.JudgeError("timed out"), all_yes()]
        with mock.patch("graders.run_judge", side_effect=outcomes):
            scores = judge.score_drafts(sorted(self.drafts.glob("*.json")), self.rubric, None)
        self.assertEqual(scores, {"draft-1": {}, "draft-2": all_yes()})
        self.assertIn("timed out", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
