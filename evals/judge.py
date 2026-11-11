"""Lab 12: run the claim-draft judge and measure how often it agrees with people.

    python evals/judge.py [--model sonnet]

Reads the drafts in evals/judge/drafts/ and your scores in
evals/judge/human_scores.csv. Runs `claude -p` once per draft with the rubric
in evals/judge/rubric.md, then prints agreement per check and overall.
"""

import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
JUDGE_DIR = ROOT / "evals" / "judge"
CHECKS = ("evidence", "no_outside_facts", "payload_fields", "tone")
ANSWERS = ("yes", "no")
TIMEOUT_SECONDS = 300


def percent(counts):
    agreed, total = counts
    return "n/a" if total == 0 else f"{round(100 * agreed / total)}%"


def parse_reply(text):
    """Pull the checks out of the judge's reply. Returns {check: "yes"|"no"}.

    The reply may have notes around the JSON, and the notes may contain braces
    of their own, so this reads the last JSON object that has a "checks" key.
    """
    decoder = json.JSONDecoder()
    checks = None
    for start, char in enumerate(text):
        if char != "{":
            continue
        try:
            data, _ = decoder.raw_decode(text, start)
        except ValueError:
            continue
        if isinstance(data, dict) and isinstance(data.get("checks"), dict):
            checks = data["checks"]
    if checks is None:
        return {}
    scores = {}
    for check in CHECKS:
        value = str(checks.get(check, "")).strip().lower()
        if value in ANSWERS:
            scores[check] = value
    return scores


def read_human_scores(path):
    """Read the people's scores. Blank cells, and drafts with no scores, are left out."""
    scores = {}
    with Path(path).open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            draft = (row.get("draft") or "").strip()
            cells = {}
            for check in CHECKS:
                value = (row.get(check) or "").strip().lower()
                if value in ANSWERS:
                    cells[check] = value
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
    with (ROOT / "data" / "reference" / "shipments.csv").open(newline="", encoding="utf-8") as source:
        record["shipment_rows"] = [row for row in csv.DictReader(source) if row["shipment_id"] == shipment_id]
    checked = record["excursion_check"]
    category = checked.get("product_category", "") if isinstance(checked, dict) else ""
    thresholds = json.loads((ROOT / "data" / "sop" / "thresholds.json").read_text(encoding="utf-8"))
    record["sop_allowance"] = thresholds["categories"].get(category)
    return record


def build_prompt(rubric, draft_text, record):
    return (
        f"{rubric}\n\n## Record\n\n```json\n{json.dumps(record, indent=2)}\n```\n\n"
        f"## Draft\n\n```json\n{draft_text}\n```\n"
    )


def run_judge(prompt, model=None):
    """One `claude -p` run. Returns the reply text, or "" if it failed."""
    command = os.environ.get("EVALS_CLAUDE") or shutil.which("claude") or "claude"
    args = [command, "-p", prompt, "--output-format", "json"]
    if model:
        args += ["--model", model]
    try:
        run = subprocess.run(args, capture_output=True, text=True, cwd=ROOT, timeout=TIMEOUT_SECONDS)
        return json.loads(run.stdout).get("result", "")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return ""


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the claim-draft judge and measure agreement with people.")
    parser.add_argument("--model", help="haiku, sonnet, or opus (default: the session default)")
    args = parser.parse_args(argv)

    rubric = (JUDGE_DIR / "rubric.md").read_text(encoding="utf-8")
    drafts = sorted((JUDGE_DIR / "drafts").glob("*.json"))
    human = read_human_scores(JUDGE_DIR / "human_scores.csv")
    if not human:
        print("No scores yet in evals/judge/human_scores.csv. Fill in yes or no for each draft first.")
        return 1

    judged = {}
    for path in drafts:
        draft_text = path.read_text(encoding="utf-8")
        try:
            payload = json.loads(draft_text)
        except ValueError:
            payload = {}
        reply = run_judge(build_prompt(rubric, draft_text, evidence_record(payload)), args.model)
        judged[path.stem] = parse_reply(reply)
        marks = " ".join(f"{check}={judged[path.stem].get(check, '?')}" for check in CHECKS)
        print(f"{path.stem}: {marks}")

    result = agreement(judged, human)
    print()
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
            if mine and theirs and mine != theirs:
                disagreements.append(f"{draft} {check}: you said {mine}, the judge said {theirs}")
    if disagreements:
        print()
        print("Where it disagrees:")
        for line in disagreements:
            print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
