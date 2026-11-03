"""Block claim commands whose payload lacks the required evidence."""

import csv
import json
import os
from pathlib import Path
import re
import shlex
import sys


CLAIM_TOOL = "carrier_claim_api.py"
# Anything that lets one command line run more than one command.
CHAIN_MARKERS = (";", "&", "|", "`", "$(", "<(", ">(", "\n", "\r")
INTERPRETER = re.compile(r"(python[0-9.]*|pythonw|py)(\.exe)?")


def block(reason):
    """Stop the tool call. Claude reads the reason, so say what to fix."""
    print(" ".join(reason.splitlines()), file=sys.stderr)
    raise SystemExit(2)


def names(token):
    """Lowercased file names in a token, split on any shell operator stuck to it."""
    pieces = re.split(r"[;&|`()<>\n\r]", token.replace("\\", "/"))
    return [piece.rsplit("/", 1)[-1].lower() for piece in pieces if piece]


def is_payload_option(token):
    """True for --payload, --payload=..., and the short forms argparse accepts."""
    option = token.split("=", 1)[0]
    return len(option) >= 3 and "--payload".startswith(option)


def claim_arguments(event):
    """Return the arguments after the claim tool, or None if the command doesn't run it."""
    tool_input = event.get("tool_input")
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not isinstance(command, str):
        return None
    text = command.replace("\\", "/") if event.get("tool_name") == "PowerShell" else command
    try:
        tokens = shlex.split(text, posix=True)
    except ValueError:
        if "carrier_claim_api" in command.lower():
            block("Write the claim command with balanced quotes.")
        return None

    calls = [
        index for index, token in enumerate(tokens)
        if CLAIM_TOOL in names(token)
        and (
            any(INTERPRETER.fullmatch(name) for before in tokens[:index] for name in names(before))
            or any(is_payload_option(after) for after in tokens[index + 1:])
        )
    ]
    if not calls:
        return None
    if any(marker in command for marker in CHAIN_MARKERS):
        block("Run the claim tool on its own, not chained with other commands.")
    if len(calls) > 1:
        block("Run the claim tool once per command.")
    return tokens[calls[0] + 1:]


def payload_path(arguments):
    """Return the one --payload value, or None if there isn't a usable one."""
    values = []
    for index, token in enumerate(arguments):
        if not is_payload_option(token):
            continue
        if "=" in token:
            values.append(token.split("=", 1)[1])
        else:
            values.append(arguments[index + 1] if index + 1 < len(arguments) else "")
    if len(values) > 1:
        block("Give exactly one --payload option.")
    if not values or not values[0] or values[0].startswith("-"):
        return None
    return values[0]


def project_path(folder, value):
    """Resolve a path from the payload or command against a folder."""
    return folder / Path(value.replace("\\", "/"))


def main():
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (ValueError, OSError):
        block("Provide a valid JSON hook event on stdin.")
    if not isinstance(event, dict):
        block("Provide a JSON object as the hook event.")

    # Only shell commands that run the claim tool are checked.
    if event.get("tool_name") not in ("Bash", "PowerShell"):
        return 0
    arguments = claim_arguments(event)
    if arguments is None:
        return 0

    path = payload_path(arguments)
    if path is None:
        block("Supply --payload <path> with a claim JSON file.")
    # Data files live in the project folder. The claim tool opens the payload
    # from the folder the command runs in, so the payload resolves from there.
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    cwd = event.get("cwd")
    working = Path(cwd) if isinstance(cwd, str) and cwd else project

    # Lab 7: the four checks below run in order. Each one that fails calls
    # block() with a one-line reason. Resolve the payload with
    # project_path(working, path) and data files with project_path(project, ...).

    # 1. The payload file exists and parses as a JSON object.
    try:
        payload = json.loads(project_path(working, path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        block(f"Create a readable, valid JSON payload at {path} before filing.")
    if not isinstance(payload, dict):
        block("Write the claim payload as a JSON object.")

    # 2. The payload's shipment_id appears in exactly one row of
    #   data/reference/shipments.csv. No rows and several rows both fail.
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

    # 3. The payload's logger_file is set, is exactly the logger_file on
    #   that shipment row, and the file exists.
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

    # 4. The payload's disposition is "hold" or "reject".
    if payload.get("disposition") not in ("hold", "reject"):
        block("Set disposition to hold or reject; release shipments cannot be claimed.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
