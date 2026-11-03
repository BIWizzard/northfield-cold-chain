"""Append a brief record of each tool call without interrupting the session."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys


def main():
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        project = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))

        # Lab 7: complete the two steps below.

        # 1. Build a record with these five fields:
        #   timestamp    the current time in UTC, ISO-8601, ending in "Z"
        #   event        the event's hook_event_name (PostToolUse or PostToolUseFailure)
        #   tool_name    from the event
        #   tool_use_id  from the event
        #   summary      for Bash or PowerShell, the command;
        #                for Read, Write, or Edit, the file_path;
        #                for any other tool, tool_input as compact JSON,
        #                cut to 200 characters
        tool_name = event["tool_name"]
        tool_input = event["tool_input"]
        if tool_name in ("Bash", "PowerShell"):
            summary = tool_input["command"]
        elif tool_name in ("Read", "Write", "Edit"):
            summary = tool_input["file_path"]
        else:
            summary = json.dumps(tool_input, separators=(",", ":"))[:200]
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "event": event["hook_event_name"],
            "tool_name": tool_name,
            "tool_use_id": event["tool_use_id"],
            "summary": summary,
        }

        # 2. Append the record to audit.jsonl in the project folder,
        #   as one line of JSON. Keep the lines already there.
        with (project / "audit.jsonl").open("a", encoding="utf-8") as destination:
            destination.write(json.dumps(record) + "\n")

    except Exception as exc:
        # Logging must never stop the session: report the problem and carry on.
        print(f"audit_log: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
