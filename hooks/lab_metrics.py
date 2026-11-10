"""Stop hook: record the session's elapsed time and token totals in metrics.jsonl.

Claude Code runs this each time Claude finishes a response. It reads the session
transcript, totals the main session, and appends one line to metrics.jsonl in the
project folder. Each line holds the running totals for its session, so the last
line for a session is the latest.

Standard library only. It never interrupts the session: every problem is reported
on stderr and the exit code is always 0 (exit 2 on a Stop hook would keep Claude
from finishing).
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys


TOKEN_FIELDS = (
    ("input_tokens", "input_tokens"),
    ("output_tokens", "output_tokens"),
    ("cache_creation_tokens", "cache_creation_input_tokens"),
    ("cache_read_tokens", "cache_read_input_tokens"),
)


def parse_timestamp(value):
    """Return an aware datetime for an ISO-8601 string, or None if it is not one."""
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def count_tokens(usage):
    """Return the four token counts from a usage block, with anything unusable as 0."""
    counts = {}
    for name, source in TOKEN_FIELDS:
        value = usage.get(source) if isinstance(usage, dict) else None
        counts[name] = value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0
    return counts


def parse_transcript(path):
    """Total the main session in a transcript file.

    Counts only the main session: entries flagged isSidechain are skipped, so a
    subagent's tokens are not included. The same message can appear on several
    lines, so each message id is counted once. Lines that are not valid JSON,
    including a half-written last line, are skipped. The transcript format is
    internal to Claude Code, so anything unexpected is ignored, not fatal.

    Raises OSError if the file cannot be read.
    """
    messages = {}  # message id -> token counts
    first = last = None
    with open(path, "rb") as source:
        for raw in source:
            try:
                entry = json.loads(raw.decode("utf-8", errors="replace"))
            except ValueError:
                continue
            if not isinstance(entry, dict) or entry.get("isSidechain"):
                continue
            if entry.get("type") not in ("user", "assistant"):
                continue
            stamp = parse_timestamp(entry.get("timestamp"))
            if stamp:
                first = stamp if first is None or stamp < first else first
                last = stamp if last is None or stamp > last else last
            message = entry.get("message")
            if entry["type"] != "assistant" or not isinstance(message, dict):
                continue
            message_id = message.get("id")
            if not isinstance(message_id, str) or not isinstance(message.get("usage"), dict):
                continue
            counts = count_tokens(message["usage"])
            seen = messages.setdefault(message_id, counts)
            for name in counts:
                seen[name] = max(seen[name], counts[name])
    totals = {name: sum(counts[name] for counts in messages.values()) for name, _ in TOKEN_FIELDS}
    # Cohort ranking uses input + output + cache writes; cache reads are informational only.
    totals["total_tokens"] = (
        totals["input_tokens"]
        + totals["output_tokens"]
        + totals["cache_creation_tokens"]
    )
    totals["messages"] = len(messages)
    totals["minutes"] = round((last - first).total_seconds() / 60, 2) if first and last else 0.0
    return totals


def main():
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        totals = parse_transcript(event["transcript_path"])
        project = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "session_id": event["session_id"],
            "transcript_path": event["transcript_path"],
            **totals,
        }
        with (project / "metrics.jsonl").open("a", encoding="utf-8") as destination:
            destination.write(json.dumps(record) + "\n")
    except Exception as exc:
        # Metrics must never stop the session: report the problem and carry on.
        print(f"lab_metrics: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
