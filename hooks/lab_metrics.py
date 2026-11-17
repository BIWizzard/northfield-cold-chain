"""Stop hook: record the session's elapsed time and token totals in metrics.jsonl.

Claude Code runs this each time Claude finishes a response. It reads the session
transcript, totals the main session and every subagent that belongs to it, and
appends one line to metrics.jsonl in the project folder. Each line holds the running totals for its session, so the last
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


def read_entries(path):
    """Yield each JSON object in a transcript file, skipping lines that are not one.

    Lines that are not valid JSON, including a half-written last line, are skipped.
    Raises OSError if the file cannot be read.
    """
    with open(path, "rb") as source:
        for raw in source:
            try:
                entry = json.loads(raw.decode("utf-8", errors="replace"))
            except ValueError:
                continue
            if isinstance(entry, dict):
                yield entry


def add_message(messages, entry):
    """Record an assistant entry's token counts under its message id.

    The same message can appear on several lines, so each id is counted once,
    keeping the largest count seen for each kind.
    """
    message = entry.get("message")
    if entry.get("type") != "assistant" or not isinstance(message, dict):
        return
    message_id = message.get("id")
    if not isinstance(message_id, str) or not isinstance(message.get("usage"), dict):
        return
    counts = count_tokens(message["usage"])
    seen = messages.setdefault(message_id, counts)
    for name in counts:
        seen[name] = max(seen[name], counts[name])


def sum_messages(messages):
    totals = {name: sum(counts[name] for counts in messages.values()) for name, _ in TOKEN_FIELDS}
    # Cohort ranking uses input + output + cache writes; cache reads are informational only.
    totals["total_tokens"] = (
        totals["input_tokens"]
        + totals["output_tokens"]
        + totals["cache_creation_tokens"]
    )
    totals["messages"] = len(messages)
    return totals


def scan_main(path):
    """Return (main messages, inline subagent messages, minutes) for a main transcript."""
    main, inline = {}, {}
    first = last = None
    for entry in read_entries(path):
        if entry.get("type") not in ("user", "assistant"):
            continue
        if entry.get("isSidechain"):
            add_message(inline, entry)
            continue
        stamp = parse_timestamp(entry.get("timestamp"))
        if stamp:
            first = stamp if first is None or stamp < first else first
            last = stamp if last is None or stamp > last else last
        add_message(main, entry)
    minutes = round((last - first).total_seconds() / 60, 2) if first and last else 0.0
    return main, inline, minutes


def parse_transcript(path):
    """Total the main session in a transcript file.

    Counts only the main session: entries flagged isSidechain are skipped, so a
    subagent's tokens are not included. The transcript format is internal to
    Claude Code, so anything unexpected is ignored, not fatal.

    Raises OSError if the file cannot be read.
    """
    main, _, minutes = scan_main(path)
    totals = sum_messages(main)
    totals["minutes"] = minutes
    return totals


def belongs_to(path, session_id):
    """True if a transcript file's entries carry this session id."""
    try:
        for entry in read_entries(path):
            if "sessionId" in entry:
                return entry["sessionId"] == session_id
    except OSError:
        pass
    return False


def subagent_transcripts(path, session_id=None):
    """Return the subagent transcript files that belong to a main transcript.

    Claude Code 2.x keeps them in <session-id>/subagents/ beside the main
    transcript. Older versions wrote agent-<id>.jsonl next to it, tagged with
    the session id, so those count too when the id matches.
    """
    path = Path(path)
    session_id = session_id or path.stem
    found = sorted((path.parent / session_id / "subagents").glob("*.jsonl"))
    found += [older for older in sorted(path.parent.glob("agent-*.jsonl")) if belongs_to(older, session_id)]
    return found


def parse_session(path, session_id=None):
    """Total a session: the main transcript plus every subagent transcript.

    The top-level token fields and total_tokens are main + subagents. Minutes are
    the main session's wall-clock time; subagents run inside it. Each message id
    is counted once across all files. A subagent file that can't be read is
    skipped; a main transcript that can't be read raises OSError.
    """
    main, subagent, minutes = scan_main(path)
    files = subagent_transcripts(path, session_id)
    counted = 0
    for transcript in files:
        try:
            for entry in read_entries(transcript):
                message = entry.get("message")
                if isinstance(message, dict) and message.get("id") in main:
                    continue  # already counted as the main session's
                add_message(subagent, entry)
            counted += 1
        except OSError:
            continue
    main_totals, subagent_totals = sum_messages(main), sum_messages(subagent)
    totals = {name: main_totals[name] + subagent_totals[name]
              for name in [field for field, _ in TOKEN_FIELDS] + ["total_tokens", "messages"]}
    totals["main_total_tokens"] = main_totals["total_tokens"]
    totals["subagent_total_tokens"] = subagent_totals["total_tokens"]
    totals["subagents"] = counted
    totals["minutes"] = minutes
    return totals


def main():
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        totals = parse_session(event["transcript_path"], event["session_id"])
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
