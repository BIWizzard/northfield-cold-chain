"""Print the latest session's total minutes and total tokens.

Total tokens is input plus output plus cache writes (cache reads are listed
separately), for the main session and every subagent it ran, with the two
shown separately. Reads metrics.jsonl, written by the hooks/lab_metrics.py Stop hook.
Run it from the repo root when your session is done:

    python tools/lab_metrics.py
"""

import argparse
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = ROOT / "hooks" / "lab_metrics.py"


def load_hook():
    """Load the hook module, so the hook and this script total a transcript the same way."""
    spec = importlib.util.spec_from_file_location("lab_metrics_hook", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def latest_record(metrics_file):
    """Return the last readable record in metrics.jsonl, or None."""
    latest = None
    try:
        lines = metrics_file.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict) and "session_id" in record:
            latest = record
    return latest


def format_report(record):
    lines = [
        f"Session: {record['session_id']}",
        f"Total minutes: {record['minutes']:.1f}",
        f"Total tokens: {record['total_tokens']:,}",
    ]
    if "subagent_total_tokens" in record:
        lines += [
            f"  Main session: {record['main_total_tokens']:,}",
            f"  Subagents ({record.get('subagents', 0)}): {record['subagent_total_tokens']:,}",
        ]
    return "\n".join(lines + [
        "",
        f"  Input:        {record['input_tokens']:,}",
        f"  Output:       {record['output_tokens']:,}",
        f"  Cache writes: {record['cache_creation_tokens']:,}",
        f"  Cache reads:  {record['cache_read_tokens']:,}",
    ])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=ROOT, help="folder holding metrics.jsonl")
    args = parser.parse_args(argv)
    record = latest_record(args.project / "metrics.jsonl")
    if record is None:
        print("No metrics yet. Start a session on a solution branch, let Claude respond "
              "at least once, then run this again.")
        return 1
    # The hook runs as Claude finishes, and the transcript can lag a turn behind, so
    # total the transcript again now. If it is gone, fall back to the saved totals.
    try:
        totals = load_hook().parse_session(record["transcript_path"], record.get("session_id"))
        record = {**record, **totals}
    except (OSError, KeyError):
        pass
    print(format_report(record))
    return 0


if __name__ == "__main__":
    sys.exit(main())
