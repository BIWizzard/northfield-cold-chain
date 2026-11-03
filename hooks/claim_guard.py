"""Block claim commands whose payload lacks the required evidence."""

import csv
import json
import os
from pathlib import Path
import sys

from claim_call import find_claim_call, read_event


def block(reason):
    """Stop the tool call. Claude reads the reason, so say what to fix."""
    print(" ".join(reason.splitlines()), file=sys.stderr)
    raise SystemExit(2)


def project_path(project, value):
    """Resolve a path from the payload against the project folder."""
    return project / Path(value.replace("\\", "/"))


def main():
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    try:
        event = read_event()
    except (ValueError, OSError):
        block("Provide a valid JSON hook event on stdin.")

    # claim_call.py decides whether this command runs the claim tool.
    found = find_claim_call(event, project)
    if found is None:
        return 0
    if found[0] == "block":
        block(found[1])
    payload_file = found[1]

    # Lab 7: each check that fails calls block() with the one-line reason shown.

    # 1. payload_file exists and parses as a JSON object.
    try:
        payload = json.loads(payload_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        block(f"Create a readable, valid JSON payload at {payload_file} before filing.")
    if not isinstance(payload, dict):
        block("Write the claim payload as a JSON object.")

    # 2. Its shipment_id is set and is in exactly one row of shipments.csv.
    shipment_id = payload.get("shipment_id")
    if not isinstance(shipment_id, str) or not shipment_id:
        block("Set shipment_id to an ID in data/reference/shipments.csv.")
    try:
        with project_path(project, "data/reference/shipments.csv").open(newline="", encoding="utf-8") as source:
            rows = [row for row in csv.DictReader(source) if row.get("shipment_id") == shipment_id]
    except (OSError, UnicodeError, csv.Error):
        block("Restore readable shipment data at data/reference/shipments.csv.")
    if len(rows) != 1:
        block(f"Resolve shipment_id {shipment_id}: expected one shipment row, found {len(rows)}.")

    # 3. Its logger_file is set, equals that row's logger_file, and exists.
    logger_file = payload.get("logger_file")
    if not isinstance(logger_file, str) or not logger_file:
        block("Set logger_file to the shipment row's logger_file.")
    if logger_file != rows[0].get("logger_file"):
        block("Set logger_file to exactly the value in the matching shipment row.")
    try:
        logger_exists = project_path(project, logger_file).is_file()
    except (OSError, ValueError):
        logger_exists = False
    if not logger_exists:
        block(f"Restore the logger evidence file at {logger_file} before filing.")

    # 4. Its disposition is "hold" or "reject".
    if payload.get("disposition") not in ("hold", "reject"):
        block("Set disposition to hold or reject; release shipments cannot be claimed.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
