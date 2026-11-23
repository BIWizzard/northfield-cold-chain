"""Block run_sql queries that could write, read raw readings, or return everything."""

import json
import sys


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        print("Provide a valid JSON hook event on stdin.", file=sys.stderr)
        return 2
    tool_input = event.get("tool_input") if isinstance(event, dict) else None
    query = tool_input.get("query") if isinstance(tool_input, dict) else None
    if not isinstance(query, str):
        query = ""

    # Lab 19: exit 2 with a one-line reason on stderr unless the query passes
    # every check below. `query` is the SQL text exactly as the tool received it.
    #
    # TODO 1. Strip `--` and `/* */` comments, and blank out quoted strings, so
    #         nothing hidden in either can change the checks that follow.
    # TODO 2. Allow one statement only (no `;` before the end).
    # TODO 3. The statement must start with SELECT or WITH, in any case.
    # TODO 4. No INSERT, UPDATE, DELETE, REPLACE, CREATE, DROP, ALTER, ATTACH,
    #         DETACH, PRAGMA or VACUUM as a whole word.
    # TODO 5. It must not name raw_readings.
    # TODO 6. It must have a WHERE or a LIMIT.
    return 0


if __name__ == "__main__":
    sys.exit(main())
