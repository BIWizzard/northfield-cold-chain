"""Block claim commands whose payload lacks the required evidence."""

import csv
import json
import os
from pathlib import Path
import re
import sys


def block(reason):
    print(" ".join(reason.splitlines()), file=sys.stderr)
    raise SystemExit(2)


def payload_path(command):
    """Read either payload option form without consuming Windows backslashes."""
    match = re.search(
        r'''(?:^|\s)--payload(?:=|\s+)(?:"([^"]*)"|'([^']*)'|([^\s'";|&]+))''',
        command,
    )
    if match:
        value = next(part for part in match.groups() if part is not None)
        if value and not value.startswith("--"):
            return value
    return None


def project_path(project, value):
    return project / Path(value.replace("\\", "/"))


def main():
    try:
        event = json.load(sys.stdin)
    except (ValueError, OSError):
        block("Provide a valid JSON hook event on stdin.")
    if not isinstance(event, dict):
        block("Provide a JSON object as the hook event.")
    if event.get("tool_name") not in ("Bash", "PowerShell"):
        return 0
    tool_input = event.get("tool_input", {})
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not isinstance(command, str) or not re.search(
        r'''(?:^|[\s/\\'"])carrier_claim_api\.py(?=$|[\s'";|&])''', command
    ):
        return 0

    path = payload_path(command)
    if path is None:
        block("Supply --payload <path> with a claim JSON file.")
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    try:
        payload = json.loads(project_path(project, path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        block(f"Create a readable, valid JSON payload at {path} before filing.")
    if not isinstance(payload, dict):
        block("Write the claim payload as a JSON object.")

    shipment_id = payload.get("shipment_id")
    if not isinstance(shipment_id, str) or not shipment_id:
        block("Set shipment_id to an ID in data/reference/shipments.csv.")
    try:
        with (project / "data/reference/shipments.csv").open(newline="", encoding="utf-8") as source:
            rows = [row for row in csv.DictReader(source) if row.get("shipment_id") == shipment_id]
    except (OSError, UnicodeError, csv.Error):
        block("Restore readable shipment data at data/reference/shipments.csv.")
    if len(rows) != 1:
        block(f"Resolve shipment_id {shipment_id}: expected one shipment row, found {len(rows)}.")

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
    if payload.get("disposition") not in ("hold", "reject"):
        block("Set disposition to hold or reject; release shipments cannot be claimed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
