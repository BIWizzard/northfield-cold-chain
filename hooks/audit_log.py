"""Append a brief record of each tool call without interrupting the session."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys


def main():
    try:
        event = json.load(sys.stdin)
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
            "tool_name": tool_name,
            "tool_use_id": event["tool_use_id"],
            "summary": summary,
        }
        project = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
        with (project / "audit.jsonl").open("a", encoding="utf-8") as destination:
            destination.write(json.dumps(record) + "\n")
    except Exception:
        # Logging must never prevent the tool session from continuing.
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
