"""Block claim commands whose payload lacks the required evidence."""

import csv
import json
import os
from pathlib import Path
import re
import sys


def block(reason):
    """Stop the tool call. Claude reads the reason, so say what to fix."""
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
    """Resolve a path from the payload or command against the project folder."""
    return project / Path(value.replace("\\", "/"))


def main():
    try:
        event = json.load(sys.stdin)
    except (ValueError, OSError):
        block("Provide a valid JSON hook event on stdin.")
    if not isinstance(event, dict):
        block("Provide a JSON object as the hook event.")

    # Only shell commands that call the claim tool are checked.
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

    # Lab 7: complete the four checks below, in order. Each one that fails
    # calls block() with a one-line reason. Resolve file paths with
    # project_path(project, ...), so relative and Windows paths both work.

    # TODO 1: The payload file at `path` exists and parses as a JSON object.
    #   If not: "Create a readable, valid JSON payload at <path> before filing."

    # TODO 2: The payload's shipment_id appears in exactly one row of
    #   data/reference/shipments.csv. No rows and several rows both fail.
    #   If not: "Resolve shipment_id <id>: expected one shipment row, found <n>."

    # TODO 3: The payload's logger_file is set, is exactly the logger_file on
    #   that shipment row, and the file exists.
    #   If not: "Set logger_file to exactly the value in the matching shipment row."
    #   or: "Restore the logger evidence file at <logger_file> before filing."

    # TODO 4: The payload's disposition is "hold" or "reject".
    #   If not: "Set disposition to hold or reject; release shipments cannot be claimed."

    return 0


if __name__ == "__main__":
    sys.exit(main())
