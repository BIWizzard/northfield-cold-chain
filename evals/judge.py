"""Lab 12: run the claim-draft judge and measure how often it agrees with people.

    python evals/judge.py [--model sonnet]

Reads the drafts in evals/judge/drafts/ and your scores in
evals/judge/human_scores.csv. Sends each draft to the judge with the rubric in
evals/judge/rubric.md (one `claude -p` run per draft, through graders.run_judge),
then prints agreement per check and overall.
"""

import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys

import graders

ROOT = Path(__file__).resolve().parents[1]
JUDGE_DIR = ROOT / "evals" / "judge"
CHECKS = ("evidence", "no_outside_facts", "payload_fields", "tone")
ANSWERS = {"yes": True, "no": False}


def percent(counts):
    agreed, total = counts
    return "n/a" if total == 0 else f"{round(100 * agreed / total)}%"


def label(value):
    return "?" if value is None else ("yes" if value else "no")


def read_human_scores(path):
    """Read the people's scores as {draft: {check: True or False}}.

    Blank cells, and drafts with no scores, are left out.
    """
    scores = {}
    with Path(path).open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            draft = (row.get("draft") or "").strip()
            cells = {}
            for check in CHECKS:
                value = (row.get(check) or "").strip().lower()
                if value in ANSWERS:
                    cells[check] = ANSWERS[value]
            if draft and cells:
                scores[draft] = cells
    return scores


def agreement(judge_scores, human_scores):
    """Count agreeing cells per check and overall as (agreed, total) pairs.

    A cell counts only when both the judge and a person scored it.
    """
    per_check = {check: [0, 0] for check in CHECKS}
    for draft, human in human_scores.items():
        model = judge_scores.get(draft, {})
        for check in CHECKS:
            if check in human and check in model:
                per_check[check][1] += 1
                if human[check] == model[check]:
                    per_check[check][0] += 1
    per_check = {check: tuple(counts) for check, counts in per_check.items()}
    overall = (sum(c[0] for c in per_check.values()), sum(c[1] for c in per_check.values()))
    return {"per_check": per_check, "overall": overall}


def evidence_record(payload):
    """The facts the judge may rely on: the checker's numbers, the CSV row, the allowance."""
    shipment_id = payload.get("shipment_id", "") if isinstance(payload, dict) else ""
    record = {"shipment_id": shipment_id}
    try:
        run = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "excursion_check.py"), shipment_id],
            capture_output=True, text=True, cwd=ROOT, timeout=60,
        )
        record["excursion_check"] = json.loads(run.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        record["excursion_check"] = "unavailable"
        print(f"{shipment_id}: tools/excursion_check.py gave no result; the judge has a thin record.",
              file=sys.stderr)
    with (ROOT / "data" / "reference" / "shipments.csv").open(newline="", encoding="utf-8") as source:
        record["shipment_rows"] = [row for row in csv.DictReader(source) if row["shipment_id"] == shipment_id]
    checked = record["excursion_check"]
    category = checked.get("product_category", "") if isinstance(checked, dict) else ""
    thresholds = json.loads((ROOT / "data" / "sop" / "thresholds.json").read_text(encoding="utf-8"))
    record["sop_allowance"] = thresholds["categories"].get(category)
    return record


def build_text(draft_text, record):
    """What the judge is shown besides the rubric: the record to check against, then the draft."""
    return (
        f"## Record\n\n```json\n{json.dumps(record, indent=2)}\n```\n\n"
        f"## Draft\n\n```json\n{draft_text}\n```"
    )


def score_drafts(drafts, rubric_path, model=None):
    """Judge each draft file. Returns {draft: {check: True or False}}.

    A draft whose judge call fails gets {} (nothing to compare), and the rest carry on.
    """
    scores = {}
    for path in drafts:
        draft_text = path.read_text(encoding="utf-8")
        try:
            payload = json.loads(draft_text)
        except ValueError:
            payload = {}
        try:
            scores[path.stem] = graders.run_judge(
                rubric_path, build_text(draft_text, evidence_record(payload)), model=model,
                expected=CHECKS,
            )
        except graders.JudgeError as error:
            scores[path.stem] = {}
            print(f"{path.stem}: the judge call failed: {error}", file=sys.stderr)
        marks = " ".join(f"{check}={label(scores[path.stem].get(check))}" for check in CHECKS)
        print(f"{path.stem}: {marks}")
    return scores


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the claim-draft judge and measure agreement with people.")
    parser.add_argument("--model", help="haiku, sonnet, or opus (default: the session default)")
    args = parser.parse_args(argv)

    drafts = sorted((JUDGE_DIR / "drafts").glob("*.json"))
    human = read_human_scores(JUDGE_DIR / "human_scores.csv")
    if not human:
        print("No scores yet in evals/judge/human_scores.csv. Fill in yes or no for each draft first.")
        return 1

    judged = score_drafts(drafts, JUDGE_DIR / "rubric.md", args.model)

    result = agreement(judged, human)
    answered = sum(1 for checks in judged.values() if checks)
    print()
    print(f"{answered} of {len(judged)} drafts judged.")
    print("Agreement with your scores:")
    for check in CHECKS:
        agreed, total = result["per_check"][check]
        print(f"  {check:<18} {percent((agreed, total)):>4}  ({agreed}/{total})")
    agreed, total = result["overall"]
    print(f"  {'overall':<18} {percent((agreed, total)):>4}  ({agreed}/{total})")

    disagreements = []
    for draft in sorted(human):
        for check in CHECKS:
            mine = human[draft].get(check)
            theirs = judged.get(draft, {}).get(check)
            if mine is not None and theirs is not None and mine != theirs:
                disagreements.append(f"{draft} {check}: you said {label(mine)}, the judge said {label(theirs)}")
    if disagreements:
        print()
        print("Where it disagrees:")
        for line in disagreements:
            print(f"  {line}")
    return 0 if answered == len(judged) else 1


if __name__ == "__main__":
    sys.exit(main())
