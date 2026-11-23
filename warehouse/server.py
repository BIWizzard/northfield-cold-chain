"""Northfield warehouse: a stdio MCP server over warehouse/northfield.db.

Newline-delimited JSON-RPC on stdin and stdout. Logs only to stderr.
Standard library only. The database is opened read-only, so no tool can
write the database, and an authorizer refuses ATTACH and VACUUM INTO, so no
tool can write a file either, whatever the SQL says.
"""

import json
import os
from pathlib import Path
import sqlite3
import sys
import time


DB_PATH = Path(__file__).resolve().parent / "northfield.db"
SERVER_INFO = {"name": "northfield-warehouse", "version": "1.0.0"}
DEFAULT_PROTOCOL = "2025-06-18"
ROW_CAP = 200
DEFAULT_LIMIT = 50
# A query that runs longer than this is stopped. The server answers one call at
# a time, so one runaway query would otherwise block every call behind it.
QUERY_TIMEOUT_SECONDS = float(os.environ.get("WAREHOUSE_QUERY_TIMEOUT", "5"))
PROGRESS_STEPS = 10_000  # SQLite virtual-machine steps between timeout checks


def deny_attach(action, *_):
    """Authorizer: refuse ATTACH, which also covers VACUUM INTO.

    mode=ro protects the database file, not the filesystem: ATTACH DATABASE and
    VACUUM INTO can create files anywhere the process can write.
    """
    return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_ATTACH else sqlite3.SQLITE_OK


def connect():
    connection = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    connection.set_authorizer(deny_attach)
    return connection


class CappedRows(list):
    """Rows from a capped query; `truncated` says the query had more rows."""

    truncated = False


def query_rows(sql, params=(), cap=None):
    """Run one query and return its rows as a list of dicts.

    With `cap`, returns at most that many rows and sets `truncated` on the
    result when the query had more. A query that runs past the timeout is
    stopped and raises sqlite3.OperationalError.
    """
    connection = connect()
    deadline = time.monotonic() + QUERY_TIMEOUT_SECONDS
    # A nonzero return from the progress handler aborts the running statement.
    connection.set_progress_handler(lambda: time.monotonic() > deadline, PROGRESS_STEPS)
    try:
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(sql, params)
        if not cap:
            return [dict(row) for row in cursor.fetchall()]
        fetched = cursor.fetchmany(cap + 1)
        rows = CappedRows(dict(row) for row in fetched[:cap])
        rows.truncated = len(fetched) > cap
        return rows
    except sqlite3.OperationalError as error:
        if time.monotonic() > deadline and str(error) == "interrupted":
            raise sqlite3.OperationalError(
                f"query stopped after {QUERY_TIMEOUT_SECONDS:g} seconds;"
                " add a WHERE or LIMIT, or make it smaller") from None
        raise
    finally:
        connection.close()


def get_shipment(arguments):
    shipment_id = arguments["shipment_id"]
    rows = query_rows(
        "SELECT s.*, c.name AS carrier_name,"
        " l.origin || ' to ' || l.destination AS route"
        " FROM shipments s"
        " LEFT JOIN carriers c ON c.carrier_id = s.carrier_id"
        " LEFT JOIN lanes l ON l.lane_id = s.lane_id"
        " WHERE s.shipment_id = ? ORDER BY s.rowid",
        (shipment_id,),
    )
    notes = query_rows(
        "SELECT * FROM carrier_notes WHERE shipment_id = ? ORDER BY note_date",
        (shipment_id,),
    )
    for row in rows:
        row["carrier_notes"] = notes
    return rows


def list_shipments(arguments):
    clauses, params = [], []
    for field in ("carrier_id", "lane_id", "week"):
        if arguments.get(field):
            clauses.append(f"{field} = ?")
            params.append(arguments[field])
    if arguments.get("date_from"):
        clauses.append("ship_date >= ?")
        params.append(arguments["date_from"])
    if arguments.get("date_to"):
        clauses.append("ship_date <= ?")
        params.append(arguments["date_to"])
    limit = int(arguments.get("limit") or DEFAULT_LIMIT)
    if limit < 1:
        raise ValueError("limit must be 1 or more")
    limit = min(limit, ROW_CAP)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return query_rows(
        f"SELECT * FROM shipments{where} ORDER BY shipment_id, rowid LIMIT ?",
        (*params, limit),
    )


