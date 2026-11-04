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

    # TODO 1: payload_file exists and parses as a JSON object.
    #   "Create a readable, valid JSON payload at <payload_file> before filing."
    #   "Write the claim payload as a JSON object."

    # TODO 2: Its shipment_id is set and is in exactly one row of shipments.csv.
    #   "Set shipment_id to an ID in data/reference/shipments.csv."
    #   "Resolve shipment_id <id>: expected one shipment row, found <n>."

    # TODO 3: Its logger_file is set, equals that row's logger_file, and exists.
    #   "Set logger_file to the shipment row's logger_file."
    #   "Set logger_file to exactly the value in the matching shipment row."
    #   "Restore the logger evidence file at <logger_file> before filing."

    # TODO 4: Its disposition is "hold" or "reject".
    #   "Set disposition to hold or reject; release shipments cannot be claimed."

    return 0


if __name__ == "__main__":
    sys.exit(main())