def get_readings(arguments):
    return query_rows(
        "SELECT timestamp, temp_c FROM raw_readings WHERE shipment_id = ?"
        " ORDER BY timestamp",
        (arguments["shipment_id"],),
    )


def list_carriers(_arguments):
    return query_rows("SELECT * FROM carriers ORDER BY carrier_id")


def list_lanes(_arguments):
    return query_rows("SELECT * FROM lanes ORDER BY lane_id")


def run_sql(arguments):
    return query_rows(arguments["query"], cap=ROW_CAP)


def schema(properties=None, required=()):
    return {"type": "object", "properties": properties or {}, "required": list(required)}


SHIPMENT_ID = {"type": "string", "description": "Shipment ID, such as SHP-0001"}

TOOLS = {
    "get_shipment": (
        get_shipment,
        "Every shipment row with this ID, with carrier name, lane route and carrier notes.",
        schema({"shipment_id": SHIPMENT_ID}, ["shipment_id"]),
    ),
    "list_shipments": (
        list_shipments,
        "List shipments. Filter by carrier_id, lane_id, week, or ship_date range"
        " (YYYY-MM-DD). Default 50 rows, at most 200.",
        schema({
            "carrier_id": {"type": "string"},
            "lane_id": {"type": "string"},
            "week": {"type": "string", "description": "For example week-01"},
            "date_from": {"type": "string"},
            "date_to": {"type": "string"},
            "limit": {"type": "integer"},
        }),
    ),
    "get_readings": (
        get_readings,
        "A shipment's logger readings (UTC timestamps, temp_c).",
        schema({"shipment_id": SHIPMENT_ID}, ["shipment_id"]),
    ),
    "list_carriers": (list_carriers, "All carriers.", schema()),
    "list_lanes": (list_lanes, "All lanes.", schema()),
    "run_sql": (
        run_sql,
        "Run one read-only SQL query. Returns up to 200 rows as JSON, with a note when"
        " there were more, or the SQLite error. A query that runs over 5 seconds is stopped.",
        schema({"query": {"type": "string"}}, ["query"]),
    ),
}


def tool_list():
    return [
        {"name": name, "description": description, "inputSchema": input_schema}
        for name, (_handler, description, input_schema) in TOOLS.items()
    ]


def text_result(text, is_error=False):
    result = {"content": [{"type": "text", "text": text}]}
    if is_error:
        result["isError"] = True
    return result


def call_tool(params):
    name = params.get("name")
    if name not in TOOLS:
        return text_result(f"Unknown tool: {name}", True)
    arguments = params.get("arguments")
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        return text_result("Bad arguments: expected a JSON object", True)
    try:
        rows = TOOLS[name][0](arguments)
    except sqlite3.Error as error:
        return text_result(f"SQLite error: {error}", True)
    except (KeyError, TypeError, ValueError) as error:
        return text_result(f"Bad arguments: {error!r}", True)
    result = text_result(json.dumps(rows, default=str))
    if getattr(rows, "truncated", False):
        result["content"].append({"type": "text", "text": (
            f"Only the first {ROW_CAP} rows are shown; the query returned more."
            " Add a WHERE or LIMIT to see the rest.")})
    return result


def handle(message):
    """Return the response for one request, or None for a notification."""
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}
    if request_id is None:
        return None
    if method == "initialize":
        result = {
            "protocolVersion": params.get("protocolVersion", DEFAULT_PROTOCOL),
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }
    elif method == "tools/list":
        result = {"tools": tool_list()}
    elif method == "tools/call":
        result = call_tool(params)
    else:
        return {
            "jsonrpc": "2.0", "id": request_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def serve():
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            print("ignored unparseable input", file=sys.stderr)
            continue
        response = handle(message)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


def self_test():
    initialize = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                         "params": {"protocolVersion": DEFAULT_PROTOCOL}})
    assert "tools" in initialize["result"]["capabilities"]
    listing = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    for tool in listing["result"]["tools"]:
        print(tool["name"])


if __name__ == "__main__":
    if "--self-test" in sys.argv[1:]:
        self_test()
    else:
        serve()
